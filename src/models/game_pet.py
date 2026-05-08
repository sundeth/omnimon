from datetime import datetime
import time
import pygame
import random

from core import game_globals, runtime_globals
from models.animation import Animation, PetFrame
import core.constants as constants
from models.game_digidex import register_digidex_entry
from utils.sprite_utils import load_pet_sprites, convert_sprites_to_list
from models.game_poop import GamePoop
from utils.module_utils import get_module
from utils.pygame_utils import blit_with_cache, sprite_load
from utils.scene_utils import change_scene
from utils.utils_unlocks import is_unlocked, unlock_item
from utils.asset_utils import image_load


class GamePet:
    def __init__(self, pet_data, traited = False):
        self.hunger = self.strength = self.age = self.injuries = self.poop_count_flag = self.weight = 0
        self.totalWin = self.totalBattles = 0

        self.traited = traited
        self.shiny = False
        self.shook = False
        self.edited = False

        # Real-time gameplay timers (seconds via time.monotonic)
        _now = time.monotonic()
        self._rt_origin = _now        # Base for per-minute tick detection
        self._rt_last_minute = 0      # Last processed minute count since _rt_origin
        self._rt_last_sleep_check = _now
        self._rt_dead_start = 0.0     # When pet entered dead state (0 = not dead)
        self._last_age_date = datetime.now().date()  # Age increments at midnight
        # Countdown/countup gameplay counters (initialized properly in reset_variables)
        self._evol_minutes = 0
        self._cd_hunger = 0
        self._cd_strength = 0
        self._cd_poop = 0

        self.set_data(pet_data)
        self.reset_variables()
        self.load_sprite()
        self.begin_position()

        self.state = ""
        self.set_state("idle")
        
        self.direction = -1
        self.injuries = 0
        self.move_timer = random.randint(60, 120)

        self.sleep_start_time = None
        self.sleep_timer = 0 
        self.back_to_sleep = 0

        self.dying = False

        self.level = 1
        self.experience = 0
        self.gcell_fragment = False
        self.vital_activities = []
        self.evolution_history = []  # Names of prior forms, oldest first

        self.bonus_stats = [0, 0, 0]  # HP, ATK, POWER bonuses from items

    def set_data(self, data):
        self.module = data["module"]
        self.name = data["name"]
        self.stage = data["stage"]
        self.version = data["version"]
        self.special = data["special"]
        self.index = data.get("index", 0)
        if self.special:
            self.special_key = data.get("special_key")
        else:
            self.special_key = None
        self.evolve = data["evolve"]
        self.sleeps = data.get("sleeps")
        self.wakes = data.get("wakes")
        self.atk_main = data.get("atk_main", 0)
        self.atk_alt = data.get("atk_alt", 0)
        if self.atk_alt == 0:
            self.atk_alt = self.atk_main
        self.atk_alt_2 = data.get("atk_alt_2", 0)
        self.time = data.get("time", 0)
        self.poop_timer = data.get("poop_timer", 60)
        self.min_weight = data.get("min_weight")
        self.evol_weight = data.get("evol_weight", 0)
        self.stomach = data.get("stomach")
        self.hunger_loss = data.get("hunger_loss")
        self.strength_loss = data.get("strength_loss")
        self.power = data.get("power")
        self.attribute = data.get("attribute")
        self.energy = data.get("energy")

        self.heal_doses = data.get("heal_doses", 1)
        self.hp = data.get("hp", 0)
        self.star = data.get("star", 0)
        self.attack = data.get("attack", 1)
        self.critical_turn = data.get("critical_turn", 0)

        self.condition_hearts_max = int(data.get("condition_hearts", 0))
        self.jogress_avaliable = int(data.get("jogress_avaliable", 0))


    def reset_variables(self):
        self.timer = 0  # Kept for animation/frame counting only
        if self.evol_weight > 0:
            self.weight = self.evol_weight
        if self.weight < self.min_weight:
            self.weight = self.min_weight
        self.dp = self.energy
        self.effort = 0
        self.sick = 0
        self.level = 1
        self.experience = 0
        self.win = self.battles = 0
        self.animation_counter = self.frame_counter = self.frame_index = 0
        self.care_food_mistake_timer = self.care_strength_mistake_timer = self.care_sleep_mistake_timer = self.care_sick_mistake_timer = 0

        # Reset real-time gameplay timers (NOT _last_age_date — age persists across evolutions)
        _now = time.monotonic()
        self._rt_origin = _now
        self._rt_last_minute = 0
        self._rt_dead_start = 0.0
        self._rt_last_sleep_check = _now
        # Countdown counters: start at max, tick down 1/min, trigger & reset at 0
        self._cd_hunger = self.hunger_loss or 0
        self._cd_strength = self.strength_loss or 0
        self._cd_poop = self.poop_timer or 0
        # Evolution count-up: starts at 0, increments 1/min, checks conditions after reaching self.time
        self._evol_minutes = 0
        self.special_encounter = False

        self.enemy_kills = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.injuries = 0
        self.starvation_counter = 0
        self.disturbance_penalty = 0
        self.overfeed_timer = 0
        self.protein_feedings = 0
        self.protein_overdose = 0
        self.shake_counter = 0
        self.pvp_wins = 0
        self.pvp_battles = 0
        
        # Death save system variables
        self.death_save_b_counter = 0
        self.death_save_shake_counter = 0
        self.death_save_immunity = 0
        self.death_cause = ""  # tracks what triggered death: injuries, sickness, hunger, strength, care_mistakes, starvation, old_age, stage_mistakes

        self.quests_completed = 0

        self.trophies = 0
        self.vital_values = 100
        self.overfeed = 0
        self.sleep_disturbances = 0

        module = get_module(self.module)

        if self.traited:
            self.level = module.traited_egg_starting_level

        self.use_condition_hearts = module.use_condition_hearts
        if self.use_condition_hearts:
            self.condition_hearts = self.condition_hearts_max
        self.mistakes = 0

        self.gcell_points = 0

        self._99g_triggered = False
        self.sick_type = ""
        self.burpmon_active = False

    def begin_position(self):
        self.subpixel_x = float(runtime_globals.SCREEN_WIDTH - runtime_globals.PET_WIDTH) / 2
        self.x = int(self.subpixel_x)
        # Old formula did not work well when MAX_PETS != 4:
        # self.y = (24 * runtime_globals.UI_SCALE) + (runtime_globals.SCREEN_HEIGHT - runtime_globals.PET_HEIGHT) // 2
        # New formula keeps the placement of the bottom of the sprite in the same place for most MAX_PETS as the previous
        # formula for MAX_PETS = 4. Slight offset to sprite for MAX_PETS <= 2 as to not overlap the top menu icons.
        if constants.MAX_PETS > 2:
            self.y = int(174 * runtime_globals.UI_SCALE - runtime_globals.PET_HEIGHT)
        else:
            self.y = int(190 * runtime_globals.UI_SCALE - runtime_globals.PET_HEIGHT - 5)
        self.x_range = (0, runtime_globals.SCREEN_WIDTH - runtime_globals.PET_WIDTH)

    def get_sprite(self, index):
        return runtime_globals.pet_sprites[self][index]

    def set_state(self, new_state, force=False):
        if self.state == "dead":
            return
        if self.state == "dying" and new_state not in ("dead", "happy2", "dying"):
            return
        if self.stage == 0 and new_state not in ("idle", "hatch"):
            return

        if self.state != new_state or force:
            self.state = new_state
            self.animation_counter = 0
            self.animation_frames = getattr(Animation, new_state.upper(), Animation.IDLE)
            self.frame_index = self.frame_counter = self.animation_counter = 0
            
            # Mark as dirty when state changes since overlays may change
            if hasattr(self, 'dirty'):
                self.dirty = True
            
            runtime_globals.game_console.log(f"{self.name} status {self.state}")

            if self.state == "nap" and self.should_sleep() and new_state != "nap":
                self.set_back_to_sleep()

            # Handle sleeping
            if new_state == "nap":
                from datetime import datetime
                self.sleep_start_time = datetime.now()
                self.sleep_timer = 0
            elif self.state == "idle":
                self.sleep_start_time = None
                self.sleep_timer = 0

    def load_sprite(self):
        """Loads animation frames for the pet using the new sprite loading utility."""
        # Get module object to access folder_path and name_format
        module_obj = get_module(self.module)
        if not module_obj:
            runtime_globals.game_console.log(f"Module {self.module} not found for pet {self.name}")
            return
        
        # Get module properties
        module_path = module_obj.folder_path
        name_format = getattr(module_obj, 'name_format', '$_dmc')
        primary_format = getattr(module_obj, 'primary_sprite_format', 'Color')
        secondary_format = getattr(module_obj, 'secondary_sprite_format', 'HD')
        
        # Load sprites using the new utility function with format parameters
        sprites_dict = load_pet_sprites(
            self.name, 
            module_path, 
            name_format,
            size=(runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT),
            primary_sprite_format=primary_format,
            secondary_sprite_format=secondary_format
        )
        
        # Convert to list format expected by existing code
        sprite_list = convert_sprites_to_list(sprites_dict)
        
        # If no sprites found at all, create fallback white squares
        if not sprite_list or all(s is None for s in sprite_list):
            runtime_globals.game_console.log(f"[Pet] No sprites found for {self.name}, creating fallback")
            fallback_sprite = pygame.Surface((runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT))
            fallback_sprite.fill((255, 255, 255))  # White square
            sprite_list = [fallback_sprite] * 20
        
        runtime_globals.pet_sprites[self] = sprite_list
        
        # Apply frame swapping if needed for modules with reverse_atk_frames
        if module_obj.reverse_atk_frames:
            sprites = runtime_globals.pet_sprites[self]
            # Swap TRAIN1 <-> TRAIN2 and ATK1 <-> ATK2
            if len(sprites) > 6:
                sprites[PetFrame.TRAIN1.value], sprites[PetFrame.TRAIN2.value] = sprites[PetFrame.TRAIN2.value], sprites[PetFrame.TRAIN1.value]
                sprites[PetFrame.ATK1.value], sprites[PetFrame.ATK2.value] = sprites[PetFrame.ATK2.value], sprites[PetFrame.ATK1.value]
            runtime_globals.pet_sprites[self] = sprites

        # If pet was saved as Burpmon, restore that sprite
        if getattr(self, 'burpmon_active', False):
            self._load_burpmon_sprite()

    def draw(self, surface):
        # Get base frame; skip if missing
        sprite_list = runtime_globals.pet_sprites.get(self)
        if not sprite_list:
            return
        
        frame_key = self.animation_frames[self.frame_index].value
        frame = sprite_list[frame_key]
        
        # Flip if facing right
        if self.direction == 1:
            frame = pygame.transform.flip(frame, True, False)
        
        # Draw base pet sprite
        blit_with_cache(surface, frame, (self.x, self.y))
        
        # Determine overlay, if any (dead pets show no overlays)
        overlay = None
        anim_phase = (self.animation_counter // constants.FRAME_RATE) % 2  # precompute phase

        sick = False

        # Dot-format modules have their own Sick/Cheer overlays (coloured pixels
        # instead of the default black-on-transparent ones).
        # Only use dot overlays when enable_old_sprites is active.
        module = get_module(self.module)
        enable_old = getattr(game_globals.configuration, 'enable_old_sprites', False)
        is_dot = enable_old and getattr(module, "primary_sprite_format", "Color") == "Dot"

        def _misc(name):
            """Return the Dot variant of a misc sprite when enabled, else the default."""
            if is_dot:
                dot = runtime_globals.misc_sprites.get(f"{name}_dot")
                if dot:
                    return dot
            return runtime_globals.misc_sprites.get(name)

        if self.state != "dead":
            if self.state == "nap":
                overlay = runtime_globals.misc_sprites.get(f"Sleep{anim_phase + 1}")
            elif self.state in {"happy2", "happy3"} and anim_phase == 0:
                overlay = _misc("Cheer")
            elif self.sick > 0:
                if getattr(self, 'sick_type', '') == "dots":
                    overlay = runtime_globals.misc_sprites.get(f"Dots{anim_phase + 1}")
                else:
                    overlay = _misc(f"Sick{anim_phase + 1}")
                sick = True
            elif self.state == "angry":
                overlay = runtime_globals.misc_sprites.get(f"Mad{anim_phase + 1}")
            elif getattr(self, "dying", False) or self.death_save_b_counter > 0 or self.death_save_shake_counter > 0:
                overlay = _misc(f"Sick{anim_phase + 1}")

        if overlay:
            x = self.x + runtime_globals.PET_WIDTH
            # Prevent overlay from overlapping menu icons
            y_offset = 20 * runtime_globals.UI_SCALE if game_globals.showClock else 5 * runtime_globals.UI_SCALE
            icon_size = 2 * runtime_globals.MENU_ICON_SIZE
            y_min = y_offset + icon_size
            y = max(y_min, self.y - (runtime_globals.PET_WIDTH // 2))
            if self.state in ["happy2", "happy3"]:
                y = self.y
            base_pos = (x, y)
            blit_with_cache(surface, overlay, base_pos)
            
            if self.state == "happy3" and not sick:
                blit_with_cache(surface, overlay, (x, y + (24 * runtime_globals.UI_SCALE)))
                blit_with_cache(surface, overlay, (x - runtime_globals.PET_WIDTH - (24 * runtime_globals.UI_SCALE), y))
                blit_with_cache(surface, overlay, (x - runtime_globals.PET_WIDTH - (24 * runtime_globals.UI_SCALE), y + (24 * runtime_globals.UI_SCALE)))

    def update(self):
        self.timer += 1
        self.update_animation()
        self.update_cache()

        # Frame-based state handling (animation/movement)
        if self.state in ("moving", "idle"):
            self.update_idle_movement()
        elif self.state == "nap":
            self.sleep_timer += 1
            self.check_wake_up()
        elif self.state == "pooping":
            if self.frame_counter in [0, int(6 * (constants.FRAME_RATE / 30))]:
                self.x += int(2 * runtime_globals.UI_SCALE)
                if hasattr(self, 'dirty'):
                    self.dirty = True
            elif self.frame_counter in [int(3 * (constants.FRAME_RATE / 30)), int(9 * (constants.FRAME_RATE / 30))]:
                self.x -= int(2 * runtime_globals.UI_SCALE)
                if hasattr(self, 'dirty'):
                    self.dirty = True

            if self.animation_counter == int(15 * (constants.FRAME_RATE / 30)):
                self.poop()

        # --- Real-time gameplay ticks ---
        now = time.monotonic()

        # Sleep check (~every 0.5s real-time)
        if now - self._rt_last_sleep_check >= 0.5:
            self._rt_last_sleep_check = now
            if self.state in ("moving", "idle") and self.should_sleep():
                self.set_state("tired")

        # Age at midnight
        today = datetime.now().date()
        if today > self._last_age_date:
            self.age += (today - self._last_age_date).days
            self._last_age_date = today
            runtime_globals.game_console.log(f"{self.name} aged to {self.age}")

        # Per-minute gameplay tick
        elapsed_min = int((now - self._rt_origin) / 60)
        if elapsed_min > self._rt_last_minute:
            minutes_passed = elapsed_min - self._rt_last_minute
            old_hour = self._rt_last_minute // 60
            self._rt_last_minute = elapsed_min

            if self.state not in ("nap", "dead"):
                self._evol_minutes += minutes_passed
                self.update_evolution()
                self.update_needs(minutes_passed)
                self.update_pooping(minutes_passed)
                self.update_care_mistakes()
                self.update_vital_values_loss()
            elif self.state == "nap" and getattr(get_module(self.module), 'count_evolution_while_sleeping', True):
                self._evol_minutes += minutes_passed
                self.update_evolution()
            if self.state != "nap":
                self.update_death_save_counters()
                self.update_death_check(now)

                if self.death_save_immunity > 0:
                    self.death_save_immunity -= 1
                    if self.death_save_immunity == 0:
                        runtime_globals.game_console.log(f"[Death Save] {self.name} immunity expired!")

            if self.back_to_sleep > 0:
                self.back_to_sleep -= 1
                if self.back_to_sleep == 0 and self.state != "nap" and self.should_sleep():
                    self.set_state("nap")

            # Per-hour tick
            new_hour = elapsed_min // 60
            if new_hour > old_hour:
                if self.state not in ("nap", "dead"):
                    self.update_vital_values_gain()

    def update_cache(self):
        # Check for changes that require cache invalidation
        frame_key = self.animation_frames[self.frame_index].value
        
        # Determine if there's an overlay (same logic as in draw method)
        anim_phase = (self.animation_counter // constants.FRAME_RATE) % 2
        has_overlay = self.state != "dead" and (
            self.state == "nap" or
            (self.state in {"happy2", "happy3"} and anim_phase == 0) or
            self.sick > 0 or
            self.state == "angry" or
            getattr(self, "dying", False)
        )
        
        # Mark as dirty if position, frame, or overlay state changed
        if (hasattr(self, 'cache_x') and hasattr(self, 'cache_frame_index') and hasattr(self, 'cache_has_overlay')):
            if (self.cache_x != self.x or 
                self.cache_frame_index != frame_key or 
                self.cache_has_overlay != has_overlay):
                self.dirty = True
        else:
            # First time setup
            self.dirty = True
        
        # Update cache values
        self.cache_x = self.x
        self.cache_frame_index = frame_key
        self.cache_has_overlay = has_overlay

    def update_idle_movement(self):
        if self.stage == 0 or self.state in ("nap", "dying"):
            return

        self.move_timer -= 1
        # Determine if we should move
        move_chance = (1 - constants.IDLE_PROBABILITY)

        if self.move_timer <= 0:
            if self.state == "idle" and random.random() < 0.30:
                self.set_state("sick" if self.sick > 0 else ("happy" if not self.need_care() else "angry"))
                self.move_timer = random.randint(60, 120)
                return

            if random.random() < move_chance:
                self.set_state("moving")
                self.direction = random.choice([-1, 1])
                self.move_timer = random.randint(20, 60)
            else:
                self.set_state("idle")
                self.move_timer = random.randint(90, 180)

        # Move in sync with frame updates (choppy movement)
        if self.state == "moving" and self.frame_counter % int(constants.FRAME_RATE / 3) == 0:  # move only when animation frame updates
            step = random.choice([2, 6])
            old_x = self.x
            self.x += (step * (runtime_globals.SCREEN_WIDTH / 240)) * self.direction
            if self.x <= self.x_range[0]:
                self.x = self.x_range[0]
                self.direction = 1
            elif self.x >= self.x_range[1]:
                self.x = self.x_range[1]
                self.direction = -1
            
            # Mark as dirty if position actually changed
            if old_x != self.x and hasattr(self, 'dirty'):
                self.dirty = True

    def update_animation(self):
        # Handle special 'nope' animation with direction flip
        if self.state == "nope" and self.timer % constants.FRAME_RATE == 0:
            self.direction *= -1

        # Choppy animation sync for movement
        if self.state == "moving":
            # Move every N frames, same as movement (e.g., every 15 frames)
            self.frame_counter += 1
            if self.frame_counter % ( constants.FRAME_RATE // 3) == 0:
                self.frame_index = (self.frame_index + 1) % len(self.animation_frames)
        else:
            # Regular animation update for non-moving states
            self.frame_counter += 1
            if self.frame_counter > (constants.FRAME_RATE // 2):
                self.frame_counter = 0
                self.frame_index = (self.frame_index + 1) % len(self.animation_frames)

        # Handle timed state resets
        self.animation_counter += 1
        if self.state not in ("moving", "idle", "nap", "dead"):
            if self.state != "nap" and self.animation_counter > int(4 * constants.FRAME_RATE):
                self.set_state("happy"if self.state == "eat" else "idle")

        # Handle hatching animation (real-time: within 5 seconds of evolution time)
        if self.stage == 0:
            elapsed_sec = time.monotonic() - self._rt_origin
            if elapsed_sec - (self.time * 60) >= -5:
                self.set_state("hatch")

    def evolve_to(self, name, version):
        runtime_globals.game_console.log(f"Evolving to {name}")
        runtime_globals.game_sound.play("evolution")
        if not hasattr(self, 'evolution_history'):
            self.evolution_history = []
        self.evolution_history.append(self.name)
        module = get_module(self.module)
        pet_data = module.get_monster(name, version)
        pet_data["module"] = module.name
        self.set_data(pet_data)
        self.reset_variables()
        self.load_sprite()
        self.set_state("happy1")
        register_digidex_entry(self.name, module.name, self.version)

    def armor_evolve(self, item_name):
        """Evolve the pet using an armor item (digimental).
        
        Args:
            item_name: The name of the armor item (must match evolution's "item" field)
        """
        runtime_globals.game_console.log(f"[GamePet] Armor evolving with {item_name}")
        
        # Find evolution with matching item requirement
        for evo in self.evolve:
            if "item" in evo and evo["item"] == item_name:
                target_name = evo["to"]
                target_version = evo.get("version", self.version)
                runtime_globals.game_console.log(f"[GamePet] Armor evolution found: {target_name} (version {target_version})")
                self.evolve_to(target_name, target_version)
                return
        
        runtime_globals.game_console.log(f"[GamePet] Warning: No armor evolution found for {item_name}")

    def force_poop(self):
        self.set_state("pooping")

    def poop(self):
        # Get module for care settings
        module = get_module(self.module)
        cfg = game_globals.configuration
        module_primary_format = getattr(module, "primary_sprite_format", "Color") if module else "Color"
        use_dot_poop_sprite = bool(getattr(cfg, "enable_old_sprites", False) and module_primary_format == "Dot")
        
        # care_poop_alarm: play sound on poop if True (default True for backwards compatibility)
        care_poop_alarm = getattr(module, 'care_poop_alarm', True)
        if care_poop_alarm:
            runtime_globals.game_sound.play("cancel")
        
        # care_poop_chance: [single, double, triple, giga] percentages
        # Default: [80, 0, 0, 20] for backwards compatibility (80% single, 20% giga/jumbo)
        care_poop_chance = getattr(module, 'care_poop_chance', [80, 0, 0, 20])
        
        # Normalize chances to ensure we have 4 values
        if len(care_poop_chance) < 4:
            care_poop_chance = care_poop_chance + [0] * (4 - len(care_poop_chance))
        
        # Calculate cumulative probabilities
        total = sum(care_poop_chance)
        if total <= 0:
            total = 100
            care_poop_chance = [100, 0, 0, 0]  # Default fallback
        
        roll = random.random() * total
        cumulative = 0
        poop_type = 0  # 0=single, 1=double, 2=triple, 3=giga
        
        for i, chance in enumerate(care_poop_chance):
            cumulative += chance
            if roll < cumulative:
                poop_type = i
                break
        
        # Calculate base position for poop
        base_x = (12 * runtime_globals.UI_SCALE) + self.x + (constants.FRAME_SIZE // 2)
        base_y = self.y + (runtime_globals.PET_HEIGHT - (24 * runtime_globals.UI_SCALE))
        
        # Create poop(s) based on type
        if poop_type == 0:  # Single
            game_globals.poop_list.append(GamePoop(base_x, base_y, use_dot_sprite=use_dot_poop_sprite))
        elif poop_type == 1:  # Double
            game_globals.poop_list.append(GamePoop(base_x - (12 * runtime_globals.UI_SCALE), base_y, use_dot_sprite=use_dot_poop_sprite))
            game_globals.poop_list.append(GamePoop(base_x + (12 * runtime_globals.UI_SCALE), base_y, use_dot_sprite=use_dot_poop_sprite))
        elif poop_type == 2:  # Triple
            game_globals.poop_list.append(GamePoop(base_x - (18 * runtime_globals.UI_SCALE), base_y, use_dot_sprite=use_dot_poop_sprite))
            game_globals.poop_list.append(GamePoop(base_x, base_y, use_dot_sprite=use_dot_poop_sprite))
            game_globals.poop_list.append(GamePoop(base_x + (18 * runtime_globals.UI_SCALE), base_y, use_dot_sprite=use_dot_poop_sprite))
        elif poop_type == 3:  # Giga (jumbo)
            giga_y = self.y + (runtime_globals.PET_HEIGHT - (48 * runtime_globals.UI_SCALE))
            game_globals.poop_list.append(GamePoop(base_x, giga_y, jumbo=True, use_dot_sprite=use_dot_poop_sprite))
        
        if self.weight > self.min_weight:
            self.weight -= 1
        self.update_99g_effect()
        self.set_state("idle")

    def check_death_conditions(self):
        if self.state in ["nap", "dead"]:
            return False

        result = False
        death_cause = ""

        module = get_module(self.module)

        # 1. 15 ou mais ferimentos em uma forma
        if module.death_max_injuries > 0 and self.injuries >= module.death_max_injuries:
            result = True
            death_cause = "injuries"

        # 2. Ficou ferido por 6h contínuas (sem curar)
        if module.death_sick_timer > 0 and self.care_sick_mistake_timer > module.death_sick_timer:
            result = True
            death_cause = "sickness"

        # 3. Fome OU força vazia por 12h contínuas
        if module.death_hunger_timer > 0 and self.care_food_mistake_timer > module.death_hunger_timer:
            result = True
            death_cause = "hunger"
        if module.death_strength_timer > 0 and self.care_strength_mistake_timer > module.death_strength_timer:
            result = True
            death_cause = "strength"

        # 4. Stage IV ou V + 5+ erros após fim do tempo de evolução
        if self.stage in [4, 5] and module.death_stage45_mistake > 0 and self.mistakes >= module.death_stage45_mistake:
            if self._evol_minutes > self.time:
                result = True
                death_cause = "stage_mistakes"

        # 5. Stage VI ou VI+ + 5+ erros após 2 days
        if self.stage >= 6 and module.death_stage67_mistake > 0 and self.mistakes >= module.death_stage67_mistake:
            if self.age >= 2:
                result = True
                death_cause = "stage_mistakes"

        if module.death_starvation_count > 0 and self.starvation_counter > module.death_starvation_count:
            result = True
            death_cause = "starvation"

        if module.death_care_mistake > 0 and self.mistakes >= module.death_care_mistake:
            result = True
            death_cause = "care_mistakes"

        # Old age overrides all other causes and cannot be saved
        if module.death_old_age > 0 and self.age >= module.death_old_age:
            return True

        # Old age death cannot be saved
        if result and death_cause == "old_age":
            return True

        # Death save system - activate if death conditions met and not immune
        if result and self.death_save_immunity == 0 and not self.dying:
            has_save_method = module.death_save_by_b_press > 0 or module.death_save_by_shake > 0
            if has_save_method:
                self.death_cause = death_cause
                self.dying = True
                self.set_state("dying")
                runtime_globals.game_sound.play("death")
                if module.death_save_by_b_press > 0 and self.death_save_b_counter == 0:
                    self.death_save_b_counter = module.death_save_by_b_press
                    runtime_globals.game_console.log(f"[Death Save] {self.name} needs {module.death_save_by_b_press} B presses in 60 seconds! Cause: {death_cause}")
                elif module.death_save_by_shake > 0 and self.death_save_shake_counter == 0:
                    self.death_save_shake_counter = module.death_save_by_shake
                    runtime_globals.game_console.log(f"[Death Save] {self.name} needs {module.death_save_by_shake} shakes in 60 seconds! Cause: {death_cause}")
                return False

        return result

    def update_death_save_counters(self):
        """Update death save counters and handle success/failure."""
        if self.dying:
            if self.death_save_b_counter <= 0 and self.death_save_shake_counter <= 0:
                # Successfully saved! Negate death trigger based on cause
                module = get_module(self.module)
                cause = getattr(self, 'death_cause', '')
                if cause == "injuries":
                    self.injuries = max(0, self.injuries - 1)
                elif cause == "sickness":
                    self.sick = 0
                    self.care_sick_mistake_timer = 0
                elif cause == "hunger":
                    self.care_food_mistake_timer = 0
                elif cause == "strength":
                    self.care_strength_mistake_timer = 0
                elif cause == "starvation":
                    self.starvation_counter = max(0, self.starvation_counter - 1)
                elif cause in ("care_mistakes", "stage_mistakes"):
                    self.mistakes = max(0, self.mistakes - 1)
                self.death_save_immunity = 60  # 60 minutes
                self.death_save_b_counter = 0
                self.death_save_shake_counter = 0
                self.dying = False
                self.death_cause = ""
                self.set_state("happy2")
                runtime_globals.game_sound.play("happy")
                runtime_globals.game_console.log(f"[Death Save] {self.name} was saved (cause: {cause})! 60-minute immunity granted.")

    def update_death_check(self, now=None):
        """Checks pet death conditions and updates the sprite accordingly."""
        if now is None:
            now = time.monotonic()
        if self.check_death_conditions() and self.death_save_immunity == 0:
            # Pet dies (either no save method or save timer expired)
            module = get_module(self.module)
            has_save_method = module.death_save_by_b_press > 0 or module.death_save_by_shake > 0
            if has_save_method:
                runtime_globals.game_sound.play("fail")
            else:
                runtime_globals.game_sound.play("death")
            self.dying = False
            self.death_cause = ""
            self.set_state("dead")
            self.burpmon_active = False

            dead_sprite = sprite_load(constants.DEAD_FRAME_PATH, size=(runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT))
            runtime_globals.pet_sprites[self][0] = dead_sprite
            runtime_globals.pet_sprites[self][1] = dead_sprite

            self._rt_dead_start = now

        # Remove pet from game if dead for 5 minutes (real-time)
        if self.state == "dead" and self._rt_dead_start > 0 and now - self._rt_dead_start > 300:
            if self in game_globals.pet_list:
                game_globals.pet_list.remove(self)
                del runtime_globals.pet_sprites[self]

            self.set_traited_egg()

            if not game_globals.pet_list:
                change_scene("egg")


    def set_eating(self, food_type: str, amount: int) -> bool:
        """
        Handles feeding logic for different food types.
        Returns True if the pet accepted the food, False otherwise.
        """
        module = get_module(self.module)

        # Can't eat if sleeping and module doesn't allow it
        if not module.can_eat_sleeping and self.state == "nap":
            return False

        # Block feeding during sleep window if care_block_actions_when_sleeping is set
        if self._is_blocked_by_sleep():
            return False

        accepted = False

        if food_type == "hunger":
            if self.hunger == self.stomach or self.overfeed_timer:
                if self.overfeed_timer == 0:
                    self.overfeed_timer = module.overfeed_timer
                    self.overfeed += 1
                self.set_state("nope")
            else:
                self.check_disturbed_sleep()
                self.set_state("eat", True)
                self.hunger = min(self.stomach, self.hunger + (module.meat_hunger_gain * amount))
                if self.stage > 1 and self.weight < 99:
                    self.weight = min(99, self.weight + module.meat_weight_gain)
                self.care_food_mistake_timer = 0
                accepted = True
                runtime_globals.game_console.log(f"{self.name} ate food (hunger). Hunger {self.hunger}")
        elif food_type == "strength":
            self.check_disturbed_sleep()
            self.set_state("eat")
            self.strength = min(self.stomach, self.strength + (module.protein_strengh_gain * amount))
            self.protein_feedings += 1
            if self.stage > 1 and self.weight < 99:
                self.weight = min(99, self.weight + module.protein_weight_gain)
            if self.protein_feedings % 4 == 0:
                self.protein_overdose = min(get_module(self.module).protein_overdose_max, self.protein_overdose + 1)
                self.protein_feedings = 0
                if self.dp < self.energy:
                    self.dp = min(self.energy, self.dp + module.protein_dp_gain)
            self.care_strength_mistake_timer = 0
            
            # Remove G-Cell points for protein feeding if module uses G-Cells
            if getattr(module, 'use_gcells', False):
                gcell_points = getattr(module, 'gcell_protein', 0)
                if gcell_points != 0:
                    self.add_gcell_points(gcell_points)
            
            accepted = True
            runtime_globals.game_console.log(f"{self.name} ate food (strength). Strength {self.strength}")
        else:
            # For other food types, only accept if pet can battle
            if self.can_battle():
                self.check_disturbed_sleep()
                self.set_state("eat")
                accepted = True
                runtime_globals.game_console.log(f"{self.name} ate food ({food_type}).")
            else:
                self.set_state("nope")

        self.update_99g_effect()
        return accepted

    def set_sick(self):
        self.sick = self.heal_doses
        self.injuries += 1
        self.set_state("sick")

    def update_99g_effect(self):
        """Handle the 99g weight effect based on the module's care_99g_effect setting."""
        module = get_module(self.module)
        effect = getattr(module, 'care_99g_effect', 'Skull')

        if effect == "Nothing":
            return

        if effect == "Burpmon":
            if self.state == "dead":
                if getattr(self, 'burpmon_active', False):
                    self.burpmon_active = False
                    self.load_sprite()
                return
            if self.weight >= 99 and not getattr(self, 'burpmon_active', False):
                self.burpmon_active = True
                self._load_burpmon_sprite()
            elif self.weight < 99 and getattr(self, 'burpmon_active', False):
                self.burpmon_active = False
                self.load_sprite()
            return

        # Dots or Skull: allow re-trigger only after weight drops below 90
        if self.weight < 90:
            self._99g_triggered = False
            if self.sick == 0:
                self.sick_type = ""

        if self.weight >= 99 and not getattr(self, '_99g_triggered', False):
            self._99g_triggered = True
            if effect == "Dots":
                self.sick_type = "dots"
                self.sick = self.heal_doses
                self.injuries += 1
                self.set_state("sick")
            else:  # Skull
                self.set_sick()

    def _load_burpmon_sprite(self):
        """Replace current pet sprite with the Burpmon sprite."""
        module_obj = get_module(self.module)
        if not module_obj:
            return
        
        primary_format = getattr(module_obj, 'primary_sprite_format', 'Color')
        secondary_format = getattr(module_obj, 'secondary_sprite_format', 'HD')
        
        sprites_dict = load_pet_sprites(
            "Burpmon",
            module_obj.folder_path,
            module_obj.name_format,
            size=(runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT),
            primary_sprite_format=primary_format,
            secondary_sprite_format=secondary_format
        )
        if sprites_dict:
            runtime_globals.pet_sprites[self] = convert_sprites_to_list(sprites_dict)
            runtime_globals.game_console.log(f"[99g] {self.name} became Burpmon!")
        else:
            runtime_globals.game_console.log(f"[99g] Burpmon sprite not found, keeping original.")

    def update_evolution(self):
        if self.stage > 5 or self._evol_minutes < self.time or self.need_care():
            return
        
        for evo in self.evolve:
            def in_range(val, r): return r[0] <= val <= r[1]
            def in_time_range(time_range):
                try:
                    now_time = datetime.now().time()
                    start_time = datetime.strptime(time_range[0].strip(), "%H:%M").time()
                    end_time = datetime.strptime(time_range[1].strip(), "%H:%M").time()
                    
                    if start_time < end_time:
                        return start_time <= now_time <= end_time
                    else:
                        # Handle overnight range (e.g., 23:00 to 01:00)
                        return now_time >= start_time or now_time <= end_time
                except Exception as e:
                    runtime_globals.game_console.log(f"[!] Error parsing time_range: {e}")
                    return False
                    
            if (
                ("jogress" in evo) or ("item" in evo) or
                ("mistakes" in evo and not in_range(self.mistakes, evo["mistakes"])) or
                ("condition_hearts" in evo and not in_range(self.condition_hearts, evo["condition_hearts"])) or
                ("training" in evo and not in_range(self.effort, evo["training"])) or
                ("overfeed" in evo and not in_range(self.overfeed, evo["overfeed"])) or
                ("special_encounter" in evo and not self.special_encounter) or
                ("level" in evo and not in_range(self.level, evo["level"])) or
                ("quests_completed" in evo and not in_range(self.quests_completed, evo["quests_completed"])) or
                ("weight" in evo and not in_range(self.weight, evo["weight"])) or
                ("trophies" in evo and not in_range(self.trophies, evo["trophies"])) or
                ("vital_values" in evo and not in_range(self.vital_values, evo["vital_values"])) or
                ("blue_gcells" in evo and not in_range(self.get_blue_gcells(), evo["blue_gcells"])) or
                ("yellow_gcells" in evo and not in_range(self.get_yellow_gcells(), evo["yellow_gcells"])) or
                ("red_gcells" in evo and not in_range(self.get_red_gcells(), evo["red_gcells"])) or
                ("gcell_level" in evo and not in_range(self.get_gcell_level(), evo["gcell_level"])) or
                ("gcell_hatch" in evo and not self.gcell_fragment) or
                ("stage-5" in evo and not in_range(self.enemy_kills[5], evo["stage-5"])) or
                ("stage-6" in evo and not in_range(self.enemy_kills[6], evo["stage-6"])) or
                ("stage-7" in evo and not in_range(self.enemy_kills[7], evo["stage-7"])) or
                ("stage-8" in evo and not in_range(self.enemy_kills[8], evo["stage-8"])) or
                ("stage-9" in evo and not in_range(self.enemy_kills[9], evo["stage-9"])) or
                ("pvp" in evo and not in_range(self.pvp_wins, evo["pvp"])) or
                ("sleep_disturbances" in evo and not in_range(self.sleep_disturbances, evo["sleep_disturbances"])) or
                ("battles" in evo and not in_range(self.battles, evo["battles"])) or
                ("win_count" in evo and not in_range(self.win, evo["win_count"])) or
                ("win_ratio" in evo and self.battles and not in_range((self.win * 100) // self.battles, evo["win_ratio"])) or
                ("time_range" in evo and not in_time_range(evo["time_range"]))
            ):
                continue

            if self.stage > 0:
                module = get_module(self.module)
                pet_data = module.get_monster(evo["to"], self.version)

                if pet_data.get("special", False):
                    special_key = pet_data.get("special_key")
                    if special_key and not is_unlocked(self.module, None, special_key):
                        runtime_globals.game_console.log(f"{self.name} cannot evolve into {evo['to']}—special evolution {special_key} is locked.")
                        continue  # Skip this evolution
                    else:
                        runtime_globals.game_console.log("Special evolution check pass")

            # Unlock evolution if present in module unlocks (new format)
            module = get_module(self.module)
            unlocks = getattr(module, "unlocks", [])
            for unlock in unlocks:
                if unlock.get("type") == "evolution" and "to" in unlock:
                    if evo["to"] in unlock["to"]:
                        unlock_item(self.module, "evolution", unlock["name"])

            if self.stage == 0 and self.shake_counter >= 99 and get_module(self.module).enable_shaken_egg:
                self.shook = True
                
            self.evolve_to(evo["to"], evo.get("version", self.version))
            
            # Update quest progress for normal evolution
            from utils.quest_event_utils import update_evolution_quest_progress
            update_evolution_quest_progress("normal", self.module)
            
            break

    def update_needs(self, minutes_passed):
        # Skip hunger/strength decay when pet should be sleeping
        sleeping = self.should_sleep() or self.state == "nap"

        # Hunger countdown
        if self._cd_hunger > 0 and not sleeping:
            if self.overfeed_timer == 0:
                self._cd_hunger -= minutes_passed
                while self._cd_hunger <= 0:
                    if self.hunger > 0:
                        self.hunger -= 1
                    else:
                        self.starvation_counter += 1
                    self._cd_hunger += self.hunger_loss
        # Strength countdown
        if self._cd_strength > 0 and not sleeping:
            self._cd_strength -= minutes_passed
            while self._cd_strength <= 0:
                if self.strength > 4:
                    self.strength = 4
                elif self.strength > 0:
                    self.strength -= 1
                self._cd_strength += self.strength_loss
        if self.overfeed_timer > 0:
            self.overfeed_timer -= 1

        self.update_99g_effect()

    def update_pooping(self, minutes_passed):
        if self.stage <= 0 or self._cd_poop <= 0:
            return
        module = get_module(self.module)
        poop_sickness_count = getattr(module, 'care_poop_sickness_count', 0)
        if poop_sickness_count > 0:
            poop_threshold = poop_sickness_count * max(1, len(game_globals.pet_list) - 1)
            poop_sick = len(game_globals.poop_list) >= poop_threshold and self.stage >= 2
        else:
            poop_sick = False
        if poop_sick:
            if self.poop_count_flag == 0:
                self.poop_count_flag = 1
                poop_effect = getattr(module, 'care_poop_sickness_effect', 'Skull')
                if poop_effect == "Nothing":
                    pass
                elif poop_effect == "Dots":
                    self.sick_type = "dots"
                    self.sick = self.heal_doses
                    self.injuries += 1
                    self.set_state("sick")
                else:  # Skull
                    self.set_sick()
                runtime_globals.game_console.log(f"[!] Care sick of poop ({len(game_globals.poop_list)})! Effect: {poop_effect}, Injuries: {self.injuries}")
        else:
            self.poop_count_flag = 0

        depletion = minutes_passed * (2 if (self.stage >= 6 and self.age >= 2) else 1)
        self._cd_poop -= depletion
        if self._cd_poop <= 0:
            self.set_state("pooping")
            self._cd_poop = max(1, self.poop_timer)

    def update_care_mistakes(self):
        sound_alert = False
        sleeping = self.should_sleep() or self.state == "nap"
        module = get_module(self.module)

        #hunger call — only tick while pet is not in sleep window;
        # once care mistake fires, timer caps at threshold (no repeat)
        if self.hunger == 0 and not sleeping:
            if self.care_food_mistake_timer < module.meat_care_mistake_time:
                self.care_food_mistake_timer += 1
                if self.care_food_mistake_timer == module.meat_care_mistake_time:
                    self.add_care_mistake("hunger")
                    sound_alert = True
        
        #strength call — same single-fire guard
        if self.strength == 0 and not sleeping:
            if self.care_strength_mistake_timer < module.protein_care_mistake_time:
                self.care_strength_mistake_timer += 1
                if self.care_strength_mistake_timer == module.protein_care_mistake_time:
                    self.add_care_mistake("strength")
                    sound_alert = True
        
        #sick call — pause timer while sleeping
        if self.sick > 0 and not sleeping:
            self.care_sick_mistake_timer += 1
        elif self.sick == 0:
            self.care_sick_mistake_timer = 0

        #sleep call
        if sleeping:
            self.care_sleep_mistake_timer += 1
            if self.care_sleep_mistake_timer >= module.sleep_care_mistake_timer:
                self.add_care_mistake("sleep")
                sound_alert = True
                self.care_sleep_mistake_timer = 0
                
        
        if sound_alert:
            runtime_globals.game_sound.play("alarm")

    def update_vital_values_gain(self):
        """Update vital values every hour - gain if pet is healthy and well-fed"""
        if self.stage <= 0 or self.state in ("dead", "nap") or self.sick > 0 or self.hunger == 0 or self.strength == 0:
            return
            
        module = get_module(self.module)
        base_gain = getattr(module, 'vital_value_base', 50)  # Default to 50 if not defined

        # Calculate multiplier based on activities (base + activities)
        activity_multiplier = 1 + len(self.vital_activities)
        vital_gain = base_gain * activity_multiplier
        
        # Add to vital_values (capped at 9999)
        self.vital_values = min(9999, self.vital_values + vital_gain)
        
        runtime_globals.game_console.log(f"[Vital] {self.name} gained {vital_gain} vital values (activities: {len(self.vital_activities)}). Total: {self.vital_values}")
        
        # Clear activities after gaining vital values
        self.vital_activities.clear()

    def update_vital_values_loss(self):
        """Update vital values every minute - lose if pet is in poor condition"""
        if self.stage <= 0 or self.state in ("dead", "nap") or self.sick <= 0 and self.hunger > 0 and self.strength > 0:
            return
            
        module = get_module(self.module)
        vital_loss = getattr(module, 'vital_value_loss', 1)  # Default to 1 if not defined
        
        # Remove from vital_values (minimum 0)
        old_vital = self.vital_values
        self.vital_values = max(0, self.vital_values - vital_loss)
        
        if old_vital != self.vital_values:
            runtime_globals.game_console.log(f"[Vital] {self.name} lost {vital_loss} vital values (poor condition). Total: {self.vital_values}")
    
    def add_care_mistake(self, mistake_type):
        module = get_module(self.module)
        
        if self.use_condition_hearts:
            if self.condition_hearts > 0:
                self.condition_hearts -= 1
                runtime_globals.game_console.log(f"[!] Care mistake ({mistake_type})! Condition hearts left: {self.condition_hearts}")
        else:
            self.mistakes += 1
            runtime_globals.game_console.log(f"[!] Care mistake ({mistake_type})! Total: {self.mistakes}")
        
        # Remove G-Cell points for care mistake if module uses G-Cells
        if getattr(module, 'use_gcells', False):
            gcell_points = getattr(module, 'gcell_care_mistake', 0)
            if gcell_points != 0:
                self.add_gcell_points(gcell_points)

    def need_care(self):
        return self.stage != 0 and self.state not in ("dead","nap") and (self.hunger == 0 or self.strength == 0 or self.sick > 0 or self.should_sleep()) 

    def call_sign(self):
        if self.stage == 0 or self.state in ("dead","nap"):
            return False
        if self.hunger == 0 and self.care_food_mistake_timer < get_module(self.module).meat_care_mistake_time:
            return True
        elif self.strength == 0 and self.care_strength_mistake_timer < get_module(self.module).protein_care_mistake_time:
            return True
        elif self.should_sleep() and self.care_sleep_mistake_timer < get_module(self.module).sleep_care_mistake_timer:
            return True
        return False

    def set_traited_egg(self):
        ruleset = get_module(self.module).ruleset

        if ruleset == "dmc":
            if self.stage in [6, 7] and random.randint(0, 10) <= 3:
                key = f"{self.module}@{self.version}"
                if key not in game_globals.traited:
                    game_globals.traited.append(key)
                    runtime_globals.game_console.log(f"Traited Egg granted for {self.name}!")
        elif ruleset == "penc":
            win_ratio = (self.win * 100) // self.battles if self.battles > 0 else 0
            if self.stage >= 6 and self.age >= 2:
                if win_ratio >= 60:
                    key = f"{self.module}@{self.version}"
                    if key not in game_globals.traited:
                        game_globals.traited.append(key)
                        runtime_globals.game_console.log(f"Traited Egg granted for {self.name}!")
        elif ruleset == "dmx":
            trait = False
            if self._evol_minutes >= 2880:  # 48 hours
                trait = True

            if self.version > 4 and self.area < 45:
                trait = False

            if trait:
                key = f"{self.module}@{self.version}"
                if key not in game_globals.traited:
                    game_globals.traited.append(key)
                    runtime_globals.game_console.log(f"Traited Egg granted for {self.name}!")
        elif ruleset == "vb":
            pass # No Traited Eggs in VB


    def _is_blocked_by_sleep(self):
        if not getattr(get_module(self.module), 'care_block_actions_when_sleeping', True):
            return False
        return self.state == "nap" or self.should_sleep()

    def _has_battle_resources(self):
        module = get_module(self.module)
        cost_type = getattr(module, 'battle_cost_type', 'DP')
        cost_amount = getattr(module, 'battle_cost_amount', 1.0)
        if cost_type == "Nothing":
            return True
        elif cost_type == "Hunger":
            return self.hunger >= cost_amount
        else:  # DP
            return self.dp >= cost_amount

    def _deduct_battle_cost(self):
        module = get_module(self.module)
        cost_type = getattr(module, 'battle_cost_type', 'DP')
        cost_amount = getattr(module, 'battle_cost_amount', 1.0)
        if cost_type == "Hunger":
            self.hunger = max(0, self.hunger - cost_amount)
        elif cost_type == "DP":
            self.dp = max(0, self.dp - cost_amount)

    def can_battle(self):
        module = get_module(self.module)
        if not getattr(module, 'care_can_battle_while_sick', False) and self.sick > 0:
            return False
        return self.stage > 1 and self.power > 0 and self.state != "dead" and self.atk_main > 0 and self._has_battle_resources() and not self._is_blocked_by_sleep()
    
    def can_battle_pvp(self):
        module = get_module(self.module)
        if not getattr(module, 'care_can_battle_while_sick', False) and self.sick > 0:
            return False
        return self.stage > 1 and self.power > 0 and self.state != "dead" and self.atk_main > 0 and self._has_battle_resources() and not self._is_blocked_by_sleep()
    
    def can_train(self):
        return self.stage > 0 and self.state != "dead" and self.atk_main > 0 and not self._is_blocked_by_sleep()

    def set_back_to_sleep(self):
        self.back_to_sleep = get_module(self.module).back_to_sleep_time

    def check_disturbed_sleep(self):
        if self.state == "nap":
            runtime_globals.game_console.log(f"[DEBUG] Sleep disturbance {self.sleep_disturbances}")
            self.set_state("idle")
            self.sleep_disturbances += 1
            self.disturbance_penalty += 2
            self.set_back_to_sleep()

    def get_hp(self):
        if not hasattr(self, 'hp') or self.hp == 0 or self.hp == None:
            self.hp = constants.HP_LEVEL[self.stage]
        hp = self.hp

        if self.level >= 2:
            hp += 2
        if self.level >= 5:
            hp += 2
        if self.level >= 6:
            hp += 2
        if self.level >= 10:
            hp += 2
        
        # Add bonus from status_change items
        if hasattr(self, 'bonus_stats') and len(self.bonus_stats) > 0:
            hp += self.bonus_stats[0]
        
        return hp
    
    def get_power(self, bonus = 0):
        ruleset = get_module(self.module).ruleset
        power = self.power + bonus
        
        # Add bonus from vb status_change items
        if hasattr(self, 'bonus_stats') and len(self.bonus_stats) > 2:
            power += self.bonus_stats[2]

        if ruleset == "dmc":
            multi = 1
            if self.traited:
                multi = 2

            if self.effort >= 16:
                if self.stage == 3:
                    power += (5 * multi)
                elif self.stage == 4:
                    power += (8 * multi)
                elif self.stage == 5:
                    power += (15 * multi)
                elif self.stage >= 6:
                    power += (25 * multi)
            return power
        elif ruleset == "penc":
            strength_bonus = 0
            traited_bonus = 0
            shaken_bonus = 0
            
            # Strength Hearts Bonus
            if self.effort >= 16:
                if self.stage == 3:
                    strength_bonus = 5
                elif self.stage == 4:
                    strength_bonus = 8
                elif self.stage == 5:
                    strength_bonus = 15
                elif self.stage >= 6:
                    strength_bonus = 20

            # Traited Egg Bonus
            if self.traited:
                if self.stage == 3:
                    traited_bonus = 5
                elif self.stage == 4:
                    traited_bonus = 8
                elif self.stage == 5:
                    traited_bonus = 15
                elif self.stage >= 6:
                    traited_bonus = 20

            # Shaken Egg Bonus
            if self.shook:
                shaken_bonus = 10

            # Total Bonus Calculation
            total_bonus = strength_bonus + traited_bonus + shaken_bonus

            return power + total_bonus
        elif ruleset == "dmx":
            if self.effort >= 16:
                if self.version > 4:
                    power += 16
                else:
                    power += 15
            if self.level >= 3:
                power += 10
            if self.level >= 6:
                power += 10
            if self.level >= 9:
                power += 10
            return power

        elif ruleset == "vb":
            """Normalize VB ruleset power using power and star values.

            Requirement: a pet with base power 70 and 10 stars should return 230.
            We use a simple linear mapping where each star contributes 16 points
            on top of the base power: normalized = base_power + star * 16.

            The implementation below is defensive: it coerces non-numeric
            values to sensible defaults (0) to avoid runtime errors.
            """
            normalized = power + (self.star * 16)
            return int(normalized)

    def get_attack(self):
        attack = 1 # constants.ATK_LEVEL[self.stage]

        if self.level >= 4:
            attack += 1
        if self.level >= 7:
            attack += 1
        
        # Add bonus from status_change items
        if hasattr(self, 'bonus_stats') and len(self.bonus_stats) > 1:
            attack += self.bonus_stats[1]
        
        return attack
    
    def finish_training(self, won = False, grade=0, phase2=False):
        module = get_module(self.module)
        if won:
            self.set_state("happy2")
            self.effort += module.training_effort_gain
            if grade > 0 and module.training_strengh_multiplier > 0:
                self.strength += int(module.training_strengh_gain_win * grade * module.training_strengh_multiplier)
            else:
                self.strength += module.training_strengh_gain_win
            if self.disturbance_penalty >= 2:
                self.disturbance_penalty -= 2
            
            # Add training activity for vital_values (only once)
            if "training" not in self.vital_activities:
                self.vital_activities.append("training")
        else:
            self.set_state("angry")
            self.strength += module.training_strengh_gain_lose

        weight_loss = module.training_weight_win if won else module.training_weight_lose
        self.weight = max(self.min_weight, self.weight - weight_loss)
        self.update_99g_effect()

        # Add/Remove G-Cell points for training if module uses G-Cells
        if getattr(module, 'use_gcells', False):
            if won:
                runtime_globals.game_console.log(f"[DEBUG] Training success for {self.name}")
                gcell_points = getattr(module, 'gcell_training_success', 0)
            else:
                # Training failure - different points based on phase
                if phase2:
                    runtime_globals.game_console.log(f"[DEBUG] Training phase 2 failure for {self.name}")
                    gcell_points = getattr(module, 'gcell_training_phase2_failure', 0)
                else:
                    runtime_globals.game_console.log(f"[DEBUG] Training phase 1 failure for {self.name}")
                    gcell_points = getattr(module, 'gcell_training_phase1_failure', 0)

            self.add_gcell_points(gcell_points)

    def finish_versus(self, won=False):
        self.battles += 1
        self._deduct_battle_cost()
        self.totalBattles += 1
        if won:
            self.set_state("happy3")
            self.win += 1
            self.totalWin += 1
            
            # Add G-Cell points for PvP win if module uses G-Cells
            module = get_module(self.module)
            if getattr(module, 'use_gcells', False):
                gcell_points = getattr(module, 'gcell_battle_win', 0)
                if gcell_points != 0:
                    self.add_gcell_points(gcell_points)
        else:
            # Remove G-Cell points for PvP loss if module uses G-Cells
            module = get_module(self.module)
            if getattr(module, 'use_gcells', False):
                gcell_points = getattr(module, 'gcell_battle_loose', 0)
                if gcell_points != 0:
                    self.add_gcell_points(gcell_points)

    def finish_battle(self, won, enemy, area, final = False, is_special_encounter=False):
        self.battles += 1
        self._deduct_battle_cost()
        self.totalBattles += 1
        if won:
            if final:
                self.set_state("happy3")
            self.win += 1
            self.totalWin += 1
            sick_chance = get_module(self.module).battle_base_sick_chance_win

            # Mark special encounter flag on win (enables special evolution paths)
            if is_special_encounter:
                self.special_encounter = True

            # Add battle activity for vital_values (only once)
            if "battle" not in self.vital_activities:
                self.vital_activities.append("battle")

            if not hasattr(self, 'area'):
                self.area = 0
                
            if self.area < area:
                self.area = area
                runtime_globals.game_console.log(f"[DEBUG] {self.name} area increased to {self.area} (previous: {self.area})")

            if not hasattr(self, 'enemy_kills'):
                self.enemy_kills = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

            self.enemy_kills[enemy.stage] += 1
            
            # Check for G-Cell fragment from Godzilla enemies (15% chance) for modules that use G-Cells
            module = get_module(self.module)
            if getattr(module, 'use_gcells', False) and "Godzilla" in enemy.name and random.random() < 0.15:
                fragment_key = f"{self.module}@{self.version}"
                if not hasattr(game_globals, 'gcell_fragments'):
                    game_globals.gcell_fragments = []
                if fragment_key not in game_globals.gcell_fragments:
                    game_globals.gcell_fragments.append(fragment_key)
                    runtime_globals.game_console.log(f"[G-Cell] {self.name} obtained a G-Cell fragment for {self.module} v{self.version} from {enemy.name}!")
            
            # Add G-Cell points for battle win if module uses G-Cells
            module = get_module(self.module)
            if getattr(module, 'use_gcells', False):
                if is_special_encounter:
                    # Random encounter win
                    gcell_points = getattr(module, 'gcell_random_encounter_win', 0)
                else:
                    # Regular battle win
                    gcell_points = getattr(module, 'gcell_battle_win', 0)
                if gcell_points != 0:
                    self.add_gcell_points(gcell_points)
        else:
            if final:
                self.set_state("lose")
            sick_chance = get_module(self.module).battle_base_sick_chance_lose
            
            # Remove G-Cell points for battle loss if module uses G-Cells
            module = get_module(self.module)
            if getattr(module, 'use_gcells', False):
                if is_special_encounter:
                    # Random encounter loss
                    gcell_points = getattr(module, 'gcell_random_encounter_loose', 0)
                else:
                    # Regular battle loss
                    gcell_points = getattr(module, 'gcell_battle_loose', 0)
                if gcell_points != 0:
                    self.add_gcell_points(gcell_points)
            if self.protein_overdose > get_module(self.module).protein_overdose_max:
                self.protein_overdose = get_module(self.module).protein_overdose_max
            sick_chance += self.protein_overdose * get_module(self.module).protein_penalty
            self.protein_overdose = 0

            if self.disturbance_penalty > get_module(self.module).disturbance_penalty_max:
                self.disturbance_penalty = get_module(self.module).disturbance_penalty_max

            sick_chance += self.disturbance_penalty
            self.disturbance_penalty = 0

        try:
            sc = float(sick_chance)
        except Exception:
            sc = 0.0
        # clamp percentage 0..100 then convert to 0.0..1.0
        sick_chance = max(0.0, min(sc, 100.0)) / 100.0
        
        if random.random() < sick_chance:
            self.set_sick()

    def add_experience(self, xp):
        self.experience += xp
        if self.level == constants.MAX_LEVEL[self.stage]:
            self.experience = 0
        if self.experience >= constants.EXPERIENCE_LEVEL[self.level+1]:
            self.experience -= constants.EXPERIENCE_LEVEL[self.level+1]
            self.level += 1
            #runtime_globals.game_message.add(f"Level UP!", (self.x + (PET_WIDTH // 2), self.y), FONT_COLOR_GREEN)
            if self.level == constants.MAX_LEVEL[self.stage]:
                self.experience = 0

    def should_sleep(self):
        if not self.sleeps or not self.wakes:
            return False
        
        # Use global sleep/wake if set
        global_sleep = getattr(game_globals, "sleep_time", None)
        global_wake = getattr(game_globals, "wake_time", None)

        try:
            now_time = datetime.now().time()

            # Use global times if set
            if global_sleep is not None and global_wake is not None:
                sleep_time = global_sleep
                wake_time = global_wake
            elif self.sleeps and self.wakes:
                # Cache parsing whenever sleeps/wakes change
                if not hasattr(self, '_cached_sleep_time') or self._last_sleeps != self.sleeps or self._last_wakes != self.wakes:
                    self._cached_sleep_time = datetime.strptime(self.sleeps.strip(), "%H:%M").time()
                    self._cached_wake_time = datetime.strptime(self.wakes.strip(), "%H:%M").time()
                    self._last_sleeps = self.sleeps
                    self._last_wakes = self.wakes
                sleep_time = self._cached_sleep_time
                wake_time = self._cached_wake_time
            else:
                return False

            if sleep_time < wake_time:
                return sleep_time <= now_time < wake_time
            else:
                return now_time >= sleep_time or now_time < wake_time

        except Exception as e:
            runtime_globals.game_console.log(f"[!] Error parsing sleep range: {e}")
            return False

    def check_wake_up(self):
        now = datetime.now()

        if not hasattr(self, 'sleep_start_time'):
            return

        global_wake = getattr(game_globals, "wake_time", None)

        try:
            # Use global wake time if set
            if global_wake is not None:
                wake_time = global_wake
            elif self.wakes:
                # Cache parsing if wakes change
                if not hasattr(self, '_cached_wake_time') or self._last_wakes != self.wakes:
                    self._cached_wake_time = datetime.strptime(self.wakes.strip(), "%H:%M").time()
                    self._last_wakes = self.wakes
                wake_time = self._cached_wake_time
            else:
                return

            # Wake up if it's the wake time exactly (match hour and minute)
            if now.hour == wake_time.hour and now.minute == wake_time.minute:
                slept_seconds = (now - self.sleep_start_time).total_seconds()
                slept_hours = int(slept_seconds // 3600)

                if slept_hours >= constants.SLEEP_RECOVERY_HOURS:
                    self.dp = self.energy
                    runtime_globals.game_console.log(f"{self.name} slept {slept_hours}h and recovered DP!")

                self.set_state("idle")
                runtime_globals.game_console.log(f"{self.name} woke up naturally at {wake_time.strftime('%H:%M')}")

        except Exception as e:
            runtime_globals.game_console.log(f"[!] Error parsing wake time: {e}")

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("frames", None)
        # Convert monotonic timestamps to elapsed seconds for serialization
        now = time.monotonic()
        state['_rt_elapsed_sec'] = now - self._rt_origin
        if self._rt_dead_start > 0:
            state['_rt_dead_elapsed_sec'] = now - self._rt_dead_start
        else:
            state['_rt_dead_elapsed_sec'] = 0.0
        # Remove non-serializable monotonic timestamps
        state.pop('_rt_origin', None)
        state.pop('_rt_last_sleep_check', None)
        state.pop('_rt_dead_start', None)
        # Remove deprecated keys from old system
        state.pop('_rt_age_origin', None)
        return state
    
    def __setstate__(self, state):
        self.__dict__.update(state)
        now = time.monotonic()
        # Restore monotonic timestamp for per-minute tick
        rt_elapsed = state.get('_rt_elapsed_sec', None)
        if rt_elapsed is None:
            rt_elapsed = getattr(self, 'timer', 0) / 30
        self._rt_origin = now - rt_elapsed
        self._rt_last_sleep_check = now
        dead_elapsed = state.get('_rt_dead_elapsed_sec', 0.0)
        self._rt_dead_start = (now - dead_elapsed) if dead_elapsed > 0 else 0.0
        # Ensure minute counter exists
        if not hasattr(self, '_rt_last_minute'):
            self._rt_last_minute = int(rt_elapsed / 60)
        # Migrate old age system to midnight-based
        if not hasattr(self, '_last_age_date'):
            self._last_age_date = datetime.now().date()
        # Migrate old elapsed-minute counters to new countdown/countup system
        if not hasattr(self, '_evol_minutes'):
            self._evol_minutes = int(rt_elapsed / 60)
        if not hasattr(self, '_cd_hunger'):
            self._cd_hunger = getattr(self, 'hunger_loss', 0) or 0
        if not hasattr(self, '_cd_strength'):
            self._cd_strength = getattr(self, 'strength_loss', 0) or 0
        if not hasattr(self, '_cd_poop'):
            self._cd_poop = getattr(self, 'poop_timer', 60) or 60
        if not hasattr(self, 'evolution_history'):
            self.evolution_history = []
        # Clean up serialization-only and deprecated keys
        for key in ('_rt_elapsed_sec', '_rt_age_elapsed_sec', '_rt_dead_elapsed_sec',
                    '_rt_age_origin', '_rt_last_age_day',
                    '_rt_last_hunger_min', '_rt_last_strength_min', '_rt_last_poop_min'):
            self.__dict__.pop(key, None)
        self.load_sprite()
        if self.state == "dead":
            runtime_globals.pet_sprites[self][0] = image_load(constants.DEAD_FRAME_PATH).convert_alpha()
            runtime_globals.pet_sprites[self][0] = pygame.transform.scale(runtime_globals.pet_sprites[self][0], (runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT))
            runtime_globals.pet_sprites[self][1] = runtime_globals.pet_sprites[self][0]

    def patch(self):
        if not hasattr(self, "trophies"):
            self.trophies = 0
        if not hasattr(self, "vital_values"):
            self.vital_values = 0
        if not hasattr(self, "vital_activities"):
            self.vital_activities = []
        if not hasattr(self, "dirty"):
            self.dirty = True  # Force initial update
            self.cache_x = -1  # Invalid initial value to force update
            self.cache_frame_index = -1  # Invalid initial value to force update
            self.cache_has_overlay = False
        if not hasattr(self, "quests_completed"):
            self.quests_completed = 0
        if not hasattr(self, "pvp_wins"):
            self.pvp_wins = 0
        if not hasattr(self, "pvp_battles"):
            self.pvp_battles = 0
        if not hasattr(self, "protein_feedings"):
            self.protein_feedings = 0
        if not hasattr(self, "edited"):
            self.edited = False
        if not hasattr(self, "gcell_points"):
            self.gcell_points = 0
        if not hasattr(self, "gcell_fragment"):
            self.gcell_fragment = False
        if not hasattr(self, "death_save_b_counter"):
            self.death_save_b_counter = 0
        if not hasattr(self, "death_save_shake_counter"):
            self.death_save_shake_counter = 0
        if not hasattr(self, "death_save_immunity"):
            self.death_save_immunity = 0
        if not hasattr(self, "bonus_stats"):
            self.bonus_stats = [0, 0, 0]
        if not hasattr(self, "atk_alt_2"):
            # Migrate old saves that stored the field without underscore
            self.atk_alt_2 = getattr(self, "atk_alt2", 0)
        if not hasattr(self, "evolution_history"):
            self.evolution_history = []
        # Migrate / repair real-time timer attributes
        now = time.monotonic()
        if not hasattr(self, '_rt_origin'):
            fps = getattr(constants, 'FRAME_RATE', 30) or 30
            elapsed_sec = getattr(self, 'timer', 0) / fps
            self._rt_origin = now - elapsed_sec
            self._rt_last_sleep_check = now
            self._rt_dead_start = now if self.state == "dead" else 0.0
            self._rt_last_minute = int(elapsed_sec / 60)
        else:
            if not hasattr(self, '_rt_last_minute'):
                self._rt_last_minute = int((now - self._rt_origin) / 60)
            if not hasattr(self, '_rt_last_sleep_check'):
                self._rt_last_sleep_check = now
            if not hasattr(self, '_rt_dead_start'):
                self._rt_dead_start = now if self.state == "dead" else 0.0
        # Migrate to countdown/countup counter system
        if not hasattr(self, '_last_age_date'):
            self._last_age_date = datetime.now().date()
        if not hasattr(self, '_evol_minutes'):
            self._evol_minutes = int((now - self._rt_origin) / 60)
        if not hasattr(self, '_cd_hunger'):
            self._cd_hunger = getattr(self, 'hunger_loss', 0) or 0
        if not hasattr(self, '_cd_strength'):
            self._cd_strength = getattr(self, 'strength_loss', 0) or 0
        if not hasattr(self, '_cd_poop'):
            self._cd_poop = getattr(self, 'poop_timer', 60) or 60
        # Clean up deprecated attributes from old timer system
        for key in ('_rt_age_origin', '_rt_last_age_day',
                    '_rt_last_hunger_min', '_rt_last_strength_min', '_rt_last_poop_min'):
            self.__dict__.pop(key, None)

    def get_blue_gcells(self):
        """
        Returns the number of blue G-Cells based on gcell_points.
        Blue G-Cells: 1 every 8 points, max 14 at 112+ points.
        """
        if self.gcell_points >= 112:
            return 14
        return min(14, self.gcell_points // 8)

    def get_yellow_gcells(self):
        """
        Returns the number of yellow G-Cells based on gcell_points.
        Yellow G-Cells: 1 every 12 points between 113-232, max 10.
        """
        if self.gcell_points < 113:
            return 0
        if self.gcell_points >= 232:
            return 10
        return min(10, (self.gcell_points - 112) // 12)

    def get_red_gcells(self):
        """
        Returns the number of red G-Cells based on gcell_points.
        Red G-Cells: 1 every 12 points between 233-472, max 20.
        """
        if self.gcell_points < 233:
            return 0
        if self.gcell_points >= 472:
            return 20
        return min(20, (self.gcell_points - 232) // 12)

    def get_gcell_level(self):
        """
        Returns the current G-Cell meter level (1-4) based on gcell_points.
        Level 1: 0-112 points (Blue)
        Level 2: 113-232 points (Yellow)
        Level 3: 233-352 points (Red)
        Level 4: 353-472 points (Red)
        """
        if self.gcell_points <= 112:
            return 1
        elif self.gcell_points <= 232:
            return 2
        elif self.gcell_points <= 352:
            return 3
        else:
            return 4

    def add_gcell_points(self, points):
        """
        Adds G-Cell points with proper capping (0 minimum, 472 maximum).
        Returns the actual amount added/subtracted.
        """
        old_points = self.gcell_points
        self.gcell_points = max(0, min(472, self.gcell_points + points))
        actual_change = self.gcell_points - old_points
        
        if actual_change != 0:
            runtime_globals.game_console.log(f"[G-Cell] {self.name} {'+' if actual_change > 0 else ''}{actual_change} points. Total: {self.gcell_points}")
        
        return actual_change

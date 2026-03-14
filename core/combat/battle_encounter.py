#=====================================================================
# BattleEncounter
#=====================================================================

import math
import random
import pygame
from typing import List, Optional
from components.minigames.count_match import CountMatch
from components.minigames.count_match_classic import CountMatchClassic
from components.minigames.count_match_z import CountMatchZ
from components.minigames.dummy_charge import DummyCharge
from components.minigames.shake_punch import ShakePunch
from components.minigames.xai_roll import XaiRoll
from components.minigames.xai_bar import XaiBar
from components.ui.ui_manager import UIManager
from components.ui.animated_sprite import AnimatedSprite
from components.ui.hp_bar import HPBar
from components.ui.label import Label
from components.ui.label_value import LabelValue
from components.ui import ui_constants
from core import game_globals, runtime_globals
from core.animation import PetFrame
from core.combat.game_battle import GameBattle
from core.combat.sim.models import Digimon, BattleProtocol
from core.game_module import sprite_load
from core.utils.module_utils import get_module
from core.utils.pet_utils import distribute_pets_evenly, get_battle_targets
from core.utils.pygame_utils import blit_with_cache, get_font, load_attack_sprites, module_attack_sprites, sprite_load_percent
from core.utils.scene_utils import change_scene
from core.utils.utils_unlocks import unlock_item
from core.utils import inventory_utils
from core.combat.sim.global_battle_simulator import GlobalBattleSimulator
from core import constants
from core.combat import combat_constants
from core.game_quest import QuestType
from core.utils.quest_event_utils import update_quest_progress

#=====================================================================
# BattleEncounter Class
#=====================================================================

BAR_COUNTER = 20  # Number of frames for the bar counter

class BattleEncounter:
    """
    Handles the logic and rendering for a battle encounter.
    """

    #========================
    # Region: Setup & State
    #========================

    def __init__(self, module, area=0, round=0, version=1, pvp_mode=False, is_random_encounter=False):
        """
        Initializes the BattleEncounter, loading graphics and setting initial state.
        """
        # Load module-specific attack sprites for pets and enemies
        self.pvp_mode = pvp_mode
        self.is_random_encounter = is_random_encounter
        self.module_attack_sprites = {}
        self.module = get_module(module)
        self.set_initial_state(area, round, version)

        # Initialize UI Manager and AnimatedSprite component for battle result animations
        self.ui_manager = UIManager()
        self.animated_sprite = AnimatedSprite(self.ui_manager)

        # Initialize minigames for different rulesets
        self.reset_minigames()

        # Create a top-centered HPBar using screen/global coordinates (not within the reduced UI area)
        width_scale = runtime_globals.SCREEN_WIDTH / 240
        left_bar_w = int(100 * width_scale)
        center_s = int(29 * width_scale)
        right_bar_w = int(100 * width_scale)
        total_w = left_bar_w + center_s + right_bar_w
        bar_h = max(29, int(29 * width_scale))
        x = (runtime_globals.SCREEN_WIDTH - total_w) // 2
        y = int(6 * width_scale)

        self.hp_bar = HPBar(0, 0, total_w, bar_h)
        # Position using screen coordinates so UIManager scaling isn't required for placement
        self.hp_bar.rect = pygame.Rect(x, y, total_w, bar_h)
        # Provide ui_scale via manager so internal scaling of bar internals matches screen sizing
        self.hp_bar.manager = self.ui_manager
        # Default mode for non-versus encounters - pass module for BattleIcon display
        self.hp_bar.set_mode('adventure', module=self.module)
        # Attempt to load center sprite now that manager is available
        self.hp_bar.on_manager_set()
        # Initialize totals if battle_player already exists
            
        self.hp_bar.set_totals(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)
        self.hp_bar.set_values(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)


        self.font = get_font(runtime_globals.FONT_SIZE_LARGE)
        self.font_small = get_font(runtime_globals.FONT_SIZE_MEDIUM)
        # Note: All sprites now handled by AnimatedSprite component

        self.attack_sprites = load_attack_sprites()
        
        self.load_module_attack_sprites()
        
        self.hit_animation_frames = self.load_hit_animation()
        self.hit_animations = []
        self.turn_limit = 12
        self.super_hits = 0
        self.strength = 0
        
        # Cache for result screen rendering (everything except animated pets)
        self.result_surface_cache = None
        self.result_animation_started = False

        # Load KO overlay sprite, scaled to pet size (preserving aspect ratio)
        self._ko_sprite = self._load_ko_sprite(runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT)
        boss_w = int(runtime_globals.PET_WIDTH * constants.BOSS_MULTIPLIER)
        boss_h = int(runtime_globals.PET_HEIGHT * constants.BOSS_MULTIPLIER)
        self._ko_sprite_boss = self._load_ko_sprite(boss_w, boss_h)
        

    def set_initial_state(self, area=0, round=0, version=1):
        """
        Set all non-graphic variables for (re)initialization.
        """
        # --- Jumper Gate: skip to boss if status_boost is active ---
        if not self.pvp_mode:
            skip_effect = self.get_battle_effect("skip_to_boss")
            if skip_effect and skip_effect.get("amount", 0) > 0:
                # Find the next boss round for this area
                current_area = game_globals.battle_area[self.module.name] if area == 0 else area
                round_to_check = game_globals.battle_round[self.module.name] if round == 0 else round
                # Only skip if not already at boss
                while not self.module.is_boss(current_area, round_to_check, version):
                    round_to_check += 1
                # Use local variables for area and round
                area = current_area
                round = round_to_check  # Set round to boss round

        self.phase = "level"
        self.after_attack_phase = None
        self.victory_status = None
        self.bonus_experience = 0
        self.frame_counter = 0
        self.result_timer = 0
        self.enemies = []
        
        # Reset result screen cache
        self.result_surface_cache = None
        self.result_animation_started = False

        if self.pvp_mode:
            self.area = 0
            self.round = 0

            self.boss = False
            self.enemy_entry_counter = 0
        else:
            # Use self.area and self.round, not the global values
            self.area = area if area != 0 else game_globals.battle_area[self.module.name]
            self.round = round if round != 0 else game_globals.battle_round[self.module.name]

            self.boss = self.module.is_boss(self.area, self.round, version)
            # For "Next and Reset" style, only flag as boss on the very last area
            if self.boss and getattr(self.module, 'adventure_style', 'Area Selection') == "Next and Reset":
                if self.module.area_exists(self.area + 1):
                    self.boss = False
            self.enemy_entry_counter = runtime_globals.PET_WIDTH + (2 * runtime_globals.UI_SCALE)

            # --- Apply XAI roll boost (Seven Switch) ---
            xai_effect = self.get_battle_effect("xai_roll")
            if xai_effect:
                xai_val = xai_effect.get("amount", None)
                if xai_val is not None:
                    runtime_globals.game_console.log(f"[BattleEncounter] XAI roll boost applied: {xai_val}")

            # --- Apply EXP multiplier boost (EXP Coat) ---
            exp_effect = self.get_battle_effect("exp_multiplier")
            if exp_effect:
                exp_val = exp_effect.get("amount", None)
                if exp_val is not None:
                    runtime_globals.game_console.log(f"[BattleEncounter] EXP multiplier boost applied: x{exp_val}")

            # --- Apply Jumper Gate boost ---
            skip_effect = self.get_battle_effect("skip_to_boss")
            if skip_effect:
                skip_val = skip_effect.get("amount", None)
                if skip_val:
                    runtime_globals.game_console.log(f"[BattleEncounter] Jumper Gate: Skipping to boss round.")

        if self.pvp_mode:
            self.hp_boost = 0
            self.attack_boost = 0
            self.strength_bonus = 0
            self.power_bonus = 0
        else:
            self.load_enemies()

            # --- Apply HP boost from status_boost items if present ---
            self.hp_boost = 0
            hp_effect = self.get_battle_effect("hp")
            if hp_effect:
                self.hp_boost = hp_effect.get("amount", 0)
                runtime_globals.game_console.log(f"[BattleEncounter] HP boost applied: +{self.hp_boost}")

            # --- Apply Attack boost from status_boost items (DMX ruleset) ---
            self.attack_boost = 0
            attack_effect = self.get_battle_effect("attack")
            if attack_effect:
                self.attack_boost = attack_effect.get("amount", 0)
                runtime_globals.game_console.log(f"[BattleEncounter] Attack boost applied: +{self.attack_boost}")

            # --- Apply Strength boost from status_boost items (PW Board) ---
            self.strength_bonus = 0
            strength_effect = self.get_battle_effect("strength")
            if strength_effect:
                self.strength_bonus = strength_effect.get("amount", 0)
                runtime_globals.game_console.log(f"[BattleEncounter] Strength boost applied: +{self.strength_bonus}")

            # --- Apply Power boost from status_boost items ---
            self.power_bonus = 0
            power_effect = self.get_battle_effect("power")
            if power_effect:
                self.power_bonus = power_effect.get("amount", 0)
                runtime_globals.game_console.log(f"[BattleEncounter] Power boost applied: +{self.power_bonus}")

        self.battle_player = GameBattle(get_battle_targets(), self.enemies, self.hp_boost, self.attack_boost, self.module)
        # PvP ordering flag: when True, enemy actions are processed before pets
        self.enemy_first = False
        
        # For PvP mode, use staggered cooldowns to prevent simultaneous attacks
        if self.pvp_mode:
            self.battle_player.reset_cooldowns_staggered()

        # Debug battle log display (when DEBUG flag is on)
        self.debug_battle_logs = []  # List of log entries per pet position: [{"turn": int, "hit": str, "arrow": str}, ...]
        self.init_debug_battle_logs()

        # Reload module attack sprites for the current battle participants
        self.load_module_attack_sprites()
        
        # Reset minigames and counters
        self.reset_minigames()
        
        # Reset and update HPBar with new battle values
        if hasattr(self, 'hp_bar') and self.hp_bar:
            self.hp_bar.set_totals(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)
            self.hp_bar.set_values(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)

    def prime_enemy_first(self):
        """Configure this encounter so enemy actions are processed before pets.

        This sets the flag and primes the BattlePlayer shot/phase arrays so
        the enemy (team2) will fire on the first update cycle.
        """
        self.enemy_first = True
        if not hasattr(self, 'battle_player') or self.battle_player is None:
            return
        bp = self.battle_player
        # Set enemy_first on GameBattle so it knows to increment turns after pet attacks
        bp.enemy_first = True
        n = max(len(bp.team1), len(bp.team2))
        for i in range(n):
            if i < len(bp.team1_shot):
                bp.team1_shot[i] = False
            if i < len(bp.team2_shot):
                bp.team2_shot[i] = True
            if i < len(bp.phase):
                bp.phase[i] = "enemy_attack"
        
        # For PvP clients, use staggered cooldowns to ensure proper synchronization
        if self.pvp_mode:
            bp.reset_cooldowns_staggered()

    def reset_minigames(self):
        """Reset all minigame instances and related counters."""
        # Reset minigame counters
        self.press_counter = 0
        self.rotation_index = 0
        self.super_hits = 0
        self.strength = 0
        self.xai_phase = 0
        
        # Clean up minigame instances
        self.count_match = None
        self.count_match_classic = None
        self.count_match_z = None
        self.dummy_charge = None
        self.shake_punch = None
        self.xai_roll = None
        self.xai_bar = None

    def get_battle_effect(self, effect_name, default=None):
        """
        Get a battle effect value if it applies to this battle.
        Only returns effects for non-PvP battles that match the current module.
        
        Args:
            effect_name: Name of the effect to retrieve
            default: Default value to return if effect doesn't exist or doesn't apply
            
        Returns:
            The effect dict if it exists and applies, otherwise default
        """
        if self.pvp_mode:
            return default
            
        if effect_name not in game_globals.battle_effects:
            return default
            
        effect = game_globals.battle_effects[effect_name]
        
        # Check if effect has module restriction
        if "module" in effect:
            if effect["module"] != self.module.name:
                return default
        
        return effect

    def setup_pvp_teams(self, my_pets, enemy_pet_data, is_host: bool = True):
        """Sets up teams for PvP battle from pet data.

        Args:
            my_pets: List of GamePet objects for the local device.
            enemy_pet_data: List of dicts describing the remote team.
            is_host: True if this device is the PvP host (device1),
                     False if it's the client (device2). Used to
                     configure the HP bar mode (pvp_host/pvp_client).
        """
        from core.game_enemy import GameEnemy
        
        # Create enemy objects from received pet data
        enemy_objects = []
        for i, pet_data in enumerate(enemy_pet_data):
            # Create GameEnemy with the pet data
            enemy = GameEnemy(
                name=pet_data["name"], 
                power=pet_data["power"],
                attribute=pet_data["attribute"], 
                area=0,  # PvP doesn't use area/round
                round=0,
                version=1,  # Default version
                atk_main=pet_data["atk_main"],
                atk_alt=pet_data["atk_alt"],
                handicap=0,  # No handicap in PvP
                id=i,  # Use index as ID
                stage=pet_data["stage"],
                hp=pet_data["hp"],
                unlock="",  # No unlock requirements for PvP
                prize="",  # No prizes in PvP
                mini_game=pet_data.get("mini_game", 0)  # Strength/MiniGame score for attack patterns
            )
            
            # Set additional properties that might be needed
            enemy.level = pet_data["level"]
            enemy.sick = 1 if pet_data["sick"] else 0
            enemy.traited = pet_data["traited"]
            enemy.shook = pet_data["shook"]
            enemy.module = pet_data["module"]
            
            # Load sprite for the enemy
            enemy.load_sprite(enemy.module, boss=False)
            
            enemy_objects.append(enemy)
        
        # Update battle_player with PvP teams (my pets vs enemy objects)
        self.battle_player = GameBattle(my_pets, enemy_objects, 0, 0, self.module)
        self.enemies = enemy_objects
        
        # Update HP bar for PvP mode
        if hasattr(self, 'hp_bar') and self.hp_bar:
            # Use dedicated PvP modes so the local player's side is always red
            # and the remote side blue, regardless of host/client role.
            if is_host:
                # Host is device1 on the left
                self.hp_bar.set_mode('pvp_host', module=self.module)
            else:
                # Client is device2 on the right
                self.hp_bar.set_mode('pvp_client', module=self.module)

            # Left bar = device1 / team2_total_hp, right bar = device2 / team1_total_hp
            # This ordering matches the adventure/PvE layout we use elsewhere.
            self.hp_bar.set_totals(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)
            self.hp_bar.set_values(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)
        
        # Initialize debug logs for PvP
        if game_globals.configuration.debug_mode:
            self.init_debug_battle_logs()

    def init_debug_battle_logs(self):
        """Initialize debug battle log entries for each pet position."""
        if not game_globals.configuration.debug_mode:
            return
        
        num_pets = len(get_battle_targets()) if not self.pvp_mode else len(self.battle_player.team1)
        self.debug_battle_logs = []
        for i in range(num_pets):
            self.debug_battle_logs.append({
                "turn": 1,
                "hit": "",
                "arrow": ""
            })

    def update_debug_battle_logs(self):
        """Update debug battle logs with current phase information and hit results."""
        if not game_globals.configuration.debug_mode or not hasattr(self, 'debug_battle_logs'):
            return
            
        for i in range(len(self.debug_battle_logs)):
            if i >= len(self.battle_player.phase) or i >= len(self.battle_player.turns):
                continue
                
            phase = self.battle_player.phase[i]
            turn = self.battle_player.turns[i]
            
            # Update turn number
            self.debug_battle_logs[i]["turn"] = turn
            
            # Update arrow and hit info based on phase
            if phase == "pet_charge":
                self.debug_battle_logs[i]["arrow"] = ">"
                # Show last hit result if available
                self.debug_battle_logs[i]["hit"] = self.get_last_hit_result(i, "pet")
            elif phase == "pet_attack":
                self.debug_battle_logs[i]["arrow"] = ">"
                self.debug_battle_logs[i]["hit"] = ""
            elif phase == "enemy_charge":
                self.debug_battle_logs[i]["arrow"] = "<"
                # Show last hit result if available
                self.debug_battle_logs[i]["hit"] = self.get_last_hit_result(i, "enemy")
            elif phase == "enemy_attack":
                self.debug_battle_logs[i]["arrow"] = "<"
                self.debug_battle_logs[i]["hit"] = ""
            else:
                self.debug_battle_logs[i]["arrow"] = ""
                self.debug_battle_logs[i]["hit"] = ""

    def get_last_hit_result(self, pet_index, attacker_type):
        """Get the last hit result for display in debug logs."""
        if not hasattr(self, 'global_battle_log') or not self.global_battle_log:
            return ""
            
        try:
            # Predict the upcoming attack for the current turn (show before it lands)
            turn = self.battle_player.turns[pet_index]
            turn_idx = max(0, int(turn) - 1)  # use current turn (0-based)
            if turn_idx < len(self.global_battle_log.battle_log):
                turn_log = self.global_battle_log.battle_log[turn_idx]

                # Support both dataclass objects and dict shapes
                attacks = None
                if hasattr(turn_log, 'attacks'):
                    attacks = turn_log.attacks
                elif isinstance(turn_log, dict):
                    attacks = turn_log.get('attacks', [])
                else:
                    attacks = []

                for attack in attacks:
                    # extract fields generically
                    if isinstance(attack, dict):
                        dev = attack.get('device')
                        attacker = attack.get('attacker')
                        defender = attack.get('defender')
                        hit = attack.get('hit')
                        damage = attack.get('damage', 0)
                    else:
                        dev = getattr(attack, 'device', None)
                        attacker = getattr(attack, 'attacker', None)
                        defender = getattr(attack, 'defender', None)
                        hit = getattr(attack, 'hit', None)
                        damage = getattr(attack, 'damage', 0)

                    try:
                        attacker = int(attacker) if attacker is not None else None
                    except Exception:
                        attacker = None
                    try:
                        defender = int(defender) if defender is not None else None
                    except Exception:
                        defender = None

                    if attacker_type == 'pet' and dev == 'device1' and attacker == pet_index:
                        if not hit:
                            return 'Miss!'
                        if damage <= 2:
                            return 'Hit!'
                        if damage == 3:
                            return 'SuperHit!'
                        if damage >= 4:
                            return 'MegaHit!'
                        return 'Hit!'

                    if attacker_type == 'enemy' and dev == 'device2' and defender == pet_index:
                        if not hit:
                            return 'Miss!'
                        if damage <= 2:
                            return 'Hit!'
                        if damage == 3:
                            return 'SuperHit!'
                        if damage >= 4:
                            return 'MegaHit!'
                        return 'Hit!'
        except:
            pass
            
        return ""

    def get_hit_text_color(self, hit_text):
        """Get the color for hit text display."""
        if hit_text == "Miss!":
            return constants.FONT_COLOR_RED
        elif hit_text == "Hit!":
            return constants.FONT_COLOR_DEFAULT  # White
        elif hit_text == "SuperHit!":
            return constants.FONT_COLOR_GREEN
        elif hit_text == "MegaHit!":
            return (255, 192, 203)  # Pink
        else:
            return constants.FONT_COLOR_DEFAULT

    def load_enemies(self):
        """
        Loads enemy data for the current area and round, sets up enemy positions and health.
        """
        selected_pets = get_battle_targets()
        version_range = self.module.get_enemy_versions(self.area, self.round)
        versions = []
        for p in selected_pets:
            if not version_range:
                versions.append(p.version)
            elif p.version not in version_range:
                versions.append(random.choice(version_range))
            else:
                versions.append(p.version)

        self.enemies = self.module.get_enemies(self.area, self.round, versions)
        if self.boss:
            # If it's a boss, ensure we have only one enemy
            self.enemies = [self.enemies[0]] if self.enemies else []

        for enemy in self.enemies:
            if enemy:
                enemy.load_sprite(self.module.name, self.boss)

    def _load_ko_sprite(self, target_w, target_h):
        """Load KO.png and scale it to fit within target dimensions, preserving aspect ratio."""
        raw = sprite_load(constants.KO_PATH)
        if raw is None:
            return None
        orig_w, orig_h = raw.get_size()
        if orig_w == 0 or orig_h == 0:
            return None
        ratio = min(target_w / orig_w, target_h / orig_h)
        new_w = max(1, int(orig_w * ratio))
        new_h = max(1, int(orig_h * ratio))
        return pygame.transform.smoothscale(raw, (new_w, new_h)).convert_alpha()

    def load_hit_animation(self):
        """
        Loads the hit animation sprite sheet and splits it into frames.
        """
        sprite_sheet = sprite_load(constants.HIT_ANIMATION_PATH, (runtime_globals.PET_WIDTH * 12, runtime_globals.PET_HEIGHT))
        frames = []
        for i in range(12):
            frame = sprite_sheet.subsurface(pygame.Rect(i * runtime_globals.PET_WIDTH, 0, runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT))
            frames.append(frame)
        return frames

    def load_module_attack_sprites(self):
        """
        Load module-specific attack sprites for all pets and enemies in battle.
        """
        # Get all unique modules from pets and enemies
        modules_to_load = set()
        
        # Add modules from battle targets (pets)
        for pet in get_battle_targets():
            modules_to_load.add(pet.module)
        
        # Add module from enemies (they use the same module as the battle area)
        modules_to_load.add(self.module.name)
        
        # Load sprites for each unique module
        for module_name in modules_to_load:
            self.module_attack_sprites[module_name] = module_attack_sprites(module_name)

    def get_attack_sprite(self, entity, attack_id):
        """
        Get attack sprite for a pet or enemy, preferring module-specific sprites over defaults.
        """
        module_name = getattr(entity, 'module', self.module.name)
        
        # First try module-specific attack sprites
        if module_name in self.module_attack_sprites:
            module_sprite = self.module_attack_sprites[module_name].get(str(attack_id))
            if module_sprite:
                return module_sprite
        
        # Fall back to default attack sprites
        return self.attack_sprites.get(str(attack_id))

    #========================
    # Region: Update Methods
    #========================

    def update(self):
        """
        Main update loop for the battle encounter, calls phase-specific updates.
        """
        self.frame_counter += 1
        self.battle_player.increment_frame_counters()
        
        # Update AnimatedSprite component
        self.animated_sprite.update()

        if self.phase == "level":
            self.update_level()
        elif self.phase == "entry":
            self.update_entry()
        elif self.phase == "intimidate":
            self.update_intimidate()
        elif self.phase == "alert":
            self.update_alert()
        elif self.phase == "charge":
            self.update_charge()
        elif self.phase == "battle":
            self.update_battle()
        elif self.phase == "clear":
            self.update_clear()
        elif self.phase == "result":
            self.update_result()

        runtime_globals.game_message.update()

        advance_every = max(1, int( constants.FRAME_RATE // 15))
        if self.frame_counter % advance_every == 0:
            for anim in self.hit_animations:
                anim[0] += 1  # Advance one frame

        self.hit_animations = [a for a in self.hit_animations if a[0] < len(self.hit_animation_frames)]

    def update_level(self):
        """
        Update logic for the level phase, transitions to entry phase after duration.
        """
        if self.frame_counter >= combat_constants.LEVEL_DURATION_FRAMES:
            self.phase = "entry"
            self.frame_counter = 0
            runtime_globals.game_sound.play("battle")

    def update_entry(self):
        """
        Update logic for the enemy entry phase, moves enemies into position.
        """

        self.enemy_entry_counter -= combat_constants.ENEMY_ENTRY_SPEED * (30 / constants.FRAME_RATE)  # Frame-rate independent speed

        if self.enemy_entry_counter <= 0:
            runtime_globals.game_console.log("Entering intimidate phase")
            self.phase = "intimidate"
            self.frame_counter = 0
            self.enemy_entry_counter = 0
            self.battle_player.reset_frame_counters()
            
            # Start intimidate animation once when entering phase
            duration = 3.0  # 3 second intimidate animation (increased from 2.0)
            if self.boss:
                # Use warning animation for boss (intimidating)
                self.animated_sprite.play_warning(duration)
            else:
                # Use battle animation for normal battle
                self.animated_sprite.play_battle(duration)

    def update_intimidate(self):
        """
        Update logic for the intimidate phase, transitions to alert phase.
        """
        if self.frame_counter >= combat_constants.IDLE_ANIM_DURATION:
            self.phase = "alert"
            self.frame_counter = 0
            # Stop intimidate animation when exiting phase
            self.animated_sprite.stop()
            
            # Reset minigames before alert phase
            self.reset_minigames()

            if self.module.ruleset == "penc":
                # For PenC, initialize count match minigame early for alert phase drawing
                pets = get_battle_targets()
                self.count_match = CountMatch(self.ui_manager, pets[0], self.animated_sprite)
                self.count_match.set_phase("ready")

    def update_alert(self):
        """
        Update logic for the alert phase, prepares for charge phase after duration.
        """
        if self.frame_counter == int(combat_constants.ALERT_DURATION_FRAMES * 0.8):
            runtime_globals.game_sound.play("happy")
        elif self.frame_counter > combat_constants.ALERT_DURATION_FRAMES:
            runtime_globals.game_console.log("Entering charge phase")
            self.phase = "charge"
            self.frame_counter = 0
            self.bar_timer = pygame.time.get_ticks()
            self.setup_charge()

    def setup_charge(self):
        """
        Setup logic for the charge phase, varies by module's battle_minigame setting.
        battle_minigame options: "None", "Dummy Bar", "Count Match (Color)", "Count Match", 
                                 "Count Match (Z)", "Xai Roll+Bar", "Xai Bar", "Punch", "Mogera"
        """
        minigame = getattr(self.module, 'battle_minigame', 'Dummy Bar')
        pets = get_battle_targets()
        
        if minigame == "None":
            # Skip charge phase, use default minigame result of 2
            self.strength = 2
            self.minigame_result = 2
        elif minigame == "Dummy Bar":
            # Dummy charge minigame (A button presses)
            self.bar_level = 14
            self.battle_player.reset_frame_counters()
            self.dummy_charge = DummyCharge(self.ui_manager, "RED")
        elif minigame == "Count Match (Color)":
            # Color count match minigame (shake-based with attribute colors)
            self.rotation_index = 3
            if not self.count_match:
                self.count_match = CountMatch(self.ui_manager, pets[0] if pets else None, self.animated_sprite)
            self.count_match.set_phase("count")
        elif minigame == "Count Match":
            # Count Match Classic (shake-based, 0-14 like Dummy Bar)
            self.bar_level = 14
            self.count_match_classic = CountMatchClassic(self.ui_manager)
        elif minigame == "Count Match (Z)":
            # Count Match Z (arrow-based with attribute scoring)
            if not self.count_match_z:
                self.count_match_z = CountMatchZ(self.ui_manager, pets[0] if pets else None, self.animated_sprite)
            self.count_match_z.set_phase("count")
        elif minigame == "Xai Roll+Bar":
            # XAI roll and bar minigame
            self.xai_phase = 1
            self.xai_roll = XaiRoll(
                x=runtime_globals.SCREEN_WIDTH // 2 - int(100 * runtime_globals.UI_SCALE) // 2,
                y=runtime_globals.SCREEN_HEIGHT // 2 - int(100 * runtime_globals.UI_SCALE) // 2,
                width=int(100 * runtime_globals.UI_SCALE),
                height=int(100 * runtime_globals.UI_SCALE),
                xai_number=1
            )
            self.xai_roll.roll()
        elif minigame == "Xai Bar":
            # XAI bar only (skips roll, uses daily xai value)
            self.xai_phase = 2
            self.xai_bar = XaiBar(
                x=runtime_globals.SCREEN_WIDTH // 2 - int(152 * runtime_globals.UI_SCALE) // 2,
                y=runtime_globals.SCREEN_HEIGHT // 2 - int(72 * runtime_globals.UI_SCALE) // 2 + int(48 * runtime_globals.UI_SCALE),
                xai_number=game_globals.xai,
                pet=pets[0] if pets else None
            )
            self.xai_bar.start()
        elif minigame == "Punch":
            # Shake punch minigame
            self.bar_level = 20
            self.shake_punch = ShakePunch(self.ui_manager, pets)
            self.shake_punch.set_phase("punch")
        elif minigame == "Mogera":
            # Mogera minigame - uses same shake punch component for now
            self.bar_level = 20
            self.shake_punch = ShakePunch(self.ui_manager, pets)
            self.shake_punch.set_phase("punch")

    def update_charge(self):
        """
        Update logic for the charge phase, handles input and transitions to pet_charge phase.
        """
        minigame = getattr(self.module, 'battle_minigame', 'Dummy Bar')
        
        # Update minigames based on battle_minigame setting
        if minigame == "None":
            # Immediately transition - no minigame
            pass
        elif minigame == "Dummy Bar" and self.dummy_charge:
            self.dummy_charge.update()
            self.strength = self.dummy_charge.strength
        elif minigame == "Count Match (Color)" and self.count_match:
            self.count_match.update()
            self.press_counter = self.count_match.get_press_counter()
            self.rotation_index = self.count_match.get_rotation_index()
        elif minigame == "Count Match" and self.count_match_classic:
            self.count_match_classic.update()
            self.strength = self.count_match_classic.strength
        elif minigame == "Count Match (Z)" and self.count_match_z:
            self.count_match_z.update()
            self.press_counter = self.count_match_z.get_press_counter()
        elif minigame == "Punch" and self.shake_punch:
            self.shake_punch.update()
            self.strength = self.shake_punch.get_strength()
        elif minigame == "Mogera" and self.shake_punch:
            self.shake_punch.update()
            self.strength = self.shake_punch.get_strength()
        elif minigame in ["Xai Roll+Bar", "Xai Bar"]:
            if self.xai_phase == 1 and self.xai_roll:
                self.xai_roll.update()
                if not self.xai_roll.rolling and not self.xai_roll.stopping:
                    self.xai_phase = 2
                    pets = get_battle_targets()
                    self.xai_bar = XaiBar(
                        x=runtime_globals.SCREEN_WIDTH // 2 - int(152 * runtime_globals.UI_SCALE) // 2,
                        y=runtime_globals.SCREEN_HEIGHT // 2 - int(72 * runtime_globals.UI_SCALE) // 2 + int(48 * runtime_globals.UI_SCALE),
                        xai_number=getattr(self, 'xai_number', game_globals.xai),
                        pet=pets[0] if pets else None
                    )
                    self.xai_bar.start()
            elif self.xai_phase == 2 and self.xai_bar:
                self.xai_bar.update()
        
        # Check if minigame time is up and transition to battle
        time_up = False
        if minigame == "None":
            time_up = True  # Immediately proceed
        elif minigame in ["Punch", "Mogera"] and self.shake_punch:
            time_up = self.shake_punch.is_time_up() or self.strength >= 20
        elif minigame in ["Xai Roll+Bar", "Xai Bar"]:
            time_up = self.xai_phase == 3
        else:
            time_up = pygame.time.get_ticks() - self.bar_timer > combat_constants.BAR_HOLD_TIME_MS
        
        if time_up:
            runtime_globals.game_console.log("Entering battle phase")
            self.phase = "battle"
            self.frame_counter = 0
            self.animated_sprite.stop()
            self.battle_player.reset_frame_counters()
            self.battle_player.reset_jump_and_forward()
            # Reset projectile delta-time trackers for the new battle phase
            self._last_pet_proj_tick = pygame.time.get_ticks()
            self._last_enemy_proj_tick = pygame.time.get_ticks()
            if minigame == "Count Match (Color)":
                self.calculate_results()
            elif minigame == "Count Match (Z)" and self.count_match_z:
                self.minigame_result = self.count_match_z.calculate_result()
            self.calculate_combat_for_pairs()

    def calculate_results(self):
        self.correct_color = self.get_first_pet_attribute()
        self.final_color = self.rotation_index
        pets = self.battle_player.team1
        if not pets:
            return

        # Calculate hits for the first pet only
        pet = pets[0]
        shakes = self.press_counter
        attr_type = getattr(pet, "attribute", "")


        if shakes < 2:
            hits = 0
        else:
            # Color mapping: 1=Red, 2=Yellow, 3=Blue
            color = self.final_color
            if attr_type in ("", "Va"):
                if color == 1:      # Red
                    hits = 3
                elif color == 2:    # Yellow
                    hits = 2
                elif color == 3:    # Blue
                    hits = 1
                else:
                    hits = 0
            elif attr_type == "Da":
                if color == 2:      # Yellow
                    hits = 3
                elif color == 1:    # Red
                    hits = 2
                elif color == 3:    # Blue
                    hits = 1
                else:
                    hits = 0
            elif attr_type == "Vi":
                if color == 3:      # Blue
                    hits = 3
                elif color == 2:    # Yellow
                    hits = 2
                elif color == 1:    # Red
                    hits = 1
                else:
                    hits = 0
            else:
                hits = 0

        # Assign the same result to all pets
        self.super_hits = hits

    def get_first_pet_attribute(self):
        """
        Get the attribute of the first pet, used for determining attack color in charge phase.
        """
        pet = get_battle_targets()[0]
        if pet.attribute in ["", "Va"]:
            return 1
        elif pet.attribute == "Da":
            return 2
        elif pet.attribute == "Vi":
            return 3
        return 1
    
    def process_battle_results(self):
        """
        Processes the results of a global protocol battle using the new log structure.
        """
        # Skip experience and level-ups for PvP mode
        if self.pvp_mode:
            runtime_globals.game_console.log("[BattleEncounter] PvP battle completed - no experience awarded")
            return
            
        # If defeat, no XP for anyone
        if self.victory_status == "Defeat":
            self.battle_player.xp = 0
            self.battle_player.bonus = 0
            # Call finish_battle here to update DP, battle number, and win rate for a loss.
            for i, pet in enumerate(self.battle_player.team1):
                pet.finish_battle(self.victory_status == "Victory", self.battle_player.team2[0], self.area, (self.boss or not self.module.battle_sequential_rounds), is_random_encounter=self.is_random_encounter)
            return

        # If victory, calculate XP for winners and bonus
        xp_multiplier = 1
        exp_effect = self.get_battle_effect("exp_multiplier")
        if exp_effect:
            xp_multiplier = exp_effect.get("amount", 1)
        boss = self.boss

        self.battle_player.xp = int((2.83 * self.battle_player.team2[0].stage) + (0.81 * self.battle_player.team2[0].power) + (0.17 * self.round) + ((0.67 * self.area) * (6.39 if boss else 0))) * xp_multiplier
        #total_xp = int(self.battle_player.xp * len(self.battle_player.team1))

        if all(digimonstatus.alive for digimonstatus in self.global_battle_log.device1_final):
            # If all pets are alive, apply bonus XP
            self.battle_player.bonus = int(self.battle_player.xp * 0.1)

        for i, pet in enumerate(self.battle_player.team1):
            prev_level = getattr(pet, "level", 1)
            # Add XP and bonus to pet, check for level up
            if hasattr(pet, "add_experience"):
                pet.add_experience(self.battle_player.xp + self.battle_player.bonus)
                self.battle_player.level_up[i] = getattr(pet, "level", 1) > prev_level
            else:
                self.battle_player.level_up[i] = False

            pet.finish_battle(self.victory_status == "Victory", self.battle_player.team2[0], self.area, (self.boss or not self.module.battle_sequential_rounds), is_random_encounter=self.is_random_encounter)

        # --- Prize logic for Victory ---
        self.prize_item = None
        if self.victory_status == "Victory":
            # Collect all enemies with a prize
            prize_enemies = [e for e in self.battle_player.team2 if hasattr(e, "prize") and e.prize]
            if prize_enemies:
                chosen_enemy = random.choice(prize_enemies)
                prize_name = getattr(chosen_enemy, "prize", None)
                if prize_name and hasattr(self.module, "items") and self.module.items:
                    matching_items = [item for item in self.module.items if item.name == prize_name]
                    if matching_items:
                        self.prize_item = random.choice(matching_items)
                        inventory_utils.add_to_inventory(self.prize_item.id, 1)
                        runtime_globals.game_console.log(f"Received item: {self.prize_item.name}")

        # --- Remove expired boosts if boss or not sequential rounds ---
        if self.boss or not self.module.battle_sequential_rounds:
            to_remove = []
            for status, effect in game_globals.battle_effects.items():
                # Only decrement boosts for this module
                if "module" in effect and effect["module"] != self.module.name:
                    continue
                if "boost_time" in effect:
                    effect["boost_time"] -= 1
                    if effect["boost_time"] <= 0:
                        to_remove.append(status)
            if to_remove:
                runtime_globals.game_console.log(f"[BattleEncounter] Removing expired boosts: {', '.join(to_remove)}")
            for status in to_remove:
                del game_globals.battle_effects[status]

    def update_battle(self):
        self.battle_player.update()

        # Update debug battle logs based on current phases
        if game_globals.configuration.debug_mode:
            self.update_debug_battle_logs()
        self.hp_bar.update()
        
        # Process attacks based on enemy_first flag
        # For DCom battles: enemy attacks first (enemy_first=True)
        # For normal PvP/battles: player attacks first (enemy_first=False)
        if self.enemy_first:
            # Enemy attacks first (DCom V2 protocol - device2 initiates)
            for i in range(len(self.battle_player.team2)):
                if self.battle_player.turns[i] <= self.turn_limit and self.battle_player.team2_shot[i] and self.battle_player.phase[i] == "enemy_attack":
                    self.setup_enemy_attack(self.battle_player.team2[i])
                    self.battle_player.team2_shot[i] = False
            
            for i in range(len(self.battle_player.team1)):
                if self.battle_player.turns[i] <= self.turn_limit and self.battle_player.team1_shot[i] and self.battle_player.phase[i] == "pet_attack":
                    self.setup_pet_attack(self.battle_player.team1[i])
                    self.battle_player.team1_shot[i] = False
        else:
            # Player attacks first (normal order)
            for i in range(len(self.battle_player.team1)):
                if self.battle_player.turns[i] <= self.turn_limit and self.battle_player.team1_shot[i] and self.battle_player.phase[i] == "pet_attack":
                    self.setup_pet_attack(self.battle_player.team1[i])
                    self.battle_player.team1_shot[i] = False

            for i in range(len(self.battle_player.team2)):
                if self.battle_player.turns[i] <= self.turn_limit and self.battle_player.team2_shot[i] and self.battle_player.phase[i] == "enemy_attack":
                    self.setup_enemy_attack(self.battle_player.team2[i])
                    self.battle_player.team2_shot[i] = False

        self.update_battle_pet_projectiles()
        self.update_battle_enemy_projectiles()

        # Check for battle termination
        if self.pvp_mode:
            # For PvP, check if simulation is complete or if we've run out of battle log entries
            max_turn = max(self.battle_player.turns)
            battle_log_length = len(self.global_battle_log.battle_log) if hasattr(self.global_battle_log, 'battle_log') else 0
            
            # Check if all pets have finished their turns or reached the end of battle log
            if (all(turn > self.turn_limit for turn in self.battle_player.turns) or 
                max_turn > battle_log_length or
                all(phase == "result" for phase in self.battle_player.phase)):
                self.phase = "result" if not self.boss else "clear"
                self.frame_counter = 0
                runtime_globals.game_console.log(f"PvP battle finished: max_turn={max_turn}, log_length={battle_log_length}")
        else:
            # For PvE, use HP-based termination
            if self.battle_player.team1_total_hp <= 0 or self.battle_player.team2_total_hp <= 0 or all(turn > self.turn_limit for turn in self.battle_player.turns):
                self.phase = "result" if not self.boss else "clear"
                self.frame_counter = 0
                runtime_globals.game_console.log("All pairs finished battle, entering result phase")

    def setup_pet_attack(self, pet):
        """
        Sets up the pet's attack animation and projectiles using the global battle log.
        """
        # Find the index of the pet in team1
        pet_index = self.battle_player.team1.index(pet)

        # Determine the current turn (1-based)
        turn = self.battle_player.turns[pet_index]

        # Get the correct log entry for this turn
        if turn - 1 >= len(self.global_battle_log.battle_log):
            runtime_globals.game_console.log(f"[BattleEncounter] Invalid turn {turn} for pet {pet_index}, log length is {len(self.global_battle_log.battle_log)}")
            # Still need to set shot_wait so battle can progress to enemy turn
            self.battle_player.shot_wait[pet_index] = True
            return
        turn_log = self.global_battle_log.battle_log[turn - 1]

        # For PvP, determine which device this pet belongs to from the perspective of the battle log
        # Both devices use the same battle log and same visual team arrangement:
        # Team1 (left) = device1 pets, Team2 (right) = device2 pets
        if self.pvp_mode:
            # For DCom battles, device mapping is swapped: device1=opponent, device2=player
            # So team1 (player) should look for device2 attacks
            if hasattr(self, 'is_dcom_mode') and self.is_dcom_mode:
                device_label = "device2"  # Player is device2 in DCom battle logs
            else:
                # Normal PvP: team1 maps to device1
                device_label = "device1"
        else:
            # PvE: my pets are always device1
            device_label = "device1"

        # Find the attack entry for this pet
        attack_entry = next(
            (a for a in turn_log.attacks if a.device == device_label and a.attacker == pet_index),
            None
        )

        runtime_globals.game_console.log(f"Device {device_label} turn {turn} attack {attack_entry}")

        if not attack_entry:
            runtime_globals.game_console.log(f"[BattleEncounter] No attack entry found for pet {pet_index} in turn {turn} for device {device_label}")
            # Still need to set shot_wait so battle can progress to enemy turn
            self.battle_player.shot_wait[pet_index] = True
            return

        # ALWAYS use the attack pattern value, regardless of hit/miss
        # The 'damage' field stores the pattern value (1=weak, 2=strong)
        # The 'hit' field indicates whether the attack connected
        hits = attack_entry.damage
        defender_idx = attack_entry.defender if attack_entry else 0

        if pet_index != defender_idx:
            runtime_globals.game_console.log(f"[BattleEncounter] Pet {pet_index} attacking defender {defender_idx} with hits: {hits}")

        # Update debug battle log for this pet
        if game_globals.configuration.debug_mode and pet_index < len(self.debug_battle_logs):
            self.debug_battle_logs[pet_index]["turn"] = turn
            self.debug_battle_logs[pet_index]["arrow"] = ">"
            # Don't show hit info during attack phase, only during charge

        # Choose attack sprite based on protocol/ruleset
        # Cap hits at 5 for animation (bonuses don't affect animation)
        anim_hits = min(5, hits)
        
        if self.module.battle_damage_limit < 3:
            # DM20/PEN20/DM/DMC: 1-2 attack types, 70% atk_main / 30% atk_alt random
            if getattr(pet, "atk_alt", 0) > 0 and random.random() < 0.3:
                atk_id = str(pet.atk_alt)
            else:
                atk_id = str(pet.atk_main)
        else:
            # DMX/PENZ/INTERNAL_PVE: 1-5 attack types
            # 1-2 = atk_main, 3-4 = atk_alt (fallback to atk_main), 5 = atk_alt2 (fallback to atk_alt/atk_main)
            if anim_hits >= 5:
                if getattr(pet, "atk_alt2", 0) > 0:
                    atk_id = str(pet.atk_alt2)
                elif getattr(pet, "atk_alt", 0) > 0:
                    atk_id = str(pet.atk_alt)
                else:
                    atk_id = str(pet.atk_main)
            elif anim_hits >= 3:
                if getattr(pet, "atk_alt", 0) > 0:
                    atk_id = str(pet.atk_alt)
                else:
                    atk_id = str(pet.atk_main)
            else:
                atk_id = str(pet.atk_main)
        atk_sprite = self.get_attack_sprite(pet, atk_id)

        # Start position
        y = self.get_y(pet_index, len(self.battle_player.team1)) + atk_sprite.get_height() // 2
        x = self.get_team1_x(pet_index)

        # Target position
        if defender_idx < len(self.battle_player.team2):
            target_enemy = self.battle_player.team2[defender_idx]
            target_x = self.get_team2_x(defender_idx) + (runtime_globals.PET_WIDTH * constants.BOSS_MULTIPLIER if self.boss else runtime_globals.PET_WIDTH) // 2
            target_y = self.get_y(defender_idx, len(self.battle_player.team2)) + atk_sprite.get_height() // 2
        else:
            target_x, target_y = x, y

        dx = target_x - x
        dy = target_y - y
        angle = -math.degrees(math.atan2(dy, dx))
        atk_sprite = pygame.transform.flip(atk_sprite, True, True)
        rotated_sprite = pygame.transform.rotate(atk_sprite, angle)

        self.battle_player.team1_projectiles[pet_index] = []
        s = runtime_globals.UI_SCALE
        base_pos = [x, y]
        base_tgt = [target_x, target_y]
        if self.module.battle_damage_limit < 3:
            # DM20/PEN20/DM/DMC: 1 or 2 projectiles, scale2x for 2
            if anim_hits >= 2:
                rotated_sprite = pygame.transform.scale2x(rotated_sprite.copy())
            self.battle_player.team1_projectiles[pet_index].append([rotated_sprite, [x, y], [target_x, target_y], attack_entry])
        else:
            # DMX/PENZ/INTERNAL_PVE: multi-sprite attacks combined into single surface
            if anim_hits >= 5:
                # Critical: double size sprite
                rotated_sprite = pygame.transform.scale2x(rotated_sprite.copy())
                self.battle_player.team1_projectiles[pet_index].append([rotated_sprite, [x, y], [target_x, target_y], attack_entry])
            elif anim_hits == 4:
                # Double strong: 2 sprites combined (or 3 if no atk_alt)
                if getattr(pet, "atk_alt", 0) > 0:
                    offsets = [(0, 0), (-20*s, -10*s)]
                else:
                    offsets = [(0, 0), (-20*s, -10*s), (-40*s, 10*s)]
                self.battle_player.team1_projectiles[pet_index].append(
                    self._combine_projectile_sprites(rotated_sprite, offsets, base_pos, base_tgt, attack_entry))
            elif anim_hits == 3:
                if getattr(pet, "atk_alt", 0) > 0:
                    self.battle_player.team1_projectiles[pet_index].append([rotated_sprite.copy(), [x, y], [target_x, target_y], attack_entry])
                else:
                    offsets = [(0, 0), (-20*s, -10*s)]
                    self.battle_player.team1_projectiles[pet_index].append(
                        self._combine_projectile_sprites(rotated_sprite, offsets, base_pos, base_tgt, attack_entry))
            elif anim_hits == 2:
                offsets = [(0, 0), (-20*s, -10*s)]
                self.battle_player.team1_projectiles[pet_index].append(
                    self._combine_projectile_sprites(rotated_sprite, offsets, base_pos, base_tgt, attack_entry))
            else:
                self.battle_player.team1_projectiles[pet_index].append([rotated_sprite.copy(), [x, y], [target_x, target_y], attack_entry])

    def setup_enemy_attack(self, enemy):
        """
        Sets up the enemy's attack animation and projectiles using the global battle log.
        Handles boss attacks (multiple per turn).
        """
        # Find the index of the enemy in team2
        enemy_index = self.battle_player.team2.index(enemy)

        # Determine the current turn (1-based)
        turn = self.battle_player.turns[enemy_index]

        # Get the correct log entry for this turn
        if turn - 1 >= len(self.global_battle_log.battle_log):
            runtime_globals.game_console.log(f"[BattleEncounter] Invalid turn {turn} for enemy {enemy_index}, log length is {len(self.global_battle_log.battle_log)}")
            # Still need to set shot_wait so battle can progress
            self.battle_player.shot_wait[enemy_index] = True
            return
        turn_log = self.global_battle_log.battle_log[turn - 1]

        # For PvP, determine which device this enemy belongs to from the perspective of the battle log
        # Both devices use the same battle log and same visual team arrangement:
        # Team1 (left) = device1 pets, Team2 (right) = device2 pets
        if self.pvp_mode:
            # For DCom battles, device mapping is swapped: device1=opponent, device2=player
            # So team2 (enemy) should look for device1 attacks
            if hasattr(self, 'is_dcom_mode') and self.is_dcom_mode:
                device_label = "device1"  # Opponent is device1 in DCom battle logs
            else:
                # Normal PvP: team2 maps to device2
                device_label = "device2"
        else:
            # PvE: enemy attacks are always device2
            device_label = "device2"

        # For bosses, collect all attacks by this enemy in this turn
        attack_entries = [
            a for a in turn_log.attacks
            if a.device == device_label and a.attacker == enemy_index
        ]

        runtime_globals.game_console.log(f"Device {device_label} turn {turn} attack {attack_entries}")

        if not attack_entries:
            runtime_globals.game_console.log(f"[BattleEncounter] No attack entries found for enemy {enemy_index} in turn {turn} for device {device_label}")
            # Still need to set shot_wait so battle can progress to next turn
            self.battle_player.shot_wait[enemy_index] = True
            return

        # ALWAYS use the attack pattern value, regardless of hit/miss
        # The 'damage' field stores the pattern value (1=weak, 2=strong)
        # The 'hit' field indicates whether the attack connected
        hits = attack_entries[0].damage if attack_entries else 0
        # Cap hits at 5 for animation (bonuses don't affect animation)
        anim_hits = min(5, hits)
        
        # Update debug battle log for enemy attacks (affects the defender pet)
        if game_globals.configuration.debug_mode and attack_entries:
            for attack_entry in attack_entries:
                defender_idx = attack_entry.defender
                if defender_idx < len(self.debug_battle_logs):
                    self.debug_battle_logs[defender_idx]["turn"] = turn
                    self.debug_battle_logs[defender_idx]["arrow"] = "<"
                    # Don't show hit info during attack phase, only during charge
        
        # Choose attack sprite based on protocol/ruleset
        if self.module.battle_damage_limit < 3:
            # DM20/PEN20/DM/DMC: 1-2 attack types, 70% atk_main / 30% atk_alt random
            atk_alt = getattr(enemy, "atk_alt", None)
            if atk_alt is not None and atk_alt > 0 and random.random() < 0.3:
                atk_id = str(atk_alt)
            else:
                atk_id = str(getattr(enemy, "atk_main", 30))
        else:
            # DMX/PENZ/INTERNAL_PVE: 1-5 attack types
            atk_alt = getattr(enemy, "atk_alt", None)
            atk_alt2 = getattr(enemy, "atk_alt2", None)
            if anim_hits >= 5:
                if atk_alt2 is not None and atk_alt2 > 0:
                    atk_id = str(atk_alt2)
                elif atk_alt is not None and atk_alt > 0:
                    atk_id = str(atk_alt)
                else:
                    atk_id = str(getattr(enemy, "atk_main", 30))
            elif anim_hits >= 3:
                if atk_alt is not None and atk_alt > 0:
                    atk_id = str(atk_alt)
                else:
                    atk_id = str(getattr(enemy, "atk_main", 30))
            else:
                atk_id = str(getattr(enemy, "atk_main", 30))
        base_sprite = self.get_attack_sprite(enemy, atk_id)
        base_sprite = pygame.transform.flip(base_sprite, True, False)

        y = self.get_y(enemy_index, len(self.battle_player.team2)) + base_sprite.get_height() // 2
        x = self.get_team2_x(enemy_index) + (runtime_globals.PET_WIDTH * constants.BOSS_MULTIPLIER if self.boss else runtime_globals.PET_WIDTH) // 2

        # For each attack entry (boss may attack multiple pets in one turn)
        for attack_entry in attack_entries:
            defender_idx = attack_entry.defender if attack_entry else 0
            self.battle_player.team2_projectiles[defender_idx] = []
            # Target position
            if defender_idx < len(self.battle_player.team1):
                target_pet_x = self.get_team1_x(defender_idx) - (runtime_globals.PET_WIDTH // 2)
                target_pet_y = self.get_y(defender_idx, len(self.battle_player.team1)) + base_sprite.get_height() // 2
            else:
                target_pet_x, target_pet_y = x, y

            dx = target_pet_x - x
            dy = target_pet_y - y
            angle = -math.degrees(math.atan2(dy, dx))
            rotated_sprite = pygame.transform.rotate(base_sprite, angle)

            # Add projectile for this attack based on protocol/ruleset
            s = runtime_globals.UI_SCALE
            base_pos = [x, y]
            base_tgt = [target_pet_x, target_pet_y]
            if self.module.battle_damage_limit < 3:
                # DM20/PEN20/DM/DMC: 1 or 2 projectiles, scale2x for 2
                if anim_hits >= 2:
                    rotated_sprite = pygame.transform.scale2x(rotated_sprite)
                self.battle_player.team2_projectiles[defender_idx].append([rotated_sprite, [x, y], [target_pet_x, target_pet_y], attack_entry])
            else:
                # DMX/PENZ/INTERNAL_PVE: multi-sprite attacks combined into single surface
                if anim_hits >= 5:
                    # Critical: double size sprite
                    rotated_sprite = pygame.transform.scale2x(rotated_sprite)
                    self.battle_player.team2_projectiles[defender_idx].append([rotated_sprite, [x, y], [target_pet_x, target_pet_y], attack_entry])
                elif anim_hits == 4:
                    atk_alt = getattr(enemy, "atk_alt", None)
                    if atk_alt is not None and atk_alt > 0:
                        offsets = [(0, 0), (20*s, 10*s)]
                    else:
                        offsets = [(0, 0), (20*s, 10*s), (40*s, -10*s)]
                    self.battle_player.team2_projectiles[defender_idx].append(
                        self._combine_projectile_sprites(rotated_sprite, offsets, base_pos, base_tgt, attack_entry))
                elif anim_hits == 3:
                    atk_alt = getattr(enemy, "atk_alt", None)
                    if atk_alt is not None and atk_alt > 0:
                        self.battle_player.team2_projectiles[defender_idx].append([rotated_sprite, [x, y], [target_pet_x, target_pet_y], attack_entry])
                    else:
                        offsets = [(0, 0), (20*s, 10*s)]
                        self.battle_player.team2_projectiles[defender_idx].append(
                            self._combine_projectile_sprites(rotated_sprite, offsets, base_pos, base_tgt, attack_entry))
                elif anim_hits == 2:
                    offsets = [(0, 0), (20*s, 10*s)]
                    self.battle_player.team2_projectiles[defender_idx].append(
                        self._combine_projectile_sprites(rotated_sprite, offsets, base_pos, base_tgt, attack_entry))
                else:
                    self.battle_player.team2_projectiles[defender_idx].append([rotated_sprite, [x, y], [target_pet_x, target_pet_y], attack_entry])

    def _combine_projectile_sprites(self, sprite, offsets, base_pos, base_target, attack_entry):
        """Combine a sprite rendered at multiple offsets into a single projectile entry."""
        if len(offsets) == 1:
            ox, oy = offsets[0]
            return [sprite.copy(), [base_pos[0] + ox, base_pos[1] + oy],
                    [base_target[0] + ox, base_target[1] + oy], attack_entry]
        sw, sh = sprite.get_width(), sprite.get_height()
        min_ox = min(o[0] for o in offsets)
        min_oy = min(o[1] for o in offsets)
        max_ox = max(o[0] for o in offsets)
        max_oy = max(o[1] for o in offsets)
        width = int(max_ox - min_ox) + sw
        height = int(max_oy - min_oy) + sh
        combined = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()
        for ox, oy in offsets:
            combined.blit(sprite, (int(ox - min_ox), int(oy - min_oy)))
        return [combined,
                [base_pos[0] + min_ox, base_pos[1] + min_oy],
                [base_target[0] + min_ox, base_target[1] + min_oy],
                attack_entry]

    def move_towards(self, pos, target, speed):
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return pos
        step = min(speed, dist)
        return [pos[0] + dx / dist * step, pos[1] + dy / dist * step]


    def update_battle_pet_projectiles(self):
        if len(self.battle_player.team1_projectiles) == 0:
            return

        # Use actual elapsed time for smooth frame-rate independent movement
        now = pygame.time.get_ticks()
        if not hasattr(self, '_last_pet_proj_tick'):
            self._last_pet_proj_tick = now
        dt_ms = min(100, max(1, now - self._last_pet_proj_tick))
        self._last_pet_proj_tick = now
        speed = combat_constants.ATTACK_SPEED * 30 * dt_ms / 1000

        for i, main_data in enumerate(self.battle_player.team1_projectiles):
            if len(main_data) == 0:
                continue

            # Move projectiles
            done = True
            for sprite_data in main_data:
                sprite, pos, target, attack_entry = sprite_data
                new_pos = self.move_towards(pos, target, speed)
                sprite_data[1][0], sprite_data[1][1] = new_pos
                if math.hypot(new_pos[0] - target[0], new_pos[1] - target[1]) > 2:
                    done = False

            # When all projectiles are done for this attack
            if done:
                defender_idx = attack_entry.defender
                hit = attack_entry.hit
                damage = attack_entry.damage

                # Play hit or miss sound and animation
                self.battle_player.shot_wait[i] = True
                if hit:
                    enemy = self.battle_player.team2[defender_idx]
                    enemy_y = self.get_y(defender_idx, len(self.battle_player.team2))
                    enemy_x = self.get_team2_x(defender_idx) + (runtime_globals.PET_WIDTH * constants.BOSS_MULTIPLIER if self.boss else runtime_globals.PET_WIDTH) // 2
                    self.hit_animations.append([0, [enemy_x, enemy_y + (16 * runtime_globals.UI_SCALE)]])
                    runtime_globals.game_sound.play("attack_hit")

                    # Apply damage
                    self.battle_player.team2_hp[defender_idx] = max(0, self.battle_player.team2_hp[defender_idx] - damage)
                    self.battle_player.team2_total_hp = sum(self.battle_player.team2_hp)
                    # Trigger HPBar animation for enemy (left side) and update current HP
                    self.hp_bar.add_damage('left', damage)
                    self.hp_bar.set_current_hp(left_current=self.battle_player.team2_total_hp)

                    self.battle_player.team2_bar_counters[defender_idx] = BAR_COUNTER
                else:
                    runtime_globals.game_sound.play("attack_fail")
                    if defender_idx >= 0 and defender_idx < len(self.battle_player.team2):
                        enemy = self.battle_player.team2[defender_idx]
                        enemy_y = self.get_y(defender_idx, len(self.battle_player.team2))
                        enemy_x = self.get_team2_x(defender_idx)
                        runtime_globals.game_message.add("MISS", (enemy_x + (16 * runtime_globals.UI_SCALE), enemy_y - (10 * runtime_globals.UI_SCALE)), (255, 0, 0))

                self.battle_player.team1_projectiles[i] = []

        # Check if all pets/enemies are in result phase
        if all(phase == "result" for phase in self.battle_player.phase):
            self.phase = "result" if not self.boss else "clear"
            self.frame_counter = 0

    def update_battle_enemy_projectiles(self):
        if len(self.battle_player.team2_projectiles) == 0:
            return

        # Use actual elapsed time for smooth frame-rate independent movement
        now = pygame.time.get_ticks()
        if not hasattr(self, '_last_enemy_proj_tick'):
            self._last_enemy_proj_tick = now
        dt_ms = min(100, max(1, now - self._last_enemy_proj_tick))
        self._last_enemy_proj_tick = now
        speed = combat_constants.ATTACK_SPEED * 30 * dt_ms / 1000

        for i, main_data in enumerate(self.battle_player.team2_projectiles):
            if len(main_data) == 0:
                continue

            # Move projectiles
            done = True
            for sprite_data in main_data:
                sprite, pos, target, attack_entry = sprite_data
                new_pos = self.move_towards(pos, target, speed)
                sprite_data[1][0], sprite_data[1][1] = new_pos
                if math.hypot(new_pos[0] - target[0], new_pos[1] - target[1]) > 2:
                    done = False

            # When all projectiles are done for this attack
            if done:
                index = i
                if self.boss:
                    index = 0
                defender_idx = attack_entry.defender
                hit = attack_entry.hit
                damage = attack_entry.damage
                self.battle_player.shot_wait[index] = True
                if hit:
                    pet_y = self.get_y(defender_idx, len(self.battle_player.team1))
                    pet_x = self.get_team1_x(defender_idx) + (runtime_globals.PET_WIDTH // 2)
                    self.hit_animations.append([0, [pet_x, pet_y + (24 * runtime_globals.UI_SCALE)]])
                    runtime_globals.game_sound.play("attack_hit")
                    self.battle_player.team1_hp[defender_idx] = max(0, self.battle_player.team1_hp[defender_idx] - damage)
                    self.battle_player.team1_total_hp = sum(self.battle_player.team1_hp)
                    # Trigger HPBar animation for player (right side) and update current HP
                    self.hp_bar.add_damage('right', damage)
                    self.hp_bar.set_current_hp(right_current=self.battle_player.team1_total_hp)

                    self.battle_player.team1_bar_counters[defender_idx] = BAR_COUNTER
                else:
                    runtime_globals.game_sound.play("attack_fail")
                    if defender_idx >= 0 and defender_idx < len(self.battle_player.team1):
                        pet_y = self.get_y(defender_idx, len(self.battle_player.team1))
                        pet_x = self.get_team1_x(defender_idx)
                        runtime_globals.game_message.add("MISS", (pet_x + (16 * runtime_globals.UI_SCALE), pet_y - (10 * runtime_globals.UI_SCALE)), (255, 0, 0))
                
                self.battle_player.team2_projectiles[i] = []

        # Check if all pets/enemies are in result phase
        if all(phase == "result" for phase in self.battle_player.phase):
            self.phase = "result" if not self.boss else "clear"
            self.frame_counter = 0

    def update_clear(self):
        """
        Update logic for the update_clear phase,
        """

        if not self.boss or self.frame_counter > int(30 * ( constants.FRAME_RATE / 30)):
            self.frame_counter = 0
            self.phase = "result"

    def _has_result_rewards(self):
        """Check if there are any meaningful rewards to display on the result screen."""
        if self.pvp_mode:
            return True  # Always show PvP results
        if self.battle_player.xp > 0 or self.battle_player.bonus > 0:
            return True
        if getattr(self, 'prize_item', None) is not None:
            return True
        if any(self.battle_player.level_up):
            return True
        # Check if any pet's module uses gcells and would gain/lose points
        for pet in self.battle_player.team1:
            pet_module = get_module(getattr(pet, 'module', self.module.name))
            if getattr(pet_module, 'use_gcells', False):
                if self.victory_status == "Victory":
                    if getattr(pet_module, 'gcell_battle_win', 0) != 0:
                        return True
                else:
                    if getattr(pet_module, 'gcell_battle_loose', 0) != 0:
                        return True
        return False

    def update_result(self):
        """
        Update logic for the result phase, handles victory or defeat actions.
        """
        # Skip the result screen entirely if there are no rewards to show
        if self.result_timer == 0 and not self._has_result_rewards():
            runtime_globals.game_console.log("[BattleEncounter] No rewards to display, skipping result screen")
            # Still need to run the post-result logic (progression, unlocks, etc.)
            # Jump the timer past the wait threshold to fall through immediately
            self.result_timer = int(120 * (constants.FRAME_RATE / 30))

        # Result timer, frame-rate independent
        self.result_timer += 1

        if self.result_timer < int(120 * ( constants.FRAME_RATE / 30)):
            # pisca aviso clear
            return

        # For PvP battles, update per-pet PvP counters, run unlock checks, then
        # return to game after showing results. We maintain per-pet counters so
        # unlocks that rely on PvP wins/participation can reference them.
        if self.pvp_mode:
            # Play appropriate sound
            runtime_globals.game_sound.play("happy" if self.victory_status == "Victory" else "fail")

            # Update each local pet's PvP counters. Pets on team1 are the local
            # owner's pets in PvP mode.
            for i, pet in enumerate(self.battle_player.team1):
                try:
                    pet.pvp_battles += 1
                    # Determine if this pet won its pairing
                    if hasattr(self.battle_player, 'winners') and i < len(self.battle_player.winners):
                        winner = self.battle_player.winners[i]
                        local_won = (winner == 'team1') or (self.victory_status == 'Victory')
                    else:
                        # Fallback: use global victory_status when per-pair winners
                        # are not available
                        local_won = (self.victory_status == 'Victory')

                    if local_won:
                        pet.pvp_wins += 1

                    # Persist these counters to global save state via runtime globals
                    # so they'll be picked up on next autosave
                    runtime_globals.game_console.log(f"[PvP] Pet {getattr(pet,'name',i)} pvp_battles={pet.pvp_battles} pvp_wins={pet.pvp_wins}")
                except Exception as e:
                    runtime_globals.game_console.log(f"[PvP] Error updating pet PvP counters: {e}")

            # Unlock logic for PvP: scan module unlock entries of type 'pvp' and
            # compare their "amount" to the pet owner's pvp_wins count.
            try:
                module_unlocks = getattr(self.module, 'unlocks', []) or []
                for unlock in module_unlocks:
                    if unlock.get('type') == 'pvp':
                        req = unlock.get('amount', None)
                        name = unlock.get('name')
                        if req is None or not name:
                            continue
                        # If any local pet has pvp_wins >= req, unlock for module
                        for pet in self.battle_player.team1:
                            if getattr(pet, 'pvp_wins', 0) >= int(req):
                                unlock_item(self.module.name, 'pvp', name)
                                break
            except Exception as e:
                runtime_globals.game_console.log(f"[PvP] Error processing PvP unlocks: {e}")

            # Return to main scene after PvP
            self.return_to_main_scene()
            return
        
        # Random encounters skip progression and return to game immediately
        if self.is_random_encounter:
            runtime_globals.game_sound.play("happy" if self.victory_status == "Victory" else "fail")
            self.return_to_main_scene()
            return

        pets = get_battle_targets()
        if self.victory_status == "Victory":
            if not self.boss:
                if len(pets) == 0:
                    #No more pets capable of continuing the battle
                    runtime_globals.game_sound.play("fail")
                    self.return_to_main_scene()
                    return
                else:
                    self.round += 1
                    # Check if the new round has enemies; if not, the area is cleared
                    next_versions = self.module.get_enemy_versions(self.area, self.round)
                    if not next_versions:
                        # Area cleared — advance to next area
                        self.area += 1
                        self.round = 1
                        if self.module.area_exists(self.area):
                            game_globals.battle_round[self.module.name] = self.round
                            game_globals.battle_area[self.module.name] = max(self.area, game_globals.battle_area.get(self.module.name, 0))
                        # Fall through to total victories, unlocks, and return_to_main_scene
                    else:
                        if self.round > game_globals.battle_round[self.module.name]:
                            game_globals.battle_round[self.module.name] = self.round
                        self.victory_status = None
                        if self.module.battle_sequential_rounds:
                            self.set_initial_state(round=self.round, area=self.area)
                            return
            else:
                # --- Unlock adventure items of the area just won ---
                unlocks = getattr(self.module, "unlocks", None)
                if isinstance(unlocks, list):
                    for unlock in unlocks:
                        unlocked = False
                        
                        # Check for area-based unlocks
                        if unlock.get("type") == "adventure" and unlock.get("area") == self.area:
                            unlocked = True
                        
                        # Check for boss-specific unlock keys
                        elif unlock.get("type") == "adventure" and "name" in unlock:
                            unlock_name = unlock["name"]
                            # Check if any defeated enemy has this unlock key
                            for enemy in self.battle_player.team2:
                                if hasattr(enemy, 'unlock') and enemy.unlock == unlock_name:
                                    unlocked = True
                                    runtime_globals.game_console.log(f"[Adventure] Boss {enemy.name} dropped unlock key: {unlock_name}")
                                    break
                        
                        if unlocked:
                            unlock_item(self.module.name, "adventure", unlock["name"])
                            runtime_globals.game_console.log(f"[Adventure] Unlocked: {unlock['name']}")

                self.area += 1
                self.round = 1

                if self.module.area_exists(self.area):
                    game_globals.battle_round[self.module.name] = self.round
                    game_globals.battle_area[self.module.name] = max(self.area, game_globals.battle_area[self.module.name])
            
            # Increment total victories for this module
            if self.module.name not in game_globals.total_victories:
                game_globals.total_victories[self.module.name] = 0
            game_globals.total_victories[self.module.name] += 1
            runtime_globals.game_console.log(f"[Battle] Total victories for {self.module.name}: {game_globals.total_victories[self.module.name]}")
            
            # Check for battle unlocks
            try:
                module_unlocks = getattr(self.module, 'unlocks', []) or []
                for unlock in module_unlocks:
                    if unlock.get('type') == 'battle':
                        req = unlock.get('amount', None)
                        name = unlock.get('name')
                        if req is None or not name:
                            continue
                        # Check if total victories >= required amount
                        current_victories = game_globals.total_victories.get(self.module.name, 0)
                        if current_victories >= int(req):
                            unlock_item(self.module.name, 'battle', name)
                            runtime_globals.game_console.log(f"[Battle] Unlocked {name} after {current_victories} victories")
            except Exception as e:
                runtime_globals.game_console.log(f"[Battle] Error processing battle unlocks: {e}")
        else:
            runtime_globals.game_sound.play("fail")
            # perdeu
            game_globals.battle_round[self.module.name] = 1

        self.return_to_main_scene()

    def load_next_round(self):
        """
        Prepares the next round by resetting health and loading new enemies.
        """
        self.phase = "level"
        self.result_timer  = 0
        self.press_counter = 0
        self.final_color = 3
        self.correct_color = 0
        self.super_hits = 0
        self.frame_counter = 0
        self.enemies = []
        self.enemy_positions = []
        self.load_enemies()

    def draw(self, surface: pygame.Surface):
        """
        Main draw loop for the battle encounter, calls phase-specific draws.
        """
        # Hide HPBar during charge phase for cleaner minigame presentation
        if self.phase not in ["charge", "result"]:
            self.draw_health_bars(surface)
        #surface.blit(self.backgroundIm, (0, 0))

        # Draw by phase
        if self.phase == "level":
            self.draw_level(surface)
        elif self.phase == "entry":
            self.draw_entry(surface)
        elif self.phase == "intimidate":
            self.draw_intimidate(surface)
        elif self.phase == "alert":
            self.draw_alert(surface)
        elif self.phase == "charge":
            self.draw_charge(surface)
        elif self.phase == "battle":
            self.draw_battle(surface)
        elif self.phase == "clear":
            self.draw_clear(surface)
        elif self.phase == "result":
            self.draw_result(surface)

        # Draw debug battle logs if DEBUG_MODE and DEBUG_BATTLE_INFO flags are enabled
        if constants.DEBUG_MODE and constants.DEBUG_BATTLE_INFO and self.phase in ["battle"]:
            self.draw_debug_battle_logs(surface)

    def draw_level(self, surface):
        """
        Draws the level information on the screen using AnimatedSprite component.
        """
        # Check if we need to start the battle level animation
        if not self.animated_sprite.is_animation_playing():
            self.animated_sprite.play_battle_level(duration_seconds=1.0)
        
        # Draw the animated sprite (just the Combat_Level sprite)
        self.animated_sprite.draw(surface)
        
        # Draw area/round text using scaled font
        from components.ui import ui_constants
        adventure_style = getattr(self.module, 'adventure_style', 'Area Selection')
        if adventure_style == "Next and Reset":
            area_text = f"AREA {self.area}"
        elif adventure_style == "Random":
            # Show first enemy name for Random style
            if self.enemies and self.enemies[0] and hasattr(self.enemies[0], 'name'):
                area_text = self.enemies[0].name
            else:
                area_text = f"AREA {self.area}-{self.round}"
        else:
            area_text = f"AREA {self.area}-{self.round}"
        
        # Position: 6 pixels from left in UI space, accounting for UI offset
        text_x = self.ui_manager.ui_offset_x + int(6 * runtime_globals.UI_SCALE)
        
        # Use title font with scaled size (32 * UI_SCALE), left-aligned
        font_size = int(32 * runtime_globals.UI_SCALE)
        font = get_font(font_size)
        text_surface = font.render(area_text, True, ui_constants.GREEN).convert_alpha()
        
        # Center vertically based on actual text height, accounting for UI offset
        text_y = self.ui_manager.ui_offset_y + ((self.ui_manager.ui_height - text_surface.get_height()) // 2)
        surface.blit(text_surface, (text_x, text_y))

    def draw_entry(self, surface):
        """
        Draws the entry phase, showing enemies and pets in their starting positions.
        """
        self.draw_enemies(surface)
        self.draw_pets(surface)
        runtime_globals.game_message.draw(surface)
        self.draw_hit_animations(surface)

    def draw_intimidate(self, surface):
        """
        Draws the intimidate phase, showing warning or battle sprites using AnimatedSprite component.
        """
        if self.frame_counter >= combat_constants.IDLE_ANIM_DURATION // 2:
            # Draw the animated sprite (animation started in update_entry when entering phase)
            self.animated_sprite.draw(surface)
        else:
            self.draw_enemies(surface)
            self.draw_pets(surface)
            runtime_globals.game_message.draw(surface)
            self.draw_hit_animations(surface)

    def draw_alert(self, surface):
        """
        Draws the alert phase, showing readiness sprites using AnimatedSprite component.
        """
        if self.module.ruleset == "penc":
            self.animated_sprite.stop()
            # PenC ruleset: Count match minigame shows in both alert and charge phases
            self.count_match.set_phase("ready")
            self.count_match.draw(surface)
            # Don't draw the animated sprite for count match - use only minigame version
        else:
            # For other rulesets, use animated sprite ready animation
            # Force stop any previous animation and setup alert animation
            self.animated_sprite.stop()
            
            if not self.animated_sprite.is_animation_playing():
                duration = 1.5  # 1.5 second alert animation
                # Use ready animation for other rulesets
                self.animated_sprite.play_ready(duration)
            
            # Draw the animated sprite
            self.animated_sprite.draw(surface)

    def draw_charge(self, surface):
        """
        Draws the charge phase, showing strength bar, minigame, or Xai roll.
        """
        # Draw enemies and pets as background for most rulesets
        if self.module.ruleset != "vb":
            self.draw_enemies(surface)
            self.draw_pets(surface)
        
        # Draw minigame UI on top
        if self.module.ruleset == "dmc":
            # DMC ruleset: Dummy charge minigame
            self.dummy_charge.draw(surface)
        elif self.module.ruleset == "penc":
            # PenC ruleset: Count match minigame
            self.count_match.draw(surface)
        elif self.module.ruleset == "vb":
            # VB ruleset: Shake punch minigame (full screen, draws its own pets)
            self.shake_punch.draw(surface)
        elif self.module.ruleset == "dmx":
            # DMX ruleset: XAI roll and bar
            if self.xai_phase == 1:
                self.xai_roll.draw(surface)
            elif self.xai_phase >= 2:
                self.xai_bar.draw(surface)

    def draw_battle(self, surface):
        """
        Draws the battle phase, showing pets and enemies in combat.
        """
        self.draw_enemies(surface)
        self.draw_pets(surface)
        runtime_globals.game_message.draw(surface)
        self.draw_hit_animations(surface)
        self.draw_projectiles(surface)
        self.draw_enemy_projectiles(surface)
        self.draw_health_bars_for_battlers(surface)

    def draw_clear(self, surface):
        """
        Draws the clear of the battle, showing clear sprites using AnimatedSprite component.
        This phase is only reached for boss battles - show win animation here.
        """
        if self.boss:
            # Use AnimatedSprite component for win animation during clear phase
            if not self.animated_sprite.is_animation_playing():
                duration = 1.0  # 1 second win animation (will be followed by clear in result phase)
                self.animated_sprite.play_win(duration)
            
            # Draw the animated sprite
            self.animated_sprite.draw(surface)

    def draw_result(self, surface):
        """
        Upgraded result screen using new UI elements:
        - Title label (WIN/LOSE) at top in theme colors
        - Animated pet sprites (not UI components)
        - Per-pet reward labels below each pet based on module's visible_stats
        - Prize label at bottom using LabelValue
        All labels use global screen positions scaled to any screen size.
        """
        # Start result animation once at the beginning
        if not self.result_animation_started:
            self.animated_sprite.stop()
            if self.victory_status == "Victory" and self.boss:
                # For boss victory: play clear for 1 second (win was already shown in clear phase)
                duration = 1.0
                self.animated_sprite.play_clear(duration)
            elif self.victory_status == "Victory":
                # For normal victory: play win for 2 seconds
                duration = 2.0
                self.animated_sprite.play_win(duration)
            else:
                # For defeat: play lose for 2 seconds
                duration = 2.0
                self.animated_sprite.play_lose(duration)
            self.result_animation_started = True
        
        # Show result animation for the first 1-2 seconds
        if self.animated_sprite.is_playing:
            # Draw the animated sprite
            self.animated_sprite.draw(surface)
        else:
            # Build UI components once (labels for title, pet rewards, and prize)
            if self.result_surface_cache is None:
                # Use UI constants for colors (not theme colors)
                win_color = ui_constants.GREEN
                lose_color = ui_constants.RED
                white_color = (245, 245, 245)
                yellow_color = ui_constants.YELLOW
                
                # Calculate positions
                width_scale = runtime_globals.SCREEN_WIDTH / 240
                height_scale = runtime_globals.SCREEN_HEIGHT / 240
                
                # Title label at top center (using global positioning)
                title_text = "WIN" if self.victory_status == "Victory" else "LOSE"
                title_color = win_color if self.victory_status == "Victory" else lose_color
                title_y = int(20 * height_scale)
                
                # Create title label (will be centered after rendering)
                self.result_title_label = Label(0, title_y, title_text, is_title=True, color_override=title_color)
                self.result_title_label.manager = self.ui_manager
                
                # Determine pets to display
                if self.pvp_mode and hasattr(self, 'show_team2_in_result') and self.show_team2_in_result:
                    pets = [enemy for enemy in self.battle_player.team2 if hasattr(enemy, 'get_sprite')]
                else:
                    pets = self.battle_player.team1
                
                # Calculate pet layout with better spacing
                total = len(pets)
                # Use larger sprites and better horizontal distribution
                base_sprite_size = runtime_globals.PET_WIDTH  # Use full size instead of half
                sprite_width = int(base_sprite_size)
                sprite_height = int(base_sprite_size)
                
                # Calculate spacing to distribute evenly across width
                margin = int(20 * width_scale)  # Side margins
                gap_between_pets = int(16 * width_scale)  # Gap between pets
                
                # Calculate the actual width occupied by all pets
                if total > 1:
                    # Total width = all sprites + gaps between them
                    total_pets_width = (total * sprite_width) + ((total - 1) * gap_between_pets)
                    
                    # If pets don't fit, scale them down
                    available_width = runtime_globals.SCREEN_WIDTH - (2 * margin)
                    if total_pets_width > available_width:
                        # Recalculate sprite size to fit
                        total_pets_width = available_width
                        sprite_width = (available_width - ((total - 1) * gap_between_pets)) // total
                        sprite_height = sprite_width  # Keep square
                else:
                    # Single pet - just the sprite width
                    total_pets_width = sprite_width
                
                # Center the pet group horizontally
                offset_x = (runtime_globals.SCREEN_WIDTH - total_pets_width) // 2
                pets_y = int(50 * height_scale)
                
                # Create per-pet reward labels with doubled font size
                self.result_pet_labels = []
                for i, pet in enumerate(pets):
                    pet_center_x = offset_x + (i * (sprite_width + gap_between_pets)) + sprite_width // 2
                    label_y_start = pets_y + sprite_height + int(12 * height_scale)
                    
                    pet_labels = []
                    current_y = label_y_start
                    
                    # Get pet's module
                    pet_module_name = getattr(pet, 'module', self.module.name)
                    pet_module = get_module(pet_module_name)
                    
                    # Check if module uses G-Cells
                    if getattr(pet_module, 'use_gcells', False):
                        # Calculate G-Cell points gained (from finish_battle logic)
                        if self.victory_status == "Victory":
                            gcell_points = getattr(pet_module, 'gcell_battle_win', 0)
                        else:
                            gcell_points = getattr(pet_module, 'gcell_battle_loose', 0)
                        
                        if gcell_points != 0:
                            # Use title font for doubled size
                            gcell_label = Label(0, current_y, f"GC {gcell_points:+d}", is_title=False, color_override=win_color if gcell_points > 0 else white_color, shadow_mode="full", custom_size=int(16*runtime_globals.UI_SCALE))
                            gcell_label.manager = self.ui_manager
                            pet_labels.append((gcell_label, pet_center_x))
                            current_y += int(28 * height_scale)  # More spacing for larger font
                    
                    # Check if module has Level in visible_stats
                    visible_stats = getattr(pet_module, 'visible_stats', None)
                    if visible_stats and "Level" in visible_stats:
                        # Show level and level up indicator
                        level = getattr(pet, "level", 1)
                        level_up_indicator = ""
                        level_color = white_color
                        
                        if not self.pvp_mode and i < len(self.battle_player.level_up):
                            if self.battle_player.level_up[i]:
                                level_up_indicator = " +"
                                level_color = win_color
                        
                        # Use title font for doubled size
                        level_label = Label(0, current_y, f"Lv {level}{level_up_indicator}", is_title=False, color_override=level_color, shadow_mode="full", custom_size=int(16*runtime_globals.UI_SCALE))
                        level_label.manager = self.ui_manager
                        pet_labels.append((level_label, pet_center_x))
                        current_y += int(28 * height_scale)  # More spacing for larger font
                        
                        # Show experience gained
                        exp_gained = self.battle_player.xp if self.victory_status == "Victory" else 0
                        
                        # Check if at max level
                        if i < len(self.battle_player.team1):
                            max_level_check = self.battle_player.team1[i].level == constants.MAX_LEVEL.get(self.battle_player.team1[i].stage, 99)
                            level_up_check = self.battle_player.level_up[i] if i < len(self.battle_player.level_up) else False
                            
                            if not level_up_check and max_level_check:
                                exp_gained = 0
                        
                        # Use title font for doubled size
                        exp_label = Label(0, current_y, f"Exp +{exp_gained}", is_title=False, color_override=win_color if exp_gained > 0 else white_color, shadow_mode="full", custom_size=int(16*runtime_globals.UI_SCALE))
                        exp_label.manager = self.ui_manager
                        pet_labels.append((exp_label, pet_center_x))
                        current_y += int(28 * height_scale)  # More spacing for larger font
                    
                    self.result_pet_labels.append(pet_labels)
                
                # Create prize labels at bottom (using Label components for doubled font size)
                prize_y = runtime_globals.SCREEN_HEIGHT - int(35 * height_scale)
                prize_label_x = int(20 * width_scale)
                
                if self.victory_status == "Victory" and getattr(self, "prize_item", None):
                    prize_text = self.prize_item.name
                    prize_value_color = ui_constants.GREEN
                else:
                    prize_text = "None"
                    prize_value_color = white_color
                
                # Create separate labels for "Prize:" and the value with title font
                self.result_prize_label_text = Label(prize_label_x, prize_y, "Prize:", is_title=False, color_override=white_color, shadow_mode="full", custom_size=int(32*runtime_globals.UI_SCALE))
                self.result_prize_label_text.manager = self.ui_manager
                
                # Create the prize value label once and cache it
                prize_value_x = prize_label_x + int(8 * width_scale)  # Will be adjusted after rendering "Prize:" text
                self.result_prize_value_label = Label(prize_value_x, prize_y, prize_text, is_title=False, color_override=prize_value_color, shadow_mode="full", custom_size=int(32*runtime_globals.UI_SCALE))
                self.result_prize_value_label.manager = self.ui_manager
                
                # Pre-cache scaled pet sprites to avoid per-frame scaling
                self.result_pet_sprites_cache = {}
                for pet in pets:
                    self.result_pet_sprites_cache[pet] = {}
                    for frame_id in [PetFrame.IDLE1.value, PetFrame.HAPPY.value, PetFrame.LOSE.value]:
                        original_sprite = pet.get_sprite(frame_id)
                        scaled_sprite = pygame.transform.scale(original_sprite, (sprite_width, sprite_height))
                        self.result_pet_sprites_cache[pet][frame_id] = scaled_sprite
                
                # Store sprite dimensions for drawing
                self.result_sprite_width = sprite_width
                self.result_sprite_height = sprite_height
                self.result_offset_x = offset_x
                self.result_gap_between_pets = gap_between_pets
                self.result_pets_y = pets_y
                
                # Create a single cached surface for ALL static text (rendered once)
                # This avoids per-frame text rendering and shadow blitting which causes flickering
                self.result_static_text_surface = pygame.Surface((runtime_globals.SCREEN_WIDTH, runtime_globals.SCREEN_HEIGHT), pygame.SRCALPHA)
                self.result_static_text_surface.fill((0, 0, 0, 0))  # Transparent
                
                # Render title label (centered at top)
                title_surface = self.result_title_label.render()
                title_x = (runtime_globals.SCREEN_WIDTH - title_surface.get_width()) // 2
                self.result_static_text_surface.blit(title_surface, (title_x, self.result_title_label.rect.y))
                
                # Render prize labels at bottom
                prize_label_surface = self.result_prize_label_text.render()
                self.result_static_text_surface.blit(prize_label_surface, (self.result_prize_label_text.rect.x, self.result_prize_label_text.rect.y))
                
                # Render prize value to the right of label
                width_scale = runtime_globals.SCREEN_WIDTH / 240
                prize_value_x = self.result_prize_label_text.rect.x + prize_label_surface.get_width() + int(8 * width_scale)
                self.result_prize_value_label.rect.x = prize_value_x
                prize_value_surface = self.result_prize_value_label.render()
                self.result_static_text_surface.blit(prize_value_surface, (prize_value_x, self.result_prize_label_text.rect.y))
                
                # Render all per-pet labels to the static surface
                for i, pet_labels in enumerate(self.result_pet_labels):
                    pet_center_x = offset_x + (i * (sprite_width + gap_between_pets)) + sprite_width // 2
                    for label, label_center_x in pet_labels:
                        label_surface = label.render()
                        label_x = label_center_x - label_surface.get_width() // 2
                        self.result_static_text_surface.blit(label_surface, (label_x, label.rect.y))
                
                # Mark cache as built
                self.result_surface_cache = True
            
            # Draw the cached static text surface (single blit for all text)
            surface.blit(self.result_static_text_surface, (0, 0))
            
            # Draw animated pet sprites (not cached, drawn directly)
            if self.pvp_mode and hasattr(self, 'show_team2_in_result') and self.show_team2_in_result:
                pets = [enemy for enemy in self.battle_player.team2 if hasattr(enemy, 'get_sprite')]
                # Use team2 indices for frame counters and winners
                team1_count = len(self.battle_player.team1)
                pet_frame_counters = []
                pet_winners = []
                for i in range(len(pets)):
                    frame_counter_idx = team1_count + i
                    if frame_counter_idx < len(self.battle_player.frame_counters):
                        pet_frame_counters.append(self.battle_player.frame_counters[frame_counter_idx])
                    else:
                        pet_frame_counters.append(0)  # Default frame counter
                    
                    winner_idx = team1_count + i  
                    if winner_idx < len(self.battle_player.winners):
                        pet_winners.append(self.battle_player.winners[winner_idx])
                    else:
                        pet_winners.append("team1")  # Default winner
            else:
                pets = self.battle_player.team1
                pet_frame_counters = self.battle_player.frame_counters[:len(self.battle_player.team1)]
                pet_winners = self.battle_player.winners[:len(self.battle_player.team1)]
            
            # Draw each pet sprite and their labels (using cached layout values)
            for i, pet in enumerate(pets):
                pet_x = self.result_offset_x + (i * (self.result_sprite_width + self.result_gap_between_pets))
                pet_center_x = pet_x + self.result_sprite_width // 2
                
                # Draw pet sprite (animated) using cached scaled sprites
                if i < len(pet_frame_counters):
                    anim_toggle = (pet_frame_counters[i] + i * 5) // (15 * constants.FRAME_RATE / 30) % 2
                else:
                    anim_toggle = 0
                    
                if (i < len(pet_winners) and pet_winners[i] == "team2") or self.victory_status == "Defeat":
                    frame_id = PetFrame.LOSE.value
                else:
                    frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.HAPPY.value
                
                # Use cached scaled sprite
                if pet in self.result_pet_sprites_cache and frame_id in self.result_pet_sprites_cache[pet]:
                    sprite = self.result_pet_sprites_cache[pet][frame_id]
                else:
                    # Fallback if cache miss (shouldn't happen)
                    sprite = pet.get_sprite(frame_id)
                    sprite = pygame.transform.scale(sprite, (self.result_sprite_width, self.result_sprite_height))
                
                blit_with_cache(surface, sprite, (pet_x, self.result_pets_y))

    def draw_hit_animations(self, surface):
        """
        Draws the hit animations at the impact points of attacks.
        """
        for frame_index, (x, y) in self.hit_animations:
            if 0 <= frame_index < len(self.hit_animation_frames):
                sprite = self.hit_animation_frames[frame_index]
                blit_with_cache(surface, sprite, (x - sprite.get_width() // 2, y - 32))

    def draw_enemies(self, surface: pygame.Surface):
        """
        Draws the enemy sprites on the screen, with animations based on the battle phase.
        """
        total = len(self.battle_player.team2)
        anim_frames = 10 * ( constants.FRAME_RATE / 30)

        for i, enemy in enumerate(self.battle_player.team2):
            y = self.get_y(i, total)
            x = self.get_team2_x(i) - self.enemy_entry_counter
            anim_toggle = (self.battle_player.frame_counters[i] + i * 5) // (15 * constants.FRAME_RATE / 30) % 2

            attack_entry = None
            if self.phase in ["battle"]:
                # Check the global battle log for an attack entry
                turn = self.battle_player.turns[i]
                if turn <= self.turn_limit and self.global_battle_log and len(self.global_battle_log.battle_log) >= turn:
                    turn_log = self.global_battle_log.battle_log[turn - 1]
                    attack_entry = next(
                        (a for a in turn_log.attacks if a.device == "device2" and a.attacker == i),
                        None
                    )

            if self.phase in ["intimidate", "entry"]:
                frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.ANGRY.value
            elif self.phase in ["alert", "charge"]:
                frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.IDLE2.value
            elif self.battle_player.team2_hp[i] <= 0:
                frame_id = PetFrame.LOSE.value
            elif attack_entry and self.battle_player.phase[i] == "enemy_attack":
                frame_id = PetFrame.ATK1.value
            elif attack_entry and self.battle_player.phase[i] == "enemy_charge":
                if self.battle_player.cooldowns[i] < anim_frames:
                    frame_id = PetFrame.ATK2.value
                else:
                    frame_id = PetFrame.ATK1.value
            elif self.battle_player.phase[i] == "result":
                if self.battle_player.winners[i] == "team1":
                    frame_id = PetFrame.LOSE.value
                else:
                    frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.HAPPY.value
            else:
                frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.IDLE2.value

            sprite = enemy.get_sprite(frame_id)

            if attack_entry and self.battle_player.phase[i] == "enemy_charge" and self.battle_player.team2_hp[i] > 0:
                y -= int(self.battle_player.attack_jump[i] * runtime_globals.UI_SCALE)
                x -= int(self.battle_player.attack_forward[i] * runtime_globals.UI_SCALE)

            if sprite:
                sprite = pygame.transform.flip(sprite, True, False)
                blit_with_cache(surface, sprite, (x + (2 * runtime_globals.UI_SCALE), y))

    def draw_pets(self, surface: pygame.Surface):
        """
        Draws the player pets on the screen, with animations based on the battle phase.
        In the result phase, pets are drawn horizontally and centered vertically.
        """
        total = len(self.battle_player.team1)
        anim_frames = 10 * ( constants.FRAME_RATE / 30)

        if self.phase == "result":
            # Horizontal layout
            spacing = min((runtime_globals.SCREEN_WIDTH - int(30 * runtime_globals.UI_SCALE)) // total, int(runtime_globals.PET_WIDTH * runtime_globals.UI_SCALE) + int(16 * runtime_globals.UI_SCALE))
            total_width = spacing * total
            offset_x = (runtime_globals.SCREEN_WIDTH - total_width) // 2
            y = (runtime_globals.SCREEN_HEIGHT - runtime_globals.PET_HEIGHT) // 2
            for i, pet in enumerate(self.battle_player.team1):
                x = self.get_team1_x(i)
                anim_toggle = (self.battle_player.frame_counters[i] + i * 5) // (15 * constants.FRAME_RATE / 30) % 2
                if self.victory_status == "Defeat":
                    frame_id = PetFrame.LOSE.value
                else:
                    frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.HAPPY.value
                sprite = pet.get_sprite(frame_id)
                sprite = pygame.transform.scale(sprite, (runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT))
                x = offset_x + i * spacing
                blit_with_cache(surface, sprite, (x, y))
        else:
            # Original vertical layout
            for i, pet in enumerate(self.battle_player.team1):
                anim_toggle = (self.battle_player.frame_counters[i] + i * 5) // (15 * constants.FRAME_RATE / 30) % 2
                x = self.get_team1_x(i)
                attack_entry = None
                if self.phase in ["battle"]:
                    # Check the global battle log for an attack entry
                    turn = self.battle_player.turns[i]
                    if turn <= self.turn_limit and self.global_battle_log and len(self.global_battle_log.battle_log) >= turn:
                        turn_log = self.global_battle_log.battle_log[turn - 1]
                        attack_entry = next(
                            (a for a in turn_log.attacks if a.device == "device1" and a.attacker == i),
                            None
                        )

                if self.phase in ["alert", "charge"]:
                    frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.ANGRY.value
                elif self.phase in ["intimidate", "entry"]:
                    frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.IDLE2.value
                elif self.battle_player.team1_hp[i] <= 0:
                    frame_id = PetFrame.LOSE.value
                elif attack_entry and self.battle_player.phase[i] == "pet_attack":
                    frame_id = PetFrame.ATK1.value
                elif attack_entry and self.battle_player.phase[i] == "pet_charge":
                    if self.battle_player.cooldowns[i] < anim_frames:
                        frame_id = PetFrame.ATK2.value
                    else:
                        frame_id = PetFrame.ATK1.value
                elif self.battle_player.phase[i] == "result":
                    if self.battle_player.winners[i] == "team2":
                        frame_id = PetFrame.LOSE.value
                    else:
                        frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.HAPPY.value
                else:
                    frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.IDLE2.value

                sprite = pet.get_sprite(frame_id)
                sprite = pygame.transform.scale(sprite, (runtime_globals.PET_WIDTH, runtime_globals.PET_HEIGHT))
                y = self.get_y(i, total)
                if attack_entry and self.battle_player.phase[i] == "pet_charge" and self.battle_player.team1_hp[i] > 0:
                    y -= int(self.battle_player.attack_jump[i] * runtime_globals.UI_SCALE)
                    x += int(self.battle_player.attack_forward[i] * runtime_globals.UI_SCALE)
                blit_with_cache(surface, sprite, (x, y))

    def draw_projectiles(self, surface):
        """
        Draws the projectiles fired by the player's pets during their attack.
        """
        for data in self.battle_player.team1_projectiles:
            for sprite, pos, target, dt in data:
                blit_with_cache(surface, sprite, (pos[0], pos[1])) 

    def draw_enemy_projectiles(self, surface):
        """
        Draws the projectiles fired by the enemies during their attack.
        """
        for data in self.battle_player.team2_projectiles:
            for sprite, pos, target, dt in data:
                blit_with_cache(surface, sprite, (pos[0], pos[1]))

    def draw_strength_bar(self, surface):
        """
        Draws the strength training bar for the DMC ruleset.
        """
        bar_x = (runtime_globals.SCREEN_WIDTH // 2) - (self.bar_back.get_width() // 2)
        bar_bottom_y = runtime_globals.SCREEN_HEIGHT - int(2 * runtime_globals.UI_SCALE)

        if self.strength == 14:
            surface.blit(self.training_max, (bar_x - int(18 * runtime_globals.UI_SCALE), bar_bottom_y - int(209 * runtime_globals.UI_SCALE)))

        blit_with_cache(surface, self.bar_back, (bar_x - int(3 * runtime_globals.UI_SCALE), bar_bottom_y - int(169 * runtime_globals.UI_SCALE)))

        for i in range(self.strength):
            y = bar_bottom_y - (i + 1) * self.bar_piece.get_height()
            surface.blit(self.bar_piece, (bar_x, y))

    def draw_health_bars(self, surface):
        """
        Draws the health bars for the player and enemy, showing current and max health.
        """
        self.hp_bar.draw(surface)

    def draw_health_bars_for_battlers(self, surface):
        """
        Draws individual health bars under each pet and enemy using the new team structure.
        """
        bar_height = int(8 * runtime_globals.UI_SCALE)
        bar_offset_y = runtime_globals.PET_HEIGHT - int(6 * runtime_globals.UI_SCALE)
        green = (0, 255, 108)
        red = (181, 41, 41)
        x_color = (255, 0, 0)
        x_thickness = max(2, int(2 * runtime_globals.UI_SCALE))

        # Draw pet health bars
        total_pets = len(self.battle_player.team1)
        for i, pet in enumerate(self.battle_player.team1):
            pet_x = self.get_team1_x(i)
            pet_y = self.get_y(i, total_pets) + bar_offset_y
            current_hp = self.battle_player.team1_hp[i]
            max_hp = self.battle_player.team1_max_hp[i]
            if current_hp > 0:
                if self.battle_player.team1_bar_counters[i] > 0:
                    pet_hp_ratio = current_hp / max_hp if max_hp else 0
                    pet_bar_width = int(runtime_globals.PET_WIDTH * pet_hp_ratio)
                    pygame.draw.rect(surface, red, (pet_x, pet_y, runtime_globals.PET_WIDTH, bar_height))
                    pygame.draw.rect(surface, green, (pet_x, pet_y, pet_bar_width, bar_height))
            else:
                pet_y = self.get_y(i, total_pets)
                if self._ko_sprite:
                    ko_x = pet_x + (runtime_globals.PET_WIDTH - self._ko_sprite.get_width()) // 2
                    ko_y = pet_y + (runtime_globals.PET_HEIGHT - self._ko_sprite.get_height()) // 2
                    surface.blit(self._ko_sprite, (ko_x, ko_y))
                else:
                    start1 = (pet_x, pet_y)
                    end1 = (pet_x + runtime_globals.PET_WIDTH, pet_y + runtime_globals.PET_HEIGHT)
                    start2 = (pet_x + runtime_globals.PET_WIDTH, pet_y)
                    end2 = (pet_x, pet_y + runtime_globals.PET_HEIGHT)
                    pygame.draw.line(surface, x_color, start1, end1, x_thickness)
                    pygame.draw.line(surface, x_color, start2, end2, x_thickness)

        # Draw enemy health bars
        total_enemies = len(self.battle_player.team2)
        if self.boss:
            bar_offset_y = int(runtime_globals.PET_HEIGHT * constants.BOSS_MULTIPLIER) - int(6 * runtime_globals.UI_SCALE)
        for i, enemy in enumerate(self.battle_player.team2):
            enemy_x = self.get_team2_x(i)
            enemy_y = self.get_y(i, total_enemies) + bar_offset_y
            current_hp = self.battle_player.team2_hp[i]
            max_hp = self.battle_player.team2_max_hp[i]
            width = runtime_globals.PET_WIDTH * constants.BOSS_MULTIPLIER if self.boss else runtime_globals.PET_WIDTH
            heigh = runtime_globals.PET_HEIGHT * constants.BOSS_MULTIPLIER if self.boss else runtime_globals.PET_HEIGHT
            if current_hp > 0:
                if self.battle_player.team2_bar_counters[i] > 0:
                    enemy_hp_ratio = current_hp / max_hp if max_hp else 0
                    enemy_bar_width = int(width * enemy_hp_ratio)
                    pygame.draw.rect(surface, red, (enemy_x, enemy_y, width, bar_height))
                    pygame.draw.rect(surface, green, (enemy_x, enemy_y, enemy_bar_width, bar_height))
            else:
                enemy_y = self.get_y(i, total_enemies)
                ko = self._ko_sprite_boss if self.boss else self._ko_sprite
                if ko:
                    ko_x = enemy_x + (width - ko.get_width()) // 2
                    ko_y = enemy_y + (heigh - ko.get_height()) // 2
                    surface.blit(ko, (ko_x, ko_y))
                else:
                    start1 = (enemy_x, enemy_y)
                    end1 = (enemy_x + width, enemy_y + heigh)
                    start2 = (enemy_x + width, enemy_y)
                    end2 = (enemy_x, enemy_y + heigh)
                    pygame.draw.line(surface, x_color, start1, end1, x_thickness)
                    pygame.draw.line(surface, x_color, start2, end2, x_thickness)

    def get_y(self, index, total):
        """
        Calculates the vertical position for drawing based on index and total number of sprites.
        Centers sprites dynamically and spreads them evenly, accounting for sprite height.
        """
        margin_top = int(40 * runtime_globals.UI_SCALE)
        margin_bottom = int(10 * runtime_globals.UI_SCALE)
        available_height = runtime_globals.SCREEN_HEIGHT - margin_top - margin_bottom

        sprite_height = runtime_globals.PET_HEIGHT

        if total == 1:
            # Center single sprite vertically
            return (runtime_globals.SCREEN_HEIGHT - sprite_height) // 2
        else:
            # Spread sprites evenly, center each sprite in its slot
            slot_height = available_height / total
            return int(margin_top + slot_height * index + (slot_height - sprite_height) / 2)

    def get_team1_x(self, index):
        """
        Returns the x position for the player's team based on index.
        """
        return runtime_globals.SCREEN_WIDTH - runtime_globals.PET_WIDTH - (4 * runtime_globals.UI_SCALE)
    
    def get_team2_x(self, index):
        """
        Returns the x position for the enemy team based on index.
        If it's a boss, it returns the enemy's x position.
        """
        return (3 * runtime_globals.UI_SCALE)
    #========================
    # Region: Event Handling
    #========================

    def handle_event(self, event):
        """
        Handles input events for the battle encounter, phase and battle_minigame specific.
        """
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        minigame = getattr(self.module, 'battle_minigame', 'Dummy Bar')
        
        # Handle string actions
        if event_type == "B":
            if self.phase == "battle":
                runtime_globals.game_sound.play("cancel")
                self.phase = "result"
                self.frame_counter = 0
            else:
                runtime_globals.game_sound.play("cancel")
                change_scene("game")
        elif self.phase == "charge":
            # Handle charge phase input based on minigame type
            if minigame == "Dummy Bar":
                if event_type in ("A", "LCLICK"):
                    if self.dummy_charge and self.dummy_charge.handle_event(event):
                        self.strength = self.dummy_charge.strength
            elif minigame == "Count Match (Color)":
                if event_type in ("Y", "SHAKE"):
                    if self.count_match and self.count_match.handle_event(event):
                        self.press_counter = self.count_match.get_press_counter()
                        self.rotation_index = self.count_match.get_rotation_index()
            elif minigame == "Count Match":
                if event_type in ("Y", "SHAKE"):
                    if self.count_match_classic and self.count_match_classic.handle_event(event):
                        self.strength = self.count_match_classic.strength
            elif minigame == "Count Match (Z)":
                if event_type in ("Y", "SHAKE"):
                    if self.count_match_z and self.count_match_z.handle_event(event):
                        self.press_counter = self.count_match_z.get_press_counter()
            elif minigame in ["Punch", "Mogera"]:
                if event_type in ("Y", "SHAKE"):
                    if self.shake_punch and self.shake_punch.handle_event(event):
                        self.strength = self.shake_punch.get_strength()
            elif minigame in ["Xai Roll+Bar", "Xai Bar"]:
                if self.xai_phase == 1 and event_type in ["A", "LCLICK"] and self.xai_roll:
                    # --- Seven Switch: force XAI roll to 7 if status_boost is active ---
                    xai_effect = self.get_battle_effect("xai_roll")
                    if xai_effect and xai_effect.get("amount", 0) == 7:
                        self.xai_roll.stop()
                        self.xai_roll.stop_target_frame = 6
                        self.xai_number = 7
                    else:
                        if not self.xai_roll.rolling:
                            self.xai_roll.roll()
                        elif not self.xai_roll.stopping:
                            self.xai_roll.stop()
                            self.xai_number = self.xai_roll.get_result()
                elif self.xai_phase == 2 and event_type in ["A", "LCLICK"] and self.xai_bar:
                    self.xai_bar.stop()
                    self.strength = self.xai_bar.get_result() or 1
                    self.xai_phase = 3
                    self.bar_timer = pygame.time.get_ticks()

    #========================
    # Region: Utility Methods
    #========================

    def return_to_main_scene(self):
        """
        Ends the battle and returns to the main game scene.
        """

        runtime_globals.game_console.log(f"[Scene_Battle] exiting to main game")
        distribute_pets_evenly()
        change_scene("game")

    def calculate_combat_for_pairs(self):
        self.simulate_global_combat()

        self.process_battle_results()

    def get_minigame_strength(self):
        """
        Returns the selected strength for the mini-game, defaulting to 1 if not set.
        Maps minigame results to battle simulator strength values.
        """
        if self.module.ruleset == "dmc":
            # DMC: Dummy charge strength 0-14
            if self.strength < 5:
                return 0
            elif self.strength < 10:
                return 1
            elif self.strength < 14:
                return 2
            else:
                return 3
        elif self.module.ruleset == "dmx":
            # DMX: XAI bar strength (varies by XAI roll)
            return self.strength
        elif self.module.ruleset == "penc":
            # PenC: Count match super hits
            return self.super_hits
        elif self.module.ruleset == "vb":
            # VB: Shake punch strength 0-20
            if self.strength < 10:
                return 0
            elif self.strength < 15:
                return 1
            elif self.strength < 20:
                return 2
            else:
                return 3
        return 1

    def simulate_global_combat(self):
        # Use the BattlePlayer's teams for simulation
        team1 = []
        team2 = []
        
        # Prepare team1 (player's Digimon)
        for i, pet in enumerate(self.battle_player.team1):
            team1.append(Digimon(
                name=pet.name,
                order=i,
                traited=1 if pet.traited else 0,
                egg_shake=1 if pet.shook else 0,
                index=i,
                hp=self.battle_player.team1_hp[i],
                attribute=pet.attribute,
                power=pet.get_power(self.power_bonus),
                handicap=0,
                buff=self.attack_boost,
                mini_game=self.get_minigame_strength(),
                level=pet.level,
                stage=pet.stage,
                sick=1 if pet.sick > 0 else 0,
                shot1=pet.atk_main,
                shot2=pet.atk_alt,
                tag_meter=0
            ))

        # Prepare team2 (enemy Digimon)
        for i, enemy in enumerate(self.battle_player.team2):
            enemy_stage_index = max(1, enemy.stage - 1)
            enemy_level = constants.MAX_LEVEL.get(enemy_stage_index, 1)
            
            # Get enemy power - handle PvP pets with custom power values
            if hasattr(enemy, '_pvp_power'):
                enemy_power = enemy._pvp_power
            elif hasattr(enemy, 'get_power') and callable(enemy.get_power):
                enemy_power = enemy.get_power()
            else:
                enemy_power = getattr(enemy, 'power', 1)
            
            team2.append(Digimon(
                name=enemy.name,
                order=i,
                traited=getattr(enemy, 'traited', 0),
                egg_shake=getattr(enemy, 'shook', 0),
                index=i,
                hp=self.battle_player.team2_hp[i],
                attribute=enemy.attribute,
                power=enemy_power,
                handicap=getattr(enemy, "handicap", 0),
                buff=0,
                mini_game=1,
                level=getattr(enemy, 'level', enemy_level),
                stage=enemy.stage,
                sick=1 if getattr(enemy, 'sick', 0) > 0 else 0,
                shot1=enemy.atk_main,
                shot2=enemy.atk_alt,
                tag_meter=0
            ))

        # Simulate the battle using the GlobalBattleSimulator
        sim = GlobalBattleSimulator(
            attribute_advantage=self.module.battle_atribute_advantage,
            damage_limit=self.module.battle_damage_limit
        )
        result = sim.simulate(team1, team2)

        # Store the result for animation/processing
        self.global_battle_log = result
        self.victory_status = "Victory" if result.winner == "device1" else "Defeat"
        
        # Update quest progress if battle was won (skip for PvP)

        if not self.pvp_mode and self.victory_status == "Victory":
            if self.boss:
                # Update BOSS quest progress
                update_quest_progress(QuestType.BOSS, 1, self.module.name)
            # Update BATTLE quest progress
            update_quest_progress(QuestType.BATTLE, 1, self.module.name)

        # Process battle results for animations and rewards
        #Remove because it is called by calling function calculate_combat_for_pairs() directly,
        #otherwise it is called twice, and DP and battles are updated twice, not once.
        #self.process_battle_results()

    def draw_debug_battle_logs(self, surface):
        """
        Draws debug battle log information between enemies and pets when DEBUG_MODE flag is enabled.
        Shows turn number, hit results, and attack direction arrows.
        """
        if not constants.DEBUG_MODE or not hasattr(self, 'debug_battle_logs'):
            return
            
        font_small = get_font(runtime_globals.FONT_SIZE_SMALL)
        
        for i, log_entry in enumerate(self.debug_battle_logs):
            if i >= len(self.battle_player.team1):
                continue
                
            # Calculate position between enemy and pet
            pet_y = self.get_y(i, len(self.battle_player.team1))
            pet_x = self.get_team1_x(i)
            
            if i < len(self.battle_player.team2):
                enemy_x = self.get_team2_x(i) + (runtime_globals.PET_WIDTH * constants.BOSS_MULTIPLIER if self.boss else runtime_globals.PET_WIDTH)
            else:
                # For cases where there are fewer enemies than pets (boss battle)
                enemy_x = self.get_team2_x(0) + (runtime_globals.PET_WIDTH * constants.BOSS_MULTIPLIER if self.boss else runtime_globals.PET_WIDTH)
            
            # Position debug log in the middle between enemy and pet
            log_x = (enemy_x + pet_x) // 2
            log_y = pet_y + runtime_globals.PET_HEIGHT // 2
            
            # Draw turn information
            turn_text = f"Turn {log_entry['turn']}"
            arrow = log_entry['arrow']
            hit_text = log_entry['hit']
            
            # Combine arrow and turn text
            if arrow == ">":
                display_text = f"{turn_text} >"
            elif arrow == "<":
                display_text = f"< {turn_text}"
            else:
                display_text = turn_text
                
            # Draw turn text
            turn_surface = font_small.render(display_text, True, constants.FONT_COLOR_DEFAULT)
            text_rect = turn_surface.get_rect(center=(log_x, log_y - int(10 * runtime_globals.UI_SCALE)))
            surface.blit(turn_surface, text_rect)
            
            # Draw hit result if available
            if hit_text:
                hit_color = self.get_hit_text_color(hit_text)
                hit_surface = font_small.render(hit_text, True, hit_color)
                hit_rect = hit_surface.get_rect(center=(log_x, log_y + int(10 * runtime_globals.UI_SCALE)))
                surface.blit(hit_surface, hit_rect)


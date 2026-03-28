#=====================================================================
# Training (Base Class for All Training Modes)
#=====================================================================
import pygame

from ui.ui_constants import TEXT_FONT
from core import runtime_globals
from models.animation import PetFrame
from ui.ui_manager import UIManager
from ui.components.animated_sprite import AnimatedSprite
from battle import combat_constants
import core.constants as constants
from utils.pet_utils import distribute_pets_evenly, get_training_targets
from utils.pygame_utils import blit_with_shadow, load_attack_sprites, module_attack_sprites
from utils.scene_utils import change_scene
from models.game_quest import QuestType
from utils.quest_event_utils import update_quest_progress

class Training:
    """
    Training mode where players build up strength by holding a bar.
    """

    def __init__(self, ui_manager: UIManager) -> None:
        self.ui_manager = ui_manager
        self.phase = "alert"
        self.frame_counter = 0

        self.attack_positions = []
        self.attack_phase = 1
        self.attack_waves = []
        self.current_wave_index = 0
        self.flash_frame = 0
        self.impact_counter = 0
        self.attacks_prepared = False
        self.phase2_reached = False

        # Animated sprite component for full-screen animations
        self.animated_sprite = AnimatedSprite(ui_manager)

        # Pet sprite caching for training display
        self._pet_sprite_cache = {}
        self.pet_state = None

        # Load only the trophy sprite since it's not handled by AnimatedSprite
        self.trophy_sprite = self.ui_manager.load_sprite_integer_scaling(name="Trophies", prefix="Status")

        self.background_color = (0, 0, 0)
        self.flash_color = (255, 216, 0)

        self.attack_jump = 0
        self.attack_forward = 0
        self.attack_frame = None
        self.attack_sprites = load_attack_sprites()
        self._alert_anim_started = False
        self._impact_anim_started = False

        self.pets = get_training_targets()
        self.module_attack_sprites = {}
        for pet in self.pets:
            self.module_attack_sprites[pet.module] = module_attack_sprites(pet.module)

    def get_attack_sprite(self, pet, attack_id):
        """
        Get attack sprite for a pet, preferring module-specific sprites over defaults.
        """
        # First try module-specific attack sprites
        if pet.module in self.module_attack_sprites:
            module_sprite = self.module_attack_sprites[pet.module].get(str(attack_id))
            if module_sprite:
                return module_sprite
        
        # Fall back to default attack sprites
        return self.attack_sprites.get(str(attack_id))

    def _combine_sprites(self, sprite, offsets):
        """Combine a sprite rendered at multiple offsets into a single surface."""
        if len(offsets) == 1:
            return sprite.copy()
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
        return combined

    def update(self):
        # Update animated sprite component
        self.animated_sprite.update()
        
        if self.phase == "alert":
            self.update_alert_phase()
        elif self.phase == "charge":
            self.update_charge_phase()
        elif self.phase == "wait_attack":
            self.update_wait_attack_phase()
        elif self.phase == "attack_move":
            self.move_attacks()
        elif self.phase == "impact":
            self.update_impact_phase()
        elif self.phase == "result":
            self.update_result_phase()
        self.frame_counter += 1

    def update_alert_phase(self):
        if self.frame_counter == int(30 * (constants.FRAME_RATE / 30)):
            runtime_globals.game_sound.play("happy")
        if self.frame_counter >= combat_constants.ALERT_DURATION_FRAMES:
            self.animated_sprite.stop()
            self.phase = "charge"
            self.frame_counter = 0
            self.bar_timer = pygame.time.get_ticks()

    def update_charge_phase(self):
        pass

    def update_wait_attack_phase(self):
        self.attack_frame = self.animate_attack(20)
        if self.frame_counter >= combat_constants.WAIT_ATTACK_READY_FRAMES:
            self.attack_frame = None
            self.phase = "attack_move"
            self.frame_counter = 0
            runtime_globals.game_sound.play("attack")

    def animate_attack(self, delay=0):
        appear_frame = int(delay * (constants.FRAME_RATE / 30))
        anim_window = int(20 * (constants.FRAME_RATE / 30))
        anim_start = appear_frame - anim_window
        anim_end = appear_frame

        progress = 0
        if anim_start <= self.frame_counter < anim_end:
            progress = (self.frame_counter - anim_start) / max(1, (anim_end - anim_start))
            if progress < 0.5:
                self.attack_forward += 1 * (30 / constants.FRAME_RATE)
                if progress < 0.25:
                    self.attack_jump += 1 * (30 / constants.FRAME_RATE)
                else:
                    self.attack_jump -= 1 * (30 / constants.FRAME_RATE)
            else:
                self.attack_forward -= 1 * (30 / constants.FRAME_RATE)
        else:
            self.attack_forward = 0
            self.attack_jump = 0

        train2_frames = int(6 * (constants.FRAME_RATE / 30))
        if delay == 20:
            if self.frame_counter > anim_end - train2_frames:
                frame_enum = PetFrame.TRAIN2
            else:
                frame_enum = PetFrame.TRAIN1
        else:
            if (self.frame_counter > anim_end - train2_frames) or (self.frame_counter < train2_frames):
                frame_enum = PetFrame.TRAIN2
            else:
                frame_enum = PetFrame.TRAIN1
        return frame_enum

    def update_impact_phase(self):
        self.flash_frame += 1
        if self.flash_frame >= combat_constants.IMPACT_DURATION_FRAMES:
            self.animated_sprite.stop()
            self.phase = "result"
            self.frame_counter = 0

    def update_result_phase(self):
        if self.frame_counter >= combat_constants.RESULT_SCREEN_FRAMES:
            self.finish_training()

    def move_attacks(self):
        pass

    def finish_training(self):
        won = self.check_victory()
        if won:
            runtime_globals.game_sound.play("attack_fail")
            
            # Update TRAINING quest progress when training is won
            update_quest_progress(QuestType.TRAINING, 1)
        else:
            runtime_globals.game_sound.play("fail")

        # Check for trophy conditions and award trophies
        self.check_and_award_trophies()

        for pet in self.pets:
            pet.finish_training(won, grade=self.get_attack_count(), phase2=self.phase2_reached)

        distribute_pets_evenly()
        change_scene("game")

    def draw_trophy_notification(self, surface, quantity=1):
        if quantity > 0:
            """Draw a small trophy icon with +1 in the bottom right corner"""
            from utils.asset_utils import font_load
            trophy_size = int(24 * runtime_globals.UI_SCALE)
            font = font_load(TEXT_FONT, int(24 * runtime_globals.UI_SCALE))
            plus_text = font.render(f"+{quantity}", True, constants.FONT_COLOR_YELLOW)

            # Draw trophy icon in bottom right
            trophy_x = runtime_globals.SCREEN_WIDTH - trophy_size - plus_text.get_width() - int(4 * runtime_globals.UI_SCALE)
            trophy_y = runtime_globals.SCREEN_HEIGHT - trophy_size
            blit_with_shadow(surface, self.trophy_sprite, (trophy_x, trophy_y))
            # Draw +1 text next to trophy
            
            text_x = trophy_x + trophy_size + int(2 * runtime_globals.UI_SCALE)
            text_y = trophy_y + int(4 * runtime_globals.UI_SCALE)
            blit_with_shadow(surface, plus_text, (text_x, text_y))

    def draw(self, screen: pygame.Surface):
        if self.phase == "alert":
            self.draw_alert(screen)
        elif self.phase == "charge":
            self.draw_charge(screen)
        elif self.phase == "wait_attack":
            self.draw_attack_ready(screen)
        elif self.phase == "attack_move":
            self.draw_attack_move(screen)
        elif self.phase == "impact":
            self.draw_impact(screen)
        elif self.phase == "result":
            self.draw_result(screen)

    def _init_pet_sprite_cache(self):
        """
        Pre-scales all pet sprites for each frame_enum and caches them.
        """
        runtime_globals.game_console.log(f"[Training._init_pet_sprite_cache] Initializing cache for {len(self.pets)} pets")
        self._pet_sprite_cache = {}
        for pet in self.pets:
            self._pet_sprite_cache[pet] = {}
            runtime_globals.game_console.log(f"[Training._init_pet_sprite_cache] Pet {pet.name}: pet_sprites has {len(runtime_globals.pet_sprites.get(pet, []))} frames")
            for frame_enum in PetFrame:
                sprite = runtime_globals.pet_sprites[pet][frame_enum.value]
                runtime_globals.game_console.log(f"[Training._init_pet_sprite_cache] {pet.name} {frame_enum.name}: sprite id={id(sprite)}, size={sprite.get_size()}")
                scaled_sprite = pygame.transform.scale(sprite, (runtime_globals.OPTION_ICON_SIZE, runtime_globals.OPTION_ICON_SIZE))
                self._pet_sprite_cache[pet][frame_enum] = scaled_sprite

    def draw_pets(self, surface, frame_enum=PetFrame.IDLE1):
        # Initialize cache if not present or pets changed
        # Cache the pets tuple to avoid expensive set comparisons every frame
        current_pets = tuple(self.pets)  # tuple for hashable comparison
        if (not hasattr(self, '_pet_sprite_cache') or 
            not hasattr(self, '_cached_pets_tuple') or 
            self._cached_pets_tuple != current_pets):
            self._init_pet_sprite_cache()
            self._cached_pets_tuple = current_pets

        # Use the correct frame_enum for animation
        if self.attack_frame:
            frame_enum = self.attack_frame
        self.pet_state = frame_enum

        total_pets = len(self.pets)
        available_height = runtime_globals.SCREEN_HEIGHT
        spacing = min(available_height // total_pets, runtime_globals.OPTION_ICON_SIZE + int(20 * runtime_globals.UI_SCALE))
        start_y = (runtime_globals.SCREEN_HEIGHT - (spacing * total_pets)) // 2

        for i, pet in enumerate(self.pets):
            pet_sprite = self._pet_sprite_cache[pet][frame_enum]
            x = runtime_globals.SCREEN_WIDTH - runtime_globals.OPTION_ICON_SIZE - int(16 * runtime_globals.UI_SCALE) + int(self.attack_forward * runtime_globals.UI_SCALE)
            y = start_y + i * spacing - int(self.attack_jump * runtime_globals.UI_SCALE)
            blit_with_shadow(surface, pet_sprite, (x, y))

    def draw_alert(self, screen):
        # Use AnimatedSprite component with predefined ready animation
        if not self._alert_anim_started:
            # Start the ready animation once
            duration = combat_constants.ALERT_DURATION_FRAMES / constants.FRAME_RATE
            self.animated_sprite.play_ready(duration)
            self._alert_anim_started = True
        
        # Only draw if still playing (don't draw after update_alert_phase stopped it)
        if self.animated_sprite.is_animation_playing():
            self.animated_sprite.draw(screen)

    def draw_attack_ready(self, surface):
        self.draw_pets(surface, PetFrame.ATK1)

    def draw_charge(self, surface):
        pass

    def draw_attack_move(self, surface):
        pass

    def draw_impact(self, screen):
        # Use AnimatedSprite component with predefined impact animation
        if not self._impact_anim_started:
            duration = combat_constants.IMPACT_DURATION_FRAMES / constants.FRAME_RATE
            self.animated_sprite.play_impact(duration)
            self._impact_anim_started = True
        
        if self.animated_sprite.is_animation_playing():
            self.animated_sprite.draw(screen)

    def draw_result(self, surface):
        pass

    def handle_event(self, event):
        event_type, event_data = event
        
        if self.phase == "charge" and event_type == "A":
            runtime_globals.game_sound.play("menu")
            self.strength = min(getattr(self, "strength", 0) + 1, getattr(self, "bar_level", 14))
        elif self.phase in ["wait_attack", "attack_move", "impact", "result"] and event_type in ["B", "START"]:
            self.finish_training()
        elif self.phase in ["alert", "charge"] and event_type == "B":
            runtime_globals.game_sound.play("cancel")
            change_scene("game")
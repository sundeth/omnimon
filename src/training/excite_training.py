#=====================================================================
# ExciteTraining (Simple Strength Bar Training)
#=====================================================================

import pygame
from core import game_globals, runtime_globals
from models.animation import PetFrame
from training.training import Training
from ui.ui_manager import UIManager
from battle import combat_constants
import core.constants as constants
from ui.minigames.xai_bar import XaiBar
from utils.pygame_utils import blit_with_shadow
from utils.scene_utils import change_scene

class ExciteTraining(Training):
    """
    Excite training mode where players build up strength by holding a bar.
    """

    def __init__(self, ui_manager: UIManager) -> None:
        super().__init__(ui_manager)
        self.xaibar = XaiBar(10 * runtime_globals.UI_SCALE, runtime_globals.SCREEN_HEIGHT // 2 - (18 * runtime_globals.UI_SCALE), game_globals.xai, self.pets[0])
        self.xaibar.start()
        # Remove separate sprite assignments; use self._sprite_cache from base class

    def update_charge_phase(self):
        self.xaibar.update()
        # End phase after a certain time or on input (like bar phase)
        if self.frame_counter > int(30 * 3 * (constants.FRAME_RATE / 30)):
            self.xaibar.stop()
            runtime_globals.game_console.log(f"XaiBar phase ended strength {self.xaibar.selected_strength}.")
            self.phase = "wait_attack"
            self.frame_counter = 0
            self.prepare_attacks()

    def move_attacks(self):
        """Handles the attack movement towards the bag, all in one phase."""
        if self.current_wave_index >= len(self.attack_waves):
            self.phase = "result"
            self.frame_counter = 0
            return

        wave = self.attack_waves[self.current_wave_index]
        new_wave = []
        all_off_screen = True

        if self.frame_counter <= 1:
            runtime_globals.game_sound.play("attack")

        now = pygame.time.get_ticks()
        if not hasattr(self, '_last_atk_tick'):
            self._last_atk_tick = now
        dt_ms = min(100, max(1, now - self._last_atk_tick))
        self._last_atk_tick = now
        speed = combat_constants.ATTACK_SPEED * 30 * dt_ms / 1000

        for sprite, x, y in wave:
            x -= speed
            if x + (24 * runtime_globals.UI_SCALE) > 0:
                all_off_screen = False
                new_wave.append((sprite, x, y))

        self.attack_waves[self.current_wave_index] = new_wave

        # Wait at least 10 frames (at 30fps) before next wave
        if all_off_screen and self.frame_counter >= int(10 * (constants.FRAME_RATE / 30)):
            self.current_wave_index += 1
            self.frame_counter = 0

    def check_victory(self):
        """Apply training results and return to game."""
        return self.xaibar.selected_strength > 0

    def check_and_award_trophies(self):
        """Award trophy if strength reaches maximum (3)"""
        if self.xaibar.selected_strength == 3:
            for pet in self.pets:
                pet.trophies += 1
            runtime_globals.game_console.log(f"[TROPHY] Excite training perfect score achieved! Trophy awarded.")

    def draw_charge(self, surface):
        self.xaibar.draw(surface)
        self.draw_pets(surface, PetFrame.IDLE1)

    def draw_pets(self, surface, frame_enum=PetFrame.IDLE1):
        """
        Draws pets using appropriate frame based on attack animation phase.
        """
        if self.phase == "attack_move":
            frame_enum = self.animate_attack(46)
        super().draw_pets(surface, frame_enum)

    def draw_attack_move(self, surface):
        self.draw_pets(surface)
        for wave in self.attack_waves:
            for sprite, x, y in wave:
                if x < runtime_globals.SCREEN_WIDTH - (90 * runtime_globals.UI_SCALE):
                    blit_with_shadow(surface, sprite, (x, y))

    def draw_result(self, surface):
        strength = self.xaibar.selected_strength
        
        # Use AnimatedSprite component with predefined result animations
        if not self.animated_sprite.is_animation_playing():
            duration = combat_constants.RESULT_SCREEN_FRAMES / constants.FRAME_RATE
            
            # Choose which result animation to play based on strength
            if strength == 0:
                self.animated_sprite.play_bad(duration)
            elif strength == 1:
                self.animated_sprite.play_good(duration)
            elif strength == 2:
                self.animated_sprite.play_great(duration)
            else:
                self.animated_sprite.play_excellent(duration)
        
        # Draw the animated sprite
        self.animated_sprite.draw(surface)

        # Trophy notification on max
        if strength == 3:
            self.draw_trophy_notification(surface)

    def prepare_attacks(self):
        """Prepare 5 attacks from each pet based on selected_strength."""
        self.attack_phase = 0
        self.attack_waves = [[] for _ in range(5)]
        pets = self.pets
        total_pets = len(pets)

        available_height = runtime_globals.SCREEN_HEIGHT
        spacing = min(available_height // total_pets, runtime_globals.OPTION_ICON_SIZE + (20 * runtime_globals.UI_SCALE))
        start_y = (runtime_globals.SCREEN_HEIGHT - (spacing * total_pets)) // 2

        # Determine super-hit pattern based on selected_strength
        strength = self.xaibar.selected_strength
        if strength == 3:
            pattern = [4, 3, 3, 3, 3]  # 5 super-hits (megahit)
        elif strength == 2:
            pattern = [3, 3, 3, 2, 2]  # 3 super-hits, 2 normal
        elif strength == 1:
            pattern = [3, 2, 1, 1, 1]  # 1 super-hit, 4 normal
        else:
            pattern = [1] * 5  # all normal, fail

        s = runtime_globals.UI_SCALE
        for i, pet in enumerate(pets):
            main_sprite = self.get_attack_sprite(pet, pet.atk_main)
            alt_sprite = self.get_attack_sprite(pet, pet.atk_alt) if getattr(pet, "atk_alt", 0) > 0 else main_sprite
            if not main_sprite:
                continue
            pet_y = start_y + i * spacing + runtime_globals.OPTION_ICON_SIZE // 2 - main_sprite.get_height() // 2
            for j, kind in enumerate(pattern):
                x = runtime_globals.SCREEN_WIDTH - runtime_globals.OPTION_ICON_SIZE - (20 * s)
                y = pet_y
                if kind == 4:
                    combined = pygame.transform.scale2x(alt_sprite)
                    self.attack_waves[j].append((combined, x, y))
                elif kind == 3:
                    offsets = [(0, 0), (-int(20 * s), -int(10 * s)), (-int(40 * s), int(10 * s))]
                    combined = self._combine_sprites(alt_sprite, offsets)
                    self.attack_waves[j].append((combined, x, y))
                elif kind == 2:
                    offsets = [(0, 0), (-int(20 * s), -int(10 * s))]
                    combined = self._combine_sprites(alt_sprite, offsets)
                    self.attack_waves[j].append((combined, x, y))
                else:
                    self.attack_waves[j].append((main_sprite, x, y))

    def get_attack_count(self):
        strength = self.xaibar.selected_strength
        if strength < 1:
            return 1
        elif strength < 3:
            return 2
        else:
            return 3

    def handle_event(self, event):
        event_type, event_data = event
        
        if self.phase == "charge" and event_type in ["A", "LCLICK"]:
            runtime_globals.game_sound.play("menu")
            self.xaibar.stop()
            runtime_globals.game_console.log(f"XaiBar phase ended strength {self.xaibar.selected_strength}.")
            self.phase = "wait_attack"
            self.frame_counter = 0
            self.prepare_attacks()
        elif self.phase in ["wait_attack", "attack_move", "impact"] and event_type in ["B", "START"]:
            runtime_globals.game_sound.play("cancel")
            self.animated_sprite.stop()
            self.phase = "result"
        elif self.phase in ["alert", "charge"] and event_type == "B":
            runtime_globals.game_sound.play("cancel")
            change_scene("game")
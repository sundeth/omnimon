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
from utils.pygame_utils import blit_with_cache
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

    def _do_xaibar_stop(self):
        """Freeze the bar; the phase advances after its 0.5s result hold."""
        runtime_globals.game_sound.play("menu")
        self.xaibar.stop()
        runtime_globals.game_console.log(f"XaiBar phase ended strength {self.xaibar.selected_strength}.")

    def _finish_xaibar_phase(self):
        self.phase = "wait_attack"
        self.frame_counter = 0
        self.prepare_attacks()

    def update_charge_phase(self):
        # After stopping, linger half a second so the landed color is visible
        if getattr(self.xaibar, 'stopped', False):
            if self.xaibar.is_finished():
                self._finish_xaibar_phase()
            return

        self.xaibar.update()
        # Auto-stop after the time limit
        if self.frame_counter > int(30 * 3 * (constants.FRAME_RATE / 30)):
            self.xaibar.stop()
            runtime_globals.game_console.log(f"XaiBar phase ended strength {self.xaibar.selected_strength}.")

    def move_attacks(self):
        """Handles the attack movement towards the bag, all in one phase."""
        if self.current_wave_index >= len(self.attack_waves):
            self.phase = "result"
            self.frame_counter = 0
            return

        wave = self.attack_waves[self.current_wave_index]
        new_wave = []
        all_off_screen = True

        # Shot sound is played by the base class on prep-end; don't duplicate here.

        now = pygame.time.get_ticks()
        if not hasattr(self, '_last_atk_tick'):
            self._last_atk_tick = now
        dt_ms = min(100, max(1, now - self._last_atk_tick))
        self._last_atk_tick = now
        speed = combat_constants.ATTACK_SPEED * 30 * dt_ms / 1000 * self.attack_speed_factor()

        for sprite, x, y in wave:
            x -= speed
            if x + (24 * runtime_globals.UI_SCALE) > 0:
                all_off_screen = False
                new_wave.append((sprite, x, y))

        self.attack_waves[self.current_wave_index] = new_wave

        # Wait at least 10 frames (at 30fps) before next wave
        if all_off_screen and self.frame_counter >= int(4 * (constants.FRAME_RATE / 30)):
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

    def draw_attack_move(self, surface):
        self.draw_pets(surface)
        for wave in self.attack_waves:
            for sprite, x, y in wave:
                if x < runtime_globals.SCREEN_WIDTH - (90 * runtime_globals.UI_SCALE):
                    blit_with_cache(surface, sprite, (x, y))

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
                self.animated_sprite.play_megahit(duration)
        
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
            pattern = [5, 4, 5, 4, 4]  # megahit
        elif strength == 2:
            pattern = [3, 4, 3, 3, 2]  # great
        elif strength == 1:
            pattern = [1, 2, 1, 2, 2]  # good
        else:
            pattern = [1, 1, 1, 1, 1]  # fail

        # Activate special attack animation if pattern includes strike 5
        if 5 in pattern:
            for pet in pets:
                if self._is_critical_attack(pet, 5):
                    self.special_attack_active = True
                    break

        # Store wave kinds for per-wave slide animation
        self.attack_wave_kinds = pattern[:]

        s = runtime_globals.UI_SCALE
        for i, pet in enumerate(pets):
            main_sprite = self.get_attack_sprite(pet, pet.atk_main)
            alt_sprite = self.get_attack_sprite(pet, pet.atk_alt) if getattr(pet, "atk_alt", 0) > 0 else main_sprite
            alt2_sprite = self.get_attack_sprite(pet, pet.atk_alt_2) if getattr(pet, "atk_alt_2", 0) > 0 else None
            if not main_sprite:
                continue
            pet_y = start_y + i * spacing + runtime_globals.OPTION_ICON_SIZE // 2 - main_sprite.get_height() // 2
            slot_center_y = pet_y + main_sprite.get_height() // 2
            for j, kind in enumerate(pattern):
                x = runtime_globals.SCREEN_WIDTH - runtime_globals.OPTION_ICON_SIZE - (20 * s)
                y = pet_y
                if kind == 5:
                    # Critical attack: prefer a dedicated atk_crit sprite (no scale2x needed).
                    # Fall back to alt2/alt/main sprite scaled 2x when no crit sprite exists.
                    # Start crit sprites at the visibility threshold (not past it) so they are
                    # hidden during the slide-in and only appear when move_attacks() fires them.
                    x_crit = runtime_globals.SCREEN_WIDTH - int(90 * s)
                    atk_alt2 = getattr(pet, "atk_alt_2", 0)
                    crit_sprite = self.get_crit_attack_sprite(pet, atk_alt2) if atk_alt2 and atk_alt2 > 0 else None
                    if crit_sprite:
                        self.attack_waves[j].append((crit_sprite, x_crit, slot_center_y - crit_sprite.get_height() // 2))
                    else:
                        sprite = alt2_sprite or alt_sprite or main_sprite
                        scaled = pygame.transform.scale2x(sprite)
                        self.attack_waves[j].append((scaled, x_crit, slot_center_y - scaled.get_height() // 2))
                elif kind == 4:
                    # 2 atk_alt sprites, fallback 3 atk_main sprites
                    if getattr(pet, "atk_alt", 0) > 0:
                        offsets = [(0, 0), (-int(20 * s), -int(10 * s))]
                        combined = self._combine_sprites(alt_sprite, offsets)
                    else:
                        offsets = [(0, 0), (-int(20 * s), -int(10 * s)), (-int(40 * s), int(10 * s))]
                        combined = self._combine_sprites(main_sprite, offsets)
                    self.attack_waves[j].append((combined, x, y))
                elif kind == 3:
                    # 1 atk_alt sprite, fallback 3 atk_main sprites
                    if getattr(pet, "atk_alt", 0) > 0:
                        self.attack_waves[j].append((alt_sprite, x, y))
                    else:
                        offsets = [(0, 0), (-int(20 * s), -int(10 * s)), (-int(40 * s), int(10 * s))]
                        combined = self._combine_sprites(main_sprite, offsets)
                        self.attack_waves[j].append((combined, x, y))
                elif kind == 2:
                    # 2 atk_main sprites
                    offsets = [(0, 0), (-int(20 * s), -int(10 * s))]
                    combined = self._combine_sprites(main_sprite, offsets)
                    self.attack_waves[j].append((combined, x, y))
                else:
                    # 1 atk_main sprite
                    self.attack_waves[j].append((main_sprite, x, y))

    def get_attack_count(self):
        # The Xai bar already reports 0-3, which is exactly the Digital
        # Monster X's Bad / Good / Great / Excellent.
        strength = self.xaibar.selected_strength
        if strength < 1:
            return 0
        elif strength < 3:
            return 2
        else:
            return 3

    def handle_event(self, event):
        event_type, event_data = event

        if self.phase == "alert":
            return

        if event_type in ["A", "LCLICK"]:
            if self.phase == "charge":
                self._do_xaibar_stop()
        elif self.phase in ["wait_attack", "attack_move", "impact"] and event_type in ["B", "START"]:
            runtime_globals.game_sound.play("cancel")
            self.animated_sprite.stop()
            self.phase = "result"
        elif self.phase == "charge" and event_type == "B":
            runtime_globals.game_sound.play("cancel")
            change_scene("game")

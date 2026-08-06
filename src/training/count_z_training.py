#=====================================================================
# CountMatchZTraining (Arrow-based Attribute Match Training)
#=====================================================================

import random
import pygame

from core import runtime_globals
from models.animation import PetFrame
from training.training import Training
from ui.ui_manager import UIManager
from ui.minigames.count_match_z import CountMatchZ
from battle import combat_constants
import core.constants as constants
from utils.pygame_utils import blit_with_cache


class CountMatchZTraining(Training):
    """
    Count Match Z training mode where players match arrows based on attribute.
    Uses the CountMatchZ minigame (arrow-based counting).
    """

    def __init__(self, ui_manager: UIManager):
        super().__init__(ui_manager)
        self.press_counter = 0
        self.start_time = 0
        self.super_hits = {}
        self.result_text = None
        self.flash_frame = 0
        self.anim_counter = -1
        
        # Initialize the count match Z minigame with our AnimatedSprite component
        self.count_match_z = None
        pet = self.pets[0]
        self.count_match_z = CountMatchZ(self.ui_manager, pet, self.animated_sprite)

    def update(self):
        """Override base update to include minigame updates."""
        # Call parent update
        super().update()
        
        # Update minigame and sync counters
        if self.count_match_z:
            self.count_match_z.update()
            self.press_counter = self.count_match_z.get_press_counter()

    def update_charge_phase(self):
        if self.count_match_z.phase != "count":
            self.start_count_phase()
        # Use frame-rate independent timing (3 seconds)
        if self.frame_counter > int(3 * constants.FRAME_RATE):
            self.phase = "wait_attack"
            self.calculate_results()
            self.prepare_attack()

    def start_count_phase(self):
        self.phase = "charge"
        self.press_counter = 0
        
        # Set minigame to count phase
        self.count_match_z.set_phase("count")

    def handle_event(self, event):
        event_type, event_data = event

        if self.phase == "alert":
            return
        
        if self.phase == "charge" and event_type in ("Y", "SHAKE"):
            # Let the minigame handle the input
            if self.count_match_z and self.count_match_z.handle_event(event):
                self.press_counter = self.count_match_z.get_press_counter()
                
        elif self.phase in ["wait_attack", "attack_move", "impact"] and event_type in ["B", "START"]:
            # Skip to result phase
            runtime_globals.game_sound.play("cancel")
            self.animated_sprite.stop()
            self.phase = "result"
            self.frame_counter = 0
        elif self.phase == "result" and event_type in ["B", "START"]:
            self.finish_training()
    def calculate_results(self):
        """Calculate training results based on minigame result."""
        pets = self.pets
        if not pets:
            return

        # Get result from minigame (0=BAD, 1=GOOD, 2=GREAT, 3=EXCELLENT/MEGAHIT)
        result = self.count_match_z.calculate_result()
        
        # Store strength result for result screen
        self.strength_result = result

        for p in pets:
            self.super_hits[p] = result

    def prepare_attack(self):
        self.attack_phase = 0
        self.attack_waves = [[] for _ in range(5)]
        pets = self.pets
        total_pets = len(pets)
        available_height = runtime_globals.SCREEN_HEIGHT
        spacing = min(available_height // total_pets, runtime_globals.OPTION_ICON_SIZE + (20 * runtime_globals.UI_SCALE))
        start_y = (runtime_globals.SCREEN_HEIGHT - (spacing * total_pets)) // 2

        # Per-wave maximum kind across all pets — drives crit-slide detection.
        wave_kinds_max = [0] * 5

        s = runtime_globals.UI_SCALE
        for i, pet in enumerate(pets):
            main_sprite = self.get_attack_sprite(pet, pet.atk_main)
            alt_sprite = self.get_attack_sprite(pet, pet.atk_alt) if getattr(pet, "atk_alt", 0) > 0 else main_sprite
            alt2_sprite = self.get_attack_sprite(pet, pet.atk_alt_2) if getattr(pet, "atk_alt_2", 0) > 0 else None
            if not main_sprite:
                continue
            count = self.super_hits.get(pet, 0)
            # Use same patterns as DMX/excite training
            if count == 3:
                pattern = [5, 4, 5, 4, 4]  # megahit
            elif count == 2:
                pattern = [3, 4, 3, 3, 2]  # great
            elif count == 1:
                pattern = [1, 2, 1, 2, 2]  # good
            else:
                pattern = [1, 1, 1, 1, 1]  # fail

            # Activate special attack animation if pattern includes strike 5
            if 5 in pattern and self._is_critical_attack(pet, 5):
                self.special_attack_active = True

            # Merge this pet's pattern into the per-wave maximum (a wave is "crit" if any pet crits in it)
            for j, kind in enumerate(pattern):
                wave_kinds_max[j] = max(wave_kinds_max[j], kind)

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
        # Set attack_wave_kinds to the per-wave maximum kind across all pets
        self.attack_wave_kinds = wave_kinds_max
        self.frame_counter = 0

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

    def draw_alert(self, surface):
        # Use the count match Z minigame to handle ready sprite drawing
        self.count_match_z.draw(surface)

    def draw_charge(self, surface):
        # Use the count match Z minigame to handle count sprite drawing
        self.count_match_z.draw(surface)

    def draw_attack_move(self, surface):
        self.draw_pets(surface)
        for wave in self.attack_waves:
            for sprite, x, y in wave:
                if x < runtime_globals.SCREEN_WIDTH - (90 * runtime_globals.UI_SCALE):
                    blit_with_cache(surface, sprite, (x, y))

    def draw_result(self, screen):
        pets = self.pets
        pet = pets[0]
        hits = self.super_hits.get(pet, 0)
        
        # Completely disable count_match_z during result phase to prevent interference
        if self.count_match_z:
            self.count_match_z.set_phase(None)
        
        # Force stop any manual countdown mode and reset AnimatedSprite state
        self.animated_sprite.stop()
        
        # Set up result animation based on strength result
        if not self.animated_sprite.is_animation_playing():
            duration = combat_constants.RESULT_SCREEN_FRAMES / constants.FRAME_RATE
            
            if hits == 3:
                self.animated_sprite.play_megahit(duration)
            elif hits == 2:
                self.animated_sprite.play_great(duration)
            elif hits == 1:
                self.animated_sprite.play_good(duration)
            else:
                self.animated_sprite.play_bad(duration)
        
        # Draw the animated sprite
        self.animated_sprite.draw(screen)
        
        # Trophy notification for megahit
        if hits == 3:
            self.draw_trophy_notification(screen, quantity=1)

    def check_victory(self):
        """Apply training results and return to game."""
        return self.super_hits.get(self.pets[0], 0) > 0

    def check_and_award_trophies(self):
        """Award trophy if strength result reaches maximum (3)"""
        if self.super_hits.get(self.pets[0], 0) == 3:
            for pet in self.pets:
                pet.trophies += 1
            runtime_globals.game_console.log(f"[TROPHY] Count Match Z training perfect score achieved! Trophy awarded.")

    def get_attack_count(self):
        """
        Determine attack count based on strength result:
          3 (megahit) -> 3
          2 (great) -> 2
          1 (good) -> 1
          0 (bad/fail) -> 0
        """
        return self.super_hits.get(self.pets[0], 0)

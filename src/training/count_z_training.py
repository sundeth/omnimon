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
from utils.pygame_utils import blit_with_shadow
from utils.scene_utils import change_scene


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
        elif self.phase == "alert" and event_type == "B":
            runtime_globals.game_sound.play("cancel")
            change_scene("game")

    def calculate_results(self):
        """Calculate training results based on minigame result."""
        pets = self.pets
        if not pets:
            return

        # Get result from minigame (0=BAD, 1=GOOD, 2=GREAT, 3=EXCELLENT)
        result = self.count_match_z.calculate_result()
        
        # Map result to hits for training
        # 0=BAD -> 1 hit
        # 1=GOOD -> 2 hits
        # 2=GREAT -> 4 hits
        # 3=EXCELLENT -> 5 hits
        hits_map = {0: 1, 1: 2, 2: 4, 3: 5}
        hits = hits_map.get(result, 1)

        for p in pets:
            self.super_hits[p] = hits

    def prepare_attack(self):
        self.attack_phase = 0
        self.attack_waves = [[] for _ in range(5)]
        pets = self.pets
        total_pets = len(pets)
        available_height = runtime_globals.SCREEN_HEIGHT
        spacing = min(available_height // total_pets, runtime_globals.OPTION_ICON_SIZE + (20 * runtime_globals.UI_SCALE))
        start_y = (runtime_globals.SCREEN_HEIGHT - (spacing * total_pets)) // 2

        s = runtime_globals.UI_SCALE
        for i, pet in enumerate(pets):
            main_sprite = self.get_attack_sprite(pet, pet.atk_main)
            alt_sprite = self.get_attack_sprite(pet, pet.atk_alt) if getattr(pet, "atk_alt", 0) > 0 else main_sprite
            if not main_sprite:
                continue
            count = self.super_hits.get(pet, 0)
            pattern = [3] * 5 if count == 5 else [2] * count + [1] * (5 - count)
            pet_y = start_y + i * spacing + runtime_globals.OPTION_ICON_SIZE // 2 - main_sprite.get_height() // 2
            for j, kind in enumerate(pattern):
                x = runtime_globals.SCREEN_WIDTH - runtime_globals.OPTION_ICON_SIZE - (20 * s)
                y = pet_y
                sprite = alt_sprite if kind >= 2 else main_sprite
                if kind == 3:
                    offsets = [(0, 0), (-int(20 * s), -int(10 * s)), (-int(40 * s), int(10 * s))]
                    combined = self._combine_sprites(sprite, offsets)
                    self.attack_waves[j].append((combined, x, y))
                elif kind == 2:
                    offsets = [(0, 0), (-int(20 * s), -int(10 * s))]
                    combined = self._combine_sprites(sprite, offsets)
                    self.attack_waves[j].append((combined, x, y))
                else:
                    self.attack_waves[j].append((sprite, x, y))
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

    def draw_pets(self, surface, frame_enum=PetFrame.IDLE1):
        """Draws pets using appropriate frame based on attack animation phase."""
        if self.phase == "attack_move":
            frame_enum = self.animate_attack(46)
        super().draw_pets(surface, frame_enum)

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
                    blit_with_shadow(surface, sprite, (x, y))

    def draw_result(self, screen):
        pets = self.pets
        pet = pets[0]
        hits = self.super_hits.get(pet, 0)
        
        # Completely disable count_match_z during result phase to prevent interference
        if self.count_match_z:
            self.count_match_z.set_phase(None)
        
        # Force stop any manual countdown mode and reset AnimatedSprite state
        self.animated_sprite.stop()
        
        # Set up result animation based on hit count
        if not self.animated_sprite.is_animation_playing():
            duration = combat_constants.RESULT_SCREEN_FRAMES / constants.FRAME_RATE
            
            if hits == 5:
                self.animated_sprite.play_megahit(duration)
            elif hits < 2:
                self.animated_sprite.play_bad(duration)
            elif hits < 4:
                self.animated_sprite.play_good(duration)
            else:
                self.animated_sprite.play_great(duration)
        
        # Draw the animated sprite
        self.animated_sprite.draw(screen)
        
        # Trophy notification for megahit
        if hits == 5:
            self.draw_trophy_notification(screen, quantity=1)

    def check_victory(self):
        """Apply training results and return to game."""
        return self.super_hits.get(self.pets[0], 0) > 1

    def check_and_award_trophies(self):
        """Award trophy if super_hits reaches maximum (5)"""
        if self.super_hits.get(self.pets[0], 0) == 5:
            for pet in self.pets:
                pet.trophies += 1
            runtime_globals.game_console.log(f"[TROPHY] Count Match Z training perfect score achieved! Trophy awarded.")

    def get_attack_count(self):
        """
        Determine attack count based on super-hit count:
          5 hits -> 3
          4 hits -> 2
          3 hits -> 1
          <3  -> 0 (defeat)
        """
        hits = self.super_hits.get(self.pets[0], 0)
        if hits >= 5:
            return 3
        if hits == 4:
            return 2
        if hits == 3:
            return 1
        return 0

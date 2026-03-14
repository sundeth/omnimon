import random

from core import game_globals, runtime_globals
from core.animation import PetFrame
from core.combat.training import Training
from components.ui.ui_manager import UIManager
from components.minigames.count_match import CountMatch
from core.combat import combat_constants
import core.constants as constants
from core.utils.pygame_utils import blit_with_shadow
from core.utils.scene_utils import change_scene

class CountMatchTraining(Training):
    def __init__(self, ui_manager: UIManager):
        super().__init__(ui_manager)
        self.press_counter = 0
        self.rotation_index = 0
        self.start_time = 0
        self.final_color = 3
        self.correct_color = 0
        self.super_hits = {}
        self.result_text = None
        self.flash_frame = 0
        self.anim_counter = -1
        
        # Initialize the count match minigame with our AnimatedSprite component
        self.count_match = None
        pet = self.pets[0]
        self.count_match = CountMatch(self.ui_manager, pet, self.animated_sprite)

    def update(self):
        """Override base update to include minigame updates."""
        # Call parent update
        super().update()
        
        # Update minigame and sync counters
        if self.count_match:
            self.count_match.update()
            # Always sync our counters with the minigame in case it processed shake events internally
            self.press_counter = self.count_match.get_press_counter()
            self.rotation_index = self.count_match.get_rotation_index()

    def update_charge_phase(self):
        if self.count_match.phase != "count":
            self.start_count_phase()
        # Use frame-rate independent timing (3 seconds)
        if self.frame_counter > int(3 * game_globals.configuration.frame_rate):
            self.phase = "wait_attack"
            self.calculate_results()
            self.prepare_attack()

    def start_count_phase(self):
        self.phase = "charge"
        self.press_counter = 0
        self.rotation_index = 4  # Start at 4 so first shake goes to 3
        
        # Set minigame to count phase
        self.count_match.set_phase("count")

    def handle_event(self, event):
        event_type, event_data = event
        
        if self.phase == "charge" and event_type in ("Y", "SHAKE"):
            # Let the minigame handle the input
            if self.count_match and self.count_match.handle_event(event):
                self.press_counter = self.count_match.get_press_counter()
                self.rotation_index = self.count_match.get_rotation_index()
                
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

    def get_first_pet_attribute(self):
        pet = self.pets[0]
        attr = getattr(pet, "attribute", "")
        if attr in ["", "Va"]:
            return 0  # Default/Vaccine -> Ready0
        elif attr == "Da":
            return 1  # Data -> Ready1
        elif attr == "Vi":
            return 2  # Virus -> Ready2
        return 0

    def calculate_results(self):
        self.correct_color = self.get_first_pet_attribute()
        self.final_color = self.rotation_index
        pets = self.pets
        if not pets:
            return

        pet = pets[0]
        shakes = self.press_counter
        attr_type = getattr(pet, "attribute", "")

        if shakes < 2:
            hits = 0
        else:
            color = self.final_color
            # Map rotation_index (1-4) to color (0-2): 
            # 4->undefined (shouldn't happen), 1->0, 2->1, 3->2
            if color == 4:
                color_mapped = 0  # Failsafe if somehow still on Count4
            else:
                color_mapped = color - 1  # 1->0, 2->1, 3->2
            correct_color = self.correct_color
            
            if attr_type in ("", "Va"):
                hits = 5 if correct_color == color_mapped else random.choice([3, 4]) if abs(correct_color - color_mapped) == 1 else 2 if abs(correct_color - color_mapped) == 2 else 1
            elif attr_type == "Da":
                hits = 5 if correct_color == color_mapped else random.choice([3, 4]) if abs(correct_color - color_mapped) == 1 else 2 if abs(correct_color - color_mapped) == 2 else 1
            elif attr_type == "Vi":
                hits = 5 if correct_color == color_mapped else random.choice([3, 4]) if abs(correct_color - color_mapped) == 1 else 2 if abs(correct_color - color_mapped) == 2 else 1
            else:
                hits = 1

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

        for i, pet in enumerate(pets):
            sprite = self.get_attack_sprite(pet, pet.atk_main)
            if not sprite:
                continue
            count = self.super_hits.get(pet, 0)
            pattern = [3] * 5 if count == 5 else [2] * count + [1] * (5 - count)
            pet_y = start_y + i * spacing + runtime_globals.OPTION_ICON_SIZE // 2 - sprite.get_height() // 2
            for j, kind in enumerate(pattern):
                x = runtime_globals.SCREEN_WIDTH - runtime_globals.OPTION_ICON_SIZE - (20 * runtime_globals.UI_SCALE)
                y = pet_y
                self.attack_waves[j].append((sprite, kind, x, y))
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

        speed = combat_constants.ATTACK_SPEED * (30 / game_globals.configuration.frame_rate)
        for sprite, kind, x, y in wave:
            x -= speed
            if x + (24 * runtime_globals.UI_SCALE) > 0:
                all_off_screen = False
                new_wave.append((sprite, kind, x, y))

        self.attack_waves[self.current_wave_index] = new_wave

        # Wait at least 10 frames (at 30fps) before next wave
        if all_off_screen and self.frame_counter >= int(10 * (game_globals.configuration.frame_rate / 30)):
            self.current_wave_index += 1
            self.frame_counter = 0

    def draw_pets(self, surface, frame_enum=PetFrame.IDLE1):
        """Draws pets using appropriate frame based on attack animation phase."""
        if self.phase == "attack_move":
            frame_enum = self.animate_attack(46)
        super().draw_pets(surface, frame_enum)

    def draw_alert(self, surface):
        # Use the count match minigame to handle ready sprite drawing via AnimatedSprite
        self.count_match.draw(surface)

    def draw_charge(self, surface):
        # Use the count match minigame to handle count sprite drawing via AnimatedSprite
        self.count_match.draw(surface)

    def draw_attack_move(self, surface):
        self.draw_pets(surface)
        for wave in self.attack_waves:
            for sprite, kind, x, y in wave:
                if x < runtime_globals.SCREEN_WIDTH - (90 * runtime_globals.UI_SCALE):
                    blit_with_shadow(surface, sprite, (x, y))
                    if kind > 1:
                        blit_with_shadow(surface, sprite, (x - (20 * runtime_globals.UI_SCALE), y - (10 * runtime_globals.UI_SCALE)))
                    if kind == 3:
                        blit_with_shadow(surface, sprite, (x - (40 * runtime_globals.UI_SCALE), y + (10 * runtime_globals.UI_SCALE)))

    def draw_result(self, screen):
        pets = self.pets
        pet = pets[0]
        hits = self.super_hits.get(pet, 0)
        
        # Completely disable count_match during result phase to prevent interference
        if self.count_match:
            self.count_match.set_phase(None)
        
        # CRITICAL: Force stop any manual countdown mode and reset AnimatedSprite state
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
            runtime_globals.game_console.log(f"[TROPHY] Count training perfect score achieved! Trophy awarded.")

    # ...existing code...
    def get_attack_count(self):
        """
        Determine attack count based on super-hit count:
          5 hits -> 3
          4 hits -> 2
          3 hits -> 1
          <3  -> 0 (defeat)
        Supports reading hits from self.super_hits (dict) or falls back to self.victories.
        """
        hits = self.super_hits.get(self.pets[0], 0)
        if hits >= 5:
            return 3
        if hits == 4:
            return 2
        if hits == 3:
            return 1
        return 0

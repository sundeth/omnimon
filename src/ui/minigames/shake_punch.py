"""
Shake Punch Minigame - Handles the punch mechanics for shake training
"""
import pygame
import random
from ui.ui_constants import TITLE_FONT
from core import runtime_globals
from models.animation import PetFrame
import core.constants as constants
from battle import combat_constants
from utils.pygame_utils import blit_with_cache, blit_with_shadow


class ShakeDetector:
    """
    Detects shake gestures from mouse/touch input for devices without accelerometer.
    Uses rapid left-right movement patterns to simulate shake gestures.
    """
    
    def __init__(self):
        self.positions = []  # Store recent mouse positions
        self.max_history = 10  # Keep last 10 positions
        self.shake_threshold = 50  # Minimum distance for shake detection
        self.direction_changes = 0  # Count direction changes
        self.min_direction_changes = 3  # Minimum changes to detect shake
        self.last_direction = None
        self.shake_cooldown = 0  # Prevent too frequent shake detection
        
    def update(self):
        """Update the shake detector each frame."""
        if self.shake_cooldown > 0:
            self.shake_cooldown -= 1
            
    def add_mouse_position(self, pos):
        """Add a mouse position and check for shake patterns."""
        if self.shake_cooldown > 0:
            return False
            
        self.positions.append(pos)
        
        # Keep only recent positions
        if len(self.positions) > self.max_history:
            self.positions.pop(0)
            
        # Need at least 3 positions to detect direction changes
        if len(self.positions) < 3:
            return False
            
        # Check for rapid left-right movement
        return self._detect_shake_pattern()
        
    def _detect_shake_pattern(self):
        """Analyze recent positions for shake patterns."""
        if len(self.positions) < 3:
            return False
            
        # Calculate horizontal movement direction changes
        direction_changes = 0
        total_distance = 0
        
        for i in range(1, len(self.positions)):
            prev_pos = self.positions[i-1]
            curr_pos = self.positions[i]
            
            # Calculate horizontal movement
            dx = curr_pos[0] - prev_pos[0]
            total_distance += abs(dx)
            
            # Determine direction (only care about significant movement)
            if abs(dx) > 5:  # Minimum movement threshold
                current_direction = 1 if dx > 0 else -1
                
                if self.last_direction is not None and current_direction != self.last_direction:
                    direction_changes += 1
                    
                self.last_direction = current_direction
        
        # Check if we have enough rapid direction changes and sufficient distance
        if direction_changes >= self.min_direction_changes and total_distance > self.shake_threshold:
            self._trigger_shake()
            return True
            
        return False
        
    def _trigger_shake(self):
        """Trigger a shake event and set cooldown."""
        self.positions.clear()
        self.direction_changes = 0
        self.last_direction = None
        self.shake_cooldown = 15  # Prevent rapid re-triggering (about 0.5 seconds at 30fps)
        
    def handle_pygame_event(self, event):
        """Handle pygame events for shake detection."""
        shake_detected = False
        
        # Handle mouse movement
        if event.type == pygame.MOUSEMOTION:
            shake_detected = self.add_mouse_position(event.pos)
            
        # Handle touch events (if available)
        elif hasattr(pygame, 'FINGERMOTION') and event.type == pygame.FINGERMOTION:
            # Convert normalized touch coordinates to screen coordinates
            touch_x = int(event.x * runtime_globals.SCREEN_WIDTH)
            touch_y = int(event.y * runtime_globals.SCREEN_HEIGHT)
            shake_detected = self.add_mouse_position((touch_x, touch_y))
            
        return shake_detected


class ShakePunch:
    """Minigame for shake training punch mechanics with mouse/touch shake detection."""
    
    def __init__(self, ui_manager, pets):
        self.ui_manager = ui_manager
        self.pets = pets
        self.strength = 0
        self.bar_level = 20
        self.bar_timer = 0
        self.phase = "punch"
        
        # Cache for performance
        self._charge_rect_cache = {}
        
        # Shake detection for mouse/touch fallback
        self.shake_detector = ShakeDetector()
        self.mouse_tracking_enabled = True
        self.last_mouse_pos = (0, 0)
        
        # Load bag sprites
        SPRITE_SETS = [
            (constants.BAG1_PATH, constants.BAG2_PATH),
            (constants.ROCK1_PATH, constants.ROCK2_PATH),
            (constants.TREE1_PATH, constants.TREE2_PATH),
            (constants.BRICK1_PATH, constants.BRICK2_PATH),
        ]
        
        selected_sprites = random.choice(SPRITE_SETS)
        from models.game_module import sprite_load
        self.bag1 = sprite_load(selected_sprites[0], size=(60 * runtime_globals.UI_SCALE, 120 * runtime_globals.UI_SCALE))
        self.bag2 = sprite_load(selected_sprites[1], size=(60 * runtime_globals.UI_SCALE, 120 * runtime_globals.UI_SCALE))
    
    def set_phase(self, phase):
        """Set the current minigame phase."""
        self.phase = phase
        if phase == "punch":
            self.bar_timer = pygame.time.get_ticks()
    
    def get_strength(self):
        """Get current strength level."""
        return self.strength
    
    def reset_strength(self):
        """Reset strength to 0."""
        self.strength = 0
    
    def is_time_up(self):
        """Check if the punch time limit has been reached."""
        return pygame.time.get_ticks() - self.bar_timer > combat_constants.PUNCH_HOLD_TIME_MS
    
    def handle_event(self, event):
        """Handle input events for strength building."""
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        
        event_type, event_data = event
        
        if self.phase == "punch" and event_type in ("Y", "SHAKE"):
            runtime_globals.game_sound.play("menu")
            self.strength = min(self.strength + 1, self.bar_level)
            return True
        return False
    
    def update(self):
        """Update the minigame state each frame."""
        self.shake_detector.update()
        
        # Detect shake from mouse/touch motion and generate SHAKE events
        if self.phase == "punch":
            mouse_pos = pygame.mouse.get_pos()
            if mouse_pos != getattr(self, '_last_mouse_pos', None):
                # Directly feed mouse position to shake detector
                shake_detected = self.shake_detector.add_mouse_position(mouse_pos)
                if shake_detected:
                    # Generate synthetic SHAKE tuple event
                    shake_event = ("SHAKE", None)
                    self.handle_event(shake_event)
                self._last_mouse_pos = mouse_pos
    
    def draw(self, surface):
        """Draw the punch minigame interface."""
        if self.phase != "punch":
            return
        
        # Determine color based on strength
        if self.strength < 10:
            color = (220, 40, 40)      # Red
        elif self.strength < 15:
            color = (255, 140, 0)      # Orange
        elif self.strength < 20:
            color = (255, 220, 0)      # Yellow
        else:
            color = (40, 220, 40)      # Green

        # Use pet width for rectangle width
        if self.pets:
            pet_sprite = self.pets[0].get_sprite(PetFrame.IDLE1.value)
            rect_width = pet_sprite.get_width()
        else:
            rect_width = int(50 * runtime_globals.UI_SCALE)
        rect_height = runtime_globals.SCREEN_HEIGHT
        screen_w = runtime_globals.SCREEN_WIDTH
        screen_h = runtime_globals.SCREEN_HEIGHT

        cache_key = (color, rect_width, rect_height, screen_w, screen_h)
        if cache_key not in self._charge_rect_cache:
            left_rect_surf = pygame.Surface((rect_width, rect_height))
            left_rect_surf.fill(color)
            right_rect_surf = pygame.Surface((rect_width, rect_height))
            right_rect_surf.fill(color)
            bg_rect_surf = pygame.Surface((screen_w - 2 * rect_width, rect_height))
            bg_rect_surf.fill((0, 0, 0))
            self._charge_rect_cache[cache_key] = (left_rect_surf, right_rect_surf, bg_rect_surf)
        else:
            left_rect_surf, right_rect_surf, bg_rect_surf = self._charge_rect_cache[cache_key]

        # Draw black background in the center
        from utils.pygame_utils import blit_with_cache
        blit_with_cache(surface, bg_rect_surf, (rect_width, 0))
        # Draw colored rectangles on left and right
        blit_with_cache(surface, left_rect_surf, (0, 0))
        blit_with_cache(surface, right_rect_surf, (screen_w - rect_width, 0))

        # --- Draw timer above "PUNCH" ---
        max_ms = combat_constants.PUNCH_HOLD_TIME_MS
        elapsed_ms = pygame.time.get_ticks() - self.bar_timer
        remaining_ms = max(0, max_ms - elapsed_ms)
        remaining_sec = int(remaining_ms / 1000) + (1 if remaining_ms % 1000 > 0 else 0)

        # Use UI manager's standard text font for timer
        from utils.asset_utils import font_load
        timer_font_size = self.ui_manager.get_text_font_size()
        timer_font = font_load(TITLE_FONT, timer_font_size)
        timer_text = timer_font.render(str(remaining_sec), True, (255, 255, 255))
        timer_x = (screen_w - timer_text.get_width()) // 2
        # Place timer above "PUNCH" with a little spacing
        timer_y = screen_h // 2 - int(60 * runtime_globals.UI_SCALE) - timer_text.get_height() - int(10 * runtime_globals.UI_SCALE)
        blit_with_shadow(surface, timer_text, (timer_x, timer_y))

        # Draw "PUNCH" text centered using UI manager's title font
        punch_font_size = self.ui_manager.get_title_font_size()
        punch_font = font_load(TITLE_FONT, punch_font_size)
        punch_text = punch_font.render("PUNCH", True, (255, 255, 255))
        punch_x = (screen_w - punch_text.get_width()) // 2
        punch_y = screen_h // 2 - int(60 * runtime_globals.UI_SCALE)
        blit_with_shadow(surface, punch_text, (punch_x, punch_y))

        # Draw strength number centered below "PUNCH" using UI manager's title font (larger)
        from utils.asset_utils import font_load
        strength_font_size = int(self.ui_manager.get_title_font_size() * 1.5)  # Make it 50% larger than title
        strength_font = font_load(TITLE_FONT, strength_font_size)
        strength_text = strength_font.render(str(self.strength), True, (255, 255, 255))
        strength_x = (screen_w - strength_text.get_width()) // 2
        strength_y = punch_y + punch_text.get_height() + int(10 * runtime_globals.UI_SCALE)
        blit_with_shadow(surface, strength_text, (strength_x, strength_y))

        # Draw pets spread on the colored rectangles, no scaling
        total = len(self.pets)
        if total > 0:
            left_count = total // 2
            right_count = total - left_count
            # Vertical spacing for pets
            left_spacing = rect_height // max(left_count, 1)
            right_spacing = rect_height // max(right_count, 1)
            
            # Use frame counter from outside for animation (we'll get it from parent)
            frame_counter = pygame.time.get_ticks() // 16  # Approximate frame counter
            
            # Draw left side pets
            for i in range(left_count):
                pet = self.pets[i]
                anim_toggle = (frame_counter + i * 5) // (15 * constants.FRAME_RATE / 30) % 2
                frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.ANGRY.value
                sprite = pet.get_sprite(frame_id)
                x = (rect_width - sprite.get_width()) // 2
                y = i * left_spacing + (left_spacing - sprite.get_height()) // 2
                blit_with_cache(surface, sprite, (x, y))
            # Draw right side pets
            for i in range(right_count):
                pet = self.pets[left_count + i]
                anim_toggle = (frame_counter + (left_count + i) * 5) // (15 * constants.FRAME_RATE / 30) % 2
                frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.ANGRY.value
                sprite = pet.get_sprite(frame_id)
                x = screen_w - rect_width + (rect_width - sprite.get_width()) // 2
                y = i * right_spacing + (right_spacing - sprite.get_height()) // 2
                blit_with_cache(surface, sprite, (x, y))
"""
Tutorial Sprite Component
Displays and animates sprites for the tutorial.
"""

import pygame
from core import game_globals, runtime_globals
from core.utils.asset_utils import image_load


class TutorialSprite:
    """
    Sprite display for tutorial animations.
    Supports positioning, scaling, animation, and movement.
    """
    
    STATE_HIDDEN = 0
    STATE_VISIBLE = 1
    STATE_MOVING = 2
    STATE_FADE_IN = 3
    STATE_FADE_OUT = 4
    
    def __init__(self):
        """Initialize the tutorial sprite."""
        self.state = self.STATE_HIDDEN
        self.sprite = None
        self.sprite_path = None
        self.base_x = 0  # Base UI coordinates
        self.base_y = 0
        self.alpha = 255
        
        # Movement animation
        self.target_x = 0
        self.target_y = 0
        self.move_speed = 2  # Pixels per frame in base coords
        self.on_move_complete = None
        
        # UI scaling
        self.ui_scale = runtime_globals.UI_SCALE
        
        # Sprite cache
        self.sprites = {}
        
    def show(self, path: str, x: int, y: int, scale: float = 1.0, anchor: str = "topleft"):
        """
        Show a sprite at the specified position.
        
        Args:
            path: Path to sprite image
            x, y: Position in base UI coordinates (240x240)
            scale: Additional scale factor
            anchor: Positioning anchor ("topleft", "center", "bottomcenter")
        """
        self.sprite_path = path
        self.sprite = self._load_sprite(path, scale)
        
        if self.sprite:
            # Adjust position based on anchor
            sprite_w = self.sprite.get_width() / self.ui_scale
            sprite_h = self.sprite.get_height() / self.ui_scale
            
            if anchor == "center":
                self.base_x = x - sprite_w / 2
                self.base_y = y - sprite_h / 2
            elif anchor == "bottomcenter":
                self.base_x = x - sprite_w / 2
                self.base_y = y - sprite_h
            elif anchor == "bottomleft":
                self.base_x = x
                self.base_y = y - sprite_h
            else:  # topleft
                self.base_x = x
                self.base_y = y
                
            self.state = self.STATE_VISIBLE
            self.alpha = 255
    
    def show_at_bottom_aligned(self, path: str, center_x: int, bottom_y: int, scale: float = 1.0):
        """
        Show sprite with bottom edge aligned to specified y position.
        
        Args:
            path: Path to sprite image
            center_x: Center X position in base UI coordinates
            bottom_y: Bottom Y position in base UI coordinates
            scale: Additional scale factor
        """
        self.show(path, center_x, bottom_y, scale, anchor="bottomcenter")
    
    def _load_sprite(self, path: str, scale: float = 1.0) -> pygame.Surface:
        """Load and scale a sprite."""
        cache_key = f"{path}_{scale}"
        if cache_key in self.sprites:
            return self.sprites[cache_key]
            
        try:
            sprite = image_load(path)
            if sprite:
                # Apply UI scale and additional scale
                new_w = int(sprite.get_width() * self.ui_scale * scale)
                new_h = int(sprite.get_height() * self.ui_scale * scale)
                sprite = pygame.transform.scale(sprite, (new_w, new_h))
                self.sprites[cache_key] = sprite
                return sprite
        except Exception as e:
            runtime_globals.game_console.log(f"[TutorialSprite] Failed to load {path}: {e}")
            
        return None
    
    def hide(self):
        """Hide the sprite."""
        self.state = self.STATE_HIDDEN
        self.sprite = None
        
    def replace(self, new_path: str, scale: float = 1.0):
        """Replace current sprite with a new one at the same position."""
        if self.state != self.STATE_HIDDEN:
            old_x = self.base_x
            old_y = self.base_y
            self.sprite_path = new_path
            self.sprite = self._load_sprite(new_path, scale)
            # Keep same position
            self.base_x = old_x
            self.base_y = old_y
    
    def move_to(self, target_x: int, target_y: int, speed: float = 2.0, on_complete=None):
        """
        Animate movement to target position.
        
        Args:
            target_x, target_y: Target position in base UI coordinates
            speed: Movement speed in base pixels per frame
            on_complete: Callback when movement completes
        """
        self.target_x = target_x
        self.target_y = target_y
        self.move_speed = speed
        self.on_move_complete = on_complete
        self.state = self.STATE_MOVING
    
    def update(self):
        """Update sprite animation."""
        if self.state == self.STATE_MOVING:
            dx = self.target_x - self.base_x
            dy = self.target_y - self.base_y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance < self.move_speed:
                # Arrived at target
                self.base_x = self.target_x
                self.base_y = self.target_y
                self.state = self.STATE_VISIBLE
                if self.on_move_complete:
                    callback = self.on_move_complete
                    self.on_move_complete = None
                    callback()
            else:
                # Move towards target
                self.base_x += dx / distance * self.move_speed
                self.base_y += dy / distance * self.move_speed
    
    def draw(self, surface: pygame.Surface):
        """Draw the sprite."""
        if self.state == self.STATE_HIDDEN or self.sprite is None:
            return
            
        # Calculate UI offset (center UI on screen)
        ui_offset_x = (runtime_globals.SCREEN_WIDTH - int(240 * self.ui_scale)) // 2
        ui_offset_y = (runtime_globals.SCREEN_HEIGHT - int(240 * self.ui_scale)) // 2
        
        # Scale position
        screen_x = ui_offset_x + int(self.base_x * self.ui_scale)
        screen_y = ui_offset_y + int(self.base_y * self.ui_scale)
        
        # Draw sprite
        if self.alpha < 255:
            alpha_sprite = self.sprite.copy()
            alpha_sprite.set_alpha(self.alpha)
            surface.blit(alpha_sprite, (screen_x, screen_y))
        else:
            surface.blit(self.sprite, (screen_x, screen_y))
    
    def is_visible(self) -> bool:
        """Check if sprite is currently visible."""
        return self.state != self.STATE_HIDDEN
    
    def get_rect(self) -> pygame.Rect:
        """Get sprite rectangle in base UI coordinates."""
        if self.sprite:
            w = self.sprite.get_width() / self.ui_scale
            h = self.sprite.get_height() / self.ui_scale
            return pygame.Rect(self.base_x, self.base_y, w, h)
        return pygame.Rect(0, 0, 0, 0)

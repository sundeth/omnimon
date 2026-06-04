"""
Sleep Scene Background - Animated background that moves based on Sleep/Wake mode
"""
import pygame
from utils.pygame_utils import blit_with_cache
from ui.components.component import UIComponent


class SleepSceneBackground(UIComponent):
    def __init__(self, x, y, width, height):
        """
        Initialize the sleep scene background with animated positioning.
        
        Args:
            x, y: Position of the component
            width, height: Size to cover (should cover full UI area - 240x240 at 1x scale)
        """
        super().__init__(x, y, width, height)
        
        self.background_sprite = None
        self.skyline_sprite = None
        self.current_mode = "sleep"  # "sleep" or "wake"
        self.background_y_offset = 0  # Will be animated based on mode
        
        # Position offsets for background sprite (in base scale)
        self.sleep_offset = 0    # y=0 for sleep mode
        self.wake_offset = -223  # y=-223 for wake mode
        
    def on_manager_set(self):
        """Called when UI manager is set - load scaled assets"""
        if not self.manager:
            return

        self.background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Background", "")
        self.skyline_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Skyline", "")
        
        # Force redraw
        self.needs_redraw = True
        
    def set_mode(self, mode):
        """
        Set the background mode (sleep or wake).
        
        Args:
            mode: "sleep" or "wake"
        """
        if mode != self.current_mode:
            self.current_mode = mode
            
            # Update background offset based on mode
            if mode == "sleep":
                self.background_y_offset = self.sleep_offset
            else:  # wake
                self.background_y_offset = self.wake_offset
                
            self.needs_redraw = True
            
    def render(self):
        """Render the animated background system"""
        # Reuse a cached render surface to reduce allocations
        target_size = (self.rect.width, self.rect.height)
        if not hasattr(self, "_render_surface") or self._render_surface is None or self._render_surface.get_size() != target_size:
            self._render_surface = pygame.Surface(target_size, pygame.SRCALPHA)
        surface = self._render_surface
        surface.fill((0, 0, 0, 0))
        
        # Draw background sprite with offset (no additional scaling for position)
        if self.background_sprite:
            # Apply offset directly - the sprite is already the right scale
            background_pos = (0, self.background_y_offset)
            blit_with_cache(surface, self.background_sprite, background_pos)
            
        # Draw skyline on top (should fit perfectly as it's 240x240 at base scale)
        if self.skyline_sprite:
            # Skyline covers the full UI area perfectly
            blit_with_cache(surface, self.skyline_sprite, (0, 0))
            
        return surface
"""
Image Component - Displays an image with optional scaling
"""
import pygame
from ui.components.component import UIComponent
from utils.asset_utils import image_load
from utils.pygame_utils import blit_with_cache


class Image(UIComponent):
    def __init__(self, x, y, width, height, image_path=None, image_surface=None, keep_aspect_ratio=True):
        super().__init__(x, y, width, height)
        self.image_path = image_path
        self.original_surface = image_surface
        self.scaled_surface = None
        self.keep_aspect_ratio = keep_aspect_ratio
        self.focusable = False
        
        # Load image if path is provided
        if self.image_path and not self.original_surface:
            self.load_image()
    
    def load_image(self):
        """Load image from path"""
        if not self.image_path:
            return
            
        self.original_surface = image_load(self.image_path).convert_alpha()
        self.needs_redraw = True

    
    def set_image(self, image_path=None, image_surface=None):
        """Set new image from path or surface"""
        if image_path:
            self.image_path = image_path
            self.original_surface = None
            self.load_image()
        elif image_surface:
            self.original_surface = image_surface
            self.needs_redraw = True
        
        self.scaled_surface = None  # Force rescaling
    
    def on_manager_set(self):
        """Called when UI manager is set"""
        if self.image_path and not self.original_surface:
            self.load_image()
    
    def calculate_scaled_size(self):
        """Calculate the scaled size based on component dimensions and aspect ratio settings"""
        if not self.original_surface:
            return (self.rect.width, self.rect.height)
        
        original_width, original_height = self.original_surface.get_size()
        target_width, target_height = self.rect.width, self.rect.height
        
        if not self.keep_aspect_ratio:
            return (target_width, target_height)
        
        # Calculate scaling to fit within target size while preserving aspect ratio
        scale_x = target_width / original_width
        scale_y = target_height / original_height
        scale = min(scale_x, scale_y)
        
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        
        return (new_width, new_height)
    
    def render(self):
        """Render the image component"""
        # Reuse a cached render surface to avoid per-frame allocations
        target_size = (self.rect.width, self.rect.height)
        if not hasattr(self, "_render_surface") or self._render_surface is None or self._render_surface.get_size() != target_size:
            self._render_surface = pygame.Surface(target_size, pygame.SRCALPHA)
        surface = self._render_surface
        surface.fill((0, 0, 0, 0))
        
        if not self.original_surface:
            # No image to display, fill with transparent
            return surface
        
        # Scale image if needed
        if not self.scaled_surface or self.needs_redraw:
            scaled_size = self.calculate_scaled_size()
            if scaled_size != self.original_surface.get_size():
                self.scaled_surface = pygame.transform.scale(self.original_surface, scaled_size)
            else:
                self.scaled_surface = self.original_surface
        
        # Center the image within the component
        image_width, image_height = self.scaled_surface.get_size()
        x = (self.rect.width - image_width) // 2
        y = (self.rect.height - image_height) // 2
        
        blit_with_cache(surface, self.scaled_surface, (x, y))
        
        # Draw highlight if focused and focusable
        if self.focused and self.focusable:
            colors = self.get_colors()
            highlight_color = colors["highlight"]
            pygame.draw.rect(surface, highlight_color, surface.get_rect(), 2)
        
        return surface
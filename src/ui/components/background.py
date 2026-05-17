"""
Background Component - Provides themed backgrounds with configurable regions
"""
import pygame
from ui.components.component import UIComponent


class Background(UIComponent):
    def __init__(self, width, height, background_type="default"):
        super().__init__(0, 0, width, height)
        self.background_type = background_type
        self.focusable = False  # Background doesn't receive focus
        self.regions = []  # List of (y_start, y_end, color_type) tuples
        self.image = None  # Optional fullscreen image (overrides regions)
        self.image_alpha = 255

    def set_image(self, surface, alpha: int = 255):
        """Set a fullscreen image to render instead of the region fill.

        Pass ``None`` to clear and fall back to region rendering.
        """
        self.image = surface
        self.image_alpha = max(0, min(255, int(alpha)))
        self.needs_redraw = True

    def clear_image(self):
        self.image = None
        self.needs_redraw = True

    def set_regions(self, regions):
        """
        Set background regions. Each region is a tuple of (y_start, y_end, color_type)
        color_type can be: "bg", "black", "dark_bg", "highlight", "fg", etc.
        """
        self.regions = regions
        self.needs_redraw = True
        
    def add_region(self, y_start, y_end, color_type):
        """Add a single region to the background"""
        self.regions.append((y_start, y_end, color_type))
        self.needs_redraw = True
        
    def clear_regions(self):
        """Clear all regions"""
        self.regions = []
        self.needs_redraw = True
        
    def render(self):
        """Render the background at proper scale"""
        # Use screen dimensions for surface
        surface = pygame.Surface((self.rect.width, self.rect.height))
        colors = self.manager.get_theme_colors()

        # If an image override is set, blit it scaled to fill — used by
        # the cosmetics shop to render the selected background preview
        # behind the detail UI.
        if self.image is not None:
            try:
                scaled = pygame.transform.smoothscale(
                    self.image, (self.rect.width, self.rect.height)
                )
                if self.image_alpha < 255:
                    scaled.set_alpha(self.image_alpha)
                surface.blit(scaled, (0, 0))
                return surface
            except Exception:
                # Fall back to region rendering on any scaling failure
                pass

        # Default background color
        surface.fill(colors["bg"])
        
        # Apply regions (regions are in base coordinates, need to scale)
        for y_start, y_end, color_type in self.regions:
            if color_type in colors:
                color = colors[color_type]
            elif color_type == "black":
                # Create a darker version of bg color
                color = colors["black"]
            else:
                color = colors["bg"]  # Fallback

            if isinstance(color_type, tuple) and len(color_type) == 3:
                color = color_type  # Direct RGB value
            
            # Scale region coordinates
            scaled_y_start = self.manager.scale_value(y_start)
            scaled_y_end = self.manager.scale_value(y_end)
            
            # Draw region
            region_rect = pygame.Rect(0, scaled_y_start, self.rect.width, scaled_y_end - scaled_y_start)
            pygame.draw.rect(surface, color, region_rect)
            
        return surface
        
    def update(self):
        """Background doesn't need updates beyond base class"""
        super().update()

"""
Armor Display Component
A single hexagon display for armor evolution, similar to JogressDisplay but simplified.
Shows one pet in a hexagon for armor evolution selection.
"""
import pygame
import math
from ui.components.component import UIComponent
from core import runtime_globals

FRAME_RATE = 30  # Constant for frame-rate independent animation

class ArmorDisplay(UIComponent):
    """Component for displaying a single pet in a hexagon for armor evolution."""
    
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        
        # Pet data
        self.pet = None
        self.pet_theme = "BLUE"  # Default theme for the pet
        
        # Layout settings (base dimensions)
        self.base_hexagon_size = 30  # Base radius of hexagon (good for 80x80 component)
        self.base_border_width = 2
        
        # Current layout (scaled)
        self.hexagon_center = None
        self.needs_layout_update = True
        
        # Animation state
        self.animation_active = False
        self.animation_timer = 0.0
        
        # Colors
        self.default_fill = (40, 40, 40)
        self.default_border = (80, 80, 80)
        
        # Cached sprites
        self.dna_sprite = None
        
    def set_pet(self, pet, theme="BLUE"):
        """Set the pet to display in the hexagon."""
        self.pet = pet
        self.pet_theme = theme
        self.needs_layout_update = True
        runtime_globals.game_console.log(f"[ArmorDisplay] Pet set: {pet.name if pet else 'None'} with theme {theme}")
        
    def clear_pet(self):
        """Clear the displayed pet."""
        self.pet = None
        self.needs_layout_update = True
        
    def get_theme_colors(self, theme_name):
        """Get theme colors for a specific theme"""
        # Import theme colors from ui_constants
        from ui.ui_constants import (
            GREEN_DARK, GREEN, GREEN_LIGHT,
            BLUE_DARK, BLUE, BLUE_LIGHT,
            GRAY_DARK, GRAY, GRAY_LIGHT
        )
        
        if theme_name == "GREEN":
            return {"bg": GREEN_DARK, "fg": GREEN, "highlight": GREEN_LIGHT}
        elif theme_name == "BLUE":  
            return {"bg": BLUE_DARK, "fg": BLUE, "highlight": BLUE_LIGHT}
        elif theme_name == "GRAY":
            return {"bg": GRAY_DARK, "fg": GRAY, "highlight": GRAY_LIGHT}
        else:
            # Default to blue theme
            return {"bg": BLUE_DARK, "fg": BLUE, "highlight": BLUE_LIGHT}
        
    def get_colors(self):
        """Get colors for the current manager theme (UIComponent compatibility)."""
        # Default blue theme colors
        return {"bg": (46, 62, 77), "fg": (82, 163, 204), "highlight": (217, 255, 248)}
        
    def update_layout(self):
        """Update the component layout based on current scaling."""
        # Center the hexagon in the component's surface
        center_x = self.rect.width // 2
        center_y = self.rect.height // 2
        
        self.hexagon_center = (center_x, center_y)
        self.needs_layout_update = False
        
    def update_colors_from_theme(self):
        """Update colors based on current theme."""
        # Use gray theme for default colors
        gray_colors = self.get_theme_colors("GRAY")
        self.default_fill = gray_colors["bg"]
        self.default_border = gray_colors["fg"]
        
    def create_mixed_color(self, color1, color2, ratio):
        """Create a mixed color between two colors based on ratio (0.0 = color1, 1.0 = color2)."""
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        return (r, g, b)
        
    def draw_hexagon(self, surface, center, radius, fill_color, border_color, border_width):
        """Draw a hexagon at the specified center with given radius and colors."""
        # Scale values for screen rendering
        if self.manager:
            scaled_center = (
                self.manager.scale_value(center[0]),
                self.manager.scale_value(center[1])
            )
            scaled_radius = self.manager.scale_value(radius)
            scaled_border_width = self.manager.scale_value(border_width)
        else:
            scaled_center = center
            scaled_radius = radius
            scaled_border_width = border_width
            
        # Calculate hexagon points
        points = []
        for i in range(6):
            angle = (math.pi / 3 * i) + (math.pi / 6)  # Start from top-right corner
            x = scaled_center[0] + scaled_radius * math.cos(angle)
            y = scaled_center[1] + scaled_radius * math.sin(angle)
            points.append((int(x), int(y)))
        
        # Draw hexagon
        if len(points) >= 3:
            pygame.draw.polygon(surface, fill_color, points)
            if border_color and scaled_border_width > 0:
                pygame.draw.polygon(surface, border_color, points, scaled_border_width)
                
    def draw_pet_sprite(self, surface, pet, center, radius):
        """Draw a pet sprite centered in the hexagon."""
        if not pet:
            return
            
        # Scale center and radius for screen rendering
        if self.manager:
            scaled_center = (
                self.manager.scale_value(center[0]),
                self.manager.scale_value(center[1])
            )
            scaled_radius = self.manager.scale_value(radius)
        else:
            scaled_center = center
            scaled_radius = radius
            
        # Get pet sprite from runtime_globals (already loaded)
        # Use IDLE1 frame (index 0) for display
        sprite = pet.get_sprite(0)
            
        # Position sprite in hexagon center
        sprite_rect = sprite.get_rect()
        sprite_rect.center = scaled_center
        
        # Scale sprite to fit in hexagon (leave some margin)
        max_size = int(scaled_radius * 1.5)  # Allow sprite to be slightly larger than radius
        if sprite_rect.width > max_size or sprite_rect.height > max_size:
            # Scale down to fit
            scale_factor = min(max_size / sprite_rect.width, max_size / sprite_rect.height)
            new_width = int(sprite_rect.width * scale_factor)
            new_height = int(sprite_rect.height * scale_factor)
            sprite = pygame.transform.scale(sprite, (new_width, new_height))
            sprite_rect = sprite.get_rect()
            sprite_rect.center = scaled_center
            
        from utils.pygame_utils import blit_with_cache
        blit_with_cache(surface, sprite, sprite_rect.topleft)
        
    def load_dna_sprite(self):
        """Load the Battle DNA sprite (cached)"""
        if self.dna_sprite is not None:
            return self.dna_sprite
            
        if not self.manager:
            return None
            
        self.dna_sprite = self.manager.load_sprite_integer_scaling("Battle", "DNA", "")
        return self.dna_sprite
        
    def update(self):
        """Update component state"""
        if self.needs_layout_update:
            self.update_layout()
            
        # Update colors if theme changed
        if self.manager:
            self.update_colors_from_theme()
            
        # Update animation
        if self.animation_active:
            # Calculate time delta (assume 1/FRAME_RATE seconds per frame)
            dt = 1.0 / FRAME_RATE
            self.animation_timer += dt
            
    def render(self):
        """Render the component using the render-based pattern"""
        # Reuse a cached render surface to avoid per-frame allocations
        target_size = (self.rect.width, self.rect.height)
        if not hasattr(self, "_render_surface") or self._render_surface is None or self._render_surface.get_size() != target_size:
            self._render_surface = pygame.Surface(target_size, pygame.SRCALPHA)
        surface = self._render_surface
        surface.fill((0, 0, 0, 0))
        
        if not self.hexagon_center:
            return surface
        
        # Draw hexagon
        if self.pet is not None:
            # Pet is present - use pet theme colors
            colors = self.get_theme_colors(self.pet_theme)
            fill_color = colors["bg"]
            border_color = colors["fg"]
        else:
            # Empty slot - use default gray colors
            fill_color = self.default_fill
            border_color = self.default_border
            
        # Draw hexagon
        self.draw_hexagon(
            surface, self.hexagon_center, self.base_hexagon_size, 
            fill_color, border_color, self.base_border_width
        )
        
        # Draw pet sprite if present
        if self.pet is not None:
            self.draw_pet_sprite(surface, self.pet, self.hexagon_center, self.base_hexagon_size)
        
        return surface
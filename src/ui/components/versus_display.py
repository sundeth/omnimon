"""
Versus Display Component - Shows 2 hexagons for versus battle interface
"""
import pygame
import math
from ui.components.component import UIComponent
from core import runtime_globals
from models.animation import PetFrame
from ui.ui_constants import *


class VersusDisplay(UIComponent):
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        
        # Pet data for the two slots
        self.slot_pets = [None, None]  # [slot1_pet, slot2_pet]
        self.slot_themes = ["BLUE", "GREEN"]  # Fixed themes for each slot (slot0=BLUE, slot1=GREEN)
        
        # Visual state
        self.show_versus_sprite = False  # Whether to show the VersusSmall sprite
        
        # Base visual settings (will be scaled by manager)
        self.base_hexagon_size = 32  # Base hexagon radius
        self.base_spacing = 12  # Base horizontal spacing between hexagons
        self.base_border_width = 2  # Base border width
        
        # Scaled visual settings (set in on_manager_set)
        self.hexagon_size = self.base_hexagon_size
        self.spacing = self.base_spacing
        self.border_width = self.base_border_width
        
        # Layout positions (calculated in update_layout)
        self.left_hexagon_center = None
        self.right_hexagon_center = None
        self.versus_sprite_center = None
        
        # Color settings
        self.default_fill = None
        self.default_border = None
        self.needs_layout_update = True
        
        # Sprite cache
        self.versus_small_sprite = None  # Cache for Battle_VersusSmall sprite
        
        # Cache
        self.cached_surface = None
        
    def set_pet_slot(self, slot_index, pet):
        """Set a pet in the specified slot (0 or 1)"""
        if 0 <= slot_index <= 1:
            old_pet = self.slot_pets[slot_index]
            self.slot_pets[slot_index] = pet
            
            # If pet changed, update display and redraw
            if old_pet != pet:
                self.update_versus_display()
                self.needs_redraw = True
                
    def clear_slot(self, slot_index):
        """Clear the specified slot"""
        self.set_pet_slot(slot_index, None)
        
    def clear_all_slots(self):
        """Clear both slots"""
        self.slot_pets = [None, None]
        self.show_versus_sprite = False
        self.needs_redraw = True
        
    def get_slot_pet(self, slot_index):
        """Get the pet in the specified slot"""
        if 0 <= slot_index <= 1:
            return self.slot_pets[slot_index]
        return None
        
    def update_versus_display(self):
        """Update the versus display state based on current pets"""
        # Show versus sprite if both pets are set
        self.show_versus_sprite = (self.slot_pets[0] is not None and self.slot_pets[1] is not None)
        
        # Load the VersusSmall sprite if needed
        if self.show_versus_sprite and not self.versus_small_sprite:
            self.load_versus_sprite()
    
    def load_versus_sprite(self):
        """Load the Battle_VersusSmall sprite"""
        if self.manager:
            try:
                # Use the UI manager's sprite loading system
                self.versus_small_sprite = self.manager.load_sprite_integer_scaling("Battle", "VersusSmall", "")
                if self.versus_small_sprite:
                    runtime_globals.game_console.log("[VersusDisplay] Successfully loaded VersusSmall sprite")
                else:
                    runtime_globals.game_console.log("[VersusDisplay] Warning: Failed to load VersusSmall sprite")
            except Exception as e:
                runtime_globals.game_console.log(f"[VersusDisplay] Error loading VersusSmall sprite: {e}")
    
    def get_theme_colors(self, theme_name):
        """Get theme colors for a specific theme"""
        if not self.manager:
            return {"bg": (40, 40, 80), "fg": (255, 255, 255), "highlight": (255, 255, 0)}
            
        # Handle custom theme colors
        if theme_name == "GREEN":
            return {"bg": GREEN_DARK, "fg": GREEN, "highlight": GREEN_LIGHT}
        elif theme_name == "BLUE":  
            return {"bg": BLUE_DARK, "fg": BLUE, "highlight": BLUE_LIGHT}
        
        # Fallback to manager theme
        return self.manager.get_theme_colors()
    
    def update_colors_from_theme(self):
        """Update colors based on current UI theme"""
        if self.manager:
            theme_colors = self.manager.get_theme_colors()
            new_fill = theme_colors.get("bg", (40, 40, 80))
            new_border = theme_colors.get("fg", (255, 255, 255))
            
            # Only mark redraw if colors actually changed
            if self.default_fill != new_fill or self.default_border != new_border:
                self.default_fill = new_fill
                self.default_border = new_border
                self.needs_redraw = True
            
    def on_manager_set(self):
        """Called when component is added to UI manager"""
        # Scale visual settings based on UI scale
        if self.manager:
            self.hexagon_size = self.manager.scale_value(self.base_hexagon_size)
            self.spacing = self.manager.scale_value(self.base_spacing)
            self.border_width = self.manager.scale_value(self.base_border_width)
        
        self.update_colors_from_theme()
        self.needs_layout_update = True
        
    def update(self):
        """Update component state"""
        if self.needs_layout_update:
            self.update_layout()
            
        # Update colors if theme changed
        if self.manager:
            self.update_colors_from_theme()
            
    def update_layout(self):
        """Calculate positions for the two hexagons in base coordinates"""
        if not hasattr(self, 'base_rect') or self.base_rect is None:
            return
            
        # Work in base coordinates - the UI manager will handle scaling
        available_width = self.base_rect.width
        available_height = self.base_rect.height
        
        # Calculate optimal hexagon size to fit horizontally
        # Available width for 2 hexagons + spacing: width = 2 * (2 * radius) + spacing
        max_radius_horizontal = (available_width - self.base_spacing) // 4  # 4 = 2 hexagons * 2 (diameter = 2*radius)
        
        # Calculate maximum hexagon size that fits vertically  
        # We only have one row of hexagons
        max_radius_vertical = available_height // 2  # diameter = 2*radius
        
        # Use the smaller of the two to ensure hexagons fit in both dimensions
        optimal_radius = min(max_radius_horizontal, max_radius_vertical, self.base_hexagon_size)
        optimal_radius = max(optimal_radius, 8)  # Minimum radius of 8 pixels
        
        # Update the hexagon size to the optimal size
        self.base_hexagon_size = optimal_radius
        
        # Center hexagons vertically
        hexagon_y = available_height // 2
        
        # Calculate horizontal positions for hexagons
        # Total width of both hexagons plus spacing
        total_width = (optimal_radius * 2 * 2) + self.base_spacing  # diameter * 2 + spacing
        start_x = (available_width - total_width) // 2
        
        left_x = start_x + optimal_radius  # Center of left hexagon
        right_x = left_x + (optimal_radius * 2) + self.base_spacing  # Center of right hexagon
        
        # Store positions in base coordinates
        self.left_hexagon_center = (left_x, hexagon_y)
        self.right_hexagon_center = (right_x, hexagon_y)
        
        # Versus sprite position (center between hexagons)
        sprite_x = (left_x + right_x) // 2
        sprite_y = hexagon_y
        self.versus_sprite_center = (sprite_x, sprite_y)
        
        self.needs_layout_update = False
        self.needs_redraw = True
    
    def render(self):
        """Render the versus display"""
        # Create surface for the component
        # Reuse cached surface if available
        if hasattr(self, 'cached_surface') and self.cached_surface and self.cached_surface.get_size() == (self.rect.width, self.rect.height):
            surface = self.cached_surface
        else:
            surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
            self.cached_surface = surface
        
        if not self.left_hexagon_center or not self.right_hexagon_center:
            return surface
            
        # Get hexagon positions and scaled size
        scaled_radius = self.manager.scale_value(self.base_hexagon_size) if self.manager else self.base_hexagon_size
        scaled_border_width = self.manager.scale_value(self.base_border_width) if self.manager else self.base_border_width
        
        # Draw hexagons with swapped display order as requested:
        # - first selected pet (slot 0) is drawn on the RIGHT
        # - second selected pet (slot 1) is drawn on the LEFT
        if self.left_hexagon_center:
            # draw slot 1 at the left center
            self.draw_hexagon(surface, 1, self.left_hexagon_center, scaled_radius, scaled_border_width)

        if self.right_hexagon_center:
            # draw slot 0 at the right center
            self.draw_hexagon(surface, 0, self.right_hexagon_center, scaled_radius, scaled_border_width)
            
        # Draw versus sprite if both pets are present
        if self.show_versus_sprite and self.versus_small_sprite and self.versus_sprite_center:
            self.draw_versus_sprite(surface)
            
        return surface
    
    def draw_hexagon(self, surface, slot_index, center, radius, border_width):
        """Draw a hexagon for the specified slot"""
        # Check if there's a pet in this slot
        pet = self.slot_pets[slot_index]
        
        if pet is not None:
            # Pet present: use theme colors for this slot
            theme_name = self.slot_themes[slot_index]
            theme_colors = self.get_theme_colors(theme_name)
            fill_color = theme_colors.get("bg", self.default_fill)
            border_color = theme_colors.get("fg", self.default_border)
        else:
            # No pet: use grey colors
            fill_color = self.default_fill or (40, 40, 80)  # Grey background
            border_color = self.default_border or (128, 128, 128)  # Grey border
        
        # Convert base center to scaled center coordinates  
        scaled_center = (
            self.manager.scale_value(center[0]) if self.manager else center[0],
            self.manager.scale_value(center[1]) if self.manager else center[1]
        )
        
        # Calculate hexagon points
        points = []
        for i in range(6):
            angle = (math.pi / 3 * i) + (math.pi / 6)  # 60 degrees * i + 30 degrees rotation
            x = scaled_center[0] + radius * math.cos(angle)
            y = scaled_center[1] + radius * math.sin(angle)
            points.append((int(x), int(y)))
        
        # Draw filled hexagon
        if len(points) >= 3:
            pygame.draw.polygon(surface, fill_color, points)
            if border_color:
                pygame.draw.polygon(surface, border_color, points, border_width)

        # Draw pet sprite if available
        if pet and hasattr(pet, 'get_sprite'):
            try:
                sprite = pet.get_sprite(PetFrame.NAP2.value if pet.state == "nap" else PetFrame.IDLE1.value)
                if sprite:
                    sprite_rect = sprite.get_rect()
                    
                    # Calculate sprite padding (leave some space around sprite in hexagon)
                    sprite_padding = max(4, radius // 8)
                    available_radius = radius - sprite_padding
                    
                    # Scale sprite to fit in hexagon with padding
                    sprite_scale_factor = min(
                        (available_radius * 2) / sprite_rect.width,
                        (available_radius * 2) / sprite_rect.height
                    )
                    
                    if sprite_scale_factor < 1.0:
                        # Scale down the sprite
                        new_width = max(1, int(sprite_rect.width * sprite_scale_factor))
                        new_height = max(1, int(sprite_rect.height * sprite_scale_factor))
                        sprite = pygame.transform.scale(sprite, (new_width, new_height))
                        sprite_rect = sprite.get_rect()
                        
                    # Center sprite in hexagon
                    sprite_rect.center = scaled_center
                    from utils.pygame_utils import blit_with_cache
                    blit_with_cache(surface, sprite, sprite_rect.topleft)
            except Exception as e:
                # Fallback if sprite loading fails
                runtime_globals.game_console.log(f"[VersusDisplay] Failed to load sprite for pet in slot {slot_index}: {e}")
                pass
    
    def draw_versus_sprite(self, surface):
        """Draw the VersusSmall sprite between the hexagons"""
        if not self.versus_small_sprite or not self.versus_sprite_center:
            return
            
        # Convert base center to scaled center coordinates
        scaled_center = (
            self.manager.scale_value(self.versus_sprite_center[0]) if self.manager else self.versus_sprite_center[0],
            self.manager.scale_value(self.versus_sprite_center[1]) if self.manager else self.versus_sprite_center[1]
        )
        
        # Center the sprite
        sprite_rect = self.versus_small_sprite.get_rect()
        sprite_rect.center = scaled_center
        from utils.pygame_utils import blit_with_cache
        blit_with_cache(surface, self.versus_small_sprite, sprite_rect.topleft)
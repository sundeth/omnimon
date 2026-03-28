"""
Jogress Display Component - Shows hexagonal layout for Jogress fusion interface
"""
import pygame
import math
from ui.components.component import UIComponent
from core import runtime_globals
from utils.pygame_utils import blit_with_cache
from models.animation import PetFrame
from core.constants import FRAME_RATE


class JogressDisplay(UIComponent):
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        
        # Pet data for the two slots
        self.slot_pets = [None, None]  # [slot1_pet, slot2_pet]
        self.slot_themes = ["GREEN", "BLUE"]  # Fixed themes for each slot
        
        # Compatibility validation callback
        self.compatibility_callback = None  # Function to check if pets are compatible
        
        # Visual state
        self.is_compatible = False
        self.show_result = False  # Whether to show the result hexagon sprite
        self.evolution_info = None  # Store evolution info including dual evolution flag
        self.hide_pet_sprites = False  # Flag to hide pet sprites during animation
        
        # Animation state
        self.animation_active = False
        self.animation_timer = 0.0  # Time in seconds
        self.animation_duration = 2.0  # Total animation duration in seconds
        self.dna_reveal_progress = 0.0  # 0.0 to 1.0, how much of DNA to show
        self.hexagon_revealed = False  # Whether top hexagon animation has started
        
        # Base visual settings (will be scaled by manager)
        self.base_hexagon_size = 32  # Base hexagon radius
        self.base_spacing = 6  # Base horizontal spacing between hexagons (reduced from 18)
        self.base_border_width = 2  # Base border width
        
        # Scaled visual settings (set in on_manager_set)
        self.hexagon_size = self.base_hexagon_size
        self.spacing = self.base_spacing
        self.border_width = self.base_border_width
        
        # Layout positions (calculated in update_layout)
        self.top_hexagon_center = None
        self.bottom_left_center = None
        self.bottom_right_center = None
        
        # Color settings
        self.default_fill = None
        self.default_border = None
        self.needs_layout_update = True
        
        # Sprite cache
        self.jogress_result_sprite = None
        self.dna_sprite = None  # Cache for Battle_DNA sprite
        self.jogress_ready_sprite = None  # Cache for Battle_JogressReady sprite
        
        # Cache
        self.cached_surface = None
        
        # Don't setup initial layout here - wait for manager to be set
        # self.update_layout()
        
    def set_compatibility_callback(self, callback):
        """Set the callback function to validate pet compatibility"""
        self.compatibility_callback = callback
        
    def set_pet_slot(self, slot_index, pet):
        """Set a pet in the specified slot (0 or 1)"""
        if 0 <= slot_index <= 1:
            old_pet = self.slot_pets[slot_index]
            self.slot_pets[slot_index] = pet
            
            # If pet changed, update compatibility and redraw
            if old_pet != pet:
                self.update_compatibility()
                self.needs_redraw = True
                
    def clear_slot(self, slot_index):
        """Clear the specified slot"""
        self.set_pet_slot(slot_index, None)
        
    def clear_all_slots(self):
        """Clear both slots"""
        self.slot_pets = [None, None]
        self.is_compatible = False
        self.show_result = False
        self.evolution_info = None
        self.needs_redraw = True
        
    def get_slot_pet(self, slot_index):
        """Get the pet in the specified slot"""
        if 0 <= slot_index <= 1:
            return self.slot_pets[slot_index]
        return None
        
    def update_compatibility(self):
        """Check if current pets are compatible and update result display"""
        old_compatible = self.is_compatible
        old_evolution_info = self.evolution_info
        
        # Check if both slots are filled
        if self.slot_pets[0] is not None and self.slot_pets[1] is not None:
            # Call compatibility validation if available
            if self.compatibility_callback:
                self.is_compatible = self.compatibility_callback(self.slot_pets[0], self.slot_pets[1])
                
                # If there's an evolution info callback, get detailed evolution info
                if hasattr(self.compatibility_callback, '__self__') and hasattr(self.compatibility_callback.__self__, 'get_jogress_evolution_info'):
                    self.evolution_info = self.compatibility_callback.__self__.get_jogress_evolution_info(self.slot_pets[0], self.slot_pets[1])
                else:
                    self.evolution_info = None
            else:
                # Default: assume compatible if both slots filled
                self.is_compatible = True
                self.evolution_info = None
                
            # Start animation if we just became compatible or evolution info changed
            if self.is_compatible and (not old_compatible or self.evolution_info != old_evolution_info):
                self.start_jogress_animation()
            elif not self.is_compatible:
                self.reset_animation()
                
        else:
            # Not enough pets for compatibility check
            self.is_compatible = False
            self.show_result = False
            self.evolution_info = None
            self.reset_animation()
            
    def start_jogress_animation(self):
        """Start the Jogress compatibility animation"""
        self.animation_active = True
        self.animation_timer = 0.0
        self.dna_reveal_progress = 0.0
        self.hexagon_revealed = False
        self.show_result = False  # Don't show result until animation completes
        self.needs_redraw = True
        runtime_globals.game_console.log("[JogressDisplay] Starting Jogress animation")
        
    def reset_animation(self):
        """Reset animation state"""
        self.animation_active = False
        self.animation_timer = 0.0
        self.dna_reveal_progress = 0.0
        self.hexagon_revealed = False
        self.show_result = False
        self.evolution_info = None
        self.needs_redraw = True
            
    def get_theme_colors(self, theme_name):
        """Get theme colors for a specific theme"""
        if not self.manager:
            return {"bg": (128, 128, 128), "fg": (160, 160, 160), "highlight": (192, 192, 192)}
            
        # Import theme colors from ui_constants
        from ui.ui_constants import (
            GREEN_DARK, GREEN, GREEN_LIGHT,
            BLUE_DARK, BLUE, BLUE_LIGHT,
            GRAY_DARK, GRAY, GRAY_LIGHT,
            BLACK, GREY
        )
        
        if theme_name == "GREEN":
            return {"bg": GREEN_DARK, "fg": GREEN, "highlight": GREEN_LIGHT}
        elif theme_name == "BLUE":  
            return {"bg": BLUE_DARK, "fg": BLUE, "highlight": BLUE_LIGHT}
        elif theme_name == "GRAY":
            return {"bg": GRAY_DARK, "fg": GRAY, "highlight": GRAY_LIGHT}
        else:
            # Default to current manager theme
            manager_colors = self.manager.get_theme_colors()
            return {"bg": manager_colors.get("bg", GRAY_DARK), 
                   "fg": manager_colors.get("fg", GRAY), 
                   "highlight": manager_colors.get("highlight", GRAY_LIGHT)}
            
    def update_colors_from_theme(self):
        """Update default colors based on current UI theme"""
        if self.manager:
            gray_colors = self.get_theme_colors("GRAY")
            new_fill = gray_colors["bg"]
            new_border = gray_colors["fg"]
            
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
        
    def update_layout(self):
        """Calculate positions for the three hexagons in base coordinates"""
        if not hasattr(self, 'base_rect') or self.base_rect is None:
            return
            
        # Work in base coordinates - the UI manager will handle scaling
        available_width = self.base_rect.width
        available_height = self.base_rect.height
        
        # Calculate optimal hexagon size to fit the available space
        # We need to fit: 2 hexagons horizontally + spacing between them
        # And vertically: 2 hexagons + vertical spacing between them
        
        vertical_spacing = self.base_spacing - 8  # Base pixels between top and bottom hexagons
        horizontal_spacing = self.base_spacing  # Use the reduced 12px spacing
        
        # Calculate maximum hexagon size that fits horizontally
        # Available width for 2 hexagons + spacing: width = 2 * (2 * radius) + spacing
        max_radius_horizontal = (available_width - horizontal_spacing) // 4  # 4 = 2 hexagons * 2 (diameter = 2*radius)
        
        # Calculate maximum hexagon size that fits vertically  
        # Available height for 2 hexagons + spacing: height = 2 * (2 * radius) + spacing
        max_radius_vertical = (available_height - vertical_spacing) // 4  # 4 = 2 hexagons * 2 (diameter = 2*radius)
        
        # Use the smaller of the two to ensure hexagons fit in both dimensions
        optimal_radius = min(max_radius_horizontal, max_radius_vertical, self.base_hexagon_size)
        optimal_radius = max(optimal_radius, 8)  # Minimum radius of 8 pixels
        
        # Update the hexagon size to the optimal size
        self.base_hexagon_size = optimal_radius
        
        # Calculate total height needed for hexagons and spacing
        hexagon_height = optimal_radius * 2  # Diameter
        total_needed_height = hexagon_height + vertical_spacing + hexagon_height
        
        # Center the entire layout vertically
        layout_start_y = (available_height - total_needed_height) // 2
        
        # Top hexagon: centered horizontally, at calculated top position
        top_x = available_width // 2
        top_y = layout_start_y + optimal_radius  # Center of top hexagon
        
        # Bottom hexagons: side by side, centered as a group, with 16px spacing from top
        bottom_y = top_y + optimal_radius + vertical_spacing + optimal_radius  # Center of bottom hexagons
        
        # Calculate horizontal positions for bottom hexagons
        # Total width of both hexagons plus spacing
        total_bottom_width = (optimal_radius * 2 * 2) + horizontal_spacing  # diameter * 2 + spacing
        bottom_start_x = (available_width - total_bottom_width) // 2
        
        bottom_left_x = bottom_start_x + optimal_radius  # Center of left hexagon
        bottom_right_x = bottom_left_x + (optimal_radius * 2) + horizontal_spacing  # Center of right hexagon
        
        # Store positions in base coordinates
        self.top_hexagon_center = (top_x, top_y)
        self.bottom_left_center = (bottom_left_x, bottom_y)
        self.bottom_right_center = (bottom_right_x, bottom_y)
        
        self.needs_layout_update = False
        self.needs_redraw = True
        
    def create_mixed_color(self, color1, color2, ratio=0.5):
        """Create a mixed color from two colors with given ratio (0.0 to 1.0)"""
        if not color1 or not color2:
            return color1 or color2 or (128, 128, 128)
            
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        
        return (r, g, b)
        
    def draw_gradient_hexagon(self, surface, center, radius, color1, color2, border_color, border_width):
        """Draw a hexagon with a gradient from color1 to color2"""
        # Convert base center to scaled screen coordinates relative to component
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
            angle = (math.pi / 3 * i) + (math.pi / 6)  # 60 degrees * i + 30 degrees rotation
            x = scaled_center[0] + scaled_radius * math.cos(angle)
            y = scaled_center[1] + scaled_radius * math.sin(angle)
            points.append((int(x), int(y)))
        
        # Create a gradient effect by drawing multiple layers
        if len(points) >= 3:
            # Draw gradient layers from outside to inside
            gradient_steps = 10
            for step in range(gradient_steps):
                ratio = step / (gradient_steps - 1)
                layer_color = self.create_mixed_color(color1, color2, ratio)
                layer_radius = scaled_radius * (1 - step * 0.1)
                
                if layer_radius > 0:
                    layer_points = []
                    for i in range(6):
                        angle = (math.pi / 3 * i) + (math.pi / 6)
                        x = scaled_center[0] + layer_radius * math.cos(angle)
                        y = scaled_center[1] + layer_radius * math.sin(angle)
                        layer_points.append((int(x), int(y)))
                    
                    if len(layer_points) >= 3:
                        pygame.draw.polygon(surface, layer_color, layer_points)
            
            # Draw border
            if border_color and scaled_border_width > 0:
                pygame.draw.polygon(surface, border_color, points, scaled_border_width)
        
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
            
            # Calculate animation progress (0.0 to 1.0)
            animation_progress = min(self.animation_timer / self.animation_duration, 1.0)
            
            # DNA reveal animation (first 70% of the animation)
            dna_phase_duration = 0.7
            if animation_progress <= dna_phase_duration:
                self.dna_reveal_progress = animation_progress / dna_phase_duration
            else:
                self.dna_reveal_progress = 1.0
                # Start hexagon reveal in the last 30% of animation
                if not self.hexagon_revealed:
                    self.hexagon_revealed = True
                    self.show_result = True
                    runtime_globals.game_console.log("[JogressDisplay] Hexagon reveal started")
                    
            # End animation
            if animation_progress >= 1.0:
                self.animation_active = False
                self.show_result = True
                runtime_globals.game_console.log("[JogressDisplay] Animation completed")
                
            self.needs_redraw = True
            
    def draw_hexagon(self, surface, center, radius, fill_color, border_color, border_width):
        """Draw a hexagon at the specified center with given colors"""
        # Convert base center to scaled screen coordinates relative to component
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
            angle = (math.pi / 3 * i) + (math.pi / 6)  # 60 degrees * i + 30 degrees rotation
            x = scaled_center[0] + scaled_radius * math.cos(angle)
            y = scaled_center[1] + scaled_radius * math.sin(angle)
            points.append((int(x), int(y)))
        
        # Draw filled hexagon
        if len(points) >= 3:
            pygame.draw.polygon(surface, fill_color, points)
            if border_color and scaled_border_width > 0:
                pygame.draw.polygon(surface, border_color, points, scaled_border_width)
                
    def draw_pet_sprite(self, surface, pet, center, radius):
        """Draw a pet sprite centered in a hexagon"""
        if not pet or not hasattr(pet, 'get_sprite'):
            return
            
        try:
            sprite = pet.get_sprite(PetFrame.NAP2.value if pet.state == "nap" else PetFrame.IDLE1.value)
            if not sprite:
                return
                
            # Convert base center to scaled screen coordinates
            if self.manager:
                scaled_center = (
                    self.manager.scale_value(center[0]),
                    self.manager.scale_value(center[1])
                )
                scaled_radius = self.manager.scale_value(radius)
            else:
                scaled_center = center
                scaled_radius = radius
                
            sprite_rect = sprite.get_rect()
            
            # Calculate sprite padding (leave some space around sprite in hexagon)
            sprite_padding = max(4, scaled_radius // 8)
            available_radius = scaled_radius - sprite_padding
            
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
            blit_with_cache(surface, sprite, sprite_rect.topleft)
            
        except Exception as e:
            runtime_globals.game_console.log(f"[JogressDisplay] Failed to draw pet sprite: {e}")
            
    def load_jogress_result_sprite(self):
        """Load the Battle_JogressUnknown sprite (cached)"""
        if self.jogress_result_sprite is not None:
            return self.jogress_result_sprite
            
        if not self.manager:
            return None
            
        try:
            # Use the UI manager's sprite loading system
            self.jogress_result_sprite = self.manager.load_sprite_integer_scaling("Battle", "JogressUnknown", "")
            if self.jogress_result_sprite:
                runtime_globals.game_console.log("[JogressDisplay] Successfully loaded and cached JogressUnknown sprite")
            return self.jogress_result_sprite
        except Exception as e:
            runtime_globals.game_console.log(f"[JogressDisplay] Failed to load JogressUnknown sprite: {e}")
            return None
            
    def load_dna_sprite(self):
        """Load the Battle DNA sprite (cached)"""
        if self.dna_sprite is not None:
            return self.dna_sprite
            
        if not self.manager:
            return None
            
        self.dna_sprite = self.manager.load_sprite_integer_scaling("Battle", "DNA", "")
        return self.dna_sprite

    def load_jogress_ready_sprite(self):
        """Load the Battle_JogressReady sprite (cached)"""
        if self.jogress_ready_sprite is not None:
            return self.jogress_ready_sprite
            
        if not self.manager:
            return None
            
        try:
            # Use the UI manager's sprite loading system
            self.jogress_ready_sprite = self.manager.load_sprite_integer_scaling("Battle", "JogressReady", "")
            if self.jogress_ready_sprite:
                runtime_globals.game_console.log("[JogressDisplay] Successfully loaded and cached JogressReady sprite")
            return self.jogress_ready_sprite
        except Exception as e:
            runtime_globals.game_console.log(f"[JogressDisplay] Failed to load JogressReady sprite: {e}")
            return None
    
    def set_hide_pet_sprites(self, hide):
        """Control visibility of pet sprites for animation purposes"""
        self.hide_pet_sprites = hide
    
    def render(self):
        """Render the component using the render-based pattern"""
        # Create the surface for this component
        # Reuse a cached render surface to avoid per-frame allocations
        target_size = (self.rect.width, self.rect.height)
        if not hasattr(self, "_render_surface") or self._render_surface is None or self._render_surface.get_size() != target_size:
            self._render_surface = pygame.Surface(target_size, pygame.SRCALPHA)
        surface = self._render_surface
        surface.fill((0, 0, 0, 0))
        
        if not self.top_hexagon_center or not self.bottom_left_center or not self.bottom_right_center:
            return surface
        
        # Draw DNA sprite with animation when pets are compatible
        if self.is_compatible and (self.animation_active or self.show_result):
            dna_sprite = self.load_dna_sprite()
            if dna_sprite:
                # Center the DNA sprite in the component
                if self.manager:
                    component_center_x = self.manager.scale_value(self.base_rect.width // 2)
                    component_center_y = self.manager.scale_value(self.base_rect.height // 2)
                else:
                    component_center_x = self.base_rect.width // 2
                    component_center_y = self.base_rect.height // 2
                
                dna_rect = dna_sprite.get_rect()
                dna_rect.center = (component_center_x, component_center_y + 10)  # Slightly lower center
                
                # During animation, draw only part of the sprite (bottom to top)
                if self.animation_active and self.dna_reveal_progress < 1.0:
                    # Calculate how many lines to reveal
                    lines_to_show = int(dna_sprite.get_height() * self.dna_reveal_progress)
                    if lines_to_show > 0:
                        # Create a clipped version of the sprite
                        sprite_height = dna_sprite.get_height()
                        start_y = sprite_height - lines_to_show
                        
                        # Create a subsurface showing only the bottom portion
                        if lines_to_show < sprite_height:
                            revealed_sprite = dna_sprite.subsurface((0, start_y, dna_sprite.get_width(), lines_to_show))
                            # Adjust position to draw from bottom up
                            adjusted_rect = revealed_sprite.get_rect()
                            adjusted_rect.centerx = dna_rect.centerx
                            adjusted_rect.bottom = dna_rect.bottom
                            blit_with_cache(surface, revealed_sprite, adjusted_rect.topleft)
                        else:
                            blit_with_cache(surface, dna_sprite, dna_rect.topleft)
                else:
                    # Animation complete or not active, draw full sprite
                    blit_with_cache(surface, dna_sprite, dna_rect.topleft)
            
        # Draw bottom hexagons (pet slots)
        for slot_index in range(2):
            pet = self.slot_pets[slot_index]
            center = self.bottom_left_center if slot_index == 0 else self.bottom_right_center
            
            if pet is not None:
                # Pet is present - use slot theme colors
                theme_name = self.slot_themes[slot_index]
                colors = self.get_theme_colors(theme_name)
                fill_color = colors["bg"]
                border_color = colors["fg"]
            else:
                # Empty slot - use default gray colors
                fill_color = self.default_fill
                border_color = self.default_border
                
            # Draw hexagon
            self.draw_hexagon(
                surface, center, self.base_hexagon_size, 
                fill_color, border_color, self.base_border_width
            )
            
            # Draw pet sprite if present and not hidden
            if pet is not None and not self.hide_pet_sprites:
                self.draw_pet_sprite(surface, pet, center, self.base_hexagon_size)
        
        # Draw top hexagon (result slot) - only show after hexagon reveal phase
        if self.show_result and self.hexagon_revealed:
            # Compatible pets - draw JogressReady sprite as background hexagon
            jogress_ready_sprite = self.load_jogress_ready_sprite()
            if jogress_ready_sprite:
                # Scale and position the JogressReady sprite to match hexagon size
                if self.manager:
                    scaled_center = (
                        self.manager.scale_value(self.top_hexagon_center[0]),
                        self.manager.scale_value(self.top_hexagon_center[1])
                    )
                    scaled_radius = self.manager.scale_value(self.base_hexagon_size)
                else:
                    scaled_center = self.top_hexagon_center
                    scaled_radius = self.base_hexagon_size
                
                # Scale the sprite to fit the hexagon size (diameter = 2 * radius)
                target_size = scaled_radius * 2
                sprite_rect = jogress_ready_sprite.get_rect()
                
                # Calculate scale factor to fit the hexagon
                scale_factor = target_size / max(sprite_rect.width, sprite_rect.height)
                if scale_factor != 1.0:
                    new_width = max(1, int(sprite_rect.width * scale_factor))
                    new_height = max(1, int(sprite_rect.height * scale_factor))
                    jogress_ready_sprite = pygame.transform.scale(jogress_ready_sprite, (new_width, new_height))
                    sprite_rect = jogress_ready_sprite.get_rect()
                
                # Center the sprite at the hexagon position
                sprite_rect.center = scaled_center
                blit_with_cache(surface, jogress_ready_sprite, sprite_rect.topleft)
            else:
                # Fallback: draw default gray hexagon if sprite fails to load
                self.draw_hexagon(
                    surface, self.top_hexagon_center, self.base_hexagon_size,
                    self.default_fill, self.default_border, self.base_border_width
                )
            
            # Draw JogressUnknown sprite(s) on top of the ready hexagon
            result_sprite = self.load_jogress_result_sprite()
            if result_sprite:
                if self.manager:
                    scaled_center = (
                        self.manager.scale_value(self.top_hexagon_center[0]),
                        self.manager.scale_value(self.top_hexagon_center[1])
                    )
                    scaled_radius = self.manager.scale_value(self.base_hexagon_size)
                else:
                    scaled_center = self.top_hexagon_center
                    scaled_radius = self.base_hexagon_size
                    
                # Check if this is a dual evolution (PenC type)
                is_dual_evolution = (self.evolution_info and 
                                   self.evolution_info.get("is_dual", False))
                
                if is_dual_evolution:
                    # Draw two sprites side by side for dual evolution at 50% scale
                    sprite_rect = result_sprite.get_rect()
                    
                    # Scale sprites to 50% for dual evolution
                    new_width = max(1, int(sprite_rect.width * 0.5))
                    new_height = max(1, int(sprite_rect.height * 0.5))
                    scaled_sprite = pygame.transform.scale(result_sprite, (new_width, new_height))
                    scaled_sprite_rect = scaled_sprite.get_rect()
                    
                    # Calculate proper spacing between sprites (half sprite width apart)
                    sprite_spacing = new_width
                    
                    # Position left sprite
                    left_sprite_rect = scaled_sprite_rect.copy()
                    left_sprite_rect.centerx = scaled_center[0] - sprite_spacing // 2
                    left_sprite_rect.centery = scaled_center[1]
                    
                    # Position right sprite
                    right_sprite_rect = scaled_sprite_rect.copy()
                    right_sprite_rect.centerx = scaled_center[0] + sprite_spacing // 2
                    right_sprite_rect.centery = scaled_center[1]
                    
                    # Draw both sprites
                    blit_with_cache(surface, scaled_sprite, left_sprite_rect.topleft)
                    blit_with_cache(surface, scaled_sprite, right_sprite_rect.topleft)
                    
                else:
                    # Single evolution - draw one sprite centered at original size (no scaling)
                    sprite_rect = result_sprite.get_rect()
                    sprite_rect.center = scaled_center
                    blit_with_cache(surface, result_sprite, sprite_rect.topleft)
        # Note: When not compatible or animation not active, top hexagon is hidden (no else block)
        
        return surface
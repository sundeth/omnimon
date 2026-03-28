"""
Flag Panel Component - Shows pet attribute and status flags from right to left
"""

import pygame
from ui.components.component import UIComponent
from core import runtime_globals
from utils.pygame_utils import blit_with_cache


class FlagPanel(UIComponent):
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
        self.focusable = False
        self.flags = []  # List of flag data to display
        self.flag_sprites = {}  # Cache for loaded flag sprites
        
        # Flag spacing - will be scaled
        self.base_flag_spacing = 2
        self.flag_spacing = self.base_flag_spacing
        
    def on_manager_set(self):
        """Called when component is added to a UI manager"""
        if self.manager:
            # Scale the flag spacing based on UI scale
            self.flag_spacing = self.manager.scale_value(self.base_flag_spacing)
            
    def load_flag_sprite(self, flag_name):
        """Load a flag sprite with fallback and scaling"""
        if flag_name in self.flag_sprites:
            return self.flag_sprites[flag_name]
            
        if not self.manager:
            return None
        
        # Try to load with preferred scale first
        sprite = self.manager.load_sprite_integer_scaling("Status", flag_name, "")

        self.flag_sprites[flag_name] = sprite
        return sprite
        
                
    def set_pet_flags(self, pet, additional_flags=None):
        """Update the flags based on pet attributes and status"""
        if not pet:
            self.flags = []
            return
            
        flags = []
        
        # Attribute flag (always present)
        attribute = getattr(pet, 'attribute', '')
        if attribute == "":
            flags.append(('Free', 'Attribute: Free'))
        elif attribute == "Da":
            flags.append(('Da', 'Attribute: Dark'))
        elif attribute == "Va":
            flags.append(('Va', 'Attribute: Vaccine'))
        elif attribute == "Vi":
            flags.append(('Vi', 'Attribute: Virus'))
        else:
            # Fallback for unknown attributes
            flags.append(('Free', f'Attribute: {attribute}'))
            
        # Status flags (only show if true)
        if getattr(pet, 'edited', False):
            flags.append(('Edited', 'This pet has been edited'))
            
        if getattr(pet, 'special', False):
            flags.append(('Special', 'This is a special pet'))
            
        if getattr(pet, 'shiny', False):
            flags.append(('Shiny', 'This pet has shiny coloring'))
            
        if getattr(pet, 'shook', False):
            flags.append(('Shook', 'This pet has been shaken'))
            
        if getattr(pet, 'traited', False):
            flags.append(('Traited', 'This pet started with traits'))
            
        # Add any additional flags provided
        if additional_flags:
            for flag in additional_flags:
                if flag == 'GCellFragment':
                    flags.append(('GCellFragment', 'This pet was hatched from a G-Cell fragment'))
            
        self.flags = flags
        self.needs_redraw = True
        
    def render(self):
        # Use screen dimensions for surface
        surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        
        if not self.flags:
            return surface
            
        # Load flag sprites
        flag_images = []
        for flag_name, tooltip in self.flags:
            sprite = self.load_flag_sprite(flag_name)
            if sprite:
                flag_images.append(sprite)
                
        if not flag_images:
            return surface
            
        # Calculate total width needed for flags
        total_flags_width = sum(img.get_width() for img in flag_images)
        total_spacing_width = (len(flag_images) - 1) * self.flag_spacing if len(flag_images) > 1 else 0
        total_width = total_flags_width + total_spacing_width
        
        # Position flags from right to left
        current_x = self.rect.width - total_width
        
        # Ensure flags don't go outside the left boundary
        if current_x < 0:
            current_x = 0
            
        # Draw flags from left to right (which were calculated from right to left)
        for i, sprite in enumerate(flag_images):
            flag_y = (self.rect.height - sprite.get_height()) // 2  # Center vertically
            blit_with_cache(surface, sprite, (current_x, flag_y))
            current_x += sprite.get_width() + self.flag_spacing
        
        # Draw highlight if focused and has tooltip
        # Skip in touch mode - focus highlights are for keyboard/mouse navigation only
        if self.focused and hasattr(self, 'tooltip_text') and self.tooltip_text and runtime_globals.INPUT_MODE != runtime_globals.TOUCH_MODE:
            colors = self.manager.get_theme_colors()
            highlight_color = colors.get("highlight", colors["fg"])  # Safe fallback
            pygame.draw.rect(surface, highlight_color, surface.get_rect(), 2)
            
        return surface
        
    def get_tooltip_at_position(self, local_x, local_y):
        """Get tooltip text for flag at given position"""
        if not self.flags:
            return None
            
        # Load flag sprites to get their dimensions
        flag_images = []
        for flag_name, tooltip in self.flags:
            sprite = self.load_flag_sprite(flag_name)
            if sprite:
                flag_images.append((sprite, tooltip))
                
        if not flag_images:
            return None
            
        # Calculate flag positions (same logic as render)
        total_flags_width = sum(img[0].get_width() for img in flag_images)
        total_spacing_width = (len(flag_images) - 1) * self.flag_spacing if len(flag_images) > 1 else 0
        total_width = total_flags_width + total_spacing_width
        
        current_x = self.rect.width - total_width
        if current_x < 0:
            current_x = 0
            
        # Check which flag the mouse is over
        for sprite, tooltip in flag_images:
            flag_width = sprite.get_width()
            flag_height = sprite.get_height()
            flag_y = (self.rect.height - flag_height) // 2
            
            if (current_x <= local_x < current_x + flag_width and 
                flag_y <= local_y < flag_y + flag_height):
                return tooltip
                
            current_x += flag_width + self.flag_spacing
            
        return None
"""
Heart Meter Component - Shows icon and hearts for stats like hunger, vitamin, effort

The component supports a factor system:
- factor=1: 1 point = 1 full heart (used for hunger, vitamin)
- factor=4: 4 points = 1 full heart, 2 points = 1 half heart (used for effort)

Examples:
- Effort value 10 with factor 4 = 2.5 hearts (2 full hearts + 1 half heart)
- Hunger value 3 with factor 1 = 3 full hearts
"""
import pygame
from ui.components.component import UIComponent
from core import runtime_globals
from utils.pygame_utils import blit_with_cache


class HeartMeter(UIComponent):
    def __init__(self, x, y, width, height, icon_name, value, max_value=4, factor=1):
        super().__init__(x, y, width, height)
        self.icon_name = icon_name  # e.g., "Hunger", "Vitamin", "Effort"
        self.value = value
        self.max_value = max_value
        self.factor = factor  # How many points equal one heart (e.g., 1 for hunger/vitamin, 4 for effort)
        self.focusable = True  # Make HeartMeter focusable for highlighting
        self.icon = None
        self.heart_images = {}
        
    def load_images(self):
        """Load heart images using unified sprite loading methods"""
        if not self.manager:
            return
            
        runtime_globals.game_console.log(f"[HeartMeter] Loading images for {self.icon_name}")
        
        # Load icon using integer scaling method
        self.icon = self.manager.load_sprite_integer_scaling("Status", self.icon_name)
        
        # Load heart images using integer scaling method
        self.heart_images = {
            "empty": self.manager.load_sprite_integer_scaling("Status", "Heart", "Empty"),
            "half": self.manager.load_sprite_integer_scaling("Status", "Heart", "Half"), 
            "full": self.manager.load_sprite_integer_scaling("Status", "Heart", "Full")
        }
        
    def set_value(self, value):
        """Update the meter value"""
        if self.value != value:
            self.value = value
            self.needs_redraw = True
    
    def set_max_value(self, max_value):
        """Update the maximum value (number of hearts)"""
        if self.max_value != max_value:
            self.max_value = max_value
            self.needs_redraw = True
        
    def render(self):
        # Use screen dimensions for surface
        surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        
        # Load images if not already loaded
        if self.icon is None:
            self.load_images()
        
        # Get colors
        colors = self.manager.get_theme_colors()
        bg_color = colors["bg"]
        fg_color = colors["black"]
        
        # Draw icon
        icon_width = self.icon.get_width()
        icon_rect = self.icon.get_rect(centery=self.rect.height//2)
        
        # Calculate background rectangle dimensions (using screen coordinates)
        # Note: self.rect is already scaled by UIManager, so no additional scaling needed
        rect_start_x = icon_width // 2  # Start from middle of icon
        rect_width = self.rect.width - rect_start_x
        # Scale padding proportionally with UI scale (2 base pixels)
        rect_padding = max(2, 2 * self.manager.ui_scale)
        
        # Draw background rounded rectangle behind hearts directly on component surface
        # Since we're drawing on the component's own surface, use direct pygame.draw
        bg_rect = pygame.Rect(rect_start_x, rect_padding, rect_width, self.rect.height - 2 * rect_padding)
        border_radius = max(2, self.manager.get_border_size())
        border_width = max(1, self.manager.get_border_size())
        
        # Draw background with border
        pygame.draw.rect(surface, bg_color, bg_rect, border_radius=border_radius)
        pygame.draw.rect(surface, fg_color, bg_rect, width=border_width, border_radius=border_radius)

        blit_with_cache(surface, self.icon, icon_rect)
        
        # Calculate heart positions - ensure we always show max_value hearts
        heart_width = self.heart_images["empty"].get_width()
        # Scale spacing proportionally with UI scale (2 base pixels)
        heart_spacing = max(2, 2 * self.manager.ui_scale)
        # Scale padding proportionally with UI scale (11 base pixels)
        heart_start_x = rect_start_x + max(11, 11 * self.manager.ui_scale)
        
        # Calculate total hearts width needed
        total_hearts_width = self.max_value * heart_width + (self.max_value - 1) * heart_spacing
        # Scale padding proportionally with UI scale (14 base pixels = 7 on each side)
        available_width = rect_width - max(14, 14 * self.manager.ui_scale)
        
        # If hearts don't fit, adjust spacing to make them fit
        if total_hearts_width > available_width and self.max_value > 1:
            heart_spacing = max(1, (available_width - self.max_value * heart_width) // (self.max_value - 1))
        
        # Draw hearts
        for i in range(self.max_value):
            heart_x = heart_start_x + i * (heart_width + heart_spacing)
            heart_y = (self.rect.height - self.heart_images["empty"].get_height()) // 2
            
            # Calculate heart display based on factor
            # factor determines how many points = 1 heart
            heart_value = (self.value / self.factor) - i
            
            # Determine heart type based on calculated heart value
            if heart_value >= 1.0:
                heart = self.heart_images["full"]
            elif heart_value >= 0.5:
                heart = self.heart_images["half"]
            else:
                heart = self.heart_images["empty"]
                
            blit_with_cache(surface, heart, (heart_x, heart_y))
        
        # Draw highlight if focused (mouse hover or keyboard focus)
        # Skip in touch mode - focus highlights are for keyboard/mouse navigation only
        if self.focused and runtime_globals.INPUT_MODE != runtime_globals.TOUCH_MODE:
            colors = self.manager.get_theme_colors()
            highlight_color = colors.get("highlight", colors["fg"])  # Safe fallback
            pygame.draw.rect(surface, highlight_color, surface.get_rect(), 2)
            
        return surface

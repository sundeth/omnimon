"""
DP Bar Component - Shows DP (Discipline Points) as a row of filled/empty indicators
"""
import pygame
from ui.components.component import UIComponent
from utils.pygame_utils import blit_with_cache
from core import runtime_globals


class DPBar(UIComponent):
    def __init__(self, x, y, width, height, value, max_value=14):
        super().__init__(x, y, width, height)
        self.value = value
        self.max_value = max_value
        self.focusable = False
        self.dp_images = {}
        
    def load_images(self):
        """Load DP images based on UI scale with fallback and scaling"""
        if not self.manager:
            return

        # Try to load with preferred scale first
        self.dp_images = {
            "empty": self.manager.load_sprite_integer_scaling("Status", "DP", "Empty"),
            "full": self.manager.load_sprite_integer_scaling("Status", "DP", "Full")
        }
        
    def set_value(self, value):
        """Update the DP value"""
        if self.value != value:
            self.value = value
            self.needs_redraw = True
        
    def render(self):
        # Use screen dimensions for surface
        surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        
        # Load images if needed
        if not self.dp_images:
            self.load_images()
        
        # Original DP sprite dimensions
        original_dp_width = self.dp_images["empty"].get_width()
        original_dp_height = self.dp_images["empty"].get_height()
        
        # Calculate ideal dimensions to fit 14 DPs with 2-pixel overlap
        base_overlap = 2  # 2 pixels overlap at 240x240 resolution
        dp_overlap = self.manager.scale_value(base_overlap)  # Scale overlap for current resolution
        dp_start_x = self.manager.scale_value(1)  # Scale base padding
        available_width = self.rect.width - 2 * dp_start_x
        
        # Calculate the effective width each DP should take (with overlap)
        # For 14 DPs with overlap: width = DP_width * 14 - overlap * 13
        # Solving for DP_width: DP_width = (width + overlap * 13) / 14
        effective_dp_width = (available_width + dp_overlap * (self.max_value - 1)) // self.max_value
        
        # Scale the DP sprites if needed to fit exactly
        if effective_dp_width != original_dp_width:
            # Maintain aspect ratio
            scale_factor = effective_dp_width / original_dp_width
            scaled_dp_height = int(original_dp_height * scale_factor)
            
            # Scale both DP images
            scaled_dp_size = (effective_dp_width, scaled_dp_height)
            scaled_dp_empty = pygame.transform.scale(self.dp_images["empty"], scaled_dp_size)
            scaled_dp_full = pygame.transform.scale(self.dp_images["full"], scaled_dp_size)
        else:
            scaled_dp_empty = self.dp_images["empty"]
            scaled_dp_full = self.dp_images["full"]
            scaled_dp_height = original_dp_height
        
        # Center vertically
        dp_start_y = (self.rect.height - scaled_dp_height) // 2
        
        # Draw all 14 DP indicators with proper overlap
        for i in range(self.max_value):
            dp_x = dp_start_x + i * (effective_dp_width - dp_overlap)
            
            # Determine DP type
            if i < self.value:
                dp = scaled_dp_full
            else:
                dp = scaled_dp_empty
                
            blit_with_cache(surface, dp, (dp_x, dp_start_y))
        
        # Draw highlight if focused and has tooltip
        # Skip in touch mode - focus highlights are for keyboard/mouse navigation only
        if self.focused and hasattr(self, 'tooltip_text') and self.tooltip_text and runtime_globals.INPUT_MODE != runtime_globals.TOUCH_MODE:
            colors = self.manager.get_theme_colors()
            highlight_color = colors.get("highlight", colors["fg"])  # Safe fallback
            pygame.draw.rect(surface, highlight_color, surface.get_rect(), 2)
            
        return surface

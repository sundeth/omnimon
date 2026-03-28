"""
Experience Bar Component - Shows experience progress with custom bar graphics
"""
import pygame
from ui.components.component import UIComponent
from utils.pygame_utils import blit_with_cache
from core import constants, runtime_globals


class ExperienceBar(UIComponent):
    def __init__(self, x, y, width, height, current_exp=0, pet_level=0, pet_stage=0, color_theme="purple"):
        super().__init__(x, y, width, height)
        self.current_exp = current_exp
        self.pet_level = pet_level
        self.pet_stage = pet_stage
        self.focusable = False
        self.exp_bar_bg = None
        self.bar_surface = None
        self.surface_needs_rebuild = True
        self.color_theme = color_theme
        
        # Set bar colors based on theme
        self.set_color_theme(color_theme)
        
    def set_color_theme(self, theme):
        """Set the color theme for the experience bar"""
        self.color_theme = theme
        
        if theme == "red":
            self.shadow_color = (0x4d, 0x1e, 0x1e)     # Dark red shadow
            self.primary_color = (0xcc, 0x33, 0x33)    # Red primary  
            self.highlight_color = (0xff, 0x55, 0x55)  # Light red highlight
        elif theme == "yellow":
            self.shadow_color = (0x4d, 0x4d, 0x1e)     # Dark yellow shadow
            self.primary_color = (0xcc, 0xcc, 0x33)    # Yellow primary
            self.highlight_color = (0xff, 0xff, 0x55)  # Light yellow highlight
        elif theme == "green":
            self.shadow_color = (0x1e, 0x4d, 0x1e)     # Dark green shadow
            self.primary_color = (0x33, 0xcc, 0x33)    # Green primary
            self.highlight_color = (0x55, 0xff, 0x55)  # Light green highlight
        elif theme == "blue":
            self.shadow_color = (0x1e, 0x1e, 0x4d)     # Dark blue shadow
            self.primary_color = (0x33, 0x33, 0xcc)    # Blue primary
            self.highlight_color = (0x55, 0x55, 0xff)  # Light blue highlight
        else:  # Default purple theme
            self.shadow_color = (0x4d, 0x2e, 0x3c)     # #4d2e3c
            self.primary_color = (0x99, 0x2e, 0x69)    # #992e69  
            self.highlight_color = (0xb3, 0x2d, 0xac)  # #b32dac
            
        # Mark for redraw if theme changed
        self.surface_needs_rebuild = True
        self.needs_redraw = True
        
    def load_images(self):
        """Load experience bar background image"""
        if not self.manager:
            return
            
        # Get sprite scale based on UI scale
        sprite_scale = self.manager.get_sprite_scale()
        
        # Load the sprite directly - it's always part of the game assets
        self.exp_bar_bg = self.manager.load_sprite_integer_scaling("Status", "Experience_Bar", "")
        self.surface_needs_rebuild = True
        
    def set_experience(self, current_exp, pet_level, pet_stage):
        """Update experience values"""
        if not self.exp_bar_bg:
            self.load_images()

        if (self.current_exp != current_exp or self.pet_level != pet_level or self.pet_stage != pet_stage):
            self.current_exp = current_exp
            self.pet_level = pet_level
            self.pet_stage = pet_stage
            self.surface_needs_rebuild = True
            self.needs_redraw = True
    
    def set_progress(self, progress):
        """Set progress directly (0.0 to 1.0) for use as a general progress bar"""
        if not self.exp_bar_bg:
            self.load_images()
            
        # Store progress as fake experience values
        self.current_exp = int(progress * 100)
        self.pet_level = 1  # Use level 1 so progress calculation works
        self.pet_stage = 1  # Use stage 1 so progress calculation works
        self.surface_needs_rebuild = True
        self.needs_redraw = True
        
    def calculate_progress(self):
        """Calculate experience progress as a percentage (0.0 to 1.0)"""
        # If we're using this as a general progress bar (set_progress was called)
        # then current_exp represents the percentage directly
        if hasattr(self, '_direct_progress'):
            return self._direct_progress
            
        # Stage 0 (Egg) don't get experience at all
        if self.pet_stage == 0:
            return 0.0
            
        # Level 10 is at max, so it's full
        if self.pet_level >= 10:
            return 1.0
            
        # For direct progress usage, return current_exp as percentage
        if self.pet_level == 1 and self.pet_stage == 1:
            return max(0.0, min(1.0, self.current_exp / 100.0))
            
        # Get experience needed for next level
        next_level_exp = constants.EXPERIENCE_LEVEL.get(self.pet_level + 1, None)
        
        # If no next level exists, we're at max level
        if next_level_exp is None:
            return 1.0
            
        # Progress is current experience divided by experience needed for next level
        # When pet.experience hits constants.EXPERIENCE_LEVEL.get(self.pet_level + 1), 
        # experience is set to 0 and the pet levels up
        progress = self.current_exp / next_level_exp
        return max(0.0, min(1.0, progress))  # Clamp between 0 and 1
        
    def build_bar_surface(self):
        """Build the experience bar fill based on current progress"""

        # Get UI scale for proper sizing
        scale = self.manager.ui_scale if self.manager else 1.0
        
        # Base dimensions at 1x scale
        base_width = 66
        base_height = 14
        
        # Scaled dimensions
        bar_width = int(base_width * scale)
        bar_height = int(base_height * scale)
        
        # Create surface for the bar fill
        bar_surface = pygame.Surface((bar_width, bar_height), pygame.SRCALPHA)
        
        # Calculate progress and fill width
        progress = self.calculate_progress()
        
        if progress <= 0:
            # Empty bar - no fill
            return bar_surface
            
        # Calculate fill area (scaled coordinates)
        # Line positions and dimensions scaled by UI scale
        line_height = int(2 * scale)
        
        # Line 1: y=3, x=5-62 (58 pixels wide)
        line1_y = int(3 * scale)
        line1_start_x = int(5 * scale)
        line1_end_x = int(62 * scale)
        line1_width = line1_end_x - line1_start_x + 1
        fill1_width = int(line1_width * progress)
        
        # Lines 2,3,4: y=5,7,9, x=3-64 (62 pixels wide)
        line2_y = int(5 * scale)
        line3_y = int(7 * scale)
        line4_y = int(9 * scale)
        line234_start_x = int(3 * scale)
        line234_end_x = int(64 * scale)
        line234_width = line234_end_x - line234_start_x + 1
        fill234_width = int(line234_width * progress)
        
        # Line 5: y=11, x=5-62 (58 pixels wide, all shadow)
        line5_y = int(11 * scale)
        line5_start_x = int(5 * scale)
        line5_end_x = int(62 * scale)
        line5_width = line5_end_x - line5_start_x + 1
        fill5_width = int(line5_width * progress)
        
        # Draw the filled portions
        if fill1_width > 0:
            # Line 1: 2px shadow on sides, rest primary
            shadow_width = int(2 * scale)
            if fill1_width <= shadow_width:
                # Only left shadow
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line1_start_x, line1_y, fill1_width, line_height))
            elif fill1_width >= line1_width - shadow_width:
                # Full line with both shadows
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line1_start_x, line1_y, shadow_width, line_height))
                pygame.draw.rect(bar_surface, self.primary_color, 
                               (line1_start_x + shadow_width, line1_y, 
                                line1_width - 2 * shadow_width, line_height))
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line1_end_x - shadow_width + 1, line1_y, shadow_width, line_height))
            else:
                # Partial fill
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line1_start_x, line1_y, shadow_width, line_height))
                pygame.draw.rect(bar_surface, self.primary_color, 
                               (line1_start_x + shadow_width, line1_y, 
                                fill1_width - shadow_width, line_height))
        
        # Line 2: 2px shadow on sides, 2px primary next to shadows, rest highlight
        if fill234_width > 0:
            shadow_width = int(2 * scale)
            primary_width = int(2 * scale)
            total_border = shadow_width + primary_width
            
            if fill234_width <= shadow_width:
                # Only left shadow
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line234_start_x, line2_y, fill234_width, line_height))
            elif fill234_width <= total_border:
                # Left shadow + partial left primary
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line234_start_x, line2_y, shadow_width, line_height))
                pygame.draw.rect(bar_surface, self.primary_color, 
                               (line234_start_x + shadow_width, line2_y, 
                                fill234_width - shadow_width, line_height))
            elif fill234_width >= line234_width - total_border:
                # Full line with all sections
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line234_start_x, line2_y, shadow_width, line_height))
                pygame.draw.rect(bar_surface, self.primary_color, 
                               (line234_start_x + shadow_width, line2_y, primary_width, line_height))
                highlight_width = line234_width - 2 * total_border
                pygame.draw.rect(bar_surface, self.highlight_color, 
                               (line234_start_x + total_border, line2_y, highlight_width, line_height))
                pygame.draw.rect(bar_surface, self.primary_color, 
                               (line234_end_x - total_border + 1, line2_y, primary_width, line_height))
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line234_end_x - shadow_width + 1, line2_y, shadow_width, line_height))
            else:
                # Partial fill with highlight
                pygame.draw.rect(bar_surface, self.shadow_color, 
                               (line234_start_x, line2_y, shadow_width, line_height))
                pygame.draw.rect(bar_surface, self.primary_color, 
                               (line234_start_x + shadow_width, line2_y, primary_width, line_height))
                pygame.draw.rect(bar_surface, self.highlight_color, 
                               (line234_start_x + total_border, line2_y, 
                                fill234_width - total_border, line_height))
        
        # Lines 3 & 4: Same pattern as line 1
        for line_y in [line3_y, line4_y]:
            if fill234_width > 0:
                shadow_width = int(2 * scale)
                if fill234_width <= shadow_width:
                    pygame.draw.rect(bar_surface, self.shadow_color, 
                                   (line234_start_x, line_y, fill234_width, line_height))
                elif fill234_width >= line234_width - shadow_width:
                    pygame.draw.rect(bar_surface, self.shadow_color, 
                                   (line234_start_x, line_y, shadow_width, line_height))
                    pygame.draw.rect(bar_surface, self.primary_color, 
                                   (line234_start_x + shadow_width, line_y, 
                                    line234_width - 2 * shadow_width, line_height))
                    pygame.draw.rect(bar_surface, self.shadow_color, 
                                   (line234_end_x - shadow_width + 1, line_y, shadow_width, line_height))
                else:
                    pygame.draw.rect(bar_surface, self.shadow_color, 
                                   (line234_start_x, line_y, shadow_width, line_height))
                    pygame.draw.rect(bar_surface, self.primary_color, 
                                   (line234_start_x + shadow_width, line_y, 
                                    fill234_width - shadow_width, line_height))
        
        # Line 5: All shadow color
        if fill5_width > 0:
            pygame.draw.rect(bar_surface, self.shadow_color, 
                           (line5_start_x, line5_y, fill5_width, line_height))
        
        return bar_surface
        
    def render(self):
        """Render the experience bar"""
        surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        
        if not self.exp_bar_bg:
            self.load_images()
            
        # Build bar fill if needed
        if self.surface_needs_rebuild or self.bar_surface is None:
            self.bar_surface = self.build_bar_surface()
            self.surface_needs_rebuild = False
            
        # Draw background sprite
        bg_x = (self.rect.width - self.exp_bar_bg.get_width()) // 2
        bg_y = (self.rect.height - self.exp_bar_bg.get_height()) // 2
        blit_with_cache(surface, self.exp_bar_bg, (bg_x, bg_y))
        
        # Draw bar fill on top
        if self.bar_surface:
            fill_x = (self.rect.width - self.bar_surface.get_width()) // 2
            fill_y = (self.rect.height - self.bar_surface.get_height()) // 2
            blit_with_cache(surface, self.bar_surface, (fill_x, fill_y))
        
        # Draw highlight if focused and has tooltip
        # Skip in touch mode - focus highlights are for keyboard/mouse navigation only
        if self.focused and hasattr(self, 'tooltip_text') and self.tooltip_text and runtime_globals.INPUT_MODE != runtime_globals.TOUCH_MODE:
            colors = self.manager.get_theme_colors()
            highlight_color = colors.get("highlight", colors["fg"])  # Safe fallback
            pygame.draw.rect(surface, highlight_color, surface.get_rect(), 2)
        
        return surface
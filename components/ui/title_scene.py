"""
Title Scene Component - A scene title with background sprite and left-aligned text
"""
import pygame
from components.ui.component import UIComponent
from core import runtime_globals


class TitleScene(UIComponent):
    def __init__(self, x, y, title_text):
        """
        Initialize the title scene component.
        
        Args:
            x: X position (should be 0 to connect with border)
            y: Y position 
            title_text: Text to display with title font
        """
        # Base dimensions at 1x scale
        width = 120
        height = 116
        
        super().__init__(x, y, width, height)
        
        self.title_text = title_text
        self.text_margin = 5  # Left margin for text in base scale
        
        # Sprites will be loaded when manager is set
        self.yellow_background_sprite = None
        self.blue_background_sprite = None
        self.green_background_sprite = None
        self.red_background_sprite = None
        self.gray_background_sprite = None
        self.font = None
        
        # Animation properties for background fade (used by sleep scene)
        self.current_mode = None  # "sleep", "wake", or None (use theme directly)
        self.is_animating = False
        self.animation_alpha = 255  # 0-255 for fade effect
        
    def on_manager_set(self):
        """Called when UI manager is set - load scaled assets"""
        if not self.manager:
            return
        
        self.yellow_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Yellow")
        self.blue_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Blue")
        self.green_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Green")
        self.red_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Red")
        self.gray_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Gray")
        self.cyan_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Cyan")
        self.yellow_bright_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Yellow_Bright")
        self.lime_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Lime")
        self.dark_red_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Dark_Red")
        self.violet_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Violet")
        self.teal_background_sprite = self.manager.load_sprite_integer_scaling("Sleep", "Title", "Teal")

        # Get title font using centralized method with proper scaling
        # Manager already handles scaling through get_title_font_size()
        font_size = self.manager.scale_value(24)
        self.font = self.get_font(custom_size=font_size)
        runtime_globals.game_console.log(f"[TitleScene] Font loaded: size={font_size}")
        
        # Force redraw
        self.needs_redraw = True
        
    def set_mode(self, mode):
        """Set the background mode (sleep=blue, wake=yellow) - used by sleep scene for animations"""
        if mode != self.current_mode:
            self.current_mode = mode
            self.needs_redraw = True
            
    def set_text(self, text):
        """Update the title text"""
        self.title_text = text
        self.needs_redraw = True
        
    def render(self):
        """Render the title scene component"""
        if getattr(self, 'cached_surface', None) is None or self.cached_surface.get_size() != (self.rect.width, self.rect.height):
            self.cached_surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        surface = self.cached_surface
        
        # Choose background sprite based on current mode (for sleep scene animation) or theme
        background_sprite = None
        
        if self.current_mode is not None:
            # Special mode behavior for sleep scene animations
            if self.current_mode == "wake":
                background_sprite = self.yellow_background_sprite
            elif self.current_mode == "sleep":
                background_sprite = self.blue_background_sprite
        else:
            # Use theme to determine background sprite for other scenes
            if self.manager and hasattr(self.manager, 'theme'):
                theme = self.manager.theme
                if theme == "BLUE":
                    background_sprite = self.blue_background_sprite
                elif theme == "YELLOW":
                    background_sprite = self.yellow_background_sprite
                elif theme == "GREEN":
                    background_sprite = self.green_background_sprite
                elif theme == "RED":
                    background_sprite = self.red_background_sprite
                elif theme == "GRAY":
                    background_sprite = self.gray_background_sprite
                elif theme == "YELLOW_BRIGHT":
                    background_sprite = self.yellow_bright_background_sprite
                elif theme == "CYAN":
                    background_sprite = self.cyan_background_sprite
                elif theme == "LIME":
                    background_sprite = self.lime_background_sprite
                elif theme == "RED_DARK_VARIANT":
                    background_sprite = self.dark_red_background_sprite
                elif theme == "VIOLET":
                    background_sprite = self.violet_background_sprite
                elif theme == "TEAL":
                    background_sprite = self.teal_background_sprite
                else:
                    # Fallback to blue if unknown theme
                    background_sprite = self.blue_background_sprite
        
        # Draw the selected background sprite
        if background_sprite:
            from core.utils.pygame_utils import blit_with_cache
            blit_with_cache(surface, background_sprite, (0, 0))
        
        # Draw title text with left margin and proper theme color
        if self.font and self.title_text:
            colors = self.manager.get_theme_colors()
            text_color = colors["black"]  # Use black color for text
            text_surface = self.font.render(self.title_text, True, text_color)
            
            # Position text with left margin and in the upper portion of the sprite
            # UIManager handles scaling, so use base coordinates
            text_x = self.text_margin  # Base margin value
            text_y = 2  # Base y position
            
            blit_with_cache(surface, text_surface, (text_x, text_y))
            
        return surface
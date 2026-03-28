"""
Code Entry Component
=====================

A component for entering fixed-length alphanumeric codes.
Works like a horizontal list where each position can be edited.

Usage:
    code_entry = CodeEntry(x, y, length=4)
    ui_manager.add_component(code_entry)
    
Controls:
    Mouse/Touch: Click on a character box to cycle its value (0-9, A-Z)
    Keyboard: LEFT/RIGHT to move between boxes, A/UP/DOWN to cycle character value
"""

import pygame
import string
from ui.components.component import UIComponent
from core import runtime_globals

class CodeEntry(UIComponent):
    def __init__(self, x, y, length=4, callback=None):
        # Size based on length (each char is 40x50 approx)
        self.base_char_w = 40
        self.base_char_h = 50
        self.base_spacing = 10
        total_w = (self.base_char_w * length) + (self.base_spacing * (length - 1))
        
        super().__init__(x, y, total_w, self.base_char_h)
        
        self.length = length
        self.callback = callback
        
        # State
        self.chars = ['A'] * length  # Default to 'A's
        self.selected_index = 0  # Currently selected character position (for keyboard)
        self.mouse_over_index = -1  # Mouse hover tracking
        
        # Charset: 0-9, A-Z
        self.charset = string.digits + string.ascii_uppercase
        
        self.focusable = True
        self.shadow_mode = "component"
        
        runtime_globals.game_console.log(f"[CodeEntry] Created length={length}")

    def get_text(self):
        """Get current code as string."""
        return "".join(self.chars)
    
    def _get_char_rect(self, index):
        """Get the rect for a specific character box (in component local coordinates)."""
        char_x = index * (self.base_char_w + self.base_spacing)
        return pygame.Rect(char_x, 0, self.base_char_w, self.base_char_h)
    
    def _cycle_character(self, index):
        """Cycle to the next character in the charset for the given index."""
        if 0 <= index < self.length:
            current_char = self.chars[index]
            char_idx = self.charset.index(current_char)
            new_idx = (char_idx + 1) % len(self.charset)
            self.chars[index] = self.charset[new_idx]
            self.needs_redraw = True
            runtime_globals.game_sound.play("select")
            runtime_globals.game_console.log(f"[CodeEntry] Character {index} cycled to {self.chars[index]}")

    def update(self):
        """Update component state including mouse hover detection."""
        super().update()
        
        # Handle mouse hover for visual feedback
        if (runtime_globals.INPUT_MODE in [runtime_globals.MOUSE_MODE, runtime_globals.TOUCH_MODE]) and self.focused:
            self._handle_mouse_hover()
    
    def _handle_mouse_hover(self):
        """Track which character box the mouse is over."""
        if not self.rect:
            return
        
        mouse_pos = runtime_globals.game_input.get_mouse_position()
        
        # Check if mouse is within component bounds
        if not self.rect.collidepoint(mouse_pos):
            if self.mouse_over_index != -1:
                self.mouse_over_index = -1
                self.needs_redraw = True
            return
        
        # Calculate which character box is being hovered
        local_x = mouse_pos[0] - self.rect.x
        index = int(local_x // (self.base_char_w + self.base_spacing))
        
        if 0 <= index < self.length:
            if self.mouse_over_index != index:
                self.mouse_over_index = index
                self.needs_redraw = True
        else:
            if self.mouse_over_index != -1:
                self.mouse_over_index = -1
                self.needs_redraw = True

    def handle_event(self, event):
        """Handle input events."""
        if not self.visible or not self.focused:
            return False
        
        # Event is a tuple: (event_type, event_data)
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        
        event_type, event_data = event
        
        # Mouse/Touch mode: Click on a character box to cycle its value
        if event_type == "LCLICK":
            if event_data and "pos" in event_data:
                mouse_pos = event_data["pos"]
                if self.rect.collidepoint(mouse_pos):
                    # Calculate which box was clicked
                    local_x = mouse_pos[0] - self.rect.x
                    clicked_index = int(local_x // (self.base_char_w + self.base_spacing))
                    
                    if 0 <= clicked_index < self.length:
                        runtime_globals.game_console.log(f"[CodeEntry] Clicked box {clicked_index}")
                        # Cycle the character at this position
                        self._cycle_character(clicked_index)
                        # Also update selection for keyboard mode
                        self.selected_index = clicked_index
                        return True
        
        # Keyboard mode: LEFT/RIGHT to navigate, A/UP/DOWN to cycle character
        elif event_type == "LEFT":
            self.selected_index = (self.selected_index - 1) % self.length
            runtime_globals.game_sound.play("menu")
            runtime_globals.game_console.log(f"[CodeEntry] Selected index: {self.selected_index}")
            self.needs_redraw = True
            return True
        
        elif event_type == "RIGHT":
            self.selected_index = (self.selected_index + 1) % self.length
            runtime_globals.game_sound.play("menu")
            runtime_globals.game_console.log(f"[CodeEntry] Selected index: {self.selected_index}")
            self.needs_redraw = True
            return True
        
        elif event_type in ["A", "UP", "DOWN"]:
            # Cycle character at selected position
            self._cycle_character(self.selected_index)
            return True
        
        return False

    def render(self):
        """Render the code entry widgets."""
        surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        
        colors = self.get_colors()
        font = self.get_font("title", 32)
        
        char_w = self.base_char_w
        char_h = self.base_char_h
        spacing = self.base_spacing
        
        for i in range(self.length):
            char_x = i * (char_w + spacing)
            
            # Draw char box
            box_rect = pygame.Rect(char_x, 0, char_w, char_h)
            
            # Determine if this box should be highlighted
            is_selected = (i == self.selected_index) and self.focused
            is_hovered = (i == self.mouse_over_index) and runtime_globals.INPUT_MODE in [runtime_globals.MOUSE_MODE, runtime_globals.TOUCH_MODE]
            
            # Visual settings based on state
            if is_selected:
                # Selected: White Background, Black Text (for keyboard mode)
                bg_color = (255, 255, 255) 
                text_color = (0, 0, 0)     
                border_color = (255, 255, 255) 
            elif is_hovered:
                # Hovered: Light grey background (for mouse mode)
                bg_color = (100, 100, 100)
                text_color = (255, 255, 255)
                border_color = (200, 200, 200)
            elif self.focused:
                # Focused but not selected: Dark grey
                bg_color = (60, 60, 60)
                text_color = (200, 200, 200)
                border_color = (100, 100, 100)
            else:
                # Unfocused: Very dark
                bg_color = colors.get('bg', (20, 20, 20))
                text_color = colors.get('fg', (150, 150, 150))
                border_color = colors.get('fg', (80, 80, 80))
            
            # Background
            pygame.draw.rect(surface, bg_color, box_rect, border_radius=5)
            # Border
            pygame.draw.rect(surface, border_color, box_rect, 2, border_radius=5)
            
            # Selection indicator underline
            if is_selected:
                pygame.draw.line(surface, text_color, 
                               (char_x + 8, char_h - 8), 
                               (char_x + char_w - 8, char_h - 8), 3)
            
            # Text
            char_surf = font.render(self.chars[i], True, text_color)
            char_rect = char_surf.get_rect(center=(char_x + char_w//2, char_h//2))
            surface.blit(char_surf, char_rect)
            
        return surface

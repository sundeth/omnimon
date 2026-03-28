"""
Toggle Button Component - A button that can be toggled on/off
"""
from ui.components.button import Button
from core import runtime_globals


class ToggleButton(Button):
    def __init__(self, x, y, width, height, text, on_toggle=None, **kwargs):
        super().__init__(x, y, width, height, text, callback=None, **kwargs)
        
        self.is_toggled = False
        self.on_toggle = on_toggle
        self.button_group = None  # Reference to ButtonGroup if part of one
        
    def set_toggled(self, toggled, silent=False):
        """Set the toggle state"""
        runtime_globals.game_console.log(f"[ToggleButton] set_toggled({toggled}, silent={silent}), current={self.is_toggled}")
        if self.is_toggled != toggled:
            self.is_toggled = toggled
            self.needs_redraw = True
            
            # Notify button group if we're being toggled on
            if toggled and self.button_group and not silent:
                runtime_globals.game_console.log(f"[ToggleButton] Notifying button_group")
                self.button_group.set_active_button(self)
            
            # Call toggle callback if not silent
            if not silent and self.on_toggle:
                runtime_globals.game_console.log(f"[ToggleButton] Calling on_toggle callback")
                self.on_toggle(self, toggled)
                
    def set_button_group(self, group):
        """Associate this button with a button group"""
        self.button_group = group
        
    def get_colors(self):
        """Get colors for toggle button based on toggle state"""
        # Get base colors from parent
        colors = super().get_colors()
        
        # If toggled, swap bg and fg colors
        if self.is_toggled:
            bg_color = colors["fg"]
            fg_color = colors["bg"]
            line_color = colors["fg"]
            
            return {
                "bg": bg_color,
                "fg": fg_color,
                "line": line_color
            }
        
        return colors
            
    def activate(self):
        """Handle activation (click or A button press)"""
        runtime_globals.game_console.log(f"[ToggleButton] activate() called, enabled={self.enabled}")
        if not self.enabled:
            return False
            
        # Toggle the state
        runtime_globals.game_console.log(f"[ToggleButton] Toggling from {self.is_toggled} to {not self.is_toggled}")
        self.set_toggled(not self.is_toggled)
        
        # Play sound
        if runtime_globals.game_sound:
            runtime_globals.game_sound.play("menu")
            
        return True

"""
Button Group - Manages a group of toggle buttons ensuring only one is active
"""


class ButtonGroup:
    def __init__(self):
        self.buttons = []
        self.active_button = None
        
    def add_button(self, button):
        """Add a button to the group"""
        if button not in self.buttons:
            self.buttons.append(button)
            button.set_button_group(self)
            
    def set_active_button(self, button):
        """Set the active button, deactivating all others"""
        if button not in self.buttons:
            return
            
        # Deactivate all other buttons
        for btn in self.buttons:
            if btn != button and btn.is_toggled:
                btn.set_toggled(False, silent=True)
                
        # Activate the specified button
        self.active_button = button
        if not button.is_toggled:
            button.set_toggled(True, silent=True)
            
    def get_active_button(self):
        """Get the currently active button"""
        return self.active_button
        
    def get_active_index(self):
        """Get the index of the active button"""
        if self.active_button and self.active_button in self.buttons:
            return self.buttons.index(self.active_button)
        return -1
        
    def clear_active(self):
        """Clear the active button, deactivating all buttons"""
        for btn in self.buttons:
            if btn.is_toggled:
                btn.set_toggled(False, silent=True)
        self.active_button = None

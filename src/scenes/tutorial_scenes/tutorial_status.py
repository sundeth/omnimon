"""
Tutorial Status Scene
Inherits from SceneStatus and overrides input handling for tutorial control.
"""

from scenes.scene_status import SceneStatus
from core import runtime_globals


class TutorialStatus(SceneStatus):
    """
    Tutorial-controlled version of SceneStatus.
    Overrides input handling to give tutorial full control.
    """
    
    def __init__(self) -> None:
        """Initialize the tutorial status scene."""
        super().__init__()
        
        # Tutorial control flags
        self.allow_exit = False
        self.allow_pet_selection = False
        self.on_exit_callback = None
        
        # Store original exit callback and replace with our own
        if self.pet_list:
            self._original_exit_callback = self.pet_list.on_exit_click
            self.pet_list.on_exit_click = self._tutorial_exit_handler
        
        runtime_globals.game_console.log("[TutorialStatus] Tutorial status scene initialized")
    
    def set_allow_exit(self, allow: bool, callback=None):
        """Set whether exiting is allowed and optional callback when exit happens."""
        self.allow_exit = allow
        self.on_exit_callback = callback
    
    def set_allow_pet_selection(self, allow: bool):
        """Set whether pet selection is allowed."""
        self.allow_pet_selection = allow
    
    def _tutorial_exit_handler(self):
        """Handle exit click in tutorial mode."""
        if self.allow_exit:
            runtime_globals.game_console.log("[TutorialStatus] Exit allowed - calling callback")
            if self.on_exit_callback:
                self.on_exit_callback()
            # Don't call original - let tutorial control the scene
        else:
            runtime_globals.game_console.log("[TutorialStatus] Exit blocked by tutorial")
            # Play cancel sound to indicate blocked
            if hasattr(runtime_globals, 'game_sound') and runtime_globals.game_sound:
                runtime_globals.game_sound.play("cancel")
    
    def handle_event(self, event) -> bool:
        """
        Handle input events with tutorial control.
        Only allows actions that the tutorial has enabled.
        """
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        event_type, event_data = event

        # Handle exit with B button - only if allowed
        if event_type == "B":
            if self.allow_exit:
                if self.on_exit_callback:
                    self.on_exit_callback()
                return True
            else:
                # Block exit - play cancel sound
                if hasattr(runtime_globals, 'game_sound') and runtime_globals.game_sound:
                    runtime_globals.game_sound.play("cancel")
                return True
        
        # Let UI manager handle clicks - our callback will intercept EXIT clicks
        if event_type in ["A", "LCLICK"]:
            # Let it pass through to UI manager
            return self.ui_manager.handle_event(event)
        
        # Allow navigation for visual feedback
        if event_type in ["LEFT", "RIGHT", "UP", "DOWN"]:
            return self.ui_manager.handle_event(event)
        
        # Allow mouse motion for hover effects
        if event_type == "MOUSE_MOTION":
            return self.ui_manager.handle_event(event)
        
        return True
    
    def get_pet_list_rect(self):
        """Get the pet list component bounds in base 240 coordinates."""
        return (0, 7, 240, 44)
    
    def get_basic_info_rect(self):
        """Get the basic info area bounds in base 240 coordinates."""
        return (0, 54, 240, 71)
    
    def get_care_info_rect(self):
        """Get the care info area (left column) bounds in base 240 coordinates."""
        margin = 12
        column_width = (240 - 2 * margin - 10) // 2
        return (margin, 125, column_width, 72)
    
    def get_battle_info_rect(self):
        """Get the battle info area (right column) bounds in base 240 coordinates."""
        margin = 12
        column_gap = 10
        column_width = (240 - 2 * margin - column_gap) // 2
        right_column_x = margin + column_width + column_gap
        return (right_column_x, 125, column_width, 72)
    
    def get_exit_button_rect(self):
        """Get the EXIT button bounds in base 240 coordinates."""
        return (174, 7, 42, 44)

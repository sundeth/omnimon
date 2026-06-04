"""
Tutorial Inventory Scene
Inherits from SceneInventory and overrides input handling for tutorial control.
"""

from scenes.scene_inventory import SceneInventory
from core import runtime_globals


class TutorialInventory(SceneInventory):
    """
    Tutorial-controlled version of SceneInventory.
    Overrides input handling to give tutorial full control.
    """
    
    def __init__(self) -> None:
        """Initialize the tutorial inventory scene."""
        super().__init__()
        
        # Tutorial control flags
        self.allow_exit = False
        self.allow_use_item = False
        self.allow_discard = False
        self.allow_navigation = True
        self.on_item_used_callback = None
        self.required_item_index = None  # If set, only this item index can be used
        
        runtime_globals.game_console.log("[TutorialInventory] Tutorial inventory scene initialized")
    
    def set_allow_exit(self, allow: bool):
        """Set whether exiting is allowed."""
        self.allow_exit = allow
    
    def set_allow_use_item(self, allow: bool, callback=None, required_index=None):
        """Set whether using items is allowed and optional callback.
        
        Args:
            allow: Whether item use is allowed
            callback: Callback when item is used
            required_index: If set, only this item index can be used (0-based)
        """
        self.allow_use_item = allow
        self.on_item_used_callback = callback
        self.required_item_index = required_index
        
        # Force selection to the required item immediately
        if required_index is not None and self.item_list:
            self.item_list.set_selected_index(required_index, instant_scroll=True)
            runtime_globals.game_console.log(f"[TutorialInventory] Forced selection to index {required_index}")
    
    def set_allow_discard(self, allow: bool):
        """Set whether discarding items is allowed."""
        self.allow_discard = allow
    
    def _check_item_allowed(self, index=None):
        """Check if an item at the given index is allowed to be used.
        
        Args:
            index: The item index to check. If None, uses currently selected index.
        """
        if self.required_item_index is None:
            return True
        if index is not None:
            return index == self.required_item_index
        if self.item_list:
            return self.item_list.selected_index == self.required_item_index
        return False
    
    def _get_clicked_item_index(self, mouse_pos):
        """Calculate which item index would be clicked at the given position.
        
        Returns the item index or -1 if click is not on an item.
        Mouse position is in screen coordinates.
        """
        if not self.item_list or not hasattr(self.item_list, 'items_rect'):
            return -1
        
        # Get the item list's screen rect (scaled)
        if not hasattr(self.item_list, 'rect') or not self.item_list.rect:
            return -1
        
        screen_rect = self.item_list.rect
        
        # Check if mouse is within the item list's screen rect
        if not screen_rect.collidepoint(mouse_pos):
            return -1
        
        # Convert mouse pos to local coordinates relative to item list (in screen coords)
        local_x = mouse_pos[0] - screen_rect.x
        local_y = mouse_pos[1] - screen_rect.y
        
        # Get items_rect (in base coordinates) and scale to screen
        items_rect = self.item_list.items_rect
        if not items_rect:
            return -1
        
        # Get UI scale to convert items_rect to screen coordinates
        ui_scale = self.ui_manager.ui_scale if self.ui_manager else 1
        
        # items_rect is in base coordinates, scale to screen
        scaled_items_rect_y = items_rect.y * ui_scale
        scaled_items_rect_height = items_rect.height * ui_scale
        
        # Check if within items area (in screen-scaled local coords)
        items_local_y = local_y - scaled_items_rect_y
        
        if items_local_y < 0 or items_local_y >= scaled_items_rect_height:
            return -1
        
        # Get item dimensions (already scaled in the component)
        item_size = self.item_list.item_size  # Already scaled
        item_spacing = self.item_list.item_spacing  # Already scaled
        scroll_offset = getattr(self.item_list, 'scroll_offset', 0)  # Already scaled
        
        # Calculate item index
        item_pos = items_local_y + scroll_offset
        item_index = int(item_pos // (item_size + item_spacing))
        
        # Validate index
        if 0 <= item_index < len(self.item_list.items):
            return item_index
        
        return -1
    
    def handle_event(self, event) -> bool:
        """
        Handle input events with tutorial control.
        Only allows actions that the tutorial has enabled.
        """
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        event_type, event_data = event

        # Handle exit - only if allowed
        if event_type == "B":
            if self.allow_exit:
                from utils.scene_utils import change_scene
                change_scene("game")
                return True
            else:
                # Block exit
                return True
        
        # Handle click events - check for item selection, but always pass through for button clicks
        if event_type == "LCLICK":
            # Get mouse position to determine which item would be clicked
            mouse_pos = None
            if event_data and "pos" in event_data:
                mouse_pos = event_data["pos"]
            elif hasattr(runtime_globals, 'input_manager') and runtime_globals.input_manager:
                mouse_pos = runtime_globals.input_manager.get_mouse_position()
            
            if mouse_pos and self.item_list and self.required_item_index is not None:
                # Check if click is on item list - determine which item would be selected
                clicked_index = self._get_clicked_item_index(mouse_pos)
                runtime_globals.game_console.log(f"[TutorialInventory] Click detected, would select index {clicked_index}, required={self.required_item_index}")
                
                if clicked_index >= 0:
                    # Click is on an item - check if it's the allowed one
                    if clicked_index != self.required_item_index:
                        # Wrong item clicked - block, play cancel, and ensure correct item stays selected
                        if hasattr(runtime_globals, 'game_sound') and runtime_globals.game_sound:
                            runtime_globals.game_sound.play("cancel")
                        # Force selection back to the required item
                        self.item_list.set_selected_index(self.required_item_index, instant_scroll=True)
                        return True
            
            # Always pass LCLICK to parent so UI buttons (Use, Discard) can be handled
            # The on_use_button() and on_discard_button() overrides will check permissions
            super().handle_event(event)
            return True  # Always return True to keep tutorial system working
        
        # Handle A button - use currently selected item
        if event_type == "A":
            if self.allow_use_item and self._check_item_allowed():
                # Let the parent handle it
                super().handle_event(event)
            else:
                # Block item use - wrong item selected
                if hasattr(runtime_globals, 'game_sound') and runtime_globals.game_sound:
                    runtime_globals.game_sound.play("cancel")
            return True
        
        # Block UP/DOWN navigation when a specific item is required - keep selection locked
        if event_type in ["UP", "DOWN"]:
            if self.required_item_index is not None:
                # Don't allow changing selection when specific item is required
                return True
            if self.allow_navigation:
                super().handle_event(event)
            return True
        
        # Allow LEFT/RIGHT navigation for other UI elements
        if event_type in ["LEFT", "RIGHT"]:
            if self.allow_navigation:
                super().handle_event(event)
            return True
        
        return True
    
    def on_use_button(self):
        """Override use button to respect tutorial control and item validation."""
        if self.allow_use_item and self._check_item_allowed():
            # Get selected item and use it
            # This will call _use_item which calls our overridden _return_to_game
            super().on_use_button()
            # Callback is triggered in _return_to_game
        else:
            # Play cancel sound - either not allowed or wrong item
            if hasattr(runtime_globals, 'game_sound') and runtime_globals.game_sound:
                runtime_globals.game_sound.play("cancel")
    
    def on_item_activated(self, item, index=0, use_immediately=False):
        """Override item activation to respect tutorial control and item validation."""
        # Check if this specific item index is allowed
        if self.allow_use_item and self._check_item_allowed(index):
            # This will eventually call _use_item which calls our overridden _return_to_game
            super().on_item_activated(item, index, use_immediately)
            # Callback is triggered in _return_to_game
        else:
            # Play cancel sound
            if hasattr(runtime_globals, 'game_sound') and runtime_globals.game_sound:
                runtime_globals.game_sound.play("cancel")
    
    def on_discard_button(self):
        """Override discard button to block it during tutorial."""
        # Always block discard in tutorial
        if hasattr(runtime_globals, 'game_sound') and runtime_globals.game_sound:
            runtime_globals.game_sound.play("cancel")
        runtime_globals.game_console.log("[TutorialInventory] Discard blocked in tutorial")
    
    def get_item_list_rect(self):
        """Get the item list component bounds in base 240 coordinates."""
        # Item list at x=0, y=27, width=156, height=176
        return (0, 27, 156, 176)
    
    def get_description_panel_rect(self):
        """Get the description panel bounds in base 240 coordinates."""
        # Text panel at x=158, y=24, width=78, height=106
        return (158, 24, 78, 106)
    
    def get_first_item_rect(self):
        """Get the first item slot bounds in base 240 coordinates."""
        # First item after title, approximately y=39 (27 + ~12), height ~31
        return (0, 39, 156, 31)
    
    def get_second_item_rect(self):
        """Get the second item slot bounds in base 240 coordinates."""
        # Second item after first, approximately y=70 (39 + 31), height ~31
        return (0, 70, 156, 31)
    
    def get_use_button_rect(self):
        """Get the USE button bounds in base 240 coordinates."""
        # USE button at x=158, y=134, width=80, height=23
        return (158, 134, 80, 23)
    
    def _return_to_game(self):
        """
        Override parent method to NOT change scene during tutorial.
        The tutorial controls scene transitions.
        """
        # During tutorial, don't actually change scene
        # Just notify the tutorial that item was used
        if self.on_item_used_callback:
            self.on_item_used_callback()
        # Don't call super()._return_to_game() which would exit the scene

"""
OmninetLinkView - Omninet account linking dialog
Shows code entry for linking device via pairing code from Module Editor
"""
import threading
from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.label import Label
from components.ui.code_entry import CodeEntry
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals
from core.service.omninet_service import omninet_service


class OmninetLinkView:
    """Omninet device linking dialog view."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback,
                 return_view="main_menu", discord_module=None):
        """Initialize the Omninet link dialog view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            return_view: View to return to after linking (or cancelling)
            discord_module: Reference to the Discord module (unused, for compatibility)
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self.return_view = return_view
        
        # State
        self._validating = False
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.link_title = None
        self.code_entry = None
        self.instruction_label = None
        self.confirm_button = None
        self.cancel_button = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the UI components."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "CONNECT")
        self.ui_manager.add_component(self.title_scene)
        
        # Link title
        self.link_title = Label(0, 40, "Omninet Pairing", is_title=True)
        self.ui_manager.add_component(self.link_title)
        
        # Code entry (4 characters)
        self.code_entry = CodeEntry((BASE_RESOLUTION - 190) // 2, 80, length=4)
        self.ui_manager.add_component(self.code_entry)
        
        # Instruction label
        self.instruction_label = Label(0, 140, "Enter code from Module Editor", is_title=False)
        self.ui_manager.add_component(self.instruction_label)
        
        # Buttons
        btn_y = 170
        btn_w = 80
        btn_h = 30
        gap = 20
        
        self.confirm_button = Button(
            (BASE_RESOLUTION // 2) - btn_w - (gap // 2), btn_y, btn_w, btn_h,
            "Confirm", self._on_confirm
        )
        self.ui_manager.add_component(self.confirm_button)
        
        self.cancel_button = Button(
            (BASE_RESOLUTION // 2) + (gap // 2), btn_y, btn_w, btn_h,
            "Cancel", self._on_cancel
        )
        self.ui_manager.add_component(self.cancel_button)
        
        # Set focus to code entry
        self.ui_manager.set_focused_component(self.code_entry)
        
        runtime_globals.game_console.log("[OmninetLinkView] UI setup complete")
    
    def _on_confirm(self):
        """Confirm button clicked."""
        if self._validating:
            return
        
        # Get code from code entry
        code = ''.join(self.code_entry.chars) if hasattr(self.code_entry, 'chars') else ""
        
        if len(code) != 4:
            self.instruction_label.set_text("Enter 4-character code")
            return
        
        runtime_globals.game_console.log(f"[OmninetLinkView] Validating code: {code}")
        self._validating = True
        self.instruction_label.set_text("Connecting to server...")
        self.confirm_button.enabled = False
        self.cancel_button.enabled = False
        
        # Show connecting message
        runtime_globals.game_message.add_slide("Connecting...", (255, 255, 255), 90)
        
        # Validate in background thread
        def validate_async():
            success, message, user_info = omninet_service.validate_pairing_code(code)
            
            # Schedule UI update on main thread
            self._on_validation_complete(success, message, user_info)
        
        threading.Thread(target=validate_async, daemon=True).start()
    
    def _on_validation_complete(self, success: bool, message: str, user_info):
        """Called when pairing code validation completes."""
        self._validating = False
        self.confirm_button.enabled = True
        self.cancel_button.enabled = True
        
        if success:
            username = user_info.get('nickname', 'User') if user_info else 'User'
            runtime_globals.game_console.log(f"[OmninetLinkView] Linked as: {username}")
            runtime_globals.game_sound.play("menu")
            runtime_globals.game_message.add_slide(f"Linked as {username}!", (0, 231, 58), 120)
            
            # Return to the config submenu
            self.change_view(self.return_view, initial_submenu="config")
        else:
            runtime_globals.game_console.log(f"[OmninetLinkView] Link failed: {message}")
            runtime_globals.game_sound.play("error")
            self.instruction_label.set_text(message[:32])  # Truncate long messages
    
    def _on_cancel(self):
        """Cancel button clicked."""
        runtime_globals.game_sound.play("cancel")
        # Return to config submenu
        self.change_view(self.return_view, initial_submenu="config")
    
    def update(self):
        """Update the view."""
        pass
    
    def draw(self, surface):
        """Draw view-specific elements."""
        pass
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        if event_type == "B":
            self._on_cancel()
            return True
        elif event_type == "A":
            self._on_confirm()
            return True
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        components = [
            self.background, self.title_scene, self.link_title,
            self.code_entry, self.instruction_label,
            self.confirm_button, self.cancel_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[OmninetLinkView] Cleanup complete")

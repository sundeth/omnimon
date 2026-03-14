"""
PetSelectionView - Pet selection for battles
Allows selecting pets for WiFi or Discord battles
"""
from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.label import Label
from components.ui.pet_selector import PetSelector
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals
from core.utils.pet_utils import get_battle_pvp_targets


class PetSelectionView:
    """Pet selection view for WiFi/Discord battles."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback, 
                 is_online_mode=False, is_dcom_mode=False, max_pets=4,
                 return_view="main_menu", discord_module=None):
        """Initialize the pet selection view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            is_online_mode: True if this is an online (Discord) battle
            is_dcom_mode: True if this is a DCom battle
            max_pets: Maximum number of pets that can be selected
            return_view: View to return to on back (e.g., "main_menu" or submenu hint)
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self.is_online_mode = is_online_mode
        self.is_dcom_mode = is_dcom_mode
        self.max_pets = 1 if is_dcom_mode else max_pets
        self.return_view = return_view
        
        # Selected pets
        self.selected_pets = []
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.pet_selector = None
        self.instructions_label = None
        self.confirm_button = None
        self.back_button = None
        
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
        
        # Pet selector
        selector_width = 220
        selector_height = 120
        selector_x = (BASE_RESOLUTION - selector_width) // 2
        selector_y = 40
        
        self.pet_selector = PetSelector(selector_x, selector_y, selector_width, selector_height)
        self.pet_selector.set_pets(get_battle_pvp_targets())
        self.pet_selector.set_interactive(True)
        self.ui_manager.add_component(self.pet_selector)
        
        # Instructions
        if self.is_dcom_mode:
            instruction_text = "Select 1 pet for DCom battle"
        else:
            instruction_text = f"Select up to {self.max_pets} pets. Press START when ready."
        
        self.instructions_label = Label(10, 165, instruction_text, is_title=False)
        self.ui_manager.add_component(self.instructions_label)
        
        # Confirm button
        confirm_width = 100
        confirm_height = 35
        confirm_x = 20
        confirm_y = 195
        
        self.confirm_button = Button(
            confirm_x, confirm_y, confirm_width, confirm_height,
            "CONFIRM", self._on_confirm
        )
        self.ui_manager.add_component(self.confirm_button)
        
        # Back button
        back_width = 80
        back_height = 35
        back_x = BASE_RESOLUTION - back_width - 20
        back_y = 195
        
        self.back_button = Button(
            back_x, back_y, back_width, back_height,
            "BACK", self._on_back
        )
        self.ui_manager.add_component(self.back_button)
        
        runtime_globals.game_console.log("[PetSelectionView] UI setup complete")
    
    def _on_confirm(self):
        """Confirm button clicked."""
        # Get selected pets from selector
        self.selected_pets = self.pet_selector.get_selected_pets() if hasattr(self.pet_selector, 'get_selected_pets') else []
        
        if not self.selected_pets:
            runtime_globals.game_console.log("[PetSelectionView] No pets selected")
            return
        
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log(f"[PetSelectionView] Selected {len(self.selected_pets)} pets")
        
        if self.is_dcom_mode:
            self.change_view("dcom", selected_pets=self.selected_pets)
        elif self.is_online_mode:
            self.change_view("discord", selected_pets=self.selected_pets, is_online_mode=True)
        else:
            self.change_view("wifi_hosting", selected_pets=self.selected_pets, is_online_mode=False)
    
    def _on_back(self):
        """Back button clicked."""
        runtime_globals.game_sound.play("cancel")
        # Return to local_battle submenu for DCom/WiFi, or main menu for Discord
        if self.is_dcom_mode or not self.is_online_mode:
            # For local battles (DCom/WiFi), return to main_menu with local_battle submenu shown
            self.change_view("main_menu", initial_submenu="local_battle")
        else:
            # For online battles (Discord), return to main_menu with arena submenu shown
            self.change_view("main_menu", initial_submenu="arena")
    
    def update(self):
        """Update the view."""
        pass
    
    def draw(self, surface):
        """Draw additional elements."""
        pass
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        if event_type == "B":
            self._on_back()
            return True
        elif event_type == "A":
            self._on_confirm()
            return True
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        components = [
            self.background, self.title_scene, self.pet_selector,
            self.instructions_label, self.confirm_button, self.back_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[PetSelectionView] Cleanup complete")
    
    def get_selected_pets(self):
        """Get the list of selected pets."""
        return self.selected_pets

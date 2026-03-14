"""
ProtocolView - Battle protocol selection
Shows protocol options for versus battles using Menu component
"""
import pygame
from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.background import Background
from components.ui.menu import Menu
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals
from core.combat.sim.models import BattleProtocol


class ProtocolView:
    """Protocol selection view for versus battles."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback, pet1, pet2):
        """Initialize the Protocol view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            pet1: First pet for battle
            pet2: Second pet for battle
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self.pet1 = pet1
        self.pet2 = pet2
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.protocol_menu = None
        
        # Protocol options mapping
        self.protocol_options = [
            "DM (Original)",
            "DM20 (V-Pet/Pendulum)",
            "PEN20 (Pendulum 20th)",
            "DMX (Digimon X)",
            "DMC (Color)",
            "Cancel"
        ]
        
        self.protocol_mapping = {
            0: BattleProtocol.DM_BS,       # DM (Original)
            1: BattleProtocol.DM20_BS,     # DM20 (V-Pet/Pendulum)
            2: BattleProtocol.PEN20_BS,    # PEN20 (Pendulum 20th)
            3: BattleProtocol.DMX_BS,      # DMX (Digimon X)
            4: BattleProtocol.DMC_BS,      # DMC (Color)
            5: None                         # Cancel
        }
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "BATTLE")
        self.ui_manager.add_component(self.title_scene)
        
        # Protocol selection menu (same style as DCom)
        self.protocol_menu = Menu(width=200, height=140)
        self.protocol_menu.open(self.protocol_options, self._on_protocol_select)
        self.ui_manager.add_component(self.protocol_menu)
        self.ui_manager.set_active_menu(self.protocol_menu)
        
        runtime_globals.game_console.log("[ProtocolView] UI setup complete")
    
    def _on_protocol_select(self, index):
        """Protocol selected from menu."""
        # Handle cancel
        if index == 5 or index >= len(self.protocol_options):
            self._on_cancel()
            return
        
        protocol = self.protocol_mapping.get(index)
        if protocol is None:
            self._on_cancel()
            return
        
        runtime_globals.game_sound.play("menu")
        
        protocol_name = self.protocol_options[index]
        runtime_globals.game_console.log(f"[ProtocolView] Protocol selected: {protocol_name}")
        
        # Close menu before transitioning
        if self.protocol_menu:
            self.protocol_menu.close()
            if self.ui_manager.active_menu == self.protocol_menu:
                self.ui_manager.active_menu = None
        
        # Change to versus battle view
        self.change_view("versus_battle", pet1=self.pet1, pet2=self.pet2, protocol=protocol)
    
    def _on_cancel(self):
        """Handle cancel button."""
        runtime_globals.game_sound.play("cancel")
        
        # Close menu before transitioning
        if self.protocol_menu:
            self.protocol_menu.close()
            if self.ui_manager.active_menu == self.protocol_menu:
                self.ui_manager.active_menu = None
        
        self.change_view("versus")
    
    def cleanup(self):
        """Remove all UI components."""
        if self.background:
            self.ui_manager.remove_component(self.background)
        if self.title_scene:
            self.ui_manager.remove_component(self.title_scene)
        if self.protocol_menu:
            self.protocol_menu.close()
            self.ui_manager.remove_component(self.protocol_menu)
    
    def update(self):
        """Update the view."""
        pass
    
    def draw(self, surface: pygame.Surface):
        """Draw the view."""
        pass
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        event_type, event_data = event
        if event_type == "B":
            self._on_cancel()

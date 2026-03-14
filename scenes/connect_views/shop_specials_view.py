"""
ShopSpecialsView - Browse and purchase special limited items
Currently disabled - shows placeholder message.
"""
from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.image import Image
from components.ui.label import Label
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals, game_globals


class ShopSpecialsView:
    """Special items shop view - currently disabled."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback, discord_module=None):
        """Initialize the shop specials view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            discord_module: Reference to the Discord module (unused, for compatibility)
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.coin_icon = None
        self.coin_label = None
        self.message_label = None
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
        self.title_scene = TitleScene(0, 9, "SPECIALS")
        self.ui_manager.add_component(self.title_scene)
        
        # Coin display
        self._setup_coin_display()
        
        # Coming soon message
        self.message_label = Label(0, BASE_RESOLUTION // 2 - 10, "Coming Soon!", is_title=True)
        self.ui_manager.add_component(self.message_label)
        
        self.sub_message_label = Label(0, BASE_RESOLUTION // 2 + 15, "Special items will be available soon.", is_title=False)
        self.ui_manager.add_component(self.sub_message_label)
        
        # Back button (bottom)
        btn_height = 24
        self.back_button = Button(
            10, BASE_RESOLUTION - btn_height - 10, 60, btn_height,
            "Back", self._on_back,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
        )
        self.ui_manager.add_component(self.back_button)
        
        runtime_globals.game_console.log("[ShopSpecialsView] UI setup complete")
    
    def _setup_coin_display(self):
        """Setup the coin icon and amount display."""
        icon_size = 16
        label_width = 55
        margin = 10
        label_x = BASE_RESOLUTION - margin - label_width
        coin_y = 9 + 4
        
        coins = getattr(game_globals, 'coins', 0)
        self.coin_label = Label(label_x, coin_y, str(coins), is_title=False)
        self.ui_manager.add_component(self.coin_label)
        
        icon_x = label_x - icon_size - 4
        self.coin_icon = Image(icon_x, coin_y - 2, icon_size, icon_size, 
                               image_path="assets/ui/Shop_Coin_1.png")
        self.ui_manager.add_component(self.coin_icon)
    
    def _on_back(self):
        """Back button clicked."""
        runtime_globals.game_sound.play("cancel")
        self.change_view("shop")
    
    def update(self):
        """Update the view."""
        coins = getattr(game_globals, 'coins', 0)
        if self.coin_label:
            self.coin_label.set_text(str(coins))
    
    def draw(self, surface):
        """Draw view-specific elements."""
        pass
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        if event_type == "B":
            self._on_back()
            return True
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        components = [
            self.background, self.title_scene,
            self.coin_icon, self.coin_label,
            self.message_label, self.sub_message_label,
            self.back_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[ShopSpecialsView] Cleanup complete")

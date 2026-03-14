"""
ShopView - Main shop menu
Shows coin balance and shop category buttons
"""
import pygame

from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.image import Image
from components.ui.label import Label
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals, game_globals
from core.utils.asset_utils import image_load


class ShopView:
    """Main shop view with category buttons."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback, discord_module=None):
        """Initialize the shop view.
        
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
        
        # Category buttons
        self.modules_button = None
        self.items_button = None
        self.gameplay_button = None
        self.cosmetics_button = None
        self.specials_button = None
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
        self.title_scene = TitleScene(0, 9, "SHOP")
        self.ui_manager.add_component(self.title_scene)
        
        # Coin display (top left)
        self._setup_coin_display()
        
        # Category buttons (2 columns x 3 rows)
        self._setup_category_buttons()
        
        runtime_globals.game_console.log("[ShopView] UI setup complete")
    
    def _setup_coin_display(self):
        """Setup the coin icon and amount display."""
        # Position at top right, aligned with title scene (y=9)
        # Title scene is 120 width, so position coin display on the right side
        icon_size = 16
        label_width = 55  # Reserve space for coin amount
        
        # Right align: BASE_RESOLUTION - margin - label_width
        margin = 10
        label_x = BASE_RESOLUTION - margin - label_width
        coin_y = 9 + 4  # Align with title top (y=9) + small offset
        
        # Coin amount label (right aligned)
        coins = getattr(game_globals, 'coins', 0)
        self.coin_label = Label(label_x, coin_y, str(coins), is_title=False)
        self.ui_manager.add_component(self.coin_label)
        
        # Coin icon (left of label)
        icon_x = label_x - icon_size - 4
        self.coin_icon = Image(icon_x, coin_y - 2, icon_size, icon_size, 
                               image_path="assets/ui/Shop_Coin_1.png")
        self.ui_manager.add_component(self.coin_icon)
    
    def _setup_category_buttons(self):
        """Setup the 6 category buttons in 2 columns x 3 rows."""
        # Button dimensions
        btn_width = 90
        btn_height = 62
        
        # Calculate positions
        title_bottom = 29
        vertical_gap = (BASE_RESOLUTION - title_bottom - (3 * btn_height)) // 4
        
        row1_y = title_bottom + vertical_gap
        row2_y = row1_y + btn_height + vertical_gap
        row3_y = row2_y + btn_height + vertical_gap
        
        horizontal_margin = 17
        horizontal_gap = (BASE_RESOLUTION - (2 * horizontal_margin) - (2 * btn_width))
        
        col1_x = horizontal_margin
        col2_x = col1_x + btn_width + horizontal_gap
        
        # Column 1: Modules, Gameplay, Specials
        self.modules_button = Button(
            col1_x, row1_y, btn_width, btn_height, "",
            self._on_modules_selected,
            decorators=["Shop_Modules"],
            cut_corners={'tl': False, 'tr': False, 'bl': True, 'br': True}
        )
        self.ui_manager.add_component(self.modules_button)
        
        self.gameplay_button = Button(
            col1_x, row2_y, btn_width, btn_height, "",
            self._on_gameplay_selected,
            decorators=["Shop_Gameplay"],
            cut_corners={'tl': False, 'tr': False, 'bl': True, 'br': True}
        )
        self.ui_manager.add_component(self.gameplay_button)
        
        self.specials_button = Button(
            col1_x, row3_y, btn_width, btn_height, "",
            self._on_specials_selected,
            decorators=["Shop_Specials"],
            cut_corners={'tl': False, 'tr': False, 'bl': True, 'br': True}
        )
        self.ui_manager.add_component(self.specials_button)
        
        # Column 2: Items, Cosmetics, Back
        self.items_button = Button(
            col2_x, row1_y, btn_width, btn_height, "",
            self._on_items_selected,
            decorators=["Shop_Items"],
            cut_corners={'tl': False, 'tr': False, 'bl': True, 'br': True}
        )
        self.ui_manager.add_component(self.items_button)
        
        self.cosmetics_button = Button(
            col2_x, row2_y, btn_width, btn_height, "",
            self._on_cosmetics_selected,
            decorators=["Shop_Cosmetics"],
            cut_corners={'tl': False, 'tr': False, 'bl': True, 'br': True}
        )
        self.ui_manager.add_component(self.cosmetics_button)
        
        self.back_button = Button(
            col2_x, row3_y, btn_width//1.5, btn_height//3, "BACK",
            self._on_back,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
        )
        self.ui_manager.add_component(self.back_button)
        
        # In Free Mode, disable all categories except Modules
        if game_globals.is_free_mode():
            self.items_button.enabled = False
            self.gameplay_button.enabled = False
            self.cosmetics_button.enabled = False
            self.specials_button.enabled = False
            runtime_globals.game_console.log("[ShopView] Free Mode: only Modules category enabled")
    
    def _on_modules_selected(self):
        """Modules button clicked."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[ShopView] Modules selected")
        self.change_view("shop_modules")
    
    def _on_items_selected(self):
        """Items button clicked."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[ShopView] Items selected")
        self.change_view("shop_items")
    
    def _on_gameplay_selected(self):
        """Gameplay button clicked."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[ShopView] Gameplay selected")
        self.change_view("shop_gameplay")
    
    def _on_cosmetics_selected(self):
        """Cosmetics button clicked."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[ShopView] Cosmetics selected")
        self.change_view("shop_cosmetics")
    
    def _on_specials_selected(self):
        """Specials button clicked."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[ShopView] Specials selected")
        self.change_view("shop_specials")
    
    def _on_back(self):
        """Back button clicked."""
        runtime_globals.game_sound.play("cancel")
        self.change_view("main_menu")
    
    def update(self):
        """Update the view."""
        # Update coin display (hide in free mode)
        if game_globals.is_free_mode():
            if self.coin_label:
                self.coin_label.set_text("FREE")
        else:
            coins = getattr(game_globals, 'coins', 0)
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
            self.modules_button, self.items_button,
            self.gameplay_button, self.cosmetics_button,
            self.specials_button, self.back_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[ShopView] Cleanup complete")

"""
ShopModulesView - Browse and purchase game modules
Shows list of available modules with details view for purchase/download.
"""
import threading
import pygame

from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.image import Image
from components.ui.label import Label
from components.ui.text_panel import TextPanel
from components.ui.shop_list import ShopList, ShopModuleItem
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals, game_globals
from core.service.omninet_service import omninet_service
from core.utils.asset_utils import image_load


class ShopModulesView:
    """Module shop view with list and detail subviews."""
    
    STATE_LIST = "list"
    STATE_DETAIL = "detail"
    STATE_LOADING = "loading"
    
    def __init__(self, ui_manager: UIManager, change_view_callback, discord_module=None):
        """Initialize the shop modules view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            discord_module: Reference to the Discord module (unused, for compatibility)
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        
        self.state = self.STATE_LOADING
        self.selected_item = None
        self.modules_data = []
        
        # List view components
        self.background = None
        self.title_scene = None
        self.coin_icon = None
        self.coin_label = None
        self.shop_list = None
        self.loading_label = None
        self.back_button = None
        
        # Detail view components
        self.detail_components = []
        
        self._setup_ui()
        self._load_modules_async()
    
    def _setup_ui(self):
        """Setup the UI components."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "MODULES")
        self.ui_manager.add_component(self.title_scene)
        
        # Coin display
        self._setup_coin_display()
        
        # Loading label
        self.loading_label = Label(0, BASE_RESOLUTION // 2, "Loading...", is_title=False)
        self.ui_manager.add_component(self.loading_label)
        
        # Back button (bottom)
        btn_height = 24
        self.back_button = Button(
            10, BASE_RESOLUTION - btn_height - 10, 60, btn_height,
            "Back", self._on_back,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
        )
        self.ui_manager.add_component(self.back_button)
        
        runtime_globals.game_console.log("[ShopModulesView] UI setup complete")
    
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
    
    def _setup_list_view(self):
        """Setup the list view with loaded modules."""
        if self.shop_list:
            self.ui_manager.remove_component(self.shop_list)
        
        # Remove loading label
        if self.loading_label:
            self.ui_manager.remove_component(self.loading_label)
            self.loading_label = None
        
        # Create shop list
        list_top = 35
        list_height = BASE_RESOLUTION - list_top - 40
        self.shop_list = ShopList(
            5, list_top, BASE_RESOLUTION - 10, list_height,
            mode=ShopList.MODE_MODULES,
            on_item_selected=self._on_module_selected
        )
        
        # Convert API data to ShopModuleItem objects
        items = []
        for mod in self.modules_data:
            owned = game_globals.purchases.owns_module(mod.get('id', ''))
            items.append(ShopModuleItem(
                item_id=mod.get('id', ''),
                name=mod.get('name', 'Unknown'),
                price=mod.get('price', 0),
                owned=owned,
                creator=mod.get('author', ''),
                version=mod.get('version', '1.0'),
                official=mod.get('official', False),
                description=mod.get('description', ''),
                size_mb=mod.get('size_mb', 0),
                contributors=mod.get('contributors', ''),
                updated_at=mod.get('updated_at', ''),
                category=mod.get('category', '')
            ))
        
        self.shop_list.set_items(items)
        self.ui_manager.add_component(self.shop_list)
        
        self.state = self.STATE_LIST
    
    def _setup_detail_view(self, item: ShopModuleItem):
        """Setup the detail view for a selected module."""
        self._clear_detail_components()
        
        # Hide list
        if self.shop_list:
            self.shop_list.visible = False
        
        padding = 10
        y_offset = 35
        
        # Module name (large)
        name_label = Label(0, y_offset, item.name, is_title=True)
        self.ui_manager.add_component(name_label)
        self.detail_components.append(name_label)
        y_offset += 25
        
        # Official badge
        if item.official:
            official_label = Label(padding, y_offset, "★ Official Module", is_title=False)
            self.ui_manager.add_component(official_label)
            self.detail_components.append(official_label)
            y_offset += 18
        
        # Author
        if item.creator:
            author_label = Label(padding, y_offset, f"Author: {item.creator}", is_title=False)
            self.ui_manager.add_component(author_label)
            self.detail_components.append(author_label)
            y_offset += 16
        
        # Contributors
        if item.contributors:
            contrib_label = Label(padding, y_offset, f"Contributors: {item.contributors[:40]}", is_title=False)
            self.ui_manager.add_component(contrib_label)
            self.detail_components.append(contrib_label)
            y_offset += 16
        
        # Version and size
        info_text = f"v{item.version}"
        if item.size_mb > 0:
            info_text += f" | {item.size_mb:.1f} MB"
        info_label = Label(padding, y_offset, info_text, is_title=False)
        self.ui_manager.add_component(info_label)
        self.detail_components.append(info_label)
        y_offset += 16
        
        # Last updated
        if item.updated_at:
            updated_label = Label(padding, y_offset, f"Updated: {item.updated_at[:10]}", is_title=False)
            self.ui_manager.add_component(updated_label)
            self.detail_components.append(updated_label)
            y_offset += 16
        
        y_offset += 5
        
        # Description panel
        desc_height = 60
        desc_panel = TextPanel(padding, y_offset, BASE_RESOLUTION - padding * 2, desc_height, 
                               item.description or "No description available.")
        self.ui_manager.add_component(desc_panel)
        self.detail_components.append(desc_panel)
        y_offset += desc_height + 10
        
        # Price display
        if item.owned:
            price_text = "Already Owned"
        elif game_globals.is_free_mode():
            price_text = "FREE"
        else:
            price_text = f"Price: {item.price} coins"
        price_label = Label(0, y_offset, price_text, is_title=False)
        self.ui_manager.add_component(price_label)
        self.detail_components.append(price_label)
        y_offset += 25
        
        # Buttons
        btn_width = 80
        btn_height = 28
        btn_y = BASE_RESOLUTION - btn_height - 10
        
        # Buy/Download button
        if item.owned:
            action_text = "Download"
            action_callback = lambda: self._on_download(item)
        elif game_globals.is_free_mode():
            # Free mode: download for free without buying
            action_text = "Download"
            action_callback = lambda: self._on_free_download(item)
        else:
            action_text = "Buy"
            action_callback = lambda: self._on_buy(item)
        
        action_button = Button(
            BASE_RESOLUTION - btn_width - padding, btn_y, btn_width, btn_height,
            action_text, action_callback,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
        )
        self.ui_manager.add_component(action_button)
        self.detail_components.append(action_button)
        
        # Back to list button
        back_list_button = Button(
            padding, btn_y, 60, btn_height,
            "Back", self._on_detail_back,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
        )
        self.ui_manager.add_component(back_list_button)
        self.detail_components.append(back_list_button)
        
        self.state = self.STATE_DETAIL
    
    def _clear_detail_components(self):
        """Remove all detail view components."""
        for comp in self.detail_components:
            if comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        self.detail_components.clear()
    
    def _load_modules_async(self):
        """Load modules from server in background thread."""
        def fetch_modules():
            try:
                success, data = omninet_service.get_shop_modules()
                if success and data:
                    self.modules_data = data
                else:
                    self.modules_data = []
                    runtime_globals.game_console.log(f"[ShopModulesView] Failed to load modules")
            except Exception as e:
                runtime_globals.game_console.log(f"[ShopModulesView] Error loading modules: {e}")
                self.modules_data = []
            
            # Schedule UI update on main thread
            self._on_modules_loaded()
        
        threading.Thread(target=fetch_modules, daemon=True).start()
    
    def _on_modules_loaded(self):
        """Called when modules are loaded from server."""
        self._setup_list_view()
    
    def _on_module_selected(self, item: ShopModuleItem):
        """Handle module selection from list."""
        runtime_globals.game_sound.play("menu")
        self.selected_item = item
        self._setup_detail_view(item)
    
    def _on_buy(self, item: ShopModuleItem):
        """Handle buy button click."""
        coins = getattr(game_globals, 'coins', 0)
        
        if coins < item.price:
            runtime_globals.game_sound.play("error")
            runtime_globals.game_message.add_slide("Not enough coins!", (255, 100, 100), 90)
            return
        
        runtime_globals.game_sound.play("menu")
        
        # Attempt purchase via API
        def do_purchase():
            try:
                success, message = omninet_service.purchase_item('module', item.id)
                if success:
                    # Update local state
                    game_globals.coins -= item.price
                    game_globals.purchases.add_module(item.id, item.name)
                    game_globals.save()
                    
                    item.owned = True
                    runtime_globals.game_message.add_slide("Purchase successful!", (0, 231, 58), 90)
                    
                    # Refresh detail view
                    self._setup_detail_view(item)
                else:
                    runtime_globals.game_sound.play("error")
                    runtime_globals.game_message.add_slide(message or "Purchase failed", (255, 100, 100), 90)
            except Exception as e:
                runtime_globals.game_console.log(f"[ShopModulesView] Purchase error: {e}")
                runtime_globals.game_sound.play("error")
                runtime_globals.game_message.add_slide("Purchase failed", (255, 100, 100), 90)
        
        threading.Thread(target=do_purchase, daemon=True).start()
    
    def _on_download(self, item: ShopModuleItem):
        """Handle download button click."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_message.add_slide("Downloading...", (255, 255, 255), 60)
        
        def do_download():
            try:
                if game_globals.is_free_mode():
                    # Free mode: use free download endpoint
                    success, data = omninet_service.download_module_free(item.id)
                else:
                    success, data = omninet_service.download_module(item.id)
                if success:
                    # TODO: Save module data to modules folder
                    runtime_globals.game_message.add_slide("Download complete!", (0, 231, 58), 90)
                else:
                    runtime_globals.game_sound.play("error")
                    runtime_globals.game_message.add_slide("Download failed", (255, 100, 100), 90)
            except Exception as e:
                runtime_globals.game_console.log(f"[ShopModulesView] Download error: {e}")
                runtime_globals.game_sound.play("error")
                runtime_globals.game_message.add_slide("Download failed", (255, 100, 100), 90)
        
        threading.Thread(target=do_download, daemon=True).start()

    def _on_free_download(self, item: ShopModuleItem):
        """Handle free download in Free Mode (no purchase required)."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_message.add_slide("Downloading...", (255, 255, 255), 60)
        
        def do_free_download():
            try:
                success, data = omninet_service.download_module_free(item.id)
                if success:
                    # Mark as owned locally
                    game_globals.purchases.add_module(item.id, item.name)
                    game_globals.save()
                    item.owned = True
                    runtime_globals.game_message.add_slide("Download complete!", (0, 231, 58), 90)
                    # Refresh detail view
                    self._setup_detail_view(item)
                else:
                    runtime_globals.game_sound.play("error")
                    error_msg = data if isinstance(data, str) else "Download failed"
                    runtime_globals.game_message.add_slide(error_msg, (255, 100, 100), 90)
            except Exception as e:
                runtime_globals.game_console.log(f"[ShopModulesView] Free download error: {e}")
                runtime_globals.game_sound.play("error")
                runtime_globals.game_message.add_slide("Download failed", (255, 100, 100), 90)
        
        threading.Thread(target=do_free_download, daemon=True).start()
    
    def _on_detail_back(self):
        """Go back from detail view to list view."""
        runtime_globals.game_sound.play("cancel")
        self._clear_detail_components()
        
        if self.shop_list:
            self.shop_list.visible = True
        
        self.state = self.STATE_LIST
        self.selected_item = None
    
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
            if self.state == self.STATE_DETAIL:
                self._on_detail_back()
            else:
                self._on_back()
            return True
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        self._clear_detail_components()
        
        components = [
            self.background, self.title_scene,
            self.coin_icon, self.coin_label,
            self.shop_list, self.loading_label,
            self.back_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[ShopModulesView] Cleanup complete")

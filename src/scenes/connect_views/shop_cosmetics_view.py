"""
ShopCosmeticsView - Browse and purchase cosmetic items (backgrounds, etc.)
Shows list with small icons and larger preview in detail view.
"""
import threading
import pygame
import os

from ui.ui_manager import UIManager
from ui.components.title_scene import TitleScene
from ui.components.button import Button
from ui.components.background import Background
from ui.components.image import Image
from ui.components.label import Label
from ui.components.shop_list import ShopList, ShopCosmeticItem
from ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals, game_globals
from services.omninet_service import omninet_service
from utils.asset_utils import image_load


class ShopCosmeticsView:
    """Cosmetics shop view with list and detail subviews."""
    
    STATE_LIST = "list"
    STATE_DETAIL = "detail"
    STATE_LOADING = "loading"
    
    def __init__(self, ui_manager: UIManager, change_view_callback, discord_module=None):
        """Initialize the shop cosmetics view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            discord_module: Reference to the Discord module (unused, for compatibility)
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        
        self.state = self.STATE_LOADING
        self.selected_item = None
        self.cosmetics_data = []
        
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
        self._load_cosmetics_async()
    
    def _setup_ui(self):
        """Setup the UI components."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "COSMETICS")
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
        
        runtime_globals.game_console.log("[ShopCosmeticsView] UI setup complete")
    
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
    
    def _load_cosmetic_preview(self, preview_path: str) -> pygame.Surface:
        """Load a cosmetic preview image from assets or data."""
        if not preview_path:
            return None
        
        try:
            # Try loading from backgrounds folder first
            bg_path = os.path.join("assets", "ui", "backgrounds", preview_path)
            if os.path.exists(bg_path):
                return image_load(bg_path).convert_alpha()
            
            # Try direct path
            if os.path.exists(preview_path):
                return image_load(preview_path).convert_alpha()
        except Exception as e:
            runtime_globals.game_console.log(f"[ShopCosmeticsView] Failed to load preview {preview_path}: {e}")
        
        return None
    
    def _create_thumbnail(self, preview: pygame.Surface, size: int) -> pygame.Surface:
        """Create a thumbnail from the preview image."""
        if not preview:
            return None
        
        # Scale to thumbnail size maintaining aspect ratio
        orig_w, orig_h = preview.get_size()
        scale = min(size / orig_w, size / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        return pygame.transform.scale(preview, (new_w, new_h))
    
    def _setup_list_view(self):
        """Setup the list view with loaded cosmetics."""
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
            mode=ShopList.MODE_COSMETICS,
            on_item_selected=self._on_cosmetic_selected
        )
        
        # Convert API data to ShopCosmeticItem objects
        items = []
        for cosm in self.cosmetics_data:
            cosm_id = cosm.get('id', '')
            owned = game_globals.purchases.owns_cosmetic(cosm_id)
            
            # Load preview and create thumbnail
            preview = self._load_cosmetic_preview(cosm.get('preview', ''))
            icon = self._create_thumbnail(preview, 28) if preview else None
            
            items.append(ShopCosmeticItem(
                item_id=cosm_id,
                name=cosm.get('name', 'Unknown'),
                price=cosm.get('price', 0),
                owned=owned,
                icon=icon,
                preview=preview,
                cosmetic_type=cosm.get('type', 'Background')
            ))
        
        self.shop_list.set_items(items)
        self.ui_manager.add_component(self.shop_list)
        
        self.state = self.STATE_LIST
    
    def _setup_detail_view(self, item: ShopCosmeticItem):
        """Setup the detail view for a selected cosmetic."""
        self._clear_detail_components()
        
        # Hide list
        if self.shop_list:
            self.shop_list.visible = False
        
        padding = 10
        y_offset = 35
        
        # Large preview image
        if item.preview:
            preview_size = 120
            preview_x = (BASE_RESOLUTION - preview_size) // 2
            
            # Create preview surface
            preview_scaled = pygame.transform.scale(item.preview, (preview_size, preview_size))
            preview_image = Image(preview_x, y_offset, preview_size, preview_size)
            preview_image.set_image(preview_scaled)
            self.ui_manager.add_component(preview_image)
            self.detail_components.append(preview_image)
            y_offset += preview_size + 10
        
        # Cosmetic name (large)
        name_label = Label(0, y_offset, item.name, is_title=True)
        self.ui_manager.add_component(name_label)
        self.detail_components.append(name_label)
        y_offset += 25
        
        # Type
        type_label = Label(0, y_offset, f"Type: {item.cosmetic_type}", is_title=False)
        self.ui_manager.add_component(type_label)
        self.detail_components.append(type_label)
        y_offset += 20
        
        # Price display
        if item.owned:
            price_text = "Already Owned"
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
    
    def _load_cosmetics_async(self):
        """Load cosmetics from server in background thread."""
        def fetch_cosmetics():
            try:
                success, data = omninet_service.get_shop_cosmetics()
                if success and data:
                    self.cosmetics_data = data
                else:
                    self.cosmetics_data = []
                    runtime_globals.game_console.log(f"[ShopCosmeticsView] Failed to load cosmetics")
            except Exception as e:
                runtime_globals.game_console.log(f"[ShopCosmeticsView] Error loading cosmetics: {e}")
                self.cosmetics_data = []
            
            self._on_cosmetics_loaded()
        
        threading.Thread(target=fetch_cosmetics, daemon=True).start()
    
    def _on_cosmetics_loaded(self):
        """Called when cosmetics are loaded from server."""
        self._setup_list_view()
    
    def _on_cosmetic_selected(self, item: ShopCosmeticItem):
        """Handle cosmetic selection from list."""
        runtime_globals.game_sound.play("menu")
        self.selected_item = item
        self._setup_detail_view(item)
    
    def _on_buy(self, item: ShopCosmeticItem):
        """Handle buy button click."""
        coins = getattr(game_globals, 'coins', 0)
        
        if coins < item.price:
            runtime_globals.game_sound.play("error")
            runtime_globals.game_message.add_slide("Not enough coins!", (255, 100, 100), 90)
            return
        
        runtime_globals.game_sound.play("menu")
        
        def do_purchase():
            try:
                success, message = omninet_service.purchase_item('cosmetic', item.id)
                if success:
                    game_globals.coins -= item.price
                    game_globals.purchases.add_cosmetic(item.id)
                    game_globals.save()
                    
                    item.owned = True
                    runtime_globals.game_message.add_slide("Purchase successful!", (0, 231, 58), 90)
                    self._setup_detail_view(item)
                else:
                    runtime_globals.game_sound.play("error")
                    runtime_globals.game_message.add_slide(message or "Purchase failed", (255, 100, 100), 90)
            except Exception as e:
                runtime_globals.game_console.log(f"[ShopCosmeticsView] Purchase error: {e}")
                runtime_globals.game_sound.play("error")
                runtime_globals.game_message.add_slide("Purchase failed", (255, 100, 100), 90)
        
        threading.Thread(target=do_purchase, daemon=True).start()
    
    def _on_download(self, item: ShopCosmeticItem):
        """Handle download button click."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_message.add_slide("Downloading...", (255, 255, 255), 60)
        
        def do_download():
            try:
                success, data = omninet_service.download_cosmetic(item.id)
                if success:
                    # TODO: Save cosmetic data to appropriate folder
                    runtime_globals.game_message.add_slide("Download complete!", (0, 231, 58), 90)
                else:
                    runtime_globals.game_sound.play("error")
                    runtime_globals.game_message.add_slide("Download failed", (255, 100, 100), 90)
            except Exception as e:
                runtime_globals.game_console.log(f"[ShopCosmeticsView] Download error: {e}")
                runtime_globals.game_sound.play("error")
                runtime_globals.game_message.add_slide("Download failed", (255, 100, 100), 90)
        
        threading.Thread(target=do_download, daemon=True).start()
    
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
        
        runtime_globals.game_console.log("[ShopCosmeticsView] Cleanup complete")

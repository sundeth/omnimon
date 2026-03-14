"""
Shop List Component - Vertical scrollable list for shop items
Inherits from BaseList and provides specialized rendering for modules, items, cosmetics, and gameplay.
"""
import pygame
from components.ui.base_list import BaseList
from core import runtime_globals, game_globals


class ShopListItem:
    """Base class for shop list items."""
    def __init__(self, item_id: str, name: str, price: int, owned: bool = False):
        self.id = item_id
        self.name = name
        self.price = price
        self.owned = owned


class ShopModuleItem(ShopListItem):
    """Module item for shop list."""
    def __init__(self, item_id: str, name: str, price: int, owned: bool = False,
                 creator: str = "", version: str = "", official: bool = False,
                 description: str = "", size_mb: float = 0, contributors: str = "",
                 updated_at: str = "", category: str = ""):
        super().__init__(item_id, name, price, owned)
        self.creator = creator
        self.version = version
        self.official = official
        self.description = description
        self.size_mb = size_mb
        self.contributors = contributors
        self.updated_at = updated_at
        self.category = category


class ShopGameplayItem(ShopListItem):
    """Gameplay item for shop list."""
    def __init__(self, item_id: str, name: str, price: int, owned: bool = False,
                 item_type: str = "", description: str = ""):
        super().__init__(item_id, name, price, owned)
        self.item_type = item_type
        self.description = description


class ShopInventoryItem(ShopListItem):
    """Inventory-style item for shop list (consumables)."""
    def __init__(self, item_id: str, name: str, price: int, owned: bool = False,
                 icon: pygame.Surface = None, description: str = "", quantity: int = 0):
        super().__init__(item_id, name, price, owned)
        self.icon = icon
        self.description = description
        self.quantity = quantity


class ShopCosmeticItem(ShopListItem):
    """Cosmetic item for shop list."""
    def __init__(self, item_id: str, name: str, price: int, owned: bool = False,
                 icon: pygame.Surface = None, preview: pygame.Surface = None,
                 cosmetic_type: str = ""):
        super().__init__(item_id, name, price, owned)
        self.icon = icon
        self.preview = preview
        self.cosmetic_type = cosmetic_type


class ShopList(BaseList):
    """Generic shop list supporting different item types."""
    
    # List display modes
    MODE_MODULES = "modules"
    MODE_GAMEPLAY = "gameplay"
    MODE_ITEMS = "items"
    MODE_COSMETICS = "cosmetics"
    
    def __init__(self, x, y, width, height, mode=MODE_MODULES, on_item_selected=None):
        """Initialize the shop list with vertical orientation.
        
        Args:
            x, y, width, height: Component dimensions
            mode: Display mode (modules, gameplay, items, cosmetics)
            on_item_selected: Callback when an item is selected (receives item)
        """
        super().__init__(x, y, width, height, orientation="vertical")
        
        self.mode = mode
        self.on_item_selected_callback = on_item_selected
        
        # Custom settings for shop list
        if mode == self.MODE_ITEMS or mode == self.MODE_COSMETICS:
            self.base_item_size = 36  # Height for icon-based items
        else:
            self.base_item_size = 44  # Height for text-based items (modules, gameplay)
        
        self.base_item_spacing = 6
        self.base_arrow_size = 12
        self.base_margin = 2
        
        # Visual settings
        self.cut_width = 8
        
        # Text scrolling for long names
        self.text_scroll_speed = 20 * (30 / (runtime_globals.FRAME_RATE if hasattr(runtime_globals, 'FRAME_RATE') else 30))
        self.text_scroll_offset = {}
        self.text_scroll_delay = 1000
        self.text_scroll_start_time = {}
    
    def on_item_activated(self, item):
        """Called when an item is activated (clicked/selected)."""
        if self.on_item_selected_callback:
            self.on_item_selected_callback(item)
    
    def handle_event(self, event):
        """Handle events and check for item activation.
        
        Args:
            event: Tuple of (event_type, event_data) from input system
        """
        result = super().handle_event(event)
        
        # Check for selection confirmation via tuple-based events
        if isinstance(event, tuple):
            event_type, event_data = event
            if event_type in ["A", "ENTER"]:
                if self.items and 0 <= self.active_index < len(self.items):
                    self.on_item_activated(self.items[self.active_index])
                    return True
            elif event_type == "LCLICK":
                if self.items and 0 <= self.active_index < len(self.items):
                    self.on_item_activated(self.items[self.active_index])
                    return True
        
        return result
    
    def _draw_items(self, surface):
        """Draw shop items based on current mode."""
        if not self.items or not self.items_rect:
            return
        
        if self.mode == self.MODE_MODULES:
            self._draw_module_items(surface)
        elif self.mode == self.MODE_GAMEPLAY:
            self._draw_gameplay_items(surface)
        elif self.mode == self.MODE_ITEMS:
            self._draw_inventory_items(surface)
        elif self.mode == self.MODE_COSMETICS:
            self._draw_cosmetic_items(surface)
    
    def _get_item_colors(self, index: int):
        """Get colors based on selection and focus state."""
        colors = self.manager.get_theme_colors()
        
        is_selected = (index == self.active_index)
        is_hovered = (index == self.mouse_over_index)
        is_keyboard_focused = (self.focused and index == self.selected_index)
        is_focus_highlighted = (is_hovered or is_keyboard_focused) and runtime_globals.INPUT_MODE != runtime_globals.TOUCH_MODE
        
        if is_selected:
            fill_color = colors["fg"]
            text_color = colors["bg"]
            border_color = colors["bg"]
        else:
            fill_color = colors["bg"]
            text_color = colors["fg"]
            border_color = colors["fg"]
        
        if is_focus_highlighted:
            border_color = colors["highlight"]
            text_color = colors["highlight"]
        
        return fill_color, text_color, border_color
    
    def _draw_item_background(self, surface, item_y, fill_color, border_color):
        """Draw item background rectangle."""
        border_size = self.manager.get_border_size()
        
        # Simple rectangle with small cut corners
        rect = pygame.Rect(self.items_rect.x, item_y, self.items_rect.width, self.item_size)
        cut = self.manager.scale_value(self.cut_width)
        
        points = [
            (rect.x + cut, rect.y),
            (rect.right, rect.y),
            (rect.right, rect.bottom - cut),
            (rect.right - cut, rect.bottom),
            (rect.x, rect.bottom),
            (rect.x, rect.y + cut),
        ]
        
        pygame.draw.polygon(surface, fill_color, points)
        pygame.draw.polygon(surface, border_color, points, border_size)
    
    def _draw_module_items(self, surface):
        """Draw module items: name, creator, version, price/owned."""
        item_total_size = self.item_size + self.item_spacing
        first_visible = max(0, int(self.scroll_offset // item_total_size))
        last_visible = min(len(self.items), first_visible + self.get_visible_item_count() + 2)
        
        for i in range(first_visible, last_visible):
            if i >= len(self.items):
                break
            
            item = self.items[i]
            item_y = self.items_rect.y + (i * item_total_size) - self.scroll_offset
            
            if item_y + self.item_size < self.items_rect.y or item_y > self.items_rect.y + self.items_rect.height:
                continue
            
            fill_color, text_color, border_color = self._get_item_colors(i)
            self._draw_item_background(surface, item_y, fill_color, border_color)
            
            # Fonts
            name_font = self.get_font("text", custom_size=18 * self.manager.ui_scale)
            small_font = self.get_font("text", custom_size=14 * self.manager.ui_scale)
            
            padding = self.manager.scale_value(6)
            
            # Draw official badge if applicable
            badge_offset = 0
            if hasattr(item, 'official') and item.official:
                badge_text = "★"
                badge_surface = small_font.render(badge_text, True, text_color)
                surface.blit(badge_surface, (self.items_rect.x + padding, item_y + padding))
                badge_offset = badge_surface.get_width() + 4
            
            # Name (top left)
            name_text = item.name[:20] + "..." if len(item.name) > 20 else item.name
            name_surface = name_font.render(name_text, True, text_color)
            surface.blit(name_surface, (self.items_rect.x + padding + badge_offset, item_y + padding))
            
            # Price or "Owned" (top right)
            if item.owned:
                price_text = "Owned"
            else:
                price_text = f"{item.price}c"
            price_surface = small_font.render(price_text, True, text_color)
            price_x = self.items_rect.right - padding - price_surface.get_width()
            surface.blit(price_surface, (price_x, item_y + padding))
            
            # Creator and version (bottom left)
            creator_text = f"by {item.creator}" if hasattr(item, 'creator') and item.creator else ""
            version_text = f"v{item.version}" if hasattr(item, 'version') and item.version else ""
            info_text = f"{creator_text} {version_text}".strip()
            if info_text:
                info_surface = small_font.render(info_text[:30], True, text_color)
                surface.blit(info_surface, (self.items_rect.x + padding, item_y + self.item_size - padding - info_surface.get_height()))
    
    def _draw_gameplay_items(self, surface):
        """Draw gameplay items: name and type."""
        item_total_size = self.item_size + self.item_spacing
        first_visible = max(0, int(self.scroll_offset // item_total_size))
        last_visible = min(len(self.items), first_visible + self.get_visible_item_count() + 2)
        
        for i in range(first_visible, last_visible):
            if i >= len(self.items):
                break
            
            item = self.items[i]
            item_y = self.items_rect.y + (i * item_total_size) - self.scroll_offset
            
            if item_y + self.item_size < self.items_rect.y or item_y > self.items_rect.y + self.items_rect.height:
                continue
            
            fill_color, text_color, border_color = self._get_item_colors(i)
            self._draw_item_background(surface, item_y, fill_color, border_color)
            
            name_font = self.get_font("text", custom_size=18 * self.manager.ui_scale)
            small_font = self.get_font("text", custom_size=14 * self.manager.ui_scale)
            
            padding = self.manager.scale_value(6)
            
            # Name (top left)
            name_text = item.name[:25] + "..." if len(item.name) > 25 else item.name
            name_surface = name_font.render(name_text, True, text_color)
            surface.blit(name_surface, (self.items_rect.x + padding, item_y + padding))
            
            # Price or "Owned" (top right)
            if item.owned:
                price_text = "Owned"
            else:
                price_text = f"{item.price}c"
            price_surface = small_font.render(price_text, True, text_color)
            price_x = self.items_rect.right - padding - price_surface.get_width()
            surface.blit(price_surface, (price_x, item_y + padding))
            
            # Type (bottom left)
            if hasattr(item, 'item_type') and item.item_type:
                type_surface = small_font.render(item.item_type, True, text_color)
                surface.blit(type_surface, (self.items_rect.x + padding, item_y + self.item_size - padding - type_surface.get_height()))
    
    def _draw_inventory_items(self, surface):
        """Draw inventory-style items with icon, name, and price."""
        item_total_size = self.item_size + self.item_spacing
        first_visible = max(0, int(self.scroll_offset // item_total_size))
        last_visible = min(len(self.items), first_visible + self.get_visible_item_count() + 2)
        
        icon_size = self.manager.scale_value(28)
        
        for i in range(first_visible, last_visible):
            if i >= len(self.items):
                break
            
            item = self.items[i]
            item_y = self.items_rect.y + (i * item_total_size) - self.scroll_offset
            
            if item_y + self.item_size < self.items_rect.y or item_y > self.items_rect.y + self.items_rect.height:
                continue
            
            fill_color, text_color, border_color = self._get_item_colors(i)
            self._draw_item_background(surface, item_y, fill_color, border_color)
            
            name_font = self.get_font("text", custom_size=16 * self.manager.ui_scale)
            small_font = self.get_font("text", custom_size=12 * self.manager.ui_scale)
            
            padding = self.manager.scale_value(4)
            
            # Icon (left side)
            icon_x = self.items_rect.x + padding
            icon_y = item_y + (self.item_size - icon_size) // 2
            
            if hasattr(item, 'icon') and item.icon:
                scaled_icon = pygame.transform.scale(item.icon, (icon_size, icon_size))
                surface.blit(scaled_icon, (icon_x, icon_y))
            
            text_x = icon_x + icon_size + padding
            
            # Name
            name_text = item.name[:18] + "..." if len(item.name) > 18 else item.name
            name_surface = name_font.render(name_text, True, text_color)
            surface.blit(name_surface, (text_x, item_y + padding + 2))
            
            # Price or quantity (bottom right)
            if item.owned and hasattr(item, 'quantity') and item.quantity > 0:
                info_text = f"x{item.quantity}"
            elif item.owned:
                info_text = "Owned"
            else:
                info_text = f"{item.price}c"
            info_surface = small_font.render(info_text, True, text_color)
            info_x = self.items_rect.right - padding - info_surface.get_width()
            surface.blit(info_surface, (info_x, item_y + self.item_size - padding - info_surface.get_height()))
    
    def _draw_cosmetic_items(self, surface):
        """Draw cosmetic items with small icon and name."""
        item_total_size = self.item_size + self.item_spacing
        first_visible = max(0, int(self.scroll_offset // item_total_size))
        last_visible = min(len(self.items), first_visible + self.get_visible_item_count() + 2)
        
        icon_size = self.manager.scale_value(28)
        
        for i in range(first_visible, last_visible):
            if i >= len(self.items):
                break
            
            item = self.items[i]
            item_y = self.items_rect.y + (i * item_total_size) - self.scroll_offset
            
            if item_y + self.item_size < self.items_rect.y or item_y > self.items_rect.y + self.items_rect.height:
                continue
            
            fill_color, text_color, border_color = self._get_item_colors(i)
            self._draw_item_background(surface, item_y, fill_color, border_color)
            
            name_font = self.get_font("text", custom_size=16 * self.manager.ui_scale)
            small_font = self.get_font("text", custom_size=12 * self.manager.ui_scale)
            
            padding = self.manager.scale_value(4)
            
            # Icon (left side)
            icon_x = self.items_rect.x + padding
            icon_y = item_y + (self.item_size - icon_size) // 2
            
            if hasattr(item, 'icon') and item.icon:
                scaled_icon = pygame.transform.scale(item.icon, (icon_size, icon_size))
                surface.blit(scaled_icon, (icon_x, icon_y))
            
            text_x = icon_x + icon_size + padding
            
            # Name and type
            name_text = item.name[:20] + "..." if len(item.name) > 20 else item.name
            name_surface = name_font.render(name_text, True, text_color)
            surface.blit(name_surface, (text_x, item_y + padding + 2))
            
            if hasattr(item, 'cosmetic_type') and item.cosmetic_type:
                type_surface = small_font.render(item.cosmetic_type, True, text_color)
                surface.blit(type_surface, (text_x, item_y + self.item_size - padding - type_surface.get_height()))
            
            # Price or "Owned" (right side)
            if item.owned:
                price_text = "Owned"
            else:
                price_text = f"{item.price}c"
            price_surface = small_font.render(price_text, True, text_color)
            price_x = self.items_rect.right - padding - price_surface.get_width()
            surface.blit(price_surface, (price_x, item_y + (self.item_size - price_surface.get_height()) // 2))

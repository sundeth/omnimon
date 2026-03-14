"""
Adventure Panel Component - Displays module information with icon, name, and progress
"""
import pygame
from components.ui.component import UIComponent
from core import runtime_globals
from core.utils.asset_utils import image_load
from core.utils.pygame_utils import blit_with_cache


class AdventurePanel(UIComponent):
    def __init__(self, x, y, width=165, height=55):
        super().__init__(x, y, width, height)
        
        # Module data
        self.module = None
        self.available_area = 0
        self.available_round = 0
        self.area_round_limits = {}
        self.progress_current = 0
        self.progress_total = 0
        
        # Sub-component for progress display
        self.progress_label = None
        
        # Visual settings
        self.icon_size = 32  # Base size for module icon
        self.padding = 2
        
    def set_module(self, module, available_area=0, available_round=0, area_round_limits=None):
        """Set the module and progress information
        
        Args:
            module: The module to display
            available_area: The current unlocked area for this module
            available_round: The current unlocked round for this module
            area_round_limits: Dict mapping area number to round count for that area
        """
        self.module = module
        self.available_area = available_area
        self.available_round = available_round
        self.area_round_limits = area_round_limits if area_round_limits is not None else {}
        
        # Hide progress for Random adventure style
        self.show_progress = getattr(module, 'adventure_style', 'Area Selection') != 'Random'
        
        # Calculate progress based on available area/round
        # Progress is areas cleared (available_area - 1), not current area
        self.progress_current = max(0, available_area - 1)
        self.progress_total = len(self.area_round_limits) if self.area_round_limits else available_area
        
        # Make the panel visible when a module is set
        self.visible = True
        
        self.needs_redraw = True
        
    def on_manager_set(self):
        """Called when component is added to UI manager"""
        self.update_colors_from_theme()
        
    def update_colors_from_theme(self):
        """Update colors based on current UI theme"""
        if self.manager:
            theme_colors = self.manager.get_theme_colors()
            self.bg_color = theme_colors.get("bg", (40, 40, 80))
            self.fg_color = theme_colors.get("fg", (255, 255, 255))
            self.border_color = theme_colors.get("fg", (255, 255, 255))
            self.needs_redraw = True
            
    def render(self):
        """Render the adventure panel"""
        # Reuse a cached render surface to avoid per-frame allocations
        target_size = (self.rect.width, self.rect.height)
        if not hasattr(self, "_render_surface") or self._render_surface is None or self._render_surface.get_size() != target_size:
            self._render_surface = pygame.Surface(target_size, pygame.SRCALPHA)
        surface = self._render_surface
        surface.fill((0, 0, 0, 0))
        
        if not self.module:
            return surface
        
        # Get theme colors
        if self.manager:
            theme_colors = self.manager.get_theme_colors()
            bg_color = theme_colors.get("bg", (40, 40, 80))
            fg_color = theme_colors.get("fg", (255, 255, 255))
            border_width = self.manager.get_border_size()
        else:
            bg_color = (40, 40, 80)
            fg_color = (255, 255, 255)
            border_width = 4
        
        # Draw background and border
        pygame.draw.rect(surface, bg_color, (0, 0, self.rect.width, self.rect.height))
        pygame.draw.rect(surface, fg_color, (0, 0, self.rect.width, self.rect.height), border_width)
        
        # Load and draw module's BattleIcon (48x48 base, needs manual scaling)
        if self.manager:
            try:
                battle_icon_path = self.module.folder_path + "/BattleIcon.png"
                battle_icon = image_load(battle_icon_path).convert_alpha()
                
                # Scale to match UI scale
                # NEW SYSTEM: Use ui_scale directly for scaling
                ui_scale = self.manager.ui_scale
                scaled_size = (48 * ui_scale, 48 * ui_scale)
                icon_sprite = pygame.transform.scale(battle_icon, scaled_size)
            except Exception as e:
                runtime_globals.game_console.log(f"[AdventurePanel] Failed to load BattleIcon: {e}")
                icon_sprite = None
            
            if icon_sprite:
                # Position icon on the left side
                scaled_padding = self.manager.scale_value(self.padding)
                icon_rect = icon_sprite.get_rect()
                icon_rect.left = scaled_padding
                icon_rect.centery = self.rect.height // 2
                blit_with_cache(surface, icon_sprite, icon_rect.topleft)
                
                # Draw module name to the right of icon (title font)
                title_font = self.get_font("title")
                text_font = self.get_font("text")
                name_text = self.module.name
                name_surface = title_font.render(name_text, False, fg_color)
                name_rect = name_surface.get_rect()
                name_rect.left = icon_rect.right + scaled_padding
                name_rect.top = scaled_padding
                blit_with_cache(surface, name_surface, name_rect.topleft)
                
                # Draw progress below the name (hidden for Random adventure style)
                if getattr(self, 'show_progress', True):
                    # Determine progress color
                    progress_color = fg_color
                    if self.progress_total > 0:
                        percentage = (self.progress_current / self.progress_total) * 100
                        if percentage < 50:
                            from components.ui.ui_constants import RED
                            progress_color = RED
                        elif percentage < 99:
                            from components.ui.ui_constants import YELLOW
                            progress_color = YELLOW
                        else:
                            from components.ui.ui_constants import GREEN
                            progress_color = GREEN
                    
                    # Draw "Progress:" label
                    progress_label_text = "Progress:"
                    progress_label_surface = text_font.render(progress_label_text, False, fg_color)
                    progress_label_rect = progress_label_surface.get_rect()
                    progress_label_rect.left = icon_rect.right + scaled_padding
                    progress_label_rect.top = name_rect.bottom + scaled_padding // 2
                    blit_with_cache(surface, progress_label_surface, progress_label_rect.topleft)
                    
                    # Draw progress value
                    progress_value_text = f"{self.progress_current}/{self.progress_total}"
                    progress_value_surface = text_font.render(progress_value_text, False, progress_color)
                    progress_value_rect = progress_value_surface.get_rect()
                    progress_value_rect.right = self.rect.width - scaled_padding
                    progress_value_rect.top = progress_label_rect.top
                    blit_with_cache(surface, progress_value_surface, progress_value_rect.topleft)
                
                # Draw battle effects below progress (if any active for this module)
                self._draw_battle_effects(surface, icon_rect, progress_label_rect, scaled_padding, text_font, fg_color, ui_scale)
        
        return surface
    
    def _draw_battle_effects(self, surface, icon_rect, progress_label_rect, scaled_padding, text_font, fg_color, ui_scale):
        """Draw active battle effect icons with amounts below the progress section"""
        from core import game_globals
        import os
        
        # Filter effects that match this module
        active_effects = []
        for status_name, effect_data in game_globals.battle_effects.items():
            if isinstance(effect_data, dict):
                effect_module = effect_data.get("module", "")
                effect_amount = effect_data.get("amount", 0)
                effect_item_id = effect_data.get("item_id", None)
                
                # Only show effects for this module with positive amounts
                if effect_module == self.module.name and effect_amount > 0 and effect_item_id:
                    active_effects.append({
                        "status": status_name,
                        "amount": effect_amount,
                        "item_id": effect_item_id,
                        "module": effect_module
                    })
        
        if not active_effects:
            return
        
        # Find items and load their icons
        effect_display_data = []
        for effect in active_effects:
            # Find the item in the module
            item = None
            for mod in runtime_globals.game_modules.values():
                if hasattr(mod, "items") and mod.name == effect["module"]:
                    for it in mod.items:
                        if it.id == effect["item_id"]:
                            item = it
                            break
                if item:
                    break
            
            if item:
                # Load item icon
                sprite_name = item.sprite_name
                if not sprite_name.lower().endswith(".png"):
                    sprite_name += ".png"
                sprite_path = os.path.join(self.module.folder_path, "items", sprite_name)
                
                if os.path.exists(sprite_path):
                    icon = image_load(sprite_path).convert_alpha()
                    # Scale icon to small size (16x16 base, scaled by ui_scale)
                    scaled_icon_size = (16 * ui_scale, 16 * ui_scale)
                    scaled_icon = pygame.transform.scale(icon, scaled_icon_size)
                    
                    effect_display_data.append({
                        "icon": scaled_icon,
                        "amount": effect["amount"]
                    })
        if not effect_display_data:
            return
        
        # Draw effects horizontally below the progress
        start_x = icon_rect.right + scaled_padding
        start_y = progress_label_rect.bottom + scaled_padding
        effect_spacing = 4 * ui_scale
        
        current_x = start_x
        for effect_data in effect_display_data:
            # Draw icon
            icon = effect_data["icon"]
            icon_rect_pos = icon.get_rect()
            icon_rect_pos.left = current_x
            icon_rect_pos.top = start_y
            blit_with_cache(surface, icon, icon_rect_pos.topleft)
            
            # Draw +amount text next to icon
            from components.ui.ui_constants import GREEN
            amount_text = f"+{effect_data['amount']}"
            amount_surface = text_font.render(amount_text, False, GREEN)
            amount_rect = amount_surface.get_rect()
            amount_rect.left = icon_rect_pos.right + scaled_padding // 2
            amount_rect.centery = icon_rect_pos.centery
            blit_with_cache(surface, amount_surface, amount_rect.topleft)
            
            # Move to next position
            current_x = amount_rect.right + effect_spacing

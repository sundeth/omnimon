"""
Scene EggSelection - New Journey Category Selection
Modern UI version with category selection for different types of pets/DIMs.
"""

import pygame
import os
import random
from ui.components.text_panel import TextPanel
from ui.ui_manager import UIManager
from ui.components.title_scene import TitleScene
from ui.components.button import Button
from ui.components.background import Background
from ui.components.image import Image
from ui.components.label import Label
from ui.components.label_value import LabelValue
from ui.components.experience_bar import ExperienceBar
from ui.components.grid import Grid, GridItem
from ui.windows.window_background import WindowBackground
from core import runtime_globals, game_globals
from services.omninet_service import omninet_service
from models.game_digidex import register_digidex_entry
from models.game_pet import GamePet
from utils.pet_utils import distribute_pets_evenly
from utils.scene_utils import change_scene
from utils.module_utils import get_module, load_modules
from utils.utils_unlocks import unlock_item
from utils import navigation_utils
from ui.ui_constants import BASE_RESOLUTION, BLUE, GRAY, GREEN, PURPLE, YELLOW, RED
from models.game_digidex import is_pet_unlocked
from utils.utils_unlocks import get_unlocked_backgrounds, is_unlocked
from utils.sprite_utils import load_pet_sprites
from utils.asset_utils import image_load
from scenes.scene_error import SceneError

#=====================================================================
# SceneEggSelection (New Journey Category Selection)
#=====================================================================
class SceneEggSelection:
    """
    Modern UI scene for egg/pet category selection to start a new journey.
    """

    def __init__(self) -> None:
        """Initialize the egg selection scene with new UI system."""
        
        # Use GRAY theme for egg selection (neutral, welcoming)
        self.ui_manager = UIManager("VIOLET")
        
        # Scene phases: "category" -> "module_selection" -> other phases will be added later
        self.phase = "category"
        
        # Module selection data
        self.available_modules = []
        self.current_module_index = 0
        self.selected_category = None
        self.module_stats_cache = {}  # Cache for calculated percentages
        
        # UI Components for category selection
        self.background = None
        self.title_scene = None
        self.classic_button = None
        self.modern_button = None
        self.conversions_button = None
        self.custom_button = None
        self.random_button = None
        self.exit_button = None
        
        # UI Components for module selection
        self.module_logo_image = None
        self.module_name_label = None
        self.version_label = None
        self.eggs_label = None
        self.digidex_label = None
        self.digidex_bar = None
        self.backgrounds_label = None
        self.backgrounds_bar = None
        self.secrets_label = None
        self.secrets_bar = None
        self.adventure_label = None
        self.adventure_bar = None
        self.prev_button = None
        self.next_button = None
        self.select_button = None
        self.back_button = None
        
        # UI Components for egg selection
        self.egg_grid = None
        self.egg_prev_button = None
        self.egg_next_button = None
        self.egg_select_button = None
        self.egg_back_button = None
        
        # Window background for areas not covered by UI
        self.window_background = WindowBackground(True)
        
        # Check if this is the first pet
        self.is_first_pet = len(game_globals.pet_list) == 0
        
        # No modules installed at all → send straight to the shop's
        # modules section instead of bouncing through SceneError (the
        # shop view handles offline state on its own).
        if not navigation_utils.has_modules_installed():
            runtime_globals.scene_connect_initial_view = "shop_modules"
            change_scene("connect")
            runtime_globals.game_console.log(
                "[SceneEggSelection] No modules installed → routing to Shop")
            return

        if not self._has_any_modules_with_eggs():
            # No installed modules have eggs (Tutorial is excluded) — show
            # the inline "get some modules" UI regardless of game mode.
            self.phase = "no_modules"
            runtime_globals.game_console.log(
                "[SceneEggSelection] No installed modules have eggs")
        elif game_globals.is_progress_mode() and not navigation_utils.has_owned_modules():
            # Progress Mode: player has no modules in their library.  Send
            # them straight into the shop's modules section instead of
            # showing an error screen.
            runtime_globals.scene_connect_initial_view = "shop_modules"
            change_scene("connect")
            return

        # Module pre-selected by the connect-exit flow (player just bought a
        # module + had no pets).  Skip the category step and jump straight
        # to that module's egg picker.
        preselected = getattr(runtime_globals, 'preselected_module', None)
        runtime_globals.preselected_module = None
        if preselected and preselected in runtime_globals.game_modules:
            self.available_modules = [preselected]
            self.current_module_index = 0
            self.phase = "egg_selection"
            self.setup_ui()
            runtime_globals.game_console.log(
                f"[SceneEggSelection] Pre-selected module '{preselected}', "
                "skipping category step")
            return
        else:
            runtime_globals.game_console.log(
                "[SceneEggSelection] Modules available, showing category selection")
        
        self.setup_ui()
        
        # Set mouse mode and focus on the recommended option (Modern if first pet and enabled, otherwise first enabled button)
        if self.is_first_pet and self.modern_button and self.modern_button.enabled:
            self.ui_manager.set_focused_component(self.modern_button)
        elif self.classic_button and self.classic_button.enabled:
            self.ui_manager.set_focused_component(self.classic_button)
        elif self.modern_button and self.modern_button.enabled:
            self.ui_manager.set_focused_component(self.modern_button)
        elif self.conversions_button and self.conversions_button.enabled:
            self.ui_manager.set_focused_component(self.conversions_button)
        elif self.custom_button and self.custom_button.enabled:
            self.ui_manager.set_focused_component(self.custom_button)
        elif self.random_button:
            self.ui_manager.set_focused_component(self.random_button)
        
        runtime_globals.game_console.log("[SceneEggSelection] New journey category selection initialized.")

    def setup_ui(self):
        """Setup the UI components based on current phase."""
        try:
            # Clear existing components
            self.clear_components()
            
            if self.phase == "no_modules":
                self.setup_no_modules_ui()
            elif self.phase == "category":
                self.setup_category_ui()
            elif self.phase == "module_selection":
                self.setup_module_selection_ui()
            elif self.phase == "egg_selection":
                self.setup_egg_selection_ui()
            
        except Exception as e:
            runtime_globals.game_console.log(f"[SceneEggSelection] ERROR in setup_ui: {e}")
            import traceback
            runtime_globals.game_console.log(f"[SceneEggSelection] Traceback: {traceback.format_exc()}")
            raise

    def _has_modules_for_category(self, category: str) -> bool:
        """Check if there are any modules with eggs available for the given category."""
        for module_name, module in runtime_globals.game_modules.items():
            module_category = getattr(module, 'category', 'Custom')
            
            # In Progress Mode, skip modules the player doesn't own
            if game_globals.is_progress_mode():
                if module_name.lower() != 'tutorial' and not game_globals.purchases.owns_module_name(module_name):
                    continue
            
            # Flexible category matching - case insensitive and handle plurals
            if (module_category.lower() == category.lower() or 
                (category.lower() == 'classic' and module_category.lower() in ['classic', 'classics']) or
                (category.lower() == 'modern' and module_category.lower() in ['modern', 'moderns']) or
                (category.lower() == 'conversions' and module_category.lower() in ['conversion', 'conversions']) or
                (category.lower() == 'custom' and module_category.lower() in ['custom', 'customs', 'other', ''])):
                
                # Check if module has any eggs (stage 0 monsters)
                eggs = module.get_monsters_by_stage(0)
                if eggs:
                    return True
        return False

    def _has_any_modules_with_eggs(self) -> bool:
        """Check if there are any installed modules that have selectable eggs.

        This is purely a scene-usability check (does the scene have anything
        to show at all?).  Ownership filtering for Progress Mode is handled
        separately in ``load_available_modules`` and in the ``__init__``
        routing logic (which shows a shop-redirect error when no owned modules
        are installed).
        """
        for module_name, module in runtime_globals.game_modules.items():
            # Skip the Tutorial module — it is not a real playable module
            if module_name.lower() == "tutorial":
                continue
            eggs = module.get_monsters_by_stage(0)
            if eggs:
                return True
        return False

    def setup_no_modules_ui(self):
        """Setup UI for when no modules are available."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "NEW JOURNEY")
        self.ui_manager.add_component(self.title_scene)
        
        # Message text panel
        message_panel = TextPanel(30, 80, 180, 80)
        message_panel.set_text("No modules installed. Install manually or download from the Shop.")
        self.ui_manager.add_component(message_panel)

        # Action buttons
        btn_w = 90
        btn_h = 30
        gap = 12
        btn_y = 180
        total_w = btn_w * 2 + gap
        start_x = (ui_width - total_w) // 2

        def on_try_again():
            runtime_globals.game_sound.play("menu")
            change_scene("egg")

        def on_shop():
            runtime_globals.game_sound.play("menu")
            change_scene("connect")

        try_again_button = Button(
            start_x, btn_y, btn_w, btn_h,
            "Try Again", on_try_again,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
        )
        self.ui_manager.add_component(try_again_button)

        shop_button = Button(
            start_x + btn_w + gap, btn_y, btn_w, btn_h,
            "Shop", on_shop,
            cut_corners={'tl': False, 'tr': True, 'bl': True, 'br': False}
        )
        self.ui_manager.add_component(shop_button)
        
        runtime_globals.game_console.log("[SceneEggSelection] No modules UI setup complete")

    def clear_components(self):
        """Clear all components from the UI manager."""
        self.ui_manager.components.clear()
        self.ui_manager.focusable_components.clear()
        self.ui_manager.focused_index = -1

    def setup_category_ui(self):
        """Setup the UI components for the category selection."""
        # Use base 240x240 resolution for UI layout
        ui_width = ui_height = BASE_RESOLUTION
        
        # Create and add the UI background that covers the full UI area
        self.background = Background(ui_width, ui_height)
        # Set single black region covering entire UI
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Create and add the title scene at top
        self.title_scene = TitleScene(0, 9, "Module")
        self.ui_manager.add_component(self.title_scene)
        
        # Calculate positions for 2x2 grid of main category buttons (100x70)
        button_width = 96
        button_height = 66
        grid_spacing = 10  # Space between buttons
        
        # Calculate grid positioning to center it
        total_grid_width = (button_width * 2) + grid_spacing
        total_grid_height = (button_height * 2) + grid_spacing
        grid_start_x = (ui_width - total_grid_width) // 2
        grid_start_y = 40  # Below title with some margin
        
        # Row 1: Classic and Modern
        classic_x = grid_start_x
        classic_y = grid_start_y
        modern_x = grid_start_x + button_width + grid_spacing
        modern_y = grid_start_y
        
        # Row 2: Conversions and Custom
        conversions_x = grid_start_x
        conversions_y = grid_start_y + button_height + grid_spacing
        custom_x = grid_start_x + button_width + grid_spacing
        custom_y = grid_start_y + button_height + grid_spacing
        
        # Check which categories have modules available
        has_classic = self._has_modules_for_category('classic')
        has_modern = self._has_modules_for_category('modern')
        has_conversions = self._has_modules_for_category('conversions')
        has_custom = self._has_modules_for_category('custom')
        
        # Create Classic button (disabled if no modules)
        self.classic_button = Button(
            classic_x, classic_y, button_width, button_height,
            "", self.on_classic_selection,
            cut_corners={'tl': False, 'tr': False, 'bl': False, 'br': False},
            decorators=["Selection_Classics"],
            enabled=has_classic
        )
        self.ui_manager.add_component(self.classic_button)
        
        # Create Modern button (with recommended decorator if first pet, disabled if no modules)
        modern_decorators = ["Selection_Modern"]
        if self.is_first_pet and has_modern:
            modern_decorators.append("Selection_Recommended")
        
        self.modern_button = Button(
            modern_x, modern_y, button_width, button_height,
            "", self.on_modern_selection,
            cut_corners={'tl': False, 'tr': False, 'bl': False, 'br': False},
            decorators=modern_decorators,
            enabled=has_modern
        )
        self.ui_manager.add_component(self.modern_button)
        
        # Create Conversions button (disabled if no modules)
        self.conversions_button = Button(
            conversions_x, conversions_y, button_width, button_height,
            "", self.on_conversions_selection,
            cut_corners={'tl': False, 'tr': False, 'bl': False, 'br': False},
            decorators=["Selection_Conversions"],
            enabled=has_conversions
        )
        self.ui_manager.add_component(self.conversions_button)
        
        # Create Custom button (disabled if no modules)
        self.custom_button = Button(
            custom_x, custom_y, button_width, button_height,
            "", self.on_custom_selection,
            cut_corners={'tl': False, 'tr': False, 'bl': False, 'br': False},
            decorators=["Selection_Custom"],
            enabled=has_custom
        )
        self.ui_manager.add_component(self.custom_button)
        
        # Calculate positions for bottom buttons (Random and Exit)
        bottom_button_width = 100
        bottom_button_height = 30
        bottom_buttons_y = conversions_y + button_height + 10  # Below main grid with margin
        
        # Center the bottom buttons
        total_bottom_width = (bottom_button_width * 2) + grid_spacing
        bottom_start_x = (ui_width - total_bottom_width) // 2
        
        random_x = bottom_start_x
        exit_x = bottom_start_x + bottom_button_width + grid_spacing
        
        # Create Random button
        self.random_button = Button(
            random_x, bottom_buttons_y, bottom_button_width, bottom_button_height,
            "RANDOM", self.on_random_selection,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
        )
        self.ui_manager.add_component(self.random_button)
        
        # Create Exit button (disabled if first pet)
        self.exit_button = Button(
            exit_x, bottom_buttons_y, bottom_button_width, bottom_button_height,
            "EXIT", self.on_exit_selection,
            cut_corners={'tl': False, 'tr': True, 'bl': True, 'br': False},
            enabled=not self.is_first_pet  # Disabled if first pet
        )
        self.ui_manager.add_component(self.exit_button)
        
        runtime_globals.game_console.log("[SceneEggSelection] Category selection UI setup completed successfully")

    def setup_module_selection_ui(self):
        """Setup the UI components for module selection."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Create background with dark grey region for module info area  
        self.background = Background(ui_width, ui_height)
        # Black background with dark grey info area (increased height for Adventure Mode bar)
        info_area_width = 220
        info_area_height = 180  # Increased from 160 to accommodate Adventure Mode bar
        info_area_x = (ui_width - info_area_width) // 2
        info_area_y = 30
        info_area_end = info_area_y + info_area_height
        
        self.background.set_regions([
            (0, info_area_y, "black"),
            (info_area_y, info_area_end, "dark_bg"),
            (info_area_end, ui_height, "black")
        ])
        self.ui_manager.add_component(self.background)
        
        # Title showing selected category
        category_title = f"{self.selected_category} Modules"
        self.title_scene = TitleScene(0, 9, category_title)
        self.ui_manager.add_component(self.title_scene)
        
        # Module logo (100x50, positioned to the right)
        logo_width = 100
        logo_height = 50
        logo_x = BASE_RESOLUTION - logo_width - 10
        logo_y = info_area_y + 10
        
        self.module_logo_image = Image(logo_x, logo_y, logo_width, logo_height)
        self.ui_manager.add_component(self.module_logo_image)
        
        # Module information labels (left side)
        info_x = info_area_x + 10
        info_y = logo_y
        
        # Module name label
        self.module_name_label = Label(info_x, info_y, "", is_title=True)
        self.ui_manager.add_component(self.module_name_label)
        
        # Version and author labels
        version_y = info_y + 25
        self.version_label = Label(info_x, version_y, "", color_override=GRAY)
        self.ui_manager.add_component(self.version_label)
        
        # Statistics section
        stats_start_y = version_y + 15
        egg_label_width = 50
        label_width = 110
        bar_width = 190
        bar_height = 14
        line_spacing = 18
        bars_x = egg_label_width + 40
        bar_y_difference = 0 # Vertical offset for bars relative to labels
        
        # Eggs count
        eggs_y = stats_start_y
        self.eggs_label = LabelValue(info_x, eggs_y, egg_label_width, 15, "Eggs:", "0", color_override=GRAY, value_color=BLUE)
        self.ui_manager.add_component(self.eggs_label)
        
        # Digidex percentage and bar (green theme)
        digidex_y = eggs_y + line_spacing
        self.digidex_label = LabelValue(info_x, digidex_y, label_width, 15, "Digidex:", "0%", color_override=GRAY, value_color=GREEN)
        self.ui_manager.add_component(self.digidex_label)
        
        digidex_bar_y = digidex_y + bar_y_difference 
        self.digidex_bar = ExperienceBar(bars_x, digidex_bar_y, bar_width, bar_height, color_theme="green")
        self.ui_manager.add_component(self.digidex_bar)
        
        # Backgrounds percentage and bar (purple theme)
        backgrounds_y = digidex_y + line_spacing
        self.backgrounds_label = LabelValue(info_x, backgrounds_y, label_width, 15, "Backgrounds:", "0%", color_override=GRAY, value_color=PURPLE)
        self.ui_manager.add_component(self.backgrounds_label)
        
        backgrounds_bar_y = backgrounds_y + bar_y_difference
        self.backgrounds_bar = ExperienceBar(bars_x, backgrounds_bar_y, bar_width, bar_height, color_theme="purple")
        self.ui_manager.add_component(self.backgrounds_bar)
        
        # Secrets percentage and bar (yellow theme)
        secrets_y = backgrounds_y + line_spacing
        self.secrets_label = LabelValue(info_x, secrets_y, label_width, 15, "Secrets:", "0%", color_override=GRAY, value_color=YELLOW)
        self.ui_manager.add_component(self.secrets_label)
        
        secrets_bar_y = secrets_y + bar_y_difference
        self.secrets_bar = ExperienceBar(bars_x, secrets_bar_y, bar_width, bar_height, color_theme="yellow")
        self.ui_manager.add_component(self.secrets_bar)
        
        # Adventure Mode percentage and bar (red theme)
        adventure_y = secrets_y + line_spacing
        self.adventure_label = LabelValue(info_x, adventure_y, label_width, 15, "Adventure:", "0%", color_override=GRAY, value_color=RED)
        self.ui_manager.add_component(self.adventure_label)
        
        adventure_bar_y = adventure_y + bar_y_difference
        self.adventure_bar = ExperienceBar(bars_x, adventure_bar_y, bar_width, bar_height, color_theme="red")
        self.ui_manager.add_component(self.adventure_bar)
        
        # Navigation and action buttons at the bottom
        button_y = adventure_y + line_spacing + 10  # Below all stats with margin
        button_width = 40
        button_height = 25
        button_spacing = 10
        
        # Previous button (<)
        prev_x = info_area_x
        self.prev_button = Button(prev_x, button_y, button_width, button_height, "<", self.on_prev_module)
        self.ui_manager.add_component(self.prev_button)
        
        # Next button (>)
        next_x = info_area_x + info_area_width - button_width
        self.next_button = Button(next_x, button_y, button_width, button_height, ">", self.on_next_module)
        self.ui_manager.add_component(self.next_button)
        
        # Select button (center-left)
        select_width = 60
        select_x = (ui_width // 2) - select_width - (button_spacing // 2)
        self.select_button = Button(select_x, button_y, select_width, button_height, "SELECT", self.on_select_module)
        self.ui_manager.add_component(self.select_button)
        
        # Back button (center-right)
        back_width = 60
        back_x = (ui_width // 2) + (button_spacing // 2)
        self.back_button = Button(back_x, button_y, back_width, button_height, "BACK", self.on_back_to_category)
        self.ui_manager.add_component(self.back_button)
        
        # Load current module data
        self.update_module_display()
        
        runtime_globals.game_console.log("[SceneEggSelection] Module selection UI setup completed successfully")

    def setup_egg_selection_ui(self):
        """Setup the UI components for egg selection."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Create background with dark grey region for egg grid area (same as module selection)
        self.background = Background(ui_width, ui_height)
        # Black background with dark grey grid area - maximized for grid
        grid_area_width = 230  # Increased from 220 to use more space
        grid_area_height = 185  # Increased from 170 to accommodate larger grid
        grid_area_x = (ui_width - grid_area_width) // 2
        grid_area_y = 30
        grid_area_end = grid_area_y + grid_area_height
        
        self.background.set_regions([
            (0, grid_area_y, "black"),
            (grid_area_y, grid_area_end, "dark_bg"),
            (grid_area_end, ui_height, "black")
        ])
        self.ui_manager.add_component(self.background)
        
        # Title showing selected module
        if self.available_modules:
            selected_module_name = self.available_modules[self.current_module_index]
            title_text = f"{selected_module_name} Eggs"
        else:
            title_text = "Egg Selection"
        self.title_scene = TitleScene(0, 9, title_text)
        self.ui_manager.add_component(self.title_scene)
        
        # Grid for egg display - maximized within gray area
        grid_width = 225  # Very thin border (2.5px on each side)
        grid_height = 140  # Increased height for larger grid
        grid_x = (ui_width - grid_width) // 2
        grid_y = grid_area_y + 5  # Minimal top margin within gray area
        
        self.egg_grid = Grid(grid_x, grid_y, grid_width, grid_height, rows=2, columns=2)
        self.egg_grid.on_selection_change = self.on_egg_selection_change
        self.egg_grid.on_page_change = self.on_egg_page_change
        self.ui_manager.add_component(self.egg_grid)
        
        # Navigation and action buttons at the bottom (matching module selection layout exactly)
        button_y = grid_y + grid_height + 8  # Reduced margin to fit in larger gray area
        button_width = 40
        button_height = 25
        button_spacing = 10
        
        # Use the same info_area_x and info_area_width as module selection for consistent positioning
        info_area_width = 220
        info_area_x = (ui_width - info_area_width) // 2
        
        # Previous page button (<) - positioned at left edge of info area (same as module selection)
        prev_x = info_area_x
        self.egg_prev_button = Button(prev_x, button_y, button_width, button_height, "<", self.on_egg_prev_page)
        self.ui_manager.add_component(self.egg_prev_button)
        
        # Next page button (>) - positioned at right edge of info area (same as module selection)
        next_x = info_area_x + info_area_width - button_width
        self.egg_next_button = Button(next_x, button_y, button_width, button_height, ">", self.on_egg_next_page)
        self.ui_manager.add_component(self.egg_next_button)
        
        # Select button (center-left) - exact same positioning as module selection
        select_width = 60
        select_x = (ui_width // 2) - select_width - (button_spacing // 2)
        self.egg_select_button = Button(select_x, button_y, select_width, button_height, "SELECT", self.on_egg_select)
        self.ui_manager.add_component(self.egg_select_button)
        
        # Back button (center-right) - exact same positioning as module selection
        back_width = 60
        back_x = (ui_width // 2) + (button_spacing // 2)
        self.egg_back_button = Button(back_x, button_y, back_width, button_height, "BACK", self.on_egg_back_to_module)
        self.ui_manager.add_component(self.egg_back_button)
        
        # Load eggs for current module
        self.load_eggs_for_module()
        
        runtime_globals.game_console.log("[SceneEggSelection] Egg selection UI setup completed successfully")

    def load_available_modules(self, category):
        """Load available modules based on the selected category."""
        self.available_modules = []
        
        # Get all modules from runtime globals
        for module_name, module in runtime_globals.game_modules.items():
            # In Progress Mode, skip modules the player doesn't own (Tutorial always allowed)
            if game_globals.is_progress_mode():
                if module_name.lower() != 'tutorial' and not game_globals.purchases.owns_module_name(module_name):
                    continue
            
            # Filter modules by category
            module_category = getattr(module, 'category', 'Custom')  # Default to Custom if no category
            
            # Flexible category matching - case insensitive and handle plurals
            if (module_category.lower() == category.lower() or 
                (category.lower() == 'classic' and module_category.lower() in ['classic', 'classics']) or
                (category.lower() == 'modern' and module_category.lower() in ['modern', 'moderns']) or
                (category.lower() == 'conversions' and module_category.lower() in ['conversion', 'conversions']) or
                (category.lower() == 'custom' and module_category.lower() in ['custom', 'customs', 'other', ''])):
                
                eggs = module.get_monsters_by_stage(0)
                if eggs:  # Only include modules that have eggs
                    self.available_modules.append(module_name)
        
        # Clear stats cache when loading new modules for a category
        self.module_stats_cache = {}
        
        # Calculate stats for all modules in this category
        for module_name in self.available_modules:
            self.module_stats_cache[module_name] = self.calculate_module_stats(module_name)
        
        # If no modules found in category, show all modules as fallback
        if not self.available_modules:
            runtime_globals.game_console.log(f"[SceneEggSelection] No modules found for category '{category}', showing all modules as fallback")
            for module_name, module in runtime_globals.game_modules.items():
                eggs = module.get_monsters_by_stage(0)
                if eggs:  # Only include modules that have eggs
                    self.available_modules.append(module_name)
                    self.module_stats_cache[module_name] = self.calculate_module_stats(module_name)
        
        self.current_module_index = 0
        runtime_globals.game_console.log(f"[SceneEggSelection] Loaded {len(self.available_modules)} modules for category '{category}'")

    def calculate_module_stats(self, module_name):
        """Calculate statistics for a module (with caching)."""
        module = get_module(module_name)
        stats = {}
        
        # Calculate Digidex percentage
        all_monsters = module.get_all_monsters()
        total_monsters = len(all_monsters)
        known_monsters = 0
        
        for monster in all_monsters:
            if is_pet_unlocked(monster["name"], module.name, monster["version"]):
                known_monsters += 1
        
        stats['digidex_percentage'] = (known_monsters / total_monsters * 100) if total_monsters > 0 else 0
        
        # Calculate Backgrounds percentage
        module_backgrounds = getattr(module, 'backgrounds', [])
        total_backgrounds = len(module_backgrounds)
        unlocked_backgrounds = get_unlocked_backgrounds(module.name, module_backgrounds)
        unlocked_background_count = len(unlocked_backgrounds)
        
        stats['backgrounds_percentage'] = (unlocked_background_count / total_backgrounds * 100) if total_backgrounds > 0 else 0
        
        # Calculate Secrets percentage
        module_unlocks = getattr(module, 'unlocks', [])
        secret_unlocks = [u for u in module_unlocks if u.get('type') not in ['adventure', 'egg', 'evolution', 'digidex']]
        total_secrets = len(secret_unlocks)
        unlocked_secrets = 0
        
        # Check unlocked secrets in game_globals
        module_unlocks_data = game_globals.unlocks.get(module.name, [])
        for secret in secret_unlocks:
            secret_name = secret.get('name', '')
            if any(u.get('name') == secret_name and u.get('type') != 'background' for u in module_unlocks_data):
                unlocked_secrets += 1
        
        stats['secrets_percentage'] = (unlocked_secrets / total_secrets * 100) if total_secrets > 0 else 0
        
        # Calculate Adventure Mode percentage
        has_adventure_mode = getattr(module, 'adventure_mode', False)
        if has_adventure_mode:
            # Get available area rounds
            try:
                # Check current area progress
                current_area = game_globals.battle_area.get(module.name, 1)
                
                # Get total areas for this module
                if hasattr(module, 'get_available_area_rounds'):
                    available_rounds = module.get_available_area_rounds()
                    total_areas = len(available_rounds) if available_rounds else 1
                elif hasattr(module, 'get_area_round_counts'):
                    area_counts = module.get_area_round_counts()
                    total_areas = len(area_counts) if area_counts else 1
                else:
                    # Fallback: check how many areas exist by testing area_exists
                    total_areas = 1
                    test_area = 2
                    while hasattr(module, 'area_exists') and module.area_exists(test_area) and test_area <= 50:
                        total_areas = test_area
                        test_area += 1
                
                # Calculate percentage based on area completion (ignore rounds)
                if current_area == 1:
                    # Area 1 means 0% completion (hasn't completed any areas yet)
                    adventure_percentage = 0.0
                else:
                    # Calculate progress based on completed areas
                    completed_areas = current_area - 1  # Areas before current one are completed
                    adventure_percentage = min((completed_areas / total_areas * 100), 100.0) if total_areas > 0 else 0.0
                
            except Exception as e:
                runtime_globals.game_console.log(f"[SceneEggSelection] Error calculating adventure progress for {module_name}: {e}")
                adventure_percentage = 0.0
        else:
            adventure_percentage = 0.0
        
        stats['adventure_percentage'] = adventure_percentage
        
        runtime_globals.game_console.log(f"[SceneEggSelection] Stats for {module_name}: Digidex={stats['digidex_percentage']:.1f}%, Backgrounds={stats['backgrounds_percentage']:.1f}%, Secrets={stats['secrets_percentage']:.1f}%, Adventure={stats['adventure_percentage']:.1f}%")
        return stats

    def load_eggs_for_module(self):
        """Load and display eggs for the currently selected module."""
        if not self.available_modules or not self.egg_grid:
            return
            
        selected_module_name = self.available_modules[self.current_module_index]
        module = get_module(selected_module_name)
        
        # Get all eggs (stage 0 monsters) from the module
        eggs = module.get_monsters_by_stage(0)
        
        # Filter out locked special eggs
        available_eggs = []
        for egg in eggs:
            # Check if this is a special egg that requires unlocking
            if egg.get("special", False):
                special_key = egg.get("special_key", "")
                module_val = egg.get("module", selected_module_name)
                
                # Special case for G-Cell fragment eggs
                if special_key == "gcell_fragment":
                    fragment_key = f"{module_val}@{egg.get('version', 1)}"
                    if hasattr(game_globals, 'gcell_fragments') and fragment_key in game_globals.gcell_fragments:
                        # Player has the fragment, allow this egg
                        available_eggs.append(egg)
                        runtime_globals.game_console.log(f"[SceneEggSelection] G-Cell fragment egg available: {egg['name']} (fragment: {fragment_key})")
                    else:
                        runtime_globals.game_console.log(f"[SceneEggSelection] Skipping G-Cell fragment egg - no fragment: {egg['name']} (needs: {fragment_key})")
                    continue
                
                # Skip other locked special eggs
                if special_key and not is_unlocked(module_val, None, special_key):
                    runtime_globals.game_console.log(f"[SceneEggSelection] Skipping locked special egg: {egg['name']} (key: {special_key})")
                    continue
            available_eggs.append(egg)
        
        # Clear existing grid items
        grid_items = []
        
        # Load sprites for each available egg
        for egg in available_eggs:
            try:
                sprite = None
                
                # First, check for device-specific sprite in devices folder
                devices_folder = os.path.join(module.folder_path, "devices")
                device_sprite_path = os.path.join(devices_folder, f"{egg['name']}.png")
                
                if os.path.exists(device_sprite_path):
                    # Load device-specific sprite
                    try:
                        sprite = image_load(device_sprite_path).convert_alpha()
                        runtime_globals.game_console.log(f"[SceneEggSelection] Using device sprite for egg: {egg['name']}")
                    except Exception as device_error:
                        runtime_globals.game_console.log(f"[SceneEggSelection] Failed to load device sprite for {egg['name']}: {device_error}")
                        sprite = None
                
                # If no device sprite found or failed to load, fall back to regular pet sprites
                if sprite is None:
                    sprites_dict = load_pet_sprites(
                        egg["name"], 
                        module.folder_path, 
                        module.name_format,
                        module_high_definition_sprites=module.high_definition_sprites
                    )
                    
                    # Get the first frame (0.png)
                    if "0" in sprites_dict:
                        sprite = sprites_dict["0"]
                
                # Create grid item with sprite and egg name
                grid_item = GridItem(
                    sprite=sprite,
                    text=egg["name"],
                    data=egg  # Store the full egg data
                )
                grid_items.append(grid_item)
                
            except Exception as e:
                runtime_globals.game_console.log(f"[SceneEggSelection] Failed to load sprite for egg {egg['name']}: {e}")
                # Create grid item without sprite
                grid_item = GridItem(
                    sprite=None,
                    text=egg["name"],
                    data=egg
                )
                grid_items.append(grid_item)
        
        # Set items in the grid
        self.egg_grid.set_items(grid_items)
        
        runtime_globals.game_console.log(f"[SceneEggSelection] Loaded {len(grid_items)} eggs for module {selected_module_name}")

    def update_module_display(self):
        """Update the module display with current module information."""
        if not self.available_modules:
            return
        
        module_name = self.available_modules[self.current_module_index]
        module = get_module(module_name)
        
        # Update module name
        if self.module_name_label:
            self.module_name_label.set_text(module_name)
        
        # Update version
        if self.version_label:
            version_text = f"Ver.: {getattr(module, 'version', '1.0')}"
            self.version_label.set_text(version_text)
        
        # Load and set module logo
        if self.module_logo_image:
            logo_path = os.path.join(module.folder_path, "logo.png")
            if os.path.exists(logo_path):
                self.module_logo_image.set_image(image_path=logo_path)
            else:
                # Clear image if no logo found
                self.module_logo_image.set_image(image_surface=None)
        
        # Update statistics using cached values
        all_eggs = module.get_monsters_by_stage(0)
        # Filter out locked special eggs for accurate count
        available_eggs = []
        for egg in all_eggs:
            if egg.get("special", False):
                special_key = egg.get("special_key", "")
                module_val = egg.get("module", module_name)
                if special_key and not is_unlocked(module_val, None, special_key):
                    continue
            available_eggs.append(egg)
        
        egg_count = len(available_eggs)
        
        if self.eggs_label:
            self.eggs_label.set_value(str(egg_count))
        
        # Get cached statistics
        stats = self.module_stats_cache.get(module_name, {})
        digidex_percentage = stats.get('digidex_percentage', 0.0)
        backgrounds_percentage = stats.get('backgrounds_percentage', 0.0)
        secrets_percentage = stats.get('secrets_percentage', 0.0)
        adventure_percentage = stats.get('adventure_percentage', 0.0)
        
        if self.digidex_label:
            self.digidex_label.set_value(f"{digidex_percentage:.0f}%")
        if self.backgrounds_label:
            self.backgrounds_label.set_value(f"{backgrounds_percentage:.0f}%")
        if self.secrets_label:
            self.secrets_label.set_value(f"{secrets_percentage:.0f}%")
        if self.adventure_label:
            self.adventure_label.set_value(f"{adventure_percentage:.0f}%")
        
        # Update progress bars with actual values
        if self.digidex_bar:
            self.digidex_bar.set_progress(digidex_percentage / 100.0)
        if self.backgrounds_bar:
            self.backgrounds_bar.set_progress(backgrounds_percentage / 100.0)
        if self.secrets_bar:
            self.secrets_bar.set_progress(secrets_percentage / 100.0)
        if self.adventure_bar:
            self.adventure_bar.set_progress(adventure_percentage / 100.0)
        
        runtime_globals.game_console.log(f"[SceneEggSelection] Updated display for module '{module_name}' v{getattr(module, 'version', '1.0')} with {egg_count} eggs")
                
    def update(self) -> None:
        """Update the egg selection scene."""
        self.window_background.update()
        self.ui_manager.update()
        
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the egg selection scene."""
        # Fill with black background first
        surface.fill((0, 0, 0))
        
        # Draw window background (for texture/pattern if needed)
        self.window_background.draw(surface)
        
        # Draw UI components on top
        self.ui_manager.draw(surface)
        
    def handle_event(self, event) -> None:
        """Handle events in the egg selection scene."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        # Handle events through UI manager first
        if self.ui_manager.handle_event(event):
            return
        
        # Handle phase-specific input actions
        if self.phase == "category":
            if event_type == "B":
                # B key has same effect as Exit button (if enabled)
                if not self.is_first_pet:
                    self.on_exit_selection()
                    return
        elif self.phase == "module_selection":
            if event_type == "R":
                # R key acts as right arrow (next module)
                self.on_next_module()
                return
            elif event_type == "L":
                # L key acts as left arrow (previous module)
                self.on_prev_module()
                return
            elif event_type == "B":
                # B key acts as back button
                self.on_back_to_category()
                return
            elif event_type == "START":
                # START key acts as select button
                self.on_select_module()
                return
        elif self.phase == "egg_selection":
            if event_type == "B":
                # B key acts as back button
                self.on_egg_back_to_module()
                return
            elif event_type == "START":
                # START key acts as select button
                self.on_egg_select()
                return
            elif event_type == "L":
                # L key acts as page left
                self.on_egg_prev_page()
                return
            elif event_type == "R":
                # R key acts as page right
                self.on_egg_next_page()
                return

    # Button callback methods for category selection
    def on_classic_selection(self):
        """Handle Classic selection button press."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[SceneEggSelection] Classic selection chosen")
        self.selected_category = "Classic"
        self.transition_to_module_selection()
        
    def on_modern_selection(self):
        """Handle Modern selection button press."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[SceneEggSelection] Modern selection chosen")
        self.selected_category = "Modern"
        self.transition_to_module_selection()
        
    def on_conversions_selection(self):
        """Handle Conversions selection button press."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[SceneEggSelection] Conversions selection chosen")
        self.selected_category = "Conversions"
        self.transition_to_module_selection()
        
    def on_custom_selection(self):
        """Handle Custom selection button press."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[SceneEggSelection] Custom selection chosen")
        self.selected_category = "Custom"
        self.transition_to_module_selection()
        
    def on_random_selection(self):
        """
        Handle Random selection button press.
        
        This method implements a full random selection process:
        1. Randomly selects a category (Classic, Modern, Conversions, Custom)
        2. Randomly selects a module from the chosen category
        3. Randomly selects an available egg from the chosen module
        4. Navigates to the egg selection phase with the random egg pre-selected
        5. Sets focus on the SELECT button for immediate confirmation
        """
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[SceneEggSelection] Random selection chosen")
        
        # Step 1: Select a random category
        categories = ["Classic", "Modern", "Conversions", "Custom"]
        random_category = random.choice(categories)
        runtime_globals.game_console.log(f"[SceneEggSelection] Random category selected: {random_category}")
        
        # Step 2: Load modules for the random category and select a random module
        self.selected_category = random_category
        self.load_available_modules(random_category)
        
        if not self.available_modules:
            runtime_globals.game_console.log("[SceneEggSelection] No modules available for random category, aborting random selection")
            return
        
        # Select random module
        self.current_module_index = random.randint(0, len(self.available_modules) - 1)
        selected_module_name = self.available_modules[self.current_module_index]
        runtime_globals.game_console.log(f"[SceneEggSelection] Random module selected: {selected_module_name}")
        
        # Step 3: Get available eggs and select a random one
        module = get_module(selected_module_name)
        all_eggs = module.get_monsters_by_stage(0)
        
        # Filter out locked special eggs (same logic as load_eggs_for_module)
        available_eggs = []
        for egg in all_eggs:
            if egg.get("special", False):
                special_key = egg.get("special_key", "")
                module_val = egg.get("module", selected_module_name)
                
                # Special case for G-Cell fragment eggs
                if special_key == "gcell_fragment":
                    fragment_key = f"{module_val}@{egg.get('version', 1)}"
                    if hasattr(game_globals, 'gcell_fragments') and fragment_key in game_globals.gcell_fragments:
                        # Player has the fragment, allow this egg
                        available_eggs.append(egg)
                    continue
                
                # Skip other locked special eggs
                if special_key and not is_unlocked(module_val, None, special_key):
                    continue
            available_eggs.append(egg)
        
        if not available_eggs:
            runtime_globals.game_console.log(f"[SceneEggSelection] No available eggs for module {selected_module_name}, aborting random selection")
            return
        
        # Select random egg
        random_egg = random.choice(available_eggs)
        runtime_globals.game_console.log(f"[SceneEggSelection] Random egg selected: {random_egg['name']}")
        
        # Step 4: Transition to egg selection phase and pre-select the random egg
        self.phase = "egg_selection"
        self.setup_ui()
        
        # Load eggs for the module and find the index of our random egg
        self.load_eggs_for_module()
        
        if self.egg_grid and self.egg_grid.items:
            # Find the index of our random egg in the grid items
            target_egg_index = -1
            for i, item in enumerate(self.egg_grid.items):
                if item.data and item.data.get('name') == random_egg['name']:
                    target_egg_index = i
                    break
            
            if target_egg_index >= 0:
                # Navigate to the correct page and select the egg
                target_page = target_egg_index // self.egg_grid.items_per_page
                self.egg_grid.current_page = target_page
                
                # Calculate the local index within the page
                local_index = target_egg_index % self.egg_grid.items_per_page
                self.egg_grid.selected_item_index = target_egg_index  # Set global index
                
                # Set the local row and column for the selected item
                self.egg_grid.selected_row = local_index // self.egg_grid.columns
                self.egg_grid.selected_col = local_index % self.egg_grid.columns
                
                # Also set the cursor to the selected item for navigation
                self.egg_grid.cursor_row = self.egg_grid.selected_row
                self.egg_grid.cursor_col = self.egg_grid.selected_col
                
                # Mark for redraw
                self.egg_grid.needs_redraw = True
                
                runtime_globals.game_console.log(f"[SceneEggSelection] Random egg pre-selected on page {target_page + 1}, index {local_index}")
        
        # Set focus on the select button as requested
        if self.egg_select_button:
            self.ui_manager.set_focused_component(self.egg_select_button)
        
    def on_exit_selection(self):
        """Handle Exit button press."""
        if not self.is_first_pet:  # Only allow exit if not first pet
            runtime_globals.game_sound.play("cancel")
            change_scene("game")
        else:
            # Should not be reachable since button is disabled for first pet
            runtime_globals.game_sound.play("cancel")

    # Button callback methods for module selection
    def on_prev_module(self):
        """Handle previous module button press."""
        runtime_globals.game_sound.play("menu")
        if self.available_modules:
            self.current_module_index = (self.current_module_index - 1) % len(self.available_modules)
            self.update_module_display()
    
    def on_next_module(self):
        """Handle next module button press."""
        runtime_globals.game_sound.play("menu")
        if self.available_modules:
            self.current_module_index = (self.current_module_index + 1) % len(self.available_modules)
            self.update_module_display()
    
    def on_select_module(self):
        """Handle select module button press."""
        runtime_globals.game_sound.play("menu")
        if self.available_modules:
            selected_module = self.available_modules[self.current_module_index]
            runtime_globals.game_console.log(f"[SceneEggSelection] Selected module: {selected_module}")
            # Transition to egg selection phase
            self.transition_to_egg_selection()
    
    def on_back_to_category(self):
        """Handle back to category button press."""
        runtime_globals.game_sound.play("cancel")
        self.phase = "category"
        self.setup_ui()
        
        # Set focus back to the previously selected category
        if self.selected_category == "Classic" and self.classic_button:
            self.ui_manager.set_focused_component(self.classic_button)
        elif self.selected_category == "Modern" and self.modern_button:
            self.ui_manager.set_focused_component(self.modern_button)
        elif self.selected_category == "Conversions" and self.conversions_button:
            self.ui_manager.set_focused_component(self.conversions_button)
        elif self.selected_category == "Custom" and self.custom_button:
            self.ui_manager.set_focused_component(self.custom_button)

    # Transition methods
    def transition_to_module_selection(self):
        """Transition from category selection to module selection."""
        self.load_available_modules(self.selected_category)
        self.phase = "module_selection"
        self.setup_ui()
        
        # Set focus on select button
        if self.select_button:
            self.ui_manager.set_focused_component(self.select_button)

    def transition_to_egg_selection(self):
        """Transition from module selection to egg selection."""
        self.phase = "egg_selection"
        self.setup_ui()
        
        # Set focus on grid
        if self.egg_grid:
            self.ui_manager.set_focused_component(self.egg_grid)

    # Button callback methods for egg selection
    def on_egg_selection_change(self, selected_item):
        """Handle egg selection change in grid."""
        if selected_item and selected_item.data:
            egg_data = selected_item.data
            runtime_globals.game_console.log(f"[SceneEggSelection] Selected egg: {egg_data['name']}")
    
    def on_egg_page_change(self, current_page, total_pages):
        """Handle egg grid page change."""
        runtime_globals.game_console.log(f"[SceneEggSelection] Page {current_page + 1} of {total_pages}")
    
    def on_egg_prev_page(self):
        """Handle previous page button press."""
        runtime_globals.game_sound.play("menu")
        if self.egg_grid:
            self.egg_grid.change_page(-1)
    
    def on_egg_next_page(self):
        """Handle next page button press."""
        runtime_globals.game_sound.play("menu")
        if self.egg_grid:
            self.egg_grid.change_page(1)
    
    def on_egg_select(self):
        """Handle egg select button press."""
        runtime_globals.game_sound.play("menu")
        if self.egg_grid:
            # Check if there's actually a selected item (with background highlighting)
            if self.egg_grid.selected_item_index >= 0:
                # Get the item at the globally selected index
                if 0 <= self.egg_grid.selected_item_index < len(self.egg_grid.items):
                    selected_item = self.egg_grid.items[self.egg_grid.selected_item_index]
                    if selected_item and selected_item.data:
                        egg_data = selected_item.data
                        runtime_globals.game_console.log(f"[SceneEggSelection] Starting new journey with egg: {egg_data['name']}")
                        self.select_egg(egg_data)
                        return
            
            # If no item is selected with highlighting, just get the currently focused item
            selected_item = self.egg_grid.get_selected_item()
            if selected_item and selected_item.data:
                egg_data = selected_item.data
                runtime_globals.game_console.log(f"[SceneEggSelection] Starting new journey with focused egg: {egg_data['name']}")
                self.select_egg(egg_data)
    
    def select_egg(self, selected_egg):
        """Create a new pet from the selected egg and add it to the game."""
        runtime_globals.game_console.log(f"[SceneEggSelection] Selected egg: {selected_egg['name']}")
        
        # Create new pet from egg data
        pet = GamePet(selected_egg)
        
        # Register in digidex
        register_digidex_entry(pet.name, pet.module, pet.version)
        
        # Handle traited eggs if applicable
        egg_key = f"{selected_egg['module']}@{selected_egg['version']}"
        if egg_key in game_globals.traited:
            pet.traited = True
            game_globals.traited.remove(egg_key)
            
        # Handle G-Cell fragment eggs if applicable
        if selected_egg.get("special", False) and selected_egg.get("special_key") == "gcell_fragment":
            fragment_key = f"{selected_egg['module']}@{selected_egg['version']}"
            if hasattr(game_globals, 'gcell_fragments') and fragment_key in game_globals.gcell_fragments:
                pet.gcell_fragment = True
                game_globals.gcell_fragments.remove(fragment_key)
                runtime_globals.game_console.log(f"[SceneEggSelection] Used G-Cell fragment {fragment_key} to hatch {pet.name}")
        
        # Add pet to the game
        game_globals.pet_list.append(pet)
        
        # Set background if this is the first pet
        bg_name = f"ver{selected_egg['version']}"
        if not game_globals.game_background:
            game_globals.game_background = bg_name
            game_globals.background_module_name = selected_egg["module"]
        
        # Unlock egg-related items
        module = get_module(selected_egg["module"])
        module_unlockables = getattr(module, 'unlocks', [])
        unlocks = module_unlockables if isinstance(module_unlockables, list) else []
        for unlock in unlocks:
            if unlock.get("type") == "egg":
                if "version" not in unlock or unlock.get("version") == selected_egg["version"]:
                    unlock_item(selected_egg["module"], "egg", unlock["name"])
        
        # Reward: new pet slot unlocked
        omninet_service.claim_reward("unlock", f"unlock:{selected_egg['module']}")

        # Go to game scene
        change_scene("game")
        distribute_pets_evenly()
    
    def on_egg_back_to_module(self):
        """Handle back to module selection button press."""
        runtime_globals.game_sound.play("cancel")
        self.phase = "module_selection"
        self.setup_ui()
        
        # Set focus back on select button
        if self.select_button:
            self.ui_manager.set_focused_component(self.select_button)

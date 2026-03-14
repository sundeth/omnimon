import pygame

from components.ui.ui_manager import UIManager
from components.ui.background import Background
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.menu import Menu
from components.ui.digidex_list import DigidexList
from components.ui.digidex_tree import DigidexTree
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals
import core.constants as constants
from core.game_digidex import is_pet_unlocked, load_digidex
from core.game_digidex_entry import GameDigidexEntry
from core.utils.pygame_utils import  sprite_load_percent
from components.window_background import WindowBackground
from core.utils.scene_utils import change_scene
from core.utils.utils_unlocks import unlock_item

UNKNOWN_SPRITE_PATH = constants.UNKNOWN_SPRITE_PATH
SPRITE_BUFFER = 10 
SPRITE_FRAME = "0.png"
SPRITE_SIZE = int(48 * runtime_globals.UI_SCALE)


class SceneDigidex:
    """Refactored SceneDigidex: uses DigidexList as main view and DigidexTree as the tree view.

    The implementation preserves the original sprite-loading window behaviour and tree
    drawing logic but delegates UI responsibilities to the new components.
    """
    def __init__(self):
        # Global background (animated)
        self.window_background = WindowBackground(False)
        
        # UI Manager with LIME theme
        self.ui_manager = UIManager(theme="LIME")
        
        # Connect input manager to UI manager
        self.ui_manager.set_input_manager(runtime_globals.game_input)
        
        # Load unknown sprite for list/tree
        self.unknown_sprite = sprite_load_percent(
            UNKNOWN_SPRITE_PATH, 
            percent=(SPRITE_SIZE / runtime_globals.SCREEN_HEIGHT) * 100, 
            keep_proportion=True, 
            base_on="height"
        )

        self.digidex_data = load_digidex()
        self.pets = self.build_pet_list()
        self.all_pets = self.pets.copy()  # Store unfiltered list for filtering

        # View state: 'list' (main), 'tree'
        self.state = 'list'
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.list_view = None
        self.tree_view = None
        self.up_button = None
        self.down_button = None
        self.tree_button = None
        self.back_button = None
        
        self._setup_ui()
        
        runtime_globals.game_console.log("[SceneDigidex] Digidex scene initialized with UI system (LIME theme).")

    def _setup_ui(self):
        """Setup UI components for the digidex scene."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "DIGIDEX")
        self.ui_manager.add_component(self.title_scene)
        
        # Filter button (top right, before EXIT)
        filter_button_width = 55
        filter_button_height = 20
        self.filter_button = Button(ui_width - filter_button_width - 60, 5, filter_button_width, filter_button_height, "FILTER", self._on_filter_click)
        self.ui_manager.add_component(self.filter_button)
        
        # Exit button (top right, next to title)
        exit_button_width = 50
        exit_button_height = 20
        self.exit_button = Button(ui_width - exit_button_width - 5, 5, exit_button_width, exit_button_height, "EXIT", self._on_exit_click)
        self.ui_manager.add_component(self.exit_button)
        
        # Filter state
        self.active_filters = {"module": None, "stage": None, "known": None}
        
        # List view (initially visible) - now has more vertical space
        # List takes space from y=30 to bottom (y=232)
        list_height = 202
        self.list_view = DigidexList(5, 30, 230, list_height, self.unknown_sprite, sprite_size=SPRITE_SIZE)
        self.list_view.set_pets(self.pets)
        self.list_view.on_selection_callback = self._on_list_selection
        self.ui_manager.add_component(self.list_view)
        
        # Tree view (initially hidden)
        self.tree_view = DigidexTree(5, 30, 230, list_height, self.unknown_sprite, sprite_size=SPRITE_SIZE)
        self.tree_view.set_pets(self.pets)
        self.tree_view.on_back = self._on_tree_back
        self.tree_view.visible = False
        self.ui_manager.add_component(self.tree_view)
        
        # Set initial focus to list view
        self.ui_manager.set_focused_component(self.list_view)

    def build_pet_list(self):
        all_entries = []
        known_count_by_module = {}

        for module in runtime_globals.game_modules.values():
            monsters = module.get_all_monsters()
            module_known_count = 0

            for monster in monsters:
                name = monster["name"]
                version = monster["version"]
                attribute = monster.get("attribute", "")
                stage = monster.get("stage", 0)
                name_format = module.name_format
                known = is_pet_unlocked(name, module.name, version)

                if not known:
                    name = "????"
                    attribute = "???"
                    sprite = self.unknown_sprite
                else:
                    module_known_count += 1
                    sprite = None

                entry = GameDigidexEntry(name, attribute, stage, module.name, version, sprite, known, name_format)
                all_entries.append(entry)

            known_count_by_module[module.name] = module_known_count

        for module in runtime_globals.game_modules.values():
            unlocks = getattr(module, "unlocks", [])
            if isinstance(unlocks, list):
                module_known_count = known_count_by_module.get(module.name, 0)
                for unlock in unlocks:
                    if unlock.get("type") == "digidex" and "amount" in unlock:
                        if module_known_count >= unlock["amount"]:
                            unlock_item(module.name, "digidex", unlock["name"])

        all_entries.sort(key=lambda e: (e.stage, e.module.lower(), e.version))
        return all_entries

    def update(self):
        # Update shared window background
        self.window_background.update()
        
        # Update UI manager (delegates to active components)
        self.ui_manager.update()

    def draw(self, surface: pygame.Surface):
        # Draw shared window background
        self.window_background.draw(surface)
        
        # Draw UI components via manager
        self.ui_manager.draw(surface)

    def handle_event(self, event):
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        
        event_type, event_data = event
        
        # Handle events through UIManager
        if self.ui_manager.handle_event(event):
            return True
        
        # Enable keyboard navigation mode for keyboard/scroll inputs
        if event_type in ["B"]:
            self.ui_manager.keyboard_navigation_mode = True
        
            if self.state == 'tree':
                self._on_tree_back()
                runtime_globals.game_sound.play("cancel")
                return True
            elif self.state == 'list':
                change_scene('game')
                runtime_globals.game_sound.play("cancel")
                return True
                
    
    def _on_list_selection(self, selected_pet):
        """Callback when a pet is selected in the list view"""
        if selected_pet and selected_pet.known:
            # Switch to tree view
            self.list_view.visible = False
            self.tree_view.visible = True
            self.filter_button.visible = False  # Hide filter button in tree view
            self.exit_button.text = "BACK"  # Change EXIT to BACK in tree view
            self.exit_button.needs_redraw = True
            self.state = 'tree'
            
            # Load and set tree data
            root = self.find_stage_zero_entry(selected_pet)
            tree_data = self.load_evolution_tree(selected_pet)
            self.tree_view.set_root(root, tree_data, selected_pet=selected_pet)
            
            # Set focus to tree view
            self.ui_manager.set_focused_component(self.tree_view)
            
            runtime_globals.game_console.log(f"[SceneDigidex] Switched to tree view for {selected_pet.name}")

    def _on_tree_back(self):
        """Called by tree component when user requests back"""
        runtime_globals.game_console.log("[SceneDigidex] _on_tree_back called")
        self.tree_view.visible = False
        self.list_view.visible = True
        self.filter_button.visible = True  # Show filter button in list view
        self.exit_button.text = "EXIT"  # Change BACK to EXIT in list view
        self.exit_button.needs_redraw = True
        self.state = 'list'
        
        # Set focus back to list view
        self.ui_manager.set_focused_component(self.list_view)
        
        runtime_globals.game_console.log("[SceneDigidex] Returned to list view")
    
    def _on_exit_click(self):
        """EXIT button clicked - exit digidex or return to list from tree"""
        runtime_globals.game_console.log(f"[SceneDigidex] EXIT button clicked, state={self.state}")
        if self.state == 'list':
            change_scene('game')
            runtime_globals.game_sound.play("cancel")
        elif self.state == 'tree':
            self._on_tree_back()
            runtime_globals.game_sound.play("cancel")
    
    def _on_filter_click(self):
        """FILTER button clicked - show filter menu"""
        runtime_globals.game_console.log("[SceneDigidex] FILTER button clicked")
        
        # Create and open filter menu
        menu = Menu(width=120, height=100)
        menu.open(
            options=["Module", "Stage", "Known", "Reset"],
            on_select=self._on_filter_menu_select,
            on_cancel=lambda: None
        )
        self.ui_manager.set_active_menu(menu)
        runtime_globals.game_sound.play("menu")
    
    def _on_filter_menu_select(self, option_index):
        """Handle filter menu selection"""
        options = ["Module", "Stage", "Known", "Reset"]
        selected = options[option_index]
        runtime_globals.game_console.log(f"[SceneDigidex] Filter option selected: {selected}")
        
        if selected == "Module":
            # Show module submenu
            module_names = [mod.name for mod in runtime_globals.game_modules.values()]
            menu = Menu(width=120, height=min(200, 20 + len(module_names) * 20))
            menu.open(
                options=module_names,
                on_select=lambda idx: self._apply_filter("module", module_names[idx]),
                on_cancel=lambda: None
            )
            self.ui_manager.set_active_menu(menu)
        
        elif selected == "Stage":
            # Show stage submenu
            stage_list = constants.STAGES
            menu = Menu(width=150, height=min(200, 20 + len(stage_list) * 20))
            menu.open(
                options=stage_list,
                on_select=lambda idx: self._apply_filter("stage", idx),
                on_cancel=lambda: None
            )
            self.ui_manager.set_active_menu(menu)
        
        elif selected == "Known":
            # Show yes/no submenu
            menu = Menu(width=100, height=60)
            menu.open(
                options=["Yes", "No"],
                on_select=lambda idx: self._apply_filter("known", idx == 0),
                on_cancel=lambda: None
            )
            self.ui_manager.set_active_menu(menu)
        
        elif selected == "Reset":
            # Clear all filters
            self._clear_filters()
    
    def _apply_filter(self, filter_type, value):
        """Apply a filter and refresh the list"""
        runtime_globals.game_console.log(f"[SceneDigidex] Applying filter: {filter_type}={value}")
        self.active_filters[filter_type] = value
        self._refresh_filtered_list()
        runtime_globals.game_sound.play("menu")
    
    def _clear_filters(self):
        """Clear all active filters"""
        runtime_globals.game_console.log("[SceneDigidex] Clearing all filters")
        self.active_filters = {"module": None, "stage": None, "known": None}
        self._refresh_filtered_list()
        runtime_globals.game_sound.play("menu")
    
    def _refresh_filtered_list(self):
        """Refresh the list view with filtered pets"""
        filtered_pets = self.all_pets.copy()
        
        # Apply module filter
        if self.active_filters["module"] is not None:
            filtered_pets = [p for p in filtered_pets if p.module == self.active_filters["module"]]
        
        # Apply stage filter
        if self.active_filters["stage"] is not None:
            filtered_pets = [p for p in filtered_pets if p.stage == self.active_filters["stage"]]
        
        # Apply known filter
        if self.active_filters["known"] is not None:
            filtered_pets = [p for p in filtered_pets if p.known == self.active_filters["known"]]
        
        # Update list view
        self.pets = filtered_pets
        self.list_view.set_pets(filtered_pets)
        self.list_view.selected_index = 0
        self.list_view.scroll_offset = 0
        self.list_view.needs_redraw = True
        
        runtime_globals.game_console.log(f"[SceneDigidex] Filtered list: {len(filtered_pets)} pets")

    # Keep helper functions for building/loading tree (copied from original for fidelity)
    def load_evolution_tree(self, root_entry):
        module = next((m for m in runtime_globals.game_modules.values() if m.name == root_entry.module), None)
        if not module:
            runtime_globals.game_console.log(f"[Digidex] Módulo '{root_entry.module}' não encontrado.")
            return {}

        tree = {}
        monsters = module.get_all_monsters()
        monsters = [m for m in monsters if m["version"] == root_entry.version]
        valid_names = {m["name"] for m in monsters}
        for monster in monsters:
            name = monster["name"]
            evolutions = monster.get("evolve", [])
            tree[name] = [evo["to"] for evo in evolutions if evo["to"] in valid_names]
        return tree

    def find_stage_zero_entry(self, pet):
        for entry in self.pets:
            if entry.module == pet.module and entry.version == pet.version and entry.stage == 0:
                return entry
        return pet

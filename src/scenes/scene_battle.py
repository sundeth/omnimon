"""
Scene Battle - Refactored to use view architecture
Manages battle-related views and delegates draw/update/input to the current view
"""
import pygame
from ui.ui_manager import UIManager
from core import runtime_globals
from ui.windows.window_background import WindowBackground
from scenes.battle_views import (
    AdventureView,
    JogressView,
    ArmorView,
    VersusView,
    ProtocolView,
    VersusBattleView,
    AdventureModuleSelectionView,
    AdventureAreaSelectionView,
    AdventureBattleView
)


class SceneBattle:
    """
    Battle scene using view-based architecture.
    Each view handles its own UI components and logic.
    """
    
    def __init__(self) -> None:
        # Use RED theme for battle
        self.ui_manager = UIManager("RED")
        
        # Connect input manager to UI manager for mouse handling
        self.ui_manager.set_input_manager(runtime_globals.game_input)
        
        # Current view
        self.current_view = None
        self.current_view_name = None

        self.window_background = WindowBackground(False)
        
        # View kwargs (for passing data between views)
        self.view_kwargs = {}
        
        # Check if this is a random encounter triggered by an event
        if runtime_globals.special_encounter:
            module_name, area, round_num = runtime_globals.special_encounter
            runtime_globals.special_encounter = []
            from utils.module_utils import get_module
            module = get_module(module_name)
            self._change_view("adventure_battle", module=module, area=area, round_num=round_num, is_random_encounter=True)
        else:
            self._change_view("main_menu")
        
        runtime_globals.game_console.log("[SceneBattle] Battle scene initialized with view architecture")
    
    def _change_view(self, view_name, **kwargs):
        """Change to a new view.
        
        Args:
            view_name: Name of the view to change to
            **kwargs: Additional arguments to pass to the view constructor
        """
        # Cleanup old view
        if self.current_view:
            try:
                self.current_view.cleanup()
            except Exception as e:
                runtime_globals.game_console.log(f"[SceneBattle] Error cleaning up view {self.current_view_name}: {e}")
        
        # Create new view
        self.current_view_name = view_name
        self.view_kwargs = kwargs
        
        view_map = {
            "main_menu": AdventureView,
            "jogress": JogressView,
            "armor": ArmorView,
            "versus": VersusView,
            "protocol": ProtocolView,
            "versus_battle": VersusBattleView,
            "adventure_module_selection": AdventureModuleSelectionView,
            "adventure_area_selection": AdventureAreaSelectionView,
            "adventure_battle": AdventureBattleView,
        }
        
        view_class = view_map.get(view_name)
        if not view_class:
            runtime_globals.game_console.log(f"[SceneBattle] ERROR: Unknown view '{view_name}'")
            return
        
        try:
            # Create view with ui_manager, change_view callback, and any additional kwargs
            self.current_view = view_class(self.ui_manager, self._change_view, **kwargs)
            runtime_globals.game_console.log(f"[SceneBattle] Changed to view: {view_name}")
        except Exception as e:
            runtime_globals.game_console.log(f"[SceneBattle] ERROR creating view {view_name}: {e}")
            import traceback
            runtime_globals.game_console.log(f"[SceneBattle] Traceback: {traceback.format_exc()}")
            raise
    
    def update(self):
        """Update the current view and UI manager."""
        # Update UI manager first
        self.ui_manager.update()
        
        # Update current view
        if self.current_view:
            self.current_view.update()
    
    def draw(self, surface: pygame.Surface):
        """Draw the current view."""
        # Clear screen
        self.window_background.draw(surface)
        
        # Hide UI during battle views (only show HP bar which is drawn by battle encounter)
        if self.current_view_name not in ["versus_battle", "adventure_battle"]:
            # Draw UI manager (handles UI components)
            self.ui_manager.draw(surface)
        
        # Draw current view (handles additional drawing like battle encounters)
        if self.current_view:
            self.current_view.draw(surface)
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        # For MOUSE_MOTION events, let the view handle them first (for minigame shake detection)
        # Then let UI manager handle them for cursor updates
        if event_type == "MOUSE_MOTION":
            if self.current_view:
                self.current_view.handle_event(event)
            # Let UI manager also handle for cursor/hover effects
            self.ui_manager.handle_event(event)
            return
        
        # Handle events through UI manager first
        if self.ui_manager.handle_event(event):
            return  # Event was handled by UI manager
        
        # Delegate to current view for any additional event handling
        if self.current_view:
            self.current_view.handle_event(event)
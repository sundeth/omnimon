# SceneConnect Refactoring Summary

## Overview
Successfully refactored SceneConnect from a monolithic 4521-line scene file into a view-based architecture similar to SceneBattle. The refactored scene uses 8 separate view classes, each responsible for a specific UI state.

## Changes Made

### 1. New View Architecture
Created `scenes/connect_views/` folder with the following views:

#### MainMenuView (`main_menu_view.py`) - ~500 lines
- Main connect menu with 4 main buttons (Arena, LocalBattle, Shop, Config)
- Sub-menus for Arena (WiFi, Discord), LocalBattle (WiFi, DCom), and Config
- Background availability checks for Shop (OmniNet), WiFi, and DCom
- Dynamic button states (Loading → Enabled/Offline)
- Description panels for focused options

#### PetSelectionView (`pet_selection_view.py`) - ~170 lines
- Pet selector for choosing battle pets
- Supports different max_pets based on mode (WiFi: 3, Discord: 3, DCom: 1)
- Confirmation and back navigation

#### WifiHostingView (`wifi_hosting_view.py`) - ~320 lines
- Host/Join menu for WiFi local battles
- Hosting: Shows 4-character code, waits for connection
- Discovery: UDP broadcast-based device discovery
- Socket-based networking with JSON protocol

#### WifiDiscoveryView (`wifi_discovery_view.py`) - ~220 lines
- Device discovery for joining WiFi battles
- Lists discovered devices with host codes
- Connection establishment

#### DComView (`dcom_view.py`) - ~450 lines
- DCom device battle flow
- Device scanning and selection
- Protocol selection (V_PET, PEN_X, COLOR)
- Battle format selection (DM20, PEN20, DMX, PENZ)
- Minigames:
  - DummyCharge (DM20): Click rapidly for 2.5s
  - XaiRoll (DMX): Shake/move mouse to roll
  - XaiBar (DMX): Minigame strength bar
- Communication thread with packet generation

#### DiscordView (`discord_view.py`) - ~340 lines
- Discord online matchmaking
- Host/Join menu
- Room browser with refresh
- Room creation with name input
- Polling for opponent connection

#### LinkDialogView (`link_dialog_view.py`) - ~150 lines
- Discord account linking
- 4-character code entry
- Pairing with Discord bot
- Can be called from different contexts (main menu, Arena submenu)

#### BattleConfirmView (`battle_confirm_view.py`) - ~230 lines
- Pre-battle confirmation screen
- Shows opponent info, device type, selected pet, battle format
- Start button → launches SceneBattle with appropriate connection params
- Cancel button → returns to appropriate view
- Supports WiFi, DCom, and Discord modes

### 2. Refactored SceneConnect (`scene_connect.py`) - ~380 lines
Reduced from 4521 lines to 380 lines by:
- Removing all phase-specific setup methods (~4000 lines of UI code)
- Removing phase management logic (replaced with view architecture)
- Keeping only essential components:
  - DiscordModule class (inline Discord client)
  - View management (`_change_view()` method)
  - View map dictionary
  - Standard scene methods (update, draw, handle_event)

### 3. Preserved Functionality
- **DiscordModule**: Inline HTTP client for Discord bot integration
  - Account linking with pairing codes
  - Room creation and joining
  - Data sending and room polling
  - Persistent login (saves to `save/discord_data.json`)

### 4. Architecture Pattern
Following SceneBattle's pattern:
```python
class SceneConnect:
    def __init__(self, initial_view="main_menu", **kwargs):
        self.ui_manager = UIManager(theme="RED_DARK_VARIANT")
        self.discord = DiscordModule()
        self._change_view(initial_view, **kwargs)
    
    def _change_view(self, view_name, **kwargs):
        # Cleanup old view
        if self.current_view:
            self.current_view.cleanup()
        
        # Create new view
        view_class = view_map[view_name]
        self.current_view = view_class(
            self.ui_manager,
            self._change_view,
            discord_module=self.discord,
            **kwargs
        )
```

Each view follows this structure:
```python
class SomeView:
    def __init__(self, ui_manager, change_view_callback, discord_module=None, **kwargs):
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self.discord = discord_module
        self._setup_ui()
    
    def _setup_ui(self):
        # Create and add UI components
        pass
    
    def update(self):
        # Update view logic
        pass
    
    def draw(self, surface):
        # Draw view-specific elements
        pass
    
    def handle_event(self, event):
        # Handle input events
        pass
    
    def cleanup(self):
        # Remove UI components
        pass
```

## Benefits
1. **Maintainability**: Each view is self-contained and easier to understand
2. **Modularity**: Views can be modified independently
3. **Testability**: Individual views can be tested in isolation
4. **Code Reusability**: Views can be reused in different contexts
5. **Clarity**: Clear separation of concerns between views
6. **Reduced Complexity**: ~90% reduction in main scene file size

## File Changes
- Created: `scenes/connect_views/__init__.py`
- Created: `scenes/connect_views/main_menu_view.py`
- Created: `scenes/connect_views/pet_selection_view.py`
- Created: `scenes/connect_views/wifi_hosting_view.py`
- Created: `scenes/connect_views/wifi_discovery_view.py`
- Created: `scenes/connect_views/dcom_view.py`
- Created: `scenes/connect_views/discord_view.py`
- Created: `scenes/connect_views/link_dialog_view.py`
- Created: `scenes/connect_views/battle_confirm_view.py`
- Renamed: `scenes/scene_connect.py` → `scenes/scene_connect_old.py` (backup)
- Created: `scenes/scene_connect.py` (new refactored version)

## Next Steps
1. Test all connection modes (WiFi, DCom, Discord) to ensure functionality
2. Verify UI transitions between views
3. Test battle confirmation and launching
4. Verify Discord linking and room management
5. Consider further refactoring if needed (e.g., extract DiscordModule to separate file)

## Notes
- The original 4521-line file is preserved as `scene_connect_old.py`
- All UI components use the RED_DARK_VARIANT theme
- View architecture matches SceneBattle for consistency
- No compile/lint errors in any of the new files

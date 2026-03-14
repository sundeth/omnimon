"""
BattleConfirmView - Pre-battle confirmation screen
Shows enemy info and allows starting or cancelling the battle
"""
from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.label import Label
from components.ui.text_panel import TextPanel
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals


class BattleConfirmView:
    """Pre-battle confirmation view."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback,
                 connection_mode="wifi", connection_socket=None, 
                 enemy_name="Unknown", enemy_device="Unknown",
                 selected_pet=None, dcom_controller=None, protocol_type=None,
                 battle_format=None, discord_module=None, discord_room=None):
        """Initialize the battle confirm view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            connection_mode: Type of connection (wifi, dcom, discord)
            connection_socket: Socket for WiFi connections
            enemy_name: Name of enemy device/user
            enemy_device: Device type of enemy
            selected_pet: Selected pet for battle
            dcom_controller: DCom controller for device battles
            protocol_type: DCom protocol type
            battle_format: Battle format (DM20, PEN20, etc.)
            discord_module: Discord module reference
            discord_room: Discord room info
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        
        self.connection_mode = connection_mode
        self.connection_socket = connection_socket
        self.enemy_name = enemy_name
        self.enemy_device = enemy_device
        self.selected_pet = selected_pet
        self.dcom_controller = dcom_controller
        self.protocol_type = protocol_type
        self.battle_format = battle_format
        self.discord = discord_module
        self.discord_room = discord_room
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.info_panel = None
        self.start_button = None
        self.cancel_button = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the UI components."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        mode_title = {
            "wifi": "WIFI BATTLE",
            "dcom": "DCOM BATTLE",
            "discord": "ONLINE BATTLE"
        }.get(self.connection_mode, "BATTLE")
        
        self.title_scene = TitleScene(0, 9, mode_title)
        self.ui_manager.add_component(self.title_scene)
        
        # Info panel with battle details
        info_lines = [
            f"Opponent: {self.enemy_name}",
            f"Device: {self.enemy_device}",
        ]
        
        if self.selected_pet:
            pet_name = self.selected_pet.get("name", "Unknown")
            info_lines.append(f"Your Pet: {pet_name}")
        
        if self.battle_format:
            info_lines.append(f"Format: {self.battle_format}")
        
        self.info_panel = TextPanel(
            20, 50,
            ui_width - 40, 100,
            info_lines
        )
        self.ui_manager.add_component(self.info_panel)
        
        # Buttons
        btn_y = 170
        btn_w = 80
        btn_h = 30
        gap = 20
        
        self.start_button = Button(
            (BASE_RESOLUTION // 2) - btn_w - (gap // 2), btn_y, btn_w, btn_h,
            "Start", self._on_start
        )
        self.ui_manager.add_component(self.start_button)
        
        self.cancel_button = Button(
            (BASE_RESOLUTION // 2) + (gap // 2), btn_y, btn_w, btn_h,
            "Cancel", self._on_cancel
        )
        self.ui_manager.add_component(self.cancel_button)
        
        runtime_globals.game_console.log(f"[BattleConfirmView] Ready - mode={self.connection_mode}")
    
    def _on_start(self):
        """Start the battle."""
        runtime_globals.game_sound.play("menu")
        runtime_globals.game_console.log("[BattleConfirmView] Starting battle...")
        
        try:
            if self.connection_mode == "wifi":
                self._start_wifi_battle()
            elif self.connection_mode == "dcom":
                self._start_dcom_battle()
            elif self.connection_mode == "discord":
                self._start_discord_battle()
        except Exception as e:
            runtime_globals.game_console.log(f"[BattleConfirmView] Error starting battle: {e}")
    
    def _start_wifi_battle(self):
        """Start a WiFi battle."""
        from scenes.scene_battle import SceneBattle
        
        if not self.connection_socket:
            runtime_globals.game_console.log("[BattleConfirmView] No connection socket!")
            return
        
        # Create battle scene with WiFi parameters
        battle_scene = SceneBattle(
            connection_type="wifi",
            connection_socket=self.connection_socket,
            selected_pet=self.selected_pet,
            enemy_name=self.enemy_name
        )
        
        runtime_globals.scene_manager.push(battle_scene)
    
    def _start_dcom_battle(self):
        """Start a DCom battle."""
        from scenes.scene_battle import SceneBattle
        
        if not self.dcom_controller:
            runtime_globals.game_console.log("[BattleConfirmView] No DCom controller!")
            return
        
        # Create battle scene with DCom parameters
        battle_scene = SceneBattle(
            connection_type="dcom",
            dcom_controller=self.dcom_controller,
            protocol_type=self.protocol_type,
            battle_format=self.battle_format,
            selected_pet=self.selected_pet,
            enemy_name=self.enemy_name
        )
        
        runtime_globals.scene_manager.push(battle_scene)
    
    def _start_discord_battle(self):
        """Start a Discord battle."""
        from scenes.scene_battle import SceneBattle
        
        if not self.discord:
            runtime_globals.game_console.log("[BattleConfirmView] No Discord module!")
            return
        
        # Create battle scene with Discord parameters
        battle_scene = SceneBattle(
            connection_type="discord",
            discord_module=self.discord,
            discord_room=self.discord_room,
            selected_pet=self.selected_pet,
            enemy_name=self.enemy_name
        )
        
        runtime_globals.scene_manager.push(battle_scene)
    
    def _on_cancel(self):
        """Cancel and return to previous view."""
        runtime_globals.game_sound.play("cancel")
        
        # Cleanup connection if needed
        if self.connection_mode == "wifi" and self.connection_socket:
            try:
                self.connection_socket.close()
            except:
                pass
        
        # Return to appropriate view
        if self.connection_mode == "discord":
            self.change_view("discord")
        elif self.connection_mode == "dcom":
            self.change_view("dcom")
        else:
            self.change_view("main_menu")
    
    def update(self):
        """Update the view."""
        pass
    
    def draw(self, surface):
        """Draw view-specific elements."""
        pass
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        if event_type == "B":
            self._on_cancel()
            return True
        elif event_type == "A":
            self._on_start()
            return True
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        components = [
            self.background, self.title_scene, self.info_panel,
            self.start_button, self.cancel_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[BattleConfirmView] Cleanup complete")

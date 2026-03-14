"""
WifiDiscoveryView - WiFi device discovery for joining local battles
(Separated from WifiHostingView for clarity - can be merged if needed)
"""
import socket
import threading

from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.label import Label
from components.ui.menu import Menu
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals


class WifiDiscoveryView:
    """WiFi discovery view for finding and joining local network battles."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback,
                 selected_pets=None, is_online_mode=False, discord_module=None):
        """Initialize the WiFi discovery view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            selected_pets: List of selected pets for battle
            is_online_mode: Whether this is online mode
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self.selected_pets = selected_pets or []
        self.is_online_mode = is_online_mode
        
        # Discovery state
        self.discovered_devices = []
        self.is_scanning = False
        
        # Network state
        self.client_socket = None
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.status_label = None
        self.device_menu = None
        self.cancel_button = None
        
        self._setup_ui()
        self._start_discovery()
    
    def _setup_ui(self):
        """Setup the UI components."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "CONNECT")
        self.ui_manager.add_component(self.title_scene)
        
        # Status label
        self.status_label = Label(10, 60, "Searching for devices...", is_title=False)
        self.ui_manager.add_component(self.status_label)
        
        # Device menu (will be populated by discovery)
        self.device_menu = Menu(width=BASE_RESOLUTION - 40, height=100)
        self.device_menu.set_position(20, 90)
        self.device_menu.visible = False
        self.ui_manager.add_component(self.device_menu)
        
        # Cancel button
        cancel_width = 100
        cancel_height = 35
        cancel_x = (BASE_RESOLUTION - cancel_width) // 2
        cancel_y = 195
        
        self.cancel_button = Button(
            cancel_x, cancel_y, cancel_width, cancel_height,
            "CANCEL", self._on_cancel
        )
        self.ui_manager.add_component(self.cancel_button)
        
        runtime_globals.game_console.log("[WifiDiscoveryView] UI setup complete")
    
    def _start_discovery(self):
        """Start device discovery in background thread."""
        self.is_scanning = True
        threading.Thread(target=self._discover_devices, daemon=True).start()
    
    def _discover_devices(self):
        """Background thread for device discovery."""
        try:
            runtime_globals.game_console.log("[WifiDiscoveryView] Starting discovery...")
            
            # UDP broadcast discovery
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.5)
            
            # Send discovery broadcast
            broadcast_msg = b"OMNIPET_DISCOVER"
            sock.sendto(broadcast_msg, ('<broadcast>', 5556))
            
            # Collect responses for a few seconds
            import time
            end_time = time.time() + 3.0
            devices = []
            
            while time.time() < end_time and self.is_scanning:
                try:
                    data, addr = sock.recvfrom(1024)
                    if data.startswith(b"OMNIPET_HOST:"):
                        host_code = data[13:].decode('utf-8')
                        devices.append({
                            'host_code': host_code,
                            'address': addr[0],
                            'port': 5555
                        })
                except socket.timeout:
                    continue
            
            sock.close()
            
            self.discovered_devices = devices
            self._discovery_complete = True
            
        except Exception as e:
            runtime_globals.game_console.log(f"[WifiDiscoveryView] Discovery error: {e}")
            self._discovery_complete = True
        finally:
            self.is_scanning = False
    
    def _connect_to_device(self, device):
        """Connect to a discovered device."""
        try:
            runtime_globals.game_console.log(f"[WifiDiscoveryView] Connecting to {device['host_code']} at {device['address']}")
            
            # Create TCP connection
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5.0)
            self.client_socket.connect((device['address'], device['port']))
            
            runtime_globals.game_console.log("[WifiDiscoveryView] Connected!")
            
            # Go to battle confirm
            self.change_view("battle_confirm",
                             connection_mode="wifi",
                             connection_socket=self.client_socket,
                             selected_pet=self.selected_pets[0] if self.selected_pets else None,
                             enemy_name=device['host_code'],
                             enemy_device="WiFi Host")
        except Exception as e:
            runtime_globals.game_console.log(f"[WifiDiscoveryView] Connection error: {e}")
            self.status_label.set_text(f"Connection failed: {str(e)[:30]}")
    
    def _on_cancel(self):
        """Cancel button clicked."""
        runtime_globals.game_sound.play("cancel")
        self.is_scanning = False
        self.change_view("main_menu")
    
    def _on_device_select(self, index):
        """Device selected from list."""
        if index < len(self.discovered_devices):
            device = self.discovered_devices[index]
            runtime_globals.game_sound.play("menu")
            self._connect_to_device(device)
        elif index == len(self.discovered_devices):  # Refresh
            runtime_globals.game_sound.play("menu")
            self.discovered_devices = []
            self.device_menu.visible = False
            self.status_label.set_text("Searching for devices...")
            self._start_discovery()
        else:
            # Last option is usually "Refresh" or "Cancel"
            self._start_discovery()
    
    def _connect_to_device(self, device):
        """Connect to a discovered device."""
        runtime_globals.game_console.log(f"[WifiDiscoveryView] Connecting to {device['address']}:{device['port']}")
        
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5.0)
            self.client_socket.connect((device['address'], device['port']))
            
            runtime_globals.game_console.log("[WifiDiscoveryView] Connected!")
            
            # Transition to battle confirm
            self.change_view("battle_confirm",
                             is_host=False,
                             selected_pets=self.selected_pets,
                             connection_socket=self.client_socket,
                             is_online_mode=self.is_online_mode)
            
        except Exception as e:
            runtime_globals.game_console.log(f"[WifiDiscoveryView] Connection failed: {e}")
            self.status_label.set_text(f"Connection failed: {e}")
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
    
    def update(self):
        """Update the view."""
        if getattr(self, '_discovery_complete', False):
            self._discovery_complete = False
            
            if self.discovered_devices:
                self.status_label.set_text(f"Found {len(self.discovered_devices)} device(s)")
                
                options = [d['host_code'] for d in self.discovered_devices]
                options.append("Refresh")
                
                self.device_menu.open(
                    options=options,
                    on_select=self._on_device_select,
                    auto_center=False
                )
                self.device_menu.set_position(20, 90)
                self.device_menu.visible = True
            else:
                self.status_label.set_text("No devices found. Try again?")
    
    def draw(self, surface):
        """Draw additional elements."""
        pass
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        if event_type == "B":
            self._on_cancel()
            return True
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        self.is_scanning = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        components = [
            self.background, self.title_scene, self.status_label,
            self.device_menu, self.cancel_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[WifiDiscoveryView] Cleanup complete")

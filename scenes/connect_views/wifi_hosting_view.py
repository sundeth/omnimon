"""
WifiHostingView - WiFi hosting and discovery for local battles
Handles both hosting and joining via local network
"""
import socket
import threading
import time

from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.label import Label
from components.ui.menu import Menu
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals


class WifiHostingView:
    """WiFi hosting view for local network battles."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback, 
                 selected_pets=None, is_online_mode=False, discord_module=None):
        """Initialize the WiFi hosting view.
        
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
        
        # State
        self.phase = "host_join_menu"  # host_join_menu, hosting, joining, device_list
        self.is_host = False
        
        # Network state
        self.host_code = ""
        self.server_socket = None
        self.client_socket = None
        self.connection_socket = None
        self.network_thread = None
        self.connection_established = False
        
        # Discovery state
        self.discovered_devices = []
        
        # Enemy data
        self.enemy_pet_count = 0
        self.enemy_modules = []
        
        # UI Components
        self.background = None
        self.title_scene = None
        
        # Host/Join menu
        self.host_join_menu = None
        
        # Hosting UI
        self.hosting_title_label = None
        self.hosting_code_label = None
        self.hosting_wait_label = None
        self.hosting_cancel_button = None
        
        # Discovery/Joining UI
        self.discovery_title_label = None
        self.discovery_status_label = None
        self.discovery_back_button = None
        
        # Device list
        self.device_list_menu = None
        
        self._setup_ui()
    
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
        
        self._setup_host_join_menu()
        self._setup_hosting_ui()
        self._setup_discovery_ui()
        
        self._show_phase("host_join_menu")
        
        runtime_globals.game_console.log("[WifiHostingView] UI setup complete")
    
    def _setup_host_join_menu(self):
        """Setup the host/join selection menu."""
        self.host_join_menu = Menu(width=BASE_RESOLUTION - 40, height=100)
        self.host_join_menu.open(
            options=["Host Battle", "Join Battle", "Back"],
            on_select=self._on_host_join_select,
            auto_center=True
        )
        self.ui_manager.add_component(self.host_join_menu)
    
    def _setup_hosting_ui(self):
        """Setup hosting phase UI."""
        self.hosting_title_label = Label(10, 60, "Hosting Network Battle", is_title=False)
        self.hosting_title_label.visible = False
        self.ui_manager.add_component(self.hosting_title_label)
        
        self.hosting_code_label = Label(10, 100, "Host Code: ----", is_title=False)
        self.hosting_code_label.visible = False
        self.ui_manager.add_component(self.hosting_code_label)
        
        self.hosting_wait_label = Label(10, 140, "Waiting for other device...", is_title=False)
        self.hosting_wait_label.visible = False
        self.ui_manager.add_component(self.hosting_wait_label)
        
        cancel_width = 100
        cancel_height = 35
        cancel_x = (BASE_RESOLUTION - cancel_width) // 2
        cancel_y = 190
        
        self.hosting_cancel_button = Button(
            cancel_x, cancel_y, cancel_width, cancel_height,
            "CANCEL", self._on_hosting_cancel
        )
        self.hosting_cancel_button.visible = False
        self.ui_manager.add_component(self.hosting_cancel_button)
    
    def _setup_discovery_ui(self):
        """Setup device discovery UI."""
        self.discovery_title_label = Label(10, 60, "Searching for devices...", is_title=False)
        self.discovery_title_label.visible = False
        self.ui_manager.add_component(self.discovery_title_label)
        
        self.discovery_status_label = Label(10, 100, "Please wait...", is_title=False)
        self.discovery_status_label.visible = False
        self.ui_manager.add_component(self.discovery_status_label)
        
        back_width = 100
        back_height = 35
        back_x = (BASE_RESOLUTION - back_width) // 2
        back_y = 190
        
        self.discovery_back_button = Button(
            back_x, back_y, back_width, back_height,
            "CANCEL", self._on_discovery_cancel
        )
        self.discovery_back_button.visible = False
        self.ui_manager.add_component(self.discovery_back_button)
    
    def _hide_all(self):
        """Hide all phase components."""
        if self.host_join_menu: self.host_join_menu.visible = False
        if self.hosting_title_label: self.hosting_title_label.visible = False
        if self.hosting_code_label: self.hosting_code_label.visible = False
        if self.hosting_wait_label: self.hosting_wait_label.visible = False
        if self.hosting_cancel_button: self.hosting_cancel_button.visible = False
        if self.discovery_title_label: self.discovery_title_label.visible = False
        if self.discovery_status_label: self.discovery_status_label.visible = False
        if self.discovery_back_button: self.discovery_back_button.visible = False
        if self.device_list_menu: self.device_list_menu.visible = False
    
    def _show_phase(self, phase):
        """Show the appropriate UI for the given phase."""
        self._hide_all()
        self.phase = phase
        
        if phase == "host_join_menu":
            self.host_join_menu.visible = True
        elif phase == "hosting":
            self.hosting_title_label.visible = True
            self.hosting_code_label.visible = True
            self.hosting_code_label.set_text(f"Host Code: {self.host_code or '----'}")
            self.hosting_wait_label.visible = True
            self.hosting_cancel_button.visible = True
        elif phase == "joining":
            self.discovery_title_label.visible = True
            self.discovery_status_label.visible = True
            self.discovery_back_button.visible = True
        elif phase == "device_list":
            if self.device_list_menu:
                self.device_list_menu.visible = True
    
    def _on_host_join_select(self, index):
        """Host/Join menu selection handler."""
        if index == 0:  # Host
            runtime_globals.game_sound.play("menu")
            self._start_hosting()
        elif index == 1:  # Join
            runtime_globals.game_sound.play("menu")
            self._start_joining()
        elif index == 2:  # Back
            runtime_globals.game_sound.play("cancel")
            self._stop_networking()
            self.change_view("main_menu")
    
    def _start_hosting(self):
        """Start hosting a network battle."""
        self.is_host = True
        self.host_code = self._generate_host_code()
        self._show_phase("hosting")
        
        # Start network thread for hosting
        self.network_thread = threading.Thread(target=self._host_network, daemon=True)
        self.network_thread.start()
    
    def _start_joining(self):
        """Start looking for hosts to join."""
        self.is_host = False
        self._show_phase("joining")
        
        # Start network thread for discovery
        self.network_thread = threading.Thread(target=self._discover_devices, daemon=True)
        self.network_thread.start()
    
    def _generate_host_code(self):
        """Generate a 4-character host code."""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    def _host_network(self):
        """Network hosting thread."""
        try:
            runtime_globals.game_console.log("[WifiHostingView] Starting host network...")
            
            # Setup TCP server for connections
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', 5555))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            
            # Setup UDP responder for discovery
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_socket.bind(('', 5556))
            udp_socket.settimeout(0.5)
            
            while self.phase == "hosting":
                # Respond to discovery broadcasts
                try:
                    data, addr = udp_socket.recvfrom(1024)
                    if data == b"OMNIPET_DISCOVER":
                        response = f"OMNIPET_HOST:{self.host_code}".encode('utf-8')
                        udp_socket.sendto(response, addr)
                        runtime_globals.game_console.log(f"[WifiHostingView] Responded to discovery from {addr}")
                except socket.timeout:
                    pass
                
                # Check for TCP connections
                try:
                    conn, addr = self.server_socket.accept()
                    runtime_globals.game_console.log(f"[WifiHostingView] Connection from {addr}")
                    self.connection_socket = conn
                    self.connection_established = True
                    udp_socket.close()
                    self.change_view("battle_confirm", 
                                     connection_mode="wifi",
                                     connection_socket=self.connection_socket,
                                     selected_pet=self.selected_pets[0] if self.selected_pets else None,
                                     enemy_name=str(addr[0]),
                                     enemy_device="WiFi Device")
                    break
                except socket.timeout:
                    continue
                except Exception as e:
                    runtime_globals.game_console.log(f"[WifiHostingView] Accept error: {e}")
                    break
        except Exception as e:
            runtime_globals.game_console.log(f"[WifiHostingView] Host network error: {e}")
        finally:
            try:
                if 'udp_socket' in locals():
                    udp_socket.close()
            except:
                pass
    
    def _discover_devices(self):
        """Device discovery thread."""
        try:
            runtime_globals.game_console.log("[WifiHostingView] Starting device discovery...")
            # Simple broadcast discovery
            # This is a simplified version - real implementation would use UDP broadcast
            
            time.sleep(2)  # Simulate discovery time
            
            # For now, just show empty list
            self._discovered_devices = []
            self._show_device_list = True
        except Exception as e:
            runtime_globals.game_console.log(f"[WifiHostingView] Discovery error: {e}")
    
    def _on_hosting_cancel(self):
        """Cancel hosting."""
        runtime_globals.game_sound.play("cancel")
        self._stop_networking()
        self._show_phase("host_join_menu")
    
    def _on_discovery_cancel(self):
        """Cancel discovery."""
        runtime_globals.game_sound.play("cancel")
        self._stop_networking()
        self._show_phase("host_join_menu")
    
    def _stop_networking(self):
        """Stop all network operations."""
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        if self.connection_socket:
            try:
                self.connection_socket.close()
            except:
                pass
            self.connection_socket = None
    
    def update(self):
        """Update the view."""
        # Check for device list update
        if getattr(self, '_show_device_list', False):
            self._show_device_list = False
            devices = getattr(self, '_discovered_devices', [])
            
            if devices:
                # Show device list menu
                device_labels = [d.get('host_code', 'Unknown') for d in devices]
                self.device_list_menu = Menu(width=BASE_RESOLUTION - 40, height=100)
                self.device_list_menu.open(
                    options=device_labels + ["Cancel"],
                    on_select=self._on_device_select,
                    auto_center=True
                )
                self.ui_manager.add_component(self.device_list_menu)
                self._show_phase("device_list")
            else:
                self.discovery_status_label.set_text("No devices found")
    
    def _on_device_select(self, index):
        """Device selection handler."""
        if index < len(self.discovered_devices):
            device = self.discovered_devices[index]
            self._connect_to_device(device)
        else:
            # Cancel
            runtime_globals.game_sound.play("cancel")
            self._show_phase("host_join_menu")
    
    def _connect_to_device(self, device):
        """Connect to a discovered device."""
        runtime_globals.game_console.log(f"[WifiHostingView] Connecting to {device}")
        # TODO: Implement connection logic
    
    def draw(self, surface):
        """Draw additional elements."""
        pass
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        if event_type == "B":
            if self.phase == "hosting":
                self._on_hosting_cancel()
            elif self.phase == "joining":
                self._on_discovery_cancel()
            elif self.phase == "host_join_menu":
                self.change_view("pet_selection", is_online_mode=self.is_online_mode)
            return True
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        self._stop_networking()
        
        components = [
            self.background, self.title_scene, self.host_join_menu,
            self.hosting_title_label, self.hosting_code_label,
            self.hosting_wait_label, self.hosting_cancel_button,
            self.discovery_title_label, self.discovery_status_label,
            self.discovery_back_button, self.device_list_menu,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[WifiHostingView] Cleanup complete")

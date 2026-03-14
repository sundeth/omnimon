"""
DComView - DCom device connection and battle
Handles DCom device discovery, protocol selection, minigames, and communication
"""
import time
import threading
import traceback

from components.ui.ui_manager import UIManager
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.background import Background
from components.ui.label import Label
from components.ui.menu import Menu
from components.ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals
from core.combat.dcom.dcom_controller import DComController
from core.combat.dcom.dcom_protocol import ProtocolType
from core.combat.sim.models import Digimon


class DComView:
    """DCom view for device battles."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback,
                 selected_pets=None, is_dcom_mode=True, discord_module=None):
        """Initialize the DCom view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
            selected_pets: List of selected pets for battle
            is_dcom_mode: Whether this is DCom mode (always True for this view)
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self.selected_pets = selected_pets or []
        
        # DCom state
        self.phase = "device_list"  # device_list, protocol_select, minigame, minigame_dmx, minigame_penz, communicating, result
        self.dcom_controller = None
        self.dcom_protocol = None
        self.dcom_battle_format = None
        self.dcom_selected_device = None
        
        # Device discovery
        self.discovered_devices = []
        
        # Minigame state
        self.dcom_minigame = None
        self.dcom_minigame_result = 0
        self.dcom_minigame_start_time = 0
        self.dcom_minigame_duration = 2500
        
        # DMX minigame state
        self.dcom_xai_phase = 0
        self.dcom_xai_roll = None
        self.dcom_xai_bar = None
        self.dcom_xai_number = 1
        
        # Communication state
        self.dcom_communicating = False
        self.dcom_comm_start_time = 0
        self.dcom_response_packets = []
        self.dcom_battle_result = None
        self.dcom_battle_sprite = None
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.status_label = None
        self.device_menu = None
        self.protocol_menu = None
        self.cancel_button = None
        
        self._setup_ui()
        
        # Pets should be selected before reaching this view
        if not self.selected_pets:
            runtime_globals.game_console.log("[DComView] ERROR: No pets selected!")
            self.change_view("main_menu", initial_submenu="local_battle")
            return
        
        # Start device scan
        self._start_dcom_scan()
    
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
        
        # Status label with word wrapping
        self.status_label = Label(10, 60, "Scanning for DCom...", is_title=False, word_wrap=True, max_width=220)
        self.ui_manager.add_component(self.status_label)
        
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
        
        runtime_globals.game_console.log("[DComView] UI setup complete")
    
    def _start_dcom_scan(self):
        """Scan for DCom devices."""
        runtime_globals.game_console.log("[DComView] Starting DCom device scan...")
        
        try:
            import serial.tools.list_ports
        except ImportError:
            runtime_globals.game_console.log("[DComView] pyserial not installed")
            self.status_label.set_text("ERROR: pyserial not installed!")
            return
        
        try:
            if not self.dcom_controller:
                self.dcom_controller = DComController()
                self.dcom_protocol = ProtocolType.V_PET
            
            # List all ports
            all_ports = DComController.list_all_ports()
            runtime_globals.game_console.log(f"[DComView] Found {len(all_ports)} serial ports")
            
            # Find DCom devices
            self.discovered_devices = self.dcom_controller.find_dcom_devices()
            
            if not self.discovered_devices:
                if all_ports:
                    self.status_label.set_text(f"No DCom found ({len(all_ports)} ports)")
                else:
                    self.status_label.set_text("No serial ports found!")
                return
            
            runtime_globals.game_console.log(f"[DComView] Found {len(self.discovered_devices)} DCom device(s)")
            self.status_label.set_text(f"Found {len(self.discovered_devices)} device(s)")
            
            # Auto-select if only one device
            if len(self.discovered_devices) == 1:
                self._on_device_select(0)
                return
            
            # Show device selection menu
            device_options = [desc for port, desc in self.discovered_devices]
            self.device_menu = Menu(width=180, height=140)
            self.device_menu.open(device_options, self._on_device_select)
            self.ui_manager.add_component(self.device_menu)
            self.ui_manager.set_active_menu(self.device_menu)
            
        except Exception as e:
            runtime_globals.game_console.log(f"[DComView] Scan error: {e}")
            self.status_label.set_text(f"Scan error: {str(e)}")
    
    def _on_device_select(self, index):
        """Device selected from menu."""
        if index >= len(self.discovered_devices):
            return
        
        port, desc = self.discovered_devices[index]
        runtime_globals.game_console.log(f"[DComView] Selected: {desc} on {port}")
        self.dcom_selected_device = (port, desc)
        
        # Close menu
        if self.device_menu:
            self.device_menu.close()
            if self.ui_manager.active_menu == self.device_menu:
                self.ui_manager.active_menu = None
        
        # Connect to device
        try:
            if not self.dcom_controller:
                self.dcom_controller = DComController()
            
            if not self.dcom_controller.connect(port):
                raise Exception("Failed to connect")
            
            runtime_globals.game_console.log("[DComView] Connected!")
            self._show_protocol_selection()
            
        except Exception as e:
            runtime_globals.game_console.log(f"[DComView] Connection error: {e}")
            self.status_label.set_text(f"Error: {str(e)}")
            if self.dcom_controller:
                self.dcom_controller.disconnect()
    
    def _show_protocol_selection(self):
        """Show protocol selection menu."""
        runtime_globals.game_console.log("[DComView] Showing protocol selection...")
        self.phase = "protocol_select"
        
        protocol_options = [
            "DM (Original)",
            "DM20 (20th Anniversary)",
            "PEN20 (Pendulum 20th)",
            "DMX (Digimon X)",
            "PenZ (Pendulum Z)",
            "DMC (Color)",
            "Cancel"
        ]
        
        self.protocol_menu = Menu(width=200, height=140)
        self.protocol_menu.open(protocol_options, self._on_protocol_select)
        self.ui_manager.add_component(self.protocol_menu)
        self.ui_manager.set_active_menu(self.protocol_menu)
    
    def _on_protocol_select(self, index):
        """Protocol selected from menu."""
        if self.protocol_menu:
            self.protocol_menu.close()
            if self.ui_manager.active_menu == self.protocol_menu:
                self.ui_manager.active_menu = None
        
        if index == 0:  # DM (Original)
            self.dcom_protocol = ProtocolType.V_PET
            self.dcom_battle_format = 'DM'
            self._start_communication_no_minigame()  # DM doesn't use minigame
        elif index == 1:  # DM20
            self.dcom_protocol = ProtocolType.V_PET
            self.dcom_battle_format = 'DM20'
            self._start_minigame()  # Dummy Charge
        elif index == 2:  # PEN20
            self.dcom_protocol = ProtocolType.PEN_X
            self.dcom_battle_format = 'PEN20'
            self._start_minigame_pen20()  # Count Match Classic
        elif index == 3:  # DMX
            self.dcom_protocol = ProtocolType.COLOR
            self.dcom_battle_format = 'DMX'
            self._start_minigame_dmx()  # Xai Roll + Xai Bar
        elif index == 4:  # PenZ
            self.dcom_protocol = ProtocolType.V_PET
            self.dcom_battle_format = 'PENZ'
            self._start_minigame_penz()  # Count Match Z
        elif index == 5:  # DMC
            self.dcom_protocol = ProtocolType.COLOR
            self.dcom_battle_format = 'DMC'
            self._start_communication_no_minigame()  # DMC doesn't use minigame
        else:  # Cancel
            self._on_cancel()
    
    def _start_minigame(self):
        """Start the DM20 minigame (Dummy Charge)."""
        from components.minigames.dummy_charge import DummyCharge
        import pygame
        
        runtime_globals.game_console.log("[DComView] Starting Dummy minigame...")
        self.phase = "minigame"
        self.dcom_minigame = DummyCharge(self.ui_manager, theme="RED_DARK_VARIANT")
        self.dcom_minigame_start_time = pygame.time.get_ticks()
        self.dcom_minigame_duration = 2500
        
        # Hide cancel button during minigame
        self.cancel_button.visible = False

    def _start_minigame_pen20(self):
        """Start the PEN20 minigame (Count Match Classic)."""
        from components.minigames.count_match_classic import CountMatchClassic
        import pygame
        
        runtime_globals.game_console.log("[DComView] Starting PEN20 Count Match Classic minigame...")
        self.phase = "minigame_pen20"
        self.dcom_minigame = CountMatchClassic(self.ui_manager, theme="RED_DARK_VARIANT")
        self.dcom_minigame_start_time = pygame.time.get_ticks()
        self.dcom_minigame_duration = 2500  # Same duration as Dummy Charge
        
        # Hide cancel button during minigame
        self.cancel_button.visible = False
    
    def _start_minigame_dmx(self):
        """Start the DMX minigame (XAI Roll + Bar)."""
        from components.minigames.xai_roll import XaiRoll
        
        runtime_globals.game_console.log("[DComView] Starting DMX XAI minigame...")
        self.phase = "minigame_dmx"
        self.dcom_xai_phase = 1
        self.dcom_xai_number = 1
        self.dcom_minigame_result = 1
        
        self.dcom_xai_roll = XaiRoll(
            x=runtime_globals.SCREEN_WIDTH // 2 - int(100 * runtime_globals.UI_SCALE) // 2,
            y=runtime_globals.SCREEN_HEIGHT // 2 - int(100 * runtime_globals.UI_SCALE) // 2,
            width=int(100 * runtime_globals.UI_SCALE),
            height=int(100 * runtime_globals.UI_SCALE),
            xai_number=1
        )
        self.dcom_xai_roll.roll()
        
        # Hide cancel button during minigame
        self.cancel_button.visible = False
    
    def _start_minigame_penz(self):
        """Start the PENZ minigame (Count Match Z)."""
        from components.minigames.count_match_z import CountMatchZ
        from components.ui.animated_sprite import AnimatedSprite
        import pygame
        
        runtime_globals.game_console.log("[DComView] Starting PENZ Count Match Z minigame...")
        self.phase = "minigame_penz"
        
        # CountMatchZ needs an animated sprite for ready/count display
        animated_sprite = AnimatedSprite(self.ui_manager)
        pet = self.selected_pets[0] if self.selected_pets else None
        self.dcom_minigame = CountMatchZ(self.ui_manager, pet, animated_sprite)
        self.dcom_minigame_start_time = pygame.time.get_ticks()
        self.dcom_minigame_duration = 3000  # 3 seconds for count match
        
        # Hide cancel button during minigame
        self.cancel_button.visible = False
    
    def _start_communication(self):
        """Start DCom communication phase - V2 listen-and-reply mode."""
        from components.ui.animated_sprite import AnimatedSprite
        import os
        
        runtime_globals.game_console.log("[DComView] ===== STARTING DCOM COMMUNICATION PHASE =====")
        self.phase = "communicating"
        self.dcom_communicating = True
        self.dcom_comm_start_time = time.time()
        self.dcom_comm_timeout = 60.0  # 60 second timeout for V2 mode
        self.dcom_response_packets = []
        self.dcom_status_count = 0
        self.dcom_last_status_time = time.time()
        self._last_comm_log_time = time.time()
        
        self.status_label.set_text("Waiting for device...")
        self.cancel_button.visible = True
        
        # Generate battle packets with minigame result
        pet = self.selected_pets[0] if self.selected_pets else None
        if not pet:
            runtime_globals.game_console.log("[DComView] ERROR: No pet selected!")
            self.status_label.set_text("Error: No pet selected")
            return
        
        digimon = self._convert_pet_to_digimon(pet)
        digimon.mini_game = self.dcom_minigame_result
        
        # Generate packets based on format
        if self.dcom_battle_format == 'DMX':
            from core.combat.sim.battle_simulator import DMXDevice
            device = DMXDevice(digimon)
            packets = [
                device.generate_packet1(),
                device.generate_packet2(),
                device.generate_packet3(),
                device.generate_packet4(),
                device.generate_packet5(),
            ]
            # Generate packet 6 with optimistic hits pattern
            device.hits = 0x1F  # All 5 rounds hit
            cou3 = 0
            eol = 0xE
            hits = 0x1F
            checksum = 0
            for pkt in packets:
                for byte in pkt:
                    checksum += (byte >> 4) & 0x0F
                    checksum += byte & 0x0F
            byte1_without_check = (cou3 << 1) | (hits >> 4)
            byte2 = ((hits & 0x0F) << 4) | eol
            checksum += byte1_without_check & 0x0F
            checksum += (byte2 >> 4) & 0x0F
            checksum += byte2 & 0x0F
            check = (8 - (checksum % 16)) % 16
            byte1 = (check << 4) | byte1_without_check
            import struct
            packets.append(struct.pack(">BB", byte1, byte2))
            self.dcom_player_packets = packets
        elif self.dcom_battle_format == 'PENZ':
            # PENZ uses same packet format as DMX (6 packets), only minigame differs
            from core.combat.sim.battle_simulator import DMXDevice
            device = DMXDevice(digimon)
            packets = [
                device.generate_packet1(),
                device.generate_packet2(),
                device.generate_packet3(),
                device.generate_packet4(),
                device.generate_packet5(),
            ]
            # Generate packet 6 with optimistic hits pattern
            device.hits = 0x1F  # All 5 rounds hit
            cou3 = 0
            eol = 0xE
            hits = 0x1F
            checksum = 0
            for pkt in packets:
                for byte in pkt:
                    checksum += (byte >> 4) & 0x0F
                    checksum += byte & 0x0F
            byte1_without_check = (cou3 << 1) | (hits >> 4)
            byte2 = ((hits & 0x0F) << 4) | eol
            checksum += byte1_without_check & 0x0F
            checksum += (byte2 >> 4) & 0x0F
            checksum += byte2 & 0x0F
            check = (8 - (checksum % 16)) % 16
            byte1 = (check << 4) | byte1_without_check
            import struct
            packets.append(struct.pack(">BB", byte1, byte2))
            self.dcom_player_packets = packets
        else:
            # DM20 or PEN20 - use DM20Device (10 packets)
            from core.combat.sim.battle_simulator import DM20Device
            device = DM20Device(digimon)
            self.dcom_player_packets = device.generate_all_packets_for_dcom(order=0)
        
        runtime_globals.game_console.log(f"[DComView] Generated {len(self.dcom_player_packets)} packets with minigame result: {self.dcom_minigame_result}")
        
        # Load battle animation sprite
        battle_sprite_path = "assets/ui/animations/play_battle.png"
        if os.path.exists(battle_sprite_path):
            runtime_globals.game_console.log("[DComView] Loading battle animation sprite...")
            try:
                self.dcom_battle_sprite = AnimatedSprite(
                    battle_sprite_path,
                    frame_width=240,
                    frame_height=240,
                    frame_count=13,
                    fps=10,
                    loop=True
                )
                self.dcom_battle_sprite.play()
                runtime_globals.game_console.log("[DComView] Battle animation loaded successfully")
            except Exception as e:
                runtime_globals.game_console.log(f"[DComView] Warning: Failed to load battle sprite: {e}")
                self.dcom_battle_sprite = None
        else:
            runtime_globals.game_console.log(f"[DComView] Warning: Battle sprite not found at {battle_sprite_path}")
            self.dcom_battle_sprite = None
        
        # Send V2 command (listen-and-reply mode)
        self._send_dcom_packets()
        runtime_globals.game_console.log("[DComView] Communication phase started - 60 second window active")
        runtime_globals.game_console.log("[DComView] IMPORTANT: Start the battle on your DM20 device NOW!")
    
    def _start_communication_no_minigame(self):
        """Start DCom communication for protocols without minigame (DM/DMC) - direct to communication."""
        from components.ui.animated_sprite import AnimatedSprite
        import os
        
        format_name = self.dcom_battle_format or "DM"
        runtime_globals.game_console.log(f"[DComView] ===== STARTING {format_name} COMMUNICATION PHASE (NO MINIGAME) =====")
        self.phase = "communicating"
        self.dcom_communicating = True
        self.dcom_comm_start_time = time.time()
        self.dcom_comm_timeout = 60.0
        self.dcom_response_packets = []
        self.dcom_status_count = 0
        self.dcom_last_status_time = time.time()
        self._last_comm_log_time = time.time()
        
        self.status_label.set_text("Waiting for device...")
        self.cancel_button.visible = True
        
        # Generate battle packets - DM and DMC protocols don't use minigame
        pet = self.selected_pets[0] if self.selected_pets else None
        if not pet:
            runtime_globals.game_console.log("[DComView] ERROR: No pet selected!")
            self.status_label.set_text("Error: No pet selected")
            return
        
        digimon = self._convert_pet_to_digimon(pet)
        digimon.mini_game = 0  # No minigame, boost comes from pills (default 0)
        
        # Generate packets based on format
        if self.dcom_battle_format == 'DM':
            # DM original uses 2 packets
            from core.combat.sim.battle_simulator import DMDevice
            device = DMDevice(digimon)
            self.dcom_player_packets = device.generate_all_packets()
        elif self.dcom_battle_format == 'DMC':
            # DMC uses DMXDevice format (6 packets) with COLOR protocol
            from core.combat.sim.battle_simulator import DMXDevice
            device = DMXDevice(digimon)
            packets = [
                device.generate_packet1(),
                device.generate_packet2(),
                device.generate_packet3(),
                device.generate_packet4(),
                device.generate_packet5(),
            ]
            # Generate packet 6 with optimistic hits pattern
            device.hits = 0x1F  # All 5 rounds hit
            cou3 = 0
            eol = 0xE
            hits = 0x1F
            checksum = 0
            for pkt in packets:
                for byte in pkt:
                    checksum += (byte >> 4) & 0x0F
                    checksum += byte & 0x0F
            byte1_without_check = (cou3 << 1) | (hits >> 4)
            byte2 = ((hits & 0x0F) << 4) | eol
            checksum += byte1_without_check & 0x0F
            checksum += (byte2 >> 4) & 0x0F
            checksum += byte2 & 0x0F
            check = (8 - (checksum % 16)) % 16
            byte1 = (check << 4) | byte1_without_check
            import struct
            packets.append(struct.pack(">BB", byte1, byte2))
            self.dcom_player_packets = packets
        
        runtime_globals.game_console.log(f"[DComView] Generated {len(self.dcom_player_packets)} {format_name} packets (no minigame)")
        
        # Load battle animation sprite
        battle_sprite_path = "assets/ui/animations/play_battle.png"
        if os.path.exists(battle_sprite_path):
            runtime_globals.game_console.log("[DComView] Loading battle animation sprite...")
            try:
                self.dcom_battle_sprite = AnimatedSprite(
                    battle_sprite_path,
                    frame_width=240,
                    frame_height=240,
                    frame_count=13,
                    fps=10,
                    loop=True
                )
                self.dcom_battle_sprite.play()
            except Exception as e:
                runtime_globals.game_console.log(f"[DComView] Warning: Failed to load battle sprite: {e}")
                self.dcom_battle_sprite = None
        else:
            self.dcom_battle_sprite = None
        
        # Send V2 command (listen-and-reply mode)
        self._send_dcom_packets()
        runtime_globals.game_console.log(f"[DComView] {format_name} communication started - waiting for device")
    
    def _send_dcom_packets(self):
        """Send V2 command with player packets to DCom device (listen-and-reply mode)."""
        runtime_globals.game_console.log("[DComView] ===== SENDING PACKETS TO DCOM =====")
        runtime_globals.game_console.log(f"[DComView] Sending {len(self.dcom_player_packets)} packets:")
        for i, packet in enumerate(self.dcom_player_packets, 1):
            hex_str = " ".join(f"{b:02X}" for b in packet)
            runtime_globals.game_console.log(f"[DComView]   Packet {i}: {hex_str}")
        try:
            hex_packets = [pkt.hex().upper() for pkt in self.dcom_player_packets]
            command = f"V2-" + "-".join(hex_packets)
            
            runtime_globals.game_console.log(f"[DComView] Sending V2 command (listen-and-reply): {command[:80]}...")
            runtime_globals.game_console.log("[DComView] DCom will wait for DM20 to send first, then reply with our packets")
            self.dcom_controller._send_raw(command + '\r')
            self.dcom_last_send_time = time.time()
            runtime_globals.game_console.log("[DComView] V2 command sent - DCom is now listening for DM20...")
        except Exception as e:
            runtime_globals.game_console.log(f"[DComView] Error sending packets: {e}")
            import traceback
            runtime_globals.game_console.log(f"Traceback:\n{traceback.format_exc()}")
            self.status_label.set_text(f"Error: {str(e)}")
    
    def _check_dcom_response(self):
        """Check for packets from DCom device (V2 listen-and-reply mode)."""
        import re
        try:
            if not hasattr(self, 'dcom_response_packets'):
                self.dcom_response_packets = []

            # Ensure controller and port are valid
            if not self.dcom_controller or not getattr(self.dcom_controller, 'serial_port', None):
                return False

            waiting = self.dcom_controller.serial_port.in_waiting
            if waiting > 0:
                runtime_globals.game_console.log(f"[DComView] Data available: {waiting} bytes")
                line = self.dcom_controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    return False

                # Handle status messages (t: prefix)
                if line.startswith('t:'):
                    self.dcom_status_count += 1
                    if time.time() - self.dcom_last_status_time > 2.0:
                        runtime_globals.game_console.log(
                            f"[DComView] DCom status: {line} (status updates: {self.dcom_status_count})"
                        )
                        self.dcom_last_status_time = time.time()
                else:
                    runtime_globals.game_console.log(f"[DComView] Received: {line}")

                # Look for both r:[4 hex] (received from DM20) and s:[4 hex] (sent to DM20)
                r_matches = re.findall(r'r:[0-9A-Fa-f]{4}', line)
                s_matches = re.findall(r's:[0-9A-Fa-f]{4}', line)

                if s_matches:
                    for match in s_matches:
                        hex_data = match[2:]
                        runtime_globals.game_console.log(f"[DComView] Our packet echoed: {hex_data}")

                if r_matches:
                    for match in r_matches:
                        hex_data = match[2:]
                        # Filter out FF00 error/terminator packets
                        if hex_data.upper() == 'FF00':
                            runtime_globals.game_console.log(f"[DComView] FF00 terminator (ignored)")
                            continue
                        self.dcom_response_packets.append(hex_data)
                        expected_packets = self._get_expected_packet_count()
                        format_name = self.dcom_battle_format or 'DM20'
                        runtime_globals.game_console.log(
                            f"[DComView] {format_name} packet {len(self.dcom_response_packets)}/{expected_packets}: {hex_data}"
                        )
                        if len(self.dcom_response_packets) >= expected_packets:
                            break

                    # Check if all packets received
                    expected_packets = self._get_expected_packet_count()
                    if len(self.dcom_response_packets) >= expected_packets:
                        runtime_globals.game_console.log(f"[DComView] ===== ALL {expected_packets} PACKETS RECEIVED =====")
                        runtime_globals.game_console.log(f"[DComView] Received packets: {' '.join(self.dcom_response_packets)}")
                        return True

            return False
        except Exception as e:
            runtime_globals.game_console.log(f"[DComView] Error checking response: {e}")
            return False
    
    def _update_dcom_communication(self):
        """Update loop for DCom communication phase."""
        current_time = time.time()
        elapsed = current_time - self.dcom_comm_start_time
        
        # Log every 5 seconds to show we're actively checking
        if current_time - self._last_comm_log_time >= 5.0:
            runtime_globals.game_console.log(f"[DComView] Still communicating... elapsed: {elapsed:.1f}s, packets: {len(getattr(self, 'dcom_response_packets', []))}")
            self._last_comm_log_time = current_time
        
        # Check for timeout
        if elapsed >= self.dcom_comm_timeout:
            runtime_globals.game_console.log("[DComView] ===== DCOM COMMUNICATION TIMEOUT =====")
            runtime_globals.game_console.log(f"[DComView] Received {len(getattr(self, 'dcom_response_packets', []))} packets before timeout")
            self.status_label.set_text("Timeout! No response from device.")
            self.dcom_communicating = False
            if self.dcom_controller:
                self.dcom_controller.disconnect()
            return
        
        # Update status label with remaining time
        remaining = int(self.dcom_comm_timeout - elapsed)
        self.status_label.set_text(f"Waiting... ({remaining}s)")
        
        # Check for device response
        if self._check_dcom_response():
            runtime_globals.game_console.log("[DComView] All packets received! Processing battle result...")
            self.dcom_communicating = False
            self._process_battle_result()
    
    def _get_expected_packet_count(self) -> int:
        """Get the expected number of packets based on battle format."""
        if self.dcom_battle_format == 'DM':
            return 2  # DM original uses only 2 packets
        elif self.dcom_battle_format in ['DMX', 'PENZ']:
            return 6  # DMX and PENZ use 6 packets
        elif self.dcom_battle_format == 'DMC':
            return 6  # DMC uses 6 packets (Color protocol)
        else:
            return 10  # DM20 and PEN20 use 10 packets
    
    def _convert_pet_to_digimon(self, pet):
        """Convert GamePet to Digimon model."""
        attr_map = {"Va": 0, "Vaccine": 0, "Da": 1, "Data": 1, "Vi": 2, "Virus": 2, "Fr": 3, "Free": 3}
        pet_attr = getattr(pet, 'attribute', 'Va')
        attribute = attr_map.get(pet_attr, 0)
        
        return Digimon(
            name=getattr(pet, 'name', 'Unknown'),
            order=0,
            traited=getattr(pet, 'traited', 0),
            egg_shake=getattr(pet, 'shook', 0),
            index=0,
            hp=getattr(pet, 'hp', 4),
            attribute=attribute,
            power=getattr(pet, 'power', 50),
            handicap=0,
            buff=0,
            mini_game=0,
            level=getattr(pet, 'level', 1),
            stage=getattr(pet, 'stage', 3),
            sick=getattr(pet, 'sick', 0),
            shot1=3,
            shot2=3,
            tag_meter=0
        )
    
    def _process_battle_result(self):
        """Process battle result from response packets and transition to PvP scene."""
        runtime_globals.game_console.log("[DComView] ===== PROCESSING DCOM BATTLE RESULT =====")
        
        try:
            if not self.selected_pets:
                raise Exception("No selected pets found")
            
            pet = self.selected_pets[0]
            runtime_globals.game_console.log(f"[DComView] Processing result for pet: {getattr(pet, 'name', 'Unknown')}")
            player_digimon = self._convert_pet_to_digimon(pet)
            
            # Parse opponent using DComBattleSimulator
            from core.combat.sim.dcom_battle_simulator import DComBattleSimulator
            simulator = DComBattleSimulator(self.dcom_controller, self.dcom_protocol, self.dcom_battle_format)
            runtime_globals.game_console.log(f"[DComView] Parsing {len(self.dcom_response_packets)} packets")
            opponent_digimon = simulator._parse_opponent_packets(self.dcom_response_packets, player_digimon)
            
            if not opponent_digimon:
                error_msg = "Received corrupt data from device"
                runtime_globals.game_console.log(f"[DComView] {error_msg}")
                self.status_label.set_text(f"ERROR: {error_msg}")
                if self.dcom_controller:
                    self.dcom_controller.disconnect()
                return
            
            runtime_globals.game_console.log(f"[DComView] Opponent: {opponent_digimon.name}, HP={opponent_digimon.hp}, Power={opponent_digimon.power}")
            
            # Build battle result
            result = simulator._build_battle_result(
                player_digimon, opponent_digimon,
                self.dcom_player_packets, self.dcom_response_packets
            )
            
            if not result:
                raise Exception("Battle result is None")
            
            runtime_globals.game_console.log(f"[DComView] Battle result: Winner={result.winner}")
            runtime_globals.game_console.log(f"[DComView] Battle log has {len(result.battle_log)} turns")
            
            # Print battle log and DCom code
            simulator.internal_simulator.print_battle_log(result)
            simulator._print_dcom_code(result)
            
            # Create PvP battle data
            self._create_dcom_pvp_data(pet, opponent_digimon, result)
            
            # Disconnect device
            self.dcom_controller.disconnect()
            
            # Transition to battle scene
            runtime_globals.game_console.log("[DComView] Transitioning to PvP battle scene...")
            from core.utils.scene_utils import change_scene
            change_scene("battle_pvp")
            
        except Exception as e:
            import traceback
            error_msg = f"[DComView] Error processing battle result: {e}"
            traceback_msg = f"[DComView] Traceback: {traceback.format_exc()}"
            runtime_globals.game_console.log(error_msg)
            runtime_globals.game_console.log(traceback_msg)
            print(error_msg)
            print(traceback_msg)
            self.status_label.set_text(f"Error: {str(e)[:50]}")
            if self.dcom_controller:
                self.dcom_controller.disconnect()
    
    def _create_dcom_pvp_data(self, my_pet, opponent_digimon, battle_result):
        """Create PvP battle data from DCom battle result."""
        from core import runtime_globals
        runtime_globals.game_console.log("[DComView] Creating PvP battle data...")
        
        # My pet data
        my_pet_data = {
            "name": getattr(my_pet, "name", "Pet"),
            "stage": getattr(my_pet, "stage", 1),
            "level": getattr(my_pet, "level", 1),
            "hp": my_pet.get_hp() if hasattr(my_pet, "get_hp") else getattr(my_pet, "hp", 100),
            "power": my_pet.get_power() if hasattr(my_pet, "get_power") else getattr(my_pet, "power", 1),
            "attribute": getattr(my_pet, "attribute", 0),
            "atk_main": getattr(my_pet, "atk_main", None),
            "atk_alt": getattr(my_pet, "atk_alt", None),
            "module": getattr(my_pet, "module", "base"),
            "sick": getattr(my_pet, "sick", 0) > 0,
            "traited": getattr(my_pet, "traited", False),
            "shook": getattr(my_pet, "shook", False),
            "mini_game": getattr(my_pet, "strength", 0)
        }
        
        # Get initial HP for opponent based on protocol
        from core.combat.sim.dcom_battle_simulator import DComBattleSimulator
        simulator = DComBattleSimulator(self.dcom_controller, self.dcom_protocol, self.dcom_battle_format)
        initial_hp = simulator.get_initial_hp(opponent_digimon)
        
        # Opponent pet data
        opponent_pet_data = {
            "name": opponent_digimon.name,
            "stage": 3,
            "level": 1,
            "hp": initial_hp,
            "power": opponent_digimon.power,
            "attribute": opponent_digimon.attribute,
            "atk_main": 30,
            "atk_alt": 30,
            "module": getattr(my_pet, "module", "base"),
            "sick": False,
            "traited": False,
            "shook": False,
            "mini_game": opponent_digimon.mini_game
        }
        
        # Serialize battle result
        battle_log_serialized = battle_result.to_dict() if hasattr(battle_result, 'to_dict') else {}
        
        battle_simulation_data = {
            "battle_log": battle_log_serialized,
            "team1": [my_pet_data],
            "team2": [opponent_pet_data],
            "module": getattr(my_pet, "module", "base"),
            "victory_status": "Defeat" if battle_result.winner == "device1" else "Victory"
        }
        
        runtime_globals.pvp_battle_data = {
            "simulation_data": battle_simulation_data,
            "original_battle_log": battle_result,
            "is_host": True,
            "my_pets": [my_pet],
            "my_team_data": [my_pet_data],
            "enemy_team_data": [opponent_pet_data],
            "module": getattr(my_pet, "module", "base"),
            "my_player_name": "YOU",
            "enemy_player_name": "DM20 DEVICE",
            "is_online_mode": False,
            "is_dcom_mode": True,
            "enemy_first": True
        }
        
        runtime_globals.game_console.log("[DComView] PvP battle data created")
    
    def _on_cancel(self):
        """Cancel button clicked."""
        runtime_globals.game_sound.play("cancel")
        self._cleanup_dcom()
        self.change_view("main_menu")
    
    def _cleanup_dcom(self):
        """Cleanup DCom resources."""
        self.dcom_communicating = False
        if self.dcom_controller:
            try:
                self.dcom_controller.disconnect()
            except:
                pass
            self.dcom_controller = None
    
    def update(self):
        """Update the view."""
        import pygame
        
        # Check for minigame completion delay (prevent button spam)
        if hasattr(self, 'waiting_after_minigame') and self.waiting_after_minigame:
            if time.time() - self.minigame_complete_time >= 0.5:  # 500ms delay
                self.waiting_after_minigame = False
                self._start_communication()
            return
        
        # Minigame updates (DM20 - Dummy Charge)
        if self.phase == "minigame" and self.dcom_minigame:
            self.dcom_minigame.update()
            
            elapsed = pygame.time.get_ticks() - self.dcom_minigame_start_time
            if elapsed >= self.dcom_minigame_duration:
                self.dcom_minigame_result = self.dcom_minigame.strength
                runtime_globals.game_console.log(f"[DComView] Minigame complete: {self.dcom_minigame_result}")
                self.dcom_minigame = None
                # Add delay to prevent button spam from clicking next view's components
                self.minigame_complete_time = time.time()
                self.waiting_after_minigame = True

        # PEN20 minigame updates (Count Match Classic)
        if self.phase == "minigame_pen20" and self.dcom_minigame:
            self.dcom_minigame.update()
            
            elapsed = pygame.time.get_ticks() - self.dcom_minigame_start_time
            if elapsed >= self.dcom_minigame_duration:
                self.dcom_minigame_result = self.dcom_minigame.strength
                runtime_globals.game_console.log(f"[DComView] PEN20 Count Match Classic complete: {self.dcom_minigame_result}")
                self.dcom_minigame = None
                # Add delay to prevent button spam from clicking next view's components
                self.minigame_complete_time = time.time()
                self.waiting_after_minigame = True
        
        # DMX minigame updates
        if self.phase == "minigame_dmx":
            if self.dcom_xai_phase == 1 and self.dcom_xai_roll:
                self.dcom_xai_roll.update()
                if not self.dcom_xai_roll.rolling and not self.dcom_xai_roll.stopping:
                    # Transition to bar phase
                    self.dcom_xai_phase = 2
                    from components.minigames.xai_bar import XaiBar
                    pet = self.selected_pets[0] if self.selected_pets else None
                    self.dcom_xai_bar = XaiBar(
                        x=runtime_globals.SCREEN_WIDTH // 2 - int(152 * runtime_globals.UI_SCALE) // 2,
                        y=runtime_globals.SCREEN_HEIGHT // 2 + int(48 * runtime_globals.UI_SCALE),
                        xai_number=self.dcom_xai_number,
                        pet=pet
                    )
                    self.dcom_xai_bar.start()
            elif self.dcom_xai_phase == 2 and self.dcom_xai_bar:
                self.dcom_xai_bar.update()
            elif self.dcom_xai_phase == 3:
                runtime_globals.game_console.log(f"[DComView] DMX minigame complete: {self.dcom_minigame_result}")
                # Add delay to prevent button spam from clicking next view's components
                self.minigame_complete_time = time.time()
                self.waiting_after_minigame = True
                self.dcom_xai_phase = 0  # Reset phase
        
        # PENZ minigame updates (Count Match Z)
        if self.phase == "minigame_penz" and self.dcom_minigame:
            self.dcom_minigame.update()
            
            elapsed = pygame.time.get_ticks() - self.dcom_minigame_start_time
            if elapsed >= self.dcom_minigame_duration:
                # Get count match Z result (0-3 based on accuracy and attribute)
                self.dcom_minigame_result = self.dcom_minigame.calculate_result()
                runtime_globals.game_console.log(f"[DComView] PENZ Count Match Z complete: {self.dcom_minigame_result}")
                self.dcom_minigame = None
                # Add delay to prevent button spam from clicking next view's components
                self.minigame_complete_time = time.time()
                self.waiting_after_minigame = True
        
        # Battle sprite animation and communication updates
        if self.phase == "communicating":
            if self.dcom_battle_sprite:
                self.dcom_battle_sprite.update()
            if self.dcom_communicating:
                self._update_dcom_communication()
    
    def draw(self, surface):
        """Draw view-specific elements."""
        # Minigame draws (background already drawn by UI manager)
        if self.phase == "minigame" and self.dcom_minigame:
            self.dcom_minigame.draw(surface)

        # PEN20 minigame draws (Count Match Classic)
        if self.phase == "minigame_pen20" and self.dcom_minigame:
            self.dcom_minigame.draw(surface)
        
        # DMX minigame draws (background already drawn by UI manager)
        if self.phase == "minigame_dmx":
            if self.dcom_xai_phase == 1 and self.dcom_xai_roll:
                self.dcom_xai_roll.draw(surface)
            elif self.dcom_xai_phase == 2 and self.dcom_xai_bar:
                self.dcom_xai_bar.draw(surface)
        
        # PENZ minigame draws (Count Match Z)
        if self.phase == "minigame_penz" and self.dcom_minigame:
            self.dcom_minigame.draw(surface)
        
        # Battle sprite during communication
        if self.phase == "communicating" and self.dcom_battle_sprite:
            self.dcom_battle_sprite.draw(surface, 0, 0)
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        
        event_type, event_data = event
        
        runtime_globals.game_console.log(f"[DComView] handle_event: type={event_type}, data={event_data}, phase={self.phase}")
        
        # Handle minigame input (DM20 - Dummy Charge)
        if self.phase == "minigame" and self.dcom_minigame:
            if event_type in ["A", "LCLICK"]:
                # Let minigame handle the event
                runtime_globals.game_console.log(f"[DComView] Passing {event_type} to minigame.handle_event")
                handled = self.dcom_minigame.handle_event(event)
                if handled:
                    runtime_globals.game_console.log(f"[DComView] Minigame handled {event_type}, strength now: {self.dcom_minigame.strength}")
                return
            elif event_type in ["B", "X"]:
                # Finish minigame and continue
                self.dcom_minigame_result = self.dcom_minigame.strength
                runtime_globals.game_console.log(f"[DComView] Minigame completed! Result: {self.dcom_minigame_result}")
                runtime_globals.game_sound.play("menu")
                self.dcom_minigame = None
                # Add delay to prevent button spam from clicking next view's components
                self.minigame_complete_time = time.time()
                self.waiting_after_minigame = True
                return

        # Handle PEN20 minigame input (Count Match Classic - uses SHAKE/Y)
        if self.phase == "minigame_pen20" and self.dcom_minigame:
            if event_type in ["Y", "SHAKE"]:
                # Let minigame handle the event
                runtime_globals.game_console.log(f"[DComView] Passing {event_type} to PEN20 Count Match Classic")
                handled = self.dcom_minigame.handle_event(event)
                if handled:
                    runtime_globals.game_console.log(f"[DComView] PEN20 Count Match Classic handled {event_type}, strength now: {self.dcom_minigame.strength}")
                return
            elif event_type in ["B", "X"]:
                # Finish minigame and continue
                self.dcom_minigame_result = self.dcom_minigame.strength
                runtime_globals.game_console.log(f"[DComView] PEN20 Count Match Classic completed! Result: {self.dcom_minigame_result}")
                runtime_globals.game_sound.play("menu")
                self.dcom_minigame = None
                # Add delay to prevent button spam from clicking next view's components
                self.minigame_complete_time = time.time()
                self.waiting_after_minigame = True
                return
        
        # Handle PENZ minigame input (Count Match Z - uses SHAKE/Y)
        if self.phase == "minigame_penz" and self.dcom_minigame:
            if event_type in ["Y", "SHAKE"]:
                # Let minigame handle the event
                runtime_globals.game_console.log(f"[DComView] Passing {event_type} to PENZ Count Match Z")
                handled = self.dcom_minigame.handle_event(event)
                if handled:
                    runtime_globals.game_console.log(f"[DComView] Count Match Z handled {event_type}, press_counter now: {self.dcom_minigame.get_press_counter()}")
                return
            elif event_type in ["B", "X"]:
                # Finish minigame and continue
                self.dcom_minigame_result = self.dcom_minigame.calculate_result()
                runtime_globals.game_console.log(f"[DComView] PENZ Count Match Z completed! Result: {self.dcom_minigame_result}")
                runtime_globals.game_sound.play("menu")
                self.dcom_minigame = None
                # Add delay to prevent button spam from clicking next view's components
                self.minigame_complete_time = time.time()
                self.waiting_after_minigame = True
                return
        
        # Handle DMX minigame input
        if self.phase == "minigame_dmx":
            if event_type in ["A", "LCLICK"]:
                if self.dcom_xai_phase == 1 and self.dcom_xai_roll:
                    if not self.dcom_xai_roll.rolling:
                        self.dcom_xai_roll.roll()
                        runtime_globals.game_console.log("[DComView] XAI roll started")
                    elif not self.dcom_xai_roll.stopping:
                        self.dcom_xai_roll.stop()
                        self.dcom_xai_number = self.dcom_xai_roll.current_frame + 1
                        runtime_globals.game_console.log(f"[DComView] XAI roll stopped at: {self.dcom_xai_number}")
                elif self.dcom_xai_phase == 2 and self.dcom_xai_bar:
                    self.dcom_xai_bar.stop()
                    strength = self.dcom_xai_bar.get_result() or 1
                    # Map strength to attack value
                    if strength <= 5:
                        self.dcom_minigame_result = 0
                    elif strength <= 10:
                        self.dcom_minigame_result = 1
                    elif strength <= 15:
                        self.dcom_minigame_result = 2
                    else:
                        self.dcom_minigame_result = 3
                    self.dcom_xai_phase = 3
                    runtime_globals.game_console.log(f"[DComView] XAI bar stopped! Strength={strength}, Attack={self.dcom_minigame_result}")
                return
            elif event_type == "ESC":
                runtime_globals.game_console.log("[DComView] Minigame cancelled")
                runtime_globals.game_sound.play("cancel")
                self._on_cancel()
                return
    
    def cleanup(self):
        """Cleanup when view is destroyed."""
        self._cleanup_dcom()
        
        components = [
            self.background, self.title_scene, self.status_label,
            self.device_menu, self.protocol_menu, self.cancel_button,
        ]
        
        for comp in components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        
        runtime_globals.game_console.log("[DComView] Cleanup complete")

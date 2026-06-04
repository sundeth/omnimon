"""
DCom controller for managing serial communication with DCom hardware devices.
"""

import re
import time
from typing import List, Optional, Tuple, Callable
import threading

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. DCom functionality disabled.")

from .dcom_protocol import DComProtocol, ProtocolType


DEFAULT_VID = 6790  # Arduino VID
DEFAULT_PID = 29987  # Arduino PID  
DEFAULT_BAUD = 9600
LINE_TIMEOUT = 0.5
RESPONSE_PATTERN = re.compile(r"r:([0-9A-F]{32})", re.IGNORECASE)


class DComController:
    """
    Manages DCom device communication via serial port.
    Handles device detection, initialization, and packet exchange.
    """
    
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.connected = False
        self.device_info = None
        self.current_protocol: Optional[ProtocolType] = None
        self._response_callback: Optional[Callable] = None
        self._listening = False
        self._listen_thread: Optional[threading.Thread] = None
        
    def find_dcom_devices(self) -> List[Tuple[str, str]]:
        """
        Find all potential DCom devices.
        
        Returns:
            List of (port, description) tuples
        """
        if not SERIAL_AVAILABLE:
            return []
            
        devices = []
        for port in serial.tools.list_ports.comports():
            # Look for Arduino devices by VID/PID
            if port.vid == DEFAULT_VID and port.pid == DEFAULT_PID:
                devices.append((port.device, f"DCom ({port.description})"))
            # Also list other USB serial devices that might be DCom
            elif port.vid is not None:
                devices.append((port.device, port.description))
        
        return devices
    
    def connect(self, port: str, baud: int = DEFAULT_BAUD) -> bool:
        """
        Connect to DCom device on specified port.
        
        Args:
            port: Serial port name (e.g., "COM3" or "/dev/ttyUSB0")
            baud: Baud rate (default 9600)
            
        Returns:
            True if connection successful
        """
        if not SERIAL_AVAILABLE:
            print("Error: pyserial not available")
            return False
        
        # Disconnect if already connected
        if self.connected:
            self.disconnect()
            
        try:
            # Try to connect without exclusive flag first (more compatible)
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baud,
                timeout=LINE_TIMEOUT,
                write_timeout=LINE_TIMEOUT
            )
            
            # Give Arduino time to reset (DTR toggles reset)
            time.sleep(2.5)
            
            # Flush buffers
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            self.connected = True
            
            # Try to get device info
            self._send_raw("I\r")
            time.sleep(0.2)
            
            # Read response
            response = self._read_line()
            if response:
                self.device_info = response
                print(f"DCom device info: {response}")
            
            return True
            
        except serial.SerialException as e:
            error_msg = str(e)
            if "PermissionError" in error_msg or "Access is denied" in error_msg or "Acesso negado" in error_msg:
                print(f"\n❌ Port {port} is busy or access denied.")
                print("\n📋 Possible solutions:")
                print("  1. Close the Omnipet game if it's running")
                print("  2. Close Arduino IDE Serial Monitor")
                print("  3. Unplug and replug the USB device")
                print("  4. Check Windows Device Manager for port conflicts")
                print(f"\n💡 Tip: The port might be open in another program.")
            else:
                print(f"Failed to connect to DCom: {e}")
            self.connected = False
            return False
        except Exception as e:
            print(f"Failed to connect to DCom: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from DCom device"""
        self._stop_listening()
        
        if self.serial_port:
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
            except Exception as e:
                print(f"Warning: Error closing port: {e}")
        
        self.serial_port = None
        self.connected = False
    
    @staticmethod
    def list_all_ports():
        """List all serial ports on the system."""
        if not SERIAL_AVAILABLE:
            return []
        
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append((port.device, port.description, f"VID:PID={port.vid}:{port.pid}"))
        return ports
        self.current_protocol = None
    
    def initialize_device(self) -> bool:
        """
        Initialize DCom device if needed.
        
        Returns:
            True if initialization successful
        """
        if not self.connected:
            return False
            
        # Check if device has pending data
        if self.serial_port.in_waiting == 0:
            print("Sending DCom initialization code")
            init_cmd = DComProtocol.get_init_command()
            self._send_raw(init_cmd + "\r")
            time.sleep(0.2)
            return True
        
        return True
    
    def send_battle_packet(self, protocol: ProtocolType, turn: int, 
                          data_segments: List[str]) -> bool:
        """
        Send a battle packet to DCom device.
        
        Args:
            protocol: Protocol type
            turn: Turn number (0, 1, or 2)
            data_segments: List of hex data segments
            
        Returns:
            True if sent successfully
        """
        if not self.connected:
            print("Error: Not connected to DCom")
            return False
        
        # Validate data
        if not DComProtocol.validate_protocol_data(protocol, data_segments):
            print(f"Error: Invalid data for protocol {protocol.value}")
            return False
        
        # Format command
        command = DComProtocol.format_command(protocol, turn, data_segments)
        
        # Send to device
        self.current_protocol = protocol
        self._send_raw(command + "\r")
        
        print(f"Sent to DCom: {command}")
        return True
    
    def send_digirom_bytes(self, protocol: ProtocolType, packets: List[bytes]) -> bool:
        """
        Send digirom packets (raw bytes) to DCom device.
        
        Args:
            protocol: Protocol type
            packets: List of packet bytes
            
        Returns:
            True if sent successfully
        """
        # Convert bytes to hex segments
        hex_segments = [DComProtocol.bytes_to_hex(p) for p in packets]
        
        # Send with turn=1 (standard for initiating battle)
        return self.send_battle_packet(protocol, 1, hex_segments)
    
    def wait_for_response(self, timeout: float = 2.0) -> Optional[List[str]]:
        """
        Wait for response from DCom device.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            List of hex response strings, or None if timeout
        """
        if not self.connected:
            return None
        
        start_time = time.time()
        responses = []
        lines_received = 0
        
        print(f"[Waiting for response, timeout={timeout}s]")
        
        while time.time() - start_time < timeout:
            line = self._read_line()
            if line:
                lines_received += 1
                print(f"  Line {lines_received}: {line}")
                
                # Parse response
                parsed = DComProtocol.parse_response(line)
                if parsed:
                    response_type, hex_data = parsed
                    print(f"  -> Parsed as {response_type}: {hex_data}")
                    responses.extend(hex_data)
                    
                    # Color/DMX typically sends 2 responses
                    if len(responses) >= 2:
                        print(f"[Got {len(responses)} responses, returning]")
                        return responses
                elif line.startswith('t'):
                    print(f"  -> Timeout marker from DCom")
                else:
                    print(f"  -> Not a data response (info/echo)")
            
            time.sleep(0.05)  # Small delay between reads
        
        print(f"[Timeout reached, received {lines_received} lines, {len(responses)} responses]")
        return responses if responses else None
    
    def start_listening(self, callback: Callable[[List[str]], None]):
        """
        Start listening for responses in background thread.
        
        Args:
            callback: Function to call with response data
        """
        if self._listening:
            return
        
        self._response_callback = callback
        self._listening = True
        
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
    
    def _listen_loop(self):
        """Background thread for listening to DCom responses"""
        while self._listening and self.connected:
            try:
                line = self._read_line()
                if line and self._response_callback:
                    parsed = DComProtocol.parse_response(line)
                    if parsed:
                        _, hex_data = parsed
                        self._response_callback(hex_data)
            except Exception as e:
                print(f"Error in listen loop: {e}")
            
            time.sleep(0.05)
    
    def _stop_listening(self):
        """Stop background listening thread"""
        self._listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=1.0)
            self._listen_thread = None
        self._response_callback = None
    
    def _send_raw(self, data: str):
        """Send raw string to serial port"""
        if self.serial_port and self.serial_port.is_open:
            print(f"[DCom TX] {data.strip()}")  # Debug output
            self.serial_port.write(data.encode())
            self.serial_port.flush()  # Force data to be sent immediately
    
    def _read_line(self) -> Optional[str]:
        """Read a line from serial port"""
        if not self.serial_port or not self.serial_port.is_open:
            return None
        
        try:
            # Check if data is available
            if self.serial_port.in_waiting > 0:
                line = self.serial_port.readline().decode('utf-8', errors='ignore')
                if line:
                    line = line.strip()
                    if line:  # Only return non-empty lines
                        print(f"[DCom RX] {line}")  # Debug output
                        return line
            return None
        except Exception as e:
            print(f"Error reading line: {e}")
            return None
    
    @staticmethod
    def get_protocol_list() -> List[ProtocolType]:
        """Get list of supported protocols"""
        return [
            ProtocolType.COLOR,     # Start with Color/DMX (most common in game)
            ProtocolType.V_PET,     # V-Pet/Pendulum/Progress
            ProtocolType.PEN_X,     # Pendulum X
            ProtocolType.IC,        # iC/Accel/Twin
            ProtocolType.PEN_Y,     # Pendulum Y
        ]
    
    def test_connection(self) -> bool:
        """
        Test if connection is working.
        
        Returns:
            True if device responds
        """
        if not self.connected:
            return False
        
        try:
            # Send info command
            self._send_raw("I\r")
            time.sleep(0.2)
            
            # Check for response
            response = self._read_line()
            return response is not None and len(response) > 0
        except Exception:
            return False

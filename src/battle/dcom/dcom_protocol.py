"""
DCom protocol definitions and packet parsing.
Based on DMComm project protocols.
"""

from enum import Enum
from typing import List, Optional, Tuple


class ProtocolType(Enum):
    """Supported DCom protocols"""
    V_PET = "V"  # V-Pet / Pendulum / Progress (2-prong)
    PEN_X = "X"  # Pendulum X (3-prong)
    PEN_Y = "Y"  # Pendulum Y
    IC = "IC"    # iC (Accel/Twin)
    COLOR = "C"  # Color/DMX
    BARCODE = "BC"  # Barcode scanner
    
    @property
    def display_name(self):
        """Human-readable protocol name"""
        names = {
            ProtocolType.V_PET: "V-Pet / Pendulum / Progress",
            ProtocolType.PEN_X: "Pendulum X",
            ProtocolType.PEN_Y: "Pendulum Y", 
            ProtocolType.IC: "iC / Accel / Twin",
            ProtocolType.COLOR: "Color / DMX",
            ProtocolType.BARCODE: "Barcode Scanner"
        }
        return names.get(self, self.value)


class DComProtocol:
    """
    Handles DCom protocol command formatting and parsing.
    Format: <PROTOCOL><TURN>-<DATA1>-<DATA2>-...
    Example: V1-FC03-FD02 (V-Pet battle win)
    """
    
    @staticmethod
    def format_command(protocol: ProtocolType, turn: int, data_segments: List[str]) -> str:
        """
        Format a DCom command string.
        
        Args:
            protocol: Protocol type
            turn: Turn number (0, 1, or 2)
            data_segments: List of hex data segments
            
        Returns:
            Formatted command string (e.g., "V1-FC03-FD02")
        """
        segments = [f"{protocol.value}{turn}"] + data_segments
        return "-".join(segments)
    
    @staticmethod
    def parse_response(response: str) -> Optional[Tuple[str, List[str]]]:
        """
        Parse a DCom response.
        
        Args:
            response: Response string from device
            
        Returns:
            Tuple of (prefix, data_segments) or None if invalid
        """
        if not response or not response.startswith("r:"):
            return None
            
        # Extract hex data after "r:"
        hex_data = response[2:].strip().upper()
        
        # Response format is typically r:<32_hex_chars>
        if len(hex_data) != 32:
            return None
            
        return ("r", [hex_data])
    
    @staticmethod
    def bytes_to_hex(data: bytes) -> str:
        """Convert bytes to uppercase hex string"""
        return data.hex().upper()
    
    @staticmethod
    def hex_to_bytes(hex_str: str) -> bytes:
        """Convert hex string to bytes"""
        return bytes.fromhex(hex_str.replace(" ", "").replace(":", ""))
    
    @staticmethod
    def format_digirom_v1(checksum1: str, checksum2: str) -> str:
        """
        Format V-Pet battle digirom.
        
        Args:
            checksum1: First checksum (4 hex chars)
            checksum2: Second checksum (4 hex chars)
            
        Returns:
            V1 command string
        """
        return DComProtocol.format_command(
            ProtocolType.V_PET, 
            1, 
            [checksum1.upper(), checksum2.upper()]
        )
    
    @staticmethod
    def format_digirom_x1(data: List[str]) -> str:
        """
        Format Pendulum X battle digirom.
        
        Args:
            data: List of 4 hex segments
            
        Returns:
            X1 command string
        """
        return DComProtocol.format_command(ProtocolType.PEN_X, 1, data)
    
    @staticmethod
    def format_digirom_c1(packet1: str, packet2: str) -> str:
        """
        Format Color/DMX battle digirom.
        
        Args:
            packet1: First 16-byte packet (32 hex chars)
            packet2: Second 16-byte packet (32 hex chars)
            
        Returns:
            C1 command string
        """
        return DComProtocol.format_command(ProtocolType.COLOR, 1, [packet1, packet2])
    
    @staticmethod
    def get_init_command() -> str:
        """Get initialization command for DCom device"""
        return "v1-0000"
    
    @staticmethod
    def get_info_command() -> str:
        """Get device info command"""
        return "I"
    
    @staticmethod
    def validate_protocol_data(protocol: ProtocolType, data: List[str]) -> bool:
        """
        Validate data segments for a protocol.
        
        Args:
            protocol: Protocol type
            data: List of data segments
            
        Returns:
            True if data is valid for protocol
        """
        if protocol == ProtocolType.V_PET:
            # V-Pet needs 2 segments of 4 hex chars each
            return len(data) == 2 and all(len(d) == 4 for d in data)
        elif protocol == ProtocolType.PEN_X:
            # Pen X needs 4 segments
            return len(data) == 4
        elif protocol == ProtocolType.COLOR:
            # Color needs 2 segments of 32 hex chars each
            return len(data) == 2 and all(len(d) == 32 for d in data)
        return True  # Other protocols not validated yet

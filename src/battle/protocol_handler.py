"""
Protocol Handler - Loads and manages protocol definitions from JSON files.

This module provides a data-driven approach to handling different device protocols,
making it easy to add new protocols by simply creating JSON definition files.
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ProtocolDefinition:
    """Represents a loaded protocol definition."""
    
    name: str
    display_name: str
    type: str
    version: str
    description: str
    packet_count: int
    fixed_hp: Optional[int] = None
    uses_minigame: bool = False
    battle_mode: str = "single"
    constants: Dict[str, Any] = field(default_factory=dict)
    packets: List[Dict[str, Any]] = field(default_factory=list)
    notes: Dict[str, str] = field(default_factory=dict)
    
    def get_constant(self, name: str) -> Optional[Any]:
        """Get a constant value by name."""
        const = self.constants.get(name)
        return const.get('value') if const else None
    
    def get_packet(self, number: int) -> Optional[Dict[str, Any]]:
        """Get a packet definition by number."""
        for packet in self.packets:
            if packet.get('number') == number:
                return packet
        return None
    
    def get_field_value(self, packet_number: int, field_name: str, data: bytes) -> Optional[Any]:
        """Extract a field value from packet data."""
        packet = self.get_packet(packet_number)
        if not packet:
            return None
        
        # This is a simplified version - full implementation would parse bits properly
        # For now, return None and let the existing code handle it
        return None


class ProtocolHandler:
    """
    Manages loading and accessing protocol definitions.
    
    Protocol definitions are stored as JSON files in the protocols folder.
    This class provides methods to discover available protocols and load their definitions.
    """
    
    def __init__(self, protocols_dir: Optional[str] = None):
        """
        Initialize the protocol handler.
        
        Args:
            protocols_dir: Path to protocols directory. If None, uses default location.
        """
        if protocols_dir is None:
            # Default to data/protocols folder relative to src root
            src_root = os.path.dirname(os.path.dirname(__file__))
            self.protocols_dir = os.path.join(src_root, 'data')
        else:
            self.protocols_dir = protocols_dir
        
        self.battle_protocols_dir = os.path.join(self.protocols_dir, 'protocols')
        self._loaded_protocols: Dict[str, ProtocolDefinition] = {}
    
    def discover_protocols(self, protocol_type: str = 'protocols') -> List[str]:
        """
        Discover available protocol files.
        
        Args:
            protocol_type: Type of protocols to discover (e.g., 'battle', 'evolution')
            
        Returns:
            List of protocol names (without .json extension)
        """
        protocol_dir = os.path.join(self.protocols_dir, protocol_type)
        
        if not os.path.exists(protocol_dir):
            return []
        
        protocols = []
        for filename in os.listdir(protocol_dir):
            if filename.endswith('.json'):
                protocol_name = filename[:-5]  # Remove .json
                protocols.append(protocol_name)
        
        return sorted(protocols)
    
    def load_protocol(self, protocol_name: str, protocol_type: str = 'protocols') -> Optional[ProtocolDefinition]:
        """
        Load a protocol definition from JSON file.
        
        Args:
            protocol_name: Name of the protocol (e.g., 'DM20', 'DMX')
            protocol_type: Type of protocol (e.g., 'battle')
            
        Returns:
            ProtocolDefinition object or None if loading failed
        """
        # Check cache first
        cache_key = f"{protocol_type}:{protocol_name}"
        if cache_key in self._loaded_protocols:
            return self._loaded_protocols[cache_key]
        
        # Load from file
        protocol_file = os.path.join(self.protocols_dir, protocol_type, f"{protocol_name}.json")
        
        if not os.path.exists(protocol_file):
            print(f"[ProtocolHandler] Protocol file not found: {protocol_file}")
            return None
        
        try:
            with open(protocol_file, 'r') as f:
                data = json.load(f)
            
            # Extract protocol info
            protocol_info = data.get('protocol', {})
            
            # Create ProtocolDefinition
            definition = ProtocolDefinition(
                name=protocol_info.get('name', protocol_name),
                display_name=protocol_info.get('display_name', protocol_name),
                type=protocol_info.get('type', protocol_type),
                version=protocol_info.get('version', '1.0'),
                description=protocol_info.get('description', ''),
                packet_count=protocol_info.get('packet_count', 0),
                fixed_hp=protocol_info.get('fixed_hp'),
                uses_minigame=protocol_info.get('uses_minigame', False),
                battle_mode=protocol_info.get('battle_mode', 'single'),
                constants=data.get('constants', {}),
                packets=data.get('packets', []),
                notes=data.get('notes', {})
            )
            
            # Cache it
            self._loaded_protocols[cache_key] = definition
            
            return definition
            
        except Exception as e:
            print(f"[ProtocolHandler] Error loading protocol {protocol_name}: {e}")
            return None
    
    def get_protocol_list(self, protocol_type: str = 'battle') -> List[Dict[str, str]]:
        """
        Get list of available protocols with their display information.
        
        Args:
            protocol_type: Type of protocols to list
            
        Returns:
            List of dicts with 'name' and 'display_name' keys
        """
        protocol_names = self.discover_protocols(protocol_type)
        protocol_list = []
        
        for name in protocol_names:
            protocol = self.load_protocol(name, protocol_type)
            if protocol:
                protocol_list.append({
                    'name': protocol.name,
                    'display_name': protocol.display_name,
                    'description': protocol.description
                })
        
        return protocol_list
    
    def get_protocol_info(self, protocol_name: str, protocol_type: str = 'battle') -> Optional[Dict[str, Any]]:
        """
        Get protocol information without fully loading it.
        
        Args:
            protocol_name: Name of the protocol
            protocol_type: Type of protocol
            
        Returns:
            Dict with protocol info or None
        """
        protocol = self.load_protocol(protocol_name, protocol_type)
        if protocol:
            return {
                'name': protocol.name,
                'display_name': protocol.display_name,
                'description': protocol.description,
                'packet_count': protocol.packet_count,
                'fixed_hp': protocol.fixed_hp,
                'uses_minigame': protocol.uses_minigame,
                'battle_mode': protocol.battle_mode
            }
        return None


# Global instance for easy access
_handler = None

def get_protocol_handler() -> ProtocolHandler:
    """Get the global protocol handler instance."""
    global _handler
    if _handler is None:
        _handler = ProtocolHandler()
    return _handler

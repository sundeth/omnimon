"""
Protocol List Utility - Show available protocols for battle system.

This utility demonstrates how to discover and display available protocols.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from core.combat.protocols import ProtocolHandler


def list_all_protocols():
    """List all available battle protocols."""
    handler = ProtocolHandler()
    
    print("=" * 70)
    print("AVAILABLE BATTLE PROTOCOLS")
    print("=" * 70)
    print()
    
    protocols = handler.discover_protocols('battle')
    
    if not protocols:
        print("No protocols found!")
        return
    
    for protocol_name in protocols:
        protocol = handler.load_protocol(protocol_name, 'battle')
        
        if protocol:
            print(f"📁 {protocol.display_name}")
            print(f"   Name: {protocol.name}")
            print(f"   Description: {protocol.description}")
            print(f"   Packet Count: {protocol.packet_count}")
            print(f"   Fixed HP: {protocol.fixed_hp if protocol.fixed_hp else 'Variable'}")
            print(f"   Uses Minigame: {'Yes' if protocol.uses_minigame else 'No'}")
            print(f"   Battle Mode: {protocol.battle_mode}")
            print()


def show_protocol_details(protocol_name: str):
    """Show detailed information about a specific protocol."""
    handler = ProtocolHandler()
    protocol = handler.load_protocol(protocol_name, 'battle')
    
    if not protocol:
        print(f"Protocol '{protocol_name}' not found!")
        return
    
    print("=" * 70)
    print(f"PROTOCOL: {protocol.display_name}")
    print("=" * 70)
    print()
    
    # Basic info
    print("BASIC INFORMATION")
    print("-" * 70)
    print(f"Name:         {protocol.name}")
    print(f"Version:      {protocol.version}")
    print(f"Description:  {protocol.description}")
    print(f"Type:         {protocol.type}")
    print()
    
    # Configuration
    print("CONFIGURATION")
    print("-" * 70)
    print(f"Packet Count:  {protocol.packet_count}")
    print(f"Fixed HP:      {protocol.fixed_hp if protocol.fixed_hp else 'Variable'}")
    print(f"Uses Minigame: {'Yes' if protocol.uses_minigame else 'No'}")
    print(f"Battle Mode:   {protocol.battle_mode}")
    print()
    
    # Constants
    if protocol.constants:
        print("CONSTANTS")
        print("-" * 70)
        for name, const in protocol.constants.items():
            value = const.get('value')
            desc = const.get('description', 'No description')
            print(f"{name:15s} = {str(value):10s}  # {desc}")
        print()
    
    # Packets
    if protocol.packets:
        print("PACKET STRUCTURE")
        print("-" * 70)
        for packet in protocol.packets:
            print(f"\nPacket {packet['number']}: {packet['description']}")
            print(f"  Fields:")
            for field in packet['fields']:
                field_name = field['name']
                field_bits = field['bits']
                field_type = field['type']
                field_desc = field.get('description', '')
                
                ref = f" (ref: {field['ref']})" if 'ref' in field else ""
                calc = " [calculated]" if field.get('calculated') else ""
                
                print(f"    - {field_name:15s} ({field_bits:2d} bits, {field_type:5s}){ref}{calc}")
                if field_desc:
                    print(f"      {field_desc}")
        print()
    
    # Notes
    if protocol.notes:
        print("NOTES")
        print("-" * 70)
        for key, note in protocol.notes.items():
            print(f"• {key}: {note}")
        print()


def compare_protocols():
    """Compare all protocols side by side."""
    handler = ProtocolHandler()
    protocols = handler.discover_protocols('battle')
    
    print("=" * 100)
    print("PROTOCOL COMPARISON")
    print("=" * 100)
    print()
    
    # Table header
    print(f"{'Protocol':<15} {'Packets':<10} {'HP':<10} {'Minigame':<10} {'Mode':<10}")
    print("-" * 100)
    
    for protocol_name in protocols:
        protocol = handler.load_protocol(protocol_name, 'battle')
        
        if protocol:
            hp_str = str(protocol.fixed_hp) if protocol.fixed_hp else "Variable"
            minigame_str = "Yes" if protocol.uses_minigame else "No"
            
            print(f"{protocol.name:<15} {protocol.packet_count:<10} {hp_str:<10} "
                  f"{minigame_str:<10} {protocol.battle_mode:<10}")
    
    print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Protocol System Utility')
    parser.add_argument('command', nargs='?', default='list', 
                       choices=['list', 'details', 'compare'],
                       help='Command to execute')
    parser.add_argument('--protocol', '-p', type=str,
                       help='Protocol name for details command')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_all_protocols()
    elif args.command == 'details':
        if args.protocol:
            show_protocol_details(args.protocol)
        else:
            print("Please specify a protocol name with --protocol")
            print("\nAvailable protocols:")
            handler = ProtocolHandler()
            for p in handler.discover_protocols('battle'):
                print(f"  - {p}")
    elif args.command == 'compare':
        compare_protocols()

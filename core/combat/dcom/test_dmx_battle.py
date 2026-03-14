"""
Test script for DCom battle communication using DMX protocol.
Tests battle packet generation and transmission with Digimon X data.
DMX/Pendulum Z uses V-Pet protocol (2-prong, V commands) with 6 packets,
NOT COLOR protocol (3-prong, C commands)."""
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from core.combat.dcom.dcom_controller import DComController
from core.combat.dcom.dcom_protocol import ProtocolType


class DigimonXData:
    """Simple container for Digimon X battle data."""
    
    def __init__(self, name: str, power: int, hp: int, level: int, attribute: int):
        self.name = name
        self.power = power
        self.hp = hp
        self.level = level  # 0-9 (displayed as 1-10)
        self.attribute = attribute  # 0=Vaccine, 1=Data, 2=Virus
        self.stage = 3  # Ultimate
        self.index = 30  # War Greymon X
        self.shot_s = 53  # Strong shot
        self.shot_w = 40  # Weak shot
        self.shot_m = 53  # Middle shot
        self.sick = 0  # Not sick
        self.buff = 1  # +1 damage
        self.mini_game = 3  # Excellent (0-3)


class DComDMXTest:
    """Test class for DCom DMX battle communication."""
    
    def __init__(self):
        self.controller = DComController()
        self.wargreymon = DigimonXData(
            name="War Greymon X",
            power=168,
            hp=22,
            level=4,  # Level 5 (displays as 4)
            attribute=0  # Vaccine
        )
    
    def list_devices(self):
        """List all available DCom devices."""
        print("Scanning for DCom devices...")
        devices = self.controller.find_dcom_devices()
        
        if not devices:
            print("No DCom devices found!")
            return []
        
        print(f"\nFound {len(devices)} device(s):")
        for i, (port, desc) in enumerate(devices):
            print(f"  [{i}] {desc}")
            print(f"      Port: {port}")
        
        return devices
    
    def connect_device(self, device_index: int = 0) -> bool:
        """Connect to a DCom device by index."""
        devices = self.controller.find_dcom_devices()
        if not devices or device_index >= len(devices):
            print(f"Invalid device index: {device_index}")
            return False
        
        port, desc = devices[device_index]
        print(f"\nConnecting to {desc} on {port}...")
        
        if self.controller.connect(port):
            print("✓ Connected successfully!")
            return True
        else:
            print("✗ Connection failed!")
            return False
    
    def generate_dmx_battle_packets(self) -> list[bytes]:
        """
        Generate DMX battle packets using Digimon X data.
        DMX uses 6 packets of 16 bits (4 hex chars) each.
        Returns list of 6 packets (2 bytes each).
        
        Correct packet structure from documentation:
        Packet 1: Order(1) Level(4) Sick(1) Attack(2) Version(4) EOL(4)
        Packet 2: Stage(3) Index(7) Attribute(2) EOL(4)
        Packet 3: Shot S(6) Shot W(6) EOL(4)
        Packet 4: COU(2) HP(5) Shot M(5) EOL(4)
        Packet 5: COU(2) Buff(2) Power(8) EOL(4)
        Packet 6: Check(4) COU(3) Hits(5) EOL(4)
        """
        packets = []
        digi = self.wargreymon
        eol = 0xE  # 1110
        
        # Packet 1: Order(1) Level(4) Sick(1) Attack(2) Version(4) EOL(4)
        # Example: 0 0100 0 11 0000 1110
        order = 0
        level = digi.level
        sick = digi.sick
        attack = digi.mini_game & 0x03  # 2 bits only (0-3)
        version = 0  # Version 1 - Black
        
        # Pack into 16 bits across 2 bytes
        # Byte 1: O(1) LLLL(4) S(1) AA(2)
        # Byte 2: VVVV(4) EEEE(4)
        byte1 = (order << 7) | (level << 3) | (sick << 2) | attack
        byte2 = (version << 4) | eol
        packets.append(bytes([byte1, byte2]))
        
        # Packet 2: Stage(3) Index(7) Attribute(2) EOL(4)
        # Example: 100 0011110 00 1110
        stage = digi.stage
        index = digi.index & 0x7F  # 7 bits
        attribute = digi.attribute & 0x03  # 2 bits
        
        # Byte 1: SSS(3) IIII(4) + I(1 bit from next)
        # Byte 2: III(2) AA(2) EEEE(4)
        byte1 = (stage << 5) | (index >> 2)  # Stage(3) + Index_high(5)
        byte2 = ((index & 0x03) << 6) | (attribute << 4) | eol  # Index_low(2) + Attribute(2) + EOL(4)
        packets.append(bytes([byte1, byte2]))
        
        # Packet 3: Shot S(6) Shot W(6) EOL(4)
        # Example: 011001 001000 1110
        shot_s = digi.shot_s & 0x3F  # 6 bits
        shot_w = digi.shot_w & 0x3F  # 6 bits
        
        byte1 = (shot_s << 2) | (shot_w >> 4)  # ShotS(6) + ShotW_high(2)
        byte2 = ((shot_w & 0x0F) << 4) | eol  # ShotW_low(4) + EOL(4)
        packets.append(bytes([byte1, byte2]))
        
        # Packet 4: COU(2) HP(5) Shot M(5) EOL(4)
        # Example: 00 10110 10101 1110
        cou = 0
        hp = digi.hp & 0x1F  # 5 bits
        shot_m = digi.shot_m & 0x1F  # 5 bits
        
        byte1 = (cou << 6) | (hp << 1) | (shot_m >> 4)  # COU(2) + HP(5) + ShotM_high(1)
        byte2 = ((shot_m & 0x0F) << 4) | eol  # ShotM_low(4) + EOL(4)
        packets.append(bytes([byte1, byte2]))
        
        # Packet 5: COU(2) Buff(2) Power(8) EOL(4)
        # Example: 00 01 10101000 1110
        buff = digi.buff & 0x03  # 2 bits
        power = digi.power
        
        byte1 = (cou << 6) | (buff << 4) | (power >> 4)  # COU(2) + Buff(2) + Power_high(4)
        byte2 = ((power & 0x0F) << 4) | eol  # Power_low(4) + EOL(4)
        packets.append(bytes([byte1, byte2]))
        
        # Packet 6: Check(4) COU(3) Hits(5) EOL(4)
        # Example: 1111 000 11111 1110
        hits = 0x1F  # All hit (5 bits)
        cou3 = 0  # 3 bits
        
        # Calculate checksum - sum all nibbles from packets 1-5
        checksum = 0
        for pkt in packets:
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F  # Upper nibble
                checksum += byte & 0x0F  # Lower nibble
        
        # Now construct packet 6 byte structure (without check nibble yet)
        # Byte 1: CCCC(4) CCC(3) H(1) = Check(4) + COU(3) + Hits_high(1)
        # Byte 2: HHHH(4) EEEE(4) = Hits_low(4) + EOL(4)
        
        # Build the two bytes with check=0 initially
        byte1_without_check = (cou3 << 1) | (hits >> 4)  # CCC(3) H(1) = lower 4 bits of byte 1
        byte2 = ((hits & 0x0F) << 4) | eol  # Hits_low(4) + EOL(4)
        
        # Add nibbles from packet 6 (without check)
        checksum += byte1_without_check & 0x0F  # Lower nibble of byte 1
        checksum += (byte2 >> 4) & 0x0F  # Upper nibble of byte 2
        checksum += byte2 & 0x0F  # Lower nibble of byte 2 (EOL)
        
        # Find check value that makes (checksum + check) % 16 == 8
        intended_remainder = 8
        check = (intended_remainder - (checksum % 16)) % 16
        
        # Now construct final byte 1 with check nibble
        byte1 = (check << 4) | byte1_without_check
        
        packets.append(bytes([byte1, byte2]))
        
        return packets
    
    def send_battle_packets(self) -> bool:
        """Send DMX battle packets to connected device."""
        if not self.controller.connected:
            print("Error: No device connected!")
            return False
        
        print(f"\nGenerating DMX battle packets for {self.wargreymon.name}...")
        print(f"  Power: {self.wargreymon.power}")
        print(f"  HP: {self.wargreymon.hp}")
        print(f"  Level: {self.wargreymon.level + 1}")
        print(f"  Attribute: {['Vaccine', 'Data', 'Virus'][self.wargreymon.attribute]}")
        
        packets = self.generate_dmx_battle_packets()
        
        print(f"\nGenerated {len(packets)} DMX packets:")
        for i, pkt in enumerate(packets, 1):
            hex_str = pkt.hex().upper()
            binary = ' '.join(format(b, '08b') for b in pkt)
            print(f"  Packet {i}: {hex_str} ({binary})")
        
        print("\n⚠️  IMPORTANT: DMX protocol uses V-Pet protocol (V commands) with 6 packets!")
        print("DMX/Pendulum Z are 2-prong devices like DM20, but exchange 6 packets instead of 10.\n")
        
        print("=== Battle Mode Selection ===")
        print("1. V0 - Listen only (wait for opponent to send first)")
        print("2. V1 - Send first (initiate battle)")
        print("3. V2 - Listen and reply (wait for opponent, then respond) [RECOMMENDED]")
        
        mode_input = input("Select mode (1-3, default=3): ").strip() or "3"
        
        # Convert input to mode number (0, 1, or 2)
        if mode_input == "1":
            turn = 0
        elif mode_input == "2":
            turn = 1
        else:  # default to 3 -> C2
            turn = 2
        
        if turn == 0:
            print("\n📡 Listening for opponent device...")
            listen_cmd = 'V0'
            self.controller._send_raw(listen_cmd + '\r')
            print(f"Sent: {listen_cmd}")
        else:
            # Build V1 or V2 command with 6 packets
            hex_packets = [pkt.hex().upper() for pkt in packets]
            command = f"V{turn}-" + "-".join(hex_packets)
            
            print(f"\nSending command: {command}")
            self.controller._send_raw(command + '\r')
            print("✓ Command sent!")
        
        # Wait for response
        print("\nWaiting for response from opponent device...")
        print(f"(V{turn} mode: DMX exchanges 6 packets)\n")
        responses = []
        sent_packets = []
        start_time = time.time()
        timeout = 15.0
        
        while time.time() - start_time < timeout:
            if self.controller.serial_port.in_waiting > 0:
                line = self.controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    if not line.startswith('t:'):
                        print(f"Received: {line}")
                    
                    import re
                    r_matches = re.findall(r'r:[0-9A-Fa-f]{4}', line)
                    s_matches = re.findall(r's:[0-9A-Fa-f]{4}', line)
                    
                    if r_matches:
                        for match in r_matches:
                            hex_data = match[2:]
                            # Filter out FF00 error/terminator packets
                            if hex_data.upper() != 'FF00':
                                responses.append(hex_data)
                                print(f"  ← DMX packet {len(responses)}/6: {hex_data}")
                            else:
                                print(f"  ⚠ DCom sent FF00 (error/terminator - packet count mismatch)")
                    
                    if s_matches:
                        for match in s_matches:
                            hex_data = match[2:]
                            sent_packets.append(hex_data)
                            print(f"  → War Greymon X packet {len(sent_packets)}/6: {hex_data}")
                    
                    # DMX exchanges 6 packets
                    if len(responses) >= 6:
                        break
            
            time.sleep(0.05)
        
        if responses:
            print(f"\n✅ Battle exchange complete!")
            print(f"   Received: {len(responses)}/6 packets from opponent")
            print(f"   Sent: {len(sent_packets)}/6 packets")
            if len(responses) < 6:
                print(f"\n⚠️  Only received {len(responses)} packets - transmission may have been interrupted")
            self.parse_dmx_battle_response(responses)
        else:
            print("✗ No response received (timeout)")
        
        return True
    
    def parse_dmx_battle_response(self, packets: list):
        """Parse DMX battle response (6 packets)."""
        if len(packets) < 6:
            print(f"Warning: Expected 6 packets, got {len(packets)}")
        
        print(f"\nParsing DMX battle data:")
        
        try:
            # Packet 2: Stage, Index, Attribute
            if len(packets) >= 2:
                pkt2 = bytes.fromhex(packets[1])
                stage = pkt2[0] >> 5
                index = ((pkt2[0] & 0x1F) << 2) | (pkt2[1] >> 6)
                attribute = (pkt2[1] >> 4) & 0x03
                
                stage_name = ["Baby II", "Child", "Adult", "Perfect", "Ultimate", "Super Ultimate"][stage] if stage < 6 else "Unknown"
                attr_name = ["Vaccine", "Data", "Virus"][attribute] if attribute < 3 else "Unknown"
                
                print(f"  Opponent Stage: {stage_name}")
                print(f"  Opponent Index: {index}")
                print(f"  Opponent Attribute: {attr_name}")
            
            # Packet 4: HP
            if len(packets) >= 4:
                pkt4 = bytes.fromhex(packets[3])
                hp = (pkt4[0] >> 1) & 0x1F
                print(f"  Opponent HP: {hp}")
            
            # Packet 5: Power
            if len(packets) >= 5:
                pkt5 = bytes.fromhex(packets[4])
                power = ((pkt5[0] & 0x0F) << 4) | (pkt5[1] >> 4)
                print(f"  Opponent Power: {power}")
            
            # Packet 6: Hits
            if len(packets) >= 6:
                pkt6 = bytes.fromhex(packets[5])
                hits = ((pkt6[0] & 0x01) << 4) | (pkt6[1] >> 4)
                print(f"  Hits: {bin(hits)[2:].zfill(5)}")
        
        except Exception as e:
            print(f"Error parsing DMX response: {e}")
    
    def disconnect(self):
        """Disconnect from device."""
        if self.controller.connected:
            print("\nDisconnecting from device...")
            self.controller.disconnect()
            print("✓ Disconnected")
    
    def run_interactive_test(self):
        """Run interactive test menu."""
        print("=" * 50)
        print("DCom Battle Test - DMX Protocol")
        print("Using War Greymon X data")
        print("=" * 50)
        
        while True:
            print("\n=== Menu ===")
            print("1. List DCom devices")
            print("2. Connect to device")
            print("3. Send battle packets (War Greymon X)")
            print("4. Disconnect")
            print("5. Exit")
            
            choice = input("\nEnter choice (1-5): ").strip()
            
            if choice == "1":
                self.list_devices()
            
            elif choice == "2":
                devices = self.list_devices()
                if devices:
                    if len(devices) == 1:
                        self.connect_device(0)
                    else:
                        idx = input(f"Enter device index (0-{len(devices)-1}): ").strip()
                        try:
                            self.connect_device(int(idx))
                        except ValueError:
                            print("Invalid index!")
            
            elif choice == "3":
                self.send_battle_packets()
            
            elif choice == "4":
                self.disconnect()
            
            elif choice == "5":
                self.disconnect()
                print("\nExiting...")
                break
            
            else:
                print("Invalid choice!")


def main():
    """Main entry point."""
    test = DComDMXTest()
    test.run_interactive_test()


if __name__ == "__main__":
    main()

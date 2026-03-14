"""
Test script for DCom battle communication using DM20 protocol.
Tests battle packet generation and transmission with Agumon data.
"""
import sys
import os
import time
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from core.combat.dcom.dcom_controller import DComController
from core.combat.dcom.dcom_protocol import ProtocolType, DComProtocol


class DigimonData:
    """Simple container for Digimon battle data."""
    
    def __init__(self, name: str, power: int, hp: int, attribute: str, stage: int):
        self.name = name
        self.power = power
        self.hp = hp
        self.attribute = attribute
        self.stage = stage
        self.atk_main = 1  # Default attack sprite
        self.atk_alt = 26  # Alternate attack sprite


class DComBattleTest:
    """Test class for DCom battle communication."""
    
    def __init__(self):
        self.controller = DComController()
        self.agumon = DigimonData(
            name="Agumon",
            power=18,  # From DM20 monster.json
            hp=100,    # Default HP for testing
            attribute="Va",  # Vaccine attribute
            stage=3    # Child/Rookie level
        )
    
    def list_devices(self):
        """List all available DCom devices."""
        print("Scanning for DCom devices...")
        devices = self.controller.find_dcom_devices()
        
        if not devices:
            print("No DCom devices found!")
            print("\nMake sure your DM20 device is:")
            print("  1. Connected via USB")
            print("  2. Powered on")
            print("  3. In communication mode (if required)")
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
    
    def generate_dm20_battle_packet(self) -> list[bytes]:
        """
        Generate DM20 battle packets using Agumon data.
        DM20 uses 10 packets of 16 bits (4 hex chars) each.
        Returns list of 10 packets (2 bytes each).
        """
        packets = []
        
        # Packet 1: Name 2, Name 1 (4 bytes for tamer name, using default)
        # Using simple name "TEST" = 0x54455354
        packets.append(bytes([0x54, 0x45]))  # "TE"
        
        # Packet 2: Name 4, Name 3
        packets.append(bytes([0x53, 0x54]))  # "ST"
        
        # Packet 3: Order | Attack | Operation | Version | EOL
        # Order: 1 bit = 0, Attack: 4 bits = 0000, Operation: 2 bits = 00, Version: 5 bits = 00001, EOL: 4 bits = 1110
        # Binary: 0 0000 00 00001 1110 = 00000000011110 = 0x001E
        # Using Order=0 (listening/replying), Attack=0000 (no minigame), Operation=00 (single), Version=00001 (Ver.1)
        packets.append(bytes([0x00, 0x1E]))
        
        # Packet 4: COU | Index L | Attribute L | EOL
        # COU: 2 bits = 00, Index: 8 bits = 00000100, Attribute: 2 bits = 00, EOL: 4 bits = 1110
        # Binary: 00 00000100 00 1110 = 0000000100001110
        # Pack across bytes: 00000001 00001110 = 0x01 0x0E
        index = 4  # Agumon index
        attribute = 0  # Vaccine = 00
        byte1 = (0 << 6) | (index >> 2)  # COU(2 bits) + upper 6 bits of Index
        byte2 = ((index & 0x03) << 6) | (attribute << 4) | 0x0E  # lower 2 bits of Index + Attribute(2 bits) + EOL
        packets.append(bytes([byte1, byte2]))
        
        # Packet 5: Shot S L | Shot W L | EOL
        # Shot S: 6 bits = 000011, Shot W: 6 bits = 000011, EOL: 4 bits = 1110
        # Binary: 000011 000011 1110 = 0000110000111110 = 0x0C3E
        shot_s = 3
        shot_w = 3
        byte1 = (shot_s << 2) | (shot_w >> 4)  # ShotS(6 bits) + upper 2 bits of ShotW
        byte2 = ((shot_w & 0x0F) << 4) | 0x0E  # lower 4 bits of ShotW + EOL
        packets.append(bytes([byte1, byte2]))
        
        # Packet 6: COU | Power L | EOL
        # COU: 4 bits = 0000, Power: 8 bits, EOL: 4 bits = 1110
        # Binary: 0000 PPPPPPPP 1110
        # For power=18=0x12=00010010: 0000 00010010 1110 = 0000000100101110 = 0x012E
        # Pack across bytes: 00000001 00101110 = 0x01 0x2E
        power = self.agumon.power
        byte1 = (0 << 4) | (power >> 4)  # COU(4 bits) + upper 4 bits of Power
        byte2 = ((power & 0x0F) << 4) | 0x0E  # lower 4 bits of Power + EOL
        packets.append(bytes([byte1, byte2]))
        
        # Packet 7: COU | Index R | Attribute R | EOL (Right digimon, all 0 for single battle)
        packets.append(bytes([0x00, 0x0E]))
        
        # Packet 8: Shot S R | Shot W R | EOL (Right digimon, all 0 for single battle)
        packets.append(bytes([0x00, 0x0E]))
        
        # Packet 9: Tag Meter | Power R | EOL (Right digimon, all 0 for single battle)
        packets.append(bytes([0x00, 0x0E]))
        
        # Packet A: Check | Dodges | Hits | EOL
        # Calculate checksum (Check field) - sum all nibbles mod 16, then find value that makes remainder 0
        # Dodges: 0000 (all dodge), Hits: 1111 (all hit), EOL: 1110
        dodges = 0x0  # 0000 = all dodge
        hits = 0xF    # 1111 = all hit
        
        # Calculate checksum: sum all 4-bit nibbles from packets 1-9
        checksum = 0
        for pkt in packets:
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F  # Upper nibble
                checksum += byte & 0x0F          # Lower nibble
        
        # Add dodges and hits
        checksum += dodges
        checksum += hits
        checksum += 0x0E  # EOL nibbles
        
        # Find check value that makes (checksum + check) % 16 == 0
        check = (16 - (checksum % 16)) % 16
        
        byte1 = (check << 4) | dodges
        byte2 = (hits << 4) | 0x0E
        packets.append(bytes([byte1, byte2]))
        
        return packets
    
    def send_battle_packets(self) -> bool:
        """Send battle packets to connected device."""
        if not self.controller.connected:
            print("Error: No device connected!")
            return False
        
        print(f"\nGenerating battle packets for {self.agumon.name}...")
        print(f"  Power: {self.agumon.power}")
        print(f"  HP: {self.agumon.hp}")
        print(f"  Attribute: {self.agumon.attribute}")
        print(f"  Stage: {self.agumon.stage}")
        
        packets = self.generate_dm20_battle_packet()
        
        print(f"\nGenerated {len(packets)} DM20 packets:")
        for i, pkt in enumerate(packets, 1):
            hex_str = pkt.hex().upper()
            # Show binary for verification
            binary = ' '.join(format(b, '08b') for b in pkt)
            print(f"  Packet {i}: {hex_str} ({binary})")
        
        print("\n=== Battle Mode Selection ===")
        print("1. V0 - Listen only (wait for opponent to send first)")
        print("2. V1 - Send first (initiate battle)")
        print("3. V2 - Listen and reply (wait for opponent, then respond) [RECOMMENDED]")
        
        mode = input("Select mode (1-3, default=3): ").strip() or "3"
        
        if mode == "1":
            # Listen only mode
            turn = 0
            print("\n📡 Listening for opponent device...")
            print("(Waiting for the other device to initiate...)")
            
            # Send V0 command (listen only)
            listen_cmd = 'V0'
            self.controller._send_raw(listen_cmd + '\r')
            print(f"Sent: {listen_cmd}")
            
            # Wait for 10 response packets
            responses = []
            start_time = time.time()
            timeout = 15.0
            
            while time.time() - start_time < timeout:
                if self.controller.serial_port.in_waiting > 0:
                    line = self.controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"Received: {line}")
                        
                        # Look for r:[4 hex] pattern (16-bit packets)
                        import re
                        matches = re.findall(r'r:[0-9A-Fa-f]{4}', line)
                        if matches:
                            for match in matches:
                                hex_data = match[2:]
                                responses.append(hex_data)
                                print(f"  -> Got packet {len(responses)}: {hex_data}")
                            
                            if len(responses) >= 10:
                                break
                
                time.sleep(0.05)
            
            if responses:
                print(f"\n✓ Received {len(responses)} packet(s)!")
                self.parse_dm20_battle_response(responses)
            else:
                print("✗ No packets received (timeout)")
            
            return True
            
        elif mode == "2":
            # Send first mode (V1)
            turn = 1
            print("\n📤 Sending battle packets (initiating battle)...")
        else:
            # Listen and reply mode (V2)
            turn = 2
            print("\n🔄 Using listen-and-reply mode (V2)...")
            print("The DCom will wait for opponent first, then send our packets")
        
        # Send to device
        print("\nSending packets to device...")
        
        # Build V1 or V2 command with 10 packets
        # Format: V1-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
        hex_packets = [pkt.hex().upper() for pkt in packets]
        command = f"V{turn}-" + "-".join(hex_packets)
        
        print(f"Sending command: {command}")
        self.controller._send_raw(command + '\r')
        
        success = True
        
        if success:
            print("✓ Command sent!")
            
            # Wait for response - DM20 sends 10 packets of 4 hex chars each
            print("\nWaiting for response from opponent device...")
            print("(V2 mode: DCom will wait for opponent, then exchange packets)\n")
            responses = []
            sent_packets = []
            start_time = time.time()
            timeout = 15.0
            
            while time.time() - start_time < timeout:
                if self.controller.serial_port.in_waiting > 0:
                    line = self.controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        # Skip status messages for cleaner output
                        if not line.startswith('t:'):
                            print(f"Received: {line}")
                        
                        # Look for both r:[4 hex] (received from opponent) and s:[4 hex] (sent to opponent)
                        import re
                        r_matches = re.findall(r'r:[0-9A-Fa-f]{4}', line)
                        s_matches = re.findall(r's:[0-9A-Fa-f]{4}', line)
                        
                        if r_matches:
                            for match in r_matches:
                                hex_data = match[2:]
                                responses.append(hex_data)
                                print(f"  ← DM20 packet {len(responses)}/10: {hex_data}")
                        
                        if s_matches:
                            for match in s_matches:
                                hex_data = match[2:]
                                sent_packets.append(hex_data)
                                print(f"  → Agumon packet {len(sent_packets)}/10: {hex_data}")
                        
                        # DM20 exchanges 10 packets each way
                        if len(responses) >= 10:
                            break
                
                time.sleep(0.05)
            
            if responses:
                print(f"\n✅ Battle exchange complete!")
                print(f"   Received: {len(responses)}/10 packets from opponent")
                print(f"   Sent: {len(sent_packets)}/10 packets (Agumon)")
                if len(responses) < 10:
                    print(f"\n⚠️  Only received {len(responses)} packets - transmission may have been interrupted")
                    print("   Keep devices very close and stable during entire exchange!")
                self.parse_dm20_battle_response(responses)
            else:
                print("✗ No response received (timeout)")
            
            return True
        else:
            print("✗ Failed to send command!")
            return False
    
    def interpret_status_message(self, message: str):
        """Interpret DCom status messages (t: prefix)."""
        if message.startswith('t:-3'):
            return "⏳ Waiting for signal..."
        elif message.startswith('t:-2'):
            return "⚠️ Timeout or error"
        elif message.startswith('t:'):
            return f"📊 Status: {message}"
        return message
    
    def parse_dm20_battle_response(self, packets: list):
        """Parse DM20 battle response (10 packets of 4 hex chars each)."""
        if len(packets) < 10:
            print(f"Warning: Expected 10 packets, got {len(packets)}")
        
        print(f"\nParsing DM20 battle data:")
        
        try:
            # Packet 4: Index L (opponent digimon)
            if len(packets) >= 4:
                pkt4 = bytes.fromhex(packets[3])
                index_l = pkt4[0] >> 2  # 6 bits for index
                attr_l = pkt4[0] & 0x03  # 2 bits for attribute
                attr_name = {0: "Vaccine", 1: "Data", 2: "Virus", 3: "Free"}.get(attr_l, "Unknown")
                print(f"  Opponent Index: {index_l}")
                print(f"  Opponent Attribute: {attr_name}")
            
            # Packet 6: Power L (opponent power)
            if len(packets) >= 6:
                pkt6 = bytes.fromhex(packets[5])
                power_l = pkt6[0]
                print(f"  Opponent Power: {power_l}")
            
            # Packet A: Hits/Dodges
            if len(packets) >= 10:
                pktA = bytes.fromhex(packets[9])
                hits = (pktA[1] >> 4) & 0x0F  # 4 bits for hits
                dodges = pktA[1] & 0x0F  # 4 bits for dodges
                print(f"  Hits: {bin(hits)[2:].zfill(4)}")
                print(f"  Dodges: {bin(dodges)[2:].zfill(4)}")
            
            # Simple battle simulation
            print(f"\n=== Battle Simulation ===")
            print(f"Agumon (Power {self.agumon.power}) vs Opponent (Power {power_l if len(packets) >= 6 else '?'})")
            
            if len(packets) >= 6:
                if self.agumon.power > power_l:
                    print("Result: VICTORY!")
                elif self.agumon.power < power_l:
                    print("Result: DEFEAT!")
                else:
                    print("Result: DRAW!")
        
        except Exception as e:
            print(f"Error parsing DM20 response: {e}")
    
    def parse_battle_response(self, hex_data: str):
        """Parse battle response from opponent device.
        
        Args:
            hex_data: Hex string of response data (e.g., '01031200640100...')
        """
        print(f"\nParsing response data ({len(hex_data)} chars):")
        
        try:
            # Convert hex string to bytes
            data = bytes.fromhex(hex_data)
            print(f"  Raw bytes: {data.hex()}")
            
            # Parse opponent data (simplified)
            if len(data) >= 6:
                opp_stage = data[1]
                opp_power = data[2]
                opp_hp = (data[3] << 8) | data[4]
                opp_attr = data[5]
                
                attr_name = {0x01: "Vaccine", 0x02: "Data", 0x03: "Virus"}.get(opp_attr, "Unknown")
                
                print(f"\nOpponent Digimon:")
                print(f"  Stage: {opp_stage}")
                print(f"  Power: {opp_power}")
                print(f"  HP: {opp_hp}")
                print(f"  Attribute: {attr_name}")
                
                # Simple battle simulation
                print(f"\n=== Battle Simulation ===")
                print(f"Agumon (Power {self.agumon.power}) vs Opponent (Power {opp_power})")
                
                if self.agumon.power > opp_power:
                    print("Result: VICTORY!")
                elif self.agumon.power < opp_power:
                    print("Result: DEFEAT!")
                else:
                    print("Result: DRAW!")
            
        except Exception as e:
            print(f"Error parsing response: {e}")
    
    def listen_for_battle(self):
        """Listen for incoming battle packets from opponent device."""
        if not self.controller.connected:
            print("Error: No device connected!")
            return
        
        print("\n📡 Listening for incoming battle...")
        print("\n⚠️  IMPORTANT: You must initiate battle on the DM20 NOW!")
        print("\nInstructions:")
        print("  1. On your DM20 device, go to the battle menu")
        print("  2. Select 'Communication Battle' or similar option")
        print("  3. Place the DM20 close to the DCom sensors")
        print("  4. Start the battle on the DM20")
        print("\n(Using V2 listen-and-reply mode for proper handshaking)\n")
        
        # Generate our battle packets to send back
        packets = self.generate_dm20_battle_packet()
        hex_packets = [pkt.hex().upper() for pkt in packets]
        
        # Send V2 command (listen and reply) with our packets
        listen_cmd = f"V2-" + "-".join(hex_packets)
        self.controller._send_raw(listen_cmd + '\r')
        print(f"✓ DCom is now in listen-and-reply mode (V2)\n")
        print("   When DM20 sends, DCom will automatically reply with Agumon data\n")
        
        # Wait for responses - DM20 sends 10 packets of r:[4 hex chars] each
        responses = []
        status_count = 0
        start_time = time.time()
        timeout = 30.0
        last_status_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.controller.serial_port.in_waiting > 0:
                line = self.controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    # Check for status messages (t: prefix)
                    if line.startswith('t:'):
                        status_count += 1
                        # Show status every 2 seconds to avoid spam
                        if time.time() - last_status_time > 2.0:
                            status_msg = self.interpret_status_message(line)
                            print(f"{status_msg} (received {status_count} status updates)")
                            last_status_time = time.time()
                    else:
                        # Show all non-status messages
                        print(f"Received: {line}")
                    
                    # Look for both r:[4 hex] (received) and s:[4 hex] (sent) patterns
                    import re
                    r_matches = re.findall(r'r:[0-9A-Fa-f]{4}', line)
                    s_matches = re.findall(r's:[0-9A-Fa-f]{4}', line)
                    
                    if r_matches:
                        for match in r_matches:
                            hex_data = match[2:]
                            responses.append(hex_data)
                            print(f"  ← DM20 packet {len(responses)}/10: {hex_data}")
                    
                    if s_matches:
                        for match in s_matches:
                            hex_data = match[2:]
                            print(f"  → Agumon packet: {hex_data}")
                    
                    # DM20 exchanges 10 packets
                    if len(responses) >= 10:
                        break
            
            time.sleep(0.05)
        
        if responses:
            print(f"\n✅ SUCCESS! Received {len(responses)} battle packet(s)!")
            for i, resp in enumerate(responses, 1):
                print(f"  Packet {i}: {resp}")
            
            # Parse DM20 packets
            print("\nParsing opponent's battle data:")
            self.parse_dm20_battle_response(responses)
        elif status_count > 0:
            print(f"\n⚠️  Partial reception (got {len(responses)} packets, {status_count} status messages)")
            if len(responses) > 0:
                print("\n💡 We got at least one packet, but transmission was interrupted:")
                for i, resp in enumerate(responses, 1):
                    print(f"  Packet {i}: {resp}")
                print("\nThis suggests:")
                print("  • IR alignment was good initially but lost during transmission")
                print("  • Keep devices VERY close and stable during entire battle sequence")
                print("  • Try holding devices in fixed position for full 3-5 seconds")
            else:
                print(f"\n❌ No battle packets received (got {status_count} status messages)")
                print("\n💡 Troubleshooting:")
                print("  • The 't:-3' messages mean DCom is listening but not receiving DM20 signals")
                print("  • Make sure the DM20 is physically close to the DCom (within 1-2 inches)")
                print("  • Verify the DM20 is in communication battle mode")
                print("  • Check that DCom IR sensors are facing the DM20 IR port")
                print("  • Try positioning the devices at different angles")
                print("  • Some DM20 models may require button press during transmission")
        else:
            print("\n❌ Timeout - no data received")
            print("  • Check physical connections")
            print("  • Verify DM20 is attempting to communicate")
    
    def disconnect(self):
        """Disconnect from device."""
        if self.controller.connected:
            print("\nDisconnecting from device...")
            self.controller.disconnect()
            print("✓ Disconnected")
    
    def run_interactive_test(self):
        """Run interactive test menu."""
        print("=" * 50)
        print("DCom Battle Test - DM20 Protocol")
        print("Using Agumon data from DM20 monster.json")
        print("=" * 50)
        
        while True:
            print("\n=== Menu ===")
            print("1. List DCom devices")
            print("2. Connect to device")
            print("3. Send battle packets (Agumon)")
            print("4. Listen for incoming battle (no send)")
            print("5. Disconnect")
            print("6. List ALL serial ports (diagnostic)")
            print("7. Exit")
            
            choice = input("\nEnter choice (1-7): ").strip()
            
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
                self.listen_for_battle()
            
            elif choice == "5":
                self.disconnect()
            
            elif choice == "6":
                print("\n📋 All serial ports on system:")
                all_ports = self.controller.list_all_ports()
                if not all_ports:
                    print("  No serial ports found!")
                else:
                    for port, desc, vid_pid in all_ports:
                        print(f"  • {port}: {desc} ({vid_pid})")
            
            elif choice == "7":
                self.disconnect()
                print("\nExiting...")
                break
            
            else:
                print("Invalid choice!")
    
    def run_auto_test(self):
        """Run automated test (for quick testing)."""
        print("=" * 50)
        print("DCom Battle Test - Automated Mode")
        print("=" * 50)
        
        # List devices
        devices = self.list_devices()
        if not devices:
            return
        
        # Connect to first device
        if not self.connect_device(0):
            return
        
        # Wait a moment for device to be ready
        time.sleep(1)
        
        # Send battle packets
        self.send_battle_packets()
        
        # Wait before disconnecting
        time.sleep(2)
        
        # Disconnect
        self.disconnect()


def main():
    """Main entry point."""
    test = DComBattleTest()
    
    # Check command line args
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        test.run_auto_test()
    else:
        test.run_interactive_test()


if __name__ == "__main__":
    main()

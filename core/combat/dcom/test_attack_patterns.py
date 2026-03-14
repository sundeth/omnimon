"""
Test script to capture DM20 attack patterns from actual device battles.

This script runs 15 battles (taps 0-14) and logs all data so you can:
1. Film your DM20 device during each battle
2. Match the filmed attack patterns to the tap count
3. Build the definitive DM20_ATTACK_PATTERNS array

Usage:
    python test_attack_patterns.py

For each battle:
- The script will announce the tap count
- Wait for you to start the battle on your DM20
- Capture the battle packets
- Log the results

Make sure to:
- Film your DM20 screen during each battle
- Note which tap count matches which filmed battle
- Record the 4 attack animations shown (each will be 1 or 2 damage)
"""

import struct
import time
import serial
import serial.tools.list_ports


def find_dcom_device():
    """Scan for DCom device on serial ports."""
    print("\n[Scanning] Looking for DCom devices...")
    
    ports = list(serial.tools.list_ports.comports())
    arduino_ports = []
    
    for port in ports:
        # Look for Arduino or CH340 (common USB-serial chips)
        if 'Arduino' in port.description or 'CH340' in port.description or 'USB' in port.description:
            arduino_ports.append((port.device, port.description))
            print(f"  Found: {port.device} - {port.description}")
    
    if not arduino_ports:
        print("  [Error] No DCom devices found!")
        return None
    
    if len(arduino_ports) == 1:
        port = arduino_ports[0][0]
        print(f"  [Auto-selected] {port}")
        return port
    
    # Multiple devices - let user choose
    print("\n[Multiple Devices] Select a device:")
    for i, (port, desc) in enumerate(arduino_ports):
        print(f"  {i+1}. {port} - {desc}")
    
    while True:
        try:
            choice = int(input("Enter device number: ")) - 1
            if 0 <= choice < len(arduino_ports):
                return arduino_ports[choice][0]
        except (ValueError, IndexError):
            print("  Invalid selection, try again.")


def connect_to_dcom(port):
    """Connect to DCom device."""
    print(f"\n[Connecting] Opening {port}...")
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
        
        # Clear any existing data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        print("  [Connected] DCom ready!")
        return ser
    except Exception as e:
        print(f"  [Error] Failed to connect: {e}")
        return None


def get_dm20_pattern_index_from_taps(taps):
    """Convert minigame taps to pattern index."""
    return max(0, min(14, taps))


def generate_battle_packets(taps):
    """Generate DM20 packets with specific tap count."""
    # Minimal packet generation following DM20 protocol
    pattern_index = get_dm20_pattern_index_from_taps(taps)
    
    packets = []
    EOL = 0x0E  # End of line marker for DM20
    
    # Packet 1: Name 2, Name 1
    packets.append(bytes([0x54, 0x45]))  # "TE"
    
    # Packet 2: Name 4, Name 3
    packets.append(bytes([0x53, 0x54]))  # "ST"
    
    # Packet 3: Order | Attack (pattern) | Operation | Version | EOL
    # Order: 1 bit = 0 (replying)
    # Attack: 5 bits = pattern_index (0-14)
    # Operation: 2 bits = 00 (single battle)
    # Version: 4 bits = 0001 (Ver.1)
    # EOL: 4 bits = 1110 (0x0E)
    # Binary: O AAAAA OO VVVV EEEE
    order = 0
    operation = 0b00
    version = 0x1
    byte1 = (order << 7) | (pattern_index << 2) | operation
    byte2 = (version << 4) | EOL
    packets.append(bytes([byte1, byte2]))
    
    # Packet 4: COU | Index L | Attribute L | EOL
    # COU: 2 bits, Index: 8 bits, Attribute: 2 bits, EOL: 4 bits
    index = 4  # Agumon
    attribute = 0  # Vaccine
    byte1 = (0 << 6) | (index >> 2)
    byte2 = ((index & 0x03) << 6) | (attribute << 4) | EOL
    packets.append(bytes([byte1, byte2]))
    
    # Packet 5: Shot S L | Shot W L | EOL
    # Shot S: 6 bits, Shot W: 6 bits, EOL: 4 bits
    shot_s = 3
    shot_w = 3
    byte1 = (shot_s << 2) | (shot_w >> 4)
    byte2 = ((shot_w & 0x0F) << 4) | EOL
    packets.append(bytes([byte1, byte2]))
    
    # Packet 6: COU | Power L | EOL
    # COU: 4 bits, Power: 8 bits, EOL: 4 bits
    power = 18  # Agumon power
    byte1 = (0 << 4) | (power >> 4)
    byte2 = ((power & 0x0F) << 4) | EOL
    packets.append(bytes([byte1, byte2]))
    
    # Packet 7: COU | Index R | Attribute R | EOL (Right digimon, all 0 for single)
    packets.append(bytes([0x00, EOL]))
    
    # Packet 8: Shot S R | Shot W R | EOL (Right digimon, all 0 for single)
    packets.append(bytes([0x00, EOL]))
    
    # Packet 9: Tag Meter | Power R | EOL (Right digimon, all 0 for single)
    packets.append(bytes([0x00, EOL]))
    
    # Packet 10: Check | Dodges | Hits | EOL
    # Calculate checksum from all previous packets
    checksum = 0
    for pkt in packets:
        for byte_val in pkt:
            checksum += (byte_val >> 4) & 0x0F  # Upper nibble
            checksum += byte_val & 0x0F         # Lower nibble
    
    # Dodges and hits for checksum
    dodges = 0x0  # All dodge
    hits = 0xF    # All hit
    checksum += dodges
    checksum += hits
    checksum += EOL
    
    # Find check value that makes (checksum + check) % 16 == 0
    check = (16 - (checksum % 16)) % 16
    
    byte1 = (check << 4) | dodges
    byte2 = (hits << 4) | EOL
    packets.append(bytes([byte1, byte2]))
    
    return packets


def send_v2_command(ser, packets):
    """Send V2 command with packets."""
    hex_packets = [pkt.hex().upper() for pkt in packets]
    command = "V2-" + "-".join(hex_packets) + '\r'
    
    print(f"  [Sending] V2 command with {len(packets)} packets")
    ser.write(command.encode('utf-8'))


def wait_for_device_response(ser, timeout=60):
    """Wait for device to respond with battle packets."""
    print(f"  [Waiting] Start battle on your DM20 NOW! (timeout: {timeout}s)")
    
    responses = []
    start_time = time.time()
    last_update = start_time
    
    while time.time() - start_time < timeout:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            if line and not line.startswith('t:'):  # Skip status messages
                # Look for r:[hex] patterns
                if line.startswith('r:'):
                    hex_data = line[2:]
                    responses.append(hex_data)
                    print(f"    Packet {len(responses)}/10: {hex_data}")
                    
                    if len(responses) >= 10:
                        return responses
        
        # Progress indicator every 5 seconds
        current_time = time.time()
        if current_time - last_update >= 5:
            elapsed = int(current_time - start_time)
            remaining = timeout - elapsed
            print(f"    ... still waiting ({remaining}s remaining) ...")
            last_update = current_time
        
        time.sleep(0.05)
    
    print(f"  [Timeout] Only received {len(responses)}/10 packets")
    return responses if len(responses) >= 4 else None


def parse_pattern_index(packets):
    """Extract pattern_index from opponent's Packet 3."""
    if len(packets) < 3:
        return None
    
    try:
        pkt3_hex = packets[2]
        pkt3_bytes = bytes.fromhex(pkt3_hex)
        pattern_index = (pkt3_bytes[0] >> 2) & 0x1F  # Bits 2-6
        return pattern_index
    except:
        return None


def parse_hits_dodges(packets):
    """Extract hit/dodge pattern from opponent's Packet 10."""
    if len(packets) < 10:
        return None, None
    
    try:
        pkt10_hex = packets[9]
        pkt10_bytes = bytes.fromhex(pkt10_hex)
        
        # Raw values
        hits_raw = (pkt10_bytes[1] >> 4) & 0x0F
        dodges_raw = pkt10_bytes[0] & 0x0F
        
        # Inverted for single battle
        hits = hits_raw ^ 0x0F
        dodges = dodges_raw ^ 0x0F
        
        # Convert to bit arrays (right to left)
        hit_bits = [(hits >> i) & 1 for i in range(4)]
        
        return hits, hit_bits
    except:
        return None, None


def run_battle_test(ser, taps):
    """Run a single battle test with specific tap count."""
    print(f"\n{'='*70}")
    print(f"BATTLE TEST #{taps + 1} - TAPS: {taps}")
    print(f"{'='*70}")
    
    # Generate and send packets
    packets = generate_battle_packets(taps)
    send_v2_command(ser, packets)
    
    # Wait for device response
    print(f"\n[Instructions]")
    print(f"  1. Start battle on your DM20 device NOW")
    print(f"  2. Press button {taps} times during minigame")
    print(f"  3. Watch the 4 attacks carefully (FILM THIS!)")
    print(f"  4. Note if each attack is 1-hit or 2-hit damage")
    print()
    
    response_packets = wait_for_device_response(ser)
    
    if not response_packets:
        print(f"  [Failed] No response from device")
        return None
    
    # Parse data
    opponent_pattern_index = parse_pattern_index(response_packets)
    hits_value, hit_bits = parse_hits_dodges(response_packets)
    
    print(f"\n[Results]")
    print(f"  Our taps: {taps}")
    print(f"  Opponent pattern index: {opponent_pattern_index}")
    print(f"  Opponent hits (inverted): 0x{hits_value:X} = {hit_bits}")
    print(f"\n[To Record From Video]")
    print(f"  TAPS {taps} → Attack pattern: [_,_,_,_]")
    print(f"  (Fill in 1 or 2 for each of the 4 attacks you saw)")
    
    return {
        'taps': taps,
        'opponent_pattern_index': opponent_pattern_index,
        'hit_bits': hit_bits
    }


def main():
    """Main test loop."""
    print("="*70)
    print("DM20 ATTACK PATTERN CAPTURE TEST")
    print("="*70)
    print("\nThis script will run 15 battles (taps 0-14).")
    print("For each battle:")
    print("  - Press button on DM20 the specified number of times")
    print("  - FILM the 4 attack animations")
    print("  - Note if each attack does 1 or 2 damage")
    print("\nReady? Make sure your DM20 is connected and powered on!")
    input("\nPress ENTER to start...")
    
    # Find and connect to DCom
    port = find_dcom_device()
    if not port:
        return
    
    ser = connect_to_dcom(port)
    if not ser:
        return
    
    # Run tests
    results = []
    for taps in range(15):  # 0-14
        result = run_battle_test(ser, taps)
        if result:
            results.append(result)
        
        # Wait between battles
        if taps < 14:
            print(f"\n[Waiting] Preparing next battle...")
            time.sleep(3)
    
    # Summary
    print("\n" + "="*70)
    print("ALL TESTS COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("  1. Review your filmed battles")
    print("  2. For each battle, note the 4 attack values (1 or 2)")
    print("  3. Update DM20_ATTACK_PATTERNS in battle_utils.py")
    print("\nResults summary:")
    print("-"*70)
    for r in results:
        print(f"  Taps {r['taps']:2d}: Pattern index {r['opponent_pattern_index']} → [?,?,?,?] (from video)")
    print("-"*70)
    
    # Close connection
    ser.close()
    print("\n[Disconnected] Test complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Interrupted] Test cancelled by user")
    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()

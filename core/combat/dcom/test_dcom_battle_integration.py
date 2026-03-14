"""
Integration test for DCom battle communication.
Uses real DM20Device class to generate/parse packets and compare with actual DCom communication.
"""
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from core.combat.dcom.dcom_controller import DComController
from core.combat.sim.battle_simulator import DM20Device, BattleResult
from core.combat.sim.models import Digimon, DigimonStatus


class DComBattleIntegrationTest:
    """Test class that uses real battle simulator classes with DCom hardware."""
    
    def __init__(self):
        self.controller = DComController()
        
        # Create test Agumon using Digimon model
        self.agumon = Digimon(
            name="Agumon",
            order=0,
            traited=0,
            egg_shake=0,
            index=4,          # Agumon index from DM20
            hp=100,
            attribute=0,      # Vaccine
            power=18,
            handicap=0,
            buff=0,
            mini_game=5,      # Attack pattern
            level=5,
            stage=3,          # Rookie
            sick=0,
            shot1=3,
            shot2=3,
            tag_meter=2
        )
        
        # Create DM20Device instance
        self.device = DM20Device(self.agumon, protocol_def=None)
    
    def connect_to_dcom(self):
        """Find and connect to DCom device."""
        print("Scanning for DCom devices...")
        devices = self.controller.find_dcom_devices()
        
        if not devices:
            print("✗ No DCom devices found!")
            return False
        
        port, desc = devices[0]
        print(f"✓ Found: {desc} on {port}")
        
        if self.controller.connect(port):
            print("✓ Connected successfully!")
            return True
        else:
            print("✗ Connection failed!")
            return False
    
    def generate_battle_packets(self):
        """Generate all 10 DM20 packets using DM20Device class."""
        print("\n" + "=" * 70)
        print("GENERATING BATTLE PACKETS")
        print("=" * 70)
        
        # Generate packets using DM20Device methods
        EOL = 0b1110
        COU = 0b00
        VERSION = 0b00001
        
        packets = []
        packets.append(self.device.generate_packet1())
        packets.append(self.device.generate_packet2())
        packets.append(self.device.generate_packet3(order=0, version=VERSION, eol=EOL))  # Order=0 for V2 mode
        packets.append(self.device.generate_packet4(cou=COU, eol=EOL))
        packets.append(self.device.generate_packet5(eol=EOL))
        packets.append(self.device.generate_packet6(cou=COU, eol=EOL))
        packets.append(self.device.generate_packet7(cou=COU, eol=EOL))
        packets.append(self.device.generate_packet8(eol=EOL))
        packets.append(self.device.generate_packet9(eol=EOL))
        packets.append(self.device.generate_packetA(eol=EOL))  # Will need opponent data
        
        return packets
    
    def send_and_receive_battle(self):
        """Send battle packets via DCom and receive opponent's response."""
        if not self.controller.connected:
            print("✗ Not connected to DCom!")
            return None, None
        
        print(f"\nBattle setup:")
        print(f"  Name: {self.agumon.name}")
        print(f"  Index: {self.agumon.index}")
        print(f"  Power: {self.agumon.power}")
        print(f"  Attribute: {['Vaccine', 'Data', 'Virus'][self.agumon.attribute]}")
        print(f"  Shots: {self.agumon.shot1}/{self.agumon.shot2}")
        print(f"  Mini-game: {self.agumon.mini_game}")
        
        # Generate initial 9 packets (PacketA needs opponent data)
        EOL = 0b1110
        COU = 0b00
        VERSION = 0b00001
        
        initial_packets = []
        initial_packets.append(self.device.generate_packet1())
        initial_packets.append(self.device.generate_packet2())
        initial_packets.append(self.device.generate_packet3(order=0, version=VERSION, eol=EOL))
        initial_packets.append(self.device.generate_packet4(cou=COU, eol=EOL))
        initial_packets.append(self.device.generate_packet5(eol=EOL))
        initial_packets.append(self.device.generate_packet6(cou=COU, eol=EOL))
        initial_packets.append(self.device.generate_packet7(cou=COU, eol=EOL))
        initial_packets.append(self.device.generate_packet8(eol=EOL))
        initial_packets.append(self.device.generate_packet9(eol=EOL))
        
        print("\nGenerated packets 1-9:")
        for i, pkt in enumerate(initial_packets, 1):
            hex_str = pkt.hex().upper()
            print(f"  Packet {i}: {hex_str}")
        
        # Build V2 command (will generate PacketA after receiving opponent data)
        # For now, send a temporary PacketA with all-hit pattern
        temp_device = DM20Device(self.agumon, None)
        # Manually set opponent data to generate a valid PacketA
        for pkt in initial_packets:
            temp_device.opponent_data.append(pkt)
        temp_packetA = temp_device.generate_packetA(eol=EOL)
        
        all_packets = initial_packets + [temp_packetA]
        hex_packets = [pkt.hex().upper() for pkt in all_packets]
        
        print(f"\nPacket A (temporary): {temp_packetA.hex().upper()}")
        
        # Build DCom V2 command
        command = f"V2-" + "-".join(hex_packets)
        
        print(f"\nSending V2 command to DCom...")
        print(f"Command length: {len(command)} chars")
        
        self.controller._send_raw(command + '\r')
        
        # Wait for response
        print("\n📡 Waiting for opponent DM20 device...")
        print("(Place DM20 close to DCom and start battle now!)\n")
        
        received_packets = []
        sent_packets = []
        start_time = time.time()
        timeout = 30.0
        
        while time.time() - start_time < timeout:
            if self.controller.serial_port.in_waiting > 0:
                line = self.controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if line and not line.startswith('t:'):
                    print(f"Received: {line}")
                
                # Parse r: and s: packets
                import re
                r_matches = re.findall(r'r:([0-9A-Fa-f]{4})', line)
                s_matches = re.findall(r's:([0-9A-Fa-f]{4})', line)
                
                for hex_data in r_matches:
                    packet = bytes.fromhex(hex_data)
                    received_packets.append(packet)
                    print(f"  ← Opponent packet {len(received_packets)}/10: {hex_data}")
                
                for hex_data in s_matches:
                    packet = bytes.fromhex(hex_data)
                    sent_packets.append(packet)
                    print(f"  → Our packet {len(sent_packets)}/10: {hex_data}")
                
                if len(received_packets) >= 10:
                    break
            
            time.sleep(0.05)
        
        if len(received_packets) < 10:
            print(f"\n⚠️ Only received {len(received_packets)}/10 packets")
            return None, None
        
        print(f"\n✓ Received all 10 packets from opponent!")
        return sent_packets, received_packets
    
    def parse_packets_to_digimon(self, packets):
        """Parse 10 DM20 packets into a Digimon object."""
        if len(packets) < 10:
            print(f"✗ Need 10 packets, got {len(packets)}")
            return None
        
        # Parse key fields from packets
        # Packet 1-2: Name (skip for now)
        
        # Packet 3: Order, Attack, Operation, Version
        pkt3 = packets[2]
        order = (pkt3[0] >> 7) & 0x1
        attack = (pkt3[0] >> 2) & 0x1F
        operation = pkt3[0] & 0x03
        version = (pkt3[1] >> 4) & 0x0F
        
        # Packet 4: Index, Attribute
        pkt4 = packets[3]
        index = ((pkt4[0] & 0x3F) << 2) | ((pkt4[1] >> 6) & 0x03)
        attribute = (pkt4[1] >> 4) & 0x03
        
        # Packet 5: Shots
        pkt5 = packets[4]
        shot1 = (pkt5[0] >> 2) & 0x3F
        shot2 = ((pkt5[0] & 0x03) << 4) | ((pkt5[1] >> 4) & 0x0F)
        
        # Packet 6: Power
        pkt6 = packets[5]
        power = ((pkt6[0] & 0x0F) << 4) | ((pkt6[1] >> 4) & 0x0F)
        
        # Packet 9: Tag meter
        pkt9 = packets[8]
        tag_meter = (pkt9[0] >> 4) & 0x0F
        
        # Packet A: Hits, Dodges
        pktA = packets[9]
        check = (pktA[0] >> 4) & 0x0F
        dodges = pktA[0] & 0x0F
        hits = (pktA[1] >> 4) & 0x0F
        
        print("\nParsed opponent data:")
        print(f"  Order: {order}")
        print(f"  Attack pattern: {attack}")
        print(f"  Index: {index}")
        print(f"  Attribute: {['Vaccine', 'Data', 'Virus', 'Free'][attribute]}")
        print(f"  Power: {power}")
        print(f"  Shots: {shot1}/{shot2}")
        print(f"  Tag meter: {tag_meter}")
        print(f"  Hits: {bin(hits)[2:].zfill(4)}")
        print(f"  Dodges: {bin(dodges)[2:].zfill(4)}")
        print(f"  Check: {check}")
        
        # Create Digimon object
        opponent = Digimon(
            name="Opponent",
            order=order,
            traited=0,
            egg_shake=0,
            index=index,
            hp=4,  # Fixed HP for DM20
            attribute=attribute,
            power=power,
            handicap=0,
            buff=0,
            mini_game=attack,
            level=5,
            stage=0,
            sick=0,
            shot1=shot1,
            shot2=shot2,
            tag_meter=tag_meter
        )
        
        return opponent, hits, dodges
    
    def create_battle_result(self, our_packets, opponent_packets):
        """Create a BattleResult object from exchanged packets."""
        print("\n" + "=" * 70)
        print("CREATING BATTLE RESULT")
        print("=" * 70)
        
        # Parse opponent packets
        opponent, opp_hits, opp_dodges = self.parse_packets_to_digimon(opponent_packets)
        
        if not opponent:
            return None
        
        # Parse our hits/dodges from our PacketA
        our_pktA = our_packets[9]
        our_hits = (our_pktA[1] >> 4) & 0x0F
        our_dodges = our_pktA[0] & 0x0F
        
        print(f"\nOur hits pattern: {bin(our_hits)[2:].zfill(4)}")
        print(f"Our dodges pattern: {bin(our_dodges)[2:].zfill(4)}")
        
        # Get attack patterns using battle_utils
        from core.combat.sim.battle_utils import get_dm20_attack_pattern
        
        our_pattern = get_dm20_attack_pattern(self.agumon.tag_meter, self.agumon.mini_game)
        opp_pattern = get_dm20_attack_pattern(opponent.tag_meter, opponent.mini_game)
        
        print(f"\nOur attack pattern: {our_pattern}")
        print(f"Opponent attack pattern: {opp_pattern}")
        
        # Simulate battle with actual damage calculations
        our_hp = 4  # DM20 fixed HP
        opp_hp = 4
        
        battle_log = []
        
        # Extract hit bits (right to left = turn 1 to 4, then reverse for MSB->LSB)
        our_hit_list = [(our_hits >> i) & 1 for i in range(4)]
        opp_hit_list = [(opp_hits >> i) & 1 for i in range(4)]
        our_hit_list.reverse()
        opp_hit_list.reverse()
        
        print(f"\n{'='*70}")
        print("BATTLE SIMULATION")
        print(f"{'='*70}")
        print(f"{self.agumon.name} (HP: {our_hp}) vs {opponent.name} (HP: {opp_hp})")
        print(f"{'='*70}\n")
        
        # Simulate up to 6 turns (like in battle_simulator.py)
        for turn in range(6):
            if our_hp <= 0 or opp_hp <= 0:
                break
            
            # Get attack index for this turn (cycles through pattern)
            our_attack_idx = turn % len(our_pattern)
            opp_attack_idx = turn % len(opp_pattern)
            
            our_damage = our_pattern[our_attack_idx]
            opp_damage = opp_pattern[opp_attack_idx]
            
            # For first 4 turns, use hit/dodge data
            if turn < 4:
                our_hit = our_hit_list[turn]
                opp_hit = opp_hit_list[turn]
            else:
                # After turn 4, both hit (no more hit/dodge data)
                our_hit = 1
                opp_hit = 1
            
            # Apply damage
            actual_our_damage = 0
            actual_opp_damage = 0
            
            if our_hit:
                actual_our_damage = our_damage
                opp_hp -= our_damage
            
            if opp_hit:
                actual_opp_damage = opp_damage
                our_hp -= opp_damage
            
            # Clamp HP to 0
            our_hp = max(0, our_hp)
            opp_hp = max(0, opp_hp)
            
            battle_log.append({
                'turn': turn + 1,
                'attacker_attack': actual_our_damage,
                'defender_attack': actual_opp_damage,
                'attacker_hp': our_hp,
                'defender_hp': opp_hp,
                'our_hit': our_hit,
                'opp_hit': opp_hit
            })
            
            print(f"Turn {turn + 1}:")
            print(f"  {self.agumon.name}: {'HIT' if our_hit else 'MISS':4s} → Damage: {actual_our_damage}, HP remaining: {our_hp}")
            print(f"  {opponent.name}: {'HIT' if opp_hit else 'MISS':4s} → Damage: {actual_opp_damage}, HP remaining: {opp_hp}")
            
            if our_hp <= 0 or opp_hp <= 0:
                break
        
        # Determine winner
        if our_hp > opp_hp:
            winner = "device1"
        elif opp_hp > our_hp:
            winner = "device2"
        else:
            winner = "draw"
        
        print(f"\n{'='*70}")
        print(f"🏆 BATTLE RESULT: {winner.upper()}")
        print(f"{'='*70}")
        print(f"Final HP: {self.agumon.name} = {our_hp}, {opponent.name} = {opp_hp}")
        
        # Create BattleResult object
        result = BattleResult(
            winner=winner,
            device1_final=[DigimonStatus(name=self.agumon.name, hp=our_hp, alive=our_hp > 0)],
            device2_final=[DigimonStatus(name=opponent.name, hp=opp_hp, alive=opp_hp > 0)],
            battle_log=battle_log,
            device1_packets=our_packets,
            device2_packets=opponent_packets
        )
        
        return result
    
    def print_battle_result(self, result):
        """Print battle result in same format as battle_simulator.py"""
        if not result:
            return
        
        print("\n" + "=" * 70)
        print("BATTLE RESULT SUMMARY (matching battle_simulator.py format)")
        print("=" * 70)
        
        print(f"\nWinner: {result.winner}")
        
        print("\nDevice 1 (Us):")
        for status in result.device1_final:
            print(f"  {status.name}: HP={status.hp}, Alive={status.alive}")
        
        print("\nDevice 2 (Opponent):")
        for status in result.device2_final:
            print(f"  {status.name}: HP={status.hp}, Alive={status.alive}")
        
        # Print battle log in simulator format
        print("\nBattle Log:")
        for log_entry in result.battle_log:
            turn = log_entry['turn']
            our_dmg = log_entry.get('attacker_attack', 0)
            opp_dmg = log_entry.get('defender_attack', 0)
            our_hp = log_entry['attacker_hp']
            opp_hp = log_entry['defender_hp']
            our_hit = log_entry.get('our_hit', 1)
            opp_hit = log_entry.get('opp_hit', 1)
            
            print(f"  Turn {turn}:")
            print(f"    Device 1: {'HIT' if our_hit else 'MISS'} - Dealt {our_dmg} damage, HP: {our_hp}")
            print(f"    Device 2: {'HIT' if opp_hit else 'MISS'} - Dealt {opp_dmg} damage, HP: {opp_hp}")
        
        print("\nExchanged Packet Data:")
        print("\nDevice 1 Packets (Our):")
        for i, packet in enumerate(result.device1_packets, 1):
            hex_str = ' '.join(f'{b:02X}' for b in packet)
            bin_str = ' '.join(f'{b:08b}' for b in packet)
            print(f"  Packet {i:2d}: {hex_str:8s} ({bin_str})")
        
        print("\nDevice 2 Packets (Opponent):")
        for i, packet in enumerate(result.device2_packets, 1):
            hex_str = ' '.join(f'{b:02X}' for b in packet)
            bin_str = ' '.join(f'{b:08b}' for b in packet)
            print(f"  Packet {i:2d}: {hex_str:8s} ({bin_str})")
        
        # Generate DCom code format
        dcom_parts = []
        for i in range(10):
            dcom_parts.append(f"r:{result.device2_packets[i].hex().upper()}")
            dcom_parts.append(f"s:{result.device1_packets[i].hex().upper()}")
        dcom_parts.append("t")
        dcom_code = ' '.join(dcom_parts)
        
        print(f"\nDCom Code: {dcom_code}")
        
        # Validate checksum for both devices
        print("\n" + "=" * 70)
        print("CHECKSUM VALIDATION")
        print("=" * 70)
        
        for device_name, packets in [("Device 1 (Our)", result.device1_packets), 
                                      ("Device 2 (Opponent)", result.device2_packets)]:
            checksum = 0
            for pkt in packets:
                for byte in pkt:
                    checksum += (byte >> 4) & 0xF
                    checksum += byte & 0xF
            
            valid = (checksum % 16) == 0
            status = "✓ VALID" if valid else "✗ INVALID"
            print(f"{device_name:20s}: checksum={checksum:3d}, mod 16={checksum % 16:2d} {status}")
        
        print("\n" + "=" * 70)
        print("INTEGRATION TEST COMPLETE")
        print("=" * 70)
    
    def run_test(self):
        """Run the complete integration test."""
        print("=" * 70)
        print("DCOM BATTLE INTEGRATION TEST")
        print("Tests real DCom communication with battle simulator classes")
        print("=" * 70)
        
        # Connect to DCom
        if not self.connect_to_dcom():
            return
        
        try:
            # Send and receive battle
            our_packets, opponent_packets = self.send_and_receive_battle()
            
            if not our_packets or not opponent_packets:
                print("\n✗ Battle communication failed")
                return
            
            # Create and print battle result
            result = self.create_battle_result(our_packets, opponent_packets)
            
            if result:
                self.print_battle_result(result)
            
        finally:
            # Disconnect
            if self.controller.connected:
                print("\nDisconnecting...")
                self.controller.disconnect()
                print("✓ Disconnected")


def main():
    """Main entry point."""
    test = DComBattleIntegrationTest()
    test.run_test()


if __name__ == "__main__":
    main()

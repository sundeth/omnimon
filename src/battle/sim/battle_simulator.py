import struct
import random
import os
import sys

# Add project root to path for imports when running directly
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

try:
    from battle_utils import get_attack_pattern
    from battle_utils import get_dm20_attack_pattern, get_dm20_single_battle_attack_pattern
    from models import *
    import protocol_constants
except ImportError:
    # Absolute imports for direct testing
    from battle.sim.battle_utils import get_attack_pattern
    from battle.sim.battle_utils import get_dm20_attack_pattern, get_dm20_single_battle_attack_pattern
    from battle.sim.models import *
    from battle.sim import protocol_constants


class BattleSimulator:
    """Packet-accurate simulator for the real device protocols.

    Protocol constants and documented packet layouts live in
    ``protocol_constants``; the DCom exchange path is the tested reference.
    """

    # BattleProtocol enum -> constants class in protocol_constants
    PROTOCOL_CONSTANTS = {
        BattleProtocol.DM_BS: protocol_constants.DM,
        BattleProtocol.DMC_BS: protocol_constants.DMC,
        BattleProtocol.DM20_BS: protocol_constants.DM20,
        BattleProtocol.DMX_BS: protocol_constants.DMX,
        BattleProtocol.PEN20_BS: protocol_constants.PEN20,
    }

    def __init__(self, protocol: BattleProtocol, verbose: bool = False):
        """
        Initialize BattleSimulator with protocol.

        Args:
            protocol: BattleProtocol enum value
            verbose: Print packet dumps and battle logs to stdout (debug/tests)
        """
        self.protocol = protocol
        self.constants = self.PROTOCOL_CONSTANTS.get(protocol, protocol_constants.DM20)
        self.protocol_name = self.constants.NAME
        self.verbose = verbose

    def simulate(self, device1: Digimon, device2: Digimon) -> BattleResult:
        """
        Simulate a battle using the protocol's packet exchange.
        """
        if self.verbose:
            print(f"[BattleSimulator] Using protocol: {self.constants.DISPLAY_NAME}")

        if self.protocol == BattleProtocol.DM_BS:
            result = self._simulate_dm_bs(device1, device2)
        elif self.protocol == BattleProtocol.DMC_BS:
            result = self._simulate_dmc_bs(device1, device2)
        elif self.protocol == BattleProtocol.DM20_BS:
            result = self._simulate_dm20_bs(device1, device2)
        elif self.protocol == BattleProtocol.DMX_BS:
            result = self._simulate_dmx_bs(device1, device2)
        elif self.protocol == BattleProtocol.PEN20_BS:
            result = self._simulate_pen20_bs(device1, device2)
        else:
            raise NotImplementedError("Protocol not implemented")

        if self.verbose:
            self.print_battle_log(result)
            self.print_dcom_code(result)
        return result
    
    def print_battle_log(self, result):
        # Generate a detailed battle log
        print(f"Winner: {result.winner}")

        # Print final states of both devices
        print("Device 1:")
        for i, status in enumerate(result.device1_final):
            print(f"  {i}: {status.name} (HP: {status.hp}, Alive: {status.alive})")
        print("Device 2:")
        for i, status in enumerate(result.device2_final):
            print(f"  {i}: {status.name} (HP: {status.hp}, Alive: {status.alive})")
        print()

        # Iterate through the battle log
        for turn_data in result.battle_log:
            print(f"Turn {turn_data.turn}")

            # Device 1 attacks
            print(" Device 1 attacks:")
            for attack in turn_data.attacks:
                if attack.device == "device1":
                    attacker_name = result.device1_final[attack.attacker].name
                    defender_name = result.device2_final[attack.defender].name if attack.defender >= 0 else "?"
                    print(f"   {attacker_name} -> {defender_name}: hit={attack.hit} dmg={attack.damage} crit={attack.critical}")

            # Device 2 attacks
            print(" Device 2 attacks:")
            for attack in turn_data.attacks:
                if attack.device == "device2":
                    attacker_name = result.device2_final[attack.attacker].name
                    defender_name = result.device1_final[attack.defender].name if attack.defender >= 0 else "?"
                    print(f"   {attacker_name} -> {defender_name}: hit={attack.hit} dmg={attack.damage} crit={attack.critical}")

            # Print status of both devices
            device1_status = [f"{status.name}({status.hp})" for status in turn_data.device1_status]
            device2_status = [f"{status.name}({status.hp})" for status in turn_data.device2_status]
            print(f" Device 1 status: {device1_status}")
            print(f" Device 2 status: {device2_status}")
            print()

        # Print exchanged packet data
        print("Exchanged Packet Data:")
        print("Device 1 Packets:")
        for i, packet in enumerate(result.device1_packets):
            self._print_packet(i, packet)

        print("Device 2 Packets:")
        for i, packet in enumerate(result.device2_packets):
            self._print_packet(i, packet)

    def _print_packet(self, index, packet):
        """
        Helper method to print a single packet in binary and hexadecimal formats.
        Handles different packet formats (bytes, list of bytes, etc.).
        """
        if isinstance(packet, bytes):
            # Process raw bytes
            binary = " ".join(f"{byte:08b}" for byte in packet)
            hex_representation = " ".join(f"{byte:02X}" for byte in packet)
            print(f"  Packet {index + 1}:")
            print(f"    Binary: {binary}")
            print(f"    Hex: {hex_representation}")
        elif isinstance(packet, list):
            # Concatenate list of bytes into a single bytes object
            concatenated = b"".join(packet)
            binary = " ".join(f"{byte:08b}" for byte in concatenated)
            hex_representation = " ".join(f"{byte:02X}" for byte in concatenated)
            print(f"  Packet {index + 1}:")
            print(f"    Binary: {binary}")
            print(f"    Hex: {hex_representation}")
        else:
            # Handle invalid packet types
            print(f"  Packet {index + 1}: Invalid packet type: {type(packet)}")

    def print_dcom_code(self, result: BattleResult):
        """
        Prints the battle packets in DCom validator format:
        r:XXXX s:XXXX r:XXXX s:XXXX ... t
        
        Alternates between device1 (r:) and device2 (s:) packets.
        """
        parts = []
        
        # Determine the maximum number of packets
        max_packets = max(len(result.device1_packets), len(result.device2_packets))
        
        for i in range(max_packets):
            # Add device1 packet (r:)
            if i < len(result.device1_packets):
                packet = result.device1_packets[i]
                if isinstance(packet, bytes):
                    hex_str = packet.hex().upper()
                elif isinstance(packet, list):
                    hex_str = b"".join(packet).hex().upper()
                else:
                    hex_str = "0000"
                parts.append(f"r:{hex_str}")
            
            # Add device2 packet (s:)
            if i < len(result.device2_packets):
                packet = result.device2_packets[i]
                if isinstance(packet, bytes):
                    hex_str = packet.hex().upper()
                elif isinstance(packet, list):
                    hex_str = b"".join(packet).hex().upper()
                else:
                    hex_str = "0000"
                parts.append(f"s:{hex_str}")
        
        # Join all parts and add terminator
        dcom_code = " ".join(parts) + " t"
        print(f"\n[DCom Validator Format]")
        print(dcom_code)
        print()

    def _get_dm_slot_from_power(self, power: int) -> tuple:
        """
        Map power level to DM slot (A-L).
        Based on original Digital Monster slot system.
        
        Returns:
            Tuple of (slot_letter, slot_index) where slot_index is 0-11 (A=0, L=11)
        """
        # Power to slot mapping based on documentation
        if power <= 10:
            return ('A', 0)
        elif power <= 15:
            return ('B', 1)
        elif power <= 20:
            return ('C', 2)
        elif power <= 25:
            return ('D', 3)
        elif power <= 30:
            return ('E', 4)
        elif power <= 35:
            return ('F', 5)
        elif power <= 40:
            return ('G', 6)
        elif power <= 45:
            return ('H', 7)
        elif power <= 50:
            return ('I', 8)
        elif power <= 55:
            return ('J', 9)
        elif power <= 59:
            return ('K', 10)
        else:  # 60+
            return ('L', 11)

    def _get_dm_win_probability(self, my_slot_index: int, opponent_slot_index: int, my_boost: int = 0, opponent_boost: int = 0) -> int:
        """
        Get win probability out of 16 for DM slot matchup.
        Based on original Digital Monster matchup table.
        
        Args:
            my_slot_index: My slot index (0-11 for A-L)
            opponent_slot_index: Opponent slot index (0-11 for A-L)
            my_boost: My boost value (0-4)
            opponent_boost: Opponent boost value (0-4)
            
        Returns:
            Win probability out of 16
        """
        # DM matchup table: chance out of 16 to win
        # Rows are my slot (A-L), columns are opponent slot (A-L)
        matchup_table = [
            # A   B   C   D   E   F   G   H   I   J   K   L
            [ 8,  8,  2,  3,  2,  3,  2,  3,  7,  1,  1,  1],  # A
            [ 8,  8,  2,  3,  2,  3,  2,  3,  7,  1,  1,  1],  # B
            [15, 15,  8, 11,  9, 11,  7, 11, 13,  3,  3,  3],  # C
            [13, 13,  5,  8,  5,  9,  5,  7, 11,  2,  2,  2],  # D
            [15, 15,  7, 11,  8, 11,  9, 11, 13,  3,  3,  3],  # E
            [13, 13,  5,  7,  5,  8,  5,  9, 11,  2,  2,  2],  # F
            [15, 15,  9, 11,  7, 11,  8, 11, 13,  3,  3,  3],  # G
            [13, 13,  5,  9,  5,  7,  5,  8, 11,  2,  2,  2],  # H
            [ 9,  9,  3,  5,  3,  5,  3,  5,  8,  1,  1,  1],  # I
            [15, 15, 13, 14, 13, 14, 13, 14, 15,  8,  5,  5],  # J
            [15, 15, 13, 14, 13, 14, 13, 14, 15, 11,  8,  5],  # K
            [15, 15, 13, 14, 13, 14, 13, 14, 15, 11, 11,  8],  # L
        ]
        
        base_probability = matchup_table[my_slot_index][opponent_slot_index]
        
        # Apply boost advantage (each boost level adds to chance, capped at 15)
        boost_diff = my_boost - opponent_boost
        adjusted_probability = min(15, max(1, base_probability + boost_diff))
        
        return adjusted_probability

    def _simulate_dm_bs(self, attacker: Digimon, defender: Digimon) -> BattleResult:
        """
        Simulates a battle using the original Digital Monster (DM) protocol.
        Uses slot-based system where winner is determined by slot matchup table.
        
        DM Protocol:
        - 2 packets (Digimon Data + Battle Result)
        - Fixed 5 HP
        - Winner determined by slot matchup with boost modifier
        - Attack pattern: Winner 1,1,1,2 / Loser 1,1,1,1
        - 4 turns, all attacks hit
        """
        import random
        
        # Get slots from power
        attacker_slot, attacker_slot_idx = self._get_dm_slot_from_power(attacker.power)
        defender_slot, defender_slot_idx = self._get_dm_slot_from_power(defender.power)
        
        if self.verbose:
            print(f"[DM] {attacker.name} slot: {attacker_slot} (power {attacker.power})")
        if self.verbose:
            print(f"[DM] {defender.name} slot: {defender_slot} (power {defender.power})")
        
        # Calculate win probability for attacker
        # In DM, boost comes from pills (0-4), here we'll use effort/16 as proxy
        attacker_boost = min(4, attacker.mini_game)
        defender_boost = min(4, defender.mini_game)
        
        win_probability = self._get_dm_win_probability(
            attacker_slot_idx, defender_slot_idx, 
            attacker_boost, defender_boost
        )
        
        if self.verbose:
            print(f"[DM] Attacker win probability: {win_probability}/16")
        
        # Roll for outcome
        roll = random.randint(1, 16)
        attacker_wins = roll <= win_probability
        
        if self.verbose:
            print(f"[DM] Roll: {roll}, Attacker wins: {attacker_wins}")
        
        # Generate packets (DM format)
        device1_packets = []
        device2_packets = []
        
        # Packet 1: Boost(4) | Slot(4) with mirrored values
        def make_dm_packet1(boost, slot_hex):
            boost_mirror = (~boost) & 0x0F
            slot_mirror = (~slot_hex) & 0x0F
            byte0 = (boost_mirror << 4) | slot_mirror
            byte1 = (boost << 4) | slot_hex
            return struct.pack(">BB", byte0, byte1)
        
        attacker_slot_hex = 0x3 + attacker_slot_idx  # A=0x3, L=0xE
        defender_slot_hex = 0x3 + defender_slot_idx
        
        device1_packets.append(make_dm_packet1(attacker_boost, attacker_slot_hex))
        device2_packets.append(make_dm_packet1(defender_boost, defender_slot_hex))
        
        # Packet 2: Version(4) | Outcome(4) with mirrored values
        def make_dm_packet2(version, outcome):
            version_mirror = (~version) & 0x0F
            outcome_mirror = (~outcome) & 0x0F
            byte0 = (version_mirror << 4) | outcome_mirror
            byte1 = (version << 4) | outcome
            return struct.pack(">BB", byte0, byte1)
        
        version = 1
        device1_packets.append(make_dm_packet2(version, 1 if attacker_wins else 2))
        device2_packets.append(make_dm_packet2(version, 2 if attacker_wins else 1))
        
        # Battle simulation with fixed HP and patterns
        attacker_hp = 5  # DM fixed HP
        defender_hp = 5
        battle_log = []
        
        # Attack patterns: Winner 1,1,1,2 / Loser 1,1,1,1
        winner_pattern = [1, 1, 1, 2]
        loser_pattern = [1, 1, 1, 1]
        
        if attacker_wins:
            attacker_pattern = winner_pattern
            defender_pattern = loser_pattern
        else:
            attacker_pattern = loser_pattern
            defender_pattern = winner_pattern
        
        # 4 turns, all attacks hit
        for turn in range(4):
            # Attacker attacks
            attacker_damage = attacker_pattern[turn]
            defender_hp = max(0, defender_hp - attacker_damage)
            
            # Defender attacks
            defender_damage = defender_pattern[turn]
            attacker_hp = max(0, attacker_hp - defender_damage)
            
            turn_log = TurnLog(
                turn=turn + 1,
                device1_status=[
                    DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
                ],
                device2_status=[
                    DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
                ],
                attacks=[
                    AttackLog(
                        turn=turn + 1,
                        device="device1",
                        attacker=0,
                        defender=0,
                        hit=True,
                        damage=attacker_damage,
                        critical=(attacker_damage == 5),
                    ),
                    AttackLog(
                        turn=turn + 1,
                        device="device2",
                        attacker=0,
                        defender=0,
                        hit=True,
                        damage=defender_damage,
                        critical=(defender_damage == 5),
                    )
                ]
            )
            battle_log.append(turn_log)

        winner = "device1" if attacker_wins else "device2"
        
        result = BattleResult(
            winner=winner,
            device1_final=[
                DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
            ],
            device2_final=[
                DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
            ],
            battle_log=battle_log,
            device1_packets=device1_packets,
            device2_packets=device2_packets
        )
        
        return result

    def _simulate_dmc_bs(self, attacker: Digimon, defender: Digimon) -> BattleResult:
        """
        Simulates a battle using the DMC protocol.
        Uses protocol definition from JSON for constants and configuration.
        """
        # Get protocol constants
        turns = protocol_constants.DMC.TURNS

        dev_att = DMCDevice(attacker)
        dev_def = DMCDevice(defender)

        # Initialize packet storage
        device1_packets = []
        device2_packets = []

        # Step 1: Device 1 sends Packet 1 (operation 0)
        att_packet1 = dev_att.generate_packet1(operation=0)
        dev_def.process_packet(att_packet1)
        device1_packets.append(att_packet1)

        # Step 2: Device 2 responds with Packet 1 (operation 1)
        def_packet1 = dev_def.generate_packet1(operation=1)
        dev_att.process_packet(def_packet1)
        device2_packets.append(def_packet1)

        # Step 3: Calculate the outcome
        outcome_device1 = dev_att.calculate_outcome(dev_def)
        outcome_device2 = 1 - outcome_device1  # Opposite outcome

        # Step 4: Device 1 sends Packet 2 (operation 2)
        att_packet2 = dev_att.generate_packet2(operation=2, outcome=outcome_device1)
        dev_def.process_packet(att_packet2)
        device1_packets.append(att_packet2)

        # Step 5: Device 2 responds with Packet 2 (operation 3)
        def_packet2 = dev_def.generate_packet2(operation=3, outcome=outcome_device2)
        dev_att.process_packet(def_packet2)
        device2_packets.append(def_packet2)

        # Step 6: Simulate the battle using attack patterns
        attacker_hp = dev_att.hp
        defender_hp = dev_def.hp
        battle_log = []

        # Determine winner and loser
        if outcome_device1 == 1:
            winner_device = dev_att
            loser_device = dev_def
            winner_pattern = get_attack_pattern(attacker.level, attacker.mini_game, protocol="DMC_WINNER")
            loser_pattern = get_attack_pattern(defender.level, defender.mini_game, protocol="DMC_LOOSER")
            winner_name = attacker.name
            loser_name = defender.name
        else:
            winner_device = dev_def
            loser_device = dev_att
            winner_pattern = get_attack_pattern(defender.level, defender.mini_game, protocol="DMC_WINNER")
            loser_pattern = get_attack_pattern(attacker.level, attacker.mini_game, protocol="DMC_LOOSER")
            winner_name = defender.name
            loser_name = attacker.name

        # Simulate battle turns using protocol definition
        for turn in range(turns):
            # Winner attacks
            winner_damage = winner_pattern[turn]
            loser_hp = max(0, loser_device.hp - winner_damage)
            loser_device.hp = loser_hp

            # Loser attacks
            loser_damage = loser_pattern[turn]
            winner_hp = max(0, winner_device.hp - loser_damage)
            winner_device.hp = winner_hp

            # Log the turn
            turn_log = TurnLog(
                turn=turn + 1,
                device1_status=[
                    DigimonStatus(name=attacker.name, hp=dev_att.hp, alive=dev_att.hp > 0)
                ],
                device2_status=[
                    DigimonStatus(name=defender.name, hp=dev_def.hp, alive=dev_def.hp > 0)
                ],
                attacks=[
                    AttackLog(
                        turn=turn + 1,
                        device="device1" if winner_device == dev_att else "device2",
                        attacker=0,
                        defender=0,
                        hit=True,
                        damage=winner_damage,
                        critical=(winner_damage == 5),
                    ),
                    AttackLog(
                        turn=turn + 1,
                        device="device1" if loser_device == dev_att else "device2",
                        attacker=0,
                        defender=0,
                        hit=True,
                        damage=loser_damage,
                        critical=(loser_damage == 5),
                    )
                ]
            )
            battle_log.append(turn_log)

        # Step 7: Determine the winner
        winner = "device1" if outcome_device1 == 1 else "device2"

        # Step 8: Prepare the final result
        result = BattleResult(
            winner=winner,
            device1_final=[
                DigimonStatus(name=attacker.name, hp=dev_att.hp, alive=dev_att.hp > 0)
            ],
            device2_final=[
                DigimonStatus(name=defender.name, hp=dev_def.hp, alive=dev_def.hp > 0)
            ],
            battle_log=battle_log,
            device1_packets=device1_packets,
            device2_packets=device2_packets
        )

        return result

    def _simulate_dm20_bs(self, attacker: Digimon, defender: Digimon) -> BattleResult:
        """
        Simulates a battle using the Digital Monster Ver.20th protocol.
        Uses protocol definition from JSON for constants and configuration.
        """
        # Get protocol constants
        EOL = protocol_constants.DM20.EOL
        VERSION = protocol_constants.DM20.DEFAULT_VERSION
        # 5 HP — the DCom-tested value (the old JSON said 4, which was wrong)
        fixed_hp = protocol_constants.DM20.FIXED_HP
        
        device1 = DM20Device(attacker)
        device2 = DM20Device(defender)

        # Constants
        COU = 0b00    # Constant Or Unknown

        # Generate and exchange packets
        packets_device1 = []
        packets_device2 = []

        # Packet exchanges (1 to 9)
        packet1_device1 = device1.generate_packet1()
        packet1_device2 = device2.generate_packet1()
        device2.process_packet(packet1_device1)
        device1.process_packet(packet1_device2)
        packets_device1.append(packet1_device1)
        packets_device2.append(packet1_device2)

        packet2_device1 = device1.generate_packet2()
        packet2_device2 = device2.generate_packet2()
        device2.process_packet(packet2_device1)
        device1.process_packet(packet2_device2)
        packets_device1.append(packet2_device1)
        packets_device2.append(packet2_device2)

        packet3_device1 = device1.generate_packet3(order=1, version=VERSION, eol=EOL)
        packet3_device2 = device2.generate_packet3(order=0, version=VERSION, eol=EOL)
        device2.process_packet(packet3_device1)
        device1.process_packet(packet3_device2)
        packets_device1.append(packet3_device1)
        packets_device2.append(packet3_device2)

        packet4_device1 = device1.generate_packet4(cou=COU, eol=EOL)
        packet4_device2 = device2.generate_packet4(cou=COU, eol=EOL)
        device2.process_packet(packet4_device1)
        device1.process_packet(packet4_device2)
        packets_device1.append(packet4_device1)
        packets_device2.append(packet4_device2)

        packet5_device1 = device1.generate_packet5(eol=EOL)
        packet5_device2 = device2.generate_packet5(eol=EOL)
        device2.process_packet(packet5_device1)
        device1.process_packet(packet5_device2)
        packets_device1.append(packet5_device1)
        packets_device2.append(packet5_device2)

        packet6_device1 = device1.generate_packet6(cou=COU, eol=EOL)
        packet6_device2 = device2.generate_packet6(cou=COU, eol=EOL)
        device2.process_packet(packet6_device1)
        device1.process_packet(packet6_device2)
        packets_device1.append(packet6_device1)
        packets_device2.append(packet6_device2)

        packet7_device1 = device1.generate_packet7(cou=COU, eol=EOL)
        packet7_device2 = device2.generate_packet7(cou=COU, eol=EOL)
        device2.process_packet(packet7_device1)
        device1.process_packet(packet7_device2)
        packets_device1.append(packet7_device1)
        packets_device2.append(packet7_device2)

        packet8_device1 = device1.generate_packet8(eol=EOL)
        packet8_device2 = device2.generate_packet8(eol=EOL)
        device2.process_packet(packet8_device1)
        device1.process_packet(packet8_device2)
        packets_device1.append(packet8_device1)
        packets_device2.append(packet8_device2)

        packet9_device1 = device1.generate_packet9(eol=EOL)
        packet9_device2 = device2.generate_packet9(eol=EOL)
        device2.process_packet(packet9_device1)
        device1.process_packet(packet9_device2)
        packets_device1.append(packet9_device1)
        packets_device2.append(packet9_device2)

        # Packet A: Check, Dodges, Hits, EOL
        packetA_device1 = device1.generate_packetA(eol=EOL)
        packetA_device2 = device2.generate_packetA(eol=EOL)
        device2.process_packet(packetA_device1)
        device1.process_packet(packetA_device2)
        packets_device1.append(packetA_device1)
        packets_device2.append(packetA_device2)

        # Simulate the battle with fixed HP from protocol
        # DM20 uses 5 HP (not 4 as previously thought)
        attacker_hp = 5  # DM20 fixed HP
        defender_hp = 5  # DM20 fixed HP
        battle_log = []

        # Retrieve attack patterns using DM20 single battle pattern table
        # Pattern index comes from minigame taps (stored in mini_game field)
        attack_pattern_device1 = get_dm20_single_battle_attack_pattern(device1.digimon.mini_game)
        attack_pattern_device2 = get_dm20_single_battle_attack_pattern(device2.digimon.mini_game)

        # Extract hits for both devices from Packet A
        # Packet A format: [Check(4)|Dodges(4), Hits(4)|EOL(4)]
        # Byte 0: CCCC DDDD (Check | Dodges)
        # Byte 1: HHHH EEEE (Hits | EOL)
        # Hits nibble: bit0 = turn 1, bit1 = turn 2, etc (read right to left)
        # Each device's Hits field = which of their attacks HIT the opponent
        device1_hits_nibble = (packetA_device1[1] >> 4) & 0x0F
        device2_hits_nibble = (packetA_device2[1] >> 4) & 0x0F
        
        # Extract individual hit bits (bit 0 = turn 1, bit 1 = turn 2, etc)
        device1_hits = [(device1_hits_nibble >> i) & 1 for i in range(4)]
        device2_hits = [(device2_hits_nibble >> i) & 1 for i in range(4)]

        # DM20 has 5 turns (attacks) but only tracks 4 hits in Packet A
        # Turn 5 uses turn 1's pattern value and turn 1's hit result
        # Both devices attack each turn simultaneously
        for turn in range(5):
            # Attack pattern index (0-3 for turns 1-4, wraps to 0 for turn 5)
            attack_index = turn % 4
            
            # Hit index for Packet A lookup (0-3, turn 5 uses turn 1's hit)
            hit_index = turn if turn < 4 else 0

            # Device 1 attacks Device 2
            device1_attack = attack_pattern_device1[attack_index]
            device1_hit = device1_hits[hit_index]
            defender_damage = device1_attack if device1_hit else 0
            defender_hp = max(0, defender_hp - defender_damage)

            # Device 2 attacks Device 1
            device2_attack = attack_pattern_device2[attack_index]
            device2_hit = device2_hits[hit_index]
            attacker_damage = device2_attack if device2_hit else 0
            attacker_hp = max(0, attacker_hp - attacker_damage)

            # Log the turn
            # IMPORTANT: Store the ATTACK PATTERN VALUE (what attack was attempted), not dealt damage
            # The battle scene needs to know the attack type (1=weak, 2=strong) even on misses
            # The 'hit' field indicates whether the attack connected
            turn_log = TurnLog(
                turn=turn + 1,
                device1_status=[
                    DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
                ],
                device2_status=[
                    DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
                ],
                attacks=[
                    AttackLog(
                        turn=turn + 1,
                        device="device1",
                        attacker=0,
                        defender=0,
                        hit=bool(device1_hit),
                        damage=device1_attack,  # Pattern value, not dealt damage
                        critical=(device1_attack == 5),
                    ),
                    AttackLog(
                        turn=turn + 1,
                        device="device2",
                        attacker=0,
                        defender=0,
                        hit=bool(device2_hit),
                        damage=device2_attack,  # Pattern value, not dealt damage
                        critical=(device2_attack == 5),
                    )
                ]
            )
            battle_log.append(turn_log)

            # End battle if both Digimon are defeated
            if attacker_hp == 0 and defender_hp == 0:
                # Device 1 attacks first, so it wins in case of a tie
                winner = "device1"
                break

            # End battle if one Digimon is defeated
            if attacker_hp == 0:
                winner = "device2"
                break
            elif defender_hp == 0:
                winner = "device1"
                break
        else:
            # If both are alive after 5 turns, winner is the one with highest HP
            if attacker_hp > defender_hp:
                winner = "device1"
            elif defender_hp > attacker_hp:
                winner = "device2"
            else:
                winner = "draw"

        # Prepare the final result
        result = BattleResult(
            winner=winner,
            device1_final=[
                DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
            ],
            device2_final=[
                DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
            ],
            battle_log=battle_log,
            device1_packets=packets_device1,
            device2_packets=packets_device2
        )

        return result
    
    def _simulate_pen20_bs(self, attacker: Digimon, defender: Digimon) -> BattleResult:
        """
        Simulates a battle using the Pendulum 20th protocol.
        Uses protocol definition from JSON for constants and configuration.
        
        PEN20 is similar to DM20:
        - Fixed 5 HP
        - 5 turns (turn 5 uses turn 1's pattern and hit)
        - Uses Dummy minigame (0-14 taps)
        - Traited and egg_shake provide power bonuses
        """
        # Get protocol constants
        EOL = protocol_constants.PEN20.EOL
        VERSION = protocol_constants.PEN20.DEFAULT_VERSION
        fixed_hp = protocol_constants.PEN20.FIXED_HP  # 5 HP like DM20
        
        device1 = PEN20Device(attacker)
        device2 = PEN20Device(defender)

        # Constants
        COU = 0b00    # Constant Or Unknown

        # Generate and exchange packets
        packets_device1 = []
        packets_device2 = []

        # Packet exchanges (1 to 9)
        packet1_device1 = device1.generate_packet1(order=0, version=VERSION, eol=EOL)
        packet1_device2 = device2.generate_packet1(order=1, version=VERSION, eol=EOL)
        device2.process_packet(packet1_device1)
        device1.process_packet(packet1_device2)
        packets_device1.append(packet1_device1)
        packets_device2.append(packet1_device2)

        packet2_device1 = device1.generate_packet2(cou=COU, eol=EOL)
        packet2_device2 = device2.generate_packet2(cou=COU, eol=EOL)
        device2.process_packet(packet2_device1)
        device1.process_packet(packet2_device2)
        packets_device1.append(packet2_device1)
        packets_device2.append(packet2_device2)

        packet3_device1 = device1.generate_packet3(cou=COU, eol=EOL)
        packet3_device2 = device2.generate_packet3(cou=COU, eol=EOL)
        device2.process_packet(packet3_device1)
        device1.process_packet(packet3_device2)
        packets_device1.append(packet3_device1)
        packets_device2.append(packet3_device2)

        packet4_device1 = device1.generate_packet4(cou=COU, eol=EOL)
        packet4_device2 = device2.generate_packet4(cou=COU, eol=EOL)
        device2.process_packet(packet4_device1)
        device1.process_packet(packet4_device2)
        packets_device1.append(packet4_device1)
        packets_device2.append(packet4_device2)

        packet5_device1 = device1.generate_packet5(cou=COU, eol=EOL)
        packet5_device2 = device2.generate_packet5(cou=COU, eol=EOL)
        device2.process_packet(packet5_device1)
        device1.process_packet(packet5_device2)
        packets_device1.append(packet5_device1)
        packets_device2.append(packet5_device2)

        packet6_device1 = device1.generate_packet6(eol=EOL)
        packet6_device2 = device2.generate_packet6(eol=EOL)
        device2.process_packet(packet6_device1)
        device1.process_packet(packet6_device2)
        packets_device1.append(packet6_device1)
        packets_device2.append(packet6_device2)

        packet7_device1 = device1.generate_packet7(cou=COU, eol=EOL)
        packet7_device2 = device2.generate_packet7(cou=COU, eol=EOL)
        device2.process_packet(packet7_device1)
        device1.process_packet(packet7_device2)
        packets_device1.append(packet7_device1)
        packets_device2.append(packet7_device2)

        packet8_device1 = device1.generate_packet8(cou=COU, eol=EOL)
        packet8_device2 = device2.generate_packet8(cou=COU, eol=EOL)
        device2.process_packet(packet8_device1)
        device1.process_packet(packet8_device2)
        packets_device1.append(packet8_device1)
        packets_device2.append(packet8_device2)

        packet9_device1 = device1.generate_packet9(cou=COU, eol=EOL)
        packet9_device2 = device2.generate_packet9(cou=COU, eol=EOL)
        device2.process_packet(packet9_device1)
        device1.process_packet(packet9_device2)
        packets_device1.append(packet9_device1)
        packets_device2.append(packet9_device2)

        # Packet A: Check, Dodges, Hits, EOL
        packetA_device1 = device1.generate_packetA(eol=EOL)
        packetA_device2 = device2.generate_packetA(eol=EOL)
        device2.process_packet(packetA_device1)
        device1.process_packet(packetA_device2)
        packets_device1.append(packetA_device1)
        packets_device2.append(packetA_device2)

        # Simulate the battle with fixed HP from protocol (PEN20 uses 5 HP like DM20)
        attacker_hp = 5  # Fixed HP
        defender_hp = 5  # Fixed HP
        battle_log = []

        # Retrieve attack patterns using DM20 single battle pattern table
        # Pattern index comes from minigame taps (stored in mini_game field)
        attack_pattern_device1 = get_dm20_single_battle_attack_pattern(device1.digimon.mini_game)
        attack_pattern_device2 = get_dm20_single_battle_attack_pattern(device2.digimon.mini_game)

        # Extract hits for both devices from Packet A
        # Packet A format: [Check(4)|hit_me(4), hit_you(4)|EOL(4)]
        # hit_me nibble: which of MY attacks HIT the opponent
        device1_hits_nibble = (packetA_device1[0]) & 0x0F  # Lower nibble of byte 0
        device2_hits_nibble = (packetA_device2[0]) & 0x0F
        
        # Extract individual hit bits (bit 0 = turn 1, bit 1 = turn 2, etc)
        device1_hits = [(device1_hits_nibble >> i) & 1 for i in range(4)]
        device2_hits = [(device2_hits_nibble >> i) & 1 for i in range(4)]

        # PEN20 has 5 turns (attacks) but only 4 hit bits in Packet A
        # Turn 5 uses turn 1's pattern value and turn 1's hit result
        for turn in range(5):
            # Attack pattern index (0-3 for turns 1-4, wraps to 0 for turn 5)
            attack_index = turn % 4
            
            # Hit index for Packet A lookup (0-3, turn 5 uses turn 1's hit)
            hit_index = turn if turn < 4 else 0

            # Device 1 attacks Device 2
            device1_attack = attack_pattern_device1[attack_index]
            device1_hit = device1_hits[hit_index]
            defender_damage = device1_attack if device1_hit else 0
            defender_hp = max(0, defender_hp - defender_damage)

            # Device 2 attacks Device 1
            device2_attack = attack_pattern_device2[attack_index]
            device2_hit = device2_hits[hit_index]
            attacker_damage = device2_attack if device2_hit else 0
            attacker_hp = max(0, attacker_hp - attacker_damage)

            # Log the turn
            # IMPORTANT: Store the ATTACK PATTERN VALUE (what attack was attempted), not dealt damage
            turn_log = TurnLog(
                turn=turn + 1,
                device1_status=[
                    DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
                ],
                device2_status=[
                    DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
                ],
                attacks=[
                    AttackLog(
                        turn=turn + 1,
                        device="device1",
                        attacker=0,
                        defender=0,
                        hit=bool(device1_hit),
                        damage=device1_attack,  # Pattern value, not dealt damage
                        critical=(device1_attack == 5),
                    ),
                    AttackLog(
                        turn=turn + 1,
                        device="device2",
                        attacker=0,
                        defender=0,
                        hit=bool(device2_hit),
                        damage=device2_attack,  # Pattern value, not dealt damage
                        critical=(device2_attack == 5),
                    )
                ]
            )
            battle_log.append(turn_log)

            # End battle if both Digimon are defeated
            if attacker_hp == 0 and defender_hp == 0:
                winner = "device1"  # Device 1 attacks first, wins ties
                break

            # End battle if one Digimon is defeated
            if attacker_hp == 0:
                winner = "device2"
                break
            elif defender_hp == 0:
                winner = "device1"
                break
        else:
            # If both are alive after 5 turns, winner is the one with highest HP
            if attacker_hp > defender_hp:
                winner = "device1"
            elif defender_hp > attacker_hp:
                winner = "device2"
            else:
                winner = "draw"

        # Prepare the final result
        result = BattleResult(
            winner=winner,
            device1_final=[
                DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
            ],
            device2_final=[
                DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
            ],
            battle_log=battle_log,
            device1_packets=packets_device1,
            device2_packets=packets_device2
        )

        return result
    
    def _simulate_dmx_bs(self, attacker: Digimon, defender: Digimon) -> BattleResult:
        """
        Simulates a battle using the DMX protocol.
        Uses protocol definition from JSON for constants and configuration.
        """
        # Get protocol constants
        turns = protocol_constants.DMX.TURNS

        device1 = DMXDevice(attacker)
        device2 = DMXDevice(defender)

        # Initialize packet storage
        packets_device1 = []
        packets_device2 = []

        # Packet exchanges
        # Packet 1: Order, Level, Sick, Attack, Version, EOL
        packet1_device1 = device1.generate_packet1()
        packet1_device2 = device2.generate_packet1()
        device2.process_packet(packet1_device1)
        device1.process_packet(packet1_device2)
        packets_device1.append(packet1_device1)
        packets_device2.append(packet1_device2)

        # Packet 2: Stage, Index, Attribute, EOL
        packet2_device1 = device1.generate_packet2()
        packet2_device2 = device2.generate_packet2()
        device2.process_packet(packet2_device1)
        device1.process_packet(packet2_device2)
        packets_device1.append(packet2_device1)
        packets_device2.append(packet2_device2)

        # Packet 3: Shot S, Shot W, EOL
        packet3_device1 = device1.generate_packet3()
        packet3_device2 = device2.generate_packet3()
        device2.process_packet(packet3_device1)
        device1.process_packet(packet3_device2)
        packets_device1.append(packet3_device1)
        packets_device2.append(packet3_device2)

        # Packet 4: COU, HP, Shot M, EOL
        packet4_device1 = device1.generate_packet4()
        packet4_device2 = device2.generate_packet4()
        device2.process_packet(packet4_device1)
        device1.process_packet(packet4_device2)
        packets_device1.append(packet4_device1)
        packets_device2.append(packet4_device2)

        # Packet 5: COU, Buff, Power, EOL
        packet5_device1 = device1.generate_packet5()
        packet5_device2 = device2.generate_packet5()
        device2.process_packet(packet5_device1)
        device1.process_packet(packet5_device2)
        packets_device1.append(packet5_device1)
        packets_device2.append(packet5_device2)

        # Packet 6: Check, COU, Hits, EOL
        packet6_device1 = device1.generate_packet6()
        packet6_device2 = device2.generate_packet6()
        device2.process_packet(packet6_device1)
        device1.process_packet(packet6_device2)
        packets_device1.append(packet6_device1)
        packets_device2.append(packet6_device2)

        # Extract hits for both devices
        device1_hits = [(device1.hits >> i) & 1 for i in range(4)]  # Extract 4 bits from hits
        device2_hits = [(device2.hits >> i) & 1 for i in range(4)]  # Extract 4 bits from hits

        # Reverse the order of bits to match the turn order (MSB -> Turn 1, LSB -> Turn 4)
        device1_hits.reverse()
        device2_hits.reverse()

        # Retrieve attack patterns for both devices
        attack_pattern_device1 = get_attack_pattern(device1.level, device1.digimon.mini_game, protocol="DMX")
        attack_pattern_device2 = get_attack_pattern(device2.level, device2.digimon.mini_game, protocol="DMX")

        # Simulate the battle using protocol configuration
        attacker_hp = device1.hp
        defender_hp = device2.hp
        battle_log = []

        # Simulate turns from protocol
        for turn in range(turns):
            # Determine the attack index (repeat 1st and 2nd attacks for turns 5 and 6)
            attack_index = turn % 4

            # Device 1 attacks Device 2
            device1_attack = attack_pattern_device1[attack_index]
            device1_hit = device1_hits[attack_index]
            defender_damage = device1_attack if device1_hit else 0
            defender_hp = max(0, defender_hp - defender_damage)

            # Device 2 attacks Device 1
            device2_attack = attack_pattern_device2[attack_index]
            device2_hit = device2_hits[attack_index]
            attacker_damage = device2_attack if device2_hit else 0
            attacker_hp = max(0, attacker_hp - attacker_damage)

            # Log the turn
            turn_log = TurnLog(
                turn=turn + 1,
                device1_status=[
                    DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
                ],
                device2_status=[
                    DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
                ],
                attacks=[
                    AttackLog(
                        turn=turn + 1,
                        device="device1",
                        attacker=0,
                        defender=0,
                        hit=bool(device1_hit),
                        damage=defender_damage,
                        # Crit is decided by the BASE attack pattern (1..5), not
                        # by dealt damage — bonuses (level, etc.) can push damage
                        # above 5 and would otherwise mask the slide-in trigger.
                        critical=(device1_attack == 5),
                    ),
                    AttackLog(
                        turn=turn + 1,
                        device="device2",
                        attacker=0,
                        defender=0,
                        hit=bool(device2_hit),
                        damage=attacker_damage,
                        critical=(device2_attack == 5),
                    )
                ]
            )
            battle_log.append(turn_log)

            # End battle if one Digimon is defeated
            if attacker_hp == 0 or defender_hp == 0:
                break

        # Determine the winner
        if attacker_hp > defender_hp:
            winner = "device1"
        elif defender_hp > attacker_hp:
            winner = "device2"
        else:
            winner = "draw"

        # Prepare the final result
        result = BattleResult(
            winner=winner,
            device1_final=[
                DigimonStatus(name=attacker.name, hp=attacker_hp, alive=attacker_hp > 0)
            ],
            device2_final=[
                DigimonStatus(name=defender.name, hp=defender_hp, alive=defender_hp > 0)
            ],
            battle_log=battle_log,
            device1_packets=packets_device1,
            device2_packets=packets_device2
        )

        return result
    
class DMCDevice:
    """
    Represents a Digimon device in a battle, able to generate and parse packets.
    Uses protocol definition for constants.
    """
    def __init__(self, data: Digimon):
        self.data = data
        self.hp = self.data.hp
        self.power = self.data.power
        self.attribute = self.data.attribute
        self.index = self.data.index
        self.shot = self.data.shot1
        self.packet_index = 0
        self.received_packets = []  # Store received packets

    def generate_packet1(self, operation):
        return DMCBSPacket(
            operation=operation,
            index=self.index,
            power=self.power,
            attribute=self.attribute,
            shot=self.shot,
            outcome=0
        ).build_packet1()

    def generate_packet2(self, operation, outcome):
        return DMCBSPacket(
            operation=operation,
            index=self.index,
            power=self.power,
            attribute=self.attribute,
            shot=self.shot,
            outcome=outcome
        ).build_packet2()

    def process_packet(self, packet):
        """
        Processes an incoming packet and stores it for later use.
        """
        self.received_packets.append(packet)

    def calculate_outcome(self, opponent):
        """
        Calculates the battle outcome based on the exchanged data.
        """
        # Example logic: Compare power and attribute advantage
        advantage = 0
        if (self.attribute == 0 and opponent.attribute == 2) or \
           (self.attribute == 1 and opponent.attribute == 0) or \
           (self.attribute == 2 and opponent.attribute == 1):
            advantage = 5  # Example attribute advantage

        hitrate = ((self.power * 100) / (self.power + opponent.power)) + advantage
        hitrate = max(0, min(hitrate, 100))  # Clamp hitrate between 0 and 100

        # Simulate attack roll
        attack_roll = random.randint(0, 99)
        return 1 if attack_roll < hitrate else 0  # 1 = win, 0 = lose


class DMDevice:
    """
    Represents a Digimon device in the original DM (Digital Monster) protocol.
    Uses slot-based battle system with 2 packets containing mirrored bits.
    """
    
    # Slot mapping: power -> slot hex value
    POWER_TO_SLOT = [
        (10, 0x3),   # A: power <= 10
        (15, 0x4),   # B: 11-15
        (20, 0x5),   # C: 16-20
        (25, 0x6),   # D: 21-25
        (30, 0x7),   # E: 26-30
        (35, 0x8),   # F: 31-35
        (40, 0x9),   # G: 36-40
        (45, 0xA),   # H: 41-45
        (50, 0xB),   # I: 46-50
        (55, 0xC),   # J: 51-55
        (59, 0xD),   # K: 56-59
    ]
    
    def __init__(self, digimon: Digimon):
        self.digimon = digimon
        self.power = digimon.power
        self.boost = min(4, max(0, digimon.mini_game if digimon.mini_game else 0))  # 0-4 from pills
        self.slot = self._get_slot_from_power(self.power)
        self.version = 1
        
    def _get_slot_from_power(self, power: int) -> int:
        """Convert power to slot hex value (3-E)."""
        for max_power, slot_hex in self.POWER_TO_SLOT:
            if power <= max_power:
                return slot_hex
        return 0xE  # L: power >= 60
    
    def _mirror_bits(self, value: int, bits: int = 4) -> int:
        """Mirror/invert bits of a value."""
        return (~value) & ((1 << bits) - 1)
    
    def generate_packet1(self) -> bytes:
        """
        Generate Packet 1: Digimon Data
        Format: [boost_mirror(4) | slot_mirror(4)] [boost(4) | slot(4)]
        """
        boost_mirror = self._mirror_bits(self.boost)
        slot_mirror = self._mirror_bits(self.slot)
        
        byte1 = (boost_mirror << 4) | slot_mirror
        byte2 = (self.boost << 4) | self.slot
        
        return struct.pack(">BB", byte1, byte2)
    
    def generate_packet2(self, outcome: int = 0) -> bytes:
        """
        Generate Packet 2: Battle Result
        Format: [version_mirror(4) | outcome_mirror(4)] [version(4) | outcome(4)]
        
        Args:
            outcome: 0 = not yet determined, 1 = victory, 2 = defeat
        """
        version_mirror = self._mirror_bits(self.version)
        outcome_mirror = self._mirror_bits(outcome)
        
        byte1 = (version_mirror << 4) | outcome_mirror
        byte2 = (self.version << 4) | outcome
        
        return struct.pack(">BB", byte1, byte2)
    
    def generate_all_packets(self) -> list:
        """Generate both packets for DM protocol."""
        return [
            self.generate_packet1(),
            self.generate_packet2()
        ]
    
    @staticmethod
    def parse_packet1(data: bytes) -> dict:
        """Parse opponent's Packet 1."""
        if len(data) < 2:
            return None
        byte1, byte2 = struct.unpack(">BB", data[:2])
        boost = (byte2 >> 4) & 0x0F
        slot = byte2 & 0x0F
        return {'boost': boost, 'slot': slot}
    
    @staticmethod
    def parse_packet2(data: bytes) -> dict:
        """Parse opponent's Packet 2."""
        if len(data) < 2:
            return None
        byte1, byte2 = struct.unpack(">BB", data[:2])
        version = (byte2 >> 4) & 0x0F
        outcome = byte2 & 0x0F
        return {'version': version, 'outcome': outcome}

    
class DM20Device:
    """
    Represents a Digimon device in the DM20_BS protocol.
    Handles packet generation, processing, and state management.
    Uses protocol definition for constants.
    """
    def __init__(self, digimon: Digimon):
        self.digimon = digimon
        self.hp = digimon.hp
        self.power = digimon.power
        self.attribute = digimon.attribute
        self.index = digimon.index
        self.shot1 = digimon.shot1
        self.shot2 = digimon.shot2
        self.tag_meter = digimon.tag_meter  # Use the tag_meter attribute from the Digimon class
        self.packets = []  # Stores packets received from the opponent
        self.opponent_data = []  # Store opponent's data
        self.own_packets = []  # Track our own sent packets for checksum calculation

    def generate_packet1(self):
        """
        Generates Packet 1: Name 2, Name 1.
        """
        tamer_name = ["O", "M", "N", "I"]
        packet = struct.pack(">BB", ord(tamer_name[1]), ord(tamer_name[0]))
        self.own_packets.append(packet)
        return packet

    def generate_packet2(self):
        """
        Generates Packet 2: Name 4, Name 3.
        """
        tamer_name = ["O", "M", "N", "I"]
        packet = struct.pack(">BB", ord(tamer_name[3]), ord(tamer_name[2]))
        self.own_packets.append(packet)
        return packet

    def generate_packet3(self, order, version, eol):
        """
        Generates Packet 3: Order | Attack (pattern index) | Operation | Version | EOL
        Packet 3: 1 bit Order, 5 bits Attack, 2 bits Operation, 4 bits Version, 4 bits EOL
        Binary: O AAAAA OO VVVV EEEE
        """
        # Convert minigame taps to pattern index
        from battle.sim.battle_utils import get_dm20_pattern_index_from_taps
        pattern_index = get_dm20_pattern_index_from_taps(self.digimon.mini_game)
        
        operation = 0b00  # Single Battle (2 bits)
        # Pack across bytes: O AAAAA OO VVVV EEEE
        byte1 = (order << 7) | (pattern_index << 2) | operation
        byte2 = (version << 4) | eol
        packet = struct.pack(">BB", byte1, byte2)
        self.own_packets.append(packet)
        return packet

    def generate_packet4(self, cou, eol):
        """
        Generates Packet 4: COU | Index L | Attribute L | EOL
        Packet 4: 2 bits COU, 8 bits Index, 2 bits Attribute, 4 bits EOL
        Binary: CC IIIIIIII AA EEEE
        """
        # Pack across bytes: CC IIIIII II AA EEEE = CCIIIIIII IAAEEEEE -> CCIIIIII IIAAEEEE
        byte1 = (cou << 6) | (self.index >> 2)
        byte2 = ((self.index & 0x03) << 6) | (self.attribute << 4) | eol
        packet = struct.pack(">BB", byte1, byte2)
        self.own_packets.append(packet)
        return packet

    def generate_packet5(self, eol):
        """
        Generates Packet 5: Shot S L | Shot W L | EOL
        Packet 5: 6 bits Shot S, 6 bits Shot W, 4 bits EOL
        Binary: SSSSSS WWWWWW EEEE
        """
        # Pack across bytes: SSSSSS WW WWWW EEEE = SSSSSSW W WWWWEEEE -> SSSSSSWW WWWWEEEE
        byte1 = (self.shot1 << 2) | (self.shot2 >> 4)
        byte2 = ((self.shot2 & 0x0F) << 4) | eol
        packet = struct.pack(">BB", byte1, byte2)
        self.own_packets.append(packet)
        return packet

    def generate_packet6(self, cou, eol):
        """
        Generates Packet 6: COU | Power L | EOL
        Packet 6: 4 bits COU, 8 bits Power, 4 bits EOL
        Binary: CCCC PPPPPPPP EEEE
        """
        # Pack across bytes: CCCC PPPP PPPP EEEE = CCCCPPPP PPPPEEEE
        byte1 = (cou << 4) | (self.power >> 4)
        byte2 = ((self.power & 0x0F) << 4) | eol
        packet = struct.pack(">BB", byte1, byte2)
        self.own_packets.append(packet)
        return packet

    def generate_packet7(self, cou, eol):
        """
        Generates Packet 7: COU | Index R | Attribute R | EOL
        For single battles, R values are 0
        """
        index_r = 0
        attribute_r = 0
        byte1 = (cou << 6) | (index_r >> 2)
        byte2 = ((index_r & 0x03) << 6) | (attribute_r << 4) | eol
        packet = struct.pack(">BB", byte1, byte2)
        self.own_packets.append(packet)
        return packet

    def generate_packet8(self, eol):
        """
        Generates Packet 8: Shot S R | Shot W R | EOL
        For single battles, R values are 0
        """
        shot_s_r = 0
        shot_w_r = 0
        byte1 = (shot_s_r << 2) | (shot_w_r >> 4)
        byte2 = ((shot_w_r & 0x0F) << 4) | eol
        packet = struct.pack(">BB", byte1, byte2)
        self.own_packets.append(packet)
        return packet

    def generate_packet9(self, eol):
        """
        Generates Packet 9: Tag Meter | Power R | EOL
        Packet 9: 4 bits Tag Meter, 8 bits Power R, 4 bits EOL
        For single battles, Power R is 0
        """
        tag_meter = self.digimon.tag_meter
        power_r = 0
        byte1 = (tag_meter << 4) | (power_r >> 4)
        byte2 = ((power_r & 0x0F) << 4) | eol
        packet = struct.pack(">BB", byte1, byte2)
        self.own_packets.append(packet)
        return packet

    def process_packet(self, packet):
        """
        Processes an incoming packet and stores it for later use.
        """
        self.opponent_data.append(packet)

    def generate_packetA(self, eol):
        """
        Generates Packet A: Check, Dodges, Hits, EOL.
        """
        if not self.opponent_data:
            raise ValueError("Opponent data is not available. Ensure packets are processed before generating Packet A.")

        # Extract opponent's power and attribute from the stored packets
        opponent_power = self.opponent_data[4][0] & 0b11111111  # Power from Packet 5
        opponent_attribute = (self.opponent_data[1][1] >> 4) & 0b1111  # Attribute from Packet 2

        power = self.digimon.power
        if (self.digimon.attribute == 0 and opponent_attribute == 2) or \
           (self.digimon.attribute == 1 and opponent_attribute == 0) or \
           (self.digimon.attribute == 2 and opponent_attribute == 1):
            power += 32  # Attribute advantage

        # Add 32 to opponent's power if they have an attribute advantage
        if (opponent_attribute == 0 and self.digimon.attribute == 2) or \
           (opponent_attribute == 1 and self.digimon.attribute == 0) or \
           (opponent_attribute == 2 and self.digimon.attribute == 1):
            opponent_power += 32

        # Initialize hits and dodges
        hits = 0
        dodges = 0

        # Calculate hits and dodges for 4 attacks
        for i in range(4):
            # Calculate hitrate
            hitrate = ((power * 100) / (power + opponent_power))
            hitrate = max(0, min(hitrate, 100))  # Clamp hitrate between 0 and 100

            # Simulate hit
            attack_roll = random.randint(0, 99)
            hit = 1 if attack_roll < hitrate else 0

            # Calculate dodge (inverted for single battles)
            dodge = 1 - hit

            # Update hits and dodges bit patterns (right to left)
            hits |= (hit << i)
            dodges |= (dodge << i)

        check = self._calculate_check(hits, dodges, eol)

        # Pack the data into bytes
        return struct.pack(">B", (check << 4) | dodges) + struct.pack(">B", (hits << 4) | eol)

    def _calculate_check(self, hits, dodges, eol):
        """
        Calculates the Check value for Packet A.
        Sums all nibbles from THIS device's own packets 1-9 plus hits, dodges, EOL, 
        and finds check value that makes total % 16 == 0.
        """
        # Sum all nibbles from OUR OWN packets 1-9 (not opponent's)
        checksum = 0
        for pkt in self.own_packets[:9]:  # First 9 packets we sent
            for byte in pkt:
                checksum += (byte >> 4) & 0xF  # Upper nibble
                checksum += byte & 0xF          # Lower nibble
        
        # Add dodges, hits, and EOL nibbles
        checksum += dodges & 0xF
        checksum += hits & 0xF
        checksum += eol & 0xF
        
        # Find check value that makes (checksum + check) % 16 == 0
        check = (16 - (checksum % 16)) % 16
        return check
    
    def generate_all_packets_for_dcom(self, order=0, cou=0b00, version=None, eol=0b1110):
        """
        Generate all 10 DM20 packets for DCom battle communication.
        Uses proper checksum calculation matching the test implementation.
        Returns list of 10 packets (bytes objects).
        """
        packets = []
        
        # Generate packets 1-9
        packets.append(self.generate_packet1())
        packets.append(self.generate_packet2())
        # Determine version from digimon.version if not explicitly provided
        if version is None:
            try:
                v = int(getattr(self.digimon, 'version', 1))
            except Exception:
                v = 1
            # Clamp DM20 version to range 1..5
            v = max(1, min(5, v))
            version = v

        packets.append(self.generate_packet3(order, version, eol))
        packets.append(self.generate_packet4(cou, eol))
        packets.append(self.generate_packet5(eol))
        packets.append(self.generate_packet6(cou, eol))
        packets.append(self.generate_packet7(cou, eol))
        packets.append(self.generate_packet8(eol))
        packets.append(self.generate_packet9(eol))
        
        # Calculate proper checksum by summing all nibbles
        checksum = 0
        for pkt in packets:
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F  # Upper nibble
                checksum += byte & 0x0F          # Lower nibble
        
        # Generate Packet A with proper checksum
        dodges = 0x0  # All dodge (0000)
        hits = 0xF    # All hit (1111)
        
        # Add dodges, hits, and EOL nibbles to checksum
        checksum += dodges
        checksum += hits
        checksum += eol
        
        # Find check value that makes (checksum + check) % 16 == 0
        check = (16 - (checksum % 16)) % 16
        
        byte1 = (check << 4) | dodges
        byte2 = (hits << 4) | eol
        packetA = struct.pack(">BB", byte1, byte2)
        packets.append(packetA)
        
        return packets

class DMCBSPacket:
    """
    Represents a DMC_BS packet (2 packets per exchange).
    """
    COU = 0x47444C43  # 'DMCL'

    def __init__(self, operation: int, index: int, power: int, attribute: int, shot: int, outcome: int):
        self.operation = operation  # Operation code (0-3)
        self.index = index          # Digimon index
        self.power = power          # Digimon power
        self.attribute = attribute  # Digimon attribute (0=Free, 1=Virus, 2=Data, 3=Vaccine)
        self.shot = shot            # Attack sprite ID
        self.outcome = outcome      # Battle outcome (0=loss, 1=win)

    def _calc_check(self, packet_bytes: bytes) -> int:
        """
        Calculates the checksum for the packet.
        The checksum is the sum of all 16-bit fields, keeping only the lowest 16 bits.
        """
        check = 0
        for i in range(0, len(packet_bytes) - 2, 2):  # Exclude the last 2 bytes (checksum field)
            segment = int.from_bytes(packet_bytes[i:i+2], 'big')
            check += segment
        return check & 0xFFFF  # Keep only the lowest 16 bits

    def build_packet1(self) -> bytes:
        """
        Builds Packet 1 (Digimon Data Packet).
        Structure:
        COU (4 bytes) | Operation (2 bytes) | Version (2 bytes) | Index (2 bytes) |
        Power (2 bytes) | Attribute (2 bytes) | Check (2 bytes)
        """
        version = 1  # Fixed version value
        packet = struct.pack(">IHHHHHH",
            self.COU,           # COU (4 bytes)
            self.operation,     # Operation (2 bytes)
            version,            # Version (2 bytes)
            self.index,         # Index (2 bytes)
            self.power,         # Power (2 bytes)
            self.attribute,     # Attribute (2 bytes)
            0                   # Check (placeholder, 2 bytes)
        )
        check = self._calc_check(packet)
        return struct.pack(">IHHHHHH",
            self.COU,
            self.operation,
            version,
            self.index,
            self.power,
            self.attribute,
            check                # Final checksum
        )

    def build_packet2(self) -> bytes:
        """
        Builds Packet 2 (Battle Data Packet).
        Structure:
        COU (4 bytes) | Operation (2 bytes) | Shot (2 bytes) | Outcome (2 bytes) |
        COU (4 bytes) | Check (2 bytes)
        """
        packet = struct.pack(">IHHHIH",
            self.COU,           # COU (4 bytes)
            self.operation,     # Operation (2 bytes)
            self.shot,          # Shot (2 bytes)
            self.outcome,       # Outcome (2 bytes)
            0,                  # Placeholder for repeated COU (4 bytes)
            0                   # Check (placeholder, 2 bytes)
        )
        check = self._calc_check(packet)
        return struct.pack(">IHHHIH",
            self.COU,
            self.operation,
            self.shot,
            self.outcome,
            0,                  # Placeholder for repeated COU
            check                # Final checksum
        )

class PEN20Device:
    """
    Represents a Digimon device in the PEN20_BS protocol.
    Handles packet generation, processing, and state management.
    Packet layouts are documented in protocol_constants.PEN20.

    PEN20 uses Dummy minigame (0-14 taps) similar to DM20.
    Power bonuses:
    - Egg shake (shook): +10 power
    - Traited: Stage 3: +5, Stage 4: +8, Stage 5: +15, Stage 6+: +20
    """
    
    # Traited power bonuses by stage
    TRAITED_BONUSES = {
        3: 5,
        4: 8,
        5: 15,
        # Stage 6+ uses 20
    }
    EGG_SHAKE_BONUS = 10
    
    def __init__(self, digimon: Digimon):
        self.digimon = digimon
        self.hp = digimon.hp
        self.attribute = digimon.attribute
        self.index = digimon.index
        self.shot1 = digimon.shot1  # Strong shot
        self.shot2 = digimon.shot2  # Weak shot
        self.traited = digimon.traited  # Trait status (0 or 1)
        self.egg_shake = digimon.egg_shake  # Egg shake status (0 or 1)
        self.sick = digimon.sick  # Sick status
        self.stage = digimon.stage  # Evolution stage for traited bonus calculation
        self.tag_meter = digimon.tag_meter
        self.packets = []  # Stores packets received from the opponent
        self.opponent_data = []  # Store opponent's data
        
        # Calculate final power with bonuses
        self.power = self._calculate_power_with_bonuses(digimon.power)
    
    def _calculate_power_with_bonuses(self, base_power):
        """Calculate final power including traited and egg_shake bonuses."""
        power = base_power
        
        # Add egg shake bonus (+10)
        if self.egg_shake:
            power += self.EGG_SHAKE_BONUS
        
        # Add traited bonus based on stage
        if self.traited:
            if self.stage >= 6:
                power += 20
            else:
                power += self.TRAITED_BONUSES.get(self.stage, 0)
        
        # Cap at 255
        return min(255, power)

    def generate_packet1(self, order, version, eol):
        """
        Generates Packet 1: Order(1) COU(1) Attack(4) Operation(2) Version(4) EOL(4)
        
        Bit layout (16 bits total):
        Byte 1: Order(1) | COU(1) | Attack(4) | Operation(2) = 8 bits
        Byte 2: Version(4) | EOL(4) = 8 bits
        """
        attack = min(14, self.digimon.mini_game)  # Dummy minigame: 0-14 taps
        operation = 0b00  # Single Battle
        cou = 0b0  # Constant (1 bit)

        # Byte 1: Order(1) + COU(1) + Attack(4) + Operation(2)
        byte1 = (order << 7) | (cou << 6) | ((attack & 0xF) << 2) | (operation & 0x3)
        
        # Byte 2: Version(4) + EOL(4)
        byte2 = ((version & 0xF) << 4) | (eol & 0xF)
        
        return struct.pack(">BB", byte1, byte2)

    def generate_packet2(self, cou, eol):
        """
        Generates Packet 2: COU(2) Index(8) Attribute(2) EOL(4)
        
        Bit layout (16 bits total):
        Byte 1: COU(2) | Index high 6 bits = 8 bits
        Byte 2: Index low 2 bits | Attribute(2) | EOL(4) = 8 bits
        """
        index = self.index & 0xFF  # 8 bits
        # Byte 1: COU(2) + Index high 6 bits
        byte1 = ((cou & 0x3) << 6) | ((index >> 2) & 0x3F)
        # Byte 2: Index low 2 bits + Attribute(2) + EOL(4)
        byte2 = ((index & 0x3) << 6) | ((self.attribute & 0x3) << 4) | (eol & 0xF)
        return struct.pack(">BB", byte1, byte2)

    def generate_packet3(self, cou, eol):
        """
        Generates Packet 3: COU(4) Shot_W(8) EOL(4)
        
        Bit layout (16 bits total):
        Byte 1: COU(4) | Shot_W high 4 bits = 8 bits
        Byte 2: Shot_W low 4 bits | EOL(4) = 8 bits
        """
        shot_w = self.shot2 & 0xFF  # 8 bits
        byte1 = ((cou & 0xF) << 4) | ((shot_w >> 4) & 0xF)
        byte2 = ((shot_w & 0xF) << 4) | (eol & 0xF)
        return struct.pack(">BB", byte1, byte2)

    def generate_packet4(self, cou, eol):
        """
        Generates Packet 4: Sick(1) COU(3) Shot_S(8) EOL(4)
        
        Bit layout (16 bits total):
        Byte 1: Sick(1) | COU(3) | Shot_S high 4 bits = 8 bits
        Byte 2: Shot_S low 4 bits | EOL(4) = 8 bits
        """
        shot_s = self.shot1 & 0xFF  # 8 bits
        byte1 = ((self.sick & 0x1) << 7) | ((cou & 0x7) << 4) | ((shot_s >> 4) & 0xF)
        byte2 = ((shot_s & 0xF) << 4) | (eol & 0xF)
        return struct.pack(">BB", byte1, byte2)

    def generate_packet5(self, cou, eol):
        """
        Generates Packet 5: COU(2) Traited(1) Egg_Shake(1) Power(8) EOL(4)
        
        Bit layout (16 bits total):
        Byte 1: COU(2) | Traited(1) | Egg_Shake(1) | Power high 4 bits = 8 bits
        Byte 2: Power low 4 bits | EOL(4) = 8 bits
        """
        power = self.power & 0xFF  # Already includes bonuses
        byte1 = ((cou & 0x3) << 6) | ((self.traited & 0x1) << 5) | ((self.egg_shake & 0x1) << 4) | ((power >> 4) & 0xF)
        byte2 = ((power & 0xF) << 4) | (eol & 0xF)
        return struct.pack(">BB", byte1, byte2)

    def generate_packet6(self, eol):
        """
        Generates Packet 6: Copy(2) Index_R(8) Attribute_R(2) EOL(4)
        For single battles, all R values are 0.
        """
        copy = 0
        index_r = 0
        attribute_r = 0
        byte1 = ((copy & 0x3) << 6) | ((index_r >> 2) & 0x3F)
        byte2 = ((index_r & 0x3) << 6) | ((attribute_r & 0x3) << 4) | (eol & 0xF)
        return struct.pack(">BB", byte1, byte2)

    def generate_packet7(self, cou, eol):
        """
        Generates Packet 7: COU, Shot W R, EOL.
        """
        shot_w_r = 0  # For single battles, Shot W R is 0
        return struct.pack(
            ">B", (cou << 4) | (shot_w_r >> 4)
        ) + struct.pack(
            ">B", ((shot_w_r & 0b1111) << 4) | eol
        )

    def generate_packet8(self, cou, eol):
        """
        Generates Packet 8: COU, Shot S R, EOL.
        """
        shot_s_r = 0  # For single battles, Shot S R is 0
        return struct.pack(
            ">B", (cou << 4) | (shot_s_r >> 4)
        ) + struct.pack(
            ">B", ((shot_s_r & 0b1111) << 4) | eol
        )

    def generate_packet9(self, cou, eol):
        """
        Generates Packet 9: COU, Power R, EOL.
        """
        power_r = 0  # For single battles, Power R is 0
        return struct.pack(
            ">B", (cou << 4) | (power_r >> 4)
        ) + struct.pack(
            ">B", ((power_r & 0b1111) << 4) | eol
        )

    def process_packet(self, packet):
        """
        Processes an incoming packet and stores it for later use.
        """
        self.opponent_data.append(packet)

    def generate_packetA(self, eol):
        """
        Generates Packet A: Check, Dodges, Hits, EOL.
        """
        if not self.opponent_data:
            raise ValueError("Opponent data is not available. Ensure packets are processed before generating Packet A.")

        # Extract opponent's power and attribute from the stored packets
        opponent_power = self.opponent_data[4][0] & 0b11111111  # Power from Packet 5
        opponent_attribute = (self.opponent_data[1][1] >> 4) & 0b1111  # Attribute from Packet 2

        power = self.digimon.power
        if (self.digimon.attribute == 0 and opponent_attribute == 2) or \
           (self.digimon.attribute == 1 and opponent_attribute == 0) or \
           (self.digimon.attribute == 2 and opponent_attribute == 1):
            power += 32  # Attribute advantage

        # Add 32 to opponent's power if they have an attribute advantage
        if (opponent_attribute == 0 and self.digimon.attribute == 2) or \
           (opponent_attribute == 1 and self.digimon.attribute == 0) or \
           (opponent_attribute == 2 and self.digimon.attribute == 1):
            opponent_power += 32

        # Initialize hits and dodges
        hits = 0
        dodges = 0

        # Calculate hits and dodges for 4 attacks
        for i in range(4):
            # Calculate hitrate
            hitrate = ((power * 100) / (power + opponent_power))
            hitrate = max(0, min(hitrate, 100))  # Clamp hitrate between 0 and 100

            # Simulate hit
            attack_roll = random.randint(0, 99)
            hit = 1 if attack_roll < hitrate else 0

            # Calculate dodge (inverted for single battles)
            dodge = 1 - hit

            # Update hits and dodges bit patterns (right to left)
            hits |= (hit << i)
            dodges |= (dodge << i)

        check = self._calculate_check(hits, dodges, eol)

        # Pack the data into bytes
        return struct.pack(">B", (check << 4) | dodges) + struct.pack(">B", (hits << 4) | eol)

    def _calculate_check(self, hits, dodges, eol):
        """
        Calculates the Check value for Packet A.
        Sums all nibbles from packets 1-9 plus hits, dodges, EOL, and finds check value
        that makes total % 16 == 0.
        """
        # Sum all nibbles from packets 1-9
        checksum = 0
        for pkt in self.opponent_data[:9]:  # First 9 packets (not including packet A)
            for byte in pkt:
                checksum += (byte >> 4) & 0xF  # Upper nibble
                checksum += byte & 0xF          # Lower nibble
        
        # Add dodges, hits, and EOL nibbles
        checksum += dodges & 0xF
        checksum += hits & 0xF
        checksum += eol & 0xF
        
        # Find check value that makes (checksum + check) % 16 == 0
        check = (16 - (checksum % 16)) % 16
        return check

    def generate_all_packets_for_dcom(self, order=0, cou=0b00, version=None,
                                      eol=protocol_constants.PEN20.EOL):
        """
        Generate all 10 PEN20 packets for DCom battle communication.

        Mirrors DM20Device.generate_all_packets_for_dcom (the DCom-tested
        pattern): packets 1-9 carry our data, packet A claims all hits with
        a checksum over our own transmission. Target remainder 0 — matching
        the tested _validate_pen20_packets rule (see protocol_constants.PEN20
        for the note about the doc claiming 12).
        """
        if version is None:
            try:
                v = int(getattr(self.digimon, 'version', 1))
            except Exception:
                v = 1
            v_min, v_max = protocol_constants.PEN20.VERSION_RANGE
            version = max(v_min, min(v_max, v))

        packets = [
            self.generate_packet1(order, version, eol),
            self.generate_packet2(cou, eol),
            self.generate_packet3(0, eol),
            self.generate_packet4(0, eol),
            self.generate_packet5(cou, eol),
            self.generate_packet6(eol),
            self.generate_packet7(0, eol),
            self.generate_packet8(0, eol),
            self.generate_packet9(0, eol),
        ]

        # Sum every nibble of packets 1-9
        checksum = 0
        for pkt in packets:
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F
                checksum += byte & 0x0F

        # Packet A: Check(4) | Dodges(4) | Hits(4) | EOL(4)
        dodges = 0x0
        hits = 0xF
        checksum += dodges + hits + (eol & 0xF)
        target = protocol_constants.PEN20.CHECKSUM_REMAINDER
        check = (target - (checksum % 16)) % 16

        packets.append(struct.pack(">BB", (check << 4) | dodges, (hits << 4) | eol))
        return packets

class DMXDevice:
    """
    Represents a Digimon device in the DMX/PENZ protocol.
    Handles packet generation, processing, and state management.
    
    DMX uses XAI Roll + XAI Bar minigame (0-3).
    PENZ uses Count Match minigame (rotation index 1-3, maps to 0-3).
    
    Attack quality is determined by level + minigame result:
    - Bad (0), Good (1), Great (2), Excellent (3)
    
    Power is capped at 255 to prevent overflow bugs from original Version 1 devices.
    """
    MAX_POWER = 255
    
    def __init__(self, digimon: Digimon):
        self.digimon = digimon
        self.hp = digimon.hp
        # Cap power at 255 to prevent Version 1 overflow bug
        self.power = min(self.MAX_POWER, digimon.power)
        self.attribute = digimon.attribute
        self.level = digimon.level
        self.sick = digimon.sick
        self.stage = digimon.stage
        self.index = digimon.index
        self.shot_s = digimon.shot1
        self.shot_w = digimon.shot2
        self.shot_m = getattr(digimon, 'dmx_shot_m', digimon.shot1)
        self.buff = min(2, digimon.buff)  # Max buff is 2
        self.order = digimon.order
        self.version = getattr(digimon, 'version', 0) & 0x0F  # 4-bit version from Digimon
        self.hits = 0  # Hit pattern (5 bits for 5 turns)
        self.check = 0  # Check value
        self.received_packets = []  # Store received packets

    def generate_packet1(self):
        """
        Generates Packet 1: Order(1) Level(4) Sick(1) Attack(2) Version(4) EOL(4).
        Total: 16 bits = 2 bytes
        
        Attack is only 2 bits (0-3): Bad(0), Good(1), Great(2), Excellent(3)
        """
        attack = self.digimon.mini_game & 0x03  # Only 2 bits (0-3)
        eol = 0xE  # 1110
        
        # Byte 1: Order(1) Level(4) Sick(1) Attack(2)
        # Byte 2: Version(4) EOL(4)
        return struct.pack(
            ">B", (self.order << 7) | (self.level << 3) | (self.sick << 2) | (attack & 0x03)
        ) + struct.pack(
            ">B", ((self.version & 0x0F) << 4) | eol
        )

    def generate_packet2(self):
        """
        Generates Packet 2: Stage(3) Index(7) Attribute(2) EOL(4).
        Total: 16 bits = 2 bytes
        
        Index is 7 bits (0-127), not 8 bits
        Attribute is 2 bits (0-3), not 3 bits
        """
        eol = 0xE  # 1110
        index = self.index & 0x7F  # 7 bits
        attribute = self.attribute & 0x03  # 2 bits
        
        # Byte 1: Stage(3) + Index high 5 bits
        # Byte 2: Index low 2 bits + Attribute(2) + EOL(4)
        return struct.pack(
            ">B", (self.stage << 5) | (index >> 2)
        ) + struct.pack(
            ">B", ((index & 0x03) << 6) | (attribute << 4) | eol
        )

    def generate_packet3(self):
        """
        Generates Packet 3: Shot S(6), Shot W(6), EOL(4).
        Total: 16 bits = 2 bytes
        """
        # Byte 1: Shot S (6 bits) + Shot W high 2 bits
        # Byte 2: Shot W low 4 bits + EOL (4 bits)
        return struct.pack(
            ">B", ((self.shot_s & 0x3F) << 2) | ((self.shot_w >> 4) & 0x03)
        ) + struct.pack(
            ">B", ((self.shot_w & 0x0F) << 4) | 0b1110
        )

    def generate_packet4(self):
        """
        Generates Packet 4: COU, HP, Shot M, EOL.
        """
        return struct.pack(
            ">B", (0b00 << 6) | (self.hp << 1) | (self.shot_m >> 4)
        ) + struct.pack(
            ">B", ((self.shot_m & 0b1111) << 4) | 0b1110
        )

    def generate_packet5(self):
        """
        Generates Packet 5: COU(2), Buff(2), Power(8), EOL(4).
        Total: 16 bits = 2 bytes
        """
        # Byte 1: COU(2) + Buff(2) + Power high 4 bits
        # Byte 2: Power low 4 bits + EOL(4)
        return struct.pack(
            ">B", (0b00 << 6) | ((self.buff & 0x03) << 4) | ((self.power >> 4) & 0x0F)
        ) + struct.pack(
            ">B", ((self.power & 0x0F) << 4) | 0b1110
        )

    def generate_packet6(self, eol=0b1110):
        """
        Generates Packet 6: Check(4) COU(3) Hits(5) EOL(4).
        Calculates checksum from all previous packets and hits pattern.
        """
        if len(self.received_packets) < 5:
            raise ValueError("Not enough packets received to calculate checksum.")

        # Extract opponent's power from Packet 5
        opponent_power_byte = self.received_packets[4][0]
        opponent_power = ((opponent_power_byte & 0x0F) << 4) | ((self.received_packets[4][1] >> 4) & 0x0F)

        # Extract opponent's attribute from Packet 2
        opponent_attribute = (self.received_packets[1][1] >> 4) & 0x03

        # Apply attribute advantage
        player_power = self.power
        if (self.attribute == 0 and opponent_attribute == 2) or \
           (self.attribute == 1 and opponent_attribute == 0) or \
           (self.attribute == 2 and opponent_attribute == 1):
            player_power += 32

        if (opponent_attribute == 0 and self.attribute == 2) or \
           (opponent_attribute == 1 and self.attribute == 0) or \
           (opponent_attribute == 2 and self.attribute == 1):
            opponent_power += 32

        # Calculate hits for 5 rounds
        hits = 0
        for i in range(5):  # DMX uses 5 rounds
            hitrate = ((player_power * 100) / (player_power + opponent_power))
            hitrate = max(0, min(hitrate, 100))

            attack_roll = random.randint(0, 99)
            hit = 1 if attack_roll < hitrate else 0
            hits |= (hit << i)

        self.hits = hits
        cou3 = 0  # 3-bit COU value

        # Calculate checksum - sum all nibbles from packets 1-5 (sent by this device)
        checksum = 0
        # We need to sum our OWN packets that were sent, not received packets
        # For simulation, we need to recalculate what we sent
        # This is tricky - we should track sent packets properly
        # For now, use a simplified approach
        
        # Generate the first 5 packets again to get nibble sums
        from io import BytesIO
        temp_packets = [
            self.generate_packet1(),
            self.generate_packet2(),
            self.generate_packet3(),
            self.generate_packet4(),
            self.generate_packet5()
        ]
        
        for pkt in temp_packets:
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F  # Upper nibble
                checksum += byte & 0x0F  # Lower nibble
        
        # Build packet 6 structure without check
        byte1_without_check = (cou3 << 1) | (hits >> 4)
        byte2 = ((hits & 0x0F) << 4) | eol
        
        # Add nibbles from packet 6 (without check nibble)
        checksum += byte1_without_check & 0x0F
        checksum += (byte2 >> 4) & 0x0F
        checksum += byte2 & 0x0F
        
        # Find check value that makes (checksum + check) % 16 == 8
        intended_remainder = 8
        check = (intended_remainder - (checksum % 16)) % 16
        self.check = check
        
        # Build final packet
        byte1 = (check << 4) | byte1_without_check
        
        return struct.pack(">BB", byte1, byte2)

    def process_packet(self, packet):
        """
        Processes an incoming packet and stores it for later use.
        """
        self.received_packets.append(packet)

    def generate_all_packets_for_dcom(self, eol=protocol_constants.DMX.EOL):
        """
        Generate all 6 DMX/PENZ packets for DCom battle communication.

        Unlike generate_packet6 (which needs the opponent's packets to roll
        hit chances), the DCom listen-and-reply flow sends before knowing the
        opponent — so packet 6 claims all 5 hits, mirroring the DCom-tested
        DM20 convention (hits=0xF there). Checksum: nibble sum of all six
        packets ≡ 8 (mod 16), matching _validate_dmx_packets.
        """
        packets = [
            self.generate_packet1(),
            self.generate_packet2(),
            self.generate_packet3(),
            self.generate_packet4(),
            self.generate_packet5(),
        ]

        checksum = 0
        for pkt in packets:
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F
                checksum += byte & 0x0F

        # Packet 6: Check(4) | COU(3) | Hits(5) | EOL(4)
        hits = 0b11111
        cou3 = 0
        byte1_without_check = (cou3 << 1) | ((hits >> 4) & 0x1)
        byte2 = ((hits & 0x0F) << 4) | (eol & 0xF)

        checksum += byte1_without_check & 0x0F
        checksum += (byte2 >> 4) & 0x0F
        checksum += byte2 & 0x0F

        target = protocol_constants.DMX.CHECKSUM_REMAINDER
        check = (target - (checksum % 16)) % 16
        self.hits = hits
        self.check = check

        packets.append(struct.pack(">BB", (check << 4) | byte1_without_check, byte2))
        return packets

# --- Test code ---
if __name__ == "__main__":
    # Test Digimon data
    device1 = Digimon(
        name="Agumon",
        order=0,
        traited=0,
        egg_shake=0,
        index=2,
        hp=6,
        attribute=0,  # Vaccine
        power=50,
        handicap=0,
        buff=0,
        mini_game=5,
        level=5,
        stage=0,
        sick=0,
        shot1=10,
        shot2=15,
        tag_meter=2
    )

    device2 = Digimon(
        name="Gabumon",
        order=0,
        traited=0,
        egg_shake=0,
        index=18,
        hp=6,
        attribute=2,  # Virus
        power=45,
        handicap=0,
        buff=0,
        mini_game=8,
        level=5,
        stage=0,
        sick=0,
        shot1=12,
        shot2=17,
        tag_meter=2
    )

    print("=" * 70)
    print("TESTING ALL BATTLE PROTOCOLS")
    print("=" * 70)
    print()
    
    # NOTE: the maintained protocol test suite lives in
    # tests/test_battle_protocols.py — this block is just a quick smoke run.
    protocol_map = {
        'DM20': BattleProtocol.DM20_BS,
        'DMC': BattleProtocol.DMC_BS,
        'DMX': BattleProtocol.DMX_BS,
        'PEN20': BattleProtocol.PEN20_BS,
    }

    test_results = []

    for protocol_name in protocol_map:
        print(f"{'='*70}")
        print(f"TESTING: {protocol_name}")
        print(f"{'='*70}")

        try:
            # Create simulator with protocol
            simulator = BattleSimulator(protocol=protocol_map[protocol_name], verbose=True)
            
            # Run battle
            result = simulator.simulate(device1, device2)
            
            # Print packet data
            if hasattr(result, 'device1_packets') and result.device1_packets:
                print("\nDevice 1 Packets:")
                for i, packet in enumerate(result.device1_packets, 1):
                    hex_str = ' '.join(f'{b:02X}' for b in packet)
                    bin_str = ' '.join(f'{b:08b}' for b in packet)
                    print(f"  Packet {i}: {hex_str}")
                    print(f"            {bin_str}")
            
            if hasattr(result, 'device2_packets') and result.device2_packets:
                print("\nDevice 2 Packets:")
                for i, packet in enumerate(result.device2_packets, 1):
                    hex_str = ' '.join(f'{b:02X}' for b in packet)
                    bin_str = ' '.join(f'{b:08b}' for b in packet)
                    print(f"  Packet {i}: {hex_str}")
                    print(f"            {bin_str}")
            
            # Print DCom code format (alternating r: and s:)
            if hasattr(result, 'device1_packets') and hasattr(result, 'device2_packets') and result.device1_packets and result.device2_packets:
                # Format: r:packet s:packet r:packet s:packet ... t
                # r: = receive (from device 2), s: = send (from device 1)
                # Packets are already in correct byte order from Device classes
                dcom_parts = []
                max_packets = max(len(result.device1_packets), len(result.device2_packets))
                
                for i in range(max_packets):
                    # Receive from device 2 - direct hex representation
                    if i < len(result.device2_packets):
                        packet = result.device2_packets[i]
                        packet_hex = ''.join(f'{b:02X}' for b in packet)
                        dcom_parts.append(f"r:{packet_hex}")
                    
                    # Send from device 1 - direct hex representation
                    if i < len(result.device1_packets):
                        packet = result.device1_packets[i]
                        packet_hex = ''.join(f'{b:02X}' for b in packet)
                        dcom_parts.append(f"s:{packet_hex}")
                
                dcom_parts.append("t")  # Terminator
                dcom_code = ' '.join(dcom_parts)
                print(f"\nDCom Code: {dcom_code}")
            
            test_results.append((protocol_name, "[OK] SUCCESS"))
            print(f"\n[OK] {protocol_name} test completed successfully!")
            
        except Exception as e:
            test_results.append((protocol_name, f"[FAIL] {str(e)}"))
            print(f"\n[FAIL] {protocol_name} test failed: {str(e)}")
        
        print()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for protocol, status in test_results:
        print(f"{protocol:15s} - {status}")
    print()
    print("=" * 70)
    print("ALL PROTOCOL TESTS COMPLETED!")
    print("=" * 70)
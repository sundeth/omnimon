"""
DCom Battle Simulator - Handles battles with physical Digimon devices via serial.
Follows the same pattern as BattleSimulator but communicates with real hardware.

Protocol-Specific Features:
- DM20 (V_PET): Fixed 5 HP, uses minigame result, 10 packets
- DMX (COLOR): Variable HP per pet, different packet format
- PEN20 (PEN_X): Variable HP per pet, different packet structure
"""
import time
import re
from typing import List, Optional, Dict
from core.combat.dcom.dcom_controller import DComController
from core.combat.dcom.dcom_protocol import ProtocolType
from core.combat.sim.models import Digimon, BattleResult, DigimonStatus
from core.combat.sim.battle_simulator import BattleSimulator, DM20Device, DMCDevice, Pen20Device, DMXDevice
from core import runtime_globals
from core.combat.sim.battle_utils import get_dm20_single_battle_attack_pattern


# Protocol configuration - defines differences between device types
PROTOCOL_CONFIG = {
    ProtocolType.V_PET: {
        "name": "DM20",
        "fixed_hp": 5,           # All Digimon have 5 HP
        "uses_minigame": True,   # Dummy minigame (0-14 taps)
        "minigame_type": "dummy",
        "packet_count": 10,      # Number of packets exchanged
        "display_name": "V-Pet/Pendulum/Progress"
    },
    ProtocolType.COLOR: {
        "name": "DMX",
        "fixed_hp": None,        # HP varies per Digimon (5-bit, max 31)
        "uses_minigame": True,   # XAI Roll + XAI Bar minigame (0-3)
        "minigame_type": "xai",
        "packet_count": 6,       # DMX sends 6 packets
        "display_name": "Digital Monster X"
    },
    ProtocolType.PEN_X: {
        "name": "PEN20",
        "fixed_hp": 5,           # Fixed 5 HP like DM20
        "uses_minigame": True,   # Dummy minigame (0-14 taps)
        "minigame_type": "dummy",
        "packet_count": 10,      # Same packet count as DM20
        "display_name": "Pendulum 20th"
    },
    # Add PENZ as an alias to COLOR with different minigame
    # Note: PENZ uses same packet format as DMX but with count_match minigame
}


class DComBattleSimulator:
    """
    Handles battles with physical Digimon devices via DCom serial communication.
    Sends player's digirom, receives opponent's packets, interprets results.
    """
    
    def __init__(self, dcom_controller: DComController, protocol: ProtocolType, battle_format: str = None):
        """
        Initialize DCom battle simulator.
        
        Args:
            dcom_controller: Active DComController instance for serial communication
            protocol: ProtocolType enum (V_PET, COLOR, PEN_X, etc.)
            battle_format: Optional battle format string ('DM20', 'PEN20', 'DMX', 'PENZ')
                          Used to override protocol detection for special cases like PENZ
        """
        self.dcom_controller = dcom_controller
        self.protocol = protocol
        self.battle_format = battle_format  # Store for later use
        self.config = PROTOCOL_CONFIG.get(protocol, PROTOCOL_CONFIG[ProtocolType.V_PET])
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Initialized for {self.config['display_name']}")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Config: HP={self.config['fixed_hp'] or 'Variable'}, Minigame={self.config['uses_minigame']}")
        if battle_format:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Battle format override: {battle_format}")
        
        # Map protocol types to BattleProtocol enums for internal simulator
        from core.combat.sim.models import BattleProtocol
        self.protocol_map = {
            ProtocolType.V_PET: BattleProtocol.DM20_BS,
            ProtocolType.COLOR: BattleProtocol.DMX_BS,
            ProtocolType.PEN_X: BattleProtocol.PEN20_BS,
        }
        
        # Create internal simulator for packet interpretation
        battle_protocol = self.protocol_map.get(protocol, BattleProtocol.DM20_BS)
        self.internal_simulator = BattleSimulator(battle_protocol)
    
    def get_initial_hp(self, digimon: Optional[Digimon] = None) -> int:
        """
        Get initial HP for a Digimon based on protocol.
        
        Args:
            digimon: Digimon object (used for protocols with variable HP)
            
        Returns:
            Initial HP value
        """
        # PENZ uses variable HP like DMX (not fixed HP like DM20)
        if self.battle_format in ['DMX', 'PENZ']:
            if digimon:
                return digimon.hp
            else:
                return 12  # Default for DMX/PENZ (stage 4 HP)
        
        if self.config['fixed_hp'] is not None:
            return self.config['fixed_hp']
        elif digimon:
            return digimon.hp
        else:
            return 4  # Default fallback
    
    def simulate_with_device(self, player_digimon: Digimon, timeout: float = 30.0) -> Optional[BattleResult]:
        """
        Simulate a battle with a physical device.
        
        Args:
            player_digimon: Player's Digimon data
            timeout: Maximum seconds to wait for device response
            
        Returns:
            BattleResult object, or None if battle failed
        """
        runtime_globals.game_console.log(f"[DComBattleSimulator] Starting {self.protocol.display_name} battle...")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player: {player_digimon.name}, HP={player_digimon.hp}, Power={player_digimon.power}")
        
        try:
            # Step 1: Generate and send player's packets
            player_packets = self._generate_player_packets(player_digimon)
            if not player_packets:
                runtime_globals.game_console.log("[DComBattleSimulator] Failed to generate player packets")
                return None
            
            self._send_packets_to_device(player_packets)
            
            # Step 2: Wait for and receive opponent's packets
            opponent_packets = self._receive_packets_from_device(timeout)
            if not opponent_packets:
                runtime_globals.game_console.log("[DComBattleSimulator] Failed to receive opponent packets")
                return None
            
            # Step 3: Parse opponent data from packets
            opponent_digimon = self._parse_opponent_packets(opponent_packets, player_digimon)
            if not opponent_digimon:
                runtime_globals.game_console.log("[DComBattleSimulator] Failed to parse opponent data")
                return None
            
            # Step 4: Create BattleResult from exchanged packets
            result = self._build_battle_result(player_digimon, opponent_digimon, player_packets, opponent_packets)
            
            # Step 5: Print battle log (like other simulators do)
            if result:
                runtime_globals.game_console.log("[DComBattleSimulator] Battle complete!")
                self.internal_simulator.print_battle_log(result)
                
                # Print DCom code format for validation
                self._print_dcom_code(result)
            else:
                runtime_globals.game_console.log("[DComBattleSimulator] Failed to build battle result")
            
            return result
            
        except Exception as e:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Battle error: {e}")
            import traceback
            runtime_globals.game_console.log(traceback.format_exc())
            return None
    
    def _generate_player_packets(self, digimon: Digimon) -> Optional[List[bytes]]:
        """Generate packets from player's Digimon data."""
        runtime_globals.game_console.log(f"[DComBattleSimulator] Generating {self.protocol.display_name} packets...")
        
        try:
            if self.protocol == ProtocolType.V_PET:
                # DM20 V-Pet protocol
                device = DM20Device(digimon)
                packets = device.generate_all_packets_for_dcom(order=0)  # order=0 for V2 listen-and-reply
                
            elif self.protocol == ProtocolType.COLOR:
                # DMX/Color protocol
                device = DMXDevice(digimon)
                packets = device.generate_all_packets_for_dcom()
                
            elif self.protocol == ProtocolType.PEN_X:
                # Pendulum X protocol
                device = Pen20Device(digimon)
                packets = device.generate_all_packets_for_dcom()
                
            else:
                runtime_globals.game_console.log(f"[DComBattleSimulator] Unsupported protocol: {self.protocol}")
                return None
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] Generated {len(packets)} packets:")
            for i, pkt in enumerate(packets, 1):
                runtime_globals.game_console.log(f"  Packet {i}: {pkt.hex().upper()}")
            
            return packets
            
        except Exception as e:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Packet generation error: {e}")
            import traceback
            runtime_globals.game_console.log(traceback.format_exc())
            return None
    
    def _send_packets_to_device(self, packets: List[bytes]):
        """Send packets to physical device via DCom."""
        runtime_globals.game_console.log("[DComBattleSimulator] Sending packets to device...")
        
        # Format command based on protocol
        hex_packets = [pkt.hex().upper() for pkt in packets]
        
        if self.protocol == ProtocolType.V_PET:
            # V2 command for DM20
            command = f"V2-" + "-".join(hex_packets)
        else:
            # Other protocols may use different commands
            command = f"V2-" + "-".join(hex_packets)
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Sending command: {command}")
        self.dcom_controller._send_raw(command + '\r')
    
    def _receive_packets_from_device(self, timeout: float) -> Optional[List[str]]:
        """Receive battle packets from physical device."""
        runtime_globals.game_console.log("[DComBattleSimulator] Waiting for device response packets...")
        
        responses = []
        start_time = time.time()
        
        # Expected packet count by protocol
        expected_packets = {
            ProtocolType.V_PET: 10,  # DM20 sends 10 packets
            ProtocolType.COLOR: 6,   # DMX sends 6 packets
            ProtocolType.PEN_X: 10,  # PEN20 sends 10 packets
        }
        expected_count = expected_packets.get(self.protocol, 10)
        
        while time.time() - start_time < timeout:
            if self.dcom_controller.serial_port.in_waiting > 0:
                line = self.dcom_controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if line and not line.startswith('t:'):  # Skip status messages
                    runtime_globals.game_console.log(f"[DComBattleSimulator] Received: {line}")
                    
                    # Look for r:[hex] patterns (received packets from device)
                    matches = re.findall(r'r:[0-9A-Fa-f]{4,8}', line)
                    if matches:
                        for match in matches:
                            hex_data = match[2:]  # Strip 'r:' prefix
                            responses.append(hex_data)
                            runtime_globals.game_console.log(f"  Battle packet {len(responses)}/{expected_count}: {hex_data}")
                        
                        if len(responses) >= expected_count:
                            break
            
            time.sleep(0.05)  # Small delay to avoid busy-waiting
        
        if len(responses) < 4:  # Minimum viable packets
            runtime_globals.game_console.log(f"[DComBattleSimulator] Insufficient packets: {len(responses)}/{expected_count}")
            return None
        
        # Check for duplicate packets (some DCom firmware sends packets 1-4 twice in positions 5-8)
        if len(responses) >= 8 and expected_count == 10:
            if responses[0] == responses[4] and responses[1] == responses[5]:
                runtime_globals.game_console.log("[DComBattleSimulator] WARNING: Detected duplicate packets (firmware bug)")
                runtime_globals.game_console.log("[DComBattleSimulator] Some packet data may be missing or invalid")
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Received {len(responses)} packets")
        return responses
    
    def _parse_opponent_packets(self, packets: List[str], player_digimon: Digimon) -> Optional[Digimon]:
        """Parse opponent's Digimon data from received packets."""
        runtime_globals.game_console.log("[DComBattleSimulator] Parsing opponent data from packets...")
        
        try:
            # Convert hex strings to bytes
            packet_bytes = [bytes.fromhex(pkt) for pkt in packets]
            
            # Validate packets before parsing
            if not self._validate_packets(packet_bytes):
                runtime_globals.game_console.log("[DComBattleSimulator] ERROR: Packet validation failed!")
                self._send_error_to_device()
                return None
            
            # Check for battle_format override (e.g., PENZ uses DMX format)
            if self.battle_format == 'PENZ':
                return self._parse_dmx_opponent(packet_bytes)
            elif self.battle_format == 'DMX':
                return self._parse_dmx_opponent(packet_bytes)
            elif self.protocol == ProtocolType.V_PET:
                return self._parse_dm20_opponent(packet_bytes)
            elif self.protocol == ProtocolType.COLOR:
                return self._parse_dmx_opponent(packet_bytes)
            elif self.protocol == ProtocolType.PEN_X:
                return self._parse_pen20_opponent(packet_bytes)
            else:
                runtime_globals.game_console.log(f"[DComBattleSimulator] Unknown protocol: {self.protocol}")
                return None
                
        except Exception as e:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Parse error: {e}")
            import traceback
            runtime_globals.game_console.log(traceback.format_exc())
            self._send_error_to_device()
            return None
    
    def _validate_packets(self, packets: List[bytes]) -> bool:
        """Validate packet EOL markers and checksum."""
        # Check for battle_format override (e.g., PENZ uses DMX format)
        if self.battle_format in ['DMX', 'PENZ']:
            return self._validate_dmx_packets(packets)
        elif self.protocol == ProtocolType.V_PET:
            return self._validate_dm20_packets(packets)
        elif self.protocol == ProtocolType.COLOR:
            return self._validate_dmx_packets(packets)
        elif self.protocol == ProtocolType.PEN_X:
            return self._validate_pen20_packets(packets)
        return True  # Unknown protocol, skip validation
    
    def _validate_dm20_packets(self, packets: List[bytes]) -> bool:
        """Validate DM20 packets: EOL markers and checksum."""
        if len(packets) < 10:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Validation failed: expected 10 packets, got {len(packets)}")
            return False
        
        # Check EOL markers (should be 0xE = 1110 in last 4 bits of byte 2 for most packets)
        # Packets 3-10 should have EOL
        expected_eol = 0xE
        for i in range(2, 10):  # Packets 3-10 (0-indexed: 2-9)
            eol = packets[i][1] & 0x0F  # Last 4 bits of byte 2
            if eol != expected_eol:
                runtime_globals.game_console.log(f"[DComBattleSimulator] Validation failed: Packet {i+1} has invalid EOL: 0x{eol:X} (expected 0x{expected_eol:X})")
                return False
        
        # Validate checksum in Packet A (packet 10)
        checksum = 0
        for pkt in packets[:10]:  # All 10 packets
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F  # Upper nibble
                checksum += byte & 0x0F          # Lower nibble
        
        if (checksum % 16) != 0:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Validation failed: Invalid checksum (sum % 16 = {checksum % 16}, expected 0)")
            return False
        
        runtime_globals.game_console.log("[DComBattleSimulator] Packet validation passed")
        return True
    
    def _validate_dmx_packets(self, packets: List[bytes]) -> bool:
        """Validate DMX packets: EOL markers and checksum."""
        if len(packets) < 6:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Validation failed: expected 6 packets, got {len(packets)}")
            return False
        
        # Check EOL markers in all 6 packets
        expected_eol = 0xE
        for i in range(6):
            eol = packets[i][1] & 0x0F  # Last 4 bits
            if eol != expected_eol:
                runtime_globals.game_console.log(f"[DComBattleSimulator] Validation failed: DMX Packet {i+1} has invalid EOL: 0x{eol:X}")
                return False
        
        # Validate checksum in Packet 6 (sum % 16 should equal 8)
        checksum = 0
        for pkt in packets[:6]:
            for byte in pkt:
                checksum += (byte >> 4) & 0x0F
                checksum += byte & 0x0F
        
        # Subtract the check nibble from packet 6 and recalculate
        check_nibble = (packets[5][0] >> 4) & 0x0F
        checksum -= check_nibble
        
        if ((checksum + check_nibble) % 16) != 8:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Validation failed: Invalid DMX checksum")
            return False
        
        runtime_globals.game_console.log("[DComBattleSimulator] DMX packet validation passed")
        return True
    
    def _validate_pen20_packets(self, packets: List[bytes]) -> bool:
        """Validate PEN20 packets: EOL markers and checksum."""
        # PEN20 uses same structure as DM20
        return self._validate_dm20_packets(packets)
    
    def _send_error_to_device(self):
        """Send error response to DCom device."""
        try:
            # Send FF00 error code to device
            error_command = "FF00"
            runtime_globals.game_console.log(f"[DComBattleSimulator] Sending error to device: {error_command}")
            self.dcom_controller._send_raw(error_command + '\r')
        except Exception as e:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Failed to send error to device: {e}")
    
    def _parse_dm20_opponent(self, packets: List[bytes]) -> Optional[Digimon]:
        """Parse DM20 (V-Pet) protocol opponent data."""
        # DM20 packet structure (10 packets):
        # Packet 1: Name 2, Name 1
        # Packet 2: Name 4, Name 3
        # Packet 3: Order | Attack (pattern) | Operation | Version | EOL
        # Packet 4: COU | Index L | Attribute L | EOL
        # Packet 5: Shot S L | Shot W L | EOL
        # Packet 6: COU | Power L | EOL
        # Packet 7: COU | Index R | Attribute R | EOL
        # Packet 8: Shot S R | Shot W R | EOL
        # Packet 9: Tag Meter | Power R | EOL
        # Packet 10: Check | Dodges | Hits | EOL
        
        if len(packets) < 10:
            runtime_globals.game_console.log(f"[DComBattleSimulator] Incomplete DM20 packets: {len(packets)}/10")
            return None
        
        try:
            # Parse packet 3: Order, Attack pattern, Operation, Version
            pkt3 = packets[2]
            pattern_index = (pkt3[0] >> 2) & 0x1F  # Bits 2-6 of byte 0 = pattern (5 bits)
            operation = pkt3[0] & 0x03  # Bits 0-1 of byte 0 = operation (2 bits)
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] Pattern index: {pattern_index}, Operation: {operation}")
            
            # Parse packet 4: Index and Attribute  
            pkt4 = packets[3]
            opponent_attribute = (pkt4[0] >> 4) & 0x0F  # Upper 4 bits
            
            # Parse packet 6: Power (packet 7 in 1-indexed)
            pkt6 = packets[5]
            opponent_power = pkt6[1] & 0x0F       # Lower 4 bits of byte 1
            
            # Parse packet 8: Shot S (attack sprites) - actual attack pattern values
            pkt8 = packets[7]
            shot1 = (pkt8[0] >> 4) & 0x0F  # Upper 4 bits = Shot S L (left/main shot)
            shot2 = pkt8[0] & 0x0F         # Lower 4 bits = Shot W L (wide/alt shot) 
            
            # Parse packet 9: Tag meter (for tag battles) and Power R
            pkt9 = packets[8]
            tag_meter = (pkt9[0] >> 4) & 0x0F  # Upper 4 bits = tag meter
            
            # Map attribute to name
            attr_to_name = {0: "Va", 1: "Da", 2: "Vi", 3: "Fr"}
            opponent_name = attr_to_name.get(opponent_attribute, "Opponent")
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent: {opponent_name}, Attr={opponent_attribute}, Power={opponent_power}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent shots: shot1={shot1}, shot2={shot2}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] Tag meter: {tag_meter}, Pattern: {pattern_index}")
            
            # Create opponent Digimon with parsed data
            opponent = Digimon(
                name=opponent_name,
                order=1,
                traited=0,
                egg_shake=0,
                index=0,
                hp=4,  # DM20 always uses 4 HP
                attribute=opponent_attribute,
                power=opponent_power * 10,  # Scale power (protocol uses 0-15)
                handicap=0,
                buff=0,
                mini_game=pattern_index,  # Store pattern index in mini_game field for battle simulation
                level=1,
                stage=3,
                sick=0,
                shot1=shot1,  # Parsed from packet 8
                shot2=shot2,  # Parsed from packet 8
                tag_meter=tag_meter  # Tag meter value for pattern calculation
            )
            
            return opponent
            
        except Exception as e:
            runtime_globals.game_console.log(f"[DComBattleSimulator] DM20 parse error: {e}")
            import traceback
            runtime_globals.game_console.log(traceback.format_exc())
            return None
    
    def _parse_dmx_opponent(self, packets: List[bytes]) -> Optional[Digimon]:
        """
        Parse DMX (Color) protocol opponent data from packets.
        
        DMX Packet Format:
        Packet 1: Order(1) Level(4) Sick(1) Attack(2) Version(4) EOL(4)
        Packet 2: Stage(3) Index(7) Attribute(2) EOL(4)
        Packet 3: Shot_S(6) Shot_W(6) EOL(4)
        Packet 4: COU(2) HP(5) Shot_M(5) EOL(4)
        Packet 5: COU(2) Buff(2) Power(8) EOL(4)
        Packet 6: Check(4) COU(3) Hits(5) EOL(4)
        """
        try:
            if len(packets) < 6:
                runtime_globals.game_console.log(f"[DComBattleSimulator] DMX parse error: Need 6 packets, got {len(packets)}")
                return None
            
            # Packet 1: Order(1) Level(4) Sick(1) Attack(2) Version(4) EOL(4)
            pkt1 = packets[0]
            order = (pkt1[0] >> 7) & 0x1
            level = (pkt1[0] >> 3) & 0xF  # 4 bits
            sick = (pkt1[0] >> 2) & 0x1
            attack = pkt1[0] & 0x3  # 2 bits (0-3)
            version = (pkt1[1] >> 4) & 0xF
            
            # Packet 2: Stage(3) Index(7) Attribute(2) EOL(4)
            pkt2 = packets[1]
            stage = (pkt2[0] >> 5) & 0x7  # 3 bits
            index = ((pkt2[0] & 0x1F) << 2) | ((pkt2[1] >> 6) & 0x3)  # 7 bits
            attribute = (pkt2[1] >> 4) & 0x3  # 2 bits
            
            # Packet 3: Shot_S(6) Shot_W(6) EOL(4)
            pkt3 = packets[2]
            shot_s = (pkt3[0] >> 2) & 0x3F  # 6 bits
            shot_w = ((pkt3[0] & 0x3) << 4) | ((pkt3[1] >> 4) & 0xF)  # 6 bits
            
            # Packet 4: COU(2) HP(5) Shot_M(5) EOL(4)
            pkt4 = packets[3]
            hp = (pkt4[0] >> 1) & 0x1F  # 5 bits
            shot_m = ((pkt4[0] & 0x1) << 4) | ((pkt4[1] >> 4) & 0xF)  # 5 bits
            
            # Packet 5: COU(2) Buff(2) Power(8) EOL(4)
            pkt5 = packets[4]
            buff = (pkt5[0] >> 4) & 0x3  # 2 bits
            power = ((pkt5[0] & 0xF) << 4) | ((pkt5[1] >> 4) & 0xF)  # 8 bits
            
            # Packet 6: Check(4) COU(3) Hits(5) EOL(4)
            pkt6 = packets[5]
            check = (pkt6[0] >> 4) & 0xF  # 4 bits
            cou_6 = (pkt6[0] >> 1) & 0x7  # 3 bits
            hits = ((pkt6[0] & 0x1) << 4) | ((pkt6[1] >> 4) & 0xF)  # 5 bits
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] DMX parsed: order={order}, level={level}, sick={sick}, attack={attack}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] DMX parsed: stage={stage}, index={index}, attr={attribute}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] DMX parsed: shot_s={shot_s}, shot_w={shot_w}, shot_m={shot_m}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] DMX parsed: hp={hp}, buff={buff}, power={power}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] DMX parsed: check={check}, hits=0b{hits:05b} ({hits})")
            
            # Map attribute to name (same as DM20)
            attr_to_name = {0: "Va", 1: "Da", 2: "Vi", 3: "Fr"}
            opponent_name = attr_to_name.get(attribute, "DMX Opponent")
            
            opponent = Digimon(
                name=opponent_name,
                order=order,
                traited=0,
                egg_shake=0,
                index=index,
                hp=hp,
                attribute=attribute,
                power=power,
                handicap=0,
                buff=buff,
                mini_game=attack,  # Attack quality 0-3
                level=level,
                stage=stage,
                sick=sick,
                shot1=shot_s,
                shot2=shot_w,
                tag_meter=0
            )
            
            # Store parsed hits for later use in battle simulation
            opponent.dmx_hits = hits
            opponent.dmx_shot_m = shot_m
            
            return opponent
            
        except Exception as e:
            runtime_globals.game_console.log(f"[DComBattleSimulator] DMX parse error: {e}")
            import traceback
            runtime_globals.game_console.log(traceback.format_exc())
            return None
    
    def _parse_pen20_opponent(self, packets: List[bytes]) -> Optional[Digimon]:
        """Parse PEN20 (Pendulum 20th) protocol opponent data.
        
        Uses same attribute-based naming as DM20 (Va, Da, Vi, Fr).
        """
        try:
            if len(packets) < 10:
                runtime_globals.game_console.log(f"[DComBattleSimulator] PEN20 parse error: Need 10 packets, got {len(packets)}")
                return None
            
            # Packet 2: COU(2) Index(8) Attribute(2) EOL(4)
            pkt2 = packets[1]
            index = ((pkt2[0] & 0x3F) << 2) | ((pkt2[1] >> 6) & 0x3)
            attribute = (pkt2[1] >> 4) & 0x3
            
            # Packet 4: Sick(1) COU(3) Shot_S(8) EOL(4)
            pkt4 = packets[3]
            sick = (pkt4[0] >> 7) & 0x1
            shot_s = ((pkt4[0] & 0xF) << 4) | ((pkt4[1] >> 4) & 0xF)
            
            # Packet 5: COU(2) Traited(1) Egg_Shake(1) Power(8) EOL(4)
            pkt5 = packets[4]
            traited = (pkt5[0] >> 5) & 0x1
            egg_shake = (pkt5[0] >> 4) & 0x1
            power = ((pkt5[0] & 0xF) << 4) | ((pkt5[1] >> 4) & 0xF)
            
            # Map attribute to name (same as DM20)
            attr_to_name = {0: "Va", 1: "Da", 2: "Vi", 3: "Fr"}
            opponent_name = attr_to_name.get(attribute, "PEN20 Opponent")
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] PEN20 parsed: name={opponent_name}, attr={attribute}, power={power}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] PEN20 parsed: sick={sick}, traited={traited}, egg_shake={egg_shake}")
            
            opponent = Digimon(
                name=opponent_name,
                order=1,
                traited=traited,
                egg_shake=egg_shake,
                index=index,
                hp=5,  # PEN20 uses fixed 5 HP
                attribute=attribute,
                power=power,
                handicap=0,
                buff=0,
                mini_game=3,
                level=1,
                stage=3,
                sick=sick,
                shot1=shot_s,
                shot2=shot_s,
                tag_meter=2
            )
            
            return opponent
            
        except Exception as e:
            runtime_globals.game_console.log(f"[DComBattleSimulator] PEN20 parse error: {e}")
            import traceback
            runtime_globals.game_console.log(traceback.format_exc())
            return None
    
    def _build_battle_result(self, player: Digimon, opponent: Digimon, 
                           player_packets: List[bytes], opponent_packets: List[str]) -> Optional[BattleResult]:
        """Build BattleResult from exchanged packets with turn-by-turn battle log."""
        runtime_globals.game_console.log("[DComBattleSimulator] Building battle result...")
        
        try:
            # Convert opponent hex strings to bytes for consistency
            opponent_bytes = [bytes.fromhex(pkt) for pkt in opponent_packets]
            
            # For DM20 protocol, extract hits/dodges from packet 10 (packet A)
            if self.protocol == ProtocolType.V_PET and len(opponent_bytes) >= 10 and len(player_packets) >= 10:
                battle_log = self._simulate_dm20_turns(player, opponent, player_packets, opponent_bytes)
            elif self.protocol == ProtocolType.COLOR and len(opponent_bytes) >= 6 and len(player_packets) >= 6:
                # DMX/PENZ protocol - extract hits from packet 6
                battle_log = self._simulate_dmx_turns(player, opponent, player_packets, opponent_bytes)
            elif self.protocol == ProtocolType.PEN_X and len(opponent_bytes) >= 10 and len(player_packets) >= 10:
                # PEN20 uses same turn simulation as DM20
                battle_log = self._simulate_dm20_turns(player, opponent, player_packets, opponent_bytes)
            else:
                # For other protocols or incomplete data, create empty log
                battle_log = []
                runtime_globals.game_console.log("[DComBattleSimulator] WARNING: No turn data available")
            
            # Calculate final HP based on battle log and protocol
            # Use protocol-specific initial HP, not the Digimon's HP field
            player_hp = self.get_initial_hp(player)
            opponent_hp = self.get_initial_hp(opponent)
            
            if battle_log:
                # Use final turn status (device1=opponent, device2=player)
                final_turn = battle_log[-1]
                opponent_hp = final_turn.device1_status[0].hp
                player_hp = final_turn.device2_status[0].hp
            
            # Determine winner from HP (device1=opponent, device2=player)
            if opponent_hp > player_hp:
                winner = "device1"  # Opponent won
            elif player_hp > opponent_hp:
                winner = "device2"  # Player won
            else:
                # Tie (same HP): DCom device (initiator) wins ties
                # device1 = DCom (opponent), device2 = Pet (player)
                winner = "device1"  # DCom wins ties - battle initiator advantage
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] Final HP: opponent={opponent_hp}, player={player_hp}, Winner: {winner}")
            
            # Create BattleResult (device1=opponent, device2=player)
            result = BattleResult(
                winner=winner,
                device1_final=[DigimonStatus(
                    name=opponent.name,
                    hp=opponent_hp,
                    alive=opponent_hp > 0
                )],
                device2_final=[DigimonStatus(
                    name=player.name,
                    hp=player_hp,
                    alive=player_hp > 0
                )],
                battle_log=battle_log,
                device1_packets=opponent_bytes,
                device2_packets=player_packets
            )
            
            return result
            
        except Exception as e:
            error_msg = f"[DComBattleSimulator] Result build error: {e}"
            runtime_globals.game_console.log(error_msg)
            import traceback
            trace = traceback.format_exc()
            runtime_globals.game_console.log(trace)
            return None
    
    def _simulate_dm20_turns(self, player: Digimon, opponent: Digimon, 
                            player_packets: List[bytes], opponent_packets: List[bytes]):
        """Simulate turn-by-turn battle from DM20 packet A hits/dodges."""
        from core.combat.sim.models import TurnLog, AttackLog, DigimonStatus
        from core.combat.sim.battle_utils import get_dm20_single_battle_attack_pattern
        
        runtime_globals.game_console.log("[DComBattleSimulator] Simulating DM20 battle turns...")
        
        # Extract packet A (packet 10) from both devices
        player_pktA = player_packets[9]   # Our packet A
        opponent_pktA = opponent_packets[9]  # Device's packet A
        
        # Extract hits from Packet A
        # Per DMCom protocol (dm20.py BattleOrCopyView):
        #   Packet 10 as 16-bit value (big-endian): CCCC HHHH YYYY EEEE
        #   - Check = bits 12-15 (>> 12)
        #   - hit_me = bits 8-11 ((>> 8) & 0xF) = which of MY attacks HIT YOU
        #   - hit_you = bits 4-7 ((>> 4) & 0xF) = which of YOUR attacks HIT ME
        #   - EOL = bits 0-3
        #
        # As bytes: Byte0 = CCCC HHHH (Check | hit_me), Byte1 = YYYY EEEE (hit_you | EOL)
        # 
        # For opponent's packet:
        #   opponent.hit_you = which of opponent's attacks HIT US (we take damage)
        #   opponent.hit_me = which of OUR attacks HIT OPPONENT (they take damage)
        
        opponent_hit_you = (opponent_pktA[1] >> 4) & 0x0F  # Upper 4 bits of byte 1 = their hits on us
        opponent_hit_me = opponent_pktA[0] & 0x0F         # Lower 4 bits of byte 0 = our hits on them
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent PacketA: hit_you=0x{opponent_hit_you:X} (their hits on us), hit_me=0x{opponent_hit_me:X} (our hits on them)")
        
        # Convert to bit arrays (bit 0 = turn 1, bit 1 = turn 2, etc)
        # opponent_attack_hits: whether opponent's attack HIT us this turn (1=we take damage)
        # player_attack_hits: whether OUR attack HIT opponent (1=they take damage)
        opponent_attack_hits = [(opponent_hit_you >> i) & 1 for i in range(4)]
        player_attack_hits = [(opponent_hit_me >> i) & 1 for i in range(4)]  # Direct hit indicator, NOT inverted!
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent hits us (per turn): {opponent_attack_hits}")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player hits opponent (per turn): {player_attack_hits}")
        
        # Extract player's pattern index from player_packets[2] (Packet 3)
        # Packet 3 format: Order(1) | Pattern(5) | Operation(2) | Version(4) | EOL(4)
        # Pattern bits are (byte0 >> 2) & 0x1F
        player_pkt3 = player_packets[2]
        player_pattern_index = (player_pkt3[0] >> 2) & 0x1F
        player_pattern = get_dm20_single_battle_attack_pattern(player_pattern_index)
        
        # Extract opponent's pattern index from opponent_packets[2] (Packet 3)
        opponent_pkt3 = opponent_packets[2]
        opponent_pattern_index = (opponent_pkt3[0] >> 2) & 0x1F
        opponent_pattern = get_dm20_single_battle_attack_pattern(opponent_pattern_index)
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player pattern (index {player_pattern_index}): {player_pattern}")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent pattern (index {opponent_pattern_index}): {opponent_pattern}")
        
        # Initialize HP (DM20 uses 5 HP)
        player_hp = 5
        opponent_hp = 5
        battle_log = []
        
        # Determine attack order based on Order field from Packet 3
        # Extract order from player's packet 3 (byte 0, bit 7)
        player_order = (player_packets[2][0] >> 7) & 1
        opponent_order = (opponent_packets[2][0] >> 7) & 1
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player order={player_order}, Opponent order={opponent_order}")
        
        # Order=1 means initiating (attacks first), Order=0 means replying (attacks second)
        opponent_attacks_first = (opponent_order > player_order)
        
        # DM20 has 5 turns (attacks) but only 4 hit bits in Packet A
        # Turn 5 uses turn 1's pattern value and hit result (wraps to index 0)
        for turn in range(5):
            attack_index = turn % 4  # Pattern index (wraps for turn 5)
            hit_index = turn if turn < 4 else 0  # Hit bit index (turn 5 uses turn 1's bit)
            
            if opponent_attacks_first:
                # Opponent attacks first
                opponent_hit = opponent_attack_hits[hit_index]
                opponent_attack = opponent_pattern[attack_index]
                player_damage = opponent_attack if opponent_hit else 0
                player_hp = max(0, player_hp - player_damage)
                
                # Player attacks second
                player_hit = player_attack_hits[hit_index]
                player_attack = player_pattern[attack_index]
                opponent_damage = player_attack if player_hit else 0
                opponent_hp = max(0, opponent_hp - opponent_damage)
                
                runtime_globals.game_console.log(f"[DComBattleSimulator] Turn {turn+1}: Opponent hit={bool(opponent_hit)} dmg={player_damage}, Player hit={bool(player_hit)} dmg={opponent_damage}")
            else:
                # Player attacks first
                player_hit = player_attack_hits[hit_index]
                player_attack = player_pattern[attack_index]
                opponent_damage = player_attack if player_hit else 0
                opponent_hp = max(0, opponent_hp - opponent_damage)
                
                # Opponent attacks second
                opponent_hit = opponent_attack_hits[hit_index]
                opponent_attack = opponent_pattern[attack_index]
                player_damage = opponent_attack if opponent_hit else 0
                player_hp = max(0, player_hp - player_damage)
                
                runtime_globals.game_console.log(f"[DComBattleSimulator] Turn {turn+1}: Player hit={bool(player_hit)} dmg={opponent_damage}, Opponent hit={bool(opponent_hit)} dmg={player_damage}")
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] Turn {turn+1} HP: Player {player_hp}, Opponent {opponent_hp}")
            
            # Log the turn (device1=opponent, device2=player)
            # IMPORTANT: Store the ATTACK PATTERN VALUE (what attack was attempted), not dealt damage
            # The battle scene needs to know the attack type (1=weak, 2=strong) even on misses
            # The 'hit' field indicates whether the attack connected
            turn_log = TurnLog(
                turn=turn + 1,
                device1_status=[DigimonStatus(name=opponent.name, hp=opponent_hp, alive=opponent_hp > 0)],
                device2_status=[DigimonStatus(name=player.name, hp=player_hp, alive=player_hp > 0)],
                attacks=[
                    AttackLog(turn=turn+1, device="device1", attacker=0, defender=0, hit=bool(opponent_hit), damage=opponent_attack),
                    AttackLog(turn=turn+1, device="device2", attacker=0, defender=0, hit=bool(player_hit), damage=player_attack)
                ]                    
            )
            battle_log.append(turn_log)
            
            # End battle if one is defeated (but still complete current turn's log entry)
            if player_hp == 0 or opponent_hp == 0:
                runtime_globals.game_console.log(f"[DComBattleSimulator] Battle ended after turn {turn+1}")
                break
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Battle complete with {len(battle_log)} turns")
        return battle_log

    def _simulate_dmx_turns(self, player: Digimon, opponent: Digimon, 
                           player_packets: List[bytes], opponent_packets: List[bytes]):
        """
        Simulate turn-by-turn battle from DMX/PENZ packet 6 hits.
        
        DMX Battle System:
        - 5 rounds total
        - Each side has 5 hit bits indicating which attacks landed
        - Attack pattern determined by: Level + minigame result (0-3)
        - Attack types: 1=SINGLE_WEAK, 2=SINGLE_STRONG, 3=DOUBLE_WEAK, 4=DOUBLE_STRONG, 5=CRITICAL
        - Pattern value is base damage (1-5), plus buff bonus (0-2), plus level attack bonus (0-2)
        - Level bonuses: +1 attack at level 4, +1 attack at level 7
        - Winner is whoever has more HP at end (ties freeze device, we give to initiator)
        """
        from core.combat.sim.models import TurnLog, AttackLog, DigimonStatus
        from core.combat.sim.battle_utils import get_attack_pattern
        
        runtime_globals.game_console.log("[DComBattleSimulator] Simulating DMX battle turns...")
        
        # Extract hits from Packet 6 for both devices
        # Packet 6 format: Check(4) COU(3) Hits(5) EOL(4)
        player_pkt6 = player_packets[5]
        opponent_pkt6 = opponent_packets[5]
        
        # Extract 5-bit hits from packet 6
        # Hits is in bits 4-8 (5 bits), spanning bytes 0-1
        player_hits = ((player_pkt6[0] & 0x1) << 4) | ((player_pkt6[1] >> 4) & 0xF)
        opponent_hits = ((opponent_pkt6[0] & 0x1) << 4) | ((opponent_pkt6[1] >> 4) & 0xF)
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player hits: 0b{player_hits:05b} ({player_hits})")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent hits: 0b{opponent_hits:05b} ({opponent_hits})")
        
        # Convert to bit arrays (bit 0 = turn 1, bit 1 = turn 2, etc - read right to left)
        player_hit_bits = [(player_hits >> i) & 1 for i in range(5)]
        opponent_hit_bits = [(opponent_hits >> i) & 1 for i in range(5)]
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player hit per turn (1-5): {player_hit_bits}")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent hit per turn (1-5): {opponent_hit_bits}")
        
        # Extract level and mini_game from Packet 1 for both sides
        # Packet 1: Order(1) Level(4) Sick(1) Attack(2) Version(4) EOL(4)
        player_pkt1 = player_packets[0]
        opponent_pkt1 = opponent_packets[0]
        
        player_level = (player_pkt1[0] >> 3) & 0xF
        player_mini_game = player_pkt1[0] & 0x3  # Attack quality 0-3
        opponent_level = (opponent_pkt1[0] >> 3) & 0xF
        opponent_mini_game = opponent_pkt1[0] & 0x3  # Attack quality 0-3
        
        # DMX level field is 0-indexed (0=Lvl.1, 6=Lvl.7, etc.), add 1 for table lookup
        # Ensure level is in valid range (1-10) after adjustment
        player_level = max(1, min(10, player_level + 1))
        opponent_level = max(1, min(10, opponent_level + 1))
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player: level={player_level}, mini_game={player_mini_game}")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent: level={opponent_level}, mini_game={opponent_mini_game}")
        
        # Get attack patterns based on level and minigame result
        # Pattern values: 1=SINGLE_WEAK, 2=SINGLE_STRONG, 3=DOUBLE_WEAK, 4=DOUBLE_STRONG, 5=CRITICAL
        # Pattern value is the base damage (1-5)
        player_pattern = get_attack_pattern(player_level, player_mini_game, "DMX")
        opponent_pattern = get_attack_pattern(opponent_level, opponent_mini_game, "DMX")
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player attack pattern: {player_pattern}")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Opponent attack pattern: {opponent_pattern}")
        
        # Calculate attack bonuses from level (cumulative)
        # Level 4: +1 Attack, Level 7: +1 Attack (total possible: +2)
        player_attack_bonus = (1 if player_level >= 4 else 0) + (1 if player_level >= 7 else 0)
        opponent_attack_bonus = (1 if opponent_level >= 4 else 0) + (1 if opponent_level >= 7 else 0)
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Attack bonus - Player: {player_attack_bonus}, Opponent: {opponent_attack_bonus}")
        
        # Get buff values from Packet 5: COU(2) Buff(2) Power(8) EOL(4)
        player_pkt5 = player_packets[4]
        opponent_pkt5 = opponent_packets[4]
        player_buff = (player_pkt5[0] >> 4) & 0x3
        opponent_buff = (opponent_pkt5[0] >> 4) & 0x3
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Player buff: {player_buff}, Opponent buff: {opponent_buff}")
        
        # Get initial HP from packet 4 for both sides
        # Packet 4: COU(2) HP(5) Shot_M(5) EOL(4)
        player_pkt4 = player_packets[3]
        opponent_pkt4 = opponent_packets[3]
        player_hp = (player_pkt4[0] >> 1) & 0x1F
        opponent_hp = (opponent_pkt4[0] >> 1) & 0x1F
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Initial HP - Player: {player_hp}, Opponent: {opponent_hp}")
        
        # Determine attack order from Packet 1
        # Order = 0 means device1/replying (attacks second), Order = 1 means initiating (attacks first)
        player_order = (player_packets[0][0] >> 7) & 1
        opponent_order = (opponent_packets[0][0] >> 7) & 1
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] Order - Player: {player_order}, Opponent: {opponent_order}")
        
        # Order=1 means initiating (attacks first), Order=0 means replying (attacks second)
        opponent_attacks_first = opponent_order == 1
        
        battle_log = []
        
        # DMX has 5 rounds
        for turn in range(5):
            # Get attack type for this turn from patterns (1-5 damage value)
            player_attack_type = player_pattern[turn] if turn < len(player_pattern) else 1
            opponent_attack_type = opponent_pattern[turn] if turn < len(opponent_pattern) else 1
            
            # Pattern value IS the base damage (1-5)
            # Add buff (max 2) and attack bonus from level
            player_damage_value = player_attack_type + min(2, player_buff) + player_attack_bonus
            opponent_damage_value = opponent_attack_type + min(2, opponent_buff) + opponent_attack_bonus
            
            if opponent_attacks_first:
                # Opponent attacks first
                opponent_hit = opponent_hit_bits[turn]
                player_damage = opponent_damage_value if opponent_hit else 0
                player_hp = max(0, player_hp - player_damage)
                
                # Player attacks second
                player_hit = player_hit_bits[turn]
                opponent_damage = player_damage_value if player_hit else 0
                opponent_hp = max(0, opponent_hp - opponent_damage)
            else:
                # Player attacks first
                player_hit = player_hit_bits[turn]
                opponent_damage = player_damage_value if player_hit else 0
                opponent_hp = max(0, opponent_hp - opponent_damage)
                
                # Opponent attacks second
                opponent_hit = opponent_hit_bits[turn]
                player_damage = opponent_damage_value if opponent_hit else 0
                player_hp = max(0, player_hp - player_damage)
            
            runtime_globals.game_console.log(f"[DComBattleSimulator] Turn {turn+1}: Player atk_type={player_attack_type} hit={player_hit} dmg={player_damage_value}, Opponent atk_type={opponent_attack_type} hit={opponent_hit} dmg={opponent_damage_value}")
            runtime_globals.game_console.log(f"[DComBattleSimulator] Turn {turn+1} HP: Player {player_hp}, Opponent {opponent_hp}")
            
            # Log the turn (device1=opponent, device2=player for BattleEncounter remapping)
            # Store attack_type in damage field for animation lookup
            turn_log = TurnLog(
                turn=turn + 1,
                device1_status=[DigimonStatus(name=opponent.name, hp=opponent_hp, alive=opponent_hp > 0)],
                device2_status=[DigimonStatus(name=player.name, hp=player_hp, alive=player_hp > 0)],
                attacks=[
                    AttackLog(turn=turn+1, device="device1", attacker=0, defender=0, hit=bool(opponent_hit), damage=opponent_attack_type),
                    AttackLog(turn=turn+1, device="device2", attacker=0, defender=0, hit=bool(player_hit), damage=player_attack_type)
                ]                    
            )
            battle_log.append(turn_log)
            
            # End battle if one is defeated
            if player_hp == 0 or opponent_hp == 0:
                runtime_globals.game_console.log(f"[DComBattleSimulator] Battle ended after turn {turn+1}")
                break
        
        runtime_globals.game_console.log(f"[DComBattleSimulator] DMX Battle complete with {len(battle_log)} turns")
        runtime_globals.game_console.log(f"[DComBattleSimulator] Final HP - Player: {player_hp}, Opponent: {opponent_hp}")
        return battle_log

    def _print_dcom_code(self, result):
        """Print DCom code in validator format: r:XXXX s:XXXX ... t"""
        print("\nDCom Code (for validator):")
        
        # Generate alternating r:/s: format
        code_parts = []
        device1_packets = result.device1_packets  # Opponent (received)
        device2_packets = result.device2_packets  # Player (sent)
        
        # Alternate between received (r:) and sent (s:) packets
        for i in range(max(len(device1_packets), len(device2_packets))):
            if i < len(device1_packets):
                # Convert bytes to hex string
                if isinstance(device1_packets[i], bytes):
                    hex_str = device1_packets[i].hex().upper()
                elif isinstance(device1_packets[i], str):
                    hex_str = device1_packets[i].upper()
                else:
                    hex_str = "".join(f"{b:02X}" for b in device1_packets[i])
                code_parts.append(f"r:{hex_str}")
            
            if i < len(device2_packets):
                # Convert bytes to hex string
                if isinstance(device2_packets[i], bytes):
                    hex_str = device2_packets[i].hex().upper()
                elif isinstance(device2_packets[i], str):
                    hex_str = device2_packets[i].upper()
                else:
                    hex_str = "".join(f"{b:02X}" for b in device2_packets[i])
                code_parts.append(f"s:{hex_str}")
        
        # Add terminator
        code_parts.append("t")
        
        # Join with spaces
        dcom_code = " ".join(code_parts)
        print(dcom_code)
        print()

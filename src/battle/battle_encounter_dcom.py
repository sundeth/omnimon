# core/combat/battle_encounter_dcom.py

"""
BattleEncounterDCom - DCom-specific battle logic
Extends BattleEncounter to handle real physical device battles via serial connection.
"""

import pygame
import traceback
from typing import Optional
from battle.battle_encounter import BattleEncounter
from battle.game_battle import GameBattle
from battle.dcom.dcom_dialog import DComDialog
from battle.dcom.dcom_controller import DComController
from battle.dcom.dcom_protocol import ProtocolType
from battle.sim.models import Digimon, BattleResult
from battle.sim.dcom_battle_simulator import DComBattleSimulator
from core import runtime_globals


class BattleEncounterDCom(BattleEncounter):
    """
    BattleEncounter subclass for handling DCom device battles.
    Manages serial communication, packet exchange, and battle simulation with real devices.
    """

    def __init__(self, module, dcom_controller=None, dcom_protocol=None, area=0, round=0, version=1):
        """
        Initialize DCom battle encounter.
        
        Args:
            module: Game module name
            dcom_controller: Optional DComController instance (will create if None)
            dcom_protocol: Optional ProtocolType (will prompt if None)
            area: Battle area
            round: Battle round
            version: Battle version
        """
        # Initialize parent with pvp_mode=True since DCom is a 1v1 battle
        super().__init__(module, area, round, version, pvp_mode=True)
        
        # DCom-specific initialization
        self.dcom_controller: Optional[DComController] = dcom_controller
        self.dcom_protocol: Optional[ProtocolType] = dcom_protocol
        self.dcom_mode = True  # Flag to indicate this is a DCom battle
        self.enemy_first = True  # Enemy (device2) attacks first in DCom V2 protocol
        self.dcom_simulator: Optional[DComBattleSimulator] = None
        self.dcom_battle_result: Optional[BattleResult] = None
        self.dcom_button_rect = None  # Will be set in draw phase
        self.global_battle_log = None  # Initialize to None, will be set after simulation
        
        # Set turn limit based on protocol (DM20 has 5 attacks)
        # Default to 5 for V_PET protocol, can be overridden in _setup_simulator
        self.turn_limit = 5
        
        # Initialize DCom dialog if no controller provided
        self.dcom_dialog = None
        self._setup_simulator()
            
        runtime_globals.game_console.log("[BattleEncounterDCom] Initialized DCom battle encounter")

    def _on_dcom_connected(self, controller: DComController, protocol: ProtocolType):
        """
        Callback when DCom device is connected and protocol selected.
        """
        self.dcom_controller = controller
        self.dcom_protocol = protocol
        self.dcom_mode = True
        
        runtime_globals.game_console.log(f"[BattleEncounterDCom] DCom connected with protocol: {protocol.display_name}")
        
        # Setup simulator now that we have controller and protocol
        self._setup_simulator()
    
    def _setup_simulator(self):
        """Initialize the DCom battle simulator."""
        # Try to get controller and protocol from runtime_globals if not provided
        if not self.dcom_controller and hasattr(runtime_globals, 'pvp_battle_data'):
            pvp_data = runtime_globals.pvp_battle_data
            if pvp_data and isinstance(pvp_data, dict):
                self.dcom_controller = pvp_data.get('dcom_controller')
                self.dcom_protocol = pvp_data.get('dcom_protocol')
                runtime_globals.game_console.log("[BattleEncounterDCom] Retrieved controller and protocol from pvp_battle_data")
        
        if self.dcom_controller and self.dcom_protocol:
            self.dcom_simulator = DComBattleSimulator(self.dcom_controller, self.dcom_protocol)
            runtime_globals.game_console.log("[BattleEncounterDCom] DCom simulator initialized")
        else:
            runtime_globals.game_console.log("[BattleEncounterDCom] WARNING: No controller/protocol available for simulator")
    
    def calculate_combat_for_pairs(self):
        """
        Override to run DCom battle simulation instead of standard combat.
        This is called when battle starts (from update_charge or similar).
        For DCom, we need to:
        1. Get player's Digimon data
        2. Communicate with physical device
        3. Get opponent's Digimon data from device
        4. Set up battle teams
        5. Run simulation
        6. Process results
        """
        runtime_globals.game_console.log("[BattleEncounterDCom] === calculate_combat_for_pairs CALLED ===")
        runtime_globals.game_console.log("[BattleEncounterDCom] Starting DCom battle...")
        
        if not self.dcom_simulator:
            runtime_globals.game_console.log("[BattleEncounterDCom] ERROR: No simulator available")
            return
        
        # Get player's Digimon data
        player_digimon = self._get_player_digimon()
        if not player_digimon:
            runtime_globals.game_console.log("[BattleEncounterDCom] ERROR: Could not create player Digimon")
            return
        
        # Run battle simulation with physical device
        # This sends packets, waits for response, parses opponent, and returns BattleResult
        runtime_globals.game_console.log("[BattleEncounterDCom] Calling simulator.simulate_with_device()...")
        self.dcom_battle_result = self.dcom_simulator.simulate_with_device(player_digimon)
        
        if self.dcom_battle_result:
            runtime_globals.game_console.log("[BattleEncounterDCom] Simulation returned result!")
            # Remap the battle log to swap device labels to match BattleEncounter convention
            # DCom simulator uses: device1=opponent, device2=player
            # BattleEncounter uses: device1=team1=player, device2=team2=enemy
            self.global_battle_log = self._remap_battle_result(self.dcom_battle_result)
            # In DCom simulator: device1=opponent (DCom), device2=player (our pet)
            # So winner=="device2" means WE won
            self.victory_status = "Victory" if self.dcom_battle_result.winner == "device2" else "Defeat"
            runtime_globals.game_console.log(f"[BattleEncounterDCom] Battle complete: {self.victory_status}")
            runtime_globals.game_console.log(f"[BattleEncounterDCom] Battle log has {len(self.global_battle_log.battle_log)} turns")
            runtime_globals.game_console.log(f"[BattleEncounterDCom] Battle result object: {self.dcom_battle_result}")
            runtime_globals.game_console.log(f"[BattleEncounterDCom] global_battle_log is: {self.global_battle_log}")
            
            # Now that we have opponent data from the device, set up battle teams properly
            # This is needed for animations and result processing
            self._setup_teams_from_battle_result()
            
            # Process battle results (updates HP, etc.)
            self.process_battle_results()
        else:
            runtime_globals.game_console.log("[BattleEncounterDCom] Battle simulation failed")
            self.victory_status = "Error"
    
    def _remap_battle_result(self, result: BattleResult) -> BattleResult:
        """
        Remap battle result to swap device labels to match BattleEncounter convention.
        
        DCom simulator uses: device1=opponent (DCom device), device2=player (our pet)
        BattleEncounter uses: device1=team1=player, device2=team2=enemy
        
        This method creates a new BattleResult with swapped device labels so the
        animations in draw_pets() and draw_enemies() work correctly.
        """
        from battle.sim.models import BattleResult, TurnLog, AttackLog, DigimonStatus
        
        remapped_log = []
        for turn_log in result.battle_log:
            # Swap device1_status and device2_status
            # Original: device1=opponent, device2=player
            # New: device1=player, device2=opponent
            remapped_attacks = []
            for attack in turn_log.attacks:
                # Swap device labels
                new_device = "device2" if attack.device == "device1" else "device1"
                remapped_attacks.append(AttackLog(
                    turn=attack.turn,
                    device=new_device,
                    attacker=attack.attacker,
                    defender=attack.defender,
                    hit=attack.hit,
                    damage=attack.damage
                ))
            
            remapped_turn = TurnLog(
                turn=turn_log.turn,
                device1_status=turn_log.device2_status,  # Player becomes device1
                device2_status=turn_log.device1_status,  # Opponent becomes device2
                attacks=remapped_attacks
            )
            remapped_log.append(remapped_turn)
        
        # Swap winner label
        new_winner = "device1" if result.winner == "device2" else "device2"
        
        remapped_result = BattleResult(
            winner=new_winner,
            device1_final=result.device2_final,  # Player becomes device1  
            device2_final=result.device1_final,  # Opponent becomes device2
            battle_log=remapped_log,
            device1_packets=result.device2_packets,
            device2_packets=result.device1_packets
        )
        
        runtime_globals.game_console.log(f"[BattleEncounterDCom] Remapped battle log: winner={new_winner}")
        return remapped_result

    def _get_player_digimon(self) -> Optional[Digimon]:
        """
        Convert current player battle state to Digimon object for simulator.
        Follows the same pattern as BattleEncounterVersus.
        
        OEM/Compatibility mode: If the pet's module battle_protocol matches the
        device we're fighting (dcom_battle_format), send real index and version.
        Otherwise send 0 for both (compatibility mode).
        """
        # Use first pet as representative
        if not self.battle_player or not self.battle_player.teams[1]:
            runtime_globals.game_console.log("[BattleEncounterDCom] No player team available")
            return None
        
        first_pet = self.battle_player.teams[1][0]
        
        # Map attribute strings to integers
        attr_map = {"Va": 0, "Vaccine": 0, "Da": 1, "Data": 1, "Vi": 2, "Virus": 2, "Fr": 3, "Free": 3}
        pet_attr = getattr(first_pet, 'attribute', 'Va')
        attribute = attr_map.get(pet_attr, 0)
        
        # OEM/Compatibility mode for index and version
        index = 0
        version = 0
        pet_module_name = getattr(first_pet, 'module', None)
        dcom_format = self.dcom_simulator.battle_format if self.dcom_simulator else None
        if pet_module_name and dcom_format:
            try:
                from utils.module_utils import get_module
                pet_module = get_module(pet_module_name)
                if pet_module and getattr(pet_module, 'battle_protocol', '') == dcom_format:
                    index = getattr(first_pet, 'index', 0)
                    version = getattr(first_pet, 'version', 0)
                    # Clamp version to the valid range for each protocol; out-of-range = special, send 0
                    _version_ranges = {
                        'DM': (1, 5), 'DM20': (1, 5), 'DMX': (1, 6), 'DMC': (1, 5),
                        'PEN': (0, 5), 'PEN20': (1, 4), 'PENZ': (0, 5), 'PENC': (0, 7),
                    }
                    v_min, v_max = _version_ranges.get(dcom_format, (1, 5))
                    if version < v_min or version > v_max:
                        version = 0
            except Exception:
                pass
        
        # Determine OEM mode (index/version were set above; if non-zero, it's OEM)
        oem_mode = index != 0 or version != 0
        
        # Omnipet uses 1-based attack sprite IDs (0=no sprite),
        # real devices use 0-based IDs, so subtract 1 before sending.
        # DMX/PENZ use 3 shots: atk_main=weak, atk_alt=strong, atk_alt_2=mega
        if dcom_format in ('DMX', 'PENZ'):
            if oem_mode:
                shot_w = max(0, getattr(first_pet, 'atk_main', 1) - 1)
                shot_s = max(0, getattr(first_pet, 'atk_alt', 1) - 1)
                shot_m = max(0, getattr(first_pet, 'atk_alt_2', 1) - 1)
            else:
                raw_w = getattr(first_pet, 'atk_main', 0)
                raw_s = getattr(first_pet, 'atk_alt', 0)
                raw_m = getattr(first_pet, 'atk_alt_2', 0)
                shot_w = max(0, raw_w - 1) if raw_w > 0 else 0
                shot_s = max(0, raw_s - 1) if raw_s > 0 else 0
                shot_m = max(0, raw_m - 1) if raw_m > 0 else 0
            shot1 = shot_s  # shot1 = strong
            shot2 = shot_w  # shot2 = weak
        else:
            shot1 = max(0, getattr(first_pet, 'atk_main', 1) - 1)
            shot2 = max(0, getattr(first_pet, 'atk_alt', 1) - 1)
            shot_m = 0
        
        # Create Digimon object from pet data
        # Note: Shot values will be capped by the simulator based on protocol (DM20 uses 6-bit = 0-63)
        digimon = Digimon(
            name=getattr(first_pet, 'name', 'Player'),
            order=0,
            traited=1 if getattr(first_pet, 'traited', False) else 0,
            egg_shake=1 if getattr(first_pet, 'shook', False) else 0,
            index=index,
            hp=getattr(first_pet, 'hp', 100),
            attribute=attribute,
            power=getattr(first_pet, 'power', 50) if hasattr(first_pet, 'power') else 50,
            handicap=0,
            buff=0,
            mini_game=3,  # Strength bonus
            level=getattr(first_pet, 'level', 1),
            stage=getattr(first_pet, 'stage', 3),
            sick=1 if getattr(first_pet, 'sick', False) else 0,
            shot1=shot1,
            shot2=shot2,
            tag_meter=2
        )
        
        # Set version for packet generators (DM20Device/DMXDevice read this)
        digimon.version = version
        # Store medium shot for DMX/PENZ protocol
        digimon.dmx_shot_m = shot_m
        
        runtime_globals.game_console.log(f"[BattleEncounterDCom] Player Digimon: {digimon.name}, HP={digimon.hp}, Power={digimon.power}, index={index}, version={version}")
        
        return digimon
    
    def _setup_teams_from_battle_result(self):
        """
        Set up battle teams after getting opponent data from device.
        This creates proper GameEnemy objects for animations.
        
        IMPORTANT: In DCom simulator, device1=opponent (DCom device), device2=player (our pet)
        In BattleEncounter, team1=player pets, team2=enemies
        So we need to swap: device1_final -> team2 (enemies), device2_final -> team1 (our pets)
        """
        if not self.dcom_battle_result or not self.battle_player:
            runtime_globals.game_console.log("[BattleEncounterDCom] Cannot setup teams: no result or battle_player")
            return
        
        from models.game_enemy import GameEnemy
        
        # Get opponent data from battle result (device1 = opponent in DCom simulator)
        opponent_status = self.dcom_battle_result.device1_final[0]
        
        # Use parsed opponent Digimon data if available (has actual attribute, shots, stage, etc.)
        opp = getattr(self.dcom_simulator, 'opponent_digimon', None)
        
        # Map attribute integer to string for GameEnemy
        attr_int_to_str = {0: "Va", 1: "Da", 2: "Vi", 3: "Fr"}
        opp_attribute = attr_int_to_str.get(opp.attribute, "Va") if opp else "Va"
        
        # Create enemy object from opponent data
        # Opponent shot values from device are 0-based, convert to 1-based for Omnipet
        enemy = GameEnemy(
            name=opponent_status.name,
            power=opp.power if opp else opponent_status.power,
            attribute=opp_attribute,
            area=0,
            round=0,
            version=opp.version if opp and hasattr(opp, 'version') else 1,
            atk_main=(opp.shot1 + 1) if opp else 1,
            atk_alt=(opp.shot2 + 1) if opp else 1,
            atk_alt_2=0,
            handicap=0,
            id=opp.index if opp else 0,
            stage=opp.stage if opp else 3,
            hp=opponent_status.hp,
            unlock="",
            prize="",
            mini_game=opp.mini_game if opp and hasattr(opp, 'mini_game') else 3
        )
        
        # Set additional properties
        enemy.level = opp.level if opp else 1
        enemy.sick = opp.sick if opp else 0
        enemy.traited = bool(opp.traited) if opp else False
        enemy.shook = bool(opp.egg_shake) if opp else False
        enemy.module = self.module
        
        # Load sprite for the enemy
        enemy.load_sprite(enemy.module, boss=False)
        
        # Update battle_player teams
        my_pets = self.battle_player.teams[1]  # Keep existing player pets
        self.battle_player = GameBattle(my_pets, [enemy], 0, 0, self.module)
        self.enemies = [enemy]
        
        # Override HP values with fixed HP from protocol (DM20 uses 5 HP)
        # The GameBattle constructor computes HP from pet objects, but for DCom
        # we need to use the protocol's fixed HP value
        fixed_hp = self.dcom_simulator.get_initial_hp() if self.dcom_simulator else 5
        for i in range(len(self.battle_player.team1_hp)):
            self.battle_player.team1_hp[i] = fixed_hp
            self.battle_player.team1_max_hp[i] = fixed_hp
        for i in range(len(self.battle_player.team2_hp)):
            self.battle_player.team2_hp[i] = fixed_hp
            self.battle_player.team2_max_hp[i] = fixed_hp
        self.battle_player.team1_total_hp = fixed_hp * len(my_pets)
        self.battle_player.team1_max_total_hp = self.battle_player.team1_total_hp
        self.battle_player.team2_total_hp = fixed_hp * len([enemy])
        self.battle_player.team2_max_total_hp = self.battle_player.team2_total_hp
        
        # Update HP bar with correct fixed HP values
        if hasattr(self, 'hp_bar') and self.hp_bar:
            # HPBar: set_totals(enemy_total, player_total) and set_values(enemy_hp, player_hp)
            self.hp_bar.set_totals(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)
            self.hp_bar.set_values(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)

        # DCom battles always have enemy attacking first
        self.prime_enemy_first()
        
        runtime_globals.game_console.log(f"[BattleEncounterDCom] Teams set up: player={my_pets[0].name}, opponent={enemy.name}")
    
    def update_result(self):
        """
        Override result handling for DCom battles.
        Extends the parent PvP unlock logic with OEM-specific unlocks:
        - versus: triggered by any OEM DCom battle
        - battle: triggered by OEM DCom victories (increments total_victories)
        - pvp: handled by parent logic (pvp_wins counter)
        """
        from core import game_globals, constants
        from utils.utils_unlocks import unlock_item
        
        # Same timer logic as parent
        if self.result_timer == 0 and not self._has_result_rewards():
            self.result_timer = int(120 * (constants.FRAME_RATE / 30))
        
        self.result_timer += 1
        
        if self.result_timer < int(120 * (constants.FRAME_RATE / 30)):
            return
        
        # Play appropriate sound
        runtime_globals.game_sound.play("happy" if self.victory_status == "Victory" else "fail")
        
        # Update PvP counters (same as parent)
        for i, pet in enumerate(self.battle_player.team1):
            try:
                pet.pvp_battles += 1
                if hasattr(self.battle_player, 'winners') and i < len(self.battle_player.winners):
                    winner = self.battle_player.winners[i]
                    local_won = (winner == 'team1') or (self.victory_status == 'Victory')
                else:
                    local_won = (self.victory_status == 'Victory')
                if local_won:
                    pet.pvp_wins += 1
                runtime_globals.game_console.log(f"[PvP] Pet {getattr(pet,'name',i)} pvp_battles={pet.pvp_battles} pvp_wins={pet.pvp_wins}")
            except Exception as e:
                runtime_globals.game_console.log(f"[PvP] Error updating pet PvP counters: {e}")
        
        # PvP-type unlocks (same as parent)
        try:
            module_unlocks = getattr(self.module, 'unlocks', []) or []
            for unlock in module_unlocks:
                if unlock.get('type') == 'pvp':
                    req = unlock.get('amount', None)
                    name = unlock.get('name')
                    if req is None or not name:
                        continue
                    for pet in self.battle_player.team1:
                        if getattr(pet, 'pvp_wins', 0) >= int(req):
                            unlock_item(self.module.name, 'pvp', name)
                            break
        except Exception as e:
            runtime_globals.game_console.log(f"[PvP] Error processing PvP unlocks: {e}")
        
        # OEM-specific unlocks: versus, battle
        if getattr(self, 'is_oem_mode', False):
            try:
                module_unlocks = getattr(self.module, 'unlocks', []) or []
                
                # Versus-type unlocks: triggered by any OEM DCom battle
                for unlock in module_unlocks:
                    if unlock.get('type') == 'versus':
                        name = unlock.get('name')
                        if name:
                            ver_req = unlock.get('version', None)
                            if ver_req is not None:
                                pet_version = getattr(self.battle_player.team1[0], 'version', 0) if self.battle_player.team1 else 0
                                if pet_version == ver_req:
                                    unlock_item(self.module.name, 'versus', name)
                                    runtime_globals.game_console.log(f"[DCom OEM] Unlocked versus: {name}")
                            else:
                                unlock_item(self.module.name, 'versus', name)
                                runtime_globals.game_console.log(f"[DCom OEM] Unlocked versus: {name}")
                
                # Battle-type unlocks: triggered by OEM DCom victories
                if self.victory_status == "Victory":
                    if self.module.name not in game_globals.total_victories:
                        game_globals.total_victories[self.module.name] = 0
                    game_globals.total_victories[self.module.name] += 1
                    runtime_globals.game_console.log(f"[DCom OEM] Total victories for {self.module.name}: {game_globals.total_victories[self.module.name]}")
                    
                    for unlock in module_unlocks:
                        if unlock.get('type') == 'battle':
                            req = unlock.get('amount', None)
                            name = unlock.get('name')
                            if req is None or not name:
                                continue
                            current_victories = game_globals.total_victories.get(self.module.name, 0)
                            if current_victories >= int(req):
                                unlock_item(self.module.name, 'battle', name)
                                runtime_globals.game_console.log(f"[DCom OEM] Unlocked battle: {name} after {current_victories} victories")
            except Exception as e:
                runtime_globals.game_console.log(f"[DCom OEM] Error processing OEM unlocks: {e}")
        
        self.return_to_main_scene()

    def draw_level(self, surface):
        """
        Override level drawing to show DCom-specific UI.
        """
        super().draw_level(surface)
        
        # Draw DCom button/indicator if available
        self._draw_dcom_button(surface)
    
    def _draw_dcom_button(self, surface):
        """
        Draw DCom connection button/status on the level/entry screen.
        """
        if not self.dcom_mode:
            return
        
        # Simple status text
        font = self.font_small
        status_text = "DCom: Connected" if self.dcom_controller else "DCom: Disconnected"
        text_surface = font.render(status_text, True, (255, 255, 255))
        
        # Position at top-right corner
        x = runtime_globals.SCREEN_WIDTH - text_surface.get_width() - 10
        y = 10
        
        surface.blit(text_surface, (x, y))
        
        # Store rect for click detection
        self.dcom_button_rect = pygame.Rect(x, y, text_surface.get_width(), text_surface.get_height())
    
    def handle_event(self, event):
        """
        Override event handling to add DCom-specific interactions.
        """
        # Handle DCom dialog events if active
        if self.dcom_dialog and hasattr(self.dcom_dialog, 'handle_event'):
            if self.dcom_dialog.handle_event(event):
                return  # Dialog handled the event
        
        # Handle DCom button clicks - event is tuple (event_type, event_data)
        if isinstance(event, tuple) and len(event) == 2:
            event_type, event_data = event
            if event_type == "LCLICK" and self.dcom_button_rect:
                mouse_pos = pygame.mouse.get_pos()
                if self.dcom_button_rect.collidepoint(mouse_pos):
                    runtime_globals.game_console.log("[BattleEncounterDCom] DCom button clicked")
                    if not self.dcom_controller and self.dcom_dialog:
                        self.dcom_dialog.show()
                    return
        
        # Call parent event handler
        super().handle_event(event)
    
    def __del__(self):
        """
        Clean up DCom resources.
        """
        if self.dcom_controller:
            try:
                self.dcom_controller.disconnect()
            except:
                pass

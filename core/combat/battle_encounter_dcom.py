# core/combat/battle_encounter_dcom.py

"""
BattleEncounterDCom - DCom-specific battle logic
Extends BattleEncounter to handle real physical device battles via serial connection.
"""

import pygame
import traceback
from typing import Optional
from core.combat.battle_encounter import BattleEncounter
from core.combat.game_battle import GameBattle
from core.combat.dcom.dcom_dialog import DComDialog
from core.combat.dcom.dcom_controller import DComController
from core.combat.dcom.dcom_protocol import ProtocolType
from core.combat.sim.models import Digimon, BattleResult
from core.combat.sim.dcom_battle_simulator import DComBattleSimulator
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
        from core.combat.sim.models import BattleResult, TurnLog, AttackLog, DigimonStatus
        
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
        
        # Create Digimon object from pet data
        # Note: Shot values will be capped by the simulator based on protocol (DM20 uses 6-bit = 0-63)
        digimon = Digimon(
            name=getattr(first_pet, 'name', 'Player'),
            order=0,
            traited=1 if getattr(first_pet, 'traited', False) else 0,
            egg_shake=1 if getattr(first_pet, 'shook', False) else 0,
            index=0,
            hp=getattr(first_pet, 'hp', 100),
            attribute=attribute,
            power=getattr(first_pet, 'power', 50) if hasattr(first_pet, 'power') else 50,
            handicap=0,
            buff=0,
            mini_game=3,  # Strength bonus
            level=getattr(first_pet, 'level', 1),
            stage=getattr(first_pet, 'stage', 3),
            sick=1 if getattr(first_pet, 'sick', False) else 0,
            shot1=getattr(first_pet, 'atk_main', 30),
            shot2=getattr(first_pet, 'atk_alt', 30),
            tag_meter=2
        )
        
        runtime_globals.game_console.log(f"[BattleEncounterDCom] Player Digimon: {digimon.name}, HP={digimon.hp}, Power={digimon.power}")
        
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
        
        from core.game_enemy import GameEnemy
        
        # Get opponent data from battle result (device1 = opponent in DCom simulator)
        opponent_status = self.dcom_battle_result.device1_final[0]
        
        # Create enemy object from opponent data
        enemy = GameEnemy(
            name=opponent_status.name,
            power=opponent_status.power,
            attribute=0,  # Will be set from status
            area=0,
            round=0,
            version=1,
            atk_main=30,  # Default values since we don't get these from device
            atk_alt=30,
            handicap=0,
            id=0,
            stage=3,  # Default stage
            hp=opponent_status.hp,
            unlock="",
            prize="",
            mini_game=3
        )
        
        # Set additional properties
        enemy.level = 1
        enemy.sick = 0
        enemy.traited = False
        enemy.shook = False
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

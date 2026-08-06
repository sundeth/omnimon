# core/combat/battle_encounter_versus.py

import pygame
from battle.battle_encounter import BattleEncounter, GameBattle
from battle.sim.battle_simulator import BattleSimulator, BattleProtocol
from models.animation import PetFrame
from battle.sim.models import Digimon
import core.constants as constants
from utils.scene_utils import change_scene
from core import game_globals, runtime_globals
from utils.utils_unlocks import unlock_item
from utils.module_utils import get_module
import ui.ui_constants as ui_constants
from ui.components.image import Image
from ui.components.label import Label
from ui.components.component import UIComponent
from battle.combat_constants import ANY_OTHER_DEVICE

class BattleEncounterVersus(BattleEncounter):
    def __init__(self, pet1, pet2, protocol: BattleProtocol):
        """
        Initializes the Versus encounter for PvP battles.
        """
        self.pet1 = pet1
        self.pet2 = pet2
        self.pet2.x = 2 * (runtime_globals.SCREEN_WIDTH / 240)
        self.protocol = protocol
        
        # Set pvp_mode flag before calling parent init
        self.pvp_mode = True
        
        # Call the base class initializer with module="DMC"
        module = "DMC"

        super().__init__(module, 0, 0, pvp_mode=True)
        self.enemy_entry_counter = 0

        # Override the BattlePlayer with the two pets for versus mode
        self.battle_player = GameBattle([pet1], [pet2], 0, 0, self.module)
        fixed_hp = None
        if protocol in [BattleProtocol.DM_BS]:
            fixed_hp = 5  # Original DM uses 5 HP
            self.turn_limit = 4  # 4 turns (3 normal + 1 finishing)
        elif protocol in [BattleProtocol.DMC_BS]:
            fixed_hp = 5  # DMC uses 5 HP (Winner 1112, Loser 1111)
            self.turn_limit = 4  # 4 turns
        elif protocol in [BattleProtocol.DM20_BS]:
            fixed_hp = 5  # DM20 uses 5 HP
            self.turn_limit = 5  # 5 turns
        elif protocol in [BattleProtocol.PEN20_BS]:
            fixed_hp = 5  # PEN20 uses 5 HP
            self.turn_limit = 5  # 5 turns
        elif protocol in [BattleProtocol.DMX_BS]:
            self.turn_limit = 5

        if fixed_hp is not None:
            self.battle_player.team1_hp[0] = fixed_hp
            self.battle_player.team2_hp[0] = fixed_hp
            self.battle_player.team1_max_hp[0] = fixed_hp
            self.battle_player.team2_max_hp[0] = fixed_hp
            self.battle_player.team1_total_hp = fixed_hp
            self.battle_player.team2_total_hp = fixed_hp
            self.battle_player.team1_max_total_hp = fixed_hp
            self.battle_player.team2_max_total_hp = fixed_hp
        else:
            team1hp = pet1.get_hp()
            team2hp = pet2.get_hp()
            self.battle_player.team1_hp[0] = team1hp
            self.battle_player.team2_hp[0] = team2hp
            self.battle_player.team1_max_hp[0] = team1hp
            self.battle_player.team2_max_hp[0] = team2hp
            self.battle_player.team1_total_hp = team1hp
            self.battle_player.team2_total_hp = team2hp
            self.battle_player.team1_max_total_hp = team1hp
            self.battle_player.team2_max_total_hp = team2hp

        self.alert_sprite = self.ui_manager.load_sprite_integer_scaling("Battle", "VersusFrame", "")

        # Setup persistent UI components for the alert phase (image + labels)
        # These components are added to the UI manager so the manager will
        # handle scaling and drawing automatically.
        self.setup_alert_components()

        # Initialize the BattleSimulator with the given protocol
        self.simulator = BattleSimulator(protocol)

        # Configure the global HPBar for versus mode and initialize totals
        self.hp_bar.set_mode('versus')
        self.hp_bar.set_totals(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)
        self.hp_bar.set_values(self.battle_player.team2_total_hp, self.battle_player.team1_total_hp)
        
        # Initialize result timer
        self.result_timer = 0
        
        # Set initial state
        self.phase = "alert"

    def calculate_combat_for_pairs(self):
        self.simulate_combat()
        
        # Load battle turns from simulation into BattlePlayer for animations
        self._load_protocol_turns_into_battle_player()

        self.process_battle_results()
    
    def _load_protocol_turns_into_battle_player(self):
        """
        Load battle turns from global_battle_log into BattlePlayer so animations can play.
        Sets up the battle system to use short cooldowns for rapid attack sequences.
        """
        if not self.global_battle_log or not self.global_battle_log.battle_log:
            runtime_globals.game_console.log("[BattleEncounterVersus] No battle log to load")
            return
        
        # Set short cooldowns for protocol battles to trigger rapid attacks
        for i in range(len(self.battle_player.team1)):
            self.battle_player.cooldowns[i] = 10  # Very short cooldown for fast attacks
            self.battle_player.phase[i] = "pet_charge"  # Start with charge phase
            self.battle_player.turns[i] = 1
        
        runtime_globals.game_console.log(f"[BattleEncounterVersus] Loaded protocol turns for {len(self.global_battle_log.battle_log)} turns")

    def setup_alert_components(self):
        """
        Create persistent UI components for the alert phase and register them
        with the UI manager so the UI system handles scaling/drawing.

        Components created:
        - self.alert_image : Image(0,0,240,240) using self.alert_sprite
        - self.left_label  : Label(27,186) left-aligned, fixed_width=170, font size 48
        - self.right_label : Label(280,245) right-aligned, fixed_width=170, font size 48
        """
        # Create alert image component (base UI coords covering the UI area)
        self.alert_image = Image(0, 0, 240, 240, image_surface=self.alert_sprite)
        # Add to UI manager so it gets scaled and drawn automatically
        self.ui_manager.add_component(self.alert_image)

        # Pet portrait images: left (above name) and right (below name)
        # Use IDLE1 frame by default. We swap which pet is shown on each side
        # so left will show pet2 (flipped to face right) and right will show pet1.
        left_sprite = None
        right_sprite = None
        # Left side shows pet2 (flip so it faces toward the center)
        left_sprite = self.pet2.get_sprite(PetFrame.IDLE1.value) if hasattr(self.pet2, 'get_sprite') else None
        if left_sprite:
            left_sprite = pygame.transform.flip(left_sprite, True, False)

        # Right side shows pet1 (no flip)
        right_sprite = self.pet1.get_sprite(PetFrame.IDLE1.value) if hasattr(self.pet1, 'get_sprite') else None

        # Create Image components for pet portraits (base coords)
        # Left portrait above the left label
        # Position: center of top-left quadrant on 240x240 base -> center (60,60)
        # With size 70x70, top-left = (60-35, 60-35) = (25,25)
        self.left_pet_image = Image(25, 15, 70, 70, image_surface=left_sprite)
        self.ui_manager.add_component(self.left_pet_image)

        # Right portrait below the right label
        # Position: center of bottom-right quadrant on 240x240 base -> center (180,180)
        # With size 70x70, top-left = (180-35, 180-35) = (145,145)
        self.right_pet_image = Image(145, 155, 70, 70, image_surface=right_sprite)
        self.ui_manager.add_component(self.right_pet_image)

        # Left label (left aligned) - now shows pet2's name
        self.left_label = Label(13, 99, text=getattr(self.pet2, 'name', ''), is_title=False, align_right=False, fixed_width=85, color_override=ui_constants.ANIM_BLACK)
        # Force a 24px font for this label instance regardless of manager defaults
        self.left_label.get_font = lambda font_type, custom_size=None: UIComponent.get_font(self.left_label, font_type, custom_size=24)
        self.ui_manager.add_component(self.left_label)

        # Right label (right aligned) - now shows pet1's name
        self.right_label = Label(140, 130, text=getattr(self.pet1, 'name', ''), is_title=False, align_right=True, fixed_width=85, color_override=ui_constants.ANIM_BLACK)
        self.right_label.get_font = lambda font_type, custom_size=None: UIComponent.get_font(self.right_label, font_type, custom_size=24)
        self.ui_manager.add_component(self.right_label)

    def _wrap_byte_value(self, value, max_value=255):
        """
        Wrap a value to fit in the specified range, but ensure it never becomes 0.
        If value exceeds max_value, wrap around (e.g., for max=255: 260->5, 256->1).
        
        Args:
            value: Integer value that might exceed the range
            max_value: Maximum allowed value (default 255 for byte)
            
        Returns:
            Value wrapped to 1-max_value range
        """
        if value <= 0:
            return 1
        if value > max_value:
            # Wrap around: (max+1)->1, (max+2)->2, etc.
            wrapped = value % (max_value + 1)
            return wrapped if wrapped != 0 else 1
        return value

    def simulate_combat(self):
        strength_bonus = 3

        # Attribute mapping
        attribute_mapping = {
            "Va": 0,  # Vaccine
            "Da": 1,  # Data
            "Vi": 2,  # Virus
            "Free": 3  # Free
        }

        # Create Digimon instance for the attacker
        # Note: DM20 protocol uses 6-bit shot values (0-63), so we cap them at 63
        attacker = Digimon(
            name=self.battle_player.team1[0].name,
            order=0,
            traited=1 if self.battle_player.team1[0].traited else 0,
            egg_shake=1 if self.battle_player.team1[0].shook else 0,
            index=0,
            hp=self.battle_player.team1_hp[0],
            attribute=attribute_mapping.get(self.battle_player.team1[0].attribute, 3),  # Default to Free if not found
            power=self.battle_player.team1[0].get_power(),
            handicap=0,
            buff=0,
            mini_game=strength_bonus,
            level=self.battle_player.team1[0].level,
            stage=self.battle_player.team1[0].stage,
            sick=1 if self.battle_player.team1[0].sick else 0,
            shot1=self._wrap_byte_value(self.battle_player.team1[0].atk_main, max_value=63),
            shot2=self._wrap_byte_value(self.battle_player.team1[0].atk_alt, max_value=63),
            tag_meter=2
        )

        # Create Digimon instance for the defender
        defender = Digimon(
            name=self.battle_player.team2[0].name,
            order=1,
            traited=1 if self.battle_player.team2[0].traited else 0,
            egg_shake=1 if self.battle_player.team2[0].shook else 0,
            index=1,
            hp=self.battle_player.team2_hp[0],
            attribute=attribute_mapping.get(self.battle_player.team2[0].attribute, 3),  # Default to Free if not found
            power=self.battle_player.team2[0].get_power(),
            handicap=0,
            buff=0,
            mini_game=strength_bonus,
            level=self.battle_player.team2[0].level,
            stage=self.battle_player.team2[0].stage,
            sick=1 if self.battle_player.team2[0].sick else 0,
            shot1=self._wrap_byte_value(self.battle_player.team2[0].atk_main, max_value=63),
            shot2=self._wrap_byte_value(self.battle_player.team2[0].atk_alt, max_value=63),
            tag_meter=2
        )

        # Run simulation
        self.global_battle_log = self.simulator.simulate(attacker, defender)

        # Store the attacker's turns as the combat log for animation
        self.victory_status = "Victory" if self.global_battle_log.winner == "device1" else "Defeat"

    def update_alert(self):
        """
        Handles the alert phase, transitioning to the battle phase.
        """
        if self.frame_counter > game_globals.configuration.frame_rate * 3:  # Wait for 3 seconds
            self.frame_counter = 0
            self.phase = "battle"
            self.calculate_combat_for_pairs()

    def update_result(self):
        """
        Handles the result phase, displaying the winner and transitioning back to the main scene.
        """
        self.result_timer += 1
        if self.result_timer == 2:
            runtime_globals.game_sound.play("happy")
        if self.result_timer > 90:  # Wait for 1.5 seconds (assuming 60 FPS)
            # Process the result
            winner = self.pet1 if self.global_battle_log.winner == "device1" else self.pet2
            loser = self.pet2 if winner == self.pet1 else self.pet1

            winner.finish_versus(True)
            loser.finish_versus(False)

            # Versus unlock logic: check if both pets are from the same module
            # and meet version requirements for versus unlocks
            pet1_module = getattr(self.pet1, 'module', None)
            pet2_module = getattr(self.pet2, 'module', None)
            
            # Only process versus unlocks if both pets are from the same module
            if pet1_module and pet2_module and pet1_module == pet2_module:
                pet_module = get_module(pet1_module)
                if pet_module:
                    module_unlocks = getattr(pet_module, 'unlocks', []) or []
                    for unlock in module_unlocks:
                        if unlock.get('type') == 'versus':
                            ver_req = unlock.get('version', None)
                            unlock_name = unlock.get('name')
                            if unlock_name:
                                # Check if at least one pet meets the version requirement
                                pet1_version = getattr(self.pet1, 'version', 0)
                                pet2_version = getattr(self.pet2, 'version', 0)

                                # Which physical device each pet was hatched on.
                                # A connection requirement is about the hardware,
                                # so device_version decides it, not the gameplay
                                # version used for evolutions.
                                dev1 = getattr(self.pet1, 'device_version', pet1_version)
                                dev2 = getattr(self.pet2, 'device_version', pet2_version)
                                dev_req = unlock.get('device_version', None)
                                opp_req = unlock.get('opponent_device_version', None)

                                # "Battle XA with XB" style pairing: one side has
                                # to be the named device and the other its partner.
                                # An opponent of ANY_OTHER_DEVICE means "any
                                # device that is not this one", which is how a
                                # device states "battle with any other version".
                                if dev_req is not None or opp_req is not None:
                                    def _side(own, other):
                                        if dev_req is not None and own != dev_req:
                                            return False
                                        if opp_req is None:
                                            return True
                                        if opp_req == ANY_OTHER_DEVICE:
                                            return other != own
                                        return other == opp_req

                                    paired = _side(dev1, dev2) or _side(dev2, dev1)
                                    if paired:
                                        unlock_item(pet1_module, 'versus', unlock_name)
                                        runtime_globals.game_console.log(f"[Versus] Unlocked {unlock_name} for {pet1_module}")
                                elif ver_req is not None:
                                    # Version requirement specified - check if either pet meets it
                                    if pet1_version == ver_req or pet2_version == ver_req:
                                        unlock_item(pet1_module, 'versus', unlock_name)
                                        runtime_globals.game_console.log(f"[Versus] Unlocked {unlock_name} for {pet1_module}")
                                else:
                                    # No version requirement - unlock for any versus battle in this module
                                    unlock_item(pet1_module, 'versus', unlock_name)
                                    runtime_globals.game_console.log(f"[Versus] Unlocked {unlock_name} for {pet1_module}")
            # Return to the main scene
            change_scene("game")

    def draw_result(self, surface: pygame.Surface):
        """
        Draws the result phase, showing the winner or indicating a draw with AnimatedSprite component.
        """
        # Start versus result animation if not already playing
        if not self.animated_sprite.is_animation_playing():
            self.animated_sprite.play_versus_result(duration_seconds=3.0)
        
        # Draw the animated sprite background
        self.animated_sprite.draw(surface)
        
        # Determine which pet won and should be displayed
        if self.global_battle_log.winner == "device1":
            winner_pet = self.pet1
        elif self.global_battle_log.winner == "device2":
            winner_pet = self.pet2
        else:
            winner_pet = None  # Draw for tie case
        
        # Animate winner pet sprite centered on screen
        # Toggle between IDLE1 and HAPPY every half second
        anim_toggle = (self.frame_counter // (game_globals.configuration.frame_rate // 2)) % 2
        
        if winner_pet:
            # Get the frame (IDLE1 or HAPPY)
            frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.HAPPY.value
            pet_sprite = winner_pet.get_sprite(frame_id)
            
            # Center the sprite on screen
            pet_x = runtime_globals.SCREEN_WIDTH // 2 - pet_sprite.get_width() // 2
            pet_y = runtime_globals.SCREEN_HEIGHT // 2 - pet_sprite.get_height() // 2
            
            surface.blit(pet_sprite, (pet_x, pet_y))
        else:
            # Draw both pets for a tie (smaller and side by side), snapped to
            # the pixel-perfect ladder (PET//2 can land between steps).
            from utils.sprite_utils import snap_pet_sprite_size
            sprite_width = snap_pet_sprite_size(runtime_globals.PET_WIDTH // 2)
            sprite_height = sprite_width
            
            # Both pets animate between IDLE1 and HAPPY
            frame_id = PetFrame.IDLE1.value if anim_toggle == 0 else PetFrame.HAPPY.value
            
            # Position for pet1 (left side)
            pet1_x = runtime_globals.SCREEN_WIDTH // 4 - sprite_width // 2
            pet1_y = runtime_globals.SCREEN_HEIGHT // 2 - sprite_height // 2
            pet1_sprite = self.pet1.get_sprite(frame_id)
            pet1_sprite = pygame.transform.scale(pet1_sprite, (sprite_width, sprite_height))
            surface.blit(pet1_sprite, (pet1_x, pet1_y))
            
            # Position for pet2 (right side)
            pet2_x = 3 * runtime_globals.SCREEN_WIDTH // 4 - sprite_width // 2
            pet2_y = runtime_globals.SCREEN_HEIGHT // 2 - sprite_height // 2
            pet2_sprite = self.pet2.get_sprite(frame_id)
            pet2_sprite = pygame.transform.scale(pet2_sprite, (sprite_width, sprite_height))
            surface.blit(pet2_sprite, (pet2_x, pet2_y))

    def draw_alert(self, surface):
        """
        Draws the alert phase overlay.
        """
        # Fill the entire screen (or UI area) with the combat blue color.
        # The UI manager will draw the persistent Image and Label components
        # that were registered in `setup_alert_components`.
        surface.fill(ui_constants.COMBAT_BLUE)
        self.ui_manager.draw(surface)
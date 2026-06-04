import random
import copy

try:
    from battle_utils import get_attack_pattern
    from models import *
except ImportError:
    # Absolute imports for direct testing
    from battle.sim.battle_utils import get_attack_pattern
    from battle.sim.models import *


class GlobalBattleSimulator:
    def __init__(self, attribute_advantage=5, damage_limit=3, force_winner=True, pvp_mode=False):
        self.attribute_advantage = attribute_advantage
        self.damage_limit = damage_limit
        self.force_winner = force_winner
        self.pvp_mode = pvp_mode

    def _attribute_advantage(self, att_attr, def_attr):
        # Vaccine > Virus > Data > Vaccine
        if att_attr == "Va":
            if def_attr == "Da":
                return -self.attribute_advantage
            elif def_attr == "Vi":
                return self.attribute_advantage
        elif att_attr == "Da":
            if def_attr == "Va":
                return self.attribute_advantage
            elif def_attr == "Vi":
                return -self.attribute_advantage
        elif att_attr == "Vi":
            if def_attr == "Va":
                return -self.attribute_advantage
            elif def_attr == "Da":
                return self.attribute_advantage
        return 0

    def simulate(self, device1, device2):
        # Deep copy the teams to avoid modifying the original objects
        device1 = [copy.deepcopy(p) for p in device1]
        device2 = [copy.deepcopy(p) for p in device2]

        # Initialize Digimon states
        for pet in device1 + device2:
            pet.alive = True
            pet.current_hp = pet.hp
            pet.log = []

        # Generate attack patterns
        for pet in device1 + device2:
            pattern = get_attack_pattern(pet.level, pet.mini_game)
            pet.attack_pattern = (pattern * 2)[:12]

        rounds = 12
        battle_log = []

        for turn in range(rounds):
            turn_attacks = []

            # Team 1 attacks
            for i, pet in enumerate(device1):
                if not pet.alive:
                    continue

                # Try to attack the opposite Digimon by index
                if i < len(device2) and device2[i].alive:
                    target = device2[i]
                else:
                    # If the opposite is dead, pick the next available target
                    targets = [t for t in device2 if t.alive]
                    if not targets:
                        break
                    target = random.choice(targets)  # Pick the first available target

                # Calculate attack
                pattern = pet.attack_pattern
                base_dmg = min(pattern[turn % len(pattern)], self.damage_limit)
                dmg = base_dmg + pet.buff
                adv = self._attribute_advantage(pet.attribute, target.attribute)
                handicap = pet.handicap
                hitrate = ((pet.power * 100) / (pet.power + target.power)) + adv - handicap
                hitrate = max(0, min(hitrate, 100))
                hit = random.randint(0, 99) < hitrate
                actual_dmg = dmg if hit else 0
                target.current_hp -= actual_dmg
                if target.current_hp <= 0:
                    target.alive = False
                    target.current_hp = 0
                turn_attacks.append(AttackLog(
                    turn=turn + 1,
                    device="device1",
                    attacker=i,
                    defender=device2.index(target),
                    hit=hit,
                    damage=actual_dmg,
                    # Crit fires on the highest base damage the pattern can roll
                    # (pre-buff/level) so cosmetic damage stacking doesn't change
                    # which attacks trigger the slide-in.
                    critical=(base_dmg == 5),
                ))

            # Team 2 attacks (boss logic included)
            for i, pet in enumerate(device2):
                if not pet.alive:
                    continue

                # If this is a boss (team2 has only one member), attack all alive members of team1
                if len(device2) == 1 and not self.pvp_mode:
                    for target in [t for t in device1 if t.alive]:  # Filter only alive pets
                        pattern = pet.attack_pattern
                        base_dmg = min(pattern[turn % len(pattern)] + 1, self.damage_limit)
                        dmg = base_dmg + pet.buff
                        adv = self._attribute_advantage(pet.attribute, target.attribute)
                        handicap = pet.handicap
                        hitrate = ((pet.power * 100) / (pet.power + target.power)) + adv - handicap
                        hitrate = max(0, min(hitrate, 100))
                        hit = random.randint(0, 99) < hitrate
                        actual_dmg = dmg if hit else 0
                        target.current_hp -= actual_dmg
                        if target.current_hp <= 0:
                            target.alive = False
                            target.current_hp = 0
                        turn_attacks.append(AttackLog(
                            turn=turn + 1,
                            device="device2",
                            attacker=i,
                            defender=device1.index(target),
                            hit=hit,
                            damage=actual_dmg,
                            critical=(base_dmg == 5),
                        ))
                else:
                    # Regular attack logic for non-boss enemies
                    if i < len(device1) and device1[i].alive:
                        target = device1[i]
                    else:
                        # If the opposite is dead, pick the next available target
                        targets = [t for t in device1 if t.alive]
                        if not targets:
                            break
                        target = random.choice(targets)  # Pick the first available target

                    # Calculate attack
                    pattern = pet.attack_pattern
                    base_dmg = min(pattern[turn % len(pattern)] + 1, self.damage_limit)
                    dmg = base_dmg + pet.buff
                    adv = self._attribute_advantage(pet.attribute, target.attribute)
                    handicap = pet.handicap
                    hitrate = ((pet.power * 100) / (pet.power + target.power)) + adv - handicap
                    hitrate = max(0, min(hitrate, 100))
                    hit = random.randint(0, 99) < hitrate
                    actual_dmg = dmg if hit else 0
                    target.current_hp -= actual_dmg
                    if target.current_hp <= 0:
                        target.alive = False
                        target.current_hp = 0
                    turn_attacks.append(AttackLog(
                        turn=turn + 1,
                        device="device2",
                        attacker=i,
                        defender=device1.index(target),
                        hit=hit,
                        damage=actual_dmg,
                        critical=(base_dmg == 5),
                    ))

            # Log the state for this turn
            battle_log.append(TurnLog(
                turn=turn + 1,
                device1_status=[
                    DigimonStatus(name=p.name, hp=p.current_hp, alive=p.alive) for p in device1
                ],
                device2_status=[
                    DigimonStatus(name=p.name, hp=p.current_hp, alive=p.alive) for p in device2
                ],
                attacks=turn_attacks
            ))

            # Check for wipeout
            device1_alive = any(p.alive for p in device1)
            device2_alive = any(p.alive for p in device2)
            if not device1_alive or not device2_alive:
                break

        # Determine winner
        device1_alive = any(p.alive for p in device1)
        device2_alive = any(p.alive for p in device2)
        if device1_alive and not device2_alive:
            winner = "device1"
        elif not device1_alive and device2_alive:
            winner = "device2"
        else:
            # No wipeout, compare remaining HP
            team1_hp = sum(p.current_hp for p in device1 if p.alive)
            team2_hp = sum(p.current_hp for p in device2 if p.alive)
            if team1_hp > team2_hp:
                winner = "device1"
            elif team2_hp > team1_hp:
                winner = "device2"
            else:
                winner = "device2" if self.force_winner else "draw"

        # Prepare final result
        result =  BattleResult(
            winner=winner,
            device1_final=[
                DigimonStatus(name=p.name, hp=p.current_hp, alive=p.alive) for p in device1
            ],
            device2_final=[
                DigimonStatus(name=p.name, hp=p.current_hp, alive=p.alive) for p in device2
            ],
            battle_log=battle_log,
            device1_packets=[],
            device2_packets=[]
        )
        self.print_battle_log(result)
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
        for i, packets in enumerate(result.device1_packets):
            for packet in packets:
                binary = " ".join(f"{byte:08b}" for byte in packet)
                hex_representation = " ".join(f"{byte:02X}" for byte in packet)
                print(f"  Packet {i + 1}:")
                print(f"    Binary: {binary}")
                print(f"    Hex: {hex_representation}")

        print("Device 2 Packets:")
        for i, packets in enumerate(result.device2_packets):
            for packet in packets:
                binary = " ".join(f"{byte:08b}" for byte in packet)
                hex_representation = " ".join(f"{byte:02X}" for byte in packet)
                print(f"  Packet {i + 1}:")
                print(f"    Binary: {binary}")
                print(f"    Hex: {hex_representation}")

if __name__ == "__main__":
    # Example 1: 4x4 party battle
    device1 = [
        Digimon(name="Agumon", hp=10, attribute="Va", power=120, handicap=0, buff=0, mini_game=2, level=3, sick=0, shot1=1, shot2=1, order=0, traited=0, egg_shake=0, index=0, stage=3),
        Digimon(name="Gabumon", hp=10, attribute="Da", power=110, handicap=0, buff=1, mini_game=3, level=3, sick=0, shot1=1, shot2=1, order=1, traited=0, egg_shake=0, index=1, stage=3),
        Digimon(name="Patamon", hp=10, attribute="Va", power=100, handicap=0, buff=0, mini_game=1, level=3, sick=0, shot1=1, shot2=1, order=2, traited=0, egg_shake=0, index=2, stage=3),
        Digimon(name="Tentomon", hp=10, attribute="Vi", power=105, handicap=0, buff=0, mini_game=2, level=3, sick=0, shot1=1, shot2=1, order=3, traited=0, egg_shake=0, index=3, stage=3),
    ]
    device2 = [
        Digimon(name="Impmon", hp=10, attribute="Vi", power=115, handicap=0, buff=0, mini_game=2, level=3, sick=0, shot1=1, shot2=1, order=0, traited=0, egg_shake=0, index=0, stage=3),
        Digimon(name="Wormmon", hp=10, attribute="Da", power=108, handicap=0, buff=1, mini_game=3, level=3, sick=0, shot1=1, shot2=1, order=1, traited=0, egg_shake=0, index=1, stage=3),
        Digimon(name="Gomamon", hp=10, attribute="Va", power=102, handicap=0, buff=0, mini_game=1, level=3, sick=0, shot1=1, shot2=1, order=2, traited=0, egg_shake=0, index=2, stage=3),
        Digimon(name="Palmon", hp=10, attribute="Da", power=104, handicap=0, buff=0, mini_game=2, level=3, sick=0, shot1=1, shot2=1, order=3, traited=0, egg_shake=0, index=3, stage=3),
    ]

    sim = GlobalBattleSimulator(attribute_advantage=5, damage_limit=3)
    result = sim.simulate(device1, device2)
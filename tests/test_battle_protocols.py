"""
Battle protocol test harness
============================

Exercises the battle simulators and the real-device packet protocols without
running the game:

    python tests/test_battle_protocols.py       # run all checks
    python tests/test_battle_protocols.py -v    # + packet dumps / battle logs

Sections:
  1. Round trips: each protocol's DCom packet generator is validated and
     parsed back with the DCom-tested validators/parsers
     (dcom_battle_simulator is the ground-truth implementation), and the
     parsed fields are compared to the input Digimon.
  2. Versus simulations: BattleSimulator for DM / DMC / DM20 / PEN20 / DMX,
     checking result integrity invariants.
  3. Global protocol: GlobalBattleSimulator scenarios (1v1, adventure 4v4,
     boss, arena) checking damage caps, HP bounds and winner consistency.
"""

import os
import sys
import argparse

# Make src importable when run from the repo root (or anywhere)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO_ROOT, "src")
for p in (_SRC, _REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from battle.sim.models import Digimon, BattleProtocol  # noqa: E402
from battle.sim.battle_simulator import (  # noqa: E402
    BattleSimulator, DM20Device, PEN20Device, DMXDevice)
from battle.sim.global_battle_simulator import GlobalBattleSimulator  # noqa: E402
from battle.sim import protocol_constants  # noqa: E402
from battle.sim.dcom_battle_simulator import DComBattleSimulator  # noqa: E402
from battle.dcom.dcom_protocol import ProtocolType  # noqa: E402


def make_digimon(name="Agumon", power=120, attribute=0, hp=10, level=3,
                 stage=3, shot1=5, shot2=9, index=4, mini_game=3, buff=0,
                 order=0, traited=0, egg_shake=0, sick=0, tag_meter=0):
    return Digimon(name=name, order=order, traited=traited, egg_shake=egg_shake,
                   index=index, hp=hp, attribute=attribute, power=power,
                   handicap=0, buff=buff, mini_game=mini_game, level=level,
                   stage=stage, sick=sick, shot1=shot1, shot2=shot2,
                   tag_meter=tag_meter)


class BattleProtocolTester:
    """Collects checks and reports a pass/fail summary."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.failures = []

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    def check(self, label, condition, detail=""):
        if condition:
            self.passed += 1
            if self.verbose:
                print(f"  [ok]   {label}")
        else:
            self.failed += 1
            self.failures.append((label, detail))
            print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))

    def section(self, title):
        print()
        print("=" * 70)
        print(title)
        print("=" * 70)

    def dump_packets(self, label, packets):
        if not self.verbose:
            return
        print(f"  {label}:")
        for i, pkt in enumerate(packets, 1):
            print(f"    Packet {i}: {pkt.hex().upper()}  "
                  f"({' '.join(f'{b:08b}' for b in pkt)})")

    # ------------------------------------------------------------------
    # Section 1: DCom round trips (generator -> tested validator/parser)
    # ------------------------------------------------------------------

    def _dcom(self, protocol_type, battle_format=None):
        # No controller needed: only the send/receive steps touch hardware.
        return DComBattleSimulator(None, protocol_type, battle_format)

    def test_dm20_roundtrip(self):
        self.section("DM20 DCom round trip")
        fixture = make_digimon(power=130, attribute=1, index=7, shot1=12, shot2=3,
                               mini_game=9)
        fixture.version = 3
        device = DM20Device(fixture)
        packets = device.generate_all_packets_for_dcom(order=0)
        self.dump_packets("DM20 generated", packets)

        self.check("DM20 generates 10 packets", len(packets) == 10,
                   f"got {len(packets)}")
        dcom = self._dcom(ProtocolType.V_PET)
        self.check("DM20 packets pass tested validator",
                   dcom._validate_dm20_packets(packets))

        parsed = dcom._parse_dm20_opponent(packets)
        self.check("DM20 packets parse back", parsed is not None)
        if parsed:
            self.check("DM20 power round-trips", parsed.power == fixture.power,
                       f"{parsed.power} != {fixture.power}")
            self.check("DM20 attribute round-trips",
                       parsed.attribute == fixture.attribute,
                       f"{parsed.attribute} != {fixture.attribute}")
            self.check("DM20 index round-trips", parsed.index == fixture.index,
                       f"{parsed.index} != {fixture.index}")
            self.check("DM20 shots round-trip",
                       parsed.shot1 == fixture.shot1 and parsed.shot2 == fixture.shot2,
                       f"({parsed.shot1},{parsed.shot2}) != ({fixture.shot1},{fixture.shot2})")

    def test_pen20_roundtrip(self):
        self.section("PEN20 DCom round trip")
        fixture = make_digimon(power=110, attribute=2, index=22, shot1=30, shot2=18,
                               mini_game=7, traited=1, egg_shake=1, stage=4)
        fixture.version = 2
        device = PEN20Device(fixture)
        packets = device.generate_all_packets_for_dcom()
        self.dump_packets("PEN20 generated", packets)

        self.check("PEN20 generates 10 packets", len(packets) == 10,
                   f"got {len(packets)}")
        dcom = self._dcom(ProtocolType.PEN_X)
        self.check("PEN20 packets pass tested validator",
                   dcom._validate_pen20_packets(packets))

        parsed = dcom._parse_pen20_opponent(packets)
        self.check("PEN20 packets parse back", parsed is not None)
        if parsed:
            # PEN20 sends power WITH traited/egg-shake bonuses applied
            self.check("PEN20 boosted power round-trips",
                       parsed.power == device.power,
                       f"{parsed.power} != {device.power} (base {fixture.power})")
            self.check("PEN20 attribute round-trips",
                       parsed.attribute == fixture.attribute,
                       f"{parsed.attribute} != {fixture.attribute}")
            self.check("PEN20 index round-trips", parsed.index == fixture.index,
                       f"{parsed.index} != {fixture.index}")
            self.check("PEN20 traited/egg_shake round-trip",
                       parsed.traited == fixture.traited
                       and parsed.egg_shake == fixture.egg_shake,
                       f"({parsed.traited},{parsed.egg_shake})")

    def test_dmx_roundtrip(self, battle_format="DMX"):
        self.section(f"{battle_format} DCom round trip")
        fixture = make_digimon(power=200, attribute=0, index=15, shot1=21, shot2=6,
                               hp=22, level=7, stage=4, buff=2, mini_game=2)
        fixture.version = 1
        fixture.dmx_shot_m = 11
        device = DMXDevice(fixture)
        packets = device.generate_all_packets_for_dcom()
        self.dump_packets(f"{battle_format} generated", packets)

        self.check(f"{battle_format} generates 6 packets", len(packets) == 6,
                   f"got {len(packets)}")
        dcom = self._dcom(ProtocolType.COLOR, battle_format=battle_format)
        self.check(f"{battle_format} packets pass tested validator",
                   dcom._validate_dmx_packets(packets))

        parsed = dcom._parse_dmx_opponent(packets)
        self.check(f"{battle_format} packets parse back", parsed is not None)
        if parsed:
            self.check(f"{battle_format} hp round-trips", parsed.hp == fixture.hp,
                       f"{parsed.hp} != {fixture.hp}")
            self.check(f"{battle_format} power round-trips",
                       parsed.power == fixture.power,
                       f"{parsed.power} != {fixture.power}")
            self.check(f"{battle_format} level round-trips",
                       parsed.level == fixture.level,
                       f"{parsed.level} != {fixture.level}")
            self.check(f"{battle_format} stage round-trips",
                       parsed.stage == fixture.stage,
                       f"{parsed.stage} != {fixture.stage}")
            self.check(f"{battle_format} index round-trips",
                       parsed.index == fixture.index,
                       f"{parsed.index} != {fixture.index}")
            self.check(f"{battle_format} buff round-trips",
                       parsed.buff == fixture.buff,
                       f"{parsed.buff} != {fixture.buff}")
            self.check(f"{battle_format} attribute round-trips",
                       parsed.attribute == fixture.attribute,
                       f"{parsed.attribute} != {fixture.attribute}")

    # ------------------------------------------------------------------
    # Section 2: Versus (BattleSimulator) integrity
    # ------------------------------------------------------------------

    def _check_result_integrity(self, name, result, expect_packets):
        self.check(f"{name} produces a winner",
                   result.winner in ("device1", "device2", "draw"),
                   str(result.winner))
        self.check(f"{name} has a battle log", len(result.battle_log) > 0)
        if expect_packets:
            self.check(f"{name} produced packets",
                       len(result.device1_packets) > 0 and len(result.device2_packets) > 0)
        for side in (result.device1_final, result.device2_final):
            for status in side:
                self.check(f"{name} final HP >= 0 ({status.name})", status.hp >= 0,
                           str(status.hp))

    def test_versus_protocols(self):
        self.section("Versus simulations (BattleSimulator)")
        pairs = {
            BattleProtocol.DM_BS: "DM",
            BattleProtocol.DMC_BS: "DMC",
            BattleProtocol.DM20_BS: "DM20",
            BattleProtocol.PEN20_BS: "PEN20",
            BattleProtocol.DMX_BS: "DMX",
        }
        for protocol, name in pairs.items():
            d1 = make_digimon(name="Left", power=120, attribute=0, hp=10)
            d1.version = 1
            d2 = make_digimon(name="Right", power=110, attribute=2, hp=10, order=1,
                              index=9, shot1=2, shot2=8)
            d2.version = 1
            try:
                sim = BattleSimulator(protocol, verbose=self.verbose)
                result = sim.simulate(d1, d2)
                self._check_result_integrity(name, result, expect_packets=True)
            except Exception as exc:
                self.check(f"{name} simulate runs", False, repr(exc))

    # ------------------------------------------------------------------
    # Section 3: Global protocol (adventure / arena)
    # ------------------------------------------------------------------

    def _team(self, count, power=110, hp=10, prefix="Pet"):
        attrs = ["Va", "Da", "Vi", ""]
        return [make_digimon(name=f"{prefix}{i}", power=power + i * 5,
                             attribute=attrs[i % 4], hp=hp, index=i,
                             mini_game=2, level=3)
                for i in range(count)]

    def _check_global_result(self, name, result, damage_limit, buffs_max=0):
        self.check(f"{name} winner set",
                   result.winner in ("device1", "device2", "draw"))
        self.check(f"{name} log within 12 turns", len(result.battle_log) <= 12,
                   str(len(result.battle_log)))
        max_dmg = damage_limit + buffs_max + 1  # +1: enemy pattern bonus
        for turn in result.battle_log:
            for atk in turn.attacks:
                self.check(f"{name} damage cap", atk.damage <= max_dmg,
                           f"turn {atk.turn}: dmg {atk.damage} > {max_dmg}")
                if not atk.hit:
                    self.check(f"{name} miss deals 0", atk.damage == 0,
                               f"turn {atk.turn}")
            for status in turn.device1_status + turn.device2_status:
                self.check(f"{name} HP >= 0", status.hp >= 0,
                           f"{status.name}: {status.hp}")

    def test_global_protocol(self):
        self.section("Global protocol (GlobalBattleSimulator)")

        # 1v1
        sim = GlobalBattleSimulator(attribute_advantage=5, damage_limit=3,
                                    verbose=self.verbose)
        result = sim.simulate(self._team(1), self._team(1, prefix="Foe"))
        self._check_global_result("global 1v1", result, damage_limit=3)

        # Adventure 4v4
        result = sim.simulate(self._team(4), self._team(4, prefix="Foe"))
        self._check_global_result("global 4v4", result, damage_limit=3)

        # Boss battle: 4 pets vs 1 boss (boss attacks the whole party)
        boss = [make_digimon(name="Boss", power=200, attribute="Vi", hp=40)]
        result = sim.simulate(self._team(4), boss)
        self._check_global_result("global boss", result, damage_limit=3)
        boss_hits = [a for t in result.battle_log for a in t.attacks
                     if a.device == "device2"]
        multi_target = len({a.defender for a in boss_hits}) > 1 if boss_hits else False
        self.check("global boss attacks multiple pets", multi_target or not boss_hits)

        # Arena: full party vs full party with buffs and a higher damage limit
        arena_sim = GlobalBattleSimulator(attribute_advantage=5, damage_limit=5,
                                          pvp_mode=True, verbose=self.verbose)
        team_a = self._team(4, power=150, hp=14, prefix="A")
        team_b = self._team(4, power=145, hp=14, prefix="B")
        for pet in team_a:
            pet.buff = 1
        result = arena_sim.simulate(team_a, team_b)
        self._check_global_result("arena 4v4", result, damage_limit=5, buffs_max=1)
        # pvp_mode: a lone survivor on team B must not gain boss behavior
        self.check("arena has no boss multi-target",
                   all(a.defender >= 0 for t in result.battle_log for a in t.attacks))

    # ------------------------------------------------------------------

    def run(self):
        self.test_dm20_roundtrip()
        self.test_pen20_roundtrip()
        self.test_dmx_roundtrip("DMX")
        self.test_dmx_roundtrip("PENZ")
        self.test_versus_protocols()
        self.test_global_protocol()

        print()
        print("=" * 70)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        if self.failures:
            print("Failures:")
            for label, detail in self.failures:
                print(f"  - {label}" + (f" ({detail})" if detail else ""))
        print("=" * 70)
        return self.failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Battle protocol test harness")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print packet dumps and battle logs")
    args = parser.parse_args()

    tester = BattleProtocolTester(verbose=args.verbose)
    sys.exit(0 if tester.run() else 1)

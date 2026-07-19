"""
Battle protocol constants
=========================

Single source of truth for the real-device battle protocol constants.

POLICY: the DCom exchange path (``dcom_battle_simulator`` + the device
classes' ``generate_all_packets_for_dcom``) was validated against real
Digimon devices and is considered the correct implementation. Values here
are the ones that tested path effectively used. Where the community protocol
documentation disagrees with tested behavior, the difference is called out
in the comments — do not "fix" those without re-testing on hardware.

The old ``src/data/protocols/*.json`` definitions were removed: they were
never used for packing/unpacking (the field extractor was a stub), several
never loaded at all (``PENZ.json`` was malformed, ``Pen20.json`` failed the
case-sensitive lookup on Linux/Android), and their values had drifted from
the tested code (e.g. DM20 fixed HP 4 vs the tested 5).

Packet layouts live as documented bit-packing in the device classes in
``battle_simulator.py`` (DM20Device, PEN20Device, DMXDevice, DMCDevice,
DMDevice); the parsing/validation mirrors live in
``dcom_battle_simulator``. ``tests/test_battle_protocols.py`` round-trips
generation through the tested parsers to keep the two in sync.

Reference document (bit layouts, checksum targets):
https://docs.google.com/document/d/11CuxpKQFaHexAbi8jHX4UnfhZVfovwDAXo5xYZCEDpM
"""


class DM:
    """Digital Monster (Original, 1997) — slot-based battle.

    2 packets of 16 bits each; no EOL marker, validation is done by
    mirrored (bit-inverted) copies of each field inside the packet.
    Packet 1: mirrors byte + (Boost(4) | Slot(4)); Packet 2: mirrors byte +
    (Version(4) | Outcome(4)). Outcome: 1 = victory, 2 = defeat.
    The power->slot table and the slot-vs-slot win-probability matrix are
    hardcoded in BattleSimulator._get_dm_slot_from_power /
    _get_dm_win_probability.
    """
    NAME = "DM"
    DISPLAY_NAME = "DM (Original Digital Monster)"
    PACKET_COUNT = 2
    FIXED_HP = 5          # in-game versus HP; real DM has no HP exchange
    TURNS = 4             # 3 normal + 1 finishing (in-game presentation)
    VERSION_RANGE = (1, 5)


class DM20:
    """Digital Monster Ver.20th — 10 packet exchange.

    Packets (16 bits each):
      1: Name_2(8)  | Name_1(8)              (tamer name, chars 2/1)
      2: Name_4(8)  | Name_3(8)              (tamer name, chars 4/3)
      3: Order(1)   | Pattern(5) | Operation(2) | Version(4) | EOL(4)
      4: COU(2)     | Index_L(8) | Attribute_L(2) | EOL(4)
      5: Shot_S_L(6)| Shot_W_L(6)| EOL(4)
      6: COU(4)     | Power_L(8) | EOL(4)
      7: COU(2)     | Index_R(8) | Attribute_R(2) | EOL(4)   (0 for single)
      8: Shot_S_R(6)| Shot_W_R(6)| EOL(4)                    (0 for single)
      9: Tag_Meter(4)| Power_R(8)| EOL(4)                    (0 for single)
      A: Check(4)   | Dodges(4)  | Hits(4)   | EOL(4)

    Checksum: sum of every nibble of all 10 packets must be ≡ 0 (mod 16);
    the Check nibble is chosen to satisfy that. Attribute: 0=Va 1=Da 2=Vi
    3=Free. Hits/Dodges are 4-bit patterns read right-to-left, repeated
    when more than 4 rounds are needed; in single battles the opponent's
    values are the inversion of ours.
    """
    NAME = "DM20"
    DISPLAY_NAME = "DM20 (V-Pet/Pendulum/Progress)"
    PACKET_COUNT = 10
    EOL = 0b1110          # 0xE end-of-line marker on packets 3..A
    DEFAULT_VERSION = 1
    VERSION_RANGE = (1, 5)
    # Tested with real devices via DCom: DM20 battles run with 5 HP.
    # (The removed DM20.json said 4 — the JSON value was wrong.)
    FIXED_HP = 5
    CHECKSUM_REMAINDER = 0
    MINIGAME = "dummy"    # 0-14 taps -> attack pattern index


class PEN20:
    """Digimon Pendulum Ver.20th — 10 packet exchange.

    Packets (16 bits each):
      1: Order(1) | COU(1) | Attack(4) | Operation(2) | Version(4) | EOL(4)
      2: COU(2)   | Index(8)   | Attribute(2) | EOL(4)
      3: COU(4)   | Shot_W(8)  | EOL(4)
      4: Sick(1)  | COU(3) | Shot_S(8) | EOL(4)
      5: COU(2)   | Traited(1) | Egg_Shake(1) | Power(8) | EOL(4)
      6: Copy(2)  | Index_R(8) | Attribute_R(2) | EOL(4)  (0 for single)
      7: COU(4)   | Shot_W_R(8)| EOL(4)                   (0 for single)
      8: COU(4)   | Shot_S_R(8)| EOL(4)                   (0 for single)
      9: COU(4)   | Power_R(8) | EOL(4)                   (0 for single)
      A: Check(4) | Dodges(4)  | Hits(4) | EOL(4)

    NOTE: the protocol document lists the Pen20 checksum target as 12, but
    the DCom-tested implementation generates and validates with target 0
    (same rule as DM20, see _validate_pen20_packets). Keeping the tested
    value; re-verify against a real Pen20 before changing.

    Power bonuses applied before sending (see PEN20Device):
    egg shake +10; traited: stage3 +5, stage4 +8, stage5 +15, stage6+ +20.
    """
    NAME = "PEN20"
    DISPLAY_NAME = "PEN20 (Pendulum 20th)"
    PACKET_COUNT = 10
    EOL = 0b1110
    DEFAULT_VERSION = 1
    VERSION_RANGE = (1, 4)
    FIXED_HP = 5
    CHECKSUM_REMAINDER = 0   # doc says 12 — tested behavior is 0
    MINIGAME = "dummy"


class DMX:
    """Digital Monster X / Digimon Pendulum Z — 6 packet exchange.

    PENZ uses the identical packet format; only the pre-battle minigame
    differs (DMX: XAI roll+bar, PENZ: count match). DCom selects it via
    the ``battle_format='PENZ'`` override.

    Packets (16 bits each):
      1: Order(1) | Level(4) | Sick(1) | Attack(2) | Version(4) | EOL(4)
      2: Stage(3) | Index(7) | Attribute(2) | EOL(4)
      3: Shot_S(6)| Shot_W(6)| EOL(4)
      4: COU(2)   | HP(5)    | Shot_M(5) | EOL(4)
      5: COU(2)   | Buff(2)  | Power(8)  | EOL(4)
      6: Check(4) | COU(3)   | Hits(5)   | EOL(4)

    Checksum: nibble sum of all 6 packets ≡ 8 (mod 16). Attack quality:
    0=Bad 1=Good 2=Great 3=Excellent. Hits: 5-bit pattern right-to-left,
    5-round battle. Variable HP (5-bit field). Power capped at 255 to
    avoid the V1 hardware overflow. Attribute advantage: +32 power.
    """
    NAME = "DMX"
    DISPLAY_NAME = "DMX / Pendulum Z"
    PACKET_COUNT = 6
    EOL = 0b1110
    DEFAULT_VERSION = 0
    VERSION_RANGE = (1, 6)
    FIXED_HP = None       # variable, 5-bit (max 31)
    DEFAULT_HP = 12       # fallback when a pet has no HP (stage 4 value)
    TURNS = 5
    MAX_POWER = 255
    CHECKSUM_REMAINDER = 8
    ATTRIBUTE_ADVANTAGE = 32
    MINIGAME = "xai"      # PENZ: "count_match"


# PENZ shares the DMX wire format; alias for readability at call sites.
PENZ = DMX


class DMC:
    """Digital Monster Color — 16-byte packets, 4 operations.

    Packet 1 (op 0/1): "DMCL"(32) | Operation(16) | Version(16) | Index(16)
                       | Power(16) | Attribute(16) | Check(16)
    Packet 2 (op 2/3): "DMCL"(32) | Operation(16) | Shot(16) | Outcome(16)
                       | COU(32) | Check(16)
    Check = sum of all preceding 16-bit words (low 16 bits kept).

    NOTE: per the protocol document DMC's *wire* attribute encoding differs
    from every other device (0=Free 1=Virus 2=Data 3=Vaccine) and the
    advantage cycle is Free>Virus>Data>Vaccine>Free. The in-game DMC versus
    simulation still uses the internal 0=Va encoding on both sides (self-
    consistent, so outcomes are unaffected); translate at the wire boundary
    before ever talking to a real DMC over DCom.
    """
    NAME = "DMC"
    DISPLAY_NAME = "DMC (Digital Monster Color)"
    PACKET_COUNT = 2
    MAGIC = 0x47444C43
    TURNS = 5
    FIXED_HP = 5          # in-game versus presentation (winner 1112 / loser 1111)
    VERSION_RANGE = (1, 5)


# OEM mode: when the pet's module battle_protocol matches the connected
# device's format, the pet's real index/version are sent so the device can
# run unlocks; out-of-range versions are sent as 0 (special).  Shared by
# dcom_view and battle_encounter_dcom (previously duplicated in both).
VERSION_RANGES = {
    'DM': DM.VERSION_RANGE,
    'DM20': DM20.VERSION_RANGE,
    'DMX': DMX.VERSION_RANGE,
    'DMC': DMC.VERSION_RANGE,
    'PEN': (0, 5),
    'PEN20': PEN20.VERSION_RANGE,
    'PENZ': (0, 5),
    'PENC': (0, 7),
}


def get_constants(protocol_name: str):
    """Constants class for a protocol name ('PENZ' resolves to DMX format)."""
    return {
        'DM': DM, 'DM20': DM20, 'PEN20': PEN20,
        'DMX': DMX, 'PENZ': PENZ, 'DMC': DMC,
    }.get(protocol_name)

import json
import os


def _load_json(file_path):
    """Load a JSON file directly.

    Paths here are built from __file__ and are already absolute, so no
    Android APP_ROOT resolution is needed. (The old optional import of
    utils.asset_utils.open_json had a broken fallback that returned parsed
    JSON where a file handle was expected, crashing any standalone use.)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


DMX_PATTERN_TABLE = None
DM20_PATTERN_TABLE = None
DM20_TAG_PATTERNS = None  # Loaded from JSON

# DM20 single battle attack patterns (verified from actual DM20 device)
# 15 patterns (0-14), each with 4 attack values (first 4 of 5-attack sequence)
# Pattern index directly corresponds to minigame taps (0-14)
# Values are direct damage: 1 or 2
# Full patterns: 11211, 11211, 11211, 12121, 12121, 21122, 21122, 21212, 21212, 12221, 21222, 21222, 22222, 22222, 22222
DM20_ATTACK_PATTERNS_SINGLE = [
    [1,1,2,1], [1,1,2,1], [1,1,2,1], [1,2,1,2], [1,2,1,2],
    [2,1,1,2], [2,1,1,2], [2,1,2,1], [2,1,2,1], [1,2,2,2],
    [2,1,2,2], [2,1,2,2], [2,2,2,2], [2,2,2,2], [2,2,2,2]
]

# DM20 damage values - direct damage, no mapping needed
DM20_DAMAGE_VALUES = [1, 2, 3]  # Possible damage values (3 for critical in tag battles)


def load_dm20_tag_patterns():
    """Load DM20 tag battle patterns from JSON file."""
    global DM20_TAG_PATTERNS
    
    if DM20_TAG_PATTERNS is not None:
        return DM20_TAG_PATTERNS
    
    try:
        json_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'attack_patterns', 'DM20.json')
        with open(json_path, 'r') as f:
            DM20_TAG_PATTERNS = json.load(f)
        return DM20_TAG_PATTERNS
    except Exception as e:
        print(f"Warning: Could not load DM20 tag patterns: {e}")
        return []


def get_dm20_pattern_index_from_taps(taps: int) -> int:
    """
    Convert minigame button taps (0-14) to DM20 pattern index (0-15).
    
    In DM20 protocol, the pattern index (0-14) directly corresponds to 
    the number of button presses in the minigame. Pattern 15 is treated as 14.
    
    Args:
        taps: Number of button presses in minigame (0-14)
        
    Returns:
        Pattern index (0-14) to use in Packet 3
    """
    # Clamp to valid range and use directly as pattern index
    return max(0, min(14, taps))


def get_dm20_single_battle_attack_pattern(pattern_index: int, minigame_taps: int = 0) -> list:
    """
    Get DM20 attack pattern for single battles.
    
    Args:
        pattern_index: Pattern index from Packet 3 (0-14)
        minigame_taps: Number of button presses in minigame (not used, kept for compatibility)
        
    Returns:
        List of 4 damage values [1-2] for the battle
    """
    # Clamp pattern index to valid range (0-14)
    pattern_index = max(0, min(14, pattern_index))
    
    # Get pattern directly (values are already final damage values)
    damage_pattern = DM20_ATTACK_PATTERNS_SINGLE[pattern_index]
    
    return damage_pattern


def get_dm20_tag_battle_attack_pattern(bar1: int, bar2: int, taps: int) -> list:
    """
    Get DM20 attack pattern for tag battles.
    
    In tag battles, the pattern depends on:
    - bar1: Tag meter value for device1 (0-3)
    - bar2: Tag meter value for device2 (0-7) 
    - taps: Number of button presses (0-14)
    
    Args:
        bar1: Tag meter for device1 (0-3)
        bar2: Tag meter for device2 (0-7)
        taps: Number of button presses in minigame (0-14)
        
    Returns:
        List of 5 damage values [1-3] for tag battle (includes critical hits)
        Returns first 4 if pattern not found (fallback to single battle pattern)
    """
    patterns = load_dm20_tag_patterns()
    
    if not patterns:
        # Fallback to single battle pattern
        return get_dm20_single_battle_attack_pattern(taps)
    
    # Find matching pattern
    for entry in patterns:
        if entry['bar1'] == bar1 and entry['bar2'] == bar2 and taps in entry['taps']:
            return entry['pattern']
    
    # No match found - use single battle pattern as fallback
    single_pattern = get_dm20_single_battle_attack_pattern(taps)
    # Extend to 5 attacks by duplicating first attack (as per DM20 spec)
    return single_pattern + [single_pattern[0]]

def get_attack_pattern(level, mini_game, protocol="DMX"):
    if protocol == "DMX":
        global DMX_PATTERN_TABLE
        if DMX_PATTERN_TABLE is None:
            pattern_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "attack_patterns", "DMX.json")
            DMX_PATTERN_TABLE = _load_json(pattern_path)
        # Find the pattern_id for this level and mini_game
        for assign in DMX_PATTERN_TABLE["assignments"]:
            if assign["level"] == level and assign["mini-game"] == mini_game:
                pattern_id = assign["pattern_id"]
                break
        else:
            pattern_id = 1  # fallback
        # Find the pattern itself
        for pat in DMX_PATTERN_TABLE["patterns"]:
            if pat["id"] == pattern_id:
                return pat["pattern"]
        return [1, 1, 1, 1, 1]  # fallback
    elif protocol == "DMC_WINNER":
        # DMC uses a fixed pattern for now
        return [1, 1, 1, 1, 2]
    elif protocol == "DMC_LOOSER":
        # DMC uses a fixed pattern for now
        return [1, 1, 1, 1, 1]
    elif protocol == "PEN20":
        # PEN20 uses DM20 attack patterns
        # For single battles, tag_meter should be 0
        return get_dm20_single_battle_attack_pattern(mini_game) + [get_dm20_single_battle_attack_pattern(mini_game)[0]]

def get_dm20_attack_pattern(tag_meter, taps):
    """
    Retrieves the correct attack pattern for the DM20 protocol based on tag_meter and taps.
    This is the legacy method - use get_dm20_single_battle_attack_pattern for single battles.
    
    :param tag_meter: The tag meter value (0-3) for tag battles, or 0 for single battles
    :param taps: The number of taps (0-14) from the minigame
    :return: A list representing the attack pattern [1-5 damage values]
    """
    global DM20_PATTERN_TABLE
    if DM20_PATTERN_TABLE is None:
        # Load the DM20 pattern table from the JSON file
        pattern_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "attack_patterns", "DM20.json")
        DM20_PATTERN_TABLE = _load_json(pattern_path)

    # Search for the matching pattern in the table
    for entry in DM20_PATTERN_TABLE:
        if entry["bar1"] == tag_meter and taps in entry["taps"]:
            return entry["pattern"]

    # Fallback pattern if no match is found
    return [1, 1, 1, 1, 1]
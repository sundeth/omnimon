"""
Game Digidex
Tracks which pets the player has obtained (unlocked) across all modules.
The digidex file is stored per save folder so that Free Mode and each
Progress Mode player have their own independent progress.
"""

import json
import os

# Legacy path (used only as a migration fallback)
_LEGACY_DIGIDEX_PATH = "save/digidex.json"

# Filename within each save folder
_DIGIDEX_FILENAME = "digidex.json"


def _get_digidex_path() -> str:
    """Get the path to the digidex file in the current save directory.

    The digidex is stored inside the game-mode-specific save folder
    (e.g. save/Default/digidex.json or save/<player_id>/digidex.json).

    Returns:
        Full path to the digidex JSON file.
    """
    from core import game_globals
    save_dir = game_globals.get_save_dir()
    return os.path.join(save_dir, _DIGIDEX_FILENAME)


def load_digidex() -> list[dict]:
    """Load the digidex progress file.

    Returns a list of unlocked pets.
    Each item contains: { "name": str, "module": str, "version": int }

    Falls back to the legacy root save/digidex.json if the per-folder
    file does not exist yet (pre-migration saves).
    """
    path = _get_digidex_path()
    if not os.path.exists(path):
        # Fallback: try legacy root-level digidex
        if os.path.exists(_LEGACY_DIGIDEX_PATH):
            return _load_from_path(_LEGACY_DIGIDEX_PATH)
        return []
    return _load_from_path(path)


def _load_from_path(path: str) -> list[dict]:
    """Read and parse a digidex JSON file at the given path."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_digidex(entries: list[dict]) -> None:
    """Save the full list of known pets to the digidex file."""
    path = _get_digidex_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def register_digidex_entry(name: str, module: str, version: int) -> None:
    """Add a pet to the digidex if it is not already present."""
    data = load_digidex()
    exists = any(
        p["name"] == name and p["module"] == module and p["version"] == version
        for p in data
    )
    if not exists:
        data.append({"name": name, "module": module, "version": version})
        save_digidex(data)


def is_pet_unlocked(name: str, module: str, version: int) -> bool:
    """Check whether a specific pet has already been unlocked."""
    data = load_digidex()
    return any(
        p["name"] == name and p["module"] == module and p["version"] == version
        for p in data
    )
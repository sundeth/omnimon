"""
Navigation Utilities
Centralized helper functions for game navigation decisions and scene routing.

Used by multiple scenes (Boot, Setup, Tutorial, Login, Error, EggSelection, Connect)
to avoid code duplication and ensure consistent navigation behavior.
"""

import os
import pickle
from typing import Optional

from core import game_globals, runtime_globals
from services.omninet_service import omninet_service
from utils.scene_utils import change_scene


def has_save_file() -> bool:
    """Check if a save file exists for the current game mode and player.

    Inspects the current save directory (determined by game mode and player_id)
    for any save_data_*.dat files without loading them.

    Returns:
        True if at least one save file exists in the current save directory.
    """
    if not game_globals._can_access_save_dir():
        return False

    save_dir = game_globals.get_save_dir()
    if not os.path.exists(save_dir):
        return False

    for filename in os.listdir(save_dir):
        if filename.startswith("save_data") and filename.endswith(".dat"):
            return True
    return False


def has_freezer_pets() -> bool:
    """Check if there are any pets stored in the freezer save file.

    Uses the game-mode-specific save directory to find freezer.pkl.
    Loads the freezer data and checks for non-None pet entries.

    Returns:
        True if freezer.pkl exists and contains at least one pet.
    """

    if not game_globals._can_access_save_dir():
        return False

    save_dir = game_globals.get_save_dir()
    freezer_path = os.path.join(save_dir, "freezer.pkl")

    if not os.path.exists(freezer_path):
        return False

    try:
        with open(freezer_path, "rb") as f:
            freezer_data = pickle.load(f)
            for page in freezer_data:
                if (hasattr(page, 'pets') and page.pets
                        and any(pet is not None for pet in page.pets)):
                    return True
            return False
    except Exception:
        return False


def has_modules_installed() -> bool:
    """Check if any game modules are installed (loaded into memory).

    Returns:
        True if at least one module is loaded in runtime_globals.game_modules.
    """
    return len(runtime_globals.game_modules) > 0


def has_owned_modules() -> bool:
    """Check if the player owns any modules.

    In Free Mode, all installed modules are considered "owned".
    In Progress Mode, checks the player's purchase list against installed modules.
    The Tutorial module is excluded from this check.

    Returns:
        True if the player owns at least one module.
    """

    if game_globals.is_free_mode():
        return has_modules_installed()

    # Progress Mode: check if any installed module is owned
    for module_name in runtime_globals.game_modules:
        if module_name.lower() == "tutorial":
            continue
        if game_globals.purchases.owns_module_name(module_name):
            return True
    return False


def has_installed_owned_modules() -> bool:
    """Check if the player has at least one installed module that they also own.

    In Free Mode, this is equivalent to has_modules_installed() (excluding Tutorial).
    In Progress Mode, checks that at least one owned module is also installed.

    Returns:
        True if at least one owned module is installed.
    """

    # Count non-tutorial installed modules
    installed_non_tutorial = [
        name for name in runtime_globals.game_modules
        if name.lower() != "tutorial"
    ]

    if game_globals.is_free_mode():
        return len(installed_non_tutorial) > 0

    # Progress Mode: check ownership of installed modules
    for module_name in installed_non_tutorial:
        if game_globals.purchases.owns_module_name(module_name):
            return True
    return False


def has_device_key() -> bool:
    """Check if the device has stored Omninet credentials (device key).

    Returns:
        True if a device key exists in the omninet service credentials.
    """
    return omninet_service.has_saved_credentials()


def get_player_id() -> Optional[str]:
    """Get the cached player ID from omninet service credentials.

    The player ID is a UUID string assigned by the Omninet server.
    It is cached locally in omninet_device.json after successful device validation.

    Returns:
        The player ID string if available, None otherwise.
    """
    return omninet_service.get_player_id()


def route_to_next_scene(check_setup_flags: bool = False,
                        check_tutorial: bool = True) -> None:
    """Route to the appropriate next scene based on current game state.

    This is the common routing pattern used after boot, setup completion, tutorial,
    login, and error recovery. The routing priority is:

        1. Setup scene (if check_setup_flags=True and a setup flag is active)
        2. Tutorial scene (if check_tutorial=True and show_tutorial is True)
        3. Main game (if the save file has pets in the party)
        4. Freezer box (if no party pets but freezer has pets)
        5. Egg selection (if no pets anywhere)

    Args:
        check_setup_flags: If True, check setup_input/setup_graphics flags first.
        check_tutorial: If True, check the show_tutorial flag.
    """

    # 0. Progress Mode login gate — must authenticate before anything else.
    # Any error (network, missing service, etc.) in Progress Mode also
    # routes to login so the user has a path to recover or switch to Free.
    if game_globals.is_progress_mode():
        try:
            authenticated = omninet_service.is_logged_in()
        except Exception as exc:
            runtime_globals.game_console.log(
                f"[Navigation] Login check failed: {exc}; routing to login")
            authenticated = False
        if not authenticated:
            change_scene("login")
            runtime_globals.game_console.log(
                "[Navigation] Routing to Login (Progress Mode, not authenticated)")
            return

    # 1. Setup flags (input or graphics configuration still needed)
    if check_setup_flags:
        if game_globals.setup_input or game_globals.setup_graphics:
            change_scene("setup")
            runtime_globals.game_console.log(
                "[Navigation] Routing to Setup (setup flags active)")
            return

    # 2. Tutorial
    if check_tutorial and game_globals.show_tutorial:
        change_scene("tutorial")
        runtime_globals.game_console.log("[Navigation] Routing to Tutorial")
        return

    # 3. Has pets in party → main game
    if game_globals.pet_list:
        change_scene("game")
        runtime_globals.game_console.log(
            "[Navigation] Routing to MainGame (pets in party)")
        return

    # 4. No party pets but freezer has pets → freezer box
    if has_freezer_pets():
        change_scene("freezer")
        runtime_globals.game_console.log(
            "[Navigation] Routing to FreezerBox (pets in freezer)")
        return

    # 5. No pets anywhere → egg selection
    change_scene("egg")
    runtime_globals.game_console.log(
        "[Navigation] Routing to EggSelection (no pets)")

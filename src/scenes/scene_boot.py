"""Scene Boot
Initial boot scene responsible for setting up the game start.
Shows the Omnipet logo, plays optional sounds, then routes to the
appropriate scene based on game state.

Navigation flow:
    1. No game mode preference → SceneSetup (first-time setup)
    2. Setup flags active → SceneSetup (incomplete setup)
    3. Progress Mode + device key → validate with server; fail → SceneError
    4. No modules + no internet → SceneError
    5. Otherwise → route_to_next_scene (tutorial → game → freezer → egg)
"""

import pygame
import socket

from ui.windows.window_background import WindowBackground
from core import game_globals, runtime_globals
import core.constants as constants
from utils.module_utils import get_module
from utils.pet_utils import distribute_pets_evenly
from utils.pygame_utils import blit_with_cache, sprite_load_percent
from utils.scene_utils import change_scene
from utils import navigation_utils


def check_internet_connection(timeout: float = 2.0) -> bool:
    """
    Check if there is an active internet connection.
    
    Args:
        timeout: Connection timeout in seconds.
        
    Returns:
        True if internet is available, False otherwise.
    """
    try:
        # Try to connect to Google's DNS server
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except (socket.timeout, socket.error, OSError):
        pass
    
    # Try alternative - Cloudflare DNS
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
        return True
    except (socket.timeout, socket.error, OSError):
        pass
    
    return False


#=====================================================================
# SceneBoot
#=====================================================================
class SceneBoot:
    """
    Boot scene for the Virtual Pet game.
    Shows background while initializing the next scene.
    """

    def __init__(self) -> None:
        """
        Initializes the boot scene with a temporary timer.
        """
        self.background = WindowBackground(True)
        # Use "Fit" method for logo image for both landscape and portrait devices
        if runtime_globals.SCREEN_WIDTH >= runtime_globals.SCREEN_HEIGHT:
            self.logo = sprite_load_percent(constants.OMNIPET_LOGO_PATH, percent=100, keep_proportion=True, base_on="height")
        else:
            self.logo = sprite_load_percent(constants.OMNIPET_LOGO_PATH, percent=100, keep_proportion=True, base_on="width")

        self.boot_timer = int(120 * (game_globals.configuration.frame_rate / 30))
        self.f12_press_count = 0  # Track F12 presses for debug toggle

        # Eagerly load sound effects now that the Android environment
        # (IS_ANDROID / APP_ROOT) is configured.  GameSound was
        # instantiated when runtime_globals was first imported — too
        # early to safely resolve paths on Android — so we defer the
        # preload to here.  No-op on subsequent boot scene re-entries.
        try:
            runtime_globals.game_sound.load_sounds()
        except Exception as exc:
            runtime_globals.game_console.log(
                f"[SceneBoot] sound preload failed: {exc}")

        runtime_globals.game_console.log("[SceneBoot] Initialized")

    def update(self) -> None:
        """
        Updates the boot scene, transitioning to the appropriate next scene after the timer expires.
        """
        self.boot_timer -= 1

        if self.boot_timer <= 0:
            self.transition_to_next_scene()

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draws the boot background.
        """
        self.background.draw(surface)
        # Center the logo image
        sprite_rect = self.logo.get_rect(center=(runtime_globals.SCREEN_WIDTH // 2, runtime_globals.SCREEN_HEIGHT // 2))
        blit_with_cache(surface, self.logo, sprite_rect)

    def handle_event(self, event) -> None:
        """Handle key press events. A/B/START/LCLICK skips boot. F12 x3 toggles debug."""

        event_type, event_data = event

        if event_type in ["A", "B", "START", "LCLICK"]:
            runtime_globals.game_sound.play("menu")
            runtime_globals.game_console.log("[SceneBoot] Skipped boot timer")
            self.boot_timer = 0
        elif event_type == "F12":
            self.f12_press_count += 1
            runtime_globals.game_console.log(f"[SceneBoot] F12 pressed ({self.f12_press_count}/3)")
            if self.f12_press_count >= 3:
                game_globals.configuration.debug_mode = not game_globals.configuration.debug_mode
                status = "enabled" if game_globals.configuration.debug_mode else "disabled"
                runtime_globals.game_sound.play("attack_fail")
                runtime_globals.game_console.log(f"[SceneBoot] Debug mode {status}")
                self.f12_press_count = 0

    def transition_to_next_scene(self) -> None:
        """Route to the appropriate next scene based on game state.

        Priority:
            1. No game mode → setup
            2. Setup flags → setup
            3. Progress Mode + device key → validate on server
            4. No modules + no internet → error
            5. Refresh pets → route_to_next_scene
        """
        # 1. No game mode chosen yet → first-time setup
        if not game_globals.has_game_mode_preference():
            change_scene("setup")
            runtime_globals.game_console.log("[SceneBoot] → Setup (no game mode)")
            return

        # 2. Setup flags still pending (input or graphics)
        if game_globals.setup_input or game_globals.setup_graphics:
            change_scene("setup")
            runtime_globals.game_console.log("[SceneBoot] → Setup (setup flags)")
            return

        # 3. Progress Mode: validate device credentials with server
        if game_globals.is_progress_mode() and navigation_utils.has_device_key():
            self._validate_progress_mode()
            return

        # 4. No modules + no internet → error
        if not navigation_utils.has_modules_installed():
            if not check_internet_connection():
                from scenes.scene_error import SceneError
                SceneError.set_error(
                    message="NO MODULE DETECTED",
                    bottom_message="Connect to the internet or install a module manually"
                )
                change_scene("error")
                runtime_globals.game_console.log("[SceneBoot] → Error (no modules, no internet)")
                return

        # 5. Refresh pets and route to next scene
        self._refresh_pets()
        navigation_utils.route_to_next_scene(check_tutorial=True)

    def _validate_progress_mode(self) -> None:
        """Validate server credentials for Progress Mode.

        On success, syncs player_id and continues to normal routing.
        On failure, shows SceneError with retry / switch-to-free-mode options.
        """
        from services.omninet_service import omninet_service

        runtime_globals.game_console.log("[SceneBoot] Validating device credentials")
        success, message, user_info = omninet_service.validate_device()

        if success:
            # Sync player_id into game_globals (server may have refreshed it)
            server_id = omninet_service.get_player_id()
            if server_id:
                game_globals.set_player_id(server_id)
            runtime_globals.game_console.log("[SceneBoot] Server validation OK")

            # Still check modules
            if not navigation_utils.has_modules_installed():
                if not check_internet_connection():
                    from scenes.scene_error import SceneError
                    SceneError.set_error(
                        message="NO MODULE DETECTED",
                        bottom_message="Connect to the internet or install a module manually"
                    )
                    change_scene("error")
                    return

            self._refresh_pets()
            navigation_utils.route_to_next_scene(check_tutorial=True)
        else:
            runtime_globals.game_console.log(
                f"[SceneBoot] Server validation failed: {message}")
            from scenes.scene_error import SceneError
            SceneError.set_error(
                message=f"SERVER: {message}",
                action_a=("boot", "Retry"),
                action_b=("switch_free", "Free Mode"),
            )
            change_scene("error")

    def _refresh_pets(self) -> None:
        """Refresh pet data from modules before entering the game scene.

        Reloads evolution data, resets positions and states, and distributes
        pets evenly.  Only meaningful at boot before SceneGame.
        """
        if not game_globals.pet_list:
            return

        for pet in game_globals.pet_list:
            module = get_module(pet.module)
            pet_data = module.get_monster(pet.name, pet.version)
            if pet_data:
                pet.evolve = pet_data.get("evolve", [])
            pet.begin_position()
            if pet.state not in ["dead", "hatch", "nap"]:
                pet.set_state("idle")
            pet.patch()
        distribute_pets_evenly()

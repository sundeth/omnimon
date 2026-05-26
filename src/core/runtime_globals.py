import os
import sys
import random

# Defence-in-depth: on some Android emulators (notably Bluestacks) the
# entry-point script's ``sys.path.insert(0, '<app>/src')`` doesn't take
# effect before this module is imported, and the top-level
# ``from input.X import Y`` lines below fail with ModuleNotFoundError.
# Try several roots to locate the sibling ``input`` package and add its
# parent (i.e. ``src/``) to sys.path before the imports run.
def _ensure_src_on_path():
    candidates = []
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.dirname(here))           # .../src
    except Exception:
        pass
    try:
        cwd = os.getcwd()
        candidates.append(os.path.join(cwd, "src"))        # <app>/src
        candidates.append(cwd)                              # <app> (if src already on path)
    except Exception:
        pass
    for src in candidates:
        try:
            if src and os.path.isdir(os.path.join(src, "input")) and src not in sys.path:
                sys.path.insert(0, src)
                return
        except Exception:
            continue

_ensure_src_on_path()

from models.game_console import GameConsole
from models.game_item import GameItem
from models.game_message import GameMessage
from models.game_sound import GameSound
from input.i2c_utils import I2CUtils
from input.input_manager import InputManager
from input.shake_detector import ShakeDetector

#=====================================================================
# Runtime (Non-Persistent) Global Variables
#=====================================================================

# --- Android Environment ---
APP_ROOT = ""  # Set to os.getcwd() on Android for absolute path building
IS_ANDROID = False  # Set to True when running on Android

KEYBOARD_MODE = 1
MOUSE_MODE = 2
TOUCH_MODE = 3
GPIO_MODE = 4
INPUT_MODE = KEYBOARD_MODE
INPUT_MODE_FORCED = False  # If True, INPUT_MODE won't auto-switch based on input device

def use_virtual_keyboard() -> bool:
    """Return True when the on-screen virtual keyboard should be shown.

    Android relies on the native system keyboard (handled separately).
    Touch / GPIO modes have no physical keyboard; the virtual one is needed.
    Mouse / Keyboard modes assume a physical keyboard and skip the overlay.
    """
    if IS_ANDROID:
        return False
    return INPUT_MODE in (TOUCH_MODE, GPIO_MODE)

# --- Resolution and Scaling (Mutable) ---
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 240
UI_SCALE = 1.0
PET_WIDTH = 48
PET_HEIGHT = 48
MENU_ICON_SIZE = 24
OPTION_ICON_SIZE = 48
OPTION_FRAME_WIDTH = 96
OPTION_FRAME_HEIGHT = 116
PET_ICON_SIZE = 48
FONT_SIZE_SMALL = 24
FONT_SIZE_MEDIUM = 28
FONT_SIZE_MEDIUM_LARGE = 30
FONT_SIZE_LARGE = 40

# --- Scene and State Control ---
game_state = "boot"
game_state_update = False
# When set, SceneConnect opens directly on this view (e.g. "shop_modules")
# instead of the main menu.  Consumed once, then cleared.
scene_connect_initial_view = None
# Set by ShopModulesView right after a successful module purchase.  When
# SceneConnect exits and the player has no pets, the connect→egg routing
# uses this to auto-download the module and pre-select it in the egg picker.
last_purchased_module = None
# If set, SceneEggSelection jumps directly into that module's egg picker,
# bypassing the category selection step.  Cleared after consumption.
preselected_module = None

# --- Main Menu Navigation ---
main_menu_index = -1

# --- Menu Selections ---
food_index = 0
strategy_index = 0
training_index = 0
battle_index = {}

# --- Runtime-only Assets and Selections ---
feeding_frames = []
selected_pets = []
misc_sprites = {}
battle_enemies = {}
pet_sprites = {}
evolution_data = []
evolution_pet = None
last_headtohead_pattern = random.randint(0, 5)
special_encounter = []

# --- Global Managers ---
game_sound = GameSound()
game_console = GameConsole()
game_message = GameMessage()
game_input = InputManager()
game_modules = {}
game_module_flag = {}
game_pet_eating = {}

default_items = {
    "protein": GameItem(
        id="default-protein",
        name="Protein",
        description="Basic food. Replenishes hunger.",
        sprite_name="Protein.png",
        module="core",
        effect="status_change",
        status="hunger",
        amount=1,
        boost_time=0,
        component_item=""
    ),
    "vitamin": GameItem(
        id="default-vitamin",
        name="Vitamin",
        description="Basic food. Replenishes strength.",
        sprite_name="Vitamin.png",
        module="core",
        effect="status_change",
        status="strength",
        amount=1,
        boost_time=0,
        component_item=""
    )
}

# --- Pet/Gameplay Flags ---
pet_alert = False
show_hearts = False
check_shaking = False

# --- Ruleset Flags ---
dmc_enabled = False
penc_enabled = False
dmx_enabled = False
vb_enabled = False

# --- Hardware/Input ---
i2c = I2CUtils()
shake_detector = ShakeDetector(i2c)
last_input_frame = 0

#=====================================================================
# Resolution Update Helper
#=====================================================================
def update_resolution_constants(width: int = None, height: int = None) -> None:
    """
    Update resolution-dependent runtime values.
    Call this after display setup to scale UI elements.
    
    If width/height not provided, uses values from game_globals.configuration.
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT, UI_SCALE
    global MENU_ICON_SIZE, OPTION_ICON_SIZE, OPTION_FRAME_WIDTH, OPTION_FRAME_HEIGHT, PET_ICON_SIZE
    global FONT_SIZE_SMALL, FONT_SIZE_MEDIUM, FONT_SIZE_MEDIUM_LARGE, FONT_SIZE_LARGE
    global PET_WIDTH, PET_HEIGHT

    # Get resolution from configuration if not provided
    if width is None or height is None:
        try:
            from core import game_globals
            config = game_globals.configuration
            width = config.screen_width
            height = config.screen_height
        except (ImportError, AttributeError):
            width = width or 240
            height = height or 240

    SCREEN_WIDTH = width
    SCREEN_HEIGHT = height
    UI_SCALE = height / 240.0

    MENU_ICON_SIZE = int(24 * UI_SCALE)
    OPTION_ICON_SIZE = int(48 * UI_SCALE)
    OPTION_FRAME_WIDTH = int(96 * UI_SCALE)
    OPTION_FRAME_HEIGHT = int(116 * UI_SCALE)
    PET_ICON_SIZE = int(48 * UI_SCALE)

    FONT_SIZE_SMALL = int(24 * UI_SCALE)
    FONT_SIZE_MEDIUM = int(28 * UI_SCALE)
    FONT_SIZE_MEDIUM_LARGE = int(30 * UI_SCALE)
    FONT_SIZE_LARGE = int(40 * UI_SCALE)

    # Prevent oversized sprites when MAX_PETS == 1
    try:
        from core import game_globals
        max_pets = game_globals.configuration.max_pets
        PET_WIDTH = PET_HEIGHT = height // max(max_pets, 4)
    except Exception:
        PET_WIDTH = PET_HEIGHT = height // 2

    # Also update combat constants if available
    try:
        import battle.combat_constants as battle_constants
        if hasattr(battle_constants, "update_combat_constants"):
            battle_constants.update_combat_constants()
    except Exception:
        pass
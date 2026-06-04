import os
from core.constants import MODULES_FOLDER
from models.game_module import GameModule
from core import runtime_globals, game_globals
from utils.asset_utils import resolve_path


def get_modules_dir() -> str:
    """Return the writable modules directory.

    On Android the APK-bundled modules folder is read-only, so downloaded
    modules live under android.storage.app_storage_path()/modules.
    Everywhere else, the workspace-relative 'modules/' folder is used.
    The directory is created if missing.
    """
    if runtime_globals.IS_ANDROID:
        try:
            from android.storage import app_storage_path  # type: ignore
            path = os.path.join(app_storage_path(), MODULES_FOLDER)
        except Exception:
            path = resolve_path(MODULES_FOLDER)
    else:
        path = resolve_path(MODULES_FOLDER)
    os.makedirs(path, exist_ok=True)
    return path


def load_modules():
    """
    Loads all modules from the modules directory and registers them in runtime_globals.game_modules.
    Also sets ruleset flags and initializes adventure mode progress if needed.

    Uses get_modules_dir() so Android downloads (which live outside the
    APK in app_storage_path()/modules) are picked up alongside any
    bundled modules.
    """
    module_dir = get_modules_dir()
    runtime_globals.game_modules = {}
    if not os.path.isdir(module_dir):
        runtime_globals.game_console.log(
            f"[load_modules] modules dir missing: {module_dir}")
        return runtime_globals.game_modules
    for folder in os.listdir(module_dir):
        folder_path = os.path.join(module_dir, folder)
        module_json_path = os.path.join(folder_path, "module.json")
        if os.path.isdir(folder_path) and os.path.exists(module_json_path):
            module = GameModule(folder_path)
            if module.adventure_mode and game_globals.battle_area.get(module.name) is None:
                game_globals.battle_area[module.name] = 1
                game_globals.battle_round[module.name] = 1
            runtime_globals.game_modules[module.name] = module
    runtime_globals.game_console.log(f"[SceneEggSelection] Loaded Modules: {len(runtime_globals.game_modules)}")
    return runtime_globals.game_modules

def get_module(name):
    """
    Returns the loaded GameModule instance by name.
    """
    return runtime_globals.game_modules[name]
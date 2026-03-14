import os
from core.constants import MODULES_FOLDER
from core.game_module import GameModule
from core import runtime_globals, game_globals

def load_modules():
    """
    Loads all modules from the MODULES_FOLDER and registers them in runtime_globals.game_modules.
    Also sets ruleset flags and initializes adventure mode progress if needed.
    """
    module_dir = MODULES_FOLDER
    runtime_globals.game_modules = {}
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
from core import runtime_globals

def change_scene(scene):
    """
    Changes the current game scene/state.
    """
    runtime_globals.game_state_update = True
    runtime_globals.game_state = scene
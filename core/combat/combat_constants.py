from core import game_globals, runtime_globals


def _get_frame_rate():
    """Get frame rate from configuration, with fallback for early initialization."""
    try:
        return game_globals.configuration.frame_rate
    except (AttributeError, RuntimeError):
        return 30  # Default fallback

def _get_screen_width():
    """Get screen width, with fallback for early initialization."""
    try:
        return game_globals.configuration.screen_width
    except (AttributeError, RuntimeError):
        return runtime_globals.SCREEN_WIDTH if runtime_globals.SCREEN_WIDTH > 0 else 240


# Timing constants - evaluated lazily via update_combat_constants()
ALERT_DURATION_FRAMES = 50
WAIT_AFTER_BAR_FRAMES = 30
IMPACT_DURATION_FRAMES = 60
WAIT_ATTACK_READY_FRAMES = 20
RESULT_SCREEN_FRAMES = 90
BAR_HOLD_TIME_MS = 2500
PUNCH_HOLD_TIME_MS = 18000
ATTACK_SPEED = 4

ENEMY_ENTRY_SPEED = 1
IDLE_ANIM_DURATION = 90
ALERT_FRAME_DELAY = 10
AFTER_ATTACK_DELAY_FRAMES = 50
LEVEL_DURATION_FRAMES = 60

READY_FRAME_COUNTER = 60
ALERT_FRAME_COUNTER = 90

def update_combat_constants():
    """Update combat constants based on current frame rate and screen width."""
    global ALERT_DURATION_FRAMES, WAIT_AFTER_BAR_FRAMES, IMPACT_DURATION_FRAMES, WAIT_ATTACK_READY_FRAMES
    global RESULT_SCREEN_FRAMES, ATTACK_SPEED, ENEMY_ENTRY_SPEED, IDLE_ANIM_DURATION
    global ALERT_FRAME_DELAY, AFTER_ATTACK_DELAY_FRAMES, LEVEL_DURATION_FRAMES
    global READY_FRAME_COUNTER, ALERT_FRAME_COUNTER

    frame_rate = _get_frame_rate()
    screen_width = _get_screen_width()
    
    ALERT_DURATION_FRAMES = int(60 * (frame_rate / 30))
    WAIT_AFTER_BAR_FRAMES = int(30 * (frame_rate / 30))
    IMPACT_DURATION_FRAMES = int(60 * (frame_rate / 30))
    WAIT_ATTACK_READY_FRAMES = int(20 * (frame_rate / 30))
    RESULT_SCREEN_FRAMES = int(90 * (frame_rate / 30))
    ATTACK_SPEED = 4 * (screen_width / 240)
    ENEMY_ENTRY_SPEED = 1 * (screen_width / 240)
    IDLE_ANIM_DURATION = int(90 * (frame_rate / 30))
    ALERT_FRAME_DELAY = int(10 * (frame_rate / 30))
    AFTER_ATTACK_DELAY_FRAMES = int(50 * (frame_rate / 30))
    LEVEL_DURATION_FRAMES = int(60 * (frame_rate / 30))
    READY_FRAME_COUNTER = int(60 * (frame_rate / 30))
    ALERT_FRAME_COUNTER = int(90 * (frame_rate / 30))


# Usage elsewhere:
# speed = get_attack_speed()
# entry_speed = get_enemy_entry_speed()
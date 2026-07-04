from core import game_globals, runtime_globals
from core import constants

def get_selected_pets():
    """
    Returns the list of currently selected pets, or all alive pets if none are selected.
    """
    if runtime_globals.selected_pets:
        pet_list = [pet for pet in runtime_globals.selected_pets if pet.state != "dead" and pet.stomach > 0 and pet.stage > 0]
    else:
        pet_list = [pet for pet in game_globals.pet_list if pet.state != "dead" and pet.stomach > 0 and pet.stage > 0]
    return pet_list

def get_training_targets():
    """
    Returns pets eligible for training based on the current strategy.
    """
    if runtime_globals.strategy_index == 0:
        return [pet for pet in get_selected_pets() if pet.can_train()]
    else:
        return [pet for pet in get_selected_pets() if pet.can_train() and (pet.effort < 16 or (
            pet.strength < 4 and
            runtime_globals.game_modules.get(pet.module).training_strengh_gain_win > 0))]

def get_battle_targets():
    """
    Returns pets eligible for battle.
    """
    return [pet for pet in get_selected_pets() if pet.can_battle()]

def get_battle_pvp_targets():
    """
    Returns pets eligible for battle.
    """
    return [pet for pet in get_selected_pets() if pet.can_battle_pvp()]

def pets_need_care():
    """
    Returns True if any pet needs care (callsign is active).
    """
    for pet in game_globals.pet_list:
        if pet.call_sign():
            return True
    return False

def all_pets_hatched():
    """
    Returns True if all pets are hatched (stage > 0).
    """
    return all(pet.stage > 0 for pet in game_globals.pet_list)

def distribute_pets_evenly():
    """
    Evenly distributes pets horizontally around the screen center.

    The layout was designed for a square canvas; spreading over the full
    width of a wide (e.g. phone landscape) render pushes pets out to the
    corners.  Distribute over a centered square-equivalent span instead:
    the full width on square screens (unchanged behavior), the central
    SCREEN_HEIGHT-wide region on wide ones — widened as needed so many
    pets still get at least 1.5x their sprite width per section.
    """
    pet_list = [pet for pet in game_globals.pet_list if pet.state != "dead"]
    count = len(pet_list)
    if count == 0:
        return
    if count == 1:
        pet_list[0].x = (runtime_globals.SCREEN_WIDTH - runtime_globals.PET_WIDTH) // 2
        pet_list[0].subpixel_x = float(pet_list[0].x)
        return
    span = min(runtime_globals.SCREEN_WIDTH,
               max(runtime_globals.SCREEN_HEIGHT,
                   count * runtime_globals.PET_WIDTH * 1.5))
    left = (runtime_globals.SCREEN_WIDTH - span) / 2
    section_width = span / count
    center_positions = [(left + section_width * i + section_width / 2) for i in range(count)]
    for i, pet in enumerate(pet_list):
        pet.x = int(center_positions[i] - runtime_globals.PET_WIDTH / 2)
        pet.subpixel_x = float(pet.x)

def reposition_for_resolution(old_w=None, old_h=None):
    """Refresh pet and poop on-screen positions after a render/window
    resolution change.

    Pet coordinates — the vertical resting position especially — are derived
    from ``SCREEN_HEIGHT`` / ``UI_SCALE`` when the pet spawns (see
    ``GamePet.begin_position``), and poops store absolute pixel positions.
    Both go stale when the resolution changes, so we recompute the pets from
    the new scale (then re-spread them) and re-seat the poops on the pets'
    ground plane, scaling their horizontal position from the old width.

    Args:
        old_w, old_h: the SCREEN_WIDTH/HEIGHT *before* the change, used to
            scale poops' horizontal position.  Omit to leave X as-is.
    """
    for pet in (getattr(game_globals, 'pet_list', None) or []):
        if hasattr(pet, 'begin_position'):
            pet.begin_position()
        if hasattr(pet, 'dirty'):
            pet.dirty = True
    # begin_position centres every pet; spread them back out evenly.
    distribute_pets_evenly()

    align_poops_to_ground(old_w)


def _ground_baseline_y():
    """Y of the line the pets stand on (bottom of the pet sprites), matching
    GamePet.begin_position — pet.y + PET_HEIGHT."""
    scale = runtime_globals.UI_SCALE
    if constants.MAX_PETS > 2:
        return int(174 * scale)
    return int(190 * scale - 5)


def _poop_sprite_size(poop):
    """(width, height) of a poop's current sprite, scaled to the active res."""
    key = "JumboPoop1" if getattr(poop, 'jumbo', False) else "Poop1"
    sprites = getattr(runtime_globals, 'misc_sprites', None) or {}
    sprite = sprites.get(key)
    if sprite:
        return sprite.get_width(), sprite.get_height()
    est = int(24 * runtime_globals.UI_SCALE)
    return est, est


def align_poops_to_ground(old_w=None):
    """Seat every poop on the pets' ground plane for the current resolution.

    A poop's bottom edge is placed on the same line as the pets' feet so they
    share a plane (``pet.y + pet_height == poop.y + poop_height``).  The
    horizontal position is scaled from ``old_w`` (when given) and clamped to
    the visible area; the vertical position is recomputed, not scaled, so it
    is always correct regardless of the resolution the poop was created at.
    """
    poops = getattr(game_globals, 'poop_list', None) or []
    if not poops:
        return
    sw = runtime_globals.SCREEN_WIDTH
    ground = _ground_baseline_y()
    ratio = (sw / old_w) if (old_w and old_w != sw) else 1.0
    for poop in poops:
        pw, ph = _poop_sprite_size(poop)
        # Bottom of the poop aligns with the bottom of the pets.
        poop.y = int(ground - ph)
        if ratio != 1.0:
            poop.x = int(poop.x * ratio)
        poop.x = max(0, min(int(poop.x), max(0, sw - pw)))
        if hasattr(poop, 'dirty'):
            poop.dirty = True


def fix_positions_for_current_resolution():
    """Re-place pets and poops so they're consistent with the current render
    resolution after loading a save.

    Pets are recomputed from scratch (their resting Y depends on the current
    scale); poops store absolute pixels, so they're scaled from the resolution
    the save was written at (``runtime_globals.save_render_resolution``) to the
    current one.  Works on every platform — call it once the display is
    finalized (e.g. from the boot scene before entering the game).
    """
    old = getattr(runtime_globals, 'save_render_resolution', None)
    if not old:
        old = (runtime_globals.SCREEN_WIDTH, runtime_globals.SCREEN_HEIGHT)
    reposition_for_resolution(old[0], old[1])


def draw_pet_outline(surface, frame, x, y, color=(255, 255, 0)):
    """
    Draws an outline around a pet sprite frame.
    """
    import pygame
    mask = pygame.mask.from_surface(frame)
    outline = mask.outline()
    if outline:
        outline = [(x + px, y + py) for px, py in outline]
        pygame.draw.lines(surface, color, True, outline, 2)
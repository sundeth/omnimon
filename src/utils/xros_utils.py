"""
Xros / Temporary evolution utilities
====================================

Temporary evolutions ("temporary-evolution" in monster.json) are battle-only
transformations (Mode Change / Xros).  The pet transforms when its
requirements are met, keeps the form for the whole battle (including all
sequential rounds) and reverts when the battle ends.

Requirements checked at selection time:
    strength  — [min, max] range on the pet's strength stat (999999 = no cap)
    unlock    — a module unlock name the player must have obtained
    friend    — pet names that must be registered in the player's digidex
    megahit   — battle-time condition; does NOT gate the pre-battle selection

While transformed the pet uses the target form's sprites and power, plus its
attack / hp when the target defines non-default (non-zero) values.
"""

import os
import pygame

from core import runtime_globals
from utils.asset_utils import image_load, resolve_path
from utils.module_utils import get_module
from utils.utils_unlocks import is_unlocked


# Fields swapped while the temporary evolution is active.
_BACKUP_FIELDS = ("name", "power", "attack", "hp", "atk_main", "atk_alt", "atk_alt_2")


# =====================================================================
# Requirement checks
# =====================================================================

def _strength_ok(evo, pet) -> bool:
    rng = evo.get("strength")
    if not rng:
        return True
    lo = rng[0] if len(rng) > 0 else -1
    hi = rng[1] if len(rng) > 1 else 999999
    value = getattr(pet, "strength", 0) or 0
    if lo not in (-1, None) and value < lo:
        return False
    if hi not in (-1, None) and hi != 999999 and value > hi:
        return False
    return True


def _unlock_ok(evo, pet) -> bool:
    name = evo.get("unlock")
    if not name:
        return True
    try:
        return is_unlocked(pet.module, None, name)
    except Exception:
        return False


def get_module_friends(module_name):
    """The player's Friend list for a module (pets met by battling
    Friend-flagged enemies).  Stored in the save file."""
    from core import game_globals
    friends = getattr(game_globals, "friends", None) or {}
    return friends.get(module_name, [])


def register_friends_from_battle(module_name, enemies) -> bool:
    """Add every Friend-flagged enemy of a battle/special encounter to the
    module's Friend list.  Returns True when something new was added."""
    from core import game_globals
    if not hasattr(game_globals, "friends") or game_globals.friends is None:
        game_globals.friends = {}
    added = False
    for enemy in enemies or []:
        if enemy is None or not getattr(enemy, "friend", False):
            continue
        name = getattr(enemy, "name", None)
        if not name:
            continue
        module_list = game_globals.friends.setdefault(module_name, [])
        if name not in module_list:
            module_list.append(name)
            added = True
            runtime_globals.game_console.log(f"[Friend] {name} registered ({module_name})")
            try:
                runtime_globals.game_message.add_slide(
                    f"{name} became a friend!", (255, 255, 0),
                    56 * runtime_globals.UI_SCALE, runtime_globals.FONT_SIZE_SMALL)
            except Exception:
                pass
    return added


def _friends_ok(evo, pet) -> bool:
    friends = evo.get("friend") or []
    if not friends:
        return True
    module_friends = get_module_friends(pet.module)
    return all(fname in module_friends for fname in friends)


def get_available_temp_evolutions(pet):
    """Return the pet's temporary evolutions whose requirements are met now."""
    result = []
    for evo in (getattr(pet, "temp_evolve", None) or []):
        if not evo.get("to"):
            continue
        if _strength_ok(evo, pet) and _unlock_ok(evo, pet) and _friends_ok(evo, pet):
            result.append(evo)
    return result


# =====================================================================
# Apply / revert
# =====================================================================

def apply_temp_evolution(pet, evo) -> bool:
    """Transform *pet* into the temp evolution's target for this battle.

    Uses the target form's sprites and power; attack and hp only when the
    target defines non-zero (non-default) values.  Original values are kept
    on ``pet.xros_backup`` for revert_temp_evolution().
    """
    module = get_module(pet.module)
    data = module.get_monster(evo.get("to"), pet.version) if module else None
    if not data:
        runtime_globals.game_console.log(
            f"[Xros] Target '{evo.get('to')}' not found in {pet.module}")
        return False

    if getattr(pet, "xros_backup", None):
        revert_temp_evolution(pet)

    pet.xros_backup = {f: getattr(pet, f, 0) for f in _BACKUP_FIELDS}
    pet.xros_evolved = dict(evo)

    pet.name = data["name"]
    if data.get("power"):
        pet.power = data["power"]
    if data.get("attack"):
        pet.attack = data["attack"]
    if data.get("hp"):
        pet.hp = data["hp"]
    if data.get("atk_main"):
        pet.atk_main = data["atk_main"]
        pet.atk_alt = data.get("atk_alt") or data["atk_main"]
        pet.atk_alt_2 = data.get("atk_alt_2", 0)

    # Reload sprites for the new form (uses the pet's module formats; when the
    # module doesn't use a global HD set this resolves the target's own HD).
    pet.load_sprite()
    runtime_globals.game_console.log(
        f"[Xros] {pet.xros_backup['name']} -> {pet.name} ({evo.get('type')})")
    return True


def revert_temp_evolution(pet) -> None:
    """Restore the pet to its pre-battle form (no-op if not transformed)."""
    backup = getattr(pet, "xros_backup", None)
    if not backup:
        return
    for field, value in backup.items():
        setattr(pet, field, value)
    pet.xros_backup = None
    pet.xros_evolved = None
    pet.load_sprite()
    runtime_globals.game_console.log(f"[Xros] Reverted to {pet.name}")


def revert_all_temp_evolutions(pets) -> list:
    """Revert every transformed pet in *pets*; returns the ones reverted."""
    reverted = []
    for pet in pets or []:
        if getattr(pet, "xros_backup", None):
            revert_temp_evolution(pet)
            reverted.append(pet)
    return reverted


# =====================================================================
# Asset loading for the xros animation
# =====================================================================

def _scale_to_fit(surface, max_w, max_h):
    w, h = surface.get_size()
    if w <= 0 or h <= 0:
        return surface
    scale = min(max_w / w, max_h / h)
    if scale == 1:
        return surface
    return pygame.transform.scale(surface, (max(1, int(w * scale)), max(1, int(h * scale))))


def load_xros_background(module, bg_name, cell_size):
    """Background image from the module's backgrounds folder, scaled to the cell."""
    if not module or not bg_name:
        return None
    for ext in (".png", ".jpg", ".jpeg", ".bmp"):
        path = os.path.join(module.folder_path, "backgrounds", bg_name + ext)
        try:
            if os.path.exists(resolve_path(path)):
                img = image_load(path).convert()
                return pygame.transform.scale(img, cell_size)
        except Exception as exc:
            runtime_globals.game_console.log(f"[Xros] bg load failed {path}: {exc}")
    return None


def load_xros_animation_frames(module, anim_name, sprite_size):
    """The 5 animation frames ("name_1".."name_5"), scaled to sprite_size."""
    frames = []
    if not module or not anim_name:
        return frames
    for i in range(1, 6):
        path = os.path.join(module.folder_path, "animations", f"{anim_name}_{i}.png")
        try:
            if os.path.exists(resolve_path(path)):
                img = image_load(path).convert_alpha()
                frames.append(_scale_to_fit(img, sprite_size, sprite_size))
        except Exception as exc:
            runtime_globals.game_console.log(f"[Xros] anim load failed {path}: {exc}")
    return frames


def load_form_sprite(module, pet_name, frame_id, sprite_size):
    """One frame of a monster's sprite set, scaled to sprite_size (or None)."""
    if not module or not pet_name:
        return None
    try:
        from utils.sprite_utils import load_pet_sprites
        sprites = load_pet_sprites(
            pet_name,
            module.folder_path,
            getattr(module, 'name_format', '$_dmc'),
            size=(sprite_size, sprite_size),
            primary_sprite_format=getattr(module, 'primary_sprite_format', 'Color'),
            secondary_sprite_format=getattr(module, 'secondary_sprite_format', 'HD'),
        )
        if sprites:
            return sprites.get(frame_id) or next(iter(sprites.values()), None)
    except Exception as exc:
        runtime_globals.game_console.log(f"[Xros] sprite load failed {pet_name}: {exc}")
    return None

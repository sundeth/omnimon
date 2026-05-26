import hashlib
import os
import pygame
import time
import core.constants as constants
from core import game_globals, runtime_globals
from models import game_console
from utils.asset_utils import image_load, resolve_path
from utils.module_utils import get_module

shadow_cache = {}  # {id(surface): shadow_surface} — validated by size on retrieval

def get_surface_hash(surface):
    """Generate a hash using the surface's memory address (instant, unique per object).
    
    Note: This uses object identity rather than content comparison. Since game sprites
    are loaded once and reused, this is much faster than MD5 hashing pixel data.
    """
    return id(surface)

def get_shadow(sprite, shadow_color=(0, 0, 0, 100)):
    """Return a darkened copy of sprite, cached by object identity.

    Guard against Python id() reuse: if the cached shadow's size doesn't match
    the current sprite's size, the old entry belongs to a different (now-freed)
    surface that happened to land at the same address — regenerate it.
    Transient surfaces (font renders, transform results) that share the same size
    as a recycled id are still a theoretical edge case, but size mismatch catches
    the vast majority of real-world stale-cache hits.
    """
    key = id(sprite)
    cached = shadow_cache.get(key)
    if cached is not None and cached.get_size() == sprite.get_size():
        return cached
    shadow = sprite.copy()
    shadow.fill(shadow_color, special_flags=pygame.BLEND_RGBA_MULT)
    shadow_cache[key] = shadow
    return shadow

def blit_with_shadow(surface, sprite, pos, offset=(2, 2), shadow_color=(0, 0, 0, 100)):
    """Blit a sprite with a drop-shadow using two direct blits.

    Two direct blits to the target surface are cheaper than building a
    composite surface on every call (which also caused the wrong-shadow bug
    because the composite cache was disabled while the shadow cache was not).
    """
    if game_globals.configuration.debug_mode and game_globals.configuration.debug_blit_logging:
        global _blit_shadow_calls, _last_log_time

        _blit_shadow_calls += 1

        current_time = time.time()
        if current_time - _last_log_time >= 1:
            runtime_globals.game_console.log(f"blit_with_shadow calls per second: {_blit_shadow_calls}")
            _blit_shadow_calls = 0
            _last_log_time = current_time

    shadow = get_shadow(sprite, shadow_color)
    surface.blit(shadow, (pos[0] + offset[0], pos[1] + offset[1]))
    surface.blit(sprite, pos)

def get_font(size=24):
    from utils.asset_utils import font_load
    return font_load(constants.FONT_TTF_PATH, size)

def get_font_alt(size=24):
    from utils.asset_utils import font_load
    return font_load(constants.FONT_ALT_TTF_PATH, size)

def sprite_load(path, size=None, scale=1):
    img = image_load(path).convert_alpha()
    if size:
        return pygame.transform.scale(img, size)
    elif scale != 1:
        base_size = img.get_size()
        new_size = (int(base_size[0] * scale), int(base_size[1] * scale))
        return pygame.transform.scale(img, new_size)
    return img

def sprite_load_percent(path, percent=100, keep_proportion=True, base_on="height", alpha=True):
    img = image_load(path)
    if alpha:
        img = img.convert_alpha()
    else:
        img = img.convert()
    orig_w, orig_h = img.get_size()
    ref_size = runtime_globals.SCREEN_WIDTH if base_on == "width" else runtime_globals.SCREEN_HEIGHT
    target = int(ref_size * (percent / 100.0))
    if keep_proportion:
        scale_factor = target / orig_h if base_on == "height" else target / orig_w
        new_w = int(orig_w * scale_factor)
        new_h = int(orig_h * scale_factor)
    else:
        if base_on == "height":
            new_w = orig_w
            new_h = target
        else:
            new_w = target
            new_h = orig_h
    return pygame.transform.scale(img, (new_w, new_h))

def sprite_load_percent_wh(path, percent_w=100, percent_h=100, keep_proportion=True):
    img = image_load(path).convert_alpha()
    orig_w, orig_h = img.get_size()
    target_w = int(runtime_globals.SCREEN_WIDTH * (percent_w / 100.0))
    target_h = int(runtime_globals.SCREEN_HEIGHT * (percent_h / 100.0))
    if keep_proportion:
        scale_factor = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale_factor)
        new_h = int(orig_h * scale_factor)
    else:
        new_w = target_w
        new_h = target_h
    return pygame.transform.scale(img, (new_w, new_h))

def load_attack_sprites():
    attack_sprites = {}
    # Scale to half pet height, maintaining aspect ratio
    target_height = 24 * runtime_globals.UI_SCALE
    # Resolve ATK_FOLDER through APP_ROOT so the listdir works on Android.
    atk_folder = resolve_path(constants.ATK_FOLDER)
    if not os.path.isdir(atk_folder):
        runtime_globals.game_console.log(
            f"[load_attack_sprites] folder missing: {atk_folder}")
        return attack_sprites
    for filename in os.listdir(atk_folder):
        if filename.endswith(".png"):
            # image_load() takes the relative path and re-resolves it
            # against APP_ROOT, so use the unresolved path here.
            path = os.path.join(constants.ATK_FOLDER, filename)
            sprite = image_load(path).convert_alpha()
            # Calculate proportional width based on target height
            original_width = sprite.get_width()
            original_height = sprite.get_height()
            if original_height > 0:
                target_width = int(original_width * (target_height / original_height))
                sprite = pygame.transform.scale(sprite, (target_width, target_height))
            atk_id = filename.split(".")[0]
            attack_sprites[atk_id] = sprite
    return attack_sprites


def load_crit_attack_sprites():
    """Load all sprites from the global assets/atk_crit folder.

    Returns a dict keyed by filename stem (e.g. '30', '30_dot').
    Callers should use _dot-aware lookup just like get_attack_sprite does:
      - Dot-format module: try f'{id}_dot' first, then f'{id}'
      - Other formats:     look up str(id) directly
    """
    crit_sprites = {}
    # Resolve through APP_ROOT for Android; on desktop this is a no-op.
    folder = resolve_path(constants.ATK_CRIT_FOLDER)
    if not os.path.isdir(folder):
        return crit_sprites
    target_height = 48 * runtime_globals.UI_SCALE  # 2× normal attack sprite size
    for filename in os.listdir(folder):
        if filename.endswith(".png"):
            # image_load re-resolves against APP_ROOT, so feed it the
            # relative form to stay portable.
            path = os.path.join(constants.ATK_CRIT_FOLDER, filename)
            try:
                sprite = image_load(path).convert_alpha()
                orig_w, orig_h = sprite.get_width(), sprite.get_height()
                if orig_h > 0:
                    target_width = int(orig_w * (target_height / orig_h))
                    sprite = pygame.transform.scale(sprite, (target_width, target_height))
                atk_id = filename.split(".")[0]
                crit_sprites[atk_id] = sprite
            except Exception as e:
                runtime_globals.game_console.log(f"[!] Error loading crit sprite {filename}: {e}")
    return crit_sprites

def _load_module_sprites_from_folder(module, folder_name):
    """
    Shared loader: returns a dict of attack sprites from `<module_folder>/<folder_name>/`.
    Loads ALL png files (both normal and _dot variants) under their exact filename stem.
    Dot vs. non-dot selection happens at lookup time based on the pet's current sprite type.
    Returns an empty dict if the module or folder doesn't exist.
    """
    mod = get_module(module)
    if not mod:
        game_console.log(f"[!] Module {module} not found for attack sprites ({folder_name}).")
        return {}

    folder = os.path.join(mod.folder_path, folder_name)
    if not os.path.exists(folder):
        return {}

    # atk_crit sprites are displayed at 2× the normal attack size
    target_height = runtime_globals.PET_HEIGHT if folder_name == "atk_crit" else runtime_globals.PET_HEIGHT // 2

    def _load_and_scale(path):
        sprite = image_load(path).convert_alpha()
        orig_w, orig_h = sprite.get_width(), sprite.get_height()
        if orig_h > 0:
            sprite = pygame.transform.scale(sprite, (int(orig_w * (target_height / orig_h)), target_height))
        return sprite

    result = {}
    try:
        for filename in os.listdir(folder):
            if not filename.endswith(".png"):
                continue
            stem = filename[:-4]
            path = os.path.join(folder, filename)
            try:
                result[stem] = _load_and_scale(path)
            except Exception as e:
                game_console.log(f"[!] Error loading sprite {filename} from {folder}: {e}")

    except OSError as e:
        game_console.log(f"[!] Error loading sprites from {folder}: {e}")
        return {}

    return result


def module_attack_sprites(module):
    """Returns attack sprites for the module from its 'atk' folder."""
    return _load_module_sprites_from_folder(module, "atk")


def module_crit_attack_sprites(module):
    """Returns critical-attack sprites for the module from its 'atk_crit' folder.
    Returns an empty dict if the module has no atk_crit folder.
    """
    return _load_module_sprites_from_folder(module, "atk_crit")


def load_misc_sprites():
    global misc_sprites
    sprite_files = [
        "Cheer.png", "Cheer_dot.png",
        "Mad1.png", "Mad2.png",
        "Sick1.png", "Sick2.png",
        "Sick1_dot.png", "Sick2_dot.png",
        "Sleep1.png", "Sleep2.png",
        "Poop1.png", "Poop2.png",
        "Poop1_dot.png", "Poop2_dot.png",
        "JumboPoop1.png", "JumboPoop2.png",
        "JumboPoop1_dot.png", "JumboPoop2_dot.png",
        "Wash.png", "CallSignInverted.png", "SickInverted.png", "PoopInverted.png",
        "Dots1.png", "Dots2.png",
    ]
    misc_sprites = {}
    for filename in sprite_files:
        path = os.path.join("assets", filename)
        try:
            sprite = sprite_load(path)
            misc_sprites[filename.split('.')[0]] = pygame.transform.scale(
                sprite, (sprite.get_width() * runtime_globals.UI_SCALE, sprite.get_height() * runtime_globals.UI_SCALE)
            )
            
        except Exception as e:
            runtime_globals.game_console.log(f"[!] Error loading {filename} from '{path}': {e}")
    return misc_sprites

# Counter and timer for logging
_blit_shadow_calls = 0
_last_log_time = time.time()

# Counter and timer for logging
_blit_cache_calls = 0
_last_cache_log_time = time.time()

blit_cache = {}

def blit_with_cache(surface, sprite, pos):
    """
    Blits a sprite and logs the number of calls per second.
    
    Note: The "cache" in the name is legacy - we now just blit directly since
    Pygame's internal blit is already highly optimized. Caching sprites by copying
    them doesn't provide any benefit and just wastes memory.
    """
    if game_globals.configuration.debug_mode and game_globals.configuration.debug_blit_logging:
        global _blit_cache_calls, _last_cache_log_time

        # Increment the counter
        _blit_cache_calls += 1

        # Log the count every second
        current_time = time.time()
        if current_time - _last_cache_log_time >= 1:
            runtime_globals.game_console.log(f"blit_with_cache calls per second: {_blit_cache_calls}")
            _blit_cache_calls = 0
            _last_cache_log_time = current_time

    # Perform the blit - Pygame's internal blit is already optimized
    surface.blit(sprite, pos)
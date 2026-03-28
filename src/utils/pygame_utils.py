import hashlib
import os
import pygame
import time
import core.constants as constants
from core import game_globals, runtime_globals
from models import game_console
from utils.asset_utils import image_load
from utils.module_utils import get_module

shadow_cache = {}
composite_shadow_cache = {}  # Cache for pre-rendered sprite+shadow composites

def get_surface_hash(surface):
    """Generate a hash using the surface's memory address (instant, unique per object).
    
    Note: This uses object identity rather than content comparison. Since game sprites
    are loaded once and reused, this is much faster than MD5 hashing pixel data.
    """
    return id(surface)

def get_shadow(sprite, shadow_color=(0, 0, 0, 100)):
    key = id(sprite)  # Use object identity directly for instant lookup
    if key not in shadow_cache:
        shadow = sprite.copy()
        shadow.fill(shadow_color, special_flags=pygame.BLEND_RGBA_MULT)
        shadow_cache[key] = shadow
    return shadow_cache[key]

def get_composite_shadow(sprite, offset=(2, 2), shadow_color=(0, 0, 0, 100)):
    """Get or create a pre-rendered composite surface with shadow + sprite.
    
    This reduces 2 blits (shadow + sprite) to 1 blit (composite).
    
    DISABLED: Cache disabled temporarily - creating new surfaces (via transform.scale/flip)
    every frame was causing cache misses and flickering. Now just renders shadow directly.
    """
    # Cache disabled - just render shadow directly each frame
    # The overhead of 2 blits is less than the cache miss overhead
    
    # Create composite surface large enough for sprite + shadow offset
    width = sprite.get_width() + abs(offset[0])
    height = sprite.get_height() + abs(offset[1])
    composite = pygame.Surface((width, height), pygame.SRCALPHA)
    composite.fill((0, 0, 0, 0))  # Transparent background
    
    # Get or create shadow (shadow cache is fine since base sprites don't change)
    shadow = get_shadow(sprite, shadow_color)
    
    # Blit shadow and sprite onto composite
    composite.blit(shadow, (offset[0], offset[1]))
    composite.blit(sprite, (0, 0))
    
    return composite
    
    # OLD CACHED VERSION (disabled):
    # Cache key includes sprite ID and offset
    # key = (id(sprite), offset[0], offset[1])
    # 
    # if key not in composite_shadow_cache:
    #     # Create composite surface large enough for sprite + shadow offset
    #     width = sprite.get_width() + abs(offset[0])
    #     height = sprite.get_height() + abs(offset[1])
    #     composite = pygame.Surface((width, height), pygame.SRCALPHA)
    #     composite.fill((0, 0, 0, 0))  # Transparent background
    #     
    #     # Get or create shadow
    #     shadow = get_shadow(sprite, shadow_color)
    #     
    #     # Blit shadow and sprite onto composite
    #     composite.blit(shadow, (offset[0], offset[1]))
    #     composite.blit(sprite, (0, 0))
    #     
    #     composite_shadow_cache[key] = composite
    # 
    # return composite_shadow_cache[key]

def blit_with_shadow(surface, sprite, pos, offset=(2, 2)):
    """
    Blits a sprite with a shadow effect using a pre-rendered composite (1 blit instead of 2).
    """
    if game_globals.configuration.debug_mode and game_globals.configuration.debug_blit_logging:
        global _blit_shadow_calls, _last_log_time

        # Increment the counter
        _blit_shadow_calls += 1

        # Log the count every second
        current_time = time.time()
        if current_time - _last_log_time >= 1:
            runtime_globals.game_console.log(f"blit_with_shadow calls per second: {_blit_shadow_calls}")
            _blit_shadow_calls = 0
            _last_log_time = current_time

    # Use pre-rendered composite (reduces 2 blits to 1)
    composite = get_composite_shadow(sprite, offset)
    surface.blit(composite, pos)

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
    for filename in os.listdir(constants.ATK_FOLDER):
        if filename.endswith(".png"):
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

def module_attack_sprites(module):
    """
    Returns a dictionary of attack sprites for the given module.
    Returns empty dict if module not found or no atk folder exists.
    """
    mod = get_module(module)
    if not mod:
        game_console.log(f"[!] Module {module} not found for attack sprites.")
        return {}
    
    attack_sprites = {}
    atk_folder = os.path.join(mod.folder_path, "atk")
    
    # Check if atk folder exists
    if not os.path.exists(atk_folder):
        return {}
    
    # Scale to half pet height, maintaining aspect ratio
    target_height = runtime_globals.PET_HEIGHT // 2
    try:
        for filename in os.listdir(atk_folder):
            if filename.endswith(".png"):
                path = os.path.join(atk_folder, filename)
                sprite = image_load(path).convert_alpha()
                # Calculate proportional width based on target height
                original_width = sprite.get_width()
                original_height = sprite.get_height()
                if original_height > 0:
                    target_width = int(original_width * (target_height / original_height))
                    sprite = pygame.transform.scale(sprite, (target_width, target_height))
                atk_id = filename.split(".")[0]
                attack_sprites[atk_id] = sprite
    except (OSError, pygame.error) as e:
        game_console.log(f"[!] Error loading attack sprites for module {module}: {e}")
        return {}
    
    return attack_sprites

def load_misc_sprites():
    global misc_sprites
    sprite_files = [
        "Cheer.png", "Mad1.png", "Mad2.png",
        "Sick1.png", "Sick2.png", "Sleep1.png",
    "Sleep2.png", "Poop1.png", "Poop2.png",
    "JumboPoop1.png", "JumboPoop2.png", "Wash.png",
    "CallSignInverted.png", "SickInverted.png", "PoopInverted.png",
    "Dots1.png", "Dots2.png"
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
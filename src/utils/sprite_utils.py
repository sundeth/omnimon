"""
Sprite loading utilities for pets and enemies with advanced format priority support.

Sprite loading follows a priority order based on:
1. module.primary_sprite_format and module.secondary_sprite_format
2. game_globals.configuration.sprite_resolution_preference (0=Default, 1=Color, 2=HD)
3. game_globals.configuration.enable_old_sprites (to use secondary format as fallback)

Sprite formats:
- "Color": Global default colorized sprites in "monsters" folder (also includes color dot sprites)
- "Dot": Black and transparent sprites in "monsters_dot" folder
- "HD": High definition sprites in "monsters_hidef" folder
"""
import os
import zipfile
import pygame
import io
from typing import Dict, List, Optional, Tuple
from core import runtime_globals, game_globals
from utils.asset_utils import image_load, resolve_path


def get_sprite_name(pet_name: str, name_format: str = "$_dmc") -> str:
    """
    Generate standardized sprite folder/zip name using module name_format.
    Default format is $_dmc where $ is replaced with pet name and : with _.
    
    Args:
        pet_name: Name of the pet (e.g., "Agumon")
        name_format: Format string (e.g., "$_dmc") where $ = pet name, : = _
    
    Returns:
        Formatted sprite name (e.g., "Agumon_dmc")
    """
    # Replace $ with pet name and : with _
    sprite_name = name_format.replace("$", pet_name).replace(":", "_")
    return sprite_name


def snap_pet_sprite_size(target: int, allow_up: bool = False) -> int:
    """Snap a desired pet-sprite size to the pixel-perfect ladder.

    Pet art is authored at 48x48. Integer multiples (48, 96, 144, ...) keep
    every source pixel an exact k x k block for ANY sprite; below 1x only the
    66% (32) and 33% (16) reductions keep the 3x3 art blocks uniform. Any
    other size smears the pixel grid, so every place that scales a pet/enemy
    sprite must pick its size through this function.

    By default returns the largest allowed size <= target so sprites never
    overflow their layout slot (floors at 16). With allow_up=True returns the
    nearest allowed size, rounding ties up — for elements allowed to exceed
    their nominal box, like the boss sprite.
    """
    target = int(target)
    if target < 48:
        candidates = [16, 32, 48]
    else:
        floor_48 = (target // 48) * 48
        candidates = [floor_48, floor_48 + 48]
    below = [c for c in candidates if c <= target]
    down = max(below) if below else 16
    if not allow_up:
        return down
    above = [c for c in candidates if c >= target]
    if not above:
        return down
    up = min(above)
    return up if (up - target) <= (target - down) else down


def scale_sprite_proportionally(sprite: pygame.Surface, target_size: tuple) -> pygame.Surface:
    """
    Scale sprite proportionally to fit within target size while maintaining aspect ratio.
    
    Args:
        sprite: Original pygame Surface
        target_size: Target size tuple (width, height)
        
    Returns:
        Scaled pygame Surface
    """
    original_width, original_height = sprite.get_size()
    target_width, target_height = target_size
    
    # Calculate scale factor to fit within target size while maintaining aspect ratio
    scale_x = target_width / original_width
    scale_y = target_height / original_height
    scale_factor = min(scale_x, scale_y)
    
    # Calculate new size
    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)
    
    return pygame.transform.scale(sprite, (new_width, new_height))


def create_fallback_sprite(size: tuple) -> pygame.Surface:
    """
    Create a 48x48 white square sprite as fallback when no sprites are found.
    
    Args:
        size: Target size tuple (width, height) - used for reference only, always creates 48x48
        
    Returns:
        Pygame Surface with white square
    """
    fallback = pygame.Surface((48, 48), pygame.SRCALPHA)
    fallback.fill((255, 255, 255, 255))  # White square
    
    # Scale to target size if needed
    if size and size != (48, 48):
        fallback = scale_sprite_proportionally(fallback, size)
    
    return fallback


def load_sprites_from_directory(sprite_path: str, size: tuple = None, scale: float = 1.0) -> Dict[int, pygame.Surface]:
    """
    Load all PNG sprites from a directory.
    
    Args:
        sprite_path: Path to directory containing sprites
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        
    Returns:
        Dictionary mapping frame number (int) to pygame Surface, returns empty dict if dir not found
    """
    sprites = {}
    # Resolve path for Android compatibility
    resolved_path = resolve_path(sprite_path)
    
    if not os.path.exists(resolved_path) or not os.path.isdir(resolved_path):
        return sprites
    
    try:
        for filename in os.listdir(resolved_path):
            if filename.lower().endswith('.png'):
                # Extract frame number from filename (e.g., "0.png" -> 0)
                try:
                    frame_num = int(filename[:-4])
                except (ValueError, IndexError):
                    # Skip files that don't have numeric names
                    continue
                    
                file_path = os.path.join(sprite_path, filename)
                try:
                    sprite = image_load(file_path).convert_alpha()
                    
                    # Apply scaling
                    if size:
                        sprite = scale_sprite_proportionally(sprite, size)
                    elif scale != 1.0:
                        base_size = sprite.get_size()
                        new_size = (int(base_size[0] * scale), int(base_size[1] * scale))
                        sprite = pygame.transform.scale(sprite, new_size)
                    
                    sprites[frame_num] = sprite
                except pygame.error as e:
                    runtime_globals.game_console.log(f"[Sprite] Failed to load sprite {file_path}: {e}")
    except OSError as e:
        runtime_globals.game_console.log(f"[Sprite] Failed to read directory {resolved_path}: {e}")
    
    return sprites


def load_sprites_from_zip(zip_path: str, size: tuple = None, scale: float = 1.0) -> Dict[int, pygame.Surface]:
    """
    Load sprites from a zip file.
    
    Args:
        zip_path: Path to zip file
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        
    Returns:
        Dictionary mapping frame number (int) to pygame Surface, returns empty dict if zip not found
    """
    sprites = {}
    resolved_zip_path = resolve_path(zip_path)
    
    if not os.path.exists(resolved_zip_path):
        return sprites
    
    try:
        with zipfile.ZipFile(resolved_zip_path, 'r') as zip_file:
            png_files = [f for f in zip_file.namelist() if f.lower().endswith('.png')]
            
            for zip_entry in png_files:
                try:
                    # Extract frame number from filename
                    filename = os.path.basename(zip_entry)
                    try:
                        frame_num = int(filename[:-4])
                    except (ValueError, IndexError):
                        continue
                    
                    # Read the file data
                    with zip_file.open(zip_entry) as sprite_file:
                        sprite_data = sprite_file.read()
                    
                    # Create pygame surface from the data
                    sprite = pygame.image.load(io.BytesIO(sprite_data)).convert_alpha()
                    
                    # Apply scaling
                    if size:
                        sprite = scale_sprite_proportionally(sprite, size)
                    elif scale != 1.0:
                        base_size = sprite.get_size()
                        new_size = (int(base_size[0] * scale), int(base_size[1] * scale))
                        sprite = pygame.transform.scale(sprite, new_size)
                    
                    sprites[frame_num] = sprite
                    
                except Exception as e:
                    runtime_globals.game_console.log(f"[Sprite] Failed to load sprite {zip_entry} from {zip_path}: {e}")
                    
    except zipfile.BadZipFile as e:
        runtime_globals.game_console.log(f"[Sprite] Invalid zip file {zip_path}: {e}")
    except Exception as e:
        runtime_globals.game_console.log(f"[Sprite] Failed to read zip file {zip_path}: {e}")
    
    return sprites


def try_load_sprite_type(sprite_type: str, module_path: str, sprite_name: str, size: tuple, scale: float) -> Dict[int, pygame.Surface]:
    """
    Try to load sprites of a specific type from module folder first, then global assets.
    
    Args:
        sprite_type: Type of sprite ("Color", "Dot", or "HD")
        module_path: Path to module folder
        sprite_name: Name of the sprite (formatted name)
        size: Target size tuple for scaling
        scale: Scale factor if size not provided
        
    Returns:
        Dictionary mapping frame number to sprite, or empty dict if not found
    """
    # Map sprite type to folder name
    folder_map = {
        "Color": "monsters",
        "Dot": "monsters_dot",
        "HD": "monsters_hidef"
    }
    
    folder_name = folder_map.get(sprite_type, "monsters")
    
    # Try module folder first
    module_sprite_dir = os.path.join(module_path, folder_name, sprite_name)
    sprites = load_sprites_from_directory(module_sprite_dir, size, scale)
    if sprites:
        log_type = f"module {sprite_type}"
        runtime_globals.game_console.log(f"[Sprite] Loaded {len(sprites)} frames from {log_type}")
        return sprites
    
    # Try module zip file
    module_sprite_zip = os.path.join(module_path, folder_name, f"{sprite_name}.zip")
    sprites = load_sprites_from_zip(module_sprite_zip, size, scale)
    if sprites:
        log_type = f"module {sprite_type}"
        runtime_globals.game_console.log(f"[Sprite] Loaded {len(sprites)} frames from {log_type} (zip)")
        return sprites
    
    # Try global assets folder
    assets_sprite_dir = os.path.join("assets", folder_name, sprite_name)
    sprites = load_sprites_from_directory(assets_sprite_dir, size, scale)
    if sprites:
        log_type = f"assets {sprite_type}"
        runtime_globals.game_console.log(f"[Sprite] Loaded {len(sprites)} frames from {log_type}")
        return sprites
    
    # Try global assets zip file
    assets_sprite_zip = os.path.join("assets", folder_name, f"{sprite_name}.zip")
    sprites = load_sprites_from_zip(assets_sprite_zip, size, scale)
    if sprites:
        log_type = f"assets {sprite_type}"
        runtime_globals.game_console.log(f"[Sprite] Loaded {len(sprites)} frames from {log_type} (zip)")
        return sprites
    
    return {}


def load_pet_sprites(
    pet_name: str,
    module_path: str,
    name_format: str = "$_dmc",
    size: tuple = None,
    scale: float = 1.0,
    primary_sprite_format: str = "Color",
    secondary_sprite_format: str = "HD"
) -> Dict[int, pygame.Surface]:
    """
    Load pet sprites with advanced priority system based on configuration and module settings.
    
    Priority logic:
    - If config.sprite_resolution_preference == 0 (Default):
      - If enable_old_sprites False: Try primary format, then secondary
      - If enable_old_sprites True: Try primary, then secondary, then remaining format
    - If config.sprite_resolution_preference == 1 (Color):
      - If enable_old_sprites False: Try Color, then HD
      - If enable_old_sprites True: Try Dot, Color, HD (in order)
    - If config.sprite_resolution_preference == 2 (HD):
      - If enable_old_sprites False: Try HD, then Color
      - If enable_old_sprites True: Try HD, Color, Dot (in order, HD has priority)
    
    Args:
        pet_name: Name of the pet
        module_path: Path to the module folder
        name_format: Format string for sprite naming (default: "$_dmc")
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        primary_sprite_format: Module's primary format ("Dot", "Color", or "HD")
        secondary_sprite_format: Module's secondary format ("Dot", "Color", or "HD")
        
    Returns:
        Dictionary mapping frame number (int) to pygame Surface
    """
    sprites, _ = load_pet_sprites_resolved(
        pet_name, module_path, name_format, size, scale,
        primary_sprite_format, secondary_sprite_format
    )
    return sprites


def _compute_sprite_load_order(primary_sprite_format: str, secondary_sprite_format: str) -> List[str]:
    """Return the ordered list of sprite formats to try, per the current config.

    Mirrors the priority table documented on load_pet_sprites().
    """
    preference = getattr(game_globals.configuration, 'sprite_resolution_preference', 0)
    enable_old = getattr(game_globals.configuration, 'enable_old_sprites', False)

    all_types = ["Color", "Dot", "HD"]

    if preference == 1:  # Color preference
        return ["Dot", "Color", "HD"] if enable_old else ["Color", "HD"]
    if preference == 2:  # HD preference
        return ["HD", "Color", "Dot"] if enable_old else ["HD", "Color"]

    # preference == 0: Default - use module's declared preferences
    if enable_old:
        load_order = [primary_sprite_format, secondary_sprite_format]
        for sprite_type in all_types:
            if sprite_type not in load_order:
                load_order.append(sprite_type)
        return load_order
    # Old sprites disabled: primary then secondary, excluding Dot
    load_order = [f for f in [primary_sprite_format, secondary_sprite_format] if f != "Dot"]
    return load_order or ["Color", "HD"]


def load_pet_sprites_resolved(
    pet_name: str,
    module_path: str,
    name_format: str = "$_dmc",
    size: tuple = None,
    scale: float = 1.0,
    primary_sprite_format: str = "Color",
    secondary_sprite_format: str = "HD"
) -> Tuple[Dict[int, pygame.Surface], Optional[str]]:
    """Like load_pet_sprites() but also reports which format was actually used.

    Returns (sprites, format) where format is "Color" / "Dot" / "HD", or
    (empty dict, None) when nothing was found.  The resolved format lets
    callers pick matching overlays (e.g. HD pets get the *_hd overlay icons).
    """
    sprite_name = get_sprite_name(pet_name, name_format)

    preference = getattr(game_globals.configuration, 'sprite_resolution_preference', 0)
    enable_old = getattr(game_globals.configuration, 'enable_old_sprites', False)
    runtime_globals.game_console.log(
        f"[Sprite] Loading {pet_name} - preference={preference}, enable_old={enable_old}, "
        f"primary={primary_sprite_format}, secondary={secondary_sprite_format}"
    )

    all_types = ["Color", "Dot", "HD"]
    load_order = _compute_sprite_load_order(primary_sprite_format, secondary_sprite_format)

    for sprite_type in load_order:
        if sprite_type in all_types:  # Safety check
            sprites = try_load_sprite_type(sprite_type, module_path, sprite_name, size, scale)
            if sprites:
                return sprites, sprite_type

    runtime_globals.game_console.log(
        f"[Sprite] No sprites found for {pet_name} ({sprite_name}) - "
        f"tried types: {load_order}"
    )
    return {}, None


def load_enemy_sprites(
    enemy_name: str,
    module_path: str,
    name_format: str = "$_dmc",
    size: tuple = None,
    scale: float = 1.0,
    primary_sprite_format: str = "Color",
    secondary_sprite_format: str = "HD"
) -> Dict[int, pygame.Surface]:
    """
    Load enemy sprites using the same system as pets.
    
    Args:
        enemy_name: Name of the enemy
        module_path: Path to the module folder
        name_format: Format string for sprite naming (default: "$_dmc")
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        primary_sprite_format: Module's primary format ("Dot", "Color", or "HD")
        secondary_sprite_format: Module's secondary format ("Dot", "Color", or "HD")
        
    Returns:
        Dictionary mapping frame number (int) to pygame Surface
    """
    # Enemies use the same loading system as pets
    return load_pet_sprites(enemy_name, module_path, name_format, size, scale, 
                           primary_sprite_format, secondary_sprite_format)


def convert_sprites_to_list(sprites_dict: Dict[int, pygame.Surface], max_frames: int = 20) -> List[Optional[pygame.Surface]]:
    """
    Convert sprite dictionary to ordered list maintaining frame order.
    
    Missing frames are kept as None (not filled with white squares).
    If dictionary is empty, creates a list of None values.
    
    Args:
        sprites_dict: Dictionary mapping frame number (int) to pygame Surface
        max_frames: Maximum number of frames to include (0-15 is standard, default 20 for safety)
        
    Returns:
        List of sprite surfaces or None for missing frames
    """
    sprite_list = [None] * max_frames
    
    for frame_num, sprite in sprites_dict.items():
        if isinstance(frame_num, int) and 0 <= frame_num < max_frames:
            sprite_list[frame_num] = sprite
    
    return sprite_list


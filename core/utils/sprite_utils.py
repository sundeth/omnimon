"""
Sprite loading utilities for pets and enemies with fallback support and zip file compatibility.
"""
import os
import zipfile
import pygame
import io
from typing import Dict, List
from core import runtime_globals, game_globals
from core.utils.asset_utils import image_load, resolve_path


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


def load_sprites_from_directory(sprite_path: str, size: tuple = None, scale: float = 1.0) -> Dict[str, pygame.Surface]:
    """
    Load all PNG sprites from a directory.
    
    Args:
        sprite_path: Path to directory containing sprites
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        
    Returns:
        Dictionary mapping filename (without .png) to pygame Surface
    """
    sprites = {}
    # Resolve path for Android compatibility
    resolved_path = resolve_path(sprite_path)
    runtime_globals.game_console.log(f"[Sprite] Checking directory: {sprite_path} -> {resolved_path}")
    if not os.path.exists(resolved_path):
        runtime_globals.game_console.log(f"[Sprite] Directory does not exist: {resolved_path}")
        return sprites
    if not os.path.isdir(resolved_path):
        runtime_globals.game_console.log(f"[Sprite] Path is not a directory: {resolved_path}")
        return sprites
    
    try:
        files = os.listdir(resolved_path)
        runtime_globals.game_console.log(f"[Sprite] Found {len(files)} files in {resolved_path}")
        for filename in files:
            if filename.lower().endswith('.png'):
                # Use original relative path for image_load (it handles Android paths internally)
                file_path = os.path.join(sprite_path, filename)
                try:
                    sprite = image_load(file_path).convert_alpha()
                    
                    # Apply scaling
                    if size:
                        # Use proportional scaling to maintain aspect ratio
                        sprite = scale_sprite_proportionally(sprite, size)
                    elif scale != 1.0:
                        base_size = sprite.get_size()
                        new_size = (int(base_size[0] * scale), int(base_size[1] * scale))
                        sprite = pygame.transform.scale(sprite, new_size)
                    
                    sprite_name = filename[:-4]  # Remove .png extension
                    sprites[sprite_name] = sprite
                except pygame.error as e:
                    runtime_globals.game_console.log(f"Failed to load sprite {file_path}: {e}")
    except OSError as e:
        runtime_globals.game_console.log(f"Failed to read directory {resolved_path}: {e}")
    
    return sprites


def load_sprites_from_zip(zip_path: str, pet_name: str, size: tuple = None, scale: float = 1.0) -> Dict[str, pygame.Surface]:
    """
    Load sprites from a zip file. Supports sprites in root or in a subfolder.
    
    Args:
        zip_path: Path to zip file
        pet_name: Name of pet (used to check for subfolder)
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        
    Returns:
        Dictionary mapping filename (without .png) to pygame Surface
    """
    sprites = {}
    # Resolve path for Android compatibility
    resolved_zip_path = resolve_path(zip_path)
    runtime_globals.game_console.log(f"[Sprite] Checking zip: {zip_path} -> {resolved_zip_path}")
    if not os.path.exists(resolved_zip_path):
        runtime_globals.game_console.log(f"[Sprite] Zip file does not exist: {resolved_zip_path}")
        return sprites
    
    try:
        with zipfile.ZipFile(resolved_zip_path, 'r') as zip_file:
            # Get list of PNG files in the zip
            png_files = [f for f in zip_file.namelist() if f.lower().endswith('.png')]
            
            for zip_entry in png_files:
                try:
                    # Read the file data
                    with zip_file.open(zip_entry) as sprite_file:
                        sprite_data = sprite_file.read()
                    
                    # Create pygame surface from the data
                    sprite = pygame.image.load(io.BytesIO(sprite_data)).convert_alpha()
                    
                    # Apply scaling
                    if size:
                        # Use proportional scaling to maintain aspect ratio
                        sprite = scale_sprite_proportionally(sprite, size)
                    elif scale != 1.0:
                        base_size = sprite.get_size()
                        new_size = (int(base_size[0] * scale), int(base_size[1] * scale))
                        sprite = pygame.transform.scale(sprite, new_size)
                    
                    # Extract just the filename (handle both root and subfolder cases)
                    filename = os.path.basename(zip_entry)
                    sprite_name = filename[:-4]  # Remove .png extension
                    sprites[sprite_name] = sprite
                    
                except Exception as e:
                    runtime_globals.game_console.log(f"Failed to load sprite {zip_entry} from {zip_path}: {e}")
                    
    except zipfile.BadZipFile as e:
        runtime_globals.game_console.log(f"Invalid zip file {zip_path}: {e}")
    except Exception as e:
        runtime_globals.game_console.log(f"Failed to read zip file {zip_path}: {e}")
    
    return sprites


def load_pet_sprites(pet_name: str, module_path: str, name_format: str = "$_dmc", size: tuple = None, scale: float = 1.0, module_high_definition_sprites: bool = False) -> Dict[str, pygame.Surface]:
    """
    Load pet sprites with fallback support and zip file compatibility.
    
    Loading order depends on game_globals.sprite_resolution_preference and module settings:
    - 0 (auto): Use hidef if module supports it, otherwise regular
    - 1 (regular): Try regular first, then hidef if not found
    - 2 (hidef): Try hidef first, then regular if not found
    
    Args:
        pet_name: Name of the pet
        module_path: Path to the module folder
        name_format: Format string for sprite naming (default: "$_dmc")
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        module_high_definition_sprites: Whether module supports high definition sprites
        
    Returns:
        Dictionary mapping sprite frame names to pygame Surfaces
    """
    
    sprite_name = get_sprite_name(pet_name, name_format)
    sprites = {}
    
    # Determine sprite resolution preference
    preference = getattr(game_globals.configuration, 'sprite_resolution_preference', 0)
    #preference = 2
    
    def try_load_sprites(sprite_folder: str, log_suffix: str) -> Dict[str, pygame.Surface]:
        """Helper to try loading sprites from both directory and zip."""
        runtime_globals.game_console.log(f"[Sprite] Trying to load {pet_name} ({sprite_name}) from {log_suffix}")
        # Try directory first
        module_sprite_dir = os.path.join(module_path, sprite_folder, sprite_name)
        runtime_globals.game_console.log(f"[Sprite] Attempting module directory: {module_sprite_dir}")
        sprites = load_sprites_from_directory(module_sprite_dir, size, scale)
        if sprites:
            runtime_globals.game_console.log(f"Loaded {len(sprites)} sprites for {pet_name} from module {log_suffix} directory")
            return sprites
        
        # Try zip file
        module_sprite_zip = os.path.join(module_path, sprite_folder, f"{sprite_name}.zip")
        runtime_globals.game_console.log(f"[Sprite] Attempting module zip: {module_sprite_zip}")
        sprites = load_sprites_from_zip(module_sprite_zip, sprite_name, size, scale)
        if sprites:
            runtime_globals.game_console.log(f"Loaded {len(sprites)} sprites for {pet_name} from module {log_suffix} zip")
            return sprites
            
        # Try assets directory
        assets_sprite_dir = os.path.join("assets", sprite_folder, sprite_name)
        runtime_globals.game_console.log(f"[Sprite] Attempting assets directory: {assets_sprite_dir}")
        sprites = load_sprites_from_directory(assets_sprite_dir, size, scale)
        if sprites:
            runtime_globals.game_console.log(f"Loaded {len(sprites)} sprites for {pet_name} from assets {log_suffix} directory")
            return sprites
        
        # Try assets zip file
        assets_sprite_zip = os.path.join("assets", sprite_folder, f"{sprite_name}.zip")
        runtime_globals.game_console.log(f"[Sprite] Attempting assets zip: {assets_sprite_zip}")
        sprites = load_sprites_from_zip(assets_sprite_zip, sprite_name, size, scale)
        if sprites:
            runtime_globals.game_console.log(f"Loaded {len(sprites)} sprites for {pet_name} from assets {log_suffix} zip")
            return sprites
            
        return {}
    
    if preference == 0:  # Auto - use hidef if module supports it
        if module_high_definition_sprites:
            sprites = try_load_sprites("monsters_hidef", "hidef")
            if sprites:
                return sprites
        # Fallback to regular
        sprites = try_load_sprites("monsters", "regular")
        if sprites:
            return sprites
            
    elif preference == 1:  # Regular first, then hidef
        sprites = try_load_sprites("monsters", "regular")
        if sprites:
            return sprites
        # Fallback to hidef
        sprites = try_load_sprites("monsters_hidef", "hidef")
        if sprites:
            return sprites
            
    elif preference == 2:  # Hidef first, then regular
        sprites = try_load_sprites("monsters_hidef", "hidef")
        if sprites:
            return sprites
        # Fallback to regular
        sprites = try_load_sprites("monsters", "regular")
        if sprites:
            return sprites
    
    # No sprites found
    runtime_globals.game_console.log(f"No sprites found for {pet_name} ({sprite_name}) with format {name_format}")
    return sprites


def load_enemy_sprites(enemy_name: str, module_path: str, name_format: str = "$_dmc", size: tuple = None, scale: float = 1.0, module_high_definition_sprites: bool = False) -> Dict[str, pygame.Surface]:
    """
    Load enemy sprites using the same fallback system as pets.
    
    Args:
        enemy_name: Name of the enemy
        module_path: Path to the module folder
        name_format: Format string for sprite naming (default: "$_dmc")
        size: Target size tuple (width, height) for scaling
        scale: Scale factor if size is not provided
        module_high_definition_sprites: Whether module supports high definition sprites
        
    Returns:
        Dictionary mapping sprite frame names to pygame Surfaces
    """
    # Enemies use the same loading system as pets
    return load_pet_sprites(enemy_name, module_path, name_format, size, scale, module_high_definition_sprites)


def convert_sprites_to_list(sprites_dict: Dict[str, pygame.Surface], max_frames: int = 20) -> List[pygame.Surface]:
    """
    Convert sprite dictionary to ordered list for compatibility with existing code.
    
    Args:
        sprites_dict: Dictionary mapping sprite names to surfaces
        max_frames: Maximum number of frames to include
        
    Returns:
        List of sprite surfaces ordered by frame number (0.png, 1.png, etc.)
    """
    sprite_list = []
    for i in range(max_frames):
        frame_name = str(i)
        if frame_name in sprites_dict:
            sprite_list.append(sprites_dict[frame_name])
        else:
            break  # Stop at first missing frame
    return sprite_list

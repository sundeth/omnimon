import os
import pygame
from core import runtime_globals

def image_load(rel_path: str):
    """
    Load an image file, adjusting path for Android environment.
    On Android, builds absolute path from APP_ROOT.
    On desktop, uses relative path as-is.
    
    Args:
        rel_path: Relative path to image (e.g., 'assets/ui/button.png')
    
    Returns:
        pygame.Surface: Loaded image
    """
    if runtime_globals.IS_ANDROID and runtime_globals.APP_ROOT:
        full_path = os.path.join(runtime_globals.APP_ROOT, rel_path)
        return pygame.image.load(full_path)
    else:
        return pygame.image.load(rel_path)

def sound_load(rel_path: str):
    """
    Load a sound file, adjusting path for Android environment.
    On Android, builds absolute path from APP_ROOT.
    On desktop, uses relative path as-is.
    
    Args:
        rel_path: Relative path to sound (e.g., 'assets/dmc_sounds/1.wav')
    
    Returns:
        pygame.mixer.Sound: Loaded sound
    """
    if runtime_globals.IS_ANDROID and runtime_globals.APP_ROOT:
        full_path = os.path.join(runtime_globals.APP_ROOT, rel_path)
        return pygame.mixer.Sound(full_path)
    else:
        return pygame.mixer.Sound(rel_path)

def resolve_path(rel_path: str) -> str:
    """
    Resolve a file path for Android environment.
    On Android, builds absolute path from APP_ROOT.
    On desktop, uses relative path as-is.
    
    Args:
        rel_path: Relative path to file
    
    Returns:
        str: Resolved absolute or relative path
    """
    if runtime_globals.IS_ANDROID and runtime_globals.APP_ROOT:
        return os.path.join(runtime_globals.APP_ROOT, rel_path)
    else:
        return rel_path

def font_load(rel_path: str, size: int):
    """
    Load a font file, adjusting path for Android environment.
    On Android, builds absolute path from APP_ROOT.
    On desktop, uses relative path as-is.
    Pass None as rel_path to use pygame's default font.
    
    Args:
        rel_path: Relative path to font file (e.g., 'assets/DigimonBasic.ttf') or None for default
        size: Font size in pixels
    
    Returns:
        pygame.font.Font: Loaded font
    """
    if size == None or size <= 0:
        size = int(16 * runtime_globals.UI_SCALE)  # Default size if zero provided
    
    if runtime_globals.IS_ANDROID and runtime_globals.APP_ROOT:
        full_path = os.path.join(runtime_globals.APP_ROOT, rel_path)
        return pygame.font.Font(full_path, size)
    else:
        return pygame.font.Font(rel_path, size)

def open_json(rel_path: str, mode='r', encoding='utf-8'):
    """
    Open a JSON file, adjusting path for Android environment.
    On Android, builds absolute path from APP_ROOT.
    On desktop, uses relative path as-is.
    
    Args:
        rel_path: Relative path to JSON file
        mode: File open mode (default 'r')
        encoding: File encoding (default 'utf-8')
    
    Returns:
        File handle
    """
    resolved_path = resolve_path(rel_path)
    return open(resolved_path, mode, encoding=encoding)

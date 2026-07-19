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

class _PixelFont(pygame.font.Font):
    """The game's font: always renders without anti-aliasing.

    Omnipet is pixel-art, so text is drawn with sharp pixels (anti-aliasing
    makes it blurry, especially once the low-res canvas is scaled up).  The
    antialias argument callers pass is ignored.
    """

    def render(self, text, antialias=False, color=(255, 255, 255), bgcolor=None):
        if bgcolor is not None:
            return super().render(text, False, color, bgcolor)
        return super().render(text, False, color)


_font_cache = {}


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

    # Fonts are immutable in this codebase (nothing calls set_bold/italic),
    # so share one Font per (path, size) — constructing a Font opens the TTF
    # from disk, and several draw paths request fonts every frame.
    key = (rel_path, size)
    font = _font_cache.get(key)
    if font is not None:
        return font

    if runtime_globals.IS_ANDROID and runtime_globals.APP_ROOT and rel_path:
        full_path = os.path.join(runtime_globals.APP_ROOT, rel_path)
        font = _PixelFont(full_path, size)
    else:
        font = _PixelFont(rel_path, size)
    _font_cache[key] = font
    return font

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

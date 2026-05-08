#=====================================================================
# GamePoop - Represents a poop object on screen
#=====================================================================

from core import runtime_globals
from utils.pygame_utils import blit_with_cache
from core import constants
import random

class GamePoop:
    """
    Represents a poop entity that can be drawn and animated on screen.
    """

    def __init__(self, x: int, y: int, jumbo=False, use_dot_sprite: bool = False) -> None:
        """
        Initializes the poop object at the given (x, y) position.

        Args:
            x (int): X-coordinate on screen.
            y (int): Y-coordinate on screen.
        """
        self.x = x
        self.y = y
        self.frame_counter = 0
        self.current_frame = 0
        self.frame_index = 0
        self.dirty = False
        self.jumbo = jumbo
        self.use_dot_sprite = use_dot_sprite

    def update(self) -> None:
        """
        Updates the internal animation counter.
        """
        self.frame_counter += 1
        # Alternate between "Poop1" and "Poop2" every 30 frames
        self.frame_index = (self.frame_counter // constants.FRAME_RATE) % 2
        if self.current_frame != self.frame_index:
            self.current_frame = self.frame_index
            self.dirty = True


    def draw(self, surface) -> None:
        """
        Draws the poop on the given surface.

        Args:
            surface: The Pygame surface where the poop is drawn.
        """
        
        base_key = f"JumboPoop{self.frame_index + 1}" if self.jumbo else f"Poop{self.frame_index + 1}"
        sprite_key = f"{base_key}_dot" if self.use_dot_sprite else base_key
        sprite = runtime_globals.misc_sprites.get(sprite_key)
        if sprite is None:
            # Safety fallback to colored sprite if dot variant is unavailable.
            sprite = runtime_globals.misc_sprites.get(base_key)
        if sprite is None:
            return
        #surface.blit(sprite, (self.x, self.y))
        blit_with_cache(surface, sprite, (self.x, self.y))

    def patch(self):
        """
        Patches the poop object to ensure it has the necessary attributes.
        """
        if not hasattr(self, "frame_counter"):
            self.frame_counter = 0
        if not hasattr(self, "current_frame"):
            self.current_frame = 0
        if not hasattr(self, "dirty"):
            self.dirty = False
        if not hasattr(self, "jumbo"):
            self.jumbo = False
        if not hasattr(self, "use_dot_sprite"):
            self.use_dot_sprite = False


"""
XrosAnimation — the temporary-evolution (Xros / Mode Change) sequence.

The screen is split into one cell per transforming pet:
    1 pet   -> fullscreen
    2 pets  -> split along the larger screen dimension
    3-4     -> 2x2
    5-6     -> 3x2 (or 2x3 on portrait render resolutions)
    7+      -> 4x2 (or 2x4)

Timeline per cell (all cells run in sync):
    0.0 - 0.5s  evolution background only
    0.5 - 1.5s  friend sprites required by the evolution, one at a time,
                offset to the sides of the center (left, right, left, ...)
    1.5 - 2.0s  the pet's (pre-evolution) sprite
    2.0 - 3.0s  the 5-frame xros animation (background + animation ONLY)
    3.0 - 3.5s  the evolved pet on its happy frame
    3.5s        finished

The evolution sound plays once at the start of the 5-frame segment.

Optimized for low-power devices: a single canvas holds every cell's
background (composited once at construction) and every sprite is pre-scaled
once — the per-frame draw is one canvas blit plus at most one sprite blit
per cell.
"""

import pygame

from core import constants, runtime_globals
from models.animation import PetFrame
from utils.module_utils import get_module
from utils.pygame_utils import blit_with_cache
from utils.xros_utils import (load_form_sprite, load_xros_animation_frames,
                              load_xros_background)


class XrosAnimation:
    # Segment lengths in seconds
    SEG_BG = 0.5
    SEG_FRIENDS = 1.0
    SEG_PET = 0.5
    SEG_ANIM = 1.0
    SEG_EVOLVED = 0.5

    def __init__(self, selections):
        """
        Args:
            selections: list of (pet, temp_evo) for pets that ARE transforming.
                Must be called BEFORE apply_temp_evolution so the pets' current
                sprites are still their pre-evolution forms.
        """
        fps = constants.FRAME_RATE
        self.frame = 0
        self.sound_played = False

        # Segment boundaries in frames
        self.t_friends = int(self.SEG_BG * fps)
        self.t_pet = self.t_friends + int(self.SEG_FRIENDS * fps)
        self.t_anim = self.t_pet + int(self.SEG_PET * fps)
        self.t_evolved = self.t_anim + int(self.SEG_ANIM * fps)
        self.t_end = self.t_evolved + int(self.SEG_EVOLVED * fps)
        self.friends_frames = max(1, self.t_pet - self.t_friends)
        self.anim_frames = max(1, self.t_evolved - self.t_anim)

        sw, sh = runtime_globals.SCREEN_WIDTH, runtime_globals.SCREEN_HEIGHT
        cols, rows = self._grid(len(selections), sw, sh)
        cell_w, cell_h = sw // cols, sh // rows
        sprite_size = int(min(cell_w, cell_h) * 0.55)

        # Single static canvas with every cell's background composited once.
        self.canvas = pygame.Surface((sw, sh))
        self.canvas.fill((0, 0, 0))

        self.cells = []
        for i, (pet, evo) in enumerate(selections):
            col, row = i % cols, i // cols
            cx = col * cell_w + cell_w // 2
            cy = row * cell_h + cell_h // 2
            module = get_module(pet.module)

            bg = load_xros_background(module, evo.get("background"), (cell_w, cell_h))
            if bg:
                self.canvas.blit(bg, (col * cell_w, row * cell_h))

            # Friend sprites (may be empty)
            friends = []
            for fname in (evo.get("friend") or []):
                sprite = load_form_sprite(module, fname, PetFrame.IDLE1.value, sprite_size)
                if sprite:
                    friends.append(sprite)

            # Pre-evolution sprite (pet still has its normal sprites here)
            base = None
            try:
                base = pygame.transform.scale(
                    pet.get_sprite(PetFrame.IDLE1.value), (sprite_size, sprite_size))
            except Exception:
                pass

            frames = load_xros_animation_frames(module, evo.get("animation"), sprite_size)
            evolved = load_form_sprite(module, evo.get("to"), PetFrame.HAPPY.value, sprite_size)

            self.cells.append({
                "center": (cx, cy),
                "half_w": cell_w // 4,
                "friends": friends,
                "base": base,
                "frames": frames,
                "evolved": evolved,
            })

    @staticmethod
    def _grid(n, sw, sh):
        """Grid dimensions for n cells on a sw x sh render surface."""
        if n <= 1:
            return 1, 1
        landscape = sw >= sh
        if n == 2:
            return (2, 1) if landscape else (1, 2)
        per_line = (n + 1) // 2  # two lines of ceil(n/2)
        return (per_line, 2) if landscape else (2, per_line)

    # ------------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self.frame >= self.t_end

    def update(self):
        self.frame += 1
        # Evolution sound once, at the start of the 5-frame animation segment.
        if not self.sound_played and self.frame >= self.t_anim:
            self.sound_played = True
            runtime_globals.game_sound.play("evolution")

    def draw(self, surface):
        # Backgrounds: one blit for the whole screen.
        blit_with_cache(surface, self.canvas, (0, 0))

        f = self.frame
        for cell in self.cells:
            cx, cy = cell["center"]

            if f < self.t_friends:
                continue  # background only

            if f < self.t_pet:
                # Friends, one at a time, offset left / right of the center.
                friends = cell["friends"]
                if not friends:
                    continue
                idx = min(len(friends) - 1,
                          (f - self.t_friends) * len(friends) // self.friends_frames)
                sprite = friends[idx]
                offset = -cell["half_w"] if idx % 2 == 0 else cell["half_w"]
                self._blit_center(surface, sprite, cx + offset, cy)

            elif f < self.t_anim:
                self._blit_center(surface, cell["base"], cx, cy)

            elif f < self.t_evolved:
                # Only background + the xros animation frames.
                frames = cell["frames"]
                if not frames:
                    continue
                idx = min(len(frames) - 1,
                          (f - self.t_anim) * len(frames) // self.anim_frames)
                self._blit_center(surface, frames[idx], cx, cy)

            else:
                self._blit_center(surface, cell["evolved"], cx, cy)

    @staticmethod
    def _blit_center(surface, sprite, cx, cy):
        if sprite is None:
            return
        blit_with_cache(surface, sprite,
                        (cx - sprite.get_width() // 2, cy - sprite.get_height() // 2))

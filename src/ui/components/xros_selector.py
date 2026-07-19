"""
XrosSelector — pre-battle temporary-evolution picker.

Layout:
    [pet1][pet2][pet...n]
    [Confirm]

Each box shows the pet's current choice (its normal form, or one of its
available temporary evolutions).  A / LCLICK on the focused box cycles the
choice forward (cyclical); LEFT/RIGHT move between the boxes and the Confirm
button.  There is no cancel — Confirm with every box on the normal form just
skips the transformation.

All sprites are pre-scaled once at construction (low-power friendly).
"""

import pygame

from core import runtime_globals
from models.animation import PetFrame
from utils.module_utils import get_module
from utils.pygame_utils import blit_with_cache, get_font
from utils.xros_utils import load_form_sprite


class XrosSelector:
    def __init__(self, candidates, ui_manager):
        """
        Args:
            candidates: list of (pet, [temp_evo, ...]) — options must be non-empty.
            ui_manager: battle UI manager (used for theme colors).
        """
        self.ui_manager = ui_manager
        self.entries = []          # one per pet
        self.focus = 0             # 0..n-1 = boxes, n = confirm button
        self.confirmed = False

        sw, sh = runtime_globals.SCREEN_WIDTH, runtime_globals.SCREEN_HEIGHT
        scale = runtime_globals.UI_SCALE
        n = max(1, len(candidates))

        # Box layout: side by side, centered
        margin = int(8 * scale)
        gap = int(6 * scale)
        box_w = min(int(72 * scale), (sw - margin * 2 - gap * (n - 1)) // n)
        box_h = int(96 * scale)
        total_w = n * box_w + (n - 1) * gap
        start_x = (sw - total_w) // 2
        box_y = (sh - box_h) // 2 - int(16 * scale)

        from utils.sprite_utils import snap_pet_sprite_size
        sprite_size = snap_pet_sprite_size(int(box_w * 0.72))
        self.font = get_font(int(10 * scale))

        for i, (pet, options) in enumerate(candidates):
            module = get_module(pet.module)
            # Option 0 = keep normal form; 1..n = temporary evolutions
            option_sprites = []
            option_names = [pet.name]
            base = None
            try:
                base = pet.get_sprite(PetFrame.IDLE1.value)
            except Exception:
                pass
            if base is not None:
                base = pygame.transform.scale(base, (sprite_size, sprite_size))
            option_sprites.append(base)

            for evo in options:
                option_names.append(evo.get("to", "?"))
                sprite = load_form_sprite(module, evo.get("to"),
                                          PetFrame.IDLE1.value, sprite_size)
                option_sprites.append(sprite)

            rect = pygame.Rect(start_x + i * (box_w + gap), box_y, box_w, box_h)
            self.entries.append({
                "pet": pet,
                "options": [None] + list(options),
                "names": option_names,
                "sprites": option_sprites,
                "labels": [self.font.render(nm, True, (255, 255, 255))
                           for nm in option_names],
                "index": 0,
                "rect": rect,
            })

        # Confirm button
        btn_w = int(90 * scale)
        btn_h = int(22 * scale)
        self.confirm_rect = pygame.Rect((sw - btn_w) // 2,
                                        box_y + box_h + int(14 * scale),
                                        btn_w, btn_h)
        self.confirm_label = get_font(int(12 * scale)).render(
            "Confirm", True, (255, 255, 255))

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def get_selections(self):
        """[(pet, temp_evo_or_None), ...] in party order."""
        return [(e["pet"], e["options"][e["index"]]) for e in self.entries]

    def has_any_selection(self) -> bool:
        return any(e["index"] > 0 for e in self.entries)

    def _cycle(self, entry):
        entry["index"] = (entry["index"] + 1) % len(entry["options"])
        runtime_globals.game_sound.play("menu")

    # ------------------------------------------------------------------
    # Input — returns "confirm" when the player confirms
    # ------------------------------------------------------------------

    def handle_event(self, event):
        if not isinstance(event, tuple) or len(event) != 2:
            return None
        event_type, event_data = event
        total = len(self.entries) + 1  # boxes + confirm

        if event_type == "LEFT":
            self.focus = (self.focus - 1) % total
            runtime_globals.game_sound.play("menu")
            return None
        if event_type == "RIGHT":
            self.focus = (self.focus + 1) % total
            runtime_globals.game_sound.play("menu")
            return None
        if event_type == "DOWN":
            self.focus = len(self.entries)
            runtime_globals.game_sound.play("menu")
            return None
        if event_type == "UP":
            if self.focus == len(self.entries):
                self.focus = 0
                runtime_globals.game_sound.play("menu")
            return None

        if event_type == "A":
            if self.focus < len(self.entries):
                self._cycle(self.entries[self.focus])
            else:
                self.confirmed = True
                runtime_globals.game_sound.play("menu")
                return "confirm"
            return None

        if event_type == "LCLICK" and event_data and "pos" in event_data:
            pos = event_data["pos"]
            if self.confirm_rect.collidepoint(pos):
                self.confirmed = True
                runtime_globals.game_sound.play("menu")
                return "confirm"
            for i, entry in enumerate(self.entries):
                if entry["rect"].collidepoint(pos):
                    self.focus = i
                    self._cycle(entry)
                    return None
        return None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface):
        colors = self.ui_manager.get_theme_colors() if self.ui_manager else \
            {"bg": (0, 60, 0), "fg": (0, 200, 80), "highlight": (120, 255, 160)}
        fg = colors.get("fg", (0, 200, 80))
        highlight = colors.get("highlight", fg)
        scale = runtime_globals.UI_SCALE
        border = max(1, int(2 * scale))

        for i, entry in enumerate(self.entries):
            rect = entry["rect"]
            focused = (i == self.focus)

            # Box (static background = default black; theme border)
            pygame.draw.rect(surface, (0, 0, 0), rect)
            pygame.draw.rect(surface, highlight if focused else fg, rect, border)

            # Current option sprite + name
            sprite = entry["sprites"][entry["index"]]
            if sprite:
                sx = rect.x + (rect.width - sprite.get_width()) // 2
                sy = rect.y + int(6 * scale)
                blit_with_cache(surface, sprite, (sx, sy))
            label = entry["labels"][entry["index"]]
            lx = rect.x + (rect.width - label.get_width()) // 2
            ly = rect.bottom - label.get_height() - int(4 * scale)
            blit_with_cache(surface, label, (lx, ly))

            # Selection arrows on the focused box sides (theme colors)
            if focused:
                ah = int(8 * scale)
                cy = rect.centery
                left_x = rect.x - int(4 * scale)
                right_x = rect.right + int(4 * scale)
                pygame.draw.polygon(surface, highlight, [
                    (left_x, cy - ah), (left_x, cy + ah), (left_x - ah, cy)])
                pygame.draw.polygon(surface, highlight, [
                    (right_x, cy - ah), (right_x, cy + ah), (right_x + ah, cy)])

        # Confirm button
        focused = (self.focus == len(self.entries))
        pygame.draw.rect(surface, (0, 0, 0), self.confirm_rect)
        pygame.draw.rect(surface, highlight if focused else fg,
                         self.confirm_rect, border)
        lx = self.confirm_rect.x + (self.confirm_rect.width - self.confirm_label.get_width()) // 2
        ly = self.confirm_rect.y + (self.confirm_rect.height - self.confirm_label.get_height()) // 2
        blit_with_cache(surface, self.confirm_label, (lx, ly))

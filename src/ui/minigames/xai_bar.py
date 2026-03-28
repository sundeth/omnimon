import pygame

import core.constants as constants
from utils.pygame_utils import blit_with_shadow, sprite_load_percent
from core import runtime_globals


XAIARROW_ICON_PATH = "assets/XaiArrow.png"  # Update this path as needed

class XaiBar:
    """XAI bar minigame for DMX ruleset"""
    
    @property
    def WIDTH(self):
        return int(152 * runtime_globals.UI_SCALE)
    
    @property
    def HEIGHT(self):
        return int(72 * runtime_globals.UI_SCALE)
    
    @property
    def INNER_WIDTH(self):
        return int(148 * runtime_globals.UI_SCALE)
    
    @property
    def INNER_HEIGHT(self):
        return int(68 * runtime_globals.UI_SCALE)

    def __init__(self, x, y, xai_number, pet):
        self.x = x
        self.y = y
        self.xai_number = xai_number
        self.pet = pet

        ext_height = 30 * runtime_globals.UI_SCALE
        self.arrow_height = int(ext_height * 0.8)
        self.arrow_sprite = sprite_load_percent(
            XAIARROW_ICON_PATH,
            percent=(self.arrow_height / runtime_globals.SCREEN_HEIGHT) * 100,
            keep_proportion=True,
            base_on="height"
        )
        self.arrow_width = self.arrow_sprite.get_width()
        self.arrow_animating = False
        self.arrow_anim_dir = 1
        self.arrow_anim_x = 0
        self.arrow_anim_min = self.x + 2 - self.arrow_width // 2
        self.arrow_anim_max = self.x + 2 + self.INNER_WIDTH - self.arrow_width // 2
        self.selected_strength = None

        # Caches
        self._bar_structures_cache = None
        self._bar_surfaces_cache = None
        self._cache_key = None
        self._static_surfaces = None  # (border_surf, inner_surf, ext_surf)

        self._update_cache()

    def _update_cache(self):
        # Use pet name, level, stage, and window size as cache key
        key = (self.pet.name, self.pet.level, self.pet.stage, runtime_globals.SCREEN_WIDTH, runtime_globals.SCREEN_HEIGHT)
        if key != self._cache_key:
            self._bar_structures_cache = self._compute_bar_structures()
            self._bar_surfaces_cache = self._compute_bar_surfaces()
            self._static_surfaces = self._compute_static_surfaces()
            self._cache_key = key

    def start(self):
        self.arrow_animating = True
        self.arrow_anim_dir = 1
        self.arrow_anim_x = self.arrow_anim_min
        self.selected_strength = None

    def stop(self):
        self.arrow_animating = False
        self.selected_strength = self._get_strength_from_arrow()

    def update(self):
        if self.arrow_animating:
            speed = max(1, 8 - self.xai_number) * (30 / constants.FRAME_RATE)
            self.arrow_anim_x += self.arrow_anim_dir * speed * runtime_globals.UI_SCALE
            if self.arrow_anim_x <= self.arrow_anim_min:
                self.arrow_anim_x = self.arrow_anim_min
                self.arrow_anim_dir = 1
            elif self.arrow_anim_x >= self.arrow_anim_max:
                self.arrow_anim_x = self.arrow_anim_max
                self.arrow_anim_dir = -1

    def _compute_bar_structures(self):
        yellow_width, orange_width, orange_height, red_width, red_height = self.getBars()
        name_seed = sum(ord(c) for c in self.pet.name)
        base_y = self.y + int(2 * runtime_globals.UI_SCALE)
        bar_left = self.x + int(2 * runtime_globals.UI_SCALE)
        bar_right = self.x + int(2 * runtime_globals.UI_SCALE) + self.INNER_WIDTH

        rects = []

        if self.pet.stage < 5:
            total_width = red_width + orange_width + yellow_width + orange_width + red_width
            max_x = bar_right - total_width
            min_x = bar_left
            offset = (name_seed % (max_x - min_x + 1)) if (max_x - min_x) > 0 else 0
            group_x = min_x + offset

            red_left_rect = pygame.Rect(group_x, base_y + self.INNER_HEIGHT - red_height, red_width, red_height)
            orange_left_rect = pygame.Rect(red_left_rect.right, base_y + self.INNER_HEIGHT - orange_height, orange_width, orange_height)
            yellow_rect = pygame.Rect(orange_left_rect.right, base_y, yellow_width, self.INNER_HEIGHT)
            orange_right_rect = pygame.Rect(yellow_rect.right, base_y + self.INNER_HEIGHT - orange_height, orange_width, orange_height)
            red_right_rect = pygame.Rect(orange_right_rect.right, base_y + self.INNER_HEIGHT - red_height, red_width, red_height)

            if red_left_rect.left < bar_left:
                clip = bar_left - red_left_rect.left
                red_left_rect.width -= clip
                red_left_rect.left = bar_left
            if red_left_rect.width > 0:
                rects.append((red_left_rect, 1))

            rects.append((orange_left_rect, 2))
            rects.append((yellow_rect, 3))
            rects.append((orange_right_rect, 2))

            if red_right_rect.right > bar_right:
                red_right_rect.width -= (red_right_rect.right - bar_right)
            if red_right_rect.width > 0:
                rects.append((red_right_rect, 1))
        else:
            side = "left" if (name_seed % 2 == 0) else "right"
            order = "small_first" if (name_seed % 4 < 2) else "big_first"

            struct1 = {
                "yellow": yellow_width,
                "orange": orange_width,
                "red": red_width
            }
            struct2 = {
                "yellow": yellow_width,
                "orange": orange_width,
                "red": 0
            }
            if order == "big_first":
                struct1, struct2 = struct2, struct1

            gap = int(8 * runtime_globals.UI_SCALE)
            total_width = (
                struct1["yellow"] + struct1["orange"] + struct1["red"] +
                struct2["yellow"] + struct2["orange"] + struct2["red"] +
                gap
            )
            max_x = bar_right - total_width
            min_x = bar_left
            offset = (name_seed % (max_x - min_x + 1)) if (max_x - min_x) > 0 else 0
            group_x = min_x + offset

            if side == "left":
                red1 = pygame.Rect(group_x, base_y + self.INNER_HEIGHT - red_height, struct1["red"], red_height)
                orange1 = pygame.Rect(red1.right, base_y + self.INNER_HEIGHT - orange_height, struct1["orange"], orange_height)
                yellow1 = pygame.Rect(orange1.right, base_y, struct1["yellow"], self.INNER_HEIGHT)
            else:
                yellow1 = pygame.Rect(group_x, base_y, struct1["yellow"], self.INNER_HEIGHT)
                orange1 = pygame.Rect(yellow1.right, base_y + self.INNER_HEIGHT - orange_height, struct1["orange"], orange_height)
                red1 = pygame.Rect(orange1.right, base_y + self.INNER_HEIGHT - red_height, struct1["red"], red_height)

            group_x2 = (group_x + struct1["red"] + struct1["orange"] + struct1["yellow"] + gap
                        if side == "left"
                        else group_x + struct1["yellow"] + struct1["orange"] + struct1["red"] + gap)

            if side == "left":
                red2 = pygame.Rect(group_x2, base_y + self.INNER_HEIGHT - red_height, struct2["red"], red_height)
                orange2 = pygame.Rect(red2.right, base_y + self.INNER_HEIGHT - orange_height, struct2["orange"], orange_height)
                yellow2 = pygame.Rect(orange2.right, base_y, struct2["yellow"], self.INNER_HEIGHT)
            else:
                yellow2 = pygame.Rect(group_x2, base_y, struct2["yellow"], self.INNER_HEIGHT)
                orange2 = pygame.Rect(yellow2.right, base_y + self.INNER_HEIGHT - orange_height, struct2["orange"], orange_height)
                red2 = pygame.Rect(orange2.right, base_y + self.INNER_HEIGHT - red_height, struct2["red"], red_height)

            if side == "left":
                if red1.width > 0: rects.append((red1, 1))
                if orange1.width > 0: rects.append((orange1, 2))
                if yellow1.width > 0: rects.append((yellow1, 3))
                if orange2.width > 0: rects.append((orange2, 2))
                if yellow2.width > 0: rects.append((yellow2, 3))
            else:
                if yellow1.width > 0: rects.append((yellow1, 3))
                if orange1.width > 0: rects.append((orange1, 2))
                if red1.width > 0: rects.append((red1, 1))
                if yellow2.width > 0: rects.append((yellow2, 3))
                if orange2.width > 0: rects.append((orange2, 2))
                if struct2["red"] > 1 and red2.width > 0:
                    rects.append((red2, 1))
        return rects

    def _compute_bar_surfaces(self):
        # Pre-render colored bar surfaces for each rect
        color_map = {1: (255, 0, 0), 2: (255, 165, 0), 3: (255, 255, 0)}
        surfaces = []
        for rect, val in self._bar_structures_cache:
            if rect.width > 0 and rect.height > 0:
                surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                pygame.draw.rect(surf, color_map[val], (0, 0, rect.width, rect.height), 0)
                surfaces.append((surf, rect.x, rect.y))
        return surfaces

    @property
    def structures(self):
        self._update_cache()
        return self._bar_structures_cache

    @property
    def bar_surfaces(self):
        self._update_cache()
        return self._bar_surfaces_cache

    def _get_strength_from_arrow(self):
        arrow_mid = self.arrow_anim_x + self.arrow_width // 2
        for rect, val in self.structures:
            if rect.left <= arrow_mid <= rect.right:
                return val
        return 0

    def get_result(self):
        """Get the strength result from the minigame (0-3)"""
        return self.selected_strength if self.selected_strength is not None else 0

    def handle_event(self, event):
        """Handle input events for the XAI bar minigame"""
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        
        event_type, event_data = event
        
        if event_type in ("A", "LCLICK"):
            if self.arrow_animating:
                self.stop()
                return True
        return False

    def draw(self, surface):
        # Use cached static surfaces to avoid per-frame allocations
        border_surf, inner_surf, ext_surf, ext_height = self._static_surfaces
        ext_y = self.y - ext_height
        blit_with_shadow(surface, border_surf, (self.x, self.y))
        blit_with_shadow(surface, inner_surf, (self.x + int(2 * runtime_globals.UI_SCALE), self.y + int(2 * runtime_globals.UI_SCALE)))
        blit_with_shadow(surface, ext_surf, (self.x, ext_y))

        # Draw arrow sprite at the top, centered or animating, with shadow
        if self.arrow_animating or self.selected_strength is not None:
            arrow_x = int(self.arrow_anim_x)
        else:
            arrow_x = self.x + (self.WIDTH - self.arrow_width) // 2
        arrow_y = ext_y + (ext_height - self.arrow_height) // 2
        blit_with_shadow(surface, self.arrow_sprite, (arrow_x, arrow_y))

        # Draw cached bar surfaces
        for surf, x, y in self.bar_surfaces:
            blit_with_shadow(surface, surf, (x, y))

    def getBars(self):
        yellow_width = int((7 + (self.pet.level / 4)) * runtime_globals.UI_SCALE)
        orange_width = int((20 + (self.pet.level / 3)) * runtime_globals.UI_SCALE)
        orange_height = int((self.INNER_HEIGHT * 2 / 3))
        red_width = int((26 + (self.pet.level / 4)) * runtime_globals.UI_SCALE)
        red_height = int((self.INNER_HEIGHT / 3))
        return yellow_width, orange_width, orange_height, red_width, red_height

    def _compute_static_surfaces(self):
        # Pre-render static surfaces used every frame
        border_surf = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (0, 0, 0), (0, 0, self.WIDTH, self.HEIGHT), 0)

        inner_surf = pygame.Surface((self.INNER_WIDTH, self.INNER_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(inner_surf, (255, 255, 255, 200), (0, 0, self.INNER_WIDTH, self.INNER_HEIGHT), 0)

        ext_height = int(30 * runtime_globals.UI_SCALE)
        ext_surf = pygame.Surface((self.WIDTH, ext_height), pygame.SRCALPHA)
        pygame.draw.rect(ext_surf, (0, 0, 0), (0, 0, self.WIDTH, ext_height), 0)
        pygame.draw.rect(ext_surf, (255, 255, 255, 200), (int(2 * runtime_globals.UI_SCALE), int(2 * runtime_globals.UI_SCALE), self.INNER_WIDTH, ext_height - int(4 * runtime_globals.UI_SCALE)), 0)

        return border_surf, inner_surf, ext_surf, ext_height
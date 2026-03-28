import time
import pygame

from core import game_globals, runtime_globals
import core.constants as constants
from utils.pet_utils import pets_need_care
from utils.pygame_utils import blit_with_cache
from utils.asset_utils import image_load

#=====================================================================
# WindowMenu - Main Menu Icon Bar (Optimized)
#=====================================================================

class WindowMenu:
    """
    Displays the main menu icons at the top and bottom of the screen,
    and highlights the currently selected item.
    """

    def __init__(self):
        self.icons = []
        self.spacing_x = 0
        self.top_y = 0
        self.bottom_y = runtime_globals.SCREEN_HEIGHT - (runtime_globals.MENU_ICON_SIZE * 2) - 10

        self.top_positions = []
        self.bottom_positions = []

        # Absolute on-screen rectangles for all 10 icons (top 0-4, bottom 5-9)
        # This is the single source of truth for hit-testing (mouse/touch).
        self.icon_rects = []

        self.prev_menu_index = -2
        self.prev_alert_state = None

        self.top_cache = None
        self.bottom_cache = None

        self.last_alert_check = time.time()

        self.load_icons()
        self.calculate_spacing()
        self.update_cache(True)


    def load_icons(self):
        """
        Loads and scales the menu icons from the sprite sheet.
        """
        try:
            menu_sheet = pygame.transform.scale(
                image_load(constants.MAIN_MENU_PATH).convert_alpha(),
                (runtime_globals.MENU_ICON_SIZE * 2, runtime_globals.MENU_ICON_SIZE * 10)
            )
            for i in range(10):  # 10 menu items
                normal = menu_sheet.subsurface((0, i * runtime_globals.MENU_ICON_SIZE, runtime_globals.MENU_ICON_SIZE, runtime_globals.MENU_ICON_SIZE))
                selected = menu_sheet.subsurface((runtime_globals.MENU_ICON_SIZE, i * runtime_globals.MENU_ICON_SIZE, runtime_globals.MENU_ICON_SIZE, runtime_globals.MENU_ICON_SIZE))
                normal = pygame.transform.scale(normal, (runtime_globals.MENU_ICON_SIZE * 2, runtime_globals.MENU_ICON_SIZE * 2))
                selected = pygame.transform.scale(selected, (runtime_globals.MENU_ICON_SIZE * 2, runtime_globals.MENU_ICON_SIZE * 2))
                self.icons.append((normal, selected))
        except pygame.error:
            runtime_globals.game_console.log("⚠️ Failed to load Menu.png")


    def calculate_spacing(self):
        """Precomputes icon positions to avoid unnecessary calculations."""
        # Divide by 6 to evenly space the icons on the screen. Dividing by 5 shifts the icons to the right on wide screens.
        self.spacing_x = (runtime_globals.SCREEN_WIDTH - (5 * runtime_globals.MENU_ICON_SIZE * 2)) // 6
        self.top_y = 20 * runtime_globals.UI_SCALE if game_globals.showClock else 5 * runtime_globals.UI_SCALE

        icon_w = runtime_globals.MENU_ICON_SIZE * 2
        icon_h = runtime_globals.MENU_ICON_SIZE * 2

        self.top_positions = [
            (self.spacing_x + i * (icon_w + self.spacing_x), 0) for i in range(5)
        ]
        self.bottom_positions = [
            (self.spacing_x + (i - 5) * (icon_w + self.spacing_x), 0) for i in range(5, 10)
        ]

        # Build absolute on-screen rects for hit-testing
        self.icon_rects = []
        for i, (x, y) in enumerate(self.top_positions):
            self.icon_rects.append(pygame.Rect(x, self.top_y + y, icon_w, icon_h))
        for i, (x, y) in enumerate(self.bottom_positions, start=5):
            self.icon_rects.append(pygame.Rect(x, self.bottom_y + y, icon_w, icon_h))


    def update_cache(self, force=False):
        """
        Rebuilds top and bottom caches only if state changes.
        """
        menu_index = runtime_globals.main_menu_index
        alert = self.check_alert()

        # Update top cache if selection changed
        if self.prev_menu_index != menu_index or force:
            self.top_cache = pygame.Surface((runtime_globals.SCREEN_WIDTH, runtime_globals.MENU_ICON_SIZE * 2), pygame.SRCALPHA)
            for i, (x, y) in enumerate(self.top_positions):
                selected = (i == menu_index) and runtime_globals.INPUT_MODE != runtime_globals.TOUCH_MODE
                icon = self.icons[i][1] if selected else self.icons[i][0]
                self.top_cache.blit(icon, (x, y))
        
        # Update bottom cache if selection or alert changed
        if self.prev_menu_index != menu_index or self.prev_alert_state != alert or force:
            self.bottom_cache = pygame.Surface((runtime_globals.SCREEN_WIDTH, runtime_globals.MENU_ICON_SIZE * 2), pygame.SRCALPHA)
            for i, (x, y) in enumerate(self.bottom_positions, start=5):
                selected = (i == menu_index) and runtime_globals.INPUT_MODE != runtime_globals.TOUCH_MODE
                if i == 9 and alert:
                    icon = self.icons[i][1]
                else:
                    icon = self.icons[i][1] if selected else self.icons[i][0]
                self.bottom_cache.blit(icon, (x, y))

        self.prev_menu_index = menu_index
        self.prev_alert_state = alert


    def draw(self, surface):
        """
        Efficiently draws menu icons using pre-rendered surfaces.
        """
        if not self.icons:
            return

        self.update_cache()
        if self.top_cache:
            #surface.blit(self.top_cache, (0, self.top_y))
            blit_with_cache(surface, self.top_cache, (0, self.top_y))
        if self.bottom_cache:
            #surface.blit(self.bottom_cache, (0, self.bottom_y))
            blit_with_cache(surface, self.bottom_cache, (0, self.bottom_y))


    def get_menu_index_at(self, pos):
        """Return the menu index at the given screen position, or -1 if none.

        This uses precomputed icon_rects so input code does not need to
        duplicate spacing math. Works for both mouse and touch coordinates.
        """
        x, y = pos
        for i, rect in enumerate(self.icon_rects):
            if rect.collidepoint(x, y):
                return i
        return -1


    def move_selection(self, direction):
        """
        Moves the menu selection cursor left or right.

        Args:
            direction (int): -1 for left, 1 for right
        """
        runtime_globals.main_menu_index = (runtime_globals.main_menu_index + direction) % 8


    def check_alert(self):
        now = time.time()
        if now - self.last_alert_check < 2:  # Check alert at most once per second
            return runtime_globals.pet_alert

        alert = pets_need_care()
        self.last_alert_check = now

        if alert != runtime_globals.pet_alert:
            runtime_globals.pet_alert = alert
            if alert:
                runtime_globals.game_sound.play("alarm")

        return runtime_globals.pet_alert

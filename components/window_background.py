import pygame
import time
import os

from core import runtime_globals, game_globals
from core.utils.module_utils import get_module
from core.utils.pygame_utils import blit_with_cache, sprite_load_percent
from core.utils.asset_utils import resolve_path
from core import constants


class WindowBackground:
    def __init__(self, boot=False):
        self.time_of_day = "day"
        self.image = None
        self.last_check_time = 0
        self.last_background = None
        self.last_module = None
        self.last_image_path = None
        self.center = None
        self.update()
        self.load_sprite(boot)

    def draw(self, surface):
        if self.image:
            #surface.blit(self.image, self.center)
            blit_with_cache(surface, self.image, self.center)

    def update(self):
        now = time.time()

        # Exit early if nothing has changed and we checked recently
        if (game_globals.game_background == self.last_background and
            game_globals.background_module_name == self.last_module and
            now - self.last_check_time < 60):
            return

        self.last_check_time = now

        # Check if we need to reload background
        current_hour = time.localtime().tm_hour
        new_time_of_day = (
            "day" if 6 <= current_hour < 16
            else "dusk" if 16 <= current_hour < 19
            else "night"
        )

        background_changed = (
            game_globals.game_background != self.last_background or
            game_globals.background_module_name != self.last_module
        )
        time_changed = new_time_of_day != self.time_of_day

        if background_changed or time_changed:
            self.time_of_day = new_time_of_day
            self.load_sprite(False)

    def load_sprite(self, boot):
        if boot:
            path = "assets/Splash.png"
        else:
            name = game_globals.game_background
            module_name = game_globals.background_module_name

            if not name or not module_name:
                # Use boot background if no background is set
                runtime_globals.game_console.log("[!] No background set, using boot background.")
                path = "assets/Splash.png"
                boot = True
            
            if not boot:
                module = get_module(module_name)
                day_night = True
                for bg in getattr(module, "backgrounds", []):
                    if bg["name"] == name:
                        day_night = bg.get("day_night", True)
                        break

                suffix = f"_{self.time_of_day}" if day_night else ""
                base_filename = f"bg_{name}{suffix}"

                high_path = os.path.join(module.folder_path, "backgrounds", f"{base_filename}_high.png")
                normal_path = os.path.join(module.folder_path, "backgrounds", f"{base_filename}.png")

                if game_globals.background_high_res and os.path.exists(resolve_path(high_path)):
                    path = high_path
                else:
                    path = normal_path

        # Avoid reloading if already loaded
        if path == self.last_image_path:
            return

        try:
            # Use the new sprite loading method to cover the screen, keeping proportions
            # Use "Fill" method for both landscape and portrait devices
            if runtime_globals.SCREEN_WIDTH >= runtime_globals.SCREEN_HEIGHT:
                self.image = sprite_load_percent(path, percent=100, keep_proportion=True, base_on="width", alpha=False)
            else:
                self.image = sprite_load_percent(path, percent=100, keep_proportion=True, base_on="height", alpha=False)
            self.last_background = game_globals.game_background
            self.last_module = game_globals.background_module_name
            self.last_image_path = path
            self.center = self.image.get_rect(center=(runtime_globals.SCREEN_WIDTH // 2, runtime_globals.SCREEN_HEIGHT // 2))
        except Exception:
            runtime_globals.game_console.log(f"[!] Error loading background: {path}")
            self.image = None

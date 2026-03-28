import pygame
from ui.ui_constants import TEXT_FONT
import core.constants as constants
import core.runtime_globals as runtime_globals
from utils.asset_utils import font_load
from utils.pygame_utils import blit_with_shadow, get_font


class GameMessage:
    def __init__(self):
        self.messages = []  # Floating messages: [surface, [x, y], alpha, dy]
        self.slide_queue = []  # List of (text, color, y, font_size)
        self.current_slide = None  # Current sliding message data
        self.slide_timer = 0
        self.slide_duration = constants.FRAME_RATE * 2  # 2 seconds at 30fps
        self.slide_speed = 6 * (30 / constants.FRAME_RATE)  # Pixels per frame

    def add(self, text: str, pos: tuple[int, int], color: tuple[int, int, int], font_size=None):
        font = font_load(TEXT_FONT, font_size)
        surface = font.render(text, True, color).convert_alpha()
        self.messages.append([surface, list(pos), 255, 0])

    def add_slide(self, text: str, color: tuple[int, int, int], y: int, font_size=None):
        if font_size is None:
            font_size = runtime_globals.FONT_SIZE_MEDIUM_LARGE
        self.slide_queue.append((text, color, y, font_size))

    def update(self):
        if not self.messages and not self.current_slide and not self.slide_queue:
            return

        # === Floating Messages ===
        updated_messages = []
        for surf, pos, alpha, dy in self.messages:
            dy += 0.5 * (30 / constants.FRAME_RATE)
            alpha -= 5 * (30 / constants.FRAME_RATE)
            if alpha > 0:
                surf.set_alpha(alpha)
                updated_messages.append([surf, [pos[0], pos[1] - dy], alpha, dy])
        self.messages = updated_messages

        # === Slide Messages ===
        if self.current_slide:
            surf, pos, alpha = self.current_slide
            if pos[0] > (runtime_globals.SCREEN_WIDTH - surf.get_width()) // 2:
                pos[0] -= self.slide_speed
            else:
                self.slide_timer += 1
                if self.slide_timer > self.slide_duration:
                    alpha -= 10
                    if alpha <= 0:
                        self.current_slide = None
                        self.slide_timer = 0
                        return
            surf.set_alpha(alpha)
            self.current_slide = (surf, pos, alpha)
        elif self.slide_queue:
            text, color, y, font_size = self.slide_queue.pop(0)
            font = get_font(font_size)
            surf = font.render(text, True, color).convert_alpha()
            start_x = runtime_globals.SCREEN_WIDTH  # Start off-screen
            surf.set_alpha(255)
            self.current_slide = (surf, [start_x, y], 255)
            self.slide_timer = 0

    def draw(self, surface: pygame.Surface):
        # Floating messages
        for surf, pos, _, _ in self.messages:
            blit_with_shadow(surface, surf, pos)

        # Slide message
        if self.current_slide:
            surf, pos, _ = self.current_slide
            blit_with_shadow(surface, surf, pos)

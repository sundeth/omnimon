"""
SpecialsView - Specials menu (password redemption and future extras)
Opened from the battle main menu's SPECIALS button.
"""
import pygame
from ui.ui_manager import UIManager
from ui.components.title_scene import TitleScene
from ui.components.button import Button
from ui.components.background import Background
from ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals


class SpecialsView:
    """Specials menu view with Password and Back buttons."""

    def __init__(self, ui_manager: UIManager, change_view_callback):
        self.ui_manager = ui_manager
        self.change_view = change_view_callback

        self.background = None
        self.title_scene = None
        self.password_button = None
        self.back_button = None

        self._setup_ui()

    def _setup_ui(self):
        ui_width = ui_height = BASE_RESOLUTION

        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)

        self.title_scene = TitleScene(0, 9, "SPECIALS")
        self.ui_manager.add_component(self.title_scene)

        button_width = 120
        button_height = 40
        button_x = (ui_width - button_width) // 2

        self.password_button = Button(
            button_x, 70, button_width, button_height,
            "PASSWORD", self._on_password,
            icon_name="Shiny", icon_prefix="Status"
        )
        self.ui_manager.add_component(self.password_button)

        self.back_button = Button(
            button_x, 130, button_width, button_height,
            "BACK", self._on_back
        )
        self.ui_manager.add_component(self.back_button)

        self.ui_manager.set_focused_component(self.password_button)
        runtime_globals.game_console.log("[SpecialsView] UI setup complete")

    def _on_password(self):
        runtime_globals.game_sound.play("menu")
        self.change_view("password")

    def _on_back(self):
        runtime_globals.game_sound.play("cancel")
        self.change_view("main_menu")

    def cleanup(self):
        for comp in (self.background, self.title_scene, self.password_button, self.back_button):
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)

    def update(self):
        pass

    def draw(self, surface: pygame.Surface):
        pass

    def handle_event(self, event):
        if not isinstance(event, tuple) or len(event) != 2:
            return
        event_type, _ = event
        if event_type == "B":
            self._on_back()
            return True

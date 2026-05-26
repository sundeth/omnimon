"""
ArenaTeamCreationView - Pick up to 3 pets and create an arena team.

Mirrors the look of the battle scene's VersusView / JogressView pet
pickers: a PetSelector at the bottom (focusable, scrollable), three slot
boxes at the top showing the currently selected pets, and Back / Confirm
buttons.

Selected pets are validated against the active season's restrictions
(allowed_stages / allowed_attributes / allowed_modules); pets that
violate the rules are disabled in the selector so the player can only
build a legal team.
"""
import threading

import pygame

from ui.ui_manager import UIManager
from ui.components.title_scene import TitleScene
from ui.components.button import Button
from ui.components.background import Background
from ui.components.label import Label
from ui.components.pet_selector import PetSelector
from ui.components.team_display import TeamDisplay
from ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals, game_globals
from services.omninet_service import omninet_service


# Arena teams are always exactly 3 pets (matching the season server rules)
MAX_TEAM_SIZE = 3
REQUIRED_TEAM_SIZE = 3


def _pet_passes(pet, restrictions: dict) -> tuple[bool, str]:
    """Return ``(ok, reason)`` for whether *pet* may join an arena team.

    Combined check covers two things:
        * Universal arena eligibility — ``power > 0`` (so dead / starter
          pets are filtered) and ``edited == False`` (edited / modded
          pets aren't allowed regardless of season rules).
        * Season restrictions when the active season has them
          (``allowed_stages`` / ``allowed_attributes`` /
          ``allowed_modules``).  Mirrors ``Season.is_pet_allowed`` on the
          server so the client doesn't waste a network round-trip on a
          team it knows the server will reject.

    Returns ``True, ""`` if the pet is eligible, or ``False, reason``
    with a short human-readable reason ready for the status label.
    """
    # Universal arena gates first — apply regardless of season rules
    if getattr(pet, 'edited', False):
        return False, "Edited pets aren't allowed"
    if int(getattr(pet, 'power', 0) or 0) <= 0:
        return False, "Pet has no power"

    if not restrictions:
        return True, ""
    stages = restrictions.get('allowed_stages')
    if stages and getattr(pet, 'stage', None) not in stages:
        return False, "Wrong stage for this season"
    attributes = restrictions.get('allowed_attributes')
    if attributes and getattr(pet, 'attribute', None) not in attributes:
        return False, "Wrong attribute for this season"
    modules = restrictions.get('allowed_modules')
    if modules and getattr(pet, 'module', None) not in modules:
        return False, "Wrong module for this season"
    return True, ""


def _pet_to_server_dict(pet) -> dict:
    """Serialize a GamePet into the dict the /teams endpoint expects."""
    def _safe(attr, default=None):
        return getattr(pet, attr, default)

    return {
        'name': _safe('name', 'Unknown'),
        'module_name': _safe('module', 'Unknown'),
        'module_version': _safe('module_version', '1.0'),
        'pet_version': _safe('version', 1),
        'stage': _safe('stage', 0),
        'level': _safe('level', 1),
        'atk_main': _safe('atk_main', 0),
        'atk_alt': _safe('atk_alt', 0),
        'atk_alt2': _safe('atk_alt2', 0),
        'power': _safe('power', 0),
        'attribute': _safe('attribute', ''),
        'hp': _safe('hp', 0),
        'star': _safe('star', 0),
        'critical_turn': _safe('critical_turn', 0),
        'extra_data': _safe('extra_data', {}),
    }


class ArenaTeamCreationView:
    """Choose 1-3 pets, validate against season rules, send to /teams."""

    def __init__(self, ui_manager: UIManager, change_view_callback,
                 discord_module=None, season: dict | None = None):
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self._season = season or {}
        self._restrictions = (self._season or {}).get('restrictions') or {}

        self._components = []
        self._selected_pet_indices = []  # ordered list of indices into pet_list
        self._submitting = False

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _add(self, comp):
        self.ui_manager.add_component(comp)
        self._components.append(comp)
        return comp

    def _setup_ui(self):
        """Layout mirrors scene_battle's VersusView: team display at top,
        BACK / CONFIRM beneath it, PetSelector along the bottom of the
        screen.  The display uses three hexagonal slots instead of two.
        """
        ui_width = ui_height = BASE_RESOLUTION
        cut = {'tl': True, 'tr': False, 'bl': False, 'br': True}

        # Black fill backdrop
        bg = Background(ui_width, ui_height)
        bg.set_regions([(0, ui_height, "black")])
        self._add(bg)
        self._add(TitleScene(0, 9, "TEAM"))

        # Team display — same position/size as VersusView's VersusDisplay
        display_width = 200
        display_height = 80
        display_x = (ui_width - display_width) // 2
        display_y = 40
        self.team_display = self._add(TeamDisplay(
            display_x, display_y, display_width, display_height))

        # Buttons — directly under the display, centered, sizes match versus
        back_button_width = 60
        confirm_button_width = 80
        button_height = 25
        button_spacing = 5
        total_button_width = (
            back_button_width + confirm_button_width + button_spacing
        )
        buttons_start_x = (ui_width - total_button_width) // 2
        buttons_y = display_y + display_height + 10

        self.back_button = self._add(Button(
            buttons_start_x, buttons_y, back_button_width, button_height,
            "BACK", self._on_back, cut_corners=cut))
        confirm_x = buttons_start_x + back_button_width + button_spacing
        self.confirm_button = self._add(Button(
            confirm_x, buttons_y, confirm_button_width, button_height,
            "CONFIRM", self._on_confirm, cut_corners=cut, enabled=False))

        # Status / info line just under the buttons
        self.status_label = self._add(Label(
            ui_width // 2, buttons_y + button_height + 6,
            self._rules_summary(),
            color_override=(180, 180, 180), center=True,
            word_wrap=True, max_width=ui_width - 20))

        # Pet selector — same position math as VersusView
        selector_y = buttons_y + button_height + 18
        selector_height = ui_height - selector_y - 6
        self.pet_selector = self._add(PetSelector(
            10, selector_y, ui_width - 20, selector_height))
        self.pet_selector.set_pets(list(getattr(game_globals, 'pet_list', [])))
        self.pet_selector.set_interactive(True)
        self.pet_selector.activation_callback = self._on_pet_activate

        # Disable pets that fail eligibility (universal arena gates +
        # season-specific filters).  Reasons are stashed per index so the
        # status label can explain why a tap was rejected.
        self._reject_reasons = {}
        eligible = []
        for i, pet in enumerate(self.pet_selector.pets):
            ok, reason = _pet_passes(pet, self._restrictions)
            if ok:
                eligible.append(i)
            else:
                self._reject_reasons[i] = reason
        self.pet_selector.enabled_pets = eligible

        self.ui_manager.set_focused_component(self.pet_selector)
        if eligible:
            self.pet_selector.focused_cell = eligible[0]

    def _rules_summary(self) -> str:
        if not self._restrictions:
            return f"Pick exactly {REQUIRED_TEAM_SIZE} pets."
        parts = []
        if self._restrictions.get('allowed_stages'):
            parts.append("stage")
        if self._restrictions.get('allowed_attributes'):
            parts.append("attr")
        if self._restrictions.get('allowed_modules'):
            parts.append("module")
        return ("Season filter: " + " / ".join(parts)
                + f". Pick exactly {REQUIRED_TEAM_SIZE}.")

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_pet_activate(self):
        pet_index = self.pet_selector.get_activation_cell()
        if pet_index < 0 or pet_index >= len(self.pet_selector.pets):
            return False
        if pet_index not in self.pet_selector.enabled_pets:
            reason = self._reject_reasons.get(pet_index, "Pet not eligible")
            self.status_label.set_text(reason)
            runtime_globals.game_sound.play("cancel")
            return False
        self._toggle_pet(pet_index)
        return True

    def _toggle_pet(self, pet_index: int):
        if pet_index in self._selected_pet_indices:
            self._selected_pet_indices.remove(pet_index)
            runtime_globals.game_sound.play("cancel")
        else:
            if len(self._selected_pet_indices) >= MAX_TEAM_SIZE:
                self.status_label.set_text(f"Team is full (max {MAX_TEAM_SIZE})")
                runtime_globals.game_sound.play("cancel")
                return
            self._selected_pet_indices.append(pet_index)
            runtime_globals.game_sound.play("menu")
        self._refresh_team_display()
        # Mirror selection back onto the PetSelector so its visual highlight
        # reflects the team membership.
        self.pet_selector.selected_pets = list(self._selected_pet_indices)
        self.pet_selector.needs_redraw = True
        # Confirm only enables on a full team (matches server requirement)
        self.confirm_button.set_enabled(
            len(self._selected_pet_indices) == REQUIRED_TEAM_SIZE)
        self.status_label.set_text(self._rules_summary())

    def _refresh_team_display(self):
        """Push the current selection onto the hexagonal team display."""
        if not self.team_display:
            return
        pets = [self.pet_selector.pets[i] for i in self._selected_pet_indices]
        self.team_display.set_pets(pets)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_confirm(self):
        if self._submitting:
            return
        if len(self._selected_pet_indices) != REQUIRED_TEAM_SIZE:
            runtime_globals.game_sound.play("cancel")
            self.status_label.set_text(
                f"Pick exactly {REQUIRED_TEAM_SIZE} pets to continue.")
            return

        runtime_globals.game_sound.play("menu")
        self._submitting = True
        self.confirm_button.set_enabled(False)
        self.back_button.set_enabled(False)
        self.status_label.set_text("Creating team...")

        pets = [
            _pet_to_server_dict(self.pet_selector.pets[i])
            for i in self._selected_pet_indices
        ]

        def _worker():
            try:
                ok, data = omninet_service.create_team(pets, team_name=None)
            except Exception as exc:
                ok, data = False, str(exc)
            if ok:
                # Mirror onto the local arena-pets bench so other systems
                # treat the chosen pets as "frozen for the season".
                try:
                    chosen = [self.pet_selector.pets[i]
                              for i in self._selected_pet_indices]
                    game_globals.send_pets_to_arena(chosen)
                except Exception as exc:
                    runtime_globals.game_console.log(
                        f"[ArenaTeamCreation] arena bench update failed: {exc}")
                self.change_view("arena")
            else:
                msg = data if isinstance(data, str) else "Failed to create team"
                self.status_label.set_text(str(msg)[:48])
                self._submitting = False
                self.confirm_button.set_enabled(True)
                self.back_button.set_enabled(True)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_back(self):
        runtime_globals.game_sound.play("cancel")
        self.change_view("arena")

    # ------------------------------------------------------------------
    # Scene interface
    # ------------------------------------------------------------------

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

    def cleanup(self):
        for comp in self._components:
            if comp and comp in self.ui_manager.components:
                self.ui_manager.remove_component(comp)
        self._components.clear()
        runtime_globals.game_console.log("[ArenaTeamCreationView] Cleanup complete")

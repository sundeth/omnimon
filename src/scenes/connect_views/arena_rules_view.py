"""
ArenaRulesView - Display the current arena season's rules.

Shows the season's start/end dates and any restrictions that constrain
which pets can join: allowed stages, attributes, or modules.  The
underlying restriction keys mirror Season.is_pet_allowed on the server:

    {
        "allowed_stages":    [3, 4, 5],
        "allowed_attributes":["Vaccine", "Data"],
        "allowed_modules":   ["DMX", "DM20"],
    }
"""
from datetime import date as _date, datetime as _datetime

from ui.ui_manager import UIManager
from ui.components.title_scene import TitleScene
from ui.components.button import Button
from ui.components.background import Background
from ui.components.label import Label
from ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals


_MONTH_ABBR = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]


def _parse_iso_date(value: str):
    """Parse an ISO date or datetime string into a date object; None on failure."""
    if not value:
        return None
    try:
        if "T" in value:
            return _datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return _date.fromisoformat(value)
    except Exception:
        return None


def _format_week_label(value: str) -> str:
    """Format a season date as e.g. ``MAY WEEK 1`` (no year, 3-letter month).

    Falls back to the raw string if the date can't be parsed.
    """
    d = _parse_iso_date(value)
    if not d:
        return value or "?"
    month = _MONTH_ABBR[d.month - 1]
    # 1-indexed week-of-month: day 1-7 = WEEK 1, 8-14 = WEEK 2, etc.
    week = ((d.day - 1) // 7) + 1
    return f"{month} WEEK {week}"


def _format_season_name(season: dict) -> str:
    """Display-friendly season name.

    The server auto-generates names like ``"Week of May 10, 2026"`` which
    overflow the 240px-wide title.  Prefer a derived ``MAY WEEK 1`` label
    based on the season's start date when available; otherwise try to
    parse the server name; if all else fails just return the raw name.
    """
    import re

    start = season.get('start_date') if season else None
    if start:
        derived = _format_week_label(start)
        if derived and derived != "?":
            return derived

    raw = (season.get('name', 'No season') if season else 'No season') or ''
    # Match patterns like "Week of May 10, 2026"
    m = re.match(
        r"\s*Week\s+of\s+([A-Za-z]+)\s+(\d{1,2})(?:\s*,\s*\d{4})?\s*$",
        raw, re.IGNORECASE,
    )
    if m:
        month_name = m.group(1).upper()[:3]
        day = int(m.group(2))
        week = ((day - 1) // 7) + 1
        return f"{month_name} WEEK {week}"
    return raw


class ArenaRulesView:
    """Read-only view of the current season's rules."""

    def __init__(self, ui_manager: UIManager, change_view_callback,
                 discord_module=None, season: dict | None = None):
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        self._season = season or {}
        self._components = []
        self._build_ui()

    # ------------------------------------------------------------------

    def _add(self, comp):
        self.ui_manager.add_component(comp)
        self._components.append(comp)
        return comp

    def _build_ui(self):
        w = h = BASE_RESOLUTION

        bg = Background(w, h)
        bg.set_regions([(0, h, "black")])
        self._add(bg)
        self._add(TitleScene(0, 9, "RULES"))

        season_name = _format_season_name(self._season)
        self._add(Label(
            w // 2, 32, season_name, is_title=True,
            color_override=(255, 255, 255), center=True,
            word_wrap=True, max_width=w - 20))

        # Start / End dates — short month + week-of-month, no year, to
        # fit comfortably in the 240px-wide layout.
        start = _format_week_label(self._season.get('start_date', ''))
        end = _format_week_label(self._season.get('end_date', ''))
        self._add(Label(
            10, 55, f"START: {start}", color_override=(200, 200, 200)))
        self._add(Label(
            10, 68, f"END:   {end}", color_override=(200, 200, 200)))

        # Restrictions block
        restrictions = self._season.get('restrictions') or {}
        y = 90
        if not restrictions:
            self._add(Label(
                w // 2, y, "No restrictions - all pets eligible",
                color_override=(180, 220, 180), center=True,
                word_wrap=True, max_width=w - 20))
        else:
            rule_specs = [
                ("Stage",     restrictions.get('allowed_stages')),
                ("Attribute", restrictions.get('allowed_attributes')),
                ("Module",    restrictions.get('allowed_modules')),
            ]
            shown_any = False
            for label, values in rule_specs:
                if not values:
                    continue
                shown_any = True
                value_str = ", ".join(str(v) for v in values)
                self._add(Label(
                    10, y, f"{label}:", color_override=(255, 215, 80)))
                self._add(Label(
                    10, y + 12, value_str, color_override=(220, 220, 220),
                    word_wrap=True, max_width=w - 20))
                y += 32
            if not shown_any:
                self._add(Label(
                    w // 2, y, "No restrictions - all pets eligible",
                    color_override=(180, 220, 180), center=True,
                    word_wrap=True, max_width=w - 20))

        # Back button — same cut-corner style as the arena view's footer
        btn_w, btn_h = 80, 24
        self._add(Button(
            (w - btn_w) // 2, h - btn_h - 10, btn_w, btn_h, "BACK",
            self._on_back,
            cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}))

    # ------------------------------------------------------------------

    def _on_back(self):
        runtime_globals.game_sound.play("cancel")
        self.change_view("arena")

    # ------------------------------------------------------------------
    # Scene interface
    # ------------------------------------------------------------------

    def update(self):
        pass

    def draw(self, surface):
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
        runtime_globals.game_console.log("[ArenaRulesView] Cleanup complete")

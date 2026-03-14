"""
Scene Login
============

Handles the full Omninet authentication flow for Progress Mode:

Phases:
    menu              → Choose: Create Account, Login, Link Device, Back
    create_account    → nickname + email + password + confirm password
    login             → email + password
    verify            → 6-character code entry (for both register and login)
    link_device       → 4-character pairing code from Module Editor
    loading           → Spinner while async operations run
    complete          → Set player_id, migrate saves, load, route onward

After successful authentication the device key is stored automatically
by OmninetService, and the player_id is synchronised into game_globals
so the correct save directory is used.

Entry points:
    - SceneSetup._on_game_mode_selected() → Progress Mode selected
    - MainMenuView._on_omninet_connect()  → Connect in Progress Mode

Uses the standard UI system (UIManager, Button, Label, TextInput, etc.).
"""

import os
import threading
import pygame

from components.ui.ui_manager import UIManager
from components.ui.background import Background
from components.ui.title_scene import TitleScene
from components.ui.button import Button
from components.ui.label import Label
from components.ui.text_input import TextInput
from components.ui.code_entry import CodeEntry
from components.ui.ui_constants import BASE_RESOLUTION
from components.window_background import WindowBackground
from core import game_globals, runtime_globals
from core.utils.scene_utils import change_scene
from core.utils import navigation_utils
from core.service.omninet_service import omninet_service


class SceneLogin:
    """
    Full-screen login scene for Omninet authentication.

    Supports account creation (with email verification), password login
    (with 2FA code), and device linking via pairing code.
    """

    def __init__(self) -> None:
        runtime_globals.game_console.log("[SceneLogin] Initializing")

        self.window_background = WindowBackground(True)
        self.ui_manager = UIManager("GREEN")
        self.ui_manager.show_external_border = False
        self.ui_manager.set_input_manager(runtime_globals.game_input)

        # Phase state
        self.phase = "menu"

        # Temporary data stored across phases
        self._email = ""
        self._nickname = ""
        self._verify_action = None  # "register" or "login"
        self._loading = False
        self._error_text = ""

        # Component references (set per-phase)
        self._components = []  # Track components for cleanup

        # Whether this scene was entered from connect (vs. from setup)
        self._from_connect = (runtime_globals.game_state == "connect"
                              or runtime_globals.game_state == "login")

        self._build_menu()

    # =====================================================================
    # Phase builders — each one clears the UI and builds a fresh layout
    # =====================================================================

    def _clear_ui(self):
        """Remove all tracked components and reset the UI manager."""
        self.ui_manager.components.clear()
        self.ui_manager.focusable_components.clear()
        self.ui_manager.focused_index = 0
        self._components.clear()
        self._error_text = ""

    def _add(self, comp):
        """Add a component to both the UI manager and the tracking list."""
        self.ui_manager.add_component(comp)
        self._components.append(comp)
        return comp

    # ── Menu phase ────────────────────────────────────────────────────

    def _build_menu(self):
        """Build the main menu: Create Account / Login / Link Device / Back."""
        self._clear_ui()
        self.phase = "menu"

        w = h = BASE_RESOLUTION

        bg = Background(w, h)
        bg.set_regions([(0, h, "black")])
        self._add(bg)

        self._add(TitleScene(0, 9, "LOGIN"))

        self._add(Label(120, 45, "OMNINET ACCOUNT", is_title=True,
                        color_override=(255, 255, 255), center=True))

        btn_w = 180
        btn_h = 28
        btn_x = (w - btn_w) // 2
        gap = 8

        y = 80
        self._add(Button(btn_x, y, btn_w, btn_h, "Create Account",
                         self._go_create_account))
        y += btn_h + gap
        self._add(Button(btn_x, y, btn_w, btn_h, "Login",
                         self._go_login))
        y += btn_h + gap
        self._add(Button(btn_x, y, btn_w, btn_h, "Link Device",
                         self._go_link_device))
        y += btn_h + gap + 8
        self._add(Button(btn_x, y, btn_w, btn_h, "Back",
                         self._go_back))

        runtime_globals.game_console.log("[SceneLogin] Menu built")

    # ── Create Account phase ──────────────────────────────────────────

    def _go_create_account(self):
        runtime_globals.game_sound.play("menu")
        self._build_create_account()

    def _build_create_account(self):
        """Build the account creation form."""
        self._clear_ui()
        self.phase = "create_account"

        w = h = BASE_RESOLUTION
        bg = Background(w, h)
        bg.set_regions([(0, h, "black")])
        self._add(bg)

        self._add(TitleScene(0, 9, "LOGIN"))
        self._add(Label(120, 45, "CREATE ACCOUNT", is_title=True,
                        color_override=(255, 255, 255), center=True))

        field_w = 200
        field_x = (w - field_w) // 2
        y = 62

        self._add(Label(field_x, y, "Nickname", color_override=(180, 180, 180)))
        y += 10
        self.inp_nickname = self._add(TextInput(
            field_x, y, field_w, placeholder="Your name", max_length=100,
            keyboard_type="default"))
        y += self._field_height() + 2

        self._add(Label(field_x, y, "Email", color_override=(180, 180, 180)))
        y += 10
        self.inp_email = self._add(TextInput(
            field_x, y, field_w, placeholder="email@example.com", max_length=255,
            keyboard_type="email"))
        y += self._field_height() + 2

        self._add(Label(field_x, y, "Password", color_override=(180, 180, 180)))
        y += 10
        self.inp_password = self._add(TextInput(
            field_x, y, field_w, placeholder="Min 6 characters", max_length=100,
            keyboard_type="default", is_password=True))
        y += self._field_height() + 2

        # Error label
        self.error_label = self._add(Label(
            120, y, "", color_override=(255, 80, 80), center=True,
            word_wrap=True, max_width=200))

        # Buttons at bottom
        btn_w = 80
        btn_h = 20
        gap = 16
        btn_y = h - btn_h - 8
        self._add(Button((w // 2) - btn_w - (gap // 2), btn_y, btn_w, btn_h,
                         "Create", self._on_create_account_submit))
        self._add(Button((w // 2) + (gap // 2), btn_y, btn_w, btn_h,
                         "Cancel", self._on_cancel))

        self.ui_manager.set_focused_component(self.inp_nickname)
        runtime_globals.game_console.log("[SceneLogin] Create Account form built")

    def _on_create_account_submit(self):
        """Validate fields and call register endpoint."""
        nickname = self.inp_nickname.get_text().strip()
        email = self.inp_email.get_text().strip()
        password = self.inp_password.get_text()

        # Client-side validation
        if len(nickname) < 3:
            self._show_error("Nickname must be 3+ characters")
            return
        if "@" not in email or "." not in email:
            self._show_error("Enter a valid email address")
            return
        if len(password) < 6:
            self._show_error("Password must be 6+ characters")
            return

        self._email = email
        self._nickname = nickname
        self._verify_action = "register"
        self._async_call(
            lambda: omninet_service.register(nickname, email, password),
            self._on_register_response,
        )

    def _on_register_response(self, result):
        success, message = result
        if success:
            runtime_globals.game_console.log("[SceneLogin] Registration sent, show verify")
            self._build_verify()
        else:
            self._show_error(message[:40])

    # ── Login phase ───────────────────────────────────────────────────

    def _go_login(self):
        runtime_globals.game_sound.play("menu")
        self._build_login()

    def _build_login(self):
        """Build the login form."""
        self._clear_ui()
        self.phase = "login"

        w = h = BASE_RESOLUTION
        bg = Background(w, h)
        bg.set_regions([(0, h, "black")])
        self._add(bg)

        self._add(TitleScene(0, 9, "LOGIN"))
        self._add(Label(120, 45, "LOGIN", is_title=True,
                        color_override=(255, 255, 255), center=True))

        field_w = 200
        field_x = (w - field_w) // 2
        y = 72

        self._add(Label(field_x, y, "Email", color_override=(180, 180, 180)))
        y += 10
        self.inp_email = self._add(TextInput(
            field_x, y, field_w, placeholder="email@example.com", max_length=255,
            keyboard_type="email"))
        y += self._field_height() + 4

        self._add(Label(field_x, y, "Password", color_override=(180, 180, 180)))
        y += 10
        self.inp_password = self._add(TextInput(
            field_x, y, field_w, placeholder="Password", max_length=100,
            keyboard_type="default", is_password=True))
        y += self._field_height() + 4

        # Error label
        self.error_label = self._add(Label(
            120, y, "", color_override=(255, 80, 80), center=True,
            word_wrap=True, max_width=200))

        # Buttons
        btn_w = 80
        btn_h = 20
        gap = 16
        btn_y = h - btn_h - 8
        self._add(Button((w // 2) - btn_w - (gap // 2), btn_y, btn_w, btn_h,
                         "Login", self._on_login_submit))
        self._add(Button((w // 2) + (gap // 2), btn_y, btn_w, btn_h,
                         "Cancel", self._on_cancel))

        self.ui_manager.set_focused_component(self.inp_email)
        runtime_globals.game_console.log("[SceneLogin] Login form built")

    def _on_login_submit(self):
        """Validate and send login request."""
        email = self.inp_email.get_text().strip()
        password = self.inp_password.get_text()

        if "@" not in email or "." not in email:
            self._show_error("Enter a valid email address")
            return
        if not password:
            self._show_error("Enter your password")
            return

        self._email = email
        self._verify_action = "login"
        self._async_call(
            lambda: omninet_service.login_request(email, password),
            self._on_login_response,
        )

    def _on_login_response(self, result):
        success, message = result
        if success:
            runtime_globals.game_console.log("[SceneLogin] Login sent, show verify")
            self._build_verify()
        else:
            self._show_error(message[:40])

    # ── Verify phase (shared by register + login) ─────────────────────

    def _build_verify(self):
        """Build the 6-character code verification form."""
        self._clear_ui()
        self.phase = "verify"

        w = h = BASE_RESOLUTION
        bg = Background(w, h)
        bg.set_regions([(0, h, "black")])
        self._add(bg)

        self._add(TitleScene(0, 9, "LOGIN"))

        title = "VERIFY EMAIL" if self._verify_action == "register" else "VERIFY LOGIN"
        self._add(Label(120, 45, title, is_title=True,
                        color_override=(255, 255, 255), center=True))

        # Instruction
        truncated_email = self._email if len(self._email) <= 28 else self._email[:25] + "..."
        self._add(Label(120, 62, f"Code sent to:", color_override=(180, 180, 180),
                        center=True))
        self._add(Label(120, 72, truncated_email, color_override=(200, 200, 200),
                        center=True))

        # Code entry (6 characters) — reuse CodeEntry with length=6
        code_w = 6 * 30 + 5 * 8  # Approximate width
        self.code_entry = self._add(
            CodeEntry((w - code_w) // 2, 90, length=6))

        # Timer label
        self._verify_seconds = 5 * 60  # 5 minutes
        self.timer_label = self._add(Label(
            120, 150, self._format_timer(), color_override=(150, 150, 150),
            center=True))

        # Error label
        self.error_label = self._add(Label(
            120, 163, "", color_override=(255, 80, 80), center=True,
            word_wrap=True, max_width=200))

        # Buttons
        btn_w = 70
        btn_h = 20
        btn_y = h - btn_h - 8
        self._add(Button((w // 2) - btn_w * 3 // 2 - 8, btn_y, btn_w, btn_h,
                         "Resend", self._on_resend_code))
        self._add(Button((w // 2) - btn_w // 2, btn_y, btn_w, btn_h,
                         "Verify", self._on_verify_submit))
        self._add(Button((w // 2) + btn_w // 2 + 8, btn_y, btn_w, btn_h,
                         "Cancel", self._on_cancel))

        self.ui_manager.set_focused_component(self.code_entry)
        runtime_globals.game_console.log("[SceneLogin] Verify form built")

    def _format_timer(self):
        """Format remaining seconds as M:SS."""
        m = self._verify_seconds // 60
        s = self._verify_seconds % 60
        return f"Expires in {m}:{s:02d}"

    def _on_verify_submit(self):
        """Submit verification code."""
        code = self.code_entry.get_text()
        if len(code) != 6:
            self._show_error("Enter the 6-character code")
            return

        if self._verify_action == "register":
            self._async_call(
                lambda: omninet_service.verify_registration(self._email, code),
                self._on_verify_response,
            )
        else:
            self._async_call(
                lambda: omninet_service.verify_login(self._email, code),
                self._on_verify_response,
            )

    def _on_verify_response(self, result):
        success, message = result
        if success:
            runtime_globals.game_console.log("[SceneLogin] Verification successful")
            runtime_globals.game_sound.play("evolution")
            self._complete_login()
        else:
            self._show_error(message[:40])

    def _on_resend_code(self):
        """Resend verification code."""
        self._async_call(
            lambda: omninet_service.resend_code(self._email),
            self._on_resend_response,
        )

    def _on_resend_response(self, result):
        success, message = result
        if success:
            self._verify_seconds = 5 * 60
            self._show_error("")  # Clear error
            runtime_globals.game_sound.play("menu")
            runtime_globals.game_message.add_slide("Code resent!", (0, 231, 58), 90)
        else:
            self._show_error(message[:40])

    # ── Link Device phase ─────────────────────────────────────────────

    def _go_link_device(self):
        runtime_globals.game_sound.play("menu")
        self._build_link_device()

    def _build_link_device(self):
        """Build the 4-character pairing code form (same as OmninetLinkView)."""
        self._clear_ui()
        self.phase = "link_device"

        w = h = BASE_RESOLUTION
        bg = Background(w, h)
        bg.set_regions([(0, h, "black")])
        self._add(bg)

        self._add(TitleScene(0, 9, "LOGIN"))
        self._add(Label(120, 45, "LINK DEVICE", is_title=True,
                        color_override=(255, 255, 255), center=True))

        self._add(Label(120, 68, "Enter code from Module Editor",
                        color_override=(180, 180, 180), center=True))

        # Code entry (4 characters)
        self.code_entry = self._add(
            CodeEntry((w - 190) // 2, 90, length=4))

        # Status / error label
        self.error_label = self._add(Label(
            120, 155, "", color_override=(255, 80, 80), center=True,
            word_wrap=True, max_width=200))

        # Buttons
        btn_w = 80
        btn_h = 20
        gap = 16
        btn_y = h - btn_h - 8
        self._add(Button((w // 2) - btn_w - (gap // 2), btn_y, btn_w, btn_h,
                         "Confirm", self._on_link_submit))
        self._add(Button((w // 2) + (gap // 2), btn_y, btn_w, btn_h,
                         "Cancel", self._on_cancel))

        self.ui_manager.set_focused_component(self.code_entry)
        runtime_globals.game_console.log("[SceneLogin] Link Device form built")

    def _on_link_submit(self):
        """Validate pairing code."""
        code = self.code_entry.get_text()
        if len(code) != 4:
            self._show_error("Enter 4-character code")
            return

        self._async_call(
            lambda: omninet_service.validate_pairing_code(code),
            self._on_link_response,
        )

    def _on_link_response(self, result):
        success, message, user_info = result
        if success:
            username = user_info.get('nickname', 'User') if user_info else 'User'
            runtime_globals.game_console.log(f"[SceneLogin] Linked as: {username}")
            runtime_globals.game_sound.play("evolution")
            self._complete_login()
        else:
            self._show_error(message[:32])

    # ── Loading overlay ───────────────────────────────────────────────

    def _build_loading(self):
        """Show a simple loading indicator over current UI."""
        self._loading = True
        # Disable all buttons while loading
        for comp in self._components:
            if isinstance(comp, Button):
                comp.enabled = False
        self._show_error("Connecting...")

    def _end_loading(self):
        """Re-enable UI after async operation completes."""
        self._loading = False
        for comp in self._components:
            if isinstance(comp, Button):
                comp.enabled = True

    # ── Async helper ──────────────────────────────────────────────────

    def _async_call(self, func, on_complete):
        """Run *func* in a background thread, then call *on_complete(result)*
        on the next update cycle.

        Args:
            func:        Callable that returns a result (runs on bg thread).
            on_complete: Callable(result) invoked on the main thread.
        """
        self._build_loading()
        self._async_result = None
        self._async_callback = on_complete

        def _worker():
            try:
                result = func()
            except Exception as e:
                runtime_globals.game_console.log(f"[SceneLogin] Async error: {e}")
                result = (False, str(e))
            self._async_result = result

        threading.Thread(target=_worker, daemon=True).start()

    # ── Navigation helpers ────────────────────────────────────────────

    def _on_cancel(self):
        """Return to menu phase — or exit scene if already on menu."""
        runtime_globals.game_sound.play("cancel")
        if self.phase == "menu":
            self._go_back()
        else:
            self._build_menu()

    def _go_back(self):
        """Exit the login scene.

        If entering from setup (first-time), go back to setup.
        If entering from connect menu, go back to connect.
        """
        runtime_globals.game_sound.play("cancel")
        # If game mode preference hasn't been saved yet, go back to setup
        if not game_globals.has_game_mode_preference():
            change_scene("setup")
        else:
            change_scene("connect")
        runtime_globals.game_console.log("[SceneLogin] Back")

    def _complete_login(self):
        """Post-login finalisation: sync player_id, migrate saves, load, route.

        This is the critical path that bridges authentication to gameplay.
        After a successful register/login/link the OmninetService already
        holds the device key and player_id.
        """
        runtime_globals.game_console.log("[SceneLogin] Completing login")

        # 1. Sync player_id into game_globals
        player_id = omninet_service.get_player_id()
        if player_id:
            game_globals.set_player_id(player_id)
            runtime_globals.game_console.log(
                f"[SceneLogin] Player ID synced: {player_id[:8]}…")
        else:
            runtime_globals.game_console.log(
                "[SceneLogin] WARNING: No player_id from service!")

        # 2. Ensure the save directory exists (creates save/<player_id>/)
        save_dir = game_globals.get_save_dir()
        os.makedirs(save_dir, exist_ok=True)

        # 3. Migrate any legacy save data into the correct directory
        game_globals.migrate_legacy_saves()

        # 4. Load save data from the (now-correct) directory
        game_globals.load()

        # 5. If still in first-time setup, clear setup flags and save
        if game_globals.setup_input or game_globals.setup_graphics:
            game_globals.setup_input = False
            game_globals.setup_graphics = False
            game_globals.save()

        # 6. Route to next scene
        navigation_utils.route_to_next_scene(check_tutorial=True)
        runtime_globals.game_console.log("[SceneLogin] Login complete, routed to next scene")

    # ── Error display ─────────────────────────────────────────────────

    def _show_error(self, text):
        """Display an error/status message in the current phase."""
        self._error_text = text
        if hasattr(self, 'error_label') and self.error_label:
            self.error_label.set_text(text)
        if text and text != "Connecting...":
            runtime_globals.game_sound.play("error")
        self.ui_manager.master_ui_dirty = True

    # ── Field height helper ───────────────────────────────────────────

    def _field_height(self):
        """Return the base height of a TextInput (always compact)."""
        return TextInput.FIELD_HEIGHT

    # =====================================================================
    # Scene interface (update / draw / handle_event)
    # =====================================================================

    def update(self) -> None:
        """Called every frame."""
        self.ui_manager.update()

        # Process async result if available
        if hasattr(self, '_async_result') and self._async_result is not None:
            result = self._async_result
            callback = self._async_callback
            self._async_result = None
            self._async_callback = None
            self._end_loading()
            callback(result)

        # Verify phase countdown
        if self.phase == "verify" and hasattr(self, '_verify_seconds'):
            # Tick once per second (approximate via frame rate)
            if not hasattr(self, '_verify_frame_counter'):
                self._verify_frame_counter = 0
            self._verify_frame_counter += 1
            fps = getattr(game_globals.configuration, 'frame_rate', 30)
            if self._verify_frame_counter >= fps:
                self._verify_frame_counter = 0
                if self._verify_seconds > 0:
                    self._verify_seconds -= 1
                    if hasattr(self, 'timer_label') and self.timer_label:
                        self.timer_label.set_text(self._format_timer())

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the scene."""
        self.window_background.draw(surface)
        self.ui_manager.draw(surface)

        # Draw virtual-keyboard overlay for the focused TextInput (if any)
        if not runtime_globals.IS_ANDROID:
            idx = self.ui_manager.focused_index
            if 0 <= idx < len(self.ui_manager.focusable_components):
                focused = self.ui_manager.focusable_components[idx]
                if isinstance(focused, TextInput):
                    focused.draw_keyboard_overlay(surface)

    def handle_event(self, event) -> None:
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            # Forward raw pygame events to focused TextInput (Android TEXTINPUT)
            if isinstance(event, pygame.event.Event):
                idx = self.ui_manager.focused_index
                if 0 <= idx < len(self.ui_manager.focusable_components):
                    focused = self.ui_manager.focusable_components[idx]
                    if isinstance(focused, TextInput):
                        focused.handle_event(event)
            return

        event_type, event_data = event

        # Global shortcuts
        if event_type == "CANCEL" and self.phase != "menu":
            self._on_cancel()
            return

        if event_type == "MOUSE_MOTION":
            self.ui_manager.handle_event(event)
            return

        # Forward clicks to the virtual-keyboard overlay first
        if event_type == "LCLICK" and event_data and "pos" in event_data:
            if not runtime_globals.IS_ANDROID:
                idx = self.ui_manager.focused_index
                if 0 <= idx < len(self.ui_manager.focusable_components):
                    focused = self.ui_manager.focusable_components[idx]
                    if isinstance(focused, TextInput):
                        screen_sz = self.ui_manager.get_scaled_resolution()
                        if focused.handle_keyboard_click(
                                event_data["pos"], screen_sz):
                            return

        # Let UI manager handle (buttons, focus navigation, etc.)
        if self.ui_manager.handle_event(event):
            return

        # Phase-specific handling
        if self.phase == "verify" and event_type == "START":
            self._on_verify_submit()
            return

        if self.phase == "link_device" and event_type == "START":
            self._on_link_submit()
            return

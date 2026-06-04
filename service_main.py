"""
Omnipet Android Background Service
==================================

Runs as a python-for-android Service when the main app is in the background.

Responsibilities:
    * Load the same save file the foreground app uses.
    * Tick every active pet (and poop) once per minute, mirroring the
      per-minute gameplay tick in GamePet.update().
    * Persist progress periodically.
    * Emit Android notifications when a pet first becomes sick, first
      poops, or first triggers a care alarm. Each notification is
      debounced -- it won't fire again until the underlying state clears
      and re-triggers.

Lifecycle:
    Started by main_android.py via PythonService JNI when the app goes
    into background / quits. The main app writes a marker file
    (`service_active.flag`) at start; on resume the main app deletes it,
    and this service exits at its next tick check.

Headless safety:
    pygame is initialised against the SDL "dummy" video & audio drivers
    so `convert_alpha()` and `pygame.transform.scale` (used by some pet
    death / Burpmon code paths) keep working without a real display.
    Sound playback is replaced by a no-op stub so we never touch the
    audio device while the foreground app may be playing.
"""

import os
import sys
import time
import traceback


# ---------------------------------------------------------------------------
# Headless SDL setup -- MUST happen before any pygame or game-module import.
# ---------------------------------------------------------------------------
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "0")

# When p4a launches a service, the working directory is the app's private
# files dir (or the unpacked APK assets dir, depending on bootstrap). We
# resolve a sensible APP_ROOT and put `src/` on sys.path the same way
# main_android.py does.
APP_ROOT = os.environ.get("ANDROID_APP_PATH") \
    or os.environ.get("PYTHON_SERVICE_ARGUMENT") \
    or os.getcwd()

if APP_ROOT and not os.path.isdir(APP_ROOT):
    APP_ROOT = os.getcwd()

# Try several candidates for src/ — on some devices cwd differs from the
# APK extraction dir.  __file__ points to the .pyc in the extraction dir,
# so dirname(__file__) is the most reliable root when available.
_HERE_svc = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
_src_candidates = [
    os.path.join(_HERE_svc, "src"),
    os.path.join(os.path.dirname(_HERE_svc), "src"),
    os.path.join(APP_ROOT, "src"),
]
for _sp in sys.path[:4]:
    if _sp and _sp not in ('.', ''):
        _src_candidates.append(_sp)
        _src_candidates.append(os.path.join(os.path.dirname(_sp), "src"))
for _sc in _src_candidates:
    if os.path.isdir(_sc) and os.path.isdir(os.path.join(_sc, "core")) and _sc not in sys.path:
        sys.path.insert(0, _sc)
        APP_ROOT = os.path.dirname(_sc)
        break
del _src_candidates, _HERE_svc

SRC_DIR = os.path.join(APP_ROOT, "src")

# Same Bluestacks cwd≠extraction-dir fix as main_android.py: manually load
# sitecustomize.pyc so p4a's .pyc import hook is installed before game imports.
if 'sitecustomize' not in sys.modules:
    import importlib.machinery as _imm
    import importlib.util as _ilu
    _sc_candidates = []
    for _sp in sys.path[:6]:
        if _sp and _sp not in ('.', ''):
            _sc_candidates.append(os.path.join(_sp, 'sitecustomize.pyc'))
            _sc_candidates.append(os.path.join(os.path.dirname(_sp), 'sitecustomize.pyc'))
    _sc_candidates.append(os.path.join(os.getcwd(), 'sitecustomize.pyc'))
    for _sc_path in _sc_candidates:
        try:
            if os.path.exists(_sc_path):
                _loader = _imm.SourcelessFileLoader('sitecustomize', _sc_path)
                _spec = _ilu.spec_from_loader('sitecustomize', _loader)
                _mod = _ilu.module_from_spec(_spec)
                sys.modules['sitecustomize'] = _mod
                _spec.loader.exec_module(_mod)
                print(f"[Service] sitecustomize loaded from {_sc_path}")
                break
        except Exception as _sc_exc:
            print(f"[Service] sitecustomize load failed ({_sc_path}): {_sc_exc}")
    del _imm, _ilu, _sc_candidates

# Same direct .pyc import hook as main_android.py.
class _PyonlyFinder:
    def find_spec(self, fullname, path, target=None):
        import importlib.machinery as _m
        import importlib.util as _u
        name = fullname.rpartition('.')[2]
        for entry in (path if path is not None else sys.path):
            try:
                pkg_dir = os.path.join(entry, name)
                init_pyc = os.path.join(pkg_dir, '__init__.pyc')
                if os.path.isfile(init_pyc):
                    loader = _m.SourcelessFileLoader(fullname, init_pyc)
                    spec = _u.spec_from_loader(fullname, loader, is_package=True)
                    if spec is not None:
                        spec.submodule_search_locations = [pkg_dir]
                    return spec
                mod_pyc = os.path.join(entry, name + '.pyc')
                if os.path.isfile(mod_pyc):
                    loader = _m.SourcelessFileLoader(fullname, mod_pyc)
                    return _u.spec_from_loader(fullname, loader)
            except Exception:
                continue
        return None

if not any(type(f).__name__ == '_PyonlyFinder' for f in sys.meta_path):
    sys.meta_path.append(_PyonlyFinder())
    print(f"[Service] _PyonlyFinder installed, cwd={os.getcwd()}, "
          f"src_dir_exists={os.path.isdir(SRC_DIR)}")

import pygame  # noqa: E402  -- import after env vars are set


def _init_headless_pygame():
    """Initialise pygame against the dummy drivers and create a 1x1 surface.

    A display surface is required for `convert_alpha()` calls that some pet
    code paths perform (e.g. dead-pet sprite swap, Burpmon transformation).
    Without it, those calls raise pygame.error and would crash the tick loop.
    """
    try:
        pygame.display.init()
    except pygame.error as exc:
        print(f"[Service] pygame.display.init failed: {exc}")
    try:
        pygame.display.set_mode((1, 1))
    except pygame.error as exc:
        print(f"[Service] pygame.display.set_mode failed: {exc}")
    # Audio: try, but ignore failure -- service must not need a real device.
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    except pygame.error as exc:
        print(f"[Service] pygame.mixer.init skipped: {exc}")


# ---------------------------------------------------------------------------
# Stop-signal handling: the main app touches this file when it wants the
# service running, and removes it when it resumes. This lets the service
# self-terminate without needing a JNI round-trip from the foreground.
# ---------------------------------------------------------------------------
def _service_marker_path():
    """Return the absolute path to the service-active marker file.

    Stored in the app's private storage so it's accessible from both the
    main app process and the service process.
    """
    try:
        from android.storage import app_storage_path  # type: ignore
        return os.path.join(app_storage_path(), "service_active.flag")
    except Exception:
        # Desktop fallback -- mainly for local smoke testing.
        return os.path.join(os.getcwd(), "service_active.flag")


# ---------------------------------------------------------------------------
# Notification backend (pyjnius-based, with a print() fallback for desktop).
# ---------------------------------------------------------------------------
class AndroidNotifier:
    """Posts Android status-bar notifications via JNI.

    Each notification is keyed by a stable id so re-posting the same key
    updates (rather than stacks) the notification. State-change debouncing
    is handled by the caller (StateTracker.diff()).
    """

    NOTIFICATION_CHANNEL_ID = "omnipet_pets"
    NOTIFICATION_CHANNEL_NAME = "Omnipet Pet Alerts"

    def __init__(self):
        self.enabled = False
        self._next_id = 1000
        self._key_to_id = {}
        try:
            from jnius import autoclass  # type: ignore

            self.PythonService = autoclass("org.kivy.android.PythonService")
            self.NotificationBuilder = autoclass("android.app.Notification$Builder")
            self.NotificationManager = autoclass("android.app.NotificationManager")
            self.NotificationChannel = autoclass("android.app.NotificationChannel")
            self.Context = autoclass("android.content.Context")
            self.Intent = autoclass("android.content.Intent")
            self.PendingIntent = autoclass("android.app.PendingIntent")
            self.BuildVERSION = autoclass("android.os.Build$VERSION")
            self.String = autoclass("java.lang.String")

            self.service = self.PythonService.mService
            self._ensure_channel()
            self.enabled = True
            print("[Service][Notifier] Initialised JNI notification backend")
        except Exception as exc:
            print(f"[Service][Notifier] JNI unavailable, notifications disabled: {exc}")

    def _ensure_channel(self):
        """Create the notification channel on Android 8+ (no-op below that)."""
        if self.BuildVERSION.SDK_INT < 26:
            return
        nm = self.service.getSystemService(self.Context.NOTIFICATION_SERVICE)
        channel = self.NotificationChannel(
            self.NOTIFICATION_CHANNEL_ID,
            self.NOTIFICATION_CHANNEL_NAME,
            self.NotificationManager.IMPORTANCE_DEFAULT,
        )
        nm.createNotificationChannel(channel)

    def _id_for_key(self, key):
        if key not in self._key_to_id:
            self._key_to_id[key] = self._next_id
            self._next_id += 1
        return self._key_to_id[key]

    def notify(self, key, title, message):
        """Post (or update) a notification.

        Args:
            key:     A stable identifier (e.g. ``"sick:Agumon"``). Same key
                     replaces the previous notification for that pet/event.
            title:   Status-bar title (short).
            message: Body text.
        """
        if not self.enabled:
            print(f"[Service][Notify] {title}: {message}")
            return

        try:
            # Build a content intent that re-launches the app when tapped.
            launch_intent = self._build_launch_intent()
            content_intent = None
            if launch_intent is not None:
                flags = self.PendingIntent.FLAG_UPDATE_CURRENT
                if self.BuildVERSION.SDK_INT >= 23:
                    flags = flags | self.PendingIntent.FLAG_IMMUTABLE
                content_intent = self.PendingIntent.getActivity(
                    self.service, 0, launch_intent, flags
                )

            if self.BuildVERSION.SDK_INT >= 26:
                builder = self.NotificationBuilder(self.service, self.NOTIFICATION_CHANNEL_ID)
            else:
                builder = self.NotificationBuilder(self.service)

            builder.setContentTitle(self.String(title))
            builder.setContentText(self.String(message))
            builder.setSmallIcon(self.service.getApplicationInfo().icon)
            builder.setAutoCancel(True)
            if content_intent is not None:
                builder.setContentIntent(content_intent)

            notification = builder.build()
            nm = self.service.getSystemService(self.Context.NOTIFICATION_SERVICE)
            nm.notify(self._id_for_key(key), notification)
        except Exception as exc:
            print(f"[Service][Notifier] notify failed ({key}): {exc}")
            traceback.print_exc()

    def _build_launch_intent(self):
        try:
            pm = self.service.getPackageManager()
            intent = pm.getLaunchIntentForPackage(self.service.getPackageName())
            if intent is not None:
                intent.addFlags(self.Intent.FLAG_ACTIVITY_NEW_TASK)
            return intent
        except Exception:
            return None

    def show_foreground(self, title, message):
        """Promote the service to a foreground service with a sticky notification.

        Called once at start-up. The notification tells the user the service
        is running so the OS won't kill it for being idle.
        """
        if not self.enabled:
            return
        try:
            if self.BuildVERSION.SDK_INT >= 26:
                builder = self.NotificationBuilder(self.service, self.NOTIFICATION_CHANNEL_ID)
            else:
                builder = self.NotificationBuilder(self.service)
            builder.setContentTitle(self.String(title))
            builder.setContentText(self.String(message))
            builder.setSmallIcon(self.service.getApplicationInfo().icon)
            builder.setOngoing(True)
            launch_intent = self._build_launch_intent()
            if launch_intent is not None:
                flags = self.PendingIntent.FLAG_UPDATE_CURRENT
                if self.BuildVERSION.SDK_INT >= 23:
                    flags = flags | self.PendingIntent.FLAG_IMMUTABLE
                pi = self.PendingIntent.getActivity(self.service, 0, launch_intent, flags)
                builder.setContentIntent(pi)
            notification = builder.build()
            self.service.startForeground(1, notification)
            print("[Service][Notifier] Promoted to foreground service")
        except Exception as exc:
            print(f"[Service][Notifier] startForeground failed: {exc}")
            traceback.print_exc()


# ---------------------------------------------------------------------------
# Per-pet state tracker. We compare last-seen flags vs current state to
# decide which notifications to fire. Re-firing requires the flag to clear
# first (debounce).
# ---------------------------------------------------------------------------
class StateTracker:
    """Tracks debounced per-pet notification triggers."""

    def __init__(self):
        # key: (pet_id, event_kind) -> bool  (True == we've already notified)
        self._fired = {}
        # last seen poop count, so we only notify on increases
        self._last_poop_count = 0

    @staticmethod
    def _pet_key(pet, kind):
        return (id(pet), kind)

    def diff(self, pets, poop_count):
        """Yield ``(notification_key, title, body)`` tuples for new triggers.

        Cleared flags don't yield anything; they reset internal state so the
        next time the condition appears we'll notify again.
        """
        events = []

        # Sickness (one notification per pet, per sickness onset)
        for pet in pets:
            key = self._pet_key(pet, "sick")
            currently_sick = getattr(pet, "sick", 0) > 0
            already_fired = self._fired.get(key, False)
            if currently_sick and not already_fired:
                events.append((
                    f"sick:{id(pet)}",
                    "Pet is sick!",
                    f"{pet.name} caught something and needs medicine.",
                ))
                self._fired[key] = True
            elif not currently_sick and already_fired:
                self._fired[key] = False  # clear so next sickness re-fires

        # Care alarm (call-sign): hunger / strength / overdue sleep
        for pet in pets:
            key = self._pet_key(pet, "alarm")
            try:
                needs_call = bool(pet.call_sign())
            except Exception:
                needs_call = False
            already_fired = self._fired.get(key, False)
            if needs_call and not already_fired:
                reason = self._call_reason(pet)
                events.append((
                    f"alarm:{id(pet)}",
                    "Pet needs attention",
                    f"{pet.name} {reason}",
                ))
                self._fired[key] = True
            elif not needs_call and already_fired:
                self._fired[key] = False

        # Dying pet (high-priority, fires on dying flag transition)
        for pet in pets:
            key = self._pet_key(pet, "dying")
            dying = bool(getattr(pet, "dying", False))
            already_fired = self._fired.get(key, False)
            if dying and not already_fired:
                events.append((
                    f"dying:{id(pet)}",
                    "Pet is dying!",
                    f"Open Omnipet to save {pet.name}.",
                ))
                self._fired[key] = True
            elif not dying and already_fired:
                self._fired[key] = False

        # Pooping: notify whenever the on-screen poop count grows.
        if poop_count > self._last_poop_count:
            delta = poop_count - self._last_poop_count
            events.append((
                "poop",
                "Cleanup needed" if delta == 1 else "Cleanup needed!",
                f"{poop_count} poop{'s' if poop_count != 1 else ''} on the field.",
            ))
        self._last_poop_count = poop_count

        return events

    @staticmethod
    def _call_reason(pet):
        if getattr(pet, "hunger", 0) == 0:
            return "is hungry."
        if getattr(pet, "strength", 0) == 0:
            return "is exhausted."
        try:
            if pet.should_sleep():
                return "wants to sleep."
        except Exception:
            pass
        return "needs your attention."


# ---------------------------------------------------------------------------
# Main service loop
# ---------------------------------------------------------------------------
TICK_INTERVAL_SECONDS = 60.0
SAVE_EVERY_N_TICKS = 5  # save every ~5 minutes


def _silence_sound(runtime_globals):
    """Replace runtime_globals.game_sound with a no-op so the service never
    touches the audio device (the foreground app may own it on some devices).
    """
    class _SilentSound:
        def play(self, name):
            return None

        def stop_all(self):
            return None

        def get_music_position(self):
            return 0

        def load_sounds(self):
            return None

    runtime_globals.game_sound = _SilentSound()


def _has_pets_to_tick(game_globals):
    """True only if there's actually something for us to do."""
    try:
        return bool(game_globals.pet_list)
    except Exception:
        return False


def main():
    print("[Service] Starting Omnipet background service")

    _init_headless_pygame()

    try:
        from core import runtime_globals, game_globals
    except Exception as exc:
        print(f"[Service] Failed to import core globals: {exc}")
        traceback.print_exc()
        return

    runtime_globals.IS_ANDROID = True
    runtime_globals.APP_ROOT = APP_ROOT

    # Resolution defaults so any sprite scaling that runs during pet update
    # has sensible numbers (it doesn't actually render anything).
    try:
        runtime_globals.update_resolution_constants(240, 240)
    except Exception:
        pass

    _silence_sound(runtime_globals)

    # No save -> nothing to do. Exit immediately as required by the brief.
    if not game_globals.has_game_mode_preference():
        print("[Service] No save / game mode preference -- exiting.")
        return

    game_globals.load_game_mode_preference()
    if game_globals.is_progress_mode():
        game_globals.load_player_id()

    # Modules must be loaded before pets can tick (pets call get_module()).
    try:
        from utils.module_utils import load_modules
        load_modules()
    except Exception as exc:
        print(f"[Service] Failed to load modules: {exc}")
        traceback.print_exc()
        return

    try:
        game_globals.migrate_legacy_saves()
        game_globals.load()
    except Exception as exc:
        print(f"[Service] Failed to load save: {exc}")
        traceback.print_exc()
        return

    if not _has_pets_to_tick(game_globals):
        print("[Service] No pets in save -- exiting.")
        return

    notifier = AndroidNotifier()
    notifier.show_foreground(
        "Omnipet running",
        "Your pets are being looked after in the background.",
    )

    tracker = StateTracker()
    # Seed the poop baseline so we don't notify on existing-at-start poops.
    tracker._last_poop_count = len(game_globals.poop_list)

    # Make sure the marker exists (the main app should create it before
    # starting us, but being defensive avoids an immediate exit on race).
    marker = _service_marker_path()
    if not os.path.exists(marker):
        try:
            with open(marker, "w") as f:
                f.write(str(int(time.time())))
        except Exception as exc:
            print(f"[Service] Could not create marker file: {exc}")

    tick_count = 0
    print(f"[Service] Loop start: {len(game_globals.pet_list)} pet(s), "
          f"tick={TICK_INTERVAL_SECONDS}s")

    try:
        while True:
            loop_start = time.monotonic()

            # Stop signal: main app removed the marker -> exit cleanly.
            if not os.path.exists(marker):
                print("[Service] Stop marker removed -- shutting down.")
                break

            # Tick pets and poops.
            for pet in list(game_globals.pet_list):
                try:
                    pet.update()
                except Exception as exc:
                    print(f"[Service] pet.update() failed for {getattr(pet, 'name', '?')}: {exc}")
                    traceback.print_exc()

            for poop in list(game_globals.poop_list):
                try:
                    poop.update()
                except Exception:
                    pass

            # Heartbeat notification every tick (≈1 min) for diagnostic testing.
            try:
                notifier.notify(
                    "service_heartbeat",
                    "Omnipet service running",
                    f"Tick {tick_count + 1} — service is active.",
                )
            except Exception as exc:
                print(f"[Service] heartbeat notify failed: {exc}")

            # Emit notifications for state changes since last tick.
            try:
                events = tracker.diff(game_globals.pet_list,
                                      len(game_globals.poop_list))
                for key, title, body in events:
                    notifier.notify(key, title, body)
            except Exception as exc:
                print(f"[Service] notification dispatch failed: {exc}")
                traceback.print_exc()

            # Periodic save.
            tick_count += 1
            if tick_count % SAVE_EVERY_N_TICKS == 0:
                try:
                    game_globals.save()
                except Exception as exc:
                    print(f"[Service] save failed: {exc}")
                    traceback.print_exc()

            # Sleep to next tick boundary.
            elapsed = time.monotonic() - loop_start
            sleep_for = max(1.0, TICK_INTERVAL_SECONDS - elapsed)
            time.sleep(sleep_for)
    except KeyboardInterrupt:
        print("[Service] KeyboardInterrupt")
    finally:
        try:
            game_globals.save()
        except Exception as exc:
            print(f"[Service] final save failed: {exc}")
        print("[Service] Stopped")


if __name__ == "__main__":
    main()

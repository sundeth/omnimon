"""
Android Background Service controller (foreground-app side).

Bridges the foreground pygame app to the python-for-android service
declared in buildozer.spec as ``services = pet_background:service_main.py:foreground``.

When the user backgrounds the app (APP_DIDENTERBACKGROUND from SDL2) or
quits, ``start_service()`` is called: it writes a marker file so the
service knows it should keep running, then asks the JVM to start the
service via ``Service<Name>.start()``.

When the app comes back to the foreground (APP_WILLENTERFOREGROUND),
``stop_service()`` removes the marker file and asks the service to
``stopSelf()``. The marker is the authoritative signal -- even if the
JNI stop call fails, the service will self-terminate at its next tick.

This module is a no-op on non-Android platforms.
"""

import os

from core import runtime_globals


# python-for-android generates the service Java class as
#     <package.domain>.<package.name>.Service<DerivedName>
# but the exact casing of <DerivedName> varies between p4a versions:
#   - older sdl2 bootstrap:     name[0].upper() + name[1:]    -> "Pet_background"
#   - newer (str.title())  :    name.title()                  -> "Pet_Background"
#   - some forks strip "_" :    name.title().replace("_","")  -> "PetBackground"
# We try them all so this controller keeps working across forks.
_PACKAGE_PREFIX = "org.omnipet.omnipet"
_SERVICE_BASE_NAME = "pet_background"


def _candidate_service_class_names():
    """Return likely fully-qualified Java class names for our service."""
    n = _SERVICE_BASE_NAME
    variants = []
    seen = set()

    def add(suffix):
        fq = f"{_PACKAGE_PREFIX}.Service{suffix}"
        if fq not in seen:
            seen.add(fq)
            variants.append(fq)

    add(n[0].upper() + n[1:])               # Pet_background
    add(n.title())                          # Pet_Background
    add(n.title().replace("_", ""))         # PetBackground
    add(n.upper())                          # PET_BACKGROUND (rare)
    return variants


def _autoclass_service():
    """Resolve the generated Java service class with version-fork tolerance."""
    from jnius import autoclass  # type: ignore
    last_exc = None
    for name in _candidate_service_class_names():
        try:
            return autoclass(name), name
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(
        f"None of the candidate service classes loaded "
        f"({_candidate_service_class_names()}). Last error: {last_exc}"
    )


_MARKER_FILENAME = "service_active.flag"


def _marker_path():
    """Resolve the marker path on the same private storage the service reads."""
    if not runtime_globals.IS_ANDROID:
        return os.path.join(os.getcwd(), _MARKER_FILENAME)
    try:
        from android.storage import app_storage_path  # type: ignore
        return os.path.join(app_storage_path(), _MARKER_FILENAME)
    except Exception:
        return os.path.join(os.getcwd(), _MARKER_FILENAME)


def _write_marker():
    try:
        with open(_marker_path(), "w") as f:
            import time
            f.write(str(int(time.time())))
    except Exception as exc:
        print(f"[BgService] Could not write marker: {exc}")


def _remove_marker():
    try:
        path = _marker_path()
        if os.path.exists(path):
            os.remove(path)
    except Exception as exc:
        print(f"[BgService] Could not remove marker: {exc}")


def _has_active_save():
    """Cheap pre-check so we never start the service when there's nothing to do."""
    try:
        from core import game_globals
        if not game_globals.has_game_mode_preference():
            return False
        # If we have no pets in memory the save likely is empty too --
        # but the service does its own re-check, so we just need a soft gate.
        return True
    except Exception:
        return False


def start_service():
    """Start the background pet-tick service (Android only).

    Safe to call multiple times -- starting an already-running service
    just delivers another onStartCommand which the service ignores.
    """
    if not runtime_globals.IS_ANDROID:
        return False
    if not _has_active_save():
        print("[BgService] No active save; not starting service.")
        return False

    _write_marker()

    try:
        from jnius import autoclass  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Service, resolved_name = _autoclass_service()
        mActivity = PythonActivity.mActivity
        # Argument is forwarded as PYTHON_SERVICE_ARGUMENT to the service.
        # We pass the app root so the service can locate src/ and modules/.
        argument = os.getcwd()
        Service.start(mActivity, argument)
        print(f"[BgService] Service start requested ({resolved_name})")
        return True
    except Exception as exc:
        print(f"[BgService] Failed to start service: {exc}")
        # Without the JNI bridge, the marker alone won't do anything --
        # remove it so we don't leave a stale flag.
        _remove_marker()
        return False


def stop_service():
    """Ask the background service to terminate.

    Removing the marker is the authoritative stop signal -- the service
    polls it each tick and exits cleanly. We *also* try a JNI stopService
    so the OS doesn't keep the foreground notification on screen until
    the next tick.
    """
    if not runtime_globals.IS_ANDROID:
        return False

    _remove_marker()

    try:
        from jnius import autoclass  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Service, resolved_name = _autoclass_service()
        mActivity = PythonActivity.mActivity
        intent = Intent(mActivity, Service)
        mActivity.stopService(intent)
        print(f"[BgService] Service stop requested ({resolved_name})")
        return True
    except Exception as exc:
        # Marker removal alone will still terminate the service at its
        # next tick boundary (<= TICK_INTERVAL_SECONDS), so this isn't
        # fatal -- just slower.
        print(f"[BgService] stopService JNI call failed (will self-stop): {exc}")
        return False


def reload_state_from_disk():
    """Refresh the foreground app's in-memory state from the save file.

    Call after ``stop_service()`` on resume. While the app was paused the
    background service may have advanced pets, added poops, or even let
    one die -- the in-memory ``game_globals`` state is now stale. We
    reload the save and re-prime sprite caches so the running scene picks
    up the new objects without crashing.

    Safe to call on desktop (it's just a save reload).
    """
    try:
        from core import game_globals, runtime_globals
    except Exception as exc:
        print(f"[BgService] reload: could not import core globals: {exc}")
        return

    try:
        # Drop sprite cache entries for pets that are about to be replaced;
        # otherwise we'd leak surfaces keyed by stale pet object identity.
        runtime_globals.pet_sprites.clear()
    except Exception:
        pass

    try:
        game_globals.load()
    except Exception as exc:
        print(f"[BgService] reload: game_globals.load() failed: {exc}")
        return

    # Re-create sprite entries for the freshly loaded pets so the next
    # frame can draw them without hitting a KeyError.
    try:
        for pet in getattr(game_globals, "pet_list", []):
            try:
                pet.load_sprite()
            except Exception as exc:
                print(f"[BgService] reload: pet.load_sprite failed for "
                      f"{getattr(pet, 'name', '?')}: {exc}")
    except Exception:
        pass

    print("[BgService] In-memory state refreshed from disk")


def request_notification_permission():
    """Ask the user (Android 13+ only) for POST_NOTIFICATIONS at runtime.

    Below API 33 the permission is granted at install time, so this is a
    no-op. Without it, the per-event notifications (sick/poop/alarm) the
    background service emits would be silently dropped on Android 13+.
    """
    if not runtime_globals.IS_ANDROID:
        return
    try:
        from android.permissions import request_permissions, Permission  # type: ignore
        request_permissions([Permission.POST_NOTIFICATIONS])
    except Exception as exc:
        # On older devices the constant won't exist; that's fine.
        print(f"[BgService] notification-permission request skipped: {exc}")

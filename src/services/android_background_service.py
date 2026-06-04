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


_status = {
    "last_result": None,        # "ok", "blocked", "unsupported", "no_save"
    "last_error": "",
    "success_count": 0,
    "fail_count": 0,
}


def get_status() -> dict:
    """Return a snapshot of the most recent service-start outcome.

    Consumed by the settings menu to surface a user-readable status
    ("OK" / "Blocked" / etc.) and a hint for MIUI/Xiaomi devices where
    Autostart must be granted manually.
    """
    return dict(_status)


def get_status_label() -> str:
    """One-word summary suitable for an option-row value."""
    result = _status.get("last_result")
    if not runtime_globals.IS_ANDROID:
        return "N/A"
    if result is None:
        return "Idle"
    return {
        "ok": "Running",
        "blocked": "Blocked",
        "unsupported": "Unavail.",
        "no_save": "Idle",
    }.get(result, result)


def start_service():
    """Start the background pet-tick service (Android only).

    Safe to call multiple times -- starting an already-running service
    just delivers another onStartCommand which the service ignores.
    """
    if not runtime_globals.IS_ANDROID:
        _status["last_result"] = "unsupported"
        return False
    if not _has_active_save():
        _status["last_result"] = "no_save"
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
        _status["last_result"] = "ok"
        _status["last_error"] = ""
        _status["success_count"] += 1
        return True
    except Exception as exc:
        msg = str(exc)
        print(f"[BgService] Failed to start service: {exc}")
        # MIUI's "process is bad" SecurityException → Autostart denied.
        if "process is bad" in msg or "SecurityException" in msg:
            _status["last_result"] = "blocked"
        else:
            _status["last_result"] = "unsupported"
        _status["last_error"] = msg[:200]
        _status["fail_count"] += 1
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


_lifecycle_registered = False


def install_lifecycle_hooks(on_pause=None, on_resume=None):
    """Register an Application.ActivityLifecycleCallbacks listener via JNI.

    SDL2's APP_DIDENTERBACKGROUND event isn't surfaced by pygame on
    every p4a build (notably the MIUI/Xiaomi case observed in the wild
    where pygame never delivers the lifecycle event).  This hooks
    Android's own per-activity callbacks, which fire on *every* Android
    version regardless of SDL routing.

    The provided callbacks run on the JVM main thread.  Keep them tiny
    and thread-safe — they typically just call ``game.save()`` and
    ``start_service()`` / ``stop_service()``.

    No-op on non-Android, on failure, or on a second call (registration
    is idempotent for the lifetime of the process).
    """
    global _lifecycle_registered
    if _lifecycle_registered or not runtime_globals.IS_ANDROID:
        return False

    try:
        from jnius import autoclass, PythonJavaClass, java_method  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        mActivity = PythonActivity.mActivity
        Application = mActivity.getApplication()

        class _Callbacks(PythonJavaClass):
            __javainterfaces__ = [
                "android/app/Application$ActivityLifecycleCallbacks"
            ]
            __javacontext__ = "app"

            @java_method("(Landroid/app/Activity;Landroid/os/Bundle;)V")
            def onActivityCreated(self, activity, savedInstanceState):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityStarted(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityResumed(self, activity):
                try:
                    if on_resume:
                        on_resume()
                except Exception as cb_exc:
                    print(f"[BgService] on_resume callback error: {cb_exc}")

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPaused(self, activity):
                try:
                    if on_pause:
                        on_pause()
                except Exception as cb_exc:
                    print(f"[BgService] on_pause callback error: {cb_exc}")

            @java_method("(Landroid/app/Activity;)V")
            def onActivityStopped(self, activity):
                pass

            @java_method("(Landroid/app/Activity;Landroid/os/Bundle;)V")
            def onActivitySaveInstanceState(self, activity, outState):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityDestroyed(self, activity):
                pass

            # --- API 29+ default methods ---
            # pyjnius raises NotImplementedError for each unimplemented default
            # method in the interface, which can prevent the preceding real
            # callbacks (onActivityPaused etc.) from executing on some devices.
            @java_method("(Landroid/app/Activity;Landroid/os/Bundle;)V")
            def onActivityPreCreated(self, activity, savedInstanceState):
                pass

            @java_method("(Landroid/app/Activity;Landroid/os/Bundle;)V")
            def onActivityPostCreated(self, activity, savedInstanceState):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPreStarted(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPostStarted(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPreResumed(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPostResumed(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPrePaused(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPostPaused(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPreStopped(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPostStopped(self, activity):
                pass

            @java_method("(Landroid/app/Activity;Landroid/os/Bundle;)V")
            def onActivityPreSaveInstanceState(self, activity, outState):
                pass

            @java_method("(Landroid/app/Activity;Landroid/os/Bundle;)V")
            def onActivityPostSaveInstanceState(self, activity, outState):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPreDestroyed(self, activity):
                pass

            @java_method("(Landroid/app/Activity;)V")
            def onActivityPostDestroyed(self, activity):
                pass

        # Hold a reference so the JVM doesn't GC the listener.
        global _callbacks_ref
        _callbacks_ref = _Callbacks()
        Application.registerActivityLifecycleCallbacks(_callbacks_ref)
        _lifecycle_registered = True
        print("[BgService] ActivityLifecycleCallbacks installed")
        return True
    except Exception as exc:
        print(f"[BgService] install_lifecycle_hooks failed: {exc}")
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

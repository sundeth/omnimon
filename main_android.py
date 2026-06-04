"""
Omnipet Virtual Pet - Android Entry Point
"""
import sys
import os

# Add src/ to sys.path.  We try multiple candidates because p4a's __file__
# resolution is inconsistent across bootstraps and emulators.  Bluestacks in
# particular can set a working directory that differs from the APK extraction
# root, so we walk up from __file__ AND from cwd to cover both cases.
_HERE = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
for _candidate in (
    os.path.join(_HERE, 'src'),
    os.path.join(os.path.dirname(_HERE), 'src'),  # one level up from __file__
    os.path.join(os.getcwd(), 'src'),
    os.path.join(os.path.dirname(os.getcwd()), 'src'),
):
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)

# On Bluestacks (and some physical devices) the APK extraction dir differs
# from cwd, so Python's site module never finds sitecustomize.pyc and the
# p4a import hook that enables loading .pyc files from package directories
# is never installed.  We locate and execute it manually here, before any
# game package is imported.
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
                print(f"[main_android] sitecustomize loaded from {_sc_path}")
                break
        except Exception as _sc_exc:
            print(f"[main_android] sitecustomize load failed ({_sc_path}): {_sc_exc}")
    del _imm, _ilu, _sc_candidates

# Direct .pyc import hook — works even if sitecustomize.pyc wasn't loaded.
# p4a strips all .py source files from the APK; only .pyc bytecode remains.
# Standard Python 3 can only find .pyc files inside __pycache__/; packages
# in the APK have them directly in the package directory.  This finder
# bridges the gap so every package import succeeds without sitecustomize.
class _PyonlyFinder:
    """Finds .pyc-only packages/modules when no .py source is present."""
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
    print(f"[main_android] _PyonlyFinder installed (sitecustomize in modules: "
          f"{'sitecustomize' in sys.modules})")

os.environ["SDL_RENDER_SCALE_QUALITY"] = "0"
import pygame

def main():
    # Initialize pygame
    pygame.init()

    # Use fullscreen with device/native resolution on Android
    try:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    except Exception:
        screen = pygame.display.set_mode((800, 480))

    pygame.display.set_caption("Omnipet")

    try:
        # Import and configure Android environment BEFORE any other game imports
        from core import runtime_globals
        runtime_globals.APP_ROOT = os.getcwd()
        runtime_globals.IS_ANDROID = True
        runtime_globals.INPUT_MODE = runtime_globals.TOUCH_MODE
        from core import game_globals
        game_globals.showClock = False

        # Update runtime resolution based on actual device screen size
        width, height = screen.get_size()

        # Run the game at half the native resolution for performance, then upscale
        game_width  = (width  // 2) & ~1
        game_height = (height // 2) & ~1

        # Update runtime globals to use the game's internal resolution (half)
        runtime_globals.update_resolution_constants(game_width, game_height)

        # Create an offscreen surface at game resolution to render into
        offscreen = pygame.Surface((game_width, game_height))

        # Now import game after environment is configured
        from vpet import VirtualPetGame
        game = VirtualPetGame()

        # Background service controller
        from services import android_background_service as bg_service

        # If a previous session left the service running, stop it now.
        bg_service.stop_service()

        # Ask for POST_NOTIFICATIONS at runtime (Android 13+).
        bg_service.request_notification_permission()

        # SDL2 lifecycle events on Android.
        APP_DIDENTERBACKGROUND = getattr(pygame, "APP_DIDENTERBACKGROUND", None)
        APP_WILLENTERFOREGROUND = getattr(pygame, "APP_WILLENTERFOREGROUND", None)
        APP_TERMINATING = getattr(pygame, "APP_TERMINATING", None)

        # Main game loop
        clock = pygame.time.Clock()
        running = True
        last_periodic_save = pygame.time.get_ticks()
        _last_frame_ticks = None  # None skips the gap check on the first iteration
        PERIODIC_SAVE_MS = 30_000

        # Flags set from the JVM callback thread; consumed on the main thread.
        # [0] = needs display re-acquire (set_mode)
        # [1] = needs game state reload from disk
        _resume_flags = [False, False]

        def _save_and_start_service():
            try:
                game.save()
            except Exception as save_exc:
                print(f"[main_android] save() failed: {save_exc}")
            try:
                bg_service.start_service()
            except Exception as svc_exc:
                print(f"[main_android] start_service() failed: {svc_exc}")

        def _on_resume_from_jvm():
            # Called on the JVM thread — must not touch pygame directly.
            # stop_service() only removes a file and calls JNI stopService,
            # both safe on the JVM thread.
            try:
                bg_service.stop_service()
            except Exception as exc:
                print(f"[main_android] on_resume stop_service failed: {exc}")
            # Signal the main pygame thread to re-acquire the display and
            # reload game state (reload_state_from_disk calls game_globals.load
            # which is not thread-safe with the running game loop).
            _resume_flags[0] = True
            _resume_flags[1] = True

        # Install Android-native lifecycle callbacks.
        bg_service.install_lifecycle_hooks(
            on_pause=_save_and_start_service,
            on_resume=_on_resume_from_jvm,
        )

        while running:
            # --- Suspension gap detection (resume fallback) ---
            # When SDL2 blocks during background, pygame.time.get_ticks()
            # keeps advancing.  A gap >3 s means the app was suspended; we
            # treat it the same as receiving APP_WILLENTERFOREGROUND.  This
            # fires even on devices where SDL2 or JNI lifecycle events are
            # unreliable (e.g. MIUI).
            _now_ticks = pygame.time.get_ticks()
            if _last_frame_ticks is not None and _now_ticks - _last_frame_ticks > 3000:
                try:
                    bg_service.stop_service()
                except Exception:
                    pass
                _resume_flags[0] = True
                _resume_flags[1] = True
            _last_frame_ticks = _now_ticks

            # --- Resume handling (main thread, pygame-safe) ---
            if _resume_flags[0]:
                _resume_flags[0] = False
                try:
                    # Re-acquire the display surface.  SDL2 may have destroyed
                    # the EGL context while the app was backgrounded; calling
                    # set_mode() obtains a fresh, valid surface.
                    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                except Exception as disp_exc:
                    print(f"[main_android] display re-acquire failed: {disp_exc}")

            if _resume_flags[1]:
                _resume_flags[1] = False
                try:
                    bg_service.reload_state_from_disk()
                except Exception as rel_exc:
                    print(f"[main_android] reload_state_from_disk failed: {rel_exc}")

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif APP_DIDENTERBACKGROUND is not None and event.type == APP_DIDENTERBACKGROUND:
                    _save_and_start_service()
                elif APP_WILLENTERFOREGROUND is not None and event.type == APP_WILLENTERFOREGROUND:
                    # SDL2 path — we're already on the main thread.
                    bg_service.stop_service()
                    # Re-acquire display and reload state via flags so the
                    # actions happen at the top of the next loop iteration,
                    # preventing potential double-execution with the JNI path.
                    _resume_flags[0] = True
                    _resume_flags[1] = True
                elif APP_TERMINATING is not None and event.type == APP_TERMINATING:
                    _save_and_start_service()
                    running = False
                else:
                    game.handle_event(event)

            game.update()

            # Periodic auto-save while running.
            now = pygame.time.get_ticks()
            if now - last_periodic_save >= PERIODIC_SAVE_MS:
                try:
                    game.save()
                except Exception as save_exc:
                    print(f"[main_android] periodic save() failed: {save_exc}")
                last_periodic_save = now

            # Render the game into the offscreen (half-res) surface
            game.draw(offscreen, clock)

            screen.fill((0, 0, 0))
            scaled = pygame.transform.scale(offscreen, screen.get_size())
            screen.blit(scaled, (0, 0))

            pygame.display.flip()
            clock.tick(game_globals.configuration.frame_rate)

        game.save()

        # Foreground loop is exiting (user quit or OS terminating). Hand
        # ticking off to the background service so pets keep advancing.
        try:
            bg_service.start_service()
        except Exception as bg_exc:
            print(f"[main_android] Failed to start background service on exit: {bg_exc}")

    except Exception as e:
        # Show error screen with crash info + diagnostic data for debugging
        import traceback
        font = pygame.font.Font(None, 32)

        tb_text = traceback.format_exc()
        error_lines = [
            "Oops, the game crashed!",
            "",
            str(e)[:70],
            "",
            f"cwd: {os.getcwd()[:65]}",
            f"file: {(str(__file__) if __file__ else 'None')[:65]}",
        ]
        for i, p in enumerate(sys.path[:4]):
            error_lines.append(f"path[{i}]: {str(p)[:65]}")
        sc_ok = 'sitecustomize' in sys.modules
        hook_ok = any(type(f).__name__ == '_PyonlyFinder' for f in sys.meta_path)
        error_lines.append(f"sc:{sc_ok} hook:{hook_ok}")
        error_lines.append("")
        error_lines.extend(tb_text.split('\n'))

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = False

            screen.fill((120, 0, 0))  # Dark red background
            y = 10
            for line in error_lines[:30]:
                text = font.render(line[:70], True, (255, 255, 255))
                screen.blit(text, (10, y))
                y += 28

            pygame.display.flip()
            clock = pygame.time.Clock()
            clock.tick(30)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

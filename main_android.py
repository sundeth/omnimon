"""
Omnipet Virtual Pet - Android Entry Point
"""
import sys
import os

# Add src directory to Python path so internal imports (core, input,
# scenes, vpet) resolve.  We try multiple locations because p4a's
# __file__ resolution is inconsistent across bootstraps and emulators
# (notably Bluestacks, where the relative path doesn't resolve and
# imports like ``from input.input_manager import ...`` fail).
_HERE = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
for _candidate in (
    os.path.join(_HERE, 'src'),
    os.path.join(os.getcwd(), 'src'),
):
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)

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
        #runtime_globals.INPUT_MODE_FORCED = True
        
        # Update runtime resolution based on actual device screen size
        width, height = screen.get_size()

        # Run the game at half the native resolution for performance, then upscale
        game_width  = (width  // 2) & ~1
        game_height = (height // 2) & ~1
        #game_width  = width
        #game_height = height

        # Update runtime globals to use the game's internal resolution (half)
        runtime_globals.update_resolution_constants(game_width, game_height)

        # Create an offscreen surface at game resolution to render into
        offscreen = pygame.Surface((game_width, game_height))
        
        # Now import game after environment is configured
        from vpet import VirtualPetGame
        game = VirtualPetGame()
        
        # Background service controller: lets us hand off pet ticking to
        # a python-for-android service when the app is paused / closed.
        from services import android_background_service as bg_service

        # If a previous session left the service running, stop it now that
        # the foreground app has taken over -- otherwise we'd double-tick.
        bg_service.stop_service()

        # Ask for POST_NOTIFICATIONS at runtime (Android 13+). Without it,
        # the background service can't show per-event status-bar alerts.
        bg_service.request_notification_permission()

        # SDL2 lifecycle events on Android. Their integer ids depend on
        # pygame version; we resolve them defensively at runtime.
        APP_DIDENTERBACKGROUND = getattr(pygame, "APP_DIDENTERBACKGROUND", None)
        APP_WILLENTERFOREGROUND = getattr(pygame, "APP_WILLENTERFOREGROUND", None)
        APP_TERMINATING = getattr(pygame, "APP_TERMINATING", None)
        # NOTE: WINDOWHIDDEN / WINDOWFOCUSLOST were tried as fallback
        # lifecycle signals but on MIUI they fire on every transient
        # focus change (including the ones caused by our own set_mode()
        # call on resume) producing an infinite save+set_mode loop with
        # a ~600ms cycle.  Stick to APP_* only — the periodic auto-save
        # below covers the case where APP_* doesn't fire at all.

        # Main game loop
        clock = pygame.time.Clock()
        running = True
        # Periodic-save state.  SDL2's APP_DIDENTERBACKGROUND event
        # delivery via pygame is unreliable across p4a versions, so we
        # also flush to disk every ~30s while in the foreground.
        last_periodic_save = pygame.time.get_ticks()
        PERIODIC_SAVE_MS = 30_000

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
            try:
                bg_service.stop_service()
                bg_service.reload_state_from_disk()
            except Exception as exc:
                print(f"[main_android] on_resume hook failed: {exc}")

        # Install Android-native lifecycle callbacks.  pygame's
        # APP_DIDENTERBACKGROUND isn't delivered on every device (notably
        # several MIUI builds), but Activity.onPause is guaranteed.
        bg_service.install_lifecycle_hooks(
            on_pause=_save_and_start_service,
            on_resume=_on_resume_from_jvm,
        )

        # NOTE: previously had a _reacquire_display() that called
        # set_mode() on resume to fix black-screen after focus switch.
        # Removed — set_mode() itself triggers another focus event on
        # MIUI, creating an infinite loop.  If the black-on-resume bug
        # comes back we need a different mechanism (e.g. a one-shot
        # flag that ignores the next N focus events).

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif APP_DIDENTERBACKGROUND is not None and event.type == APP_DIDENTERBACKGROUND:
                    _save_and_start_service()
                elif APP_WILLENTERFOREGROUND is not None and event.type == APP_WILLENTERFOREGROUND:
                    bg_service.stop_service()
                    bg_service.reload_state_from_disk()
                elif APP_TERMINATING is not None and event.type == APP_TERMINATING:
                    _save_and_start_service()
                    running = False
                else:
                    game.handle_event(event)

            game.update()

            # Periodic auto-save while running (durable progress even if
            # the OS kills us without firing a lifecycle event).
            now = pygame.time.get_ticks()
            if now - last_periodic_save >= PERIODIC_SAVE_MS:
                try:
                    game.save()
                except Exception as save_exc:
                    print(f"[main_android] periodic save() failed: {save_exc}")
                last_periodic_save = now

            # Render the game into the offscreen (half-res) surface
            game.draw(offscreen, clock)

            # Scale the offscreen surface to the *exact* screen size and
            # blit at (0, 0).  Doing this (instead of an integer 2x
            # centered blit) guarantees no letterboxing, no off-screen
            # clipping, and a linear display→game touch mapping that
            # input_manager already does correctly.
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
        # Show error screen with crash info
        import traceback
        font = pygame.font.Font(None, 32)
        
        error_lines = ["Oops, the game crashed!", "", str(e), ""]
        error_lines.extend(traceback.format_exc().split('\n'))
        
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = False
            
            screen.fill((120, 0, 0))  # Dark red background
            y = 10
            for line in error_lines[:25]:  # Show up to 25 lines
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

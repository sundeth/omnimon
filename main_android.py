"""
Omnipet Virtual Pet - Android Entry Point
"""
import sys
import os

# Add src directory to Python path so internal imports (core, components, scenes, vpet) resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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

        # Main game loop
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif APP_DIDENTERBACKGROUND is not None and event.type == APP_DIDENTERBACKGROUND:
                    # App backgrounded: hand off to the service so pets
                    # keep ticking and we can fire status-bar notifications.
                    try:
                        game.save()
                    except Exception:
                        pass
                    bg_service.start_service()
                elif APP_WILLENTERFOREGROUND is not None and event.type == APP_WILLENTERFOREGROUND:
                    # Resuming: tell the service to stop so we don't
                    # double-tick the same save, then refresh in-memory
                    # state from disk because the service may have
                    # advanced the world while we were paused.
                    bg_service.stop_service()
                    bg_service.reload_state_from_disk()
                elif APP_TERMINATING is not None and event.type == APP_TERMINATING:
                    # OS is killing us -- start the service so the pets
                    # don't freeze the moment we die.
                    try:
                        game.save()
                    except Exception:
                        pass
                    bg_service.start_service()
                    running = False
                else:
                    game.handle_event(event)

            game.update()

            # Render the game into the offscreen (half-res) surface
            game.draw(offscreen, clock)

            # Upscale 2x using pixel-perfect integer scaling (no interpolation/blur)
            
            scaled = pygame.transform.scale(
                offscreen,
                (game_width * 2, game_height * 2)
            )
            scaled_rect = scaled.get_rect(center=screen.get_rect().center)
            screen.blit(scaled, scaled_rect)
            #screen.blit(offscreen, (0, 0))

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

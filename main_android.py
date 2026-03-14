"""
Omnipet Virtual Pet - Android Entry Point
"""
import sys
import os

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
        
        # Main game loop
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
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

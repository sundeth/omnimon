"""
Scene Setup
First-time setup scene for configuring input and graphics settings.
"""

import pygame
import random
import os

from components.ui.label import Label
from components.ui.image import Image
from components.ui.game_mode_selector import GameModeSelector
from components.window_background import WindowBackground
from components.ui.ui_manager import UIManager
from core import game_globals, runtime_globals
from core.game_input.input_manager import GPIO_RELEASE_EVENT
from core.game_configuration import GameConfiguration
from core.utils.scene_utils import change_scene
from core.utils.asset_utils import image_load
from core.utils import navigation_utils


class SceneSetup:
    """
    Setup scene for first-time configuration.
    Guides users through input and graphics setup for optimal performance.
    """
    
    # Input buttons to configure (in order)
    INPUT_BUTTONS = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "X", "Y", "L", "R", "START", "SELECT"]

    def __init__(self) -> None:
        """
        Initializes the setup scene with UI elements.
        """
        self.background = WindowBackground(True)
        self.ui_manager = UIManager("GREY")
        
        # Disable external border for setup scene (like tutorial)
        self.ui_manager.show_external_border = False
        
        # Phase management
        # Order: welcome -> input_intro -> input_detect -> input_mapping -> graphics_test -> complete
        self.phase = "welcome"
        self.phase_timer = int(5 * game_globals.configuration.frame_rate)  # 5 seconds per phase
        
        # Title label - centered (240x240 coordinates)
        title_y = 40
        self.title_label = Label(
            x=10,
            y=title_y,
            text="Welcome to Omnipet!",
            is_title=True,
            color_override=(255, 255, 255),
            center=False,
            word_wrap=False,
            max_width=220
        )
        
        # Subtitle label - below title
        subtitle_y = title_y + 40
        self.subtitle_label = Label(
            x=10,
            y=subtitle_y,
            text="Press START to skip setup",
            color_override=(200, 200, 200),
            center=False,
            word_wrap=True,
            max_width=220
        )
        
        # Controller image (hidden initially)
        self.controller_image = None
        
        self.ui_manager.add_component(self.title_label)
        self.ui_manager.add_component(self.subtitle_label)
        
        # Input setup variables
        self.detected_input_type = None  # "keyboard", "gpio", "joystick"
        self.current_button_index = 0
        self.temp_keyboard_map = {}
        self.temp_gpio_map = {}
        self.temp_joystick_map = {}
        self.input_wait_timer = 0
        self.last_raw_input = None  # Store last detected raw input for mapping
        
        # Graphics test variables
        self.test_surface = None
        self.test_sprite = None
        self.test_sprite_scaled = None
        self.test_frame_count = 0
        self.test_fps_samples = []
        self.test_start_time = 0
        self.test_current_multiplier = 1.0
        self.test_stable_frames = 0
        self.test_required_stable_frames = int(2 * game_globals.configuration.frame_rate)
        self.test_completed = False
        self.test_message_timer = 0
        self.real_screen_width = 0
        self.real_screen_height = 0
        self.graphics_accepted = None  # None = waiting, True = accepted, False = rejected
        
        # Game mode selector (created on demand)
        self.game_mode_selector = None
        
        runtime_globals.game_console.log("[SceneSetup] Initialized in welcome phase")

    def update_labels(self, title: str, subtitle: str) -> None:
        """Update the text labels."""
        self.title_label.set_text(title)
        self.subtitle_label.set_text(subtitle)

    def update(self) -> None:
        """Updates the setup scene based on current phase."""
        self.ui_manager.update()
        
        # Route to phase-specific update method
        if self.phase == "welcome":
            self.update_welcome()
        elif self.phase == "input_intro":
            self.update_input_intro()
        elif self.phase == "input_detect":
            self.update_input_detect()
        elif self.phase == "input_mapping":
            self.update_input_mapping()
        elif self.phase == "input_complete":
            self.update_input_complete()
        elif self.phase == "graphics_test":
            self.update_graphics_test()
        elif self.phase == "graphics_confirm":
            self.update_graphics_confirm()
        elif self.phase == "game_mode":
            pass  # Game mode selector handles its own input

    def update_welcome(self) -> None:
        """Update welcome phase - waits for timer then transitions."""
        self.phase_timer -= 1
        
        if self.phase_timer <= 0:
            self.transition_from_welcome()

    def transition_from_welcome(self) -> None:
        """Transition from welcome to next phase."""
        # Check if input setup is needed (skip on Android)
        if game_globals.setup_input and not runtime_globals.IS_ANDROID:
            self.start_input_intro()
        elif game_globals.setup_graphics:
            self.start_graphics_test()
        else:
            self.complete_setup()

    # =========================================================================
    # INPUT SETUP PHASES
    # =========================================================================
    
    def start_input_intro(self) -> None:
        """Show input setup introduction message."""
        self.phase = "input_intro"
        self.update_labels("Setting up input", "Press any button to configure")
        self.phase_timer = int(5 * game_globals.configuration.frame_rate)  # 5 seconds
        
        # Show controller image
        self.show_controller_image()
        
        runtime_globals.game_console.log("[SceneSetup] Input intro started")

    def show_controller_image(self) -> None:
        """Display the controller image."""
        if self.controller_image is None:
            sprite_path = "assets/Controllers.png"
            if os.path.exists(sprite_path):
                # Image is 240x240, place at 0,0 to show controller at bottom-left
                self.controller_image = Image(
                    x=0, y=0,
                    width=240, height=240,
                    image_path=sprite_path
                )
                self.ui_manager.add_component(self.controller_image)

    def hide_controller_image(self) -> None:
        """Hide the controller image."""
        if self.controller_image is not None:
            self.ui_manager.remove_component(self.controller_image)
            self.controller_image = None

    def update_input_intro(self) -> None:
        """Update input intro phase."""
        self.phase_timer -= 1
        
        if self.phase_timer <= 0:
            self.start_input_detect()

    def start_input_detect(self) -> None:
        """Start detecting input type."""
        self.phase = "input_detect"
        self.update_labels("Press any button", "on your input device")
        self.detected_input_type = None
        self.input_wait_timer = int(30 * game_globals.configuration.frame_rate)  # 30 second timeout
        
        runtime_globals.game_console.log("[SceneSetup] Input detection started")

    def update_input_detect(self) -> None:
        """Wait for any input to detect input type."""
        self.input_wait_timer -= 1
        
        if self.input_wait_timer <= 0:
            # Timeout - skip input setup
            runtime_globals.game_console.log("[SceneSetup] Input detection timed out")
            self.skip_input_setup()

    def start_input_mapping(self) -> None:
        """Start mapping individual buttons."""
        self.phase = "input_mapping"
        self.current_button_index = 0
        self.temp_keyboard_map = {}
        self.temp_gpio_map = {}
        self.temp_joystick_map = {}
        
        # Copy F-keys to temp map (not remappable)
        for i in range(1, 13):
            self.temp_keyboard_map[f"F{i}"] = f"K_F{i}"
        
        self.prompt_next_button()

    def prompt_next_button(self) -> None:
        """Prompt for the next button to map."""
        if self.current_button_index >= len(self.INPUT_BUTTONS):
            # All buttons mapped
            self.complete_input_mapping()
            return
        
        button = self.INPUT_BUTTONS[self.current_button_index]
        input_type_name = self.detected_input_type.capitalize() if self.detected_input_type else "Input"
        
        self.update_labels(f"Press {button}", f"on {input_type_name}")
        self.input_wait_timer = int(15 * game_globals.configuration.frame_rate)  # 15 second timeout per button

    def update_input_mapping(self) -> None:
        """Update input mapping phase."""
        self.input_wait_timer -= 1
        
        if self.input_wait_timer <= 0:
            # Timeout for this button - use default
            self.use_default_for_current_button()
    
    def update_input_complete(self) -> None:
        """Update input complete phase - wait for another device or continue."""
        self.input_wait_timer -= 1
        
        if self.input_wait_timer <= 0:
            # Timeout - continue to next phase
            self.finalize_input_setup()

    def use_default_for_current_button(self) -> None:
        """Use default mapping for current button if no input received."""
        if self.current_button_index < len(self.INPUT_BUTTONS):
            button = self.INPUT_BUTTONS[self.current_button_index]
            
            if self.detected_input_type == "keyboard":
                self.temp_keyboard_map[button] = GameConfiguration.DEFAULT_KEYBOARD_MAP.get(button, "K_SPACE")
            elif self.detected_input_type == "gpio":
                # Find default GPIO for this button
                for pin, action in GameConfiguration.DEFAULT_GPIO_MAP.items():
                    if action == button:
                        self.temp_gpio_map[pin] = button
                        break
            elif self.detected_input_type == "joystick":
                for btn_idx, action in GameConfiguration.DEFAULT_JOYSTICK_MAP.items():
                    if action == button:
                        self.temp_joystick_map[btn_idx] = button
                        break
            
            self.current_button_index += 1
            self.prompt_next_button()

    def complete_input_mapping(self) -> None:
        """Complete input mapping and prompt for additional device or continue."""
        config = game_globals.configuration
        
        if self.detected_input_type == "keyboard":
            config.keyboard_map = self.temp_keyboard_map
            config.configured_input_type = "keyboard"
        elif self.detected_input_type == "gpio":
            config.gpio_map = self.temp_gpio_map
            config.configured_input_type = "gpio"
        elif self.detected_input_type == "joystick":
            config.joystick_map = self.temp_joystick_map
            config.configured_input_type = "joystick"
        
        # Reload input mappings in the input manager
        from core.game_input.input_manager import reload_input_mappings
        reload_input_mappings(runtime_globals.game_input)
        
        runtime_globals.game_console.log(f"[SceneSetup] Input mapping complete. Type: {self.detected_input_type}")
        
        # Show option to configure another device or continue
        self.phase = "input_complete"
        self.update_labels("Input configured!", "Press button on another device or A/START to continue")
        self.input_wait_timer = int(10 * game_globals.configuration.frame_rate)  # 10 second timeout
        
    def finalize_input_setup(self) -> None:
        """Finalize input setup and move to next phase."""
        game_globals.setup_input = False
        self.hide_controller_image()
        
        # Move to graphics test if needed
        if game_globals.setup_graphics:
            self.start_graphics_test()
        else:
            self.complete_setup()

    def skip_input_setup(self) -> None:
        """Skip input setup and use defaults."""
        game_globals.setup_input = False
        self.hide_controller_image()
        
        runtime_globals.game_console.log("[SceneSetup] Input setup skipped")
        
        if game_globals.setup_graphics:
            self.start_graphics_test()
        else:
            self.complete_setup()

    # =========================================================================
    # GRAPHICS TEST PHASES
    # =========================================================================
    
    def start_graphics_test(self) -> None:
        """Initialize and start the graphics test phase."""
        self.phase = "graphics_test"
        self.update_labels("Graphics Setup", "Testing... Press B to skip")
        self.hide_controller_image()
        
        # Get real screen resolution
        display_info = pygame.display.Info()
        self.real_screen_width = display_info.current_w
        self.real_screen_height = display_info.current_h
        
        runtime_globals.game_console.log(f"[SceneSetup] Real screen: {self.real_screen_width}x{self.real_screen_height}")
        
        # Load test sprite (JumboPoop1.png - 48x48)
        sprite_path = "assets/JumboPoop1.png"
        if os.path.exists(sprite_path):
            self.test_sprite = image_load(sprite_path)
            self.test_sprite_scaled = self.test_sprite.copy()
        else:
            runtime_globals.game_console.log(f"[SceneSetup] Warning: Test sprite not found at {sprite_path}")
            self.test_sprite = pygame.Surface((48, 48))
            self.test_sprite.fill((255, 0, 255))
            self.test_sprite_scaled = self.test_sprite.copy()
        
        # Create test surface (hidden from player)
        base_width = game_globals.configuration.base_resolution_width
        base_height = game_globals.configuration.base_resolution_height
        self.test_surface = pygame.Surface((base_width, base_height))
        
        self.test_start_time = pygame.time.get_ticks()
        self.test_frame_count = 0
        self.test_fps_samples = []
        self.test_stable_frames = 0
        self.test_current_multiplier = 1.0
        self.test_completed = False
        
        runtime_globals.game_console.log("[SceneSetup] Graphics test started")

    def update_graphics_test(self) -> None:
        """Update graphics test phase."""
        if self.test_completed:
            return
        
        # Blit 12 test sprites at random locations on test surface
        if self.test_surface and self.test_sprite_scaled:
            self.test_surface.fill((0, 0, 0))
            
            for _ in range(12):
                max_x = max(1, self.test_surface.get_width() - self.test_sprite_scaled.get_width())
                max_y = max(1, self.test_surface.get_height() - self.test_sprite_scaled.get_height())
                x = random.randint(0, max_x)
                y = random.randint(0, max_y)
                self.test_surface.blit(self.test_sprite_scaled, (x, y))
        
        # Calculate current FPS
        self.test_frame_count += 1
        current_time = pygame.time.get_ticks()
        elapsed = (current_time - self.test_start_time) / 1000.0
        
        if elapsed > 0:
            current_fps = self.test_frame_count / elapsed
            self.test_fps_samples.append(current_fps)
            
            if len(self.test_fps_samples) > 30:
                self.test_fps_samples.pop(0)
            
            if len(self.test_fps_samples) >= 10:
                avg_fps = sum(self.test_fps_samples) / len(self.test_fps_samples)
                target_fps = game_globals.configuration.frame_rate
                
                if avg_fps >= target_fps * 0.95:
                    self.test_stable_frames += 1
                    
                    if self.test_stable_frames >= self.test_required_stable_frames:
                        if game_globals.configuration.fullscreen:
                            new_multiplier = self.test_current_multiplier * 1.2
                            new_width = int(game_globals.configuration.base_resolution_width * new_multiplier)
                            new_height = int(game_globals.configuration.base_resolution_height * new_multiplier)
                            
                            if new_width <= self.real_screen_width and new_height <= self.real_screen_height:
                                self.increase_test_resolution(new_multiplier)
                            else:
                                self.complete_graphics_test()
                        else:
                            new_fps = game_globals.configuration.frame_rate * 2
                            if new_fps <= 120:
                                game_globals.configuration.frame_rate = new_fps
                                self.test_stable_frames = 0
                                self.test_fps_samples = []
                            else:
                                self.complete_graphics_test()
                else:
                    if self.test_stable_frames > 0:
                        self.complete_graphics_test()
                    else:
                        self.test_stable_frames = 0

    def increase_test_resolution(self, new_multiplier: float) -> None:
        """Increase test resolution and scale test sprite accordingly."""
        self.test_current_multiplier = new_multiplier
        
        new_width = int(game_globals.configuration.base_resolution_width * new_multiplier)
        new_height = int(game_globals.configuration.base_resolution_height * new_multiplier)
        self.test_surface = pygame.Surface((new_width, new_height))
        
        if self.test_sprite:
            new_sprite_width = int(48 * new_multiplier)
            new_sprite_height = int(48 * new_multiplier)
            self.test_sprite_scaled = pygame.transform.scale(self.test_sprite, (new_sprite_width, new_sprite_height))
        
        self.test_stable_frames = 0
        self.test_fps_samples = []
        self.test_frame_count = 0
        self.test_start_time = pygame.time.get_ticks()
        
        runtime_globals.game_console.log(f"[SceneSetup] Resolution multiplier: {new_multiplier:.2f} ({new_width}x{new_height})")

    def complete_graphics_test(self) -> None:
        """Complete graphics test and show confirmation."""
        self.test_completed = True
        game_globals.configuration.resolution_multiplyer_max = self.test_current_multiplier
        
        # Show confirmation message
        if game_globals.configuration.fullscreen:
            new_width = int(game_globals.configuration.base_resolution_width * self.test_current_multiplier)
            new_height = int(game_globals.configuration.base_resolution_height * self.test_current_multiplier)
            message = f"Recommended: {new_width}x{new_height}"
        else:
            message = f"Recommended: {game_globals.configuration.frame_rate} FPS"
        
        self.phase = "graphics_confirm"
        self.update_labels("Graphics Complete", f"{message} A=Accept B=Skip")
        self.graphics_accepted = None
        self.test_message_timer = int(10 * game_globals.configuration.frame_rate)  # 10 seconds auto-accept
        
        runtime_globals.game_console.log(f"[SceneSetup] Graphics test complete. Multiplier: {self.test_current_multiplier:.2f}")

    def update_graphics_confirm(self) -> None:
        """Wait for user to accept or reject graphics settings."""
        self.test_message_timer -= 1
        
        if self.test_message_timer <= 0:
            # Auto-accept after timeout
            self.accept_graphics_settings()

    def accept_graphics_settings(self) -> None:
        """Accept and apply graphics settings."""
        if game_globals.configuration.fullscreen:
            game_globals.configuration.screen_width = int(
                game_globals.configuration.base_resolution_width * game_globals.configuration.resolution_multiplyer_max
            )
            game_globals.configuration.screen_height = int(
                game_globals.configuration.base_resolution_height * game_globals.configuration.resolution_multiplyer_max
            )
            
            # Update runtime globals
            runtime_globals.update_resolution_constants(
                game_globals.configuration.screen_width,
                game_globals.configuration.screen_height
            )
        
        game_globals.setup_graphics = False
        runtime_globals.game_console.log("[SceneSetup] Graphics settings accepted and applied")
        self.complete_setup()

    def reject_graphics_settings(self) -> None:
        """Reject graphics settings and use defaults."""
        game_globals.setup_graphics = False
        runtime_globals.game_console.log("[SceneSetup] Graphics settings rejected, using defaults")
        self.complete_setup()

    # =========================================================================
    # COMPLETION
    # =========================================================================
    
    def complete_setup(self) -> None:
        """Complete setup and transition to game mode selection.

        If a game mode is already set (e.g. re-entered setup for remapping),
        skip mode selection and route directly to the next scene.
        """
        if game_globals.has_game_mode_preference():
            runtime_globals.game_console.log("[SceneSetup] Game mode already set, skipping mode selection")
            game_globals.setup_input = False
            game_globals.setup_graphics = False
            game_globals.save()
            navigation_utils.route_to_next_scene(check_tutorial=True)
            return
        # Show game mode selection before going to the game
        self.start_game_mode_selection()

    def start_game_mode_selection(self) -> None:
        """Show the game mode selection screen (Progression vs Free)."""
        self.phase = "game_mode"
        
        # Hide the title/subtitle labels
        self.title_label.visible = False
        self.subtitle_label.visible = False
        
        # Create and add the game mode selector
        self.game_mode_selector = GameModeSelector(
            x=0, y=0,
            width=240, height=240,
            on_select_callback=self._on_game_mode_selected
        )
        self.ui_manager.add_component(self.game_mode_selector)
        self.ui_manager.set_focused_component(self.game_mode_selector)
        
        runtime_globals.game_console.log("[SceneSetup] Game mode selection started")

    def _on_game_mode_selected(self, index: int) -> None:
        """Handle game mode selection.

        Args:
            index: 0 = Progression Mode, 1 = Free Mode
        """
        if index == 0:
            game_globals.game_mode = game_globals.GAME_MODE_PROGRESS
            runtime_globals.game_console.log("[SceneSetup] Progression Mode selected")
        else:
            game_globals.game_mode = game_globals.GAME_MODE_FREE
            runtime_globals.game_console.log("[SceneSetup] Free Mode selected")

        # Persist the mode preference so next launch reads the right subfolder
        game_globals.save_game_mode_preference()

        if game_globals.is_progress_mode():
            # Progress Mode requires login to obtain player_id before
            # the save directory can be resolved.  Hand off to SceneLogin.
            change_scene("login")
            runtime_globals.game_console.log("[SceneSetup] → SceneLogin (Progress Mode)")
            return

        # Free Mode: migrate saves, create save dir, load, finalize
        game_globals.migrate_legacy_saves()
        save_dir = game_globals.get_save_dir()
        os.makedirs(save_dir, exist_ok=True)
        game_globals.load()
        self.finalize_setup()

    def finalize_setup(self) -> None:
        """Finalize setup after game mode is chosen and transition to next scene."""
        runtime_globals.game_console.log("[SceneSetup] Setup complete")

        # Clear setup flags so we don't re-enter setup on next boot
        game_globals.setup_input = False
        game_globals.setup_graphics = False
        game_globals.save()

        # Use centralized routing
        navigation_utils.route_to_next_scene(check_tutorial=True)

    def draw(self, surface: pygame.Surface) -> None:
        """Draws the setup scene."""
        self.background.draw(surface)
        self.ui_manager.draw(surface)

    def handle_event(self, event) -> bool:
        """Handle input events."""
        event_type, event_data = event
        
        # Welcome phase - START skips entire setup, other buttons advance
        if self.phase == "welcome":
            if event_type == "START":
                # Skip entire setup but still require game mode selection
                runtime_globals.game_sound.play("cancel")
                game_globals.setup_input = False
                game_globals.setup_graphics = False
                self.complete_setup()
                return True
            elif event_type in ["A", "B", "SELECT", "LCLICK"]:
                self.transition_from_welcome()
                return True
        
        # Input intro - ESC/B skips
        elif self.phase == "input_intro":
            if event_type in ["B", "START", "SELECT"]:
                self.skip_input_setup()
                return True
            if event_type in ["A", "LCLICK"]:
                self.start_input_detect()
                return True
        
        # Input detection - detect input type
        elif self.phase == "input_detect":
            if event_type in ["B"]:
                self.skip_input_setup()
                return True
            # Handle in handle_raw_input instead
        
        # Input mapping - map buttons
        elif self.phase == "input_mapping":
            if event_type in ["B"]:
                self.skip_input_setup()
                return True
            # Handle in handle_raw_input instead
        
        # Input complete - wait for another device or continue
        elif self.phase == "input_complete":
            if event_type in ["A", "START"]:
                self.finalize_input_setup()
                return True
            # Other buttons restart detection for new device
        
        # Graphics test - B skips
        elif self.phase == "graphics_test":
            if event_type in ["B"]:
                # Skip graphics test and use defaults
                game_globals.setup_graphics = False
                self.complete_setup()
                return True
        
        # Graphics confirmation
        elif self.phase == "graphics_confirm":
            if event_type in ["A", "START"]:
                self.finalize_input_setup()
                return True
            # Other buttons restart detection for new device
        
        # Graphics confirmation
        elif self.phase == "graphics_confirm":
            if event_type == "A":
                self.accept_graphics_settings()
                return True
            elif event_type == "B":
                self.reject_graphics_settings()
                return True
        
        # Game mode selection - delegate to the selector component
        elif self.phase == "game_mode":
            if self.game_mode_selector:
                return self.game_mode_selector.handle_event(event)
        
        return self.ui_manager.handle_event(event)

    def handle_raw_pygame_event(self, pygame_event) -> bool:
        """Handle raw pygame events for input detection/mapping.
        This should be called from the main game loop before normal event processing.
        """
        if self.phase == "input_detect":
            return self.detect_input_type(pygame_event)
        elif self.phase == "input_mapping":
            return self.map_input_button(pygame_event)
        elif self.phase == "input_complete":
            # Check if user wants to configure another input device
            # If it's a different type, restart detection
            current_type = self.detected_input_type
            if current_type == "keyboard" and hasattr(pygame_event, 'gpio_pin') and pygame_event.type == GPIO_RELEASE_EVENT:
                self.detected_input_type = None
                self.start_input_detect()
                return True
            elif current_type == "keyboard" and pygame_event.type == pygame.JOYBUTTONDOWN:
                self.detected_input_type = None
                self.start_input_detect()
                return True
            elif current_type == "gpio" and pygame_event.type == pygame.KEYDOWN:
                if pygame_event.key != pygame.K_RETURN and pygame_event.key != pygame.K_BACKSPACE:  # Ignore A/START
                    self.detected_input_type = None
                    self.start_input_detect()
                    return True
            elif current_type == "gpio" and pygame_event.type == pygame.JOYBUTTONDOWN:
                self.detected_input_type = None
                self.start_input_detect()
                return True
            elif current_type == "joystick" and pygame_event.type == pygame.KEYDOWN:
                if pygame_event.key != pygame.K_RETURN and pygame_event.key != pygame.K_BACKSPACE:  # Ignore A/START
                    self.detected_input_type = None
                    self.start_input_detect()
                    return True
            elif current_type == "joystick" and hasattr(pygame_event, 'gpio_pin') and pygame_event.type == GPIO_RELEASE_EVENT:
                self.detected_input_type = None
                self.start_input_detect()
                return True
        return False

    def detect_input_type(self, pygame_event) -> bool:
        """Detect which input type the user is using."""
        # Keyboard
        if pygame_event.type == pygame.KEYDOWN:
            # Check for skip keys
            if pygame_event.key == pygame.K_ESCAPE:
                self.skip_input_setup()
                return True
            
            # If keyboard not yet detected, detect it and prompt for UP
            if self.detected_input_type != "keyboard":
                self.detected_input_type = "keyboard"
                self.update_labels("Keyboard detected", "Now press UP")
                self.last_raw_input = None
                self.input_wait_timer = int(30 * game_globals.configuration.frame_rate)  # Reset timer
                runtime_globals.game_console.log("[SceneSetup] Keyboard detected, waiting for UP")
                return True
            
            # Keyboard already detected, this is the UP button
            key_name = pygame.key.name(pygame_event.key).upper()
            # Handle special key names
            if key_name == "UP":
                key_str = "K_UP"
            elif key_name == "DOWN":
                key_str = "K_DOWN"
            elif key_name == "LEFT":
                key_str = "K_LEFT"
            elif key_name == "RIGHT":
                key_str = "K_RIGHT"
            elif key_name == "RETURN":
                key_str = "K_RETURN"
            elif key_name == "ESCAPE":
                key_str = "K_ESCAPE"
            elif key_name == "BACKSPACE":
                key_str = "K_BACKSPACE"
            elif key_name == "TAB":
                key_str = "K_TAB"
            elif key_name == "SPACE":
                key_str = "K_SPACE"
            elif key_name == "LEFT CTRL":
                key_str = "K_LCTRL"
            elif key_name == "LEFT SHIFT":
                key_str = "K_LSHIFT"
            else:
                key_str = f"K_{key_name.replace(' ', '_')}"
            
            self.temp_keyboard_map["UP"] = key_str
            self.current_button_index = 1  # Skip to next button
            
            runtime_globals.game_console.log(f"[SceneSetup] Keyboard detected, UP mapped to {key_str}")
            self.start_input_mapping()
            return True
        
        # GPIO (only react to release events to match fire-on-release debounce)
        if hasattr(pygame_event, 'gpio_pin') and pygame_event.type == GPIO_RELEASE_EVENT:
            pin = pygame_event.gpio_pin
            if pin in GameConfiguration.VALID_GPIO_PINS:
                if pin == 20:  # Skip pin (B button default)
                    self.skip_input_setup()
                    return True
                
                # If GPIO not yet detected, detect it and prompt for UP
                if self.detected_input_type != "gpio":
                    self.detected_input_type = "gpio"
                    self.update_labels("GPIO detected", "Now press UP")
                    self.last_raw_input = None
                    self.input_wait_timer = int(30 * game_globals.configuration.frame_rate)  # Reset timer
                    runtime_globals.game_console.log("[SceneSetup] GPIO detected, waiting for UP")
                    return True
                
                # GPIO already detected, this is the UP button
                self.temp_gpio_map[pin] = "UP"
                self.current_button_index = 1
                
                runtime_globals.game_console.log(f"[SceneSetup] GPIO detected, UP mapped to pin {pin}")
                self.start_input_mapping()
                return True
        
        # Joystick button
        if pygame_event.type == pygame.JOYBUTTONDOWN:
            if pygame_event.button == 1:  # Button 1 skips (B button default)
                self.skip_input_setup()
                return True
            
            # If joystick not yet detected, detect it and prompt for UP
            if self.detected_input_type != "joystick":
                self.detected_input_type = "joystick"
                self.update_labels("Joystick detected", "Now press UP")
                self.last_raw_input = None
                self.input_wait_timer = int(30 * game_globals.configuration.frame_rate)  # Reset timer
                runtime_globals.game_console.log("[SceneSetup] Joystick detected, waiting for UP")
                return True
            
            # Joystick already detected, this is the UP button
            self.temp_joystick_map[pygame_event.button] = "UP"
            self.current_button_index = 1
            
            runtime_globals.game_console.log(f"[SceneSetup] Joystick detected, UP mapped to button {pygame_event.button}")
            self.start_input_mapping()
            return True
        
        # Joystick hat (D-pad)
        if pygame_event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = pygame_event.value
            if hat_y == 1:  # Up on D-pad
                self.detected_input_type = "joystick"
                self.update_labels("Joystick D-pad", "Using defaults for directions")
                
                # For hat-based input, use defaults for directions
                runtime_globals.game_console.log("[SceneSetup] Joystick D-pad detected, using hat defaults")
                self.current_button_index = 4  # Skip to A button
                self.start_input_mapping()
                return True
        
        return False

    def map_input_button(self, pygame_event) -> bool:
        """Map individual input buttons."""
        if self.current_button_index >= len(self.INPUT_BUTTONS):
            return False
        
        current_button = self.INPUT_BUTTONS[self.current_button_index]
        
        if self.detected_input_type == "keyboard":
            if pygame_event.type == pygame.KEYDOWN:
                if pygame_event.key == pygame.K_ESCAPE:
                    self.skip_input_setup()
                    return True
                
                key_name = pygame.key.name(pygame_event.key).upper()
                # Handle special key names
                if key_name == "UP":
                    key_str = "K_UP"
                elif key_name == "DOWN":
                    key_str = "K_DOWN"
                elif key_name == "LEFT":
                    key_str = "K_LEFT"
                elif key_name == "RIGHT":
                    key_str = "K_RIGHT"
                elif key_name == "RETURN":
                    key_str = "K_RETURN"
                elif key_name == "ESCAPE":
                    key_str = "K_ESCAPE"
                elif key_name == "BACKSPACE":
                    key_str = "K_BACKSPACE"
                elif key_name == "TAB":
                    key_str = "K_TAB"
                elif key_name == "SPACE":
                    key_str = "K_SPACE"
                elif key_name == "LEFT CTRL":
                    key_str = "K_LCTRL"
                elif key_name == "LEFT SHIFT":
                    key_str = "K_LSHIFT"
                elif key_name.startswith("["):
                    # Numpad keys
                    key_str = f"K_KP{key_name[1:-1]}"
                else:
                    key_str = f"K_{key_name.replace(' ', '_')}"
                
                self.temp_keyboard_map[current_button] = key_str
                runtime_globals.game_console.log(f"[SceneSetup] {current_button} mapped to {key_str}")
                
                self.current_button_index += 1
                self.prompt_next_button()
                return True
        
        elif self.detected_input_type == "gpio":
            if hasattr(pygame_event, 'gpio_pin') and pygame_event.type == GPIO_RELEASE_EVENT:
                pin = pygame_event.gpio_pin
                if pin in GameConfiguration.VALID_GPIO_PINS:
                    if pin == 20:  # Skip
                        self.skip_input_setup()
                        return True
                    
                    self.temp_gpio_map[pin] = current_button
                    runtime_globals.game_console.log(f"[SceneSetup] {current_button} mapped to GPIO {pin}")
                    
                    self.current_button_index += 1
                    self.prompt_next_button()
                    return True
        
        elif self.detected_input_type == "joystick":
            if pygame_event.type == pygame.JOYBUTTONDOWN:
                if pygame_event.button == 1:  # Skip
                    self.skip_input_setup()
                    return True
                
                self.temp_joystick_map[pygame_event.button] = current_button
                runtime_globals.game_console.log(f"[SceneSetup] {current_button} mapped to button {pygame_event.button}")
                
                self.current_button_index += 1
                self.prompt_next_button()
                return True
        
        return False


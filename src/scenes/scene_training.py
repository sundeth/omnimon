"""
Scene Training
Handles both Dummy and Head-to-Head training modes for pets.
"""

import pygame

from ui.ui_manager import UIManager
from ui.components.title_scene import TitleScene
from ui.components.button import Button
from ui.components.pet_selector import PetSelector
from ui.components.background import Background
from ui.windows.window_background import WindowBackground

from core import game_globals, runtime_globals
from training.count_training import CountMatchTraining
from training.count_classic_training import CountMatchClassicTraining
from training.count_z_training import CountMatchZTraining
from training.dummy_training import DummyTraining
from training.excite_training import ExciteTraining
from training.head_training import HeadToHeadTraining
from training.mogera_training import MogeraTraining
from training.shake_training import ShakeTraining
import core.constants as constants
from utils.pet_utils import get_training_targets
from utils.scene_utils import change_scene
from ui.ui_constants import BASE_RESOLUTION, GREEN

# Gameplay shop item IDs for training modes
TRAINING_GAMEPLAY_IDS = {
    "count_classic": "b2c3d4e5-0002-4000-b000-000000000001",  # Count Match (Classic)
    "count_z": "b2c3d4e5-0002-4000-b000-000000000002",        # Count Match (Z)
    "count": "b2c3d4e5-0002-4000-b000-000000000003",          # Count Match (Color)
    "head": "b2c3d4e5-0002-4000-b000-000000000004",           # Head Charge
    "mogera": "b2c3d4e5-0002-4000-b000-000000000005",         # Mogera
    "excite": "b2c3d4e5-0002-4000-b000-000000000006",         # Xai Bar (Excite)
    "punch": "b2c3d4e5-0002-4000-b000-000000000007",          # Punch
}

#=====================================================================
# SceneTraining (Training Menu)
#=====================================================================

class SceneTraining:
    def __init__(self) -> None:
        # Use GREEN theme for training
        self.ui_manager = UIManager("GREEN")
        
        # UI Components for menu phase
        self.background = None
        self.title_scene = None
        self.pet_selector = None
        self.dummy_button = None
        self.head_button = None
        self.count_button = None
        self.count_classic_button = None
        self.count_z_button = None
        self.excite_button = None
        self.punch_button = None
        self.mogera_button = None
        self.exit_button = None
        
        # Training phase UI components
        self.training_exit_button = None
        
        # Legacy background for training phase
        self.window_background = WindowBackground(False)

        self.phase = "menu"
        self.mode = None
        
        # Create static background surface with border for menu phase
        self.static_border_surface = None
        self.create_static_background()
        
        # Set up modern UI for menu
        self.setup_ui()

        runtime_globals.game_console.log("[SceneTraining] Training scene initialized.")

    def owns_training_mode(self, mode_key: str) -> bool:
        """Check if the player owns a training mode.
        
        Args:
            mode_key: Key for the training mode (e.g., 'count', 'head', 'mogera')
            
        Returns:
            True if the player owns the training mode, False otherwise.
            Dummy training is always available.
            In Free Mode, all training modes are unlocked.
        """
        if mode_key == "dummy":
            return True  # Dummy is always available
        
        if game_globals.is_free_mode():
            return True  # Free Mode: all training modes unlocked
        
        gameplay_id = TRAINING_GAMEPLAY_IDS.get(mode_key)
        if not gameplay_id:
            return False
        
        return game_globals.purchases.owns_gameplay(gameplay_id)

    def create_static_background(self):
        """Create a static surface with GREEN border around the screen"""
        # Get screen dimensions and UI information
        screen_width, screen_height = runtime_globals.SCREEN_WIDTH, runtime_globals.SCREEN_HEIGHT
        ui_scale = self.ui_manager.ui_scale
        
        # Calculate border size (2 pixels * ui_scale)
        border_size = 2 * ui_scale
        
        # Create surface for just the GREEN border
        self.static_border_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.static_border_surface.fill((0, 0, 0, 0))  # Transparent
        
        # Draw GREEN border around the UI area
        for i in range(border_size):
            border_rect = pygame.Rect(0, 0, 
                                    screen_width, screen_height)
            pygame.draw.rect(self.static_border_surface, GREEN, border_rect, border_size)
        
        # Blit position is always (0, 0) since surface covers entire screen
        self.static_border_pos = (0, 0)

    def setup_ui(self):
        """Setup the UI components for the training menu."""
        try:
            # Use base 240x240 resolution for UI layout
            ui_width = ui_height = BASE_RESOLUTION
            
            # Create and add the UI background that covers the full UI area
            self.background = Background(ui_width, ui_height)
            # Set single black region covering entire UI
            self.background.set_regions([(0, ui_height, "black")])
            self.ui_manager.add_component(self.background)
            
            # Create and add the title scene at top left
            self.title_scene = TitleScene(0, 9, "TRAINING")
            self.ui_manager.add_component(self.title_scene)
            
            # Create and add the pet selector at bottom right (60% of UI width)
            selector_width = int(ui_width * 0.6)  # 60% of UI width
            selector_height = 46
            selector_x = ui_width - selector_width - 5  # Right aligned with margin
            selector_y = ui_height - selector_height - 5  # Bottom aligned with margin
            
            self.pet_selector = PetSelector(selector_x, selector_y, selector_width, selector_height)
            # Set pets and make it static for now
            self.pet_selector.set_pets(get_training_targets())
            self.pet_selector.set_interactive(False)  # Static display for now
            self.ui_manager.add_component(self.pet_selector)
            
            # Create training type buttons (56x56) arranged in 3 rows of 3
            # Only show buttons for training modes the player owns
            button_size = 54
            button_spacing = 2
            start_x = 36  # Left margin
            start_y = 25  # Below title
            
            # Collect owned training modes as (button_instance, mode_key)
            owned_buttons = []
            
            # Row 1: Dummy (always available), Head-to-Head, Count Match (Color)
            # Dummy is always available
            self.dummy_button = Button(
                0, 0, button_size, button_size,  # Position will be set later
                "", self.on_dummy_training,
                cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': False},
                decorators=["Dummy"]
            )
            owned_buttons.append(self.dummy_button)

            if self.owns_training_mode("head"):
                self.head_button = Button(
                    0, 0, button_size, button_size,
                    "", self.on_head_training,
                    cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': False},
                    decorators=["HeadToHead"]
                )
                owned_buttons.append(self.head_button)

            if self.owns_training_mode("count"):
                self.count_button = Button(
                    0, 0, button_size, button_size,
                    "", self.on_count_training,
                    cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True},
                    decorators=["CountMatch"]
                )
                owned_buttons.append(self.count_button)

            if self.owns_training_mode("count_classic"):
                self.count_classic_button = Button(
                    0, 0, button_size, button_size,
                    "", self.on_count_classic_training,
                    cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': False},
                    decorators=["CountMatch_Classic"]
                )
                owned_buttons.append(self.count_classic_button)

            if self.owns_training_mode("count_z"):
                self.count_z_button = Button(
                    0, 0, button_size, button_size,
                    "", self.on_count_z_training,
                    cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': False},
                    decorators=["CountMatch_Z"]
                )
                owned_buttons.append(self.count_z_button)

            if self.owns_training_mode("excite"):
                # Excite button has two decorators: Excite and current XAI number
                excite_decorators = ["Excite", f"Xai_{game_globals.xai}"]
                self.excite_button = Button(
                    0, 0, button_size, button_size,
                    "", self.on_excite_training,
                    cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True},
                    decorators=excite_decorators
                )
                owned_buttons.append(self.excite_button)

            if self.owns_training_mode("punch"):
                self.punch_button = Button(
                    0, 0, button_size, button_size,
                    "", self.on_punch_training,
                    cut_corners={'tl': False, 'tr': False, 'bl': False, 'br': False},
                    decorators=["Punch"]
                )
                owned_buttons.append(self.punch_button)

            if self.owns_training_mode("mogera"):
                self.mogera_button = Button(
                    0, 0, button_size, button_size,
                    "", self.on_mogera_training,
                    cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True},
                    decorators=["Mogera"]
                )
                owned_buttons.append(self.mogera_button)

            # Exit button is always available
            self.exit_button = Button(
                0, 0, button_size, button_size,
                "EXIT", self.on_exit_training,
                cut_corners={'tl': True, 'tr': False, 'bl': False, 'br': True}
            )
            owned_buttons.append(self.exit_button)
            
            # Arrange buttons in a 3-column grid
            columns = 3
            for i, button in enumerate(owned_buttons):
                row = i // columns
                col = i % columns
                new_x = start_x + col * (button_size + button_spacing)
                new_y = start_y + row * (button_size + button_spacing)
                button.rect.x = new_x
                button.rect.y = new_y
                self.ui_manager.add_component(button)
            
            self.owned_buttons = owned_buttons
            
            runtime_globals.game_console.log("[SceneTraining] UI setup completed successfully")
            
        except Exception as e:
            runtime_globals.game_console.log(f"[SceneTraining] ERROR in setup_ui: {e}")
            import traceback
            runtime_globals.game_console.log(f"[SceneTraining] Traceback: {traceback.format_exc()}")
            raise
        
        # Restore focus to last used training button
        idx = runtime_globals.training_index
        if idx < len(self.owned_buttons):
            self.ui_manager.set_focused_component(self.owned_buttons[idx])
        elif self.dummy_button:
            self.ui_manager.set_focused_component(self.dummy_button)
            
    def hide_menu_buttons(self):
        """Hide all menu buttons when entering training phase."""
        buttons = [
            self.dummy_button, self.head_button, self.count_button,
            self.count_classic_button, self.count_z_button,
            self.excite_button, self.punch_button, self.mogera_button,
            self.exit_button, self.pet_selector, self.title_scene, self.background
        ]
        for button in buttons:
            if button is not None:
                button.visible = False
                button.focusable = False
    
    def show_menu_buttons(self):
        """Show all menu buttons when returning to menu phase."""
        buttons = [
            self.dummy_button, self.head_button, self.count_button,
            self.count_classic_button, self.count_z_button,
            self.excite_button, self.punch_button, self.mogera_button,
            self.exit_button, self.pet_selector, self.title_scene, self.background
        ]
        for button in buttons:
            if button is not None:
                button.visible = True
                # Only make training buttons focusable (not pet_selector, title_scene, background)
                if button not in [self.pet_selector, self.title_scene, self.background]:
                    button.focusable = True

    # Button callback methods that preserve existing training logic
    def on_dummy_training(self):
        """Handle Dummy training button press."""
        if len(get_training_targets()) > 0:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "dummy"
            self.mode = DummyTraining(self.ui_manager)
            self.create_training_exit_button()  # Create exit button for training phase
            runtime_globals.game_console.log("Starting Dummy Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")
            
    def on_head_training(self):
        """Handle Head-to-Head training button press."""
        if len(get_training_targets()) > 1:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "headtohead"

            self.mode = HeadToHeadTraining(self.ui_manager)
            self.create_training_exit_button()  # Create exit button for training phase
            runtime_globals.game_console.log("Starting Head-to-Head Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")
            
    def on_count_training(self):
        """Handle Count Match training button press."""
        if len(get_training_targets()) > 0:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "count"
            self.mode = CountMatchTraining(self.ui_manager)
            self.create_training_exit_button()  # Create exit button for training phase
            runtime_globals.game_console.log("Starting Count Match Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")

    def on_count_classic_training(self):
        """Handle Count Match Classic training button press."""
        if len(get_training_targets()) > 0:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "count_classic"
            self.mode = CountMatchClassicTraining(self.ui_manager)
            self.create_training_exit_button()
            runtime_globals.game_console.log("Starting Count Match Classic Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")

    def on_count_z_training(self):
        """Handle Count Match Z training button press."""
        if len(get_training_targets()) > 0:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "count_z"
            self.mode = CountMatchZTraining(self.ui_manager)
            self.create_training_exit_button()
            runtime_globals.game_console.log("Starting Count Match Z Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")
            
    def on_excite_training(self):
        """Handle Excite training button press."""
        if len(get_training_targets()) > 0:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "excite"
            self.mode = ExciteTraining(self.ui_manager)
            self.create_training_exit_button()  # Create exit button for training phase
            runtime_globals.game_console.log("Starting Excite Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")
            
    def on_punch_training(self):
        """Handle Punch training button press."""
        if len(get_training_targets()) > 0:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "punch"
            self.mode = ShakeTraining(self.ui_manager)
            self.create_training_exit_button()  # Create exit button for training phase
            runtime_globals.game_console.log("Starting Shake Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")
            
    def on_mogera_training(self):
        """Handle Mogera training button press."""
        if len(get_training_targets()) > 0:
            runtime_globals.game_sound.play("menu")
            self.hide_menu_buttons()
            self.phase = "mogera"
            self.mode = MogeraTraining(self.ui_manager)
            self.create_training_exit_button()  # Create exit button for training phase
            runtime_globals.game_console.log("Starting Mogera Training.")
            for pet in get_training_targets():
                pet.check_disturbed_sleep()
        else:
            runtime_globals.game_sound.play("cancel")
            
    def on_exit_training(self):
        """Handle EXIT button press."""
        if self.mode:
            runtime_globals.game_sound.play("cancel")
            self.mode.handle_event(("B", None))
        else:
            runtime_globals.game_sound.play("cancel")
            self._save_training_index()
            change_scene("game")

    def on_training_exit(self):
        """Handle training exit button press - send B key to current training mode."""
        if self.mode:
            self.mode.handle_event(("B", None))

    def create_training_exit_button(self):
        """Create the exit button for training phases using screen coordinates."""
        if not self.training_exit_button:
            # Calculate screen position (top right corner with margin)
            button_size = 30  # 30x30 at 1x scale
            margin = 10
            
            # Position at top right corner of screen
            screen_x = 10 + margin
            screen_y = margin
            
            self.training_exit_button = Button(
                0, 0, button_size, button_size,  # Base size, position will be set via screen coords
                "", self.on_training_exit,
                decorators=["ExitButton_Green"],
                shadow_mode="full"
            )
            
            # Enable screen coordinates and set position
            self.training_exit_button.use_screen_coordinates = True
            self.ui_manager.add_component(self.training_exit_button)
            
            # Set screen position after adding to manager (so scaling is applied)
            self.training_exit_button.set_screen_coordinates(True, screen_x, screen_y)
            self.training_exit_button.focusable = True

    def remove_training_exit_button(self):
        """Remove the training exit button."""
        if self.training_exit_button:
            # Remove from UI manager components list and focusable list
            if self.training_exit_button in self.ui_manager.components:
                self.ui_manager.components.remove(self.training_exit_button)
            if self.training_exit_button in self.ui_manager.focusable_components:
                self.ui_manager.focusable_components.remove(self.training_exit_button)
            self.training_exit_button = None

    def update(self):
        if self.phase == "menu":
            # Update UI manager for menu phase
            self.ui_manager.update()
            # Update pet selector with current targets
            if self.pet_selector:
                self.pet_selector.set_pets(get_training_targets())
                
        elif self.mode:
            self.mode.update()
            
            # Update the training exit button if it exists
            if self.training_exit_button:
                self.training_exit_button.update()
                
            # Check if training mode completed and return to menu
            if hasattr(self.mode, 'phase') and self.mode.phase == "exit":
                self.phase = "menu"
                self.mode = None
                self.remove_training_exit_button()
                self.show_menu_buttons()

    def draw(self, surface: pygame.Surface):
        # Always draw the window background first (all states)
        self.window_background.draw(surface)
        
        # Draw the GREEN border on top
        surface.blit(self.static_border_surface, self.static_border_pos)
        
        if self.phase == "menu":
            # Draw UI components on top
            self.ui_manager.draw(surface)
            
        elif self.mode:
            # Use legacy system for training phases
            self.mode.draw(surface)
            
            # Draw training exit button AFTER training mode so it appears on top
            # Only draw it during phases where we want it visible (not alert/impact which cover full screen)
            if (self.training_exit_button and 
                (runtime_globals.INPUT_MODE == runtime_globals.MOUSE_MODE or runtime_globals.INPUT_MODE == runtime_globals.TOUCH_MODE) and
                self.mode.phase not in ["alert", "impact", "result"]):
                self.training_exit_button.draw(surface)
                
    def handle_event(self, event):
        if self.phase == "menu":
            self.handle_menu_input(event)
        elif self.mode:
            # Only route click events to the UIManager when the click actually lands
            # on the exit button's rect.  Routing all events (including A keypresses
            # and off-target clicks) would let the focused exit button steal inputs
            # that should go to the active training minigame.
            if self.training_exit_button and (runtime_globals.INPUT_MODE == runtime_globals.MOUSE_MODE or runtime_globals.INPUT_MODE == runtime_globals.TOUCH_MODE):
                event_type, event_data = event
                if event_type == "LCLICK" and event_data and "pos" in event_data:
                    if self.training_exit_button.rect.collidepoint(event_data["pos"]):
                        if self.ui_manager.handle_event(event):
                            return  # Exit button consumed the click

            # Pass event to training mode
            self.mode.handle_event(event)

    def _save_training_index(self):
        """Save the currently focused button index to runtime_globals."""
        idx = self.ui_manager.focused_index
        focused = self.ui_manager.focusable_components[idx] if 0 <= idx < len(self.ui_manager.focusable_components) else None
        if focused and hasattr(self, 'owned_buttons'):
            try:
                runtime_globals.training_index = self.owned_buttons.index(focused)
            except ValueError:
                pass

    def handle_menu_input(self, event):
        # Handle pygame events through UI manager first
        if self.ui_manager.handle_event(event):
            return
        
        # Handle string action events (from input manager)
        event_type, event_data = event
        if event_type == "B":
            runtime_globals.game_sound.play("cancel")
            self._save_training_index()
            change_scene("game")
            return


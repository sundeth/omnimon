"""
JogressView - Jogress fusion selection
Shows pet selector and jogress display for 2-pet fusion
"""
import pygame
from ui.ui_manager import UIManager
from ui.components.title_scene import TitleScene
from ui.components.button import Button
from ui.components.background import Background
from ui.components.pet_selector import PetSelector
from ui.components.jogress_display import JogressDisplay
from ui.ui_constants import BASE_RESOLUTION
from core import runtime_globals
from utils.pet_utils import get_selected_pets
from utils.scene_utils import change_scene
from core import game_globals


class JogressView:
    """Jogress fusion selection view."""
    
    def __init__(self, ui_manager: UIManager, change_view_callback):
        """Initialize the Jogress view.
        
        Args:
            ui_manager: The UI manager instance
            change_view_callback: Callback to change to another view
        """
        self.ui_manager = ui_manager
        self.change_view = change_view_callback
        
        # Selection state
        self.selected_pets = []  # List of selected pet indices (max 2)
        self.selection_themes = ["GREEN", "BLUE"]  # GREEN→left, BLUE→right
        self.pet_theme_assignments = {}  # Dict: pet_index -> theme_name
        
        # Evolution animation state
        self.evolution_animation_active = False
        self.evolution_animation_timer = 0.0
        self.evolution_animation_duration = 3.0
        self.pet_circles = []
        self.particles = []
        
        # Jogress execution state
        self.jogress_executing = False  # True when performing jogress after animation
        
        # UI Components
        self.background = None
        self.title_scene = None
        self.pet_selector = None
        self.jogress_display = None
        self.confirm_button = None
        self.back_button = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components."""
        ui_width = ui_height = BASE_RESOLUTION
        
        # Background
        self.background = Background(ui_width, ui_height)
        self.background.set_regions([(0, ui_height, "black")])
        self.ui_manager.add_component(self.background)
        
        # Title
        self.title_scene = TitleScene(0, 9, "BATTLE")
        self.ui_manager.add_component(self.title_scene)
        
        # Jogress display
        display_width = 160
        display_height = 125
        display_x = (ui_width - display_width) // 2
        display_y = 25
        
        self.jogress_display = JogressDisplay(display_x, display_y, display_width, display_height)
        self.jogress_display.set_compatibility_callback(self._check_pet_compatibility)
        self.ui_manager.add_component(self.jogress_display)
        
        # Buttons
        back_button_width = 60
        confirm_button_width = 80
        button_height = 25
        button_spacing = 5
        
        total_button_width = back_button_width + confirm_button_width + button_spacing
        buttons_start_x = (ui_width - total_button_width) // 2
        buttons_y = display_y + display_height + 10
        
        self.back_button = Button(
            buttons_start_x, buttons_y, back_button_width, button_height,
            "BACK", self._on_back
        )
        self.ui_manager.add_component(self.back_button)
        
        confirm_button_x = buttons_start_x + back_button_width + button_spacing
        self.confirm_button = Button(
            confirm_button_x, buttons_y, confirm_button_width, button_height,
            "CONFIRM", self._on_confirm,
            enabled=False
        )
        self.ui_manager.add_component(self.confirm_button)
        
        # Pet selector
        selector_y = buttons_y + button_height + 5
        selector_height = 50
        self.pet_selector = PetSelector(10, selector_y, ui_width - 20, selector_height)
        self.pet_selector.set_pets(get_selected_pets())
        self.pet_selector.set_interactive(True)
        self.pet_selector.activation_callback = self._handle_pet_activation
        self.ui_manager.add_component(self.pet_selector)
        
        # Set initial focus
        self.ui_manager.set_focused_component(self.pet_selector)
        self.pet_selector.focused_cell = 0
        
        runtime_globals.game_console.log("[JogressView] UI setup complete")
    
    def _handle_pet_activation(self):
        """Handle pet activation from pet selector."""
        pet_index = self.pet_selector.get_activation_cell()
        if pet_index >= 0 and pet_index < len(self.pet_selector.pets):
            if pet_index in self.pet_selector.enabled_pets:
                return self._toggle_pet_selection(pet_index)
        return False
    
    def _toggle_pet_selection(self, pet_index):
        """Toggle pet selection (max 2 pets)."""
        if pet_index in self.selected_pets:
            # Deselect
            self.selected_pets.remove(pet_index)
            
            if self.jogress_display:
                slot_to_clear = None
                if pet_index in self.pet_theme_assignments:
                    theme = self.pet_theme_assignments[pet_index]
                    slot_to_clear = 0 if theme == "GREEN" else 1
                    
                if slot_to_clear is not None:
                    self.jogress_display.clear_slot(slot_to_clear)
            
            if pet_index in self.pet_theme_assignments:
                del self.pet_theme_assignments[pet_index]
                
            runtime_globals.game_sound.play("cancel")
        else:
            # Select
            if len(self.selected_pets) < 2:
                self.selected_pets.append(pet_index)
                
                # Assign theme
                used_themes = set(self.pet_theme_assignments.values())
                available_themes = [theme for theme in self.selection_themes if theme not in used_themes]
                
                if available_themes:
                    self.pet_theme_assignments[pet_index] = available_themes[0]
                    assigned_theme = available_themes[0]
                    
                    if self.jogress_display:
                        pet = self.pet_selector.pets[pet_index] if pet_index < len(self.pet_selector.pets) else None
                        if pet:
                            slot_index = 0 if assigned_theme == "GREEN" else 1
                            self.jogress_display.set_pet_slot(slot_index, pet)
                else:
                    self.pet_theme_assignments[pet_index] = "GREEN"
                    if self.jogress_display:
                        pet = self.pet_selector.pets[pet_index] if pet_index < len(self.pet_selector.pets) else None
                        if pet:
                            self.jogress_display.set_pet_slot(0, pet)
                
                runtime_globals.game_sound.play("menu")
            else:
                runtime_globals.game_sound.play("cancel")
                return False
        
        # Update state
        self.pet_selector.selected_pets = self.selected_pets[:]
        
        if self.confirm_button:
            self.confirm_button.set_enabled(len(self.selected_pets) == 2)
        
        self._update_pet_themes()
        self.pet_selector.needs_redraw = True
        return True
    
    def _update_pet_themes(self):
        """Update pet selector themes."""
        if not self.pet_selector:
            return
            
        self.pet_selector.clear_custom_themes()
        
        for pet_index in self.selected_pets:
            if pet_index in self.pet_theme_assignments:
                theme = self.pet_theme_assignments[pet_index]
                self.pet_selector.set_pet_custom_theme(pet_index, theme)
    
    def _check_pet_compatibility(self, pet1, pet2):
        """Check if two pets are compatible for Jogress."""
        if not pet1 or not pet2:
            return False
            
        if pet1.module != pet2.module:
            return False

        # Pet1 must have jogress options
        for evo in pet1.evolve:
            if "jogress" not in evo:
                continue

            # Check for jogress_prefix matching
            if evo.get("jogress_prefix", False):
                if pet2.name.startswith(evo["jogress"]):
                    return True

            # Standard jogress (not PenC)
            if evo["jogress"] != "PenC":
                if pet2.name == evo["jogress"] and pet2.version == evo.get("version", pet1.version):
                    return True

            # PenC jogress (based on attribute + stage)
            elif evo["jogress"] == "PenC":
                if (
                    (pet2.attribute == evo.get("attribute") or (pet2.attribute == "" and evo.get("attribute") == "Free")) and
                    pet2.stage == evo.get("stage")
                ):
                    return True

        return False
    
    def get_jogress_evolution_info(self, pet1, pet2):
        """Get evolution info for compatible pets - used by JogressDisplay."""
        if not pet1 or not pet2:
            return None
            
        for evo in pet1.evolve:
            if "jogress" not in evo:
                continue

            # Check for jogress_prefix matching (standard jogress - single pet)
            if evo.get("jogress_prefix", False):
                if pet2.name.startswith(evo["jogress"]):
                    return {
                        "evolution": evo,
                        "is_dual": False
                    }

            # Standard jogress (not PenC) - single pet result
            if evo["jogress"] != "PenC":
                if pet2.name == evo["jogress"] and pet2.version == evo.get("version", pet1.version):
                    return {
                        "evolution": evo,
                        "is_dual": False
                    }

            # PenC jogress (based on attribute + stage) - DUAL evolution (both pets evolve)
            elif evo["jogress"] == "PenC":
                if (
                    (pet2.attribute == evo.get("attribute") or (pet2.attribute == "" and evo.get("attribute") == "Free")) and
                    pet2.stage == evo.get("stage")
                ):
                    # Check if pet2 also has a matching PenC evolution
                    evo2 = next((e for e in pet2.evolve if e.get("jogress") == "PenC" and e.get("attribute") == pet1.attribute), None)
                    return {
                        "evolution": evo,
                        "evolution2": evo2,  # Pet2's evolution (may be None)
                        "is_dual": True
                    }

        return None
    
    def _on_confirm(self):
        """Handle confirm button."""
        if len(self.selected_pets) != 2:
            runtime_globals.game_sound.play("cancel")
            return
        
        # Check compatibility
        pet1 = game_globals.pet_list[self.selected_pets[0]]
        pet2 = game_globals.pet_list[self.selected_pets[1]]
        
        if not self._check_pet_compatibility(pet1, pet2):
            runtime_globals.game_console.log("[JogressView] Pets are not compatible")
            runtime_globals.game_sound.play("cancel")
            return
        
        # Start evolution animation (original implementation)
        self._start_evolution_animation()
    
    def _perform_jogress(self):
        """Execute Jogress evolution - matches original scene_battle logic."""
        pet1 = game_globals.pet_list[self.selected_pets[0]]
        pet2 = game_globals.pet_list[self.selected_pets[1]]
        
        if pet1.module != pet2.module:
            runtime_globals.game_console.log("[JogressView] Module mismatch")
            return

        for evo in pet1.evolve:
            if "jogress" not in evo:
                continue

            # Jogress prefix matching (standard jogress - removes pet2)
            if evo.get("jogress_prefix", False):
                if pet2.name.startswith(evo["jogress"]):
                    if not hasattr(pet1, 'evolution_history'):
                        pet1.evolution_history = []
                    pet1.evolution_history.append("JOGRESS" + pet2.name)
                    pet1.evolve_to(evo["to"], pet1.version)
                    pet2.evolve_to(evo["to"], pet2.version)
                    # Transfer special attributes from pet2 to pet1
                    if pet2.traited:
                        pet1.traited = True
                    if pet2.shiny:
                        pet1.shiny = True
                    if pet2.shook:
                        pet1.shook = True
                    game_globals.pet_list.remove(pet2)
                    runtime_globals.game_sound.play("evolution")
                    runtime_globals.game_console.log(f"[Jogress] {pet1.name} jogressed to {evo['to']}!")
                    
                    # Update quest progress for jogress
                    from utils.quest_event_utils import update_evolution_quest_progress
                    update_evolution_quest_progress("jogress", pet1.module)
                    
                    change_scene("game")
                    return

            # Standard jogress (not PenC) - removes pet2
            if evo["jogress"] != "PenC":
                if pet2.name == evo["jogress"] and pet2.version == evo.get("version", pet1.version):
                    if not hasattr(pet1, 'evolution_history'):
                        pet1.evolution_history = []
                    pet1.evolution_history.append(pet2.name)
                    pet1.evolve_to(evo["to"], pet1.version)
                    pet2.evolve_to(evo["to"], pet2.version)
                    # Transfer special attributes from pet2 to pet1
                    if pet2.traited:
                        pet1.traited = True
                    if pet2.shiny:
                        pet1.shiny = True
                    if pet2.shook:
                        pet1.shook = True
                    game_globals.pet_list.remove(pet2)
                    runtime_globals.game_sound.play("evolution")
                    runtime_globals.game_console.log(f"[Jogress] {pet1.name} jogressed to {evo['to']}!")
                    
                    # Update quest progress for jogress
                    from utils.quest_event_utils import update_evolution_quest_progress
                    update_evolution_quest_progress("jogress", pet1.module)
                    
                    change_scene("game")
                    return

            # PenC jogress (dual evolution - KEEPS both pets)
            elif evo["jogress"] == "PenC":
                if (pet2.attribute == evo.get("attribute") or (pet2.attribute == "" and evo.get("attribute") == "Free")) and pet2.stage == evo.get("stage"):
                    # Find pet2's matching PenC evolution
                    evo2 = next((e for e in pet2.evolve if e.get("jogress") == "PenC" and e.get("attribute") == pet1.attribute), None)

                    if evo2:
                        # Both pets evolve - this is dual evolution
                        pet1.evolve_to(evo["to"], pet1.version)
                        pet2.evolve_to(evo2["to"], pet2.version)
                    else:
                        # Only pet1 evolves if pet2 doesn't have matching evolution
                        pet1.evolve_to(evo["to"], pet1.version)

                    runtime_globals.game_sound.play("evolution")
                    runtime_globals.game_console.log(f"[Jogress] {pet1.name} jogressed to {evo['to']}!")
                    
                    # Update quest progress for jogress
                    from utils.quest_event_utils import update_evolution_quest_progress
                    update_evolution_quest_progress("jogress", pet1.module)
                    
                    change_scene("game")
                    return

        runtime_globals.game_console.log("[Jogress] Invalid combination.")
        runtime_globals.game_sound.play("fail")
    
    def _on_back(self):
        """Handle back button."""
        runtime_globals.game_sound.play("cancel")
        self.change_view("main_menu")
    
    def cleanup(self):
        """Remove all UI components."""
        if self.background:
            self.ui_manager.remove_component(self.background)
        if self.title_scene:
            self.ui_manager.remove_component(self.title_scene)
        if self.pet_selector:
            self.ui_manager.remove_component(self.pet_selector)
        if self.jogress_display:
            self.ui_manager.remove_component(self.jogress_display)
        if self.confirm_button:
            self.ui_manager.remove_component(self.confirm_button)
        if self.back_button:
            self.ui_manager.remove_component(self.back_button)
    
    def _start_evolution_animation(self):
        """Start the Jogress evolution animation with circles and particles."""
        import math
        
        self.evolution_animation_active = True
        self.evolution_animation_timer = 0.0
        self.pet_circles = []
        self.particles = []
        
        # Hide confirm and back buttons during animation
        if self.confirm_button:
            self.confirm_button.visible = False
        if self.back_button:
            self.back_button.visible = False
            
        # Hide the pet sprites in the JogressDisplay
        if self.jogress_display:
            self.jogress_display.set_hide_pet_sprites(True)
            
        # Get pet positions from jogress display
        if self.jogress_display:
            # Convert base coordinates to screen coordinates
            if self.ui_manager:
                # Get the jogress display's screen position
                display_rect = self.jogress_display.rect
                display_offset_x = display_rect.x
                display_offset_y = display_rect.y
                
                # Pet circle positions (bottom hexagons)
                if self.jogress_display.bottom_left_center and self.jogress_display.bottom_right_center:
                    left_center = self.jogress_display.bottom_left_center
                    right_center = self.jogress_display.bottom_right_center
                    
                    # Convert to screen coordinates
                    left_screen_x = display_offset_x + self.ui_manager.scale_value(left_center[0])
                    left_screen_y = display_offset_y + self.ui_manager.scale_value(left_center[1])
                    right_screen_x = display_offset_x + self.ui_manager.scale_value(right_center[0])
                    right_screen_y = display_offset_y + self.ui_manager.scale_value(right_center[1])
                    
                    # Initial circle radius
                    initial_radius = self.ui_manager.scale_value(self.jogress_display.base_hexagon_size) * 0.6
                    
                    # Create pet circles
                    self.pet_circles = [
                        {
                            "x": left_screen_x,
                            "y": left_screen_y, 
                            "initial_radius": initial_radius,
                            "current_radius": initial_radius,
                            "color": (255, 255, 255)  # White
                        },
                        {
                            "x": right_screen_x,
                            "y": right_screen_y,
                            "initial_radius": initial_radius, 
                            "current_radius": initial_radius,
                            "color": (255, 255, 255)  # White
                        }
                    ]
        
        runtime_globals.game_console.log("[JogressView] Evolution animation started")
    
    def _update_evolution_animation(self):
        """Update the evolution animation state."""
        if not self.evolution_animation_active:
            return
            
        import random
        import math
        
        # Update timer
        dt = 1.0 / 30.0  # Assume 30 FPS
        self.evolution_animation_timer += dt
        
        # Animation progress (0.0 to 1.0)
        progress = min(self.evolution_animation_timer / self.evolution_animation_duration, 1.0)
        
        # Phase 1: Spawn particles and shrink circles (first 80% of animation)
        if progress < 0.8:
            phase_progress = progress / 0.8
            
            # Shrink pet circles
            for circle in self.pet_circles:
                circle["current_radius"] = circle["initial_radius"] * (1.0 - phase_progress)
                
            # Spawn particles from circles
            if random.random() < 0.3:  # 30% chance per frame
                for circle in self.pet_circles:
                    if circle["current_radius"] > 2:  # Only spawn from visible circles
                        # Get target position (top hexagon center)
                        target_x, target_y = self._get_top_hexagon_screen_center()
                        
                        # Spawn particle at circle edge
                        angle = random.uniform(0, 2 * math.pi)
                        spawn_x = circle["x"] + math.cos(angle) * circle["current_radius"]
                        spawn_y = circle["y"] + math.sin(angle) * circle["current_radius"]
                        
                        # Calculate movement vector
                        dx = target_x - spawn_x
                        dy = target_y - spawn_y
                        distance = math.sqrt(dx * dx + dy * dy)
                        
                        if distance > 0:
                            # Normalize and set speed
                            speed = 3.0  # pixels per frame
                            vx = (dx / distance) * speed
                            vy = (dy / distance) * speed
                            
                            # Add particle
                            self.particles.append({
                                "x": spawn_x,
                                "y": spawn_y,
                                "vx": vx,
                                "vy": vy,
                                "target_x": target_x,
                                "target_y": target_y,
                                "life": 1.0,
                                "size": random.uniform(2, 4)
                            })
        
        # Update particles
        for particle in self.particles[:]:  # Copy list to allow removal
            particle["x"] += particle["vx"]
            particle["y"] += particle["vy"]
            particle["life"] -= 0.02  # Fade out
            
            # Check if particle reached target or faded out
            dx = particle["target_x"] - particle["x"]
            dy = particle["target_y"] - particle["y"]
            distance = math.sqrt(dx * dx + dy * dy)
            
            if distance < 5 or particle["life"] <= 0:
                self.particles.remove(particle)
        
        # Phase 2: Complete animation (last 20%)
        if progress >= 0.8:
            # Clear remaining particles and circles
            if progress >= 0.9:
                self.particles.clear()
                for circle in self.pet_circles:
                    circle["current_radius"] = 0
        
        # End animation and perform evolution
        if progress >= 1.0:
            self.evolution_animation_active = False
            runtime_globals.game_console.log("[JogressView] Evolution animation completed, performing Jogress...")
            self._perform_jogress()
    
    def _get_top_hexagon_screen_center(self):
        """Get the screen coordinates of the top hexagon center."""
        if self.jogress_display and self.jogress_display.top_hexagon_center:
            # Get the jogress display's screen position
            display_rect = self.jogress_display.rect
            display_offset_x = display_rect.x
            display_offset_y = display_rect.y
            
            top_center = self.jogress_display.top_hexagon_center
            screen_x = display_offset_x + self.ui_manager.scale_value(top_center[0])
            screen_y = display_offset_y + self.ui_manager.scale_value(top_center[1])
            
            return screen_x, screen_y
        return 120, 60  # Fallback center
    
    def _draw_evolution_animation(self, surface):
        """Draw the evolution animation over the UI."""
        if not self.evolution_animation_active:
            return
            
        # Draw pet circles
        for circle in self.pet_circles:
            if circle["current_radius"] > 0:
                pygame.draw.circle(
                    surface, 
                    circle["color"], 
                    (int(circle["x"]), int(circle["y"])), 
                    int(circle["current_radius"])
                )
        
        # Draw particles
        for particle in self.particles:
            if particle["life"] > 0:
                # Fade particle alpha based on life
                alpha = int(255 * particle["life"])
                color = (255, 255, 255, alpha)
                
                # Create a small surface for the particle with alpha
                particle_surface = pygame.Surface((int(particle["size"] * 2), int(particle["size"] * 2)), pygame.SRCALPHA)
                pygame.draw.circle(
                    particle_surface, 
                    color[:3],  # RGB only for circle
                    (int(particle["size"]), int(particle["size"])), 
                    int(particle["size"])
                )
                
                # Set surface alpha
                particle_surface.set_alpha(alpha)
                
                # Blit to main surface
                surface.blit(
                    particle_surface, 
                    (int(particle["x"] - particle["size"]), int(particle["y"] - particle["size"]))
                )
    
    def update(self):
        """Update the view."""
        # Update evolution animation
        self._update_evolution_animation()
    
    def draw(self, surface: pygame.Surface):
        """Draw the view."""
        # Draw evolution animation over the UI
        self._draw_evolution_animation(surface)
    
    def handle_event(self, event):
        """Handle input events."""
        if not isinstance(event, tuple) or len(event) != 2:
            return
        event_type, event_data = event
        if event_type == "B":
            self._on_back()

"""
Count Match Z Minigame

A minigame similar to Count Match but with a different visual style and scoring system.
Shows arrows based on pet attribute during ready phase, then counts shakes in charge phase.

Ready Phase:
- Shows "Combat_ReadyBW_1" using animated component
- Shows 1-3 (or 4) arrows at y=157 using "Combat_ReadyBW_ArrowB_1"
- Arrow count based on attribute: Free=1, Vi=1, Da=2, Va=3

Charge Phase:
- Shows "Combat_CountBW_1" 
- Each shake adds an arrow using "Combat_ReadyBW_ArrowW_1"
- Does not rotate past max count

Scoring (3 count mode):
                BAD     GOOD    GREAT   EXCELLENT
    Free        0       3       2       1
    Vi          0       3       2       1
    Da          0       3       1       2
    Va          0       1       2       3

4 count mode (pet.level > 5):
- Same as 3 count but with extra arrow
- 0 or 1 shakes = BAD, other results shift by +1
"""
import pygame
from components.ui.ui_manager import UIManager
from components.minigames.count_match import ShakeDetector
from core import runtime_globals


class CountMatchZ:
    """
    Count Match Z minigame - arrow-based counting with attribute-based scoring.
    """

    def __init__(self, ui_manager: UIManager, pet=None, animated_sprite=None) -> None:
        self.ui_manager = ui_manager
        if self.ui_manager is None:
            raise ValueError("UIManager cannot be None")
            
        self.pet = pet
        self.phase = "ready"  # ready, count
        self.press_counter = 0
        self.max_count = 3  # Default 3 count mode
        
        # Check if we should use 4 count mode (pet level > 5)
        if pet and hasattr(pet, 'level') and pet.level > 5:
            self.max_count = 4
        
        # Use the provided AnimatedSprite component
        self.animated_sprite = animated_sprite
        
        # Shake detection for mouse/touch fallback
        self.shake_detector = ShakeDetector()
        
        # Load arrow sprites from assets/ui/
        sprite_scale_factor = runtime_globals.UI_SCALE
        self._arrow_b_sprite = self.ui_manager.load_sprite_non_integer_scaling("assets/ReadyBW_ArrowB.png", sprite_scale_factor)
        self._arrow_w_sprite = self.ui_manager.load_sprite_non_integer_scaling("assets/ReadyBW_ArrowW.png", sprite_scale_factor)
        
        # Calculate arrow positions
        self._arrow_y = int(78 * runtime_globals.UI_SCALE)  # y=157 scaled
        
        self.set_phase("ready")

    def get_target_arrow_count(self):
        """Get the target arrow count based on pet's attribute."""
        if not self.pet:
            return 1
            
        attr = getattr(self.pet, "attribute", "")
        
        if attr == "" or attr == "Free":
            return 1  # Free -> 1 arrow
        elif attr == "Vi":
            return 1  # Virus -> 1 arrow
        elif attr == "Da":
            return 2  # Data -> 2 arrows
        elif attr == "Va":
            return 3  # Vaccine -> 3 arrows
        else:
            return 1

    def _calculate_arrow_positions(self, count):
        """Calculate arrow positions from left to right based on max_count mode."""
        if count <= 0:
            return []
            
        arrow_width = self._arrow_b_sprite.get_width() if self._arrow_b_sprite else int(32 * runtime_globals.UI_SCALE)
        
        # Fixed positions for 3 or 4 arrow slots from left to right
        # Calculate spacing based on max_count (3 or 4 arrows)
        padding = int(20 * runtime_globals.UI_SCALE)
        available_width = runtime_globals.SCREEN_WIDTH - (2 * padding)
        spacing = available_width // self.max_count
        
        # Start from left side with padding
        start_x = padding + (spacing - arrow_width) // 2
        
        positions = []
        for i in range(count):
            x = start_x + (i * spacing)
            positions.append((x, self._arrow_y))
        
        return positions

    def set_phase(self, phase):
        """Set the current phase (ready or count)."""
        self.phase = phase
        if self.animated_sprite:
            self.animated_sprite.stop()
            
        if phase == "count":
            # Reset counter when starting count phase
            self.press_counter = 0
            # Setup count mode in animated sprite - use BW count sprite
            if self.animated_sprite:
                self.animated_sprite.setup_countdown_count_bw()
        elif phase == "ready":
            # Setup ready mode in animated sprite - use BW ready sprite
            if self.animated_sprite:
                self.animated_sprite.setup_countdown_ready_bw()

    def handle_event(self, event):
        """Handle input events for the minigame."""
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        
        event_type, event_data = event
        
        if self.phase == "count" and event_type in ("Y", "SHAKE"):
            # Only count up to max_count
            if self.press_counter < self.max_count:
                self.press_counter += 1
                runtime_globals.game_sound.play("menu")
            return True
        return False

    def update(self):
        """Update the minigame state each frame."""
        self.shake_detector.update()
        if self.phase != "count":
            return

        # Detect shake from mouse/touch motion
        last_pos = getattr(self, '_last_mouse_pos', None)
        mouse_pos = pygame.mouse.get_pos()
        if mouse_pos == last_pos:
            return

        if self.shake_detector.add_mouse_position(mouse_pos):
            self.handle_event(("SHAKE", None))
        self._last_mouse_pos = mouse_pos

    def get_press_counter(self):
        """Get the current press counter."""
        return self.press_counter

    def calculate_result(self):
        """
        Calculate the result based on matching shake count with target arrow count.
        
        The goal is to match the number of arrows shown during the ready phase.
        - Exact match = EXCELLENT (3)
        - Off by 1 = GREAT (2)
        - Off by 2 = GOOD (1)
        - Off by 3+ or 0 shakes = BAD (0)
        
        Returns:
            0 = BAD, 1 = GOOD, 2 = GREAT, 3 = EXCELLENT
        """
        shakes = self.press_counter
        target = self.get_target_arrow_count()
        
        # 0 shakes is always BAD
        if shakes == 0:
            return 0  # BAD
        
        # Calculate difference from target
        diff = abs(shakes - target)
        
        if diff == 0:
            return 3  # EXCELLENT - exact match
        elif diff == 1:
            return 2  # GREAT - off by 1
        elif diff == 2:
            return 1  # GOOD - off by 2
        else:
            return 0  # BAD - off by 3+

    def draw(self, surface):
        """Draw the count match Z minigame components."""
        if self.phase == "ready":
            self.draw_ready(surface)
        else:
            self.draw_count(surface)

    def draw_ready(self, surface):
        """Draw the ready phase with attribute-based arrows."""
        # Draw animated sprite (ReadyBW)
        if self.animated_sprite:
            self.animated_sprite.draw(surface)
        
        # Draw target arrows (black arrows showing what to match)
        if self._arrow_b_sprite:
            target_count = self.get_target_arrow_count()
            positions = self._calculate_arrow_positions(target_count)
            for x, y in positions:
                surface.blit(self._arrow_b_sprite, (x, y))

    def draw_count(self, surface):
        """Draw the count phase with player's shake arrows."""
        # Draw animated sprite (CountBW)
        if self.animated_sprite:
            self.animated_sprite.draw(surface)
        
        # Draw white arrows for shakes made
        if self._arrow_w_sprite:
            positions = self._calculate_arrow_positions(self.press_counter)
            for x, y in positions:
                surface.blit(self._arrow_w_sprite, (x, y))

"""
Count Match Classic Minigame

A minigame similar to DummyCharge but uses SHAKE/Y events to charge from 0 to 14.
Shows a static sprite "Combat_CountClassic_1" during the charge phase using AnimatedSprite.
Success result depends on shake number (exactly like DummyCharge).
"""
from components.ui.ui_manager import UIManager
from core import runtime_globals


class CountMatchClassic:
    """
    Count Match Classic minigame - uses shakes instead of button presses.
    Works like DummyCharge but with SHAKE/Y input instead of A button.
    """

    def __init__(self, ui_manager: UIManager, animated_sprite=None, theme: str = "GREEN") -> None:
        self.strength = 0
        self.max_strength = 14
        self.ui_manager = ui_manager
        
        # Use the provided AnimatedSprite component
        self.animated_sprite = animated_sprite
        
        # internal state
        self.phase = "charge"
        
        # Setup the classic countdown sprite via AnimatedSprite
        if self.animated_sprite:
            self.animated_sprite.setup_countdown_classic()

    def update(self):
        """Update the minigame state each frame."""
        if self.animated_sprite:
            self.animated_sprite.update()

    def handle_event(self, event):
        """Process input events (shake/Y presses)."""
        event_type, event_data = event
        
        if event_type in ["Y", "SHAKE"]:
            runtime_globals.game_sound.play("menu")
            self.strength = min(self.strength + 1, self.max_strength)
            return True
        return False

    def draw(self, surface):
        """Draws the count match classic sprite using AnimatedSprite."""
        if self.animated_sprite:
            self.animated_sprite.draw(surface)

    def get_strength(self):
        """Get the current strength/shake count."""
        return self.strength

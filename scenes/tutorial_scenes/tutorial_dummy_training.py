"""
Tutorial Dummy Training
A modified DummyTraining that waits for player to charge instead of using timer.
"""

import pygame
from core.combat.dummy_training import DummyTraining
from core import runtime_globals
from core.combat import combat_constants
import core.constants as constants


class TutorialDummyTraining(DummyTraining):
    """
    Tutorial version of DummyTraining.
    In tutorial mode, the charge phase waits for player to reach target strength
    instead of using a timer.
    """
    
    def __init__(self, ui_manager, tutorial_mode: bool = True, target_strength: int = 14):
        super().__init__(ui_manager)
        self.tutorial_mode = tutorial_mode
        self.target_strength = target_strength
        self._charge_started = False
        self.on_charge_complete_callback = None
        runtime_globals.game_console.log(f"[TutorialDummyTraining] Created with tutorial_mode={tutorial_mode}, target={target_strength}")
    
    def set_on_charge_complete(self, callback):
        """Set callback for when charging is complete."""
        self.on_charge_complete_callback = callback
    
    def update_charge_phase(self):
        """Override charge phase to wait for player in tutorial mode."""
        # Always update the minigame to sync strength
        self.minigame.update()
        self.strength = self.minigame.strength
        
        if self.tutorial_mode:
            # In tutorial mode, only transition when target strength is reached
            if self.strength >= self.target_strength:
                runtime_globals.game_console.log(f"[TutorialDummyTraining] Target strength {self.target_strength} reached!")
                self.phase = "wait_attack"
                self.frame_counter = 0
                self.prepare_attacks()
                
                # Notify callback
                if self.on_charge_complete_callback:
                    self.on_charge_complete_callback()
            # Otherwise, do NOT check the timer - wait for player
        else:
            # Normal mode - use timer
            if pygame.time.get_ticks() - self.bar_timer > combat_constants.BAR_HOLD_TIME_MS:
                self.phase = "wait_attack"
                self.frame_counter = 0
                self.prepare_attacks()

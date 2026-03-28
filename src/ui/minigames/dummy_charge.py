from ui.ui_manager import UIManager
from core import runtime_globals
import core.constants as constants
from utils.pygame_utils import blit_with_shadow


class DummyCharge:

    def __init__(self, ui_manager: UIManager, theme: str = "GREEN") -> None:
        self.strength = 0
        self.bar_level = 14
        self._holding = False
        self._hold_ticks = 0
        self.ui_manager = ui_manager
        
        # Determine theme-based sprites
        is_green_theme = "GREEN" in theme
        is_red_theme = "RED" in theme
        
        # Calculate proper sprite scale - UI scale is based on 240x240, but sprites are 2x size
        sprite_scale_factor = runtime_globals.UI_SCALE / 2
        
        # cached sprites expected to be provided externally by the caller if needed
        self._sprite_cache = {}
        
        # Load themed sprites based on theme
        if is_green_theme:
            self._sprite_cache['bar_back'] = self.ui_manager.load_sprite_non_integer_scaling(constants.BAR_BACK_GREEN_PATH, sprite_scale_factor)
        elif is_red_theme:
            self._sprite_cache['bar_back'] = self.ui_manager.load_sprite_non_integer_scaling(constants.BAR_BACK_RED_PATH, sprite_scale_factor)
        else:
            # Default to green for other themes
            self._sprite_cache['bar_back'] = self.ui_manager.load_sprite_non_integer_scaling(constants.BAR_BACK_GREEN_PATH, sprite_scale_factor)
            
        # Load bar piece sprites (green, yellow, red max)
        self._sprite_cache['bar_piece_green'] = self.ui_manager.load_sprite_non_integer_scaling(constants.BAR_PIECE_GREEN_PATH, sprite_scale_factor)
        self._sprite_cache['bar_piece_yellow'] = self.ui_manager.load_sprite_non_integer_scaling(constants.BAR_PIECE_YELLOW_PATH, sprite_scale_factor)
        self._sprite_cache['bar_piece_red_max'] = self.ui_manager.load_sprite_non_integer_scaling(constants.BAR_PIECE_RED_MAX_PATH, sprite_scale_factor)
        
        # internal state
        self.phase = "charge"  # charge, wait_attack, impact, result
        self.frame_counter = 0

    def update(self):
        pass


    def handle_event(self, event):
        """Process input events (button presses)."""
        event_type, event_data = event
        
        if event_type in ["A", "LCLICK"]:
            runtime_globals.game_sound.play("menu")
            self.strength = min(getattr(self, "strength", 0) + 1, getattr(self, "bar_level", 14))
            return True
        return False

    def draw(self, surface):
        """Draws the themed charge UI. Bar draws from bottom to top: 10 green, 3 yellow, 1 red max."""
        bar_back = self._sprite_cache['bar_back']
        bar_piece_green = self._sprite_cache['bar_piece_green']
        bar_piece_yellow = self._sprite_cache['bar_piece_yellow']
        bar_piece_red_max = self._sprite_cache['bar_piece_red_max']

        # Center the bar horizontally on screen
        bar_x = (runtime_globals.SCREEN_WIDTH // 2) - (bar_back.get_width() // 2)
        bar_y = (runtime_globals.SCREEN_HEIGHT // 2) - (bar_back.get_height() // 2)
        
        # Draw the bar background
        blit_with_shadow(surface, bar_back, (bar_x, bar_y))
        
        # Calculate sprite scale factor for positioning
        sprite_scale_factor = runtime_globals.UI_SCALE / 2
        
        # Bar back segment positions (in original 2x coordinates, then scaled)
        # Bar back is now 72x374 with 13 regular segments + 1 max segment
        # Bottom regular segment at 13,347, top regular segment at 13,59, max segment at 13,13
        # Distance between segments is 8 pixels (between the colored pixels)
        segment_start_x = int(13 * sprite_scale_factor)  # Offset from bar_back left edge
        max_segment_y = int(13 * sprite_scale_factor)    # Max segment at top
        bottom_segment_y = int(347 * sprite_scale_factor)  # Bottom regular segment
        top_regular_segment_y = int(59 * sprite_scale_factor)  # Top regular segment
        
        # Calculate segment spacing based on actual positions
        # From bottom (347) to top (59) with 13 segments total means 12 gaps between them
        total_distance = bottom_segment_y - top_regular_segment_y  # 347 - 59 = 288 pixels
        segment_spacing = total_distance / 12  # 288 / 12 = 24 pixels per segment (including 8px gap + 16px segment)
        
        # Bar pieces have 4px glow on all sides, so we need to offset them by -4px to align with segments
        glow_offset = int(4 * sprite_scale_factor)
        
        # Draw strength bars from bottom to top (strength 1 = bottom segment, strength 14 = all segments)
        for i in range(self.strength):
            if i < 10:
                # Green segments (strength 1-10): segments 0-9 (bottom 10 segments)
                sprite = bar_piece_green
                # Bottom segment (strength 1, i=0) should be at y=347
                # Calculate position from bottom, moving up
                segment_y = bottom_segment_y - (i * segment_spacing)
                piece_x = bar_x + segment_start_x - glow_offset
                piece_y = bar_y + int(segment_y) - glow_offset
                
            elif i < 13:
                # Yellow segments (strength 11-13): segments 10-12 (next 3 segments)
                sprite = bar_piece_yellow
                # Continue from where green left off
                segment_y = bottom_segment_y - (i * segment_spacing)
                piece_x = bar_x + segment_start_x - glow_offset
                piece_y = bar_y + int(segment_y) - glow_offset
                
            elif i == 13:
                # Red max segment (strength 14): segment 13 (top segment)
                sprite = bar_piece_red_max
                piece_x = bar_x + segment_start_x - glow_offset
                piece_y = bar_y + max_segment_y - glow_offset
            
            blit_with_shadow(surface, sprite, (piece_x, piece_y))
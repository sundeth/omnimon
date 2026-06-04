"""
Base List Component - A flexible list component supporting both horizontal and vertical layouts
Provides common functionality for all list-based UI components with consistent behavior:
- Arrow button navigation with touch/mouse support
- Smooth scrolling animations
- Drag/swipe gestures
- Mouse hover detection
- Keyboard navigation
- Customizable rendering for child classes
"""
import pygame
import math
from ui.components.component import UIComponent
from core import runtime_globals
from utils.pygame_utils import blit_with_cache


class BaseList(UIComponent):
    def __init__(self, x, y, width, height, orientation="horizontal"):
        """
        Initialize the base list component.
        
        Args:
            x, y, width, height: Component dimensions
            orientation: "horizontal" or "vertical" - determines scroll direction
        """
        super().__init__(x, y, width, height)
        
        # Core configuration
        self.orientation = orientation.lower()
        self.focusable = True
        
        # Item management
        self.items = []  # List of items to display
        self.selected_index = 0  # Currently focused item (for navigation)
        self.active_index = 0    # Currently selected item (for interaction)
        
        # Layout configuration (base values, will be scaled)
        self.base_item_size = 60  # Width for horizontal, height for vertical
        self.base_item_spacing = 8  # Spacing between items
        self.base_arrow_size = 24  # Size of arrow buttons
        self.base_margin = 2      # Margin around arrows
        
        # Calculated layout values (set in _calculate_layout)
        self.item_size = self.base_item_size
        self.item_spacing = self.base_item_spacing
        self.arrow_size = self.base_arrow_size
        self.margin = self.base_margin
        self.visible_item_count = 1
        
        # Scroll state
        self.scroll_offset = 0
        self.target_scroll_offset = 0
        self.first_visible_item = 0
        
        # Animation settings
        self.scroll_animation_speed = 300  # pixels per second
        self.last_scroll_time = 0
        
        # Mouse/touch interaction
        self.mouse_over_index = -1
        self.dragging = False
        self.drag_start_pos = (0, 0)
        self.drag_start_scroll = 0
        self.drag_accumulated = 0
        self.drag_threshold = 0  # Will be set based on item_size
        self.last_mouse_click_time = 0  # Track mouse clicks to prevent double activation
        
        # Arrow button state
        self.prev_arrow_pressed = False
        self.next_arrow_pressed = False
        self.arrow_press_time = 0
        
        # Rendering optimization
        self.cached_surface = None
        self.cache_key = None
        self.needs_layout_recalc = True
        
        # Layout rects (will be calculated in _calculate_layout)
        self.prev_arrow_rect = None
        self.next_arrow_rect = None
        self.items_rect = None
        
        # Visual customization - can be overridden to hide background/borders
        self.show_background = True      # Whether to draw the items area background
        self.show_border = True          # Whether to draw the items area border
        self.background_color = None     # Custom background color (None = use theme)
        self.border_color = None         # Custom border color (None = use theme)
        
    def set_items(self, items):
        """Set the list of items to display"""
        self.items = items[:]
        self.selected_index = 0
        self.active_index = 0
        self.scroll_offset = 0
        self.target_scroll_offset = 0
        self.first_visible_item = 0
        self.mouse_over_index = -1
        self.needs_layout_recalc = True
        self.cached_surface = None
        self.needs_redraw = True
        
    def set_selected_index(self, index, instant_scroll=False):
        """Set the selected index and optionally scroll to it instantly
        
        Args:
            index: The index to select
            instant_scroll: If True, scroll immediately without animation
        """
        if not self.items or index < 0 or index >= len(self.items):
            return
        
        self.selected_index = index
        self.active_index = index
        
        if instant_scroll:
            # Calculate scroll position to center the item
            visible_count = self.get_visible_item_count()
            item_total_size = self.item_size + self.item_spacing
            
            # Try to center the item, but clamp to valid scroll range
            center_scroll = (index - visible_count // 2) * item_total_size
            max_scroll = max(0, (len(self.items) - visible_count) * item_total_size)
            center_scroll = max(0, min(center_scroll, max_scroll))
            
            # Set both current and target to same value for instant scroll
            self.scroll_offset = center_scroll
            self.target_scroll_offset = center_scroll
        else:
            # Animate to visible
            self.ensure_visible(index)
        
        self.needs_redraw = True
    
    def set_background_visible(self, visible):
        """Set whether the list background should be visible"""
        self.show_background = visible
        self.cached_surface = None
        self.needs_redraw = True
        
    def set_border_visible(self, visible):
        """Set whether the list border should be visible"""
        self.show_border = visible
        self.cached_surface = None
        self.needs_redraw = True
        
    def set_background_color(self, color):
        """Set custom background color (None to use theme default)"""
        self.background_color = color
        self.cached_surface = None
        self.needs_redraw = True
        
    def set_border_color(self, color):
        """Set custom border color (None to use theme default)"""
        self.border_color = color
        self.cached_surface = None
        self.needs_redraw = True
                    
    def set_manager(self, manager):
        """Set the UI manager for this component"""
        self.manager = manager
        self.on_manager_set()
        
    def on_manager_set(self):
        """Called when UI manager is set - recalculate layout with proper scaling"""
        self.needs_layout_recalc = True
        self.cached_surface = None
        
    def _calculate_layout(self):
        """Calculate layout dimensions and visible item count"""
        if not self.manager:
            return
            
        # Scale base values
        self.item_size = self.manager.scale_value(self.base_item_size)
        self.item_spacing = self.manager.scale_value(self.base_item_spacing)
        self.arrow_size = self.manager.scale_value(self.base_arrow_size)
        self.margin = self.manager.scale_value(self.base_margin)
        
        # Calculate arrow button rects and items area
        if self.orientation == "horizontal":
            # Horizontal layout: [<][items...][>]
            self.prev_arrow_rect = pygame.Rect(0, 0, self.arrow_size, self.rect.height)
            self.next_arrow_rect = pygame.Rect(
                self.rect.width - self.arrow_size, 0, 
                self.arrow_size, self.rect.height
            )
            
            items_x = self.arrow_size + self.margin
            items_width = self.rect.width - (2 * self.arrow_size) - (2 * self.margin)
            self.items_rect = pygame.Rect(items_x, 0, items_width, self.rect.height)
            
            # Calculate visible items
            item_total_size = self.item_size + self.item_spacing
            self.visible_item_count = max(1, items_width // item_total_size)
            
        else:  # vertical
            # Vertical layout: [^]
            #                  [items...]
            #                  [v]
            self.prev_arrow_rect = pygame.Rect(0, self.margin, self.rect.width, self.arrow_size)
            self.next_arrow_rect = pygame.Rect(
                0, self.rect.height - self.arrow_size - self.margin,
                self.rect.width, self.arrow_size
            )
            
            items_y = self.arrow_size + (2 * self.margin)
            items_height = self.rect.height - (2 * self.arrow_size) - (4 * self.margin)
            self.items_rect = pygame.Rect(0, items_y, self.rect.width, items_height)
            
            # Calculate visible items
            item_total_size = self.item_size + self.item_spacing
            self.visible_item_count = max(1, items_height // item_total_size)
            
        # Set drag threshold
        self.drag_threshold = item_total_size
        
        self.needs_layout_recalc = False
        
    def get_visible_item_count(self):
        """Get the number of items visible in the viewport"""
        if self.needs_layout_recalc:
            self._calculate_layout()
        return self.visible_item_count
        
    def ensure_visible(self, index):
        """Ensure the given item index is visible by scrolling if necessary"""
        if not self.items or index < 0 or index >= len(self.items):
            return
        
        # Don't auto-scroll during drag - let user control scroll
        if self.dragging:
            return
            
        visible_count = self.get_visible_item_count()
        item_total_size = self.item_size + self.item_spacing
        
        # Calculate scroll position needed to show this item
        min_scroll = index * item_total_size
        max_scroll = (index - visible_count + 1) * item_total_size
        
        if self.target_scroll_offset < max_scroll:
            self.target_scroll_offset = max_scroll
        elif self.target_scroll_offset > min_scroll:
            self.target_scroll_offset = min_scroll
            
        # Clamp to valid range
        max_scroll_offset = max(0, (len(self.items) - visible_count) * item_total_size)
        self.target_scroll_offset = max(0, min(self.target_scroll_offset, max_scroll_offset))
        
    def select_previous(self):
        """Select the previous item (immediately sets both navigation and selection)"""
        if self.items and self.selected_index > 0:
            old_active = self.active_index
            self.selected_index -= 1
            self.active_index = self.selected_index  # Immediately set selection for keyboard navigation
            
            # Notify UI manager about keyboard navigation
            if self.manager:
                self.manager.keyboard_navigation_mode = True
                self.manager.last_keyboard_action_time = pygame.time.get_ticks()
            self.ensure_visible(self.selected_index)
            self.prev_arrow_pressed = True
            self.arrow_press_time = pygame.time.get_ticks()
            self.needs_redraw = True
            
            # Notify subclasses of selection change
            if old_active != self.active_index:
                self._on_selection_changed(old_active, self.active_index)
            
    def select_next(self):
        """Select the next item (immediately sets both navigation and selection)"""
        if self.items and self.selected_index < len(self.items) - 1:
            old_active = self.active_index
            self.selected_index += 1
            self.active_index = self.selected_index  # Immediately set selection for keyboard navigation
            
            # Notify UI manager about keyboard navigation
            if self.manager:
                self.manager.keyboard_navigation_mode = True
                self.manager.last_keyboard_action_time = pygame.time.get_ticks()
            self.ensure_visible(self.selected_index)
            self.next_arrow_pressed = True
            self.arrow_press_time = pygame.time.get_ticks()
            self.needs_redraw = True
            
            # Notify subclasses of selection change
            if old_active != self.active_index:
                self._on_selection_changed(old_active, self.active_index)
            
    def activate_current_item(self):
        """Activate the currently focused item (sets selection and calls activation callback)"""
        if 0 <= self.selected_index < len(self.items):
            old_active = self.active_index
            self.active_index = self.selected_index  # Set selection state
            
            # Notify subclasses of selection change
            if old_active != self.active_index:
                self._on_selection_changed(old_active, self.active_index)
                
            # Notify subclasses of activation
            self._on_item_activated(self.selected_index, "keyboard")
            self.needs_redraw = True
            
    def scroll_by_items(self, count):
        """Scroll by a specific number of items (positive = forward, negative = backward)"""
        item_total_size = self.item_size + self.item_spacing
        scroll_distance = count * item_total_size
        
        max_scroll = max(0, (len(self.items) - self.get_visible_item_count()) * item_total_size)
        new_scroll = max(0, min(self.target_scroll_offset + scroll_distance, max_scroll))
        
        if new_scroll != self.target_scroll_offset:
            self.target_scroll_offset = new_scroll
            if count < 0:
                self.prev_arrow_pressed = True
            else:
                self.next_arrow_pressed = True
            self.arrow_press_time = pygame.time.get_ticks()
            self.needs_redraw = True
            
    def _on_selection_changed(self, old_index, new_index):
        """Called when selection changes - override in subclasses"""
        pass
        
    def _on_item_activated(self, index, interaction_type="keyboard"):
        """Called when an item is activated via keyboard - override in subclasses"""
        pass
        
    def _on_item_clicked(self, index, was_already_selected=False):
        """Called when an item is clicked with mouse - override in subclasses
        
        Args:
            index: The index of the clicked item
            was_already_selected: Whether the item was already selected before the click
        """
        # Default behavior: do nothing, just select the item
        pass
        
    def update(self):
        """Update component state"""
        super().update()
        
        current_time = pygame.time.get_ticks()
        dt = (current_time - self.last_scroll_time) / 1000.0 if self.last_scroll_time > 0 else 0
        self.last_scroll_time = current_time
        
        # Handle arrow button press timing
        if (self.prev_arrow_pressed or self.next_arrow_pressed) and self.arrow_press_time > 0:
            if current_time - self.arrow_press_time > 150:  # 150ms press visual feedback
                self.prev_arrow_pressed = False
                self.next_arrow_pressed = False
                self.needs_redraw = True
                
        # Update scroll animation
        if abs(self.scroll_offset - self.target_scroll_offset) > 1:
            scroll_diff = self.target_scroll_offset - self.scroll_offset
            scroll_step = self.scroll_animation_speed * dt
            if abs(scroll_diff) < scroll_step:
                self.scroll_offset = self.target_scroll_offset
            else:
                self.scroll_offset += scroll_step if scroll_diff > 0 else -scroll_step
            self.needs_redraw = True
            
        # Handle mouse hover whenever mouse / touch is the active mode.
        # The hover visual is local state; gating it on self.focused caused
        # the highlight to die after the list lost focus to another scene
        # element, requiring the user to reopen the shop to get it back.
        if runtime_globals.INPUT_MODE in (
            runtime_globals.MOUSE_MODE, runtime_globals.TOUCH_MODE
        ):
            self._handle_mouse_hover()
            
    def _handle_mouse_hover(self):
        """Handle mouse hover for selection changes"""
        if not self.rect or not (runtime_globals.INPUT_MODE in [runtime_globals.MOUSE_MODE, runtime_globals.TOUCH_MODE]):
            return
            
        # Don't change focus during drag
        if self.dragging or (hasattr(runtime_globals.game_input, 'is_dragging') and 
                           runtime_globals.game_input.is_dragging()):
            return
            
        mouse_pos = runtime_globals.game_input.get_mouse_position()
        relative_pos = (mouse_pos[0] - self.rect.x, mouse_pos[1] - self.rect.y)
        
        # Check if mouse is within component bounds
        if not (0 <= relative_pos[0] < self.rect.width and 0 <= relative_pos[1] < self.rect.height):
            if self.mouse_over_index != -1:
                self.mouse_over_index = -1
                self.needs_redraw = True
            return
            
        # Calculate which item is being hovered
        if self.items_rect and self.items_rect.collidepoint(relative_pos):
            if self.orientation == "horizontal":
                local_pos = relative_pos[0] - self.items_rect.x
                item_index = int((local_pos + self.scroll_offset) // (self.item_size + self.item_spacing))
            else:  # vertical
                local_pos = relative_pos[1] - self.items_rect.y
                item_index = int((local_pos + self.scroll_offset) // (self.item_size + self.item_spacing))
                
            if 0 <= item_index < len(self.items):
                if self.mouse_over_index != item_index:
                    self.mouse_over_index = item_index
                    self.needs_redraw = True
            else:
                if self.mouse_over_index != -1:
                    self.mouse_over_index = -1
                    self.needs_redraw = True
        else:
            if self.mouse_over_index != -1:
                self.mouse_over_index = -1
                self.needs_redraw = True
                
    def handle_scroll(self, event):
        """Mouse wheel scroll handler — UIManager dispatches SCROLL events
        here directly when the cursor is over this component, regardless
        of focus state.  Returning True consumes the event.
        """
        if not self.items:
            return False
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        event_type, event_data = event
        if event_type != "SCROLL" or not event_data:
            return False
        direction = event_data.get("direction")
        if direction == "UP":
            if self.orientation == "horizontal":
                self.select_previous()
            else:
                self.scroll_by_items(-1)
        elif direction == "DOWN":
            if self.orientation == "horizontal":
                self.select_next()
            else:
                self.scroll_by_items(1)
        else:
            return False
        runtime_globals.game_sound.play("menu")
        return True

    def handle_event(self, event):
        """Handle input events - now expects tuple-based events"""
        event_type, event_data = event

        if not self.items:
            return False

        # Also accept SCROLL via handle_event for paths that route everything
        # through the focused component.  Duplicates handle_scroll but is
        # cheap and keeps both routing styles working.
        if event_type == "SCROLL" and event_data:
            return self.handle_scroll(event)

        if not self.focused:
            return False
            
        # Handle directional inputs
        if self.orientation == "horizontal":
            if event_type == "LEFT":
                if self.selected_index <= 0:
                    return False  # At boundary — let UIManager move focus out
                self.select_previous()
                runtime_globals.game_sound.play("menu")
                return True
            elif event_type == "RIGHT":
                if self.selected_index >= len(self.items) - 1:
                    return False  # At boundary — let UIManager move focus out
                self.select_next()
                runtime_globals.game_sound.play("menu")
                return True
        else:  # vertical
            if event_type == "UP":
                if self.selected_index <= 0:
                    return False  # At boundary — let UIManager move focus out
                self.select_previous()
                runtime_globals.game_sound.play("menu")
                return True
            elif event_type == "DOWN":
                if self.selected_index >= len(self.items) - 1:
                    return False  # At boundary — let UIManager move focus out
                self.select_next()
                runtime_globals.game_sound.play("menu")
                return True
                
        # Handle action buttons
        if event_type in ["A", "ENTER"]:
            # For keyboard, just activate the already-selected item
            current_time = pygame.time.get_ticks()
            
            # Prevent activation if it's immediately after a mouse click (within 500ms)
            if current_time - self.last_mouse_click_time < 500:
                return False
                
            if 0 <= self.selected_index < len(self.items):
                # Just notify activation since selection already happened in select_previous/next
                self._on_item_activated(self.selected_index, "keyboard")
                runtime_globals.game_sound.play("menu")
                return True
                
        # Handle mouse click
        elif event_type == "LCLICK":
            if event_data and "pos" in event_data:
                mouse_pos = event_data["pos"]
                if self.rect.collidepoint(mouse_pos):
                    # Check if mouse is over an item (mouse_over_index is set by _handle_mouse_hover)
                    if self.mouse_over_index >= 0 and self.mouse_over_index < len(self.items):
                        # Check if clicking on already selected item
                        was_already_selected = (self.selected_index == self.mouse_over_index)
                        
                        # Update selection indices
                        old_active = self.active_index
                        self.active_index = self.mouse_over_index
                        self.selected_index = self.mouse_over_index
                        self.last_mouse_click_time = pygame.time.get_ticks()
                        
                        # Notify subclasses of selection change
                        if old_active != self.active_index:
                            self._on_selection_changed(old_active, self.active_index)
                        
                        # Notify subclasses of click
                        self._on_item_clicked(self.mouse_over_index, was_already_selected)
                        runtime_globals.game_sound.play("menu")
                        self.needs_redraw = True
                        return True
                        
        # Handle scroll events
        elif event_type == "SCROLL":
            if event_data:
                direction = event_data.get("direction")
                # Check if mouse is over this list (using last known mouse position)
                mouse_pos = runtime_globals.game_input.get_mouse_position()
                if self.rect.collidepoint(mouse_pos):
                    if direction == "UP":
                        if self.orientation == "horizontal":
                            self.select_previous()
                        else:
                            self.scroll_by_items(-1)
                    elif direction == "DOWN":
                        if self.orientation == "horizontal":
                            self.select_next()
                        else:
                            self.scroll_by_items(1)
                    runtime_globals.game_sound.play("menu")
                    return True
                    
        # Drag events are handled by handle_drag() method, not here
        # This prevents double-handling when both handle_event and handle_drag are called
                
        # Handle mouse motion for hover
        if event_type == "MOUSE_MOTION":
            if event_data and "pos" in event_data:
                # _handle_mouse_hover is called from update(), not from events
                pass
                
        return False
    
    def handle_drag(self, event):
        """Handle drag events from ui_manager"""
        if not isinstance(event, tuple) or len(event) != 2:
            return False
        
        event_type, event_data = event
        
        if not (runtime_globals.INPUT_MODE in [runtime_globals.MOUSE_MODE, runtime_globals.TOUCH_MODE]):
            return False
        
        if event_type == "DRAG_START":
            if event_data and "pos" in event_data:
                mouse_pos = event_data["pos"]
                if self.rect.collidepoint(mouse_pos):
                    self.dragging = True
                    self.drag_start_pos = mouse_pos
                    self.drag_start_scroll = self.scroll_offset
                    self.drag_accumulated = 0
                    self._last_drag_distance = 0
                    return True
                    
        elif event_type == "DRAG_MOTION":
            if self.dragging and event_data and "pos" in event_data:
                return self._handle_drag_motion(event_data["pos"])
                
        elif event_type == "DRAG_END":
            if self.dragging:
                self.dragging = False
                return True
        
        return False
        
    def _handle_mouse_click(self, mouse_pos):
        """Handle mouse click events"""
        local_pos = (mouse_pos[0] - self.rect.x, mouse_pos[1] - self.rect.y)
        
        # Check arrow clicks
        if self.prev_arrow_rect and self.prev_arrow_rect.collidepoint(local_pos):
            if self.orientation == "horizontal":
                self.select_previous()
            else:
                self.scroll_by_items(-1)
            runtime_globals.game_sound.play("menu")
            return True
            
        elif self.next_arrow_rect and self.next_arrow_rect.collidepoint(local_pos):
            if self.orientation == "horizontal":
                self.select_next()
            else:
                self.scroll_by_items(1)
            runtime_globals.game_sound.play("menu")
            return True
            
        elif self.items_rect and self.items_rect.collidepoint(local_pos):
            # Calculate which item was clicked
            if self.orientation == "horizontal":
                item_pos = local_pos[0] - self.items_rect.x + self.scroll_offset
            else:
                item_pos = local_pos[1] - self.items_rect.y + self.scroll_offset
                
            item_index = int(item_pos // (self.item_size + self.item_spacing))
            
            if 0 <= item_index < len(self.items):
                # Check if clicking on already selected item
                was_already_selected = (self.selected_index == item_index)
                
                # Mouse click sets SELECTION (active_index) and NAVIGATION (selected_index)
                old_active = self.active_index
                self.active_index = item_index  # Set selection state (persistent)
                self.selected_index = item_index  # Set navigation state (for keyboard)
                self.last_mouse_click_time = pygame.time.get_ticks()  # Record mouse click time
                
                # Notify subclasses of selection change
                if old_active != self.active_index:
                    self._on_selection_changed(old_active, self.active_index)
                    
                # Notify subclasses of click with the selection state
                self._on_item_clicked(item_index, was_already_selected)
                runtime_globals.game_sound.play("menu")
                self.needs_redraw = True
                return True
            else:
                # Click on empty space within items area - just consume the event
                self.last_mouse_click_time = pygame.time.get_ticks()  # Record to prevent spurious A actions
                return True
                
        return False
        
    def _handle_drag_motion(self, mouse_pos):
        """Handle drag motion for touch scrolling"""
        if not self.dragging:
            return False
            
        # Calculate drag distance from current scroll position
        if self.orientation == "horizontal":
            drag_delta = self.drag_start_pos[0] - mouse_pos[0]
        else:
            drag_delta = self.drag_start_pos[1] - mouse_pos[1]
        
        # Apply scroll directly based on drag delta
        new_scroll = self.drag_start_scroll + drag_delta
        
        # Clamp scroll to valid range
        visible_count = self.get_visible_item_count()
        max_scroll = max(0, (len(self.items) - visible_count) * (self.item_size + self.item_spacing))
        new_scroll = max(0, min(new_scroll, max_scroll))
        
        # Apply scroll immediately for responsive dragging
        self.scroll_offset = new_scroll
        self.target_scroll_offset = new_scroll
        self.needs_redraw = True
        
        return True
        
    def render(self):
        """Render the list component"""
        if self.needs_layout_recalc:
            self._calculate_layout()
            
        # Check if we need to rebuild cache
        current_key = (
            self.scroll_offset, 
            self.selected_index, 
            self.active_index,
            self.mouse_over_index,
            len(self.items),
            self.prev_arrow_pressed,
            self.next_arrow_pressed
        )
        
        if self.cached_surface is None or current_key != self.cache_key:
            self.cached_surface = self._render_to_cache()
            self.cache_key = current_key
            
        return self.cached_surface
        
    def _render_to_cache(self):
        """Render the component to cached surface - override in subclasses"""
        surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        
        if not self.manager:
            return surface
            
        colors = self.manager.get_theme_colors()
        
        # Draw arrow buttons
        if self.prev_arrow_rect:
            self._draw_arrow(surface, self.prev_arrow_rect, "prev", self.prev_arrow_pressed)
        if self.next_arrow_rect:
            self._draw_arrow(surface, self.next_arrow_rect, "next", self.next_arrow_pressed)
            
        # Draw items area background (if enabled)
        if self.items_rect and self.show_background:
            bg_color = self.background_color if self.background_color else colors["bg"]
            pygame.draw.rect(surface, bg_color, self.items_rect)

        # Draw items area border (if enabled)
        if self.items_rect and self.show_border:
            border_color = self.border_color if self.border_color else colors["fg"]
            pygame.draw.rect(surface, border_color, self.items_rect, 1)

        # Clip item drawing to items_rect so tall items can't overflow into
        # the prev/next arrow strips (this was hiding the bottom arrow when
        # the first item was focused).
        if self.items_rect:
            prev_clip = surface.get_clip()
            surface.set_clip(self.items_rect)
            try:
                self._draw_items(surface)
            finally:
                surface.set_clip(prev_clip)
        else:
            self._draw_items(surface)

        return surface
        
    def _draw_arrow(self, surface, rect, direction, pressed):
        """Draw navigation arrow button"""
        colors = self.manager.get_theme_colors()
        
        # Color logic
        if pressed:
            bg_color = colors["highlight"]
            fg_color = colors["bg"]
            line_color = fg_color
        else:
            bg_color = colors["bg"]
            fg_color = colors["fg"]
            line_color = colors.get("black", colors["fg"])
            
        # Draw background
        pygame.draw.rect(surface, bg_color, rect)
        pygame.draw.rect(surface, line_color, rect, width=1)
        
        # Draw arrow triangle
        center_x = rect.centerx
        center_y = rect.centery
        size = min(rect.width, rect.height) // 4
        
        if self.orientation == "horizontal":
            if direction == "prev":  # left arrow
                points = [
                    (center_x + size//2, center_y - size),
                    (center_x + size//2, center_y + size),
                    (center_x - size//2, center_y)
                ]
            else:  # next = right arrow
                points = [
                    (center_x - size//2, center_y - size),
                    (center_x - size//2, center_y + size),
                    (center_x + size//2, center_y)
                ]
        else:  # vertical
            if direction == "prev":  # up arrow
                points = [
                    (center_x - size, center_y + size//2),
                    (center_x + size, center_y + size//2),
                    (center_x, center_y - size//2)
                ]
            else:  # next = down arrow
                points = [
                    (center_x - size, center_y - size//2),
                    (center_x + size, center_y - size//2),
                    (center_x, center_y + size//2)
                ]
                
        pygame.draw.polygon(surface, fg_color, points)
        
    def _draw_items(self, surface):
        """Draw the items - override in subclasses for custom rendering"""
        if not self.items or not self.items_rect:
            return
            
        colors = self.manager.get_theme_colors()
        
        # Calculate visible range
        item_total_size = self.item_size + self.item_spacing
        first_visible = max(0, int(self.scroll_offset // item_total_size))
        last_visible = min(len(self.items), first_visible + self.get_visible_item_count() + 2)
        
        for i in range(first_visible, last_visible):
            if i >= len(self.items):
                break
                
            item = self.items[i]
            
            # Calculate item position
            if self.orientation == "horizontal":
                item_x = self.items_rect.x + (i * item_total_size) - self.scroll_offset
                item_y = self.items_rect.y
                item_rect = pygame.Rect(item_x, item_y, self.item_size, self.items_rect.height)
            else:  # vertical
                item_x = self.items_rect.x
                item_y = self.items_rect.y + (i * item_total_size) - self.scroll_offset
                item_rect = pygame.Rect(item_x, item_y, self.items_rect.width, self.item_size)
                
            # Skip if completely outside visible area
            if self.orientation == "horizontal":
                if item_x + self.item_size < self.items_rect.x or item_x > self.items_rect.right:
                    continue
            else:
                if item_y + self.item_size < self.items_rect.y or item_y > self.items_rect.bottom:
                    continue
                    
            # Determine item state and colors
            is_selected = (i == self.selected_index)
            is_active = (i == self.active_index)
            is_hovered = (i == self.mouse_over_index)
            
            if is_selected and self.focused:
                bg_color = colors["highlight"]
                text_color = colors["bg"]
                border_color = colors["bg"]
            elif is_selected or is_hovered:
                bg_color = colors["bg"]
                text_color = colors["highlight"]
                border_color = colors["highlight"]
            else:
                bg_color = colors["bg"]
                text_color = colors["fg"]
                border_color = colors["fg"]
                
            # Draw item background
            pygame.draw.rect(surface, bg_color, item_rect)
            pygame.draw.rect(surface, border_color, item_rect, 1)
            
            # Draw item content - default implementation draws text
            if hasattr(item, 'name'):
                font = self.get_font("text")
                if font:
                    text_surface = font.render(str(item.name), True, text_color)
                    text_rect = text_surface.get_rect(center=item_rect.center)
                    blit_with_cache(surface, text_surface, text_rect.topleft)
            elif isinstance(item, (str, int, float)):
                font = self.get_font("text")
                if font:
                    text_surface = font.render(str(item), True, text_color)
                    text_rect = text_surface.get_rect(center=item_rect.center)
                    blit_with_cache(surface, text_surface, text_rect.topleft)
                    
    def get_item_rect(self, index):
        """Get the rect for a specific item (relative to component)"""
        if index < 0 or index >= len(self.items) or not self.items_rect:
            return None
            
        item_total_size = self.item_size + self.item_spacing
        
        if self.orientation == "horizontal":
            item_x = self.items_rect.x + (index * item_total_size) - self.scroll_offset
            item_y = self.items_rect.y
            return pygame.Rect(item_x, item_y, self.item_size, self.items_rect.height)
        else:  # vertical
            item_x = self.items_rect.x
            item_y = self.items_rect.y + (index * item_total_size) - self.scroll_offset
            return pygame.Rect(item_x, item_y, self.items_rect.width, self.item_size)
            
    def get_focused_sub_rect(self):
        """Get the rect of the currently focused item for highlighting"""
        if not self.items or self.selected_index < 0 or self.selected_index >= len(self.items):
            return None
            
        # Get the item rect relative to the component
        item_rect = self.get_item_rect(self.selected_index)
        if not item_rect:
            return None
            
        # Convert to screen coordinates
        screen_rect = pygame.Rect(
            self.rect.x + item_rect.x,
            self.rect.y + item_rect.y,
            item_rect.width,
            item_rect.height
        )
        
        return screen_rect
        
    def get_mouse_sub_rect(self, mouse_pos):
        """Get the rect for the item under the mouse cursor"""
        if not self.items:
            return None
            
        # Convert to component-relative coordinates
        relative_x = mouse_pos[0] - self.rect.x
        relative_y = mouse_pos[1] - self.rect.y
        
        # Check if mouse is within component bounds
        if not (0 <= relative_x < self.rect.width and 0 <= relative_y < self.rect.height):
            return None
            
        # If we have a valid mouse over index, use it
        if 0 <= self.mouse_over_index < len(self.items):
            item_rect = self.get_item_rect(self.mouse_over_index)
            if item_rect:
                return pygame.Rect(
                    self.rect.x + item_rect.x,
                    self.rect.y + item_rect.y,
                    item_rect.width,
                    item_rect.height
                )
        
        # Mouse is over the component but not over a specific item
        # Hide the highlight by returning None
        return None
"""
Input Event System
==================

Unified event format for all input types (keyboard, mouse, touch, joystick).

All events are returned as tuples: (event_type, event_data)
- event_type: str from InputEventType enum
- event_data: dict with event-specific data, or None for simple events

Examples:
    ("UP", None)
    ("LCLICK", {"pos": (100, 200)})
    ("DRAG_MOTION", {"pos": (150, 250), "start_pos": (100, 200), "distance": 70.7})
    ("SCROLL", {"amount": 1, "direction": "UP"})
"""

from enum import Enum
from typing import Tuple, Optional, Dict, Any


class InputEventType(str, Enum):
    """
    Enumeration of all possible input event types.
    Using str Enum for easy comparison and serialization.
    """
    # Directional inputs (keyboard/joystick D-pad/hat)
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    
    # Action buttons
    A = "A"
    B = "B"
    START = "START"
    SELECT = "SELECT"
    
    # Analog stick directions (from joystick)
    ANALOG_UP = "ANALOG_UP"
    ANALOG_DOWN = "ANALOG_DOWN"
    ANALOG_LEFT = "ANALOG_LEFT"
    ANALOG_RIGHT = "ANALOG_RIGHT"
    
    # Mouse button events
    LCLICK = "LCLICK"          # Left mouse button up (completed click)
    RCLICK = "RCLICK"          # Right mouse button up
    MOUSE_MOTION = "MOUSE_MOTION"  # Mouse moved (for hover detection)
    
    # Drag events (mouse/touch)
    DRAG_START = "DRAG_START"      # Drag initiated (threshold exceeded)
    DRAG_MOTION = "DRAG_MOTION"    # Drag in progress
    DRAG_END = "DRAG_END"          # Drag completed
    
    # Scroll events
    SCROLL = "SCROLL"
    
    # Debug function keys
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"


# Type alias for input events
InputEvent = Tuple[str, Optional[Dict[str, Any]]]


# ============================================================================
# Event Creation Helpers
# ============================================================================

def create_simple_event(event_type: str) -> InputEvent:
    """
    Create a simple event with no data (keyboard, joystick buttons).
    
    Args:
        event_type: Event type from InputEventType enum
        
    Returns:
        Tuple (event_type, None)
    """
    return (event_type, None)


def create_click_event(event_type: str, pos: Tuple[int, int], extra_data: Optional[Dict[str, Any]] = None) -> InputEvent:
    """
    Create a mouse click event.
    
    Args:
        event_type: "LCLICK" or "RCLICK"
        pos: Mouse position (x, y)
        
    Returns:
        Tuple (event_type, {"pos": (x, y), **extra_data})
    """
    data: Dict[str, Any] = {"pos": pos}
    if extra_data:
        data.update(extra_data)
    return (event_type, data)


def create_motion_event(pos: Tuple[int, int]) -> InputEvent:
    """
    Create a mouse motion event.
    
    Args:
        pos: Mouse position (x, y)
        
    Returns:
        Tuple ("MOUSE_MOTION", {"pos": (x, y)})
    """
    return (InputEventType.MOUSE_MOTION, {"pos": pos})


def create_drag_start_event(pos: Tuple[int, int]) -> InputEvent:
    """
    Create a drag start event.
    
    Args:
        pos: Starting position (x, y)
        
    Returns:
        Tuple ("DRAG_START", {"pos": (x, y)})
    """
    return (InputEventType.DRAG_START, {"pos": pos})


def create_drag_motion_event(
    pos: Tuple[int, int], 
    start_pos: Tuple[int, int], 
    distance: float
) -> InputEvent:
    """
    Create a drag motion event.
    
    Args:
        pos: Current position (x, y)
        start_pos: Starting position (x, y)
        distance: Distance from start position
        
    Returns:
        Tuple ("DRAG_MOTION", {"pos": (x, y), "start_pos": (x, y), "distance": float})
    """
    return (InputEventType.DRAG_MOTION, {
        "pos": pos,
        "start_pos": start_pos,
        "distance": distance
    })


def create_drag_end_event(pos: Tuple[int, int], start_pos: Tuple[int, int]) -> InputEvent:
    """
    Create a drag end event.
    
    Args:
        pos: Ending position (x, y)
        start_pos: Starting position (x, y)
        
    Returns:
        Tuple ("DRAG_END", {"pos": (x, y), "start_pos": (x, y)})
    """
    return (InputEventType.DRAG_END, {
        "pos": pos,
        "start_pos": start_pos
    })


def create_scroll_event(amount: int, direction: str) -> InputEvent:
    """
    Create a scroll event.
    
    Args:
        amount: Scroll amount (typically 1 or -1)
        direction: "UP" or "DOWN"
        
    Returns:
        Tuple ("SCROLL", {"amount": int, "direction": str})
    """
    return (InputEventType.SCROLL, {
        "amount": amount,
        "direction": direction
    })


# ============================================================================
# Event Data Access Helpers
# ============================================================================

def get_event_type(event: InputEvent) -> str:
    """
    Get the event type from an input event.
    
    Args:
        event: Input event tuple
        
    Returns:
        Event type string
    """
    return event[0]


def get_event_data(event: InputEvent) -> Optional[Dict[str, Any]]:
    """
    Get the event data from an input event.
    
    Args:
        event: Input event tuple
        
    Returns:
        Event data dict or None
    """
    return event[1]


def get_event_pos(event: InputEvent) -> Optional[Tuple[int, int]]:
    """
    Get position from an event that contains position data.
    
    Args:
        event: Input event tuple
        
    Returns:
        Position tuple (x, y) or None if no position data
    """
    data = get_event_data(event)
    return data.get("pos") if data else None


def is_event_type(event: InputEvent, event_type: str) -> bool:
    """
    Check if an event is of a specific type.
    
    Args:
        event: Input event tuple
        event_type: Event type to check against
        
    Returns:
        True if event matches type
    """
    return get_event_type(event) == event_type


def is_directional_event(event: InputEvent) -> bool:
    """
    Check if event is a directional input (UP/DOWN/LEFT/RIGHT).
    
    Args:
        event: Input event tuple
        
    Returns:
        True if event is directional
    """
    event_type = get_event_type(event)
    return event_type in (
        InputEventType.UP, InputEventType.DOWN, 
        InputEventType.LEFT, InputEventType.RIGHT
    )


def is_action_event(event: InputEvent) -> bool:
    """
    Check if event is an action button (A/B/START/SELECT).
    
    Args:
        event: Input event tuple
        
    Returns:
        True if event is action button
    """
    event_type = get_event_type(event)
    return event_type in (
        InputEventType.A, InputEventType.B, 
        InputEventType.START, InputEventType.SELECT
    )


def is_mouse_event(event: InputEvent) -> bool:
    """
    Check if event is a mouse event (click, motion, drag, scroll).
    
    Args:
        event: Input event tuple
        
    Returns:
        True if event is mouse-related
    """
    event_type = get_event_type(event)
    return event_type in (
        InputEventType.LCLICK, InputEventType.RCLICK,
        InputEventType.MOUSE_MOTION,
        InputEventType.DRAG_START, InputEventType.DRAG_MOTION, InputEventType.DRAG_END,
        InputEventType.SCROLL
    )


def is_drag_event(event: InputEvent) -> bool:
    """
    Check if event is a drag event.
    
    Args:
        event: Input event tuple
        
    Returns:
        True if event is drag-related
    """
    event_type = get_event_type(event)
    return event_type in (
        InputEventType.DRAG_START, InputEventType.DRAG_MOTION, InputEventType.DRAG_END
    )

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class QuestData:
    """
    Data class for quest definitions loaded from JSON.
    This represents the template/definition of a quest, not an active quest instance.
    """
    id: str
    name: str
    type: int
    target_amount_range: Optional[List[int]] = None
    target_amount: Optional[int] = None
    reward_type: int = 0
    reward_value: Optional[str] = None
    reward_item: Optional[str] = None
    reward_quantity: int = 1
    reward_amount: int = 1


@dataclass
class EventData:
    """
    Data class for event definitions loaded from JSON.
    This represents the template/definition of an event, not an active event instance.
    """
    id: str
    name: str
    global_event: bool = False
    type: int = 0
    chance_percent: int = 1
    area: int = 1
    round: int = 1
    item: str = ""
    item_quantity: int = 1

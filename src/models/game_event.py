from enum import Enum


class EventType(Enum):
    ENEMY_BATTLE = 0
    ITEM_PACKAGE = 1


class GameEvent:
    """
    Represents a random event that can occur during gameplay.
    """
    
    def __init__(self, event_id: str, name: str, module: str, global_event: bool, 
                 event_type: EventType, chance_percent: int, area: int, round_num: int,
                 item: str = "", item_quantity: int = 1):
        self.id = event_id
        self.name = name
        self.module = module
        self.global_event = global_event
        self.type = event_type
        self.chance_percent = chance_percent
        self.area = area
        self.round = round_num
        self.item = item
        self.item_quantity = item_quantity
    
    def __str__(self) -> str:
        if self.type == EventType.ITEM_PACKAGE:
            return f"{self.name}: {self.item} x{self.item_quantity}"
        else:
            return f"{self.name}: Battle Event in Area {self.area}"

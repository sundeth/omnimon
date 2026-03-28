from dataclasses import dataclass

@dataclass
class GameItem:
    id: str
    name: str
    description: str
    sprite_name: str
    module: str
    effect: str
    status: str
    amount: int
    boost_time: int
    component_item: str

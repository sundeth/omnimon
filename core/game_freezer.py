from dataclasses import dataclass, field
from typing import List, Optional
from core.game_pet import GamePet


@dataclass
class GameFreezer:
    pets: List[Optional[GamePet]]  # Add this field
    page: int
    background: str
    background_module: str
    game_mode: int = -1  # -1 = legacy/unknown (treated as free), 0 = free, 1 = progress

    pet_grid: List[List[Optional[GamePet]]] = field(init=False)

    def __post_init__(self):
        self.rebuild()

    def rebuild(self):
        grid_size = 5
        self.pet_grid = []
        for i in range(0, grid_size * grid_size, grid_size):
            row = self.pets[i:i + grid_size]
            if len(row) < grid_size:
                row += [None] * (grid_size - len(row))
            self.pet_grid.append(row)
        while len(self.pet_grid) < grid_size:
            self.pet_grid.append([None] * grid_size)

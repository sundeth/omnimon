from dataclasses import dataclass

import pygame

@dataclass
class GameEvolutionEntity:
    from_name: str
    from_sprite: pygame.surface
    from_attribute: str
    to_name: str
    to_sprite: pygame.surface
    to_attribute: str
    stage: int
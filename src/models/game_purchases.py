"""
GamePurchases - Tracks purchased items from the shop.
Stores purchase IDs per category for modules, cosmetics, gameplay, items, and specials.
Items are consumable and track quantity.
"""
from dataclasses import dataclass, field
from typing import Dict, Set, Optional
import json


@dataclass
class GamePurchases:
    """
    Tracks all shop purchases for the player.
    
    Attributes:
        modules: Set of purchased module IDs (GUIDs)
        module_names: Set of purchased module local names (for egg selection filtering)
        cosmetics: Set of purchased cosmetic IDs (GUIDs) 
        gameplay: Set of purchased gameplay feature IDs (GUIDs)
        items: Dict mapping item ID to quantity (consumable items)
        specials: Set of purchased special item IDs (GUIDs)
    """
    modules: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    cosmetics: Set[str] = field(default_factory=set)
    gameplay: Set[str] = field(default_factory=set)
    items: Dict[str, int] = field(default_factory=dict)  # item_id -> quantity
    specials: Set[str] = field(default_factory=set)
    
    def owns_module(self, module_id: str) -> bool:
        """Check if player owns a module."""
        return module_id in self.modules
    
    def owns_cosmetic(self, cosmetic_id: str) -> bool:
        """Check if player owns a cosmetic."""
        return cosmetic_id in self.cosmetics
    
    def owns_gameplay(self, gameplay_id: str) -> bool:
        """Check if player owns a gameplay feature."""
        return gameplay_id in self.gameplay
    
    def owns_special(self, special_id: str) -> bool:
        """Check if player owns a special item."""
        return special_id in self.specials
    
    def get_item_quantity(self, item_id: str) -> int:
        """Get quantity of a consumable item."""
        return self.items.get(item_id, 0)
    
    def has_item(self, item_id: str) -> bool:
        """Check if player has at least one of an item."""
        return self.get_item_quantity(item_id) > 0
    
    def owns_module_name(self, module_name: str) -> bool:
        """Check if player owns a module by its local name."""
        return module_name in self.module_names

    def add_module(self, module_id: str, module_name: str = None) -> None:
        """Add a purchased module.
        
        Args:
            module_id: Shop GUID for the module
            module_name: Optional local module name for egg selection filtering
        """
        self.modules.add(module_id)
        if module_name:
            self.module_names.add(module_name)
    
    def add_cosmetic(self, cosmetic_id: str) -> None:
        """Add a purchased cosmetic."""
        self.cosmetics.add(cosmetic_id)
    
    def add_gameplay(self, gameplay_id: str) -> None:
        """Add a purchased gameplay feature."""
        self.gameplay.add(gameplay_id)
    
    def add_special(self, special_id: str) -> None:
        """Add a purchased special item."""
        self.specials.add(special_id)
    
    def add_item(self, item_id: str, quantity: int = 1) -> None:
        """Add consumable items (stacks with existing quantity)."""
        current = self.items.get(item_id, 0)
        self.items[item_id] = current + quantity
    
    def use_item(self, item_id: str, quantity: int = 1) -> bool:
        """
        Use a consumable item.
        
        Returns:
            True if item was used, False if insufficient quantity
        """
        current = self.items.get(item_id, 0)
        if current < quantity:
            return False
        
        self.items[item_id] = current - quantity
        
        # Remove item if quantity reaches 0
        if self.items[item_id] <= 0:
            del self.items[item_id]
        
        return True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'modules': list(self.modules),
            'module_names': list(self.module_names),
            'cosmetics': list(self.cosmetics),
            'gameplay': list(self.gameplay),
            'items': self.items.copy(),
            'specials': list(self.specials),
        }
    
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> 'GamePurchases':
        """Create from dictionary (for deserialization)."""
        if not data:
            return cls()
        
        return cls(
            modules=set(data.get('modules', [])),
            module_names=set(data.get('module_names', [])),
            cosmetics=set(data.get('cosmetics', [])),
            gameplay=set(data.get('gameplay', [])),
            items=data.get('items', {}),
            specials=set(data.get('specials', [])),
        )
    
    def __repr__(self) -> str:
        return (f"GamePurchases(modules={len(self.modules)}, cosmetics={len(self.cosmetics)}, "
                f"gameplay={len(self.gameplay)}, items={len(self.items)}, specials={len(self.specials)})")

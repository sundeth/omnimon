from core import game_globals, runtime_globals

def get_inventory_value(item_id):
    """
    Returns the quantity of the item with the given id, or 0 if not present.
    """
    return game_globals.inventory.get(item_id, 0)

def add_to_inventory(item_id, amount=1):
    """
    Adds the specified amount of the item to the inventory.
    """
    game_globals.inventory[item_id] = game_globals.inventory.get(item_id, 0) + amount

def remove_from_inventory(item_id, amount=1):
    """
    Removes the specified amount of the item from the inventory.
    """
    if item_id in game_globals.inventory:
        game_globals.inventory[item_id] -= amount
        if game_globals.inventory[item_id] <= 0:
            del game_globals.inventory[item_id]

def get_item_by_id(item_id):
    """
    Gets an item object by item ID across all modules.
    Returns the item object if found, None otherwise.
    """
    # Search through all loaded modules for the item
    for module_name, module in runtime_globals.game_modules.items():
        # Check if module has items
        if hasattr(module, "items"):
            # Search for item by ID
            for item in module.items:
                if item.id == item_id:
                    return item
    
    return None

def get_item_by_name(module_name, item_name):
    """
    Gets an item object by module name and item name.
    Returns the item object if found, None otherwise.
    """
    # Check if module exists
    if module_name not in runtime_globals.game_modules:
        return None
    
    module = runtime_globals.game_modules[module_name]
    
    # Check if module has items
    if not hasattr(module, "items"):
        return None
    
    # Search for item by name
    for item in module.items:
        if item.name == item_name:
            return item
    
    return None
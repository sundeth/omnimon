from core import game_globals, runtime_globals


def _shop_purchases_items():
    """Return the GamePurchases.items dict if available, else None."""
    purchases = getattr(game_globals, 'purchases', None)
    if purchases is None:
        return None
    return getattr(purchases, 'items', None)


def get_inventory_value(item_id):
    """
    Returns the quantity of the item with the given id, or 0 if not present.

    Module inventories are checked first; if the id isn't there we fall
    back to shop-purchased items so cross-module shop items show the right
    quantity wherever this helper is used.
    """
    amount = game_globals.inventory.get(item_id, 0)
    if amount:
        return amount
    shop_items = _shop_purchases_items()
    if shop_items is not None:
        return shop_items.get(item_id, 0)
    return 0


def add_to_inventory(item_id, amount=1):
    """
    Adds the specified amount of the item to the inventory.

    If the item id is already tracked in shop purchases, the increment
    goes there to keep shop-item counts consistent across modules.
    """
    shop_items = _shop_purchases_items()
    if shop_items is not None and item_id in shop_items:
        shop_items[item_id] = shop_items.get(item_id, 0) + amount
        return
    game_globals.inventory[item_id] = game_globals.inventory.get(item_id, 0) + amount


def remove_from_inventory(item_id, amount=1):
    """
    Removes the specified amount of the item from the inventory.

    Shop-purchased items are decremented from purchases.items instead of
    the per-module inventory dict.
    """
    if item_id in game_globals.inventory:
        game_globals.inventory[item_id] -= amount
        if game_globals.inventory[item_id] <= 0:
            del game_globals.inventory[item_id]
        return
    shop_items = _shop_purchases_items()
    if shop_items is not None and item_id in shop_items:
        shop_items[item_id] = max(0, shop_items.get(item_id, 0) - amount)
        if shop_items[item_id] <= 0:
            del shop_items[item_id]

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
from core import game_globals, runtime_globals

# Use a single list of unlocks per module, each unlock has a "type" field
def ensure_module_key(module: str):
    if not isinstance(module, str):
        runtime_globals.game_console.log(f"[Unlocks] Invalid module key: {module} (type: {type(module)})")
        return
    if module not in game_globals.unlocks:
        game_globals.unlocks[module] = []

def unlock_item(module: str, unlock_type: str, name: str, label: str = None):
    """
    Unlocks an item (egg, background, evolution, etc) for a specific module,
    but only if it exists in the module's unlockables.
    """
    ensure_module_key(module)
    # Find the item in the module's unlocks
    module_obj = runtime_globals.game_modules.get(module)
    unlocks = getattr(module_obj, "unlocks", []) if module_obj else []
    unlock_data = None
    for unlock in unlocks:
        if unlock.get("type") == unlock_type and unlock.get("name") == name:
            unlock_data = unlock
            break
    if not unlock_data:
        # Do not unlock if not present in module's unlockables
        runtime_globals.game_console.log(f"[Unlocks] Tried to unlock missing item: {module} {unlock_type} {name}")
        return
    # Only add if not already unlocked
    if not any(isinstance(u, dict) and u.get("type") == unlock_type and u.get("name") == name for u in game_globals.unlocks[module]):
        unlock_entry = {"type": unlock_type, "name": name}
        entry_label = label if label else unlock_data.get("label", name)
        if entry_label:
            unlock_entry["label"] = entry_label
        game_globals.unlocks[module].append(unlock_entry)
        runtime_globals.game_message.add_slide(f"{entry_label} unlocked!", (255, 255, 0), 56 * runtime_globals.UI_SCALE, runtime_globals.FONT_SIZE_SMALL)

        # --- Group unlock logic ---
        # After unlocking, check for group unlocks in this module
        for group_unlock in unlocks:
            if group_unlock.get("type") == "group" and isinstance(group_unlock.get("list"), list):
                group_list = group_unlock["list"]
                # If the just-unlocked item is in the group list
                if name in group_list:
                    # Check if all items in the group list are unlocked
                    all_unlocked = all(
                        is_unlocked(module, None, key)  # None means any type
                        if not any(u.get("name") == key for u in game_globals.unlocks[module])
                        else True
                        for key in group_list
                    )
                    # If all are unlocked, unlock the group record
                    if all_unlocked and not is_unlocked(module, "group", group_unlock["name"]):
                        group_label = group_unlock.get("label", group_unlock["name"])
                        group_entry = {"type": "group", "name": group_unlock["name"]}
                        if group_label:
                            group_entry["label"] = group_label
                        game_globals.unlocks[module].append(group_entry)
                        runtime_globals.game_message.add_slide(f"{group_label} unlocked!", (255, 255, 0), 56 * runtime_globals.UI_SCALE, runtime_globals.FONT_SIZE_SMALL)

def is_unlocked(module: str, unlock_type: str, name: str) -> bool:
    """
    Checks if an item is unlocked.
    If unlock_type is None, checks for any type with that name.
    """
    ensure_module_key(module)
    if unlock_type is None:
        return any(isinstance(u, dict) and u.get("name") == name for u in game_globals.unlocks[module])
    return any(isinstance(u, dict) and u.get("type") == unlock_type and u.get("name") == name for u in game_globals.unlocks[module])

def get_unlocked_backgrounds(module: str, module_backgrounds: list = None) -> list[dict]:
    """
    Returns list of unlocked background dicts (with name and label) for a module.
    module_backgrounds should be the module's 'backgrounds' list.
    """
    ensure_module_key(module)
    # Get all unlocked background names for this module
    unlocked_names = {u["name"] for u in game_globals.unlocks[module]}
    backgrounds = []
    # Use the module's backgrounds list to get labels and info
    if module_backgrounds:
        for bg in module_backgrounds:
            if bg["name"] in unlocked_names:
                backgrounds.append({"name": bg["name"], "label": bg.get("label", bg["name"])})
    else:
        # Fallback: just return unlocked names with their label if present
        backgrounds = [{"name": u["name"], "label": u.get("label", u["name"])} for u in game_globals.unlocks[module] if isinstance(u, dict) and u.get("type") == "background"]
    return backgrounds
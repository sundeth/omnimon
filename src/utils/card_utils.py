"""
Card collection utilities
=========================

Game-side reader for the module editor's card collections and helpers for
the player's collection state.

A module ships its collection as `cards.json` in the module folder (see the
module editor's CollectionFile):
    cards:   [{id, type, name, number, series, value, lr, rarity,
               sprites: {front, back}}, ...]
    effects: [{value, lr, effects: [{type, item/dna/unlock/area/round,
               amount, version}]}, ...]
    packs:   [...]                       (not used by the game yet)
Card sprites live in `modules/<module>/cards/`.

Cards and effects are intentionally decoupled: effects are keyed by the
binary value (+ optional L/R), so a foreign physical card with a matching
value still triggers this module's effect.

Player state lives in game_globals (persisted with the save):
    card_collection: {module_name: {card_id: {"digital": n, "physical": n}}}
    card_cooldowns:  {card_id: unix timestamp of last use}
Digital copies can be "used" (1 hour cooldown). Physical copies (scanned
via NFC) are display-only and never cool down.
"""

import json
import os
import random
import time

import pygame

from core import game_globals, runtime_globals
from utils.asset_utils import resolve_path, image_load
from utils.inventory_utils import add_to_inventory, get_item_by_name
from utils.utils_unlocks import unlock_item, is_unlocked

CARD_USE_COOLDOWN_SECONDS = 3600  # all digital cards share a 1h cooldown

# Display order of card types (mirrors the module editor)
CARD_TYPE_ORDER = ["Soul Plate", "DDP Chip", "iD Plate", "Custom"]

_module_cards_cache = {}   # module_name -> parsed cards.json dict (or None)
_card_sprite_cache = {}    # (module, filename, w, h) -> Surface


# ---------------------------------------------------------------------------
# Module card data
# ---------------------------------------------------------------------------

def get_module_cards(module_name):
    """Parsed cards.json for a module, or None when it has no collection."""
    if module_name in _module_cards_cache:
        return _module_cards_cache[module_name]

    data = None
    module = runtime_globals.game_modules.get(module_name)
    if module is not None:
        path = os.path.join(module.folder_path, "cards.json")
        try:
            resolved = resolve_path(path)
            if os.path.exists(resolved):
                with open(resolved, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                data = {
                    "cards": raw.get("cards") or [],
                    "effects": raw.get("effects") or [],
                    "packs": raw.get("packs") or [],
                }
                if not data["cards"] and not data["effects"]:
                    data = None
        except Exception as exc:
            runtime_globals.game_console.log(
                f"[Cards] Failed to load cards.json for {module_name}: {exc}")
            data = None

    _module_cards_cache[module_name] = data
    return data


def modules_with_cards():
    """[(module_name, cards_data)] for every module shipping cards, sorted by name."""
    result = []
    for name in sorted(runtime_globals.game_modules.keys()):
        data = get_module_cards(name)
        if data and data["cards"]:
            result.append((name, data))
    return result


def ordered_cards(cards):
    """Cards ordered for display: type, then number, Soul Plates alphabetical.

    Soul Plates always have number 0, so the name tiebreak sorts them
    alphabetically — same rule the module editor uses.
    """
    def type_order(card):
        t = card.get("type") or ""
        return CARD_TYPE_ORDER.index(t) if t in CARD_TYPE_ORDER else 99

    return sorted(cards, key=lambda c: (
        type_order(c),
        c.get("number") or 0,
        (c.get("name") or "").lower(),
    ))


def find_card_by_id(card_id):
    """Locate a card by uuid across every module. Returns (module_name, card) or (None, None)."""
    for module_name, data in modules_with_cards():
        for card in data["cards"]:
            if card.get("id") == card_id:
                return module_name, card
    return None, None


def find_card_by_value(value, number=None):
    """Best-effort match of an NFC payload to a known card by value (+number)."""
    for module_name, data in modules_with_cards():
        for card in data["cards"]:
            if card.get("value") != value:
                continue
            if number is not None and (card.get("number") or 0) != number:
                continue
            return module_name, card
    return None, None


def load_card_sprite(module_name, card, side="front", max_w=64, max_h=88):
    """Load a card sprite scaled to fit (max_w, max_h), keeping proportions.

    Returns None when the sprite file is missing.
    """
    sprites = card.get("sprites") or {}
    filename = sprites.get(side)
    if not filename:
        return None
    key = (module_name, filename, int(max_w), int(max_h))
    cached = _card_sprite_cache.get(key)
    if cached is not None:
        return cached

    module = runtime_globals.game_modules.get(module_name)
    if module is None:
        return None
    path = os.path.join(module.folder_path, "cards", filename)
    try:
        sprite = image_load(path).convert_alpha()
    except Exception:
        return None
    w, h = sprite.get_size()
    if w <= 0 or h <= 0:
        return None
    scale = min(max_w / w, max_h / h)
    sprite = pygame.transform.smoothscale(
        sprite, (max(1, int(w * scale)), max(1, int(h * scale))))
    _card_sprite_cache[key] = sprite
    return sprite


def clear_card_caches():
    """Drop cached card data and sprites (e.g. after a resolution change)."""
    _module_cards_cache.clear()
    _card_sprite_cache.clear()


# ---------------------------------------------------------------------------
# Player collection state
# ---------------------------------------------------------------------------

def _collection():
    if not hasattr(game_globals, "card_collection") or game_globals.card_collection is None:
        game_globals.card_collection = {}
    return game_globals.card_collection


def _cooldowns():
    if not hasattr(game_globals, "card_cooldowns") or game_globals.card_cooldowns is None:
        game_globals.card_cooldowns = {}
    return game_globals.card_cooldowns


def get_owned(module_name, card_id):
    """{"digital": n, "physical": n} for a card (zeros when not owned)."""
    entry = _collection().get(module_name, {}).get(card_id)
    if not entry:
        return {"digital": 0, "physical": 0}
    return {"digital": entry.get("digital", 0), "physical": entry.get("physical", 0)}


def total_copies(module_name, card_id):
    owned = get_owned(module_name, card_id)
    return owned["digital"] + owned["physical"]


def add_card_copy(module_name, card_id, physical=False):
    """Register one copy of a card in the player's collection."""
    module_cards = _collection().setdefault(module_name, {})
    entry = module_cards.setdefault(card_id, {"digital": 0, "physical": 0})
    entry["physical" if physical else "digital"] = \
        entry.get("physical" if physical else "digital", 0) + 1
    runtime_globals.game_console.log(
        f"[Cards] Added {'physical' if physical else 'digital'} copy of {card_id} ({module_name})")


def module_collection_stats(module_name, cards):
    """(total_cards, unique_owned, total_copies_owned) for the header line."""
    owned_map = _collection().get(module_name, {})
    unique = 0
    copies = 0
    for card in cards:
        entry = owned_map.get(card.get("id"))
        if entry:
            n = entry.get("digital", 0) + entry.get("physical", 0)
            if n > 0:
                unique += 1
                copies += n
    return len(cards), unique, copies


# ---------------------------------------------------------------------------
# Cooldowns (digital use)
# ---------------------------------------------------------------------------

def cooldown_remaining(card_id):
    """Seconds left before the card can be used again (0 when ready)."""
    last = _cooldowns().get(card_id)
    if not last:
        return 0
    remaining = CARD_USE_COOLDOWN_SECONDS - (time.time() - last)
    return max(0, remaining)


def cooldown_fraction(card_id):
    """Remaining cooldown as 0.0-1.0 (0 = ready)."""
    return cooldown_remaining(card_id) / CARD_USE_COOLDOWN_SECONDS


def start_cooldown(card_id):
    _cooldowns()[card_id] = time.time()


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------

def _lr_matches(group_lr, card_lr):
    group_lr = group_lr or "Any"
    if group_lr == "Any":
        return True
    # card_lr may be "L", "R" or "L/R" (matches either)
    if not card_lr:
        return False
    return group_lr in card_lr.split("/")


def find_effect_groups(module_name, value, lr):
    """Effect groups in a module matching a binary value (+L/R scope)."""
    data = get_module_cards(module_name)
    if not data:
        return []
    return [g for g in data["effects"]
            if g.get("value") == value and _lr_matches(g.get("lr"), lr)]


def resolve_card_effects(module_name, card):
    """All effects a card triggers in its module."""
    effects = []
    for group in find_effect_groups(module_name, card.get("value"), card.get("lr")):
        effects.extend(group.get("effects") or [])
    return effects


def random_effect_group():
    """A random effect group from any module (for unknown NFC tags).

    Returns (module_name, effects_list) or (None, None) when no module has
    effects.
    """
    pool = []
    for module_name, data in modules_with_cards():
        for group in data["effects"]:
            if group.get("effects"):
                pool.append((module_name, group["effects"]))
    if not pool:
        return None, None
    return random.choice(pool)


def apply_card_effects(module_name, effects):
    """Apply a list of card effects.

    Returns an outcome dict for the caller (the Collection scene) to act on:
        rewards:   list of reward dicts for RewardPopupUI
        unlock:    "done" (at least one new unlock), "already" (all were
                   unlocked before) or None (no unlock effects)
        encounter: (module_name, area, round) for a special encounter, or None
    """
    outcome = {"rewards": [], "unlock": None, "encounter": None}
    unlock_done = False
    unlock_seen = False

    for effect in effects or []:
        etype = effect.get("type") or "Item"

        if etype == "Item":
            item_name = effect.get("item")
            amount = effect.get("amount") or 1
            if not item_name:
                continue
            item_obj = get_item_by_name(module_name, item_name)
            if item_obj:
                add_to_inventory(item_obj.id, amount)
            else:
                add_to_inventory(item_name, amount)
            outcome["rewards"].append({
                "reward_type": "ITEM",
                "reward_value": item_name,
                "reward_quantity": amount,
            })

        elif etype == "DNA":
            # TODO: wire to the real DNA system once it exists — for now the
            # reward is announced but has no gameplay effect.
            dna = effect.get("dna") or "DNA"
            amount = effect.get("amount") or 1
            runtime_globals.game_console.log(
                f"[Cards] DNA effect stubbed: {dna} x{amount} (no DNA system yet)")
            outcome["rewards"].append({
                "reward_type": "ITEM",
                "reward_value": f"{dna} DNA",
                "reward_quantity": amount,
            })

        elif etype == "Unlock":
            name = effect.get("unlock")
            if not name:
                continue
            unlock_seen = True
            if is_unlocked(module_name, None, name):
                runtime_globals.game_console.log(
                    f"[Cards] Unlock '{name}' already unlocked ({module_name})")
            else:
                # Cards reference unlockables by name only; unlock_item needs
                # the entry's declared type, so resolve it from the module.
                module_obj = runtime_globals.game_modules.get(module_name)
                declared = getattr(module_obj, "unlocks", []) if module_obj else []
                entry = next((u for u in declared if u.get("name") == name), None)
                if entry is None:
                    runtime_globals.game_console.log(
                        f"[Cards] Unlock '{name}' not declared by {module_name}, skipping")
                    continue
                unlock_item(module_name, entry.get("type"), name)
                unlock_done = True
                runtime_globals.game_console.log(
                    f"[Cards] Unlocked '{name}' ({module_name})")

        elif etype == "Encounter":
            outcome["encounter"] = (
                module_name,
                effect.get("area") or 1,
                effect.get("round") or 1,
            )

    if unlock_seen:
        outcome["unlock"] = "done" if unlock_done else "already"
    return outcome

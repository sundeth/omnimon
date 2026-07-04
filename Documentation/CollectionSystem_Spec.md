# Collection System — Implementation Spec

Status: **Stage 1 implemented** (2026-07-04) — Digimon Database (uuid ids,
`#card=` fragment loader) and Module Editor (Collection tab with Cards /
Effects / Card Packs, ZIP import, Edit Art handoff, RFID export, Tools import,
docs + report). See `CollectionSystem_Stage1_Report.md` for details and open
pendencies. Implementation order:
**1) Digimon Database → 2) Module Editor → 3) Omnipet (game) → 4) Omninet.**
Game and Omninet phases are deferred; their requirements are captured here so
schemas don't churn.

---

## 1. Concept

Modules can ship a collection of collectable cards (Soul Plate, DDP Chip,
iD Plate, Custom). Players acquire them physically (NFID/RFID tags) or
digitally (card packs in the shop, adventure-mode battle rewards — only for
modules that have a collection). **The card's binary value (+ L/R for 5-bit
cards) is what matters mechanically**; name/number/series/art are presentation.

Cards are shareable across modules: a card's identity is a **UUID minted by
the card maker at creation** and preserved forever (Edit Art round-trips,
imports into any module). Effects are resolved by binary value, so a card from
module A works in module B if the bit length is compatible, even if B's
collection doesn't contain it.

### Binary / L-R model
- Bit lengths: Soul Plate **5**, iD Plate **5**, DDP Chip **6**, Custom **1–10**.
- Cards with different bit lengths are physically incompatible (DDP vs others).
- Soul Plates are always both L and R (`L/R`). iD Plates are `L`, `R`, or `L/R`.
- Effects carry an L/R selector (default `Any`), enabled only for 5-bit values.
- Effect matching: `effect.value == card.value` AND
  (`effect.lr == Any` OR `card.lr == L/R` OR `card.lr == effect.lr`).

### RFID payload (per physical card; export now, read in-game later)
```json
{ "id": "<uuid>", "name": "Agumon", "value": "01011",  "number": 3, "series": 1 }
```
`value` gets an `-L` / `-R` suffix for sided iD Plates (`"01011-L"`);
no suffix means `L/R`.

---

## 2. Digimon Database (card maker) changes

1. **UUID**: generate at card creation and export it as the card's **`id`**
   (matching every other object's id convention). The current slug-based `id`
   is dropped from the JSON — the slug remains a filename-only concern (ZIP
   and library file names, derived from the card name at save time). Never
   regenerate the uuid on edit.
2. **Edit Art entry point**: card maker reads `location.hash` on boot:
   `/card-maker#card=<base64url(card json)>` → behaves like `loadInitial()`.
   Unknown fields (uuid, rarity, module additions) are carried through and
   re-exported untouched.
3. Export JSON already contains everything needed to re-render (artwork url +
   x/y/scale, back transforms, effect icon, colors...). Custom-uploaded artwork
   has `artwork.url = null` → module editor flags it: Edit Art shows an error
   ("custom artwork — re-upload required") per spec.

---

## 3. Module folder layout

```
<module>/
├── module.json, monster.json, item.json, battle.json, ...
├── cards.json                  # collection: cards + effects + packs
└── cards/
    ├── <uuid>.png              # front, template-native size
    ├── <uuid>_back.png         # back (Soul/iD/Custom; NOT per-card for DDP)
    ├── DDP Chip_back.png       # single shared DDP back (kept iff ≥1 DDP card)
    └── pack_<uuid>.png         # card-pack sprites
```

- **Sprite resolution**: the card templates ARE the physical card sizes the
  module uses — verified from the template PNGs: Soul Plate **125×275**,
  iD Plate **205×325**, DDP Chip **250×350**. Imports are downscaled from the
  card-maker masters to exactly these per-type sizes. Custom uploads are
  resized down to fit within 250×350 (the largest card) if larger, aspect
  preserved.
- Only front/back 2D sprites are imported from card-maker ZIPs; 3D assets and
  `_artwork.png` print sheets are ignored.

## 4. `cards.json` schema

```json
{
  "schema_version": 1,
  "cards": [
    {
      "id": "8c1f...-uuid",
      "type": "iD Plate",            // Soul Plate | DDP Chip | iD Plate | Custom
      "name": "Agumon",
      "number": 3,                    // 0 for Soul Plates
      "series": "1",
      "value": "01011",               // binary, 1-10 bits
      "lr": "L/R",                    // L | R | L/R  (Soul: always L/R; DDP: omit)
      "rarity": "Common",             // Common | Rare | Legendary
      "custom_art": false,            // true → Edit Art unavailable
      "sprites": { "front": "cards/<uuid>.png", "back": "cards/<uuid>_back.png" },
      "art": { }                      // full card-maker JSON (verbatim) for Edit Art
    }
  ],
  "effects": [
    {
      "value": "01011",
      "lr": "Any",                    // Any | L | R (5-bit values only)
      "effects": [
        { "type": "Item",      "item": "<item id>", "amount": 1, "version": -1 },
        { "type": "DNA",       "dna": "Dragon",     "amount": 2, "version": -1 },
        { "type": "Encounter", "area": 3, "round": 2,            "version": -1 },
        { "type": "Unlock",    "unlock": "<unlock name>",        "version": -1 }
      ]
    }
  ],
  "packs": [
    {
      "id": "pack-uuid",
      "name": "Starter Pack",
      "sprite": "cards/pack_<uuid>.png",
      "cards_per_pack": 5,
      "shine_chance": 1.45,           // float %, 2 decimals (holo/shiny pull)
      "cards": [ { "id": "<card uuid>", "odds": 70 } ]   // relative weights
    }
  ]
}
```

Notes:
- `dna` combo values: `X of each`, Beast, Bird, Machine, Water, Dragon,
  Insect, Holy, Dark. `version` −1 = all pet versions (default).
- Effects/cards are intentionally decoupled: effects may exist with no matching
  card in this module (foreign cards still trigger them), and cards may have no
  effect. The **module report** lists both situations as informational warnings.
- Pack "import by type/series" fills `cards` with default odds by rarity
  (defaults TBD, e.g. Common 70 / Rare 25 / Legendary 5 relative weights).

## 5. Module Editor — Collection tab (after Item)

Inner tabs: **Cards | Effects | Card Packs**.

### Cards tab
- Left: filter combo (All / Soul Plate / DDP Chip / iD Plate / Custom) + list
  (front sprite thumb, name, number except Soul) ordered by type → number
  (Soul = 0, alphabetical within).
- Buttons: **Add** (type popup incl. Custom; next sequential number per type,
  0 for Soul; no sprites yet — clicking the empty front/back preview box opens
  an upload dialog, same pattern as module logo/battle icon; DDP back preview
  edits the *shared* back — warn it affects all DDP cards),
  **Import** (multi-ZIP; uuid match → replace-confirm asked **once** per batch;
  else type+number+name match → per-card add-as-new (new uuid) or override),
  **Edit Art** (opens browser at DB card maker with `#card=`; error for
  `custom_art`), **Remove** (confirm; deletes the card's sprite files; shared
  DDP back removed only when the last DDP card goes; effects are never removed).
- Right: front/back previews on top, then editable fields (name, type, series,
  number, value/binary, lr, rarity). Art-related fields (colors, icons,
  artwork) are **not** editable here. Saving a field that diverges from the
  baked sprite pops a one-time warning: "this won't update the card art".
- **Export RFID data** button: writes the RFID JSON (§1) for the selected card.

### Effects tab
- Left: list of binary values (shown as bits, with `-L`/`-R` suffix when set).
- Right: `value` (1–10 bits), `lr` combo (enabled iff 5 bits), effect list
  editor per the schema (type combo → conditional fields; item combo from
  `item.json`, unlock combo from `module.json` unlocks, area/round > 0
  validated against `battle.json`, amounts > 0, version int ≥ −1).

### Card Packs tab
- Left: pack list. Right: name, sprite (upload box), cards-per-pack,
  shine chance (0.00–100.00 %), card list with odds, and an
  "Add all of type/series…" bulk action using rarity-default odds.

### Tools menu
- **Import Collection from Module…**: pick another module folder → choose
  cards / effects / packs → copies entries + sprite files, matching by uuid
  (single batch replace-confirm), effects merged by (value, lr).

### Docs & report
- New **CollectionGenerator** in `docgenerators/` following the existing
  visual style (GeneratorUtils): card gallery grouped by type (front sprite,
  name, number, series, rarity, value), effects table (value/lr → resolved
  effect descriptions, item names/unlock labels, version), packs section
  (sprite, size, shine %, contents with normalized percentages).
- `ModuleReportGenerator`: add checks — cards without effects, effects without
  cards (informational), dangling item/unlock/area references in effects
  (errors), duplicate (type, number), duplicate uuid.

## 6. Omnipet (game) — deferred, schema-aware
- Shop sells packs (Progress Mode via Omninet; Free Mode: no shop, offline
  save); adventure battles can drop cards (drop config TBD — future addition
  to `cards.json`); NFID reading resolves effects by `value` + `lr`.
- Player collection stored in the save file (Free Mode) / Omninet (Progress).
- Shiny: game-side holo effect flag on owned card instances.

## 7. Omninet — deferred
1. Store player cards (Progress Mode), 2) trading between players,
3) card-pack shop. Module publishing already ships the module folder, so
`cards.json` + `cards/` travel with it; verify upload size limits.

---

## Open items
- Default rarity→odds weights for pack bulk-import (proposal: 70/25/5).
- Effect L/R matching rule (§1) — confirm.
- Whether DDP back upload lives on the card (shared, with warning) or in a
  dedicated spot.
- Adventure-mode drop tables (future `cards.json` addition).

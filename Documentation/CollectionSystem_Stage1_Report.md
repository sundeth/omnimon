# Collection System — Stage 1 Implementation Report

Autonomous overnight run, 2026-07-04. Everything below is implemented, compiled
and covered by headless tests where possible. **Nothing was committed** — all
changes are in the working trees for your review.

---

## 1. Digimon Database (done, tested)

| Change | File |
|---|---|
| Card `id` is now a **uuid** minted at creation (v4, with a non-secure-context fallback since the site runs on plain http on the LAN), preserved forever across edits | `webapp/app/static/card_maker.js` |
| **Unknown-field passthrough**: fields the card maker doesn't know (e.g. `rarity`) survive load→edit→export untouched; server-injected `png_url`/`glb_url` are stripped | `card_maker.js` (`KNOWN_CARD_FIELDS`, `state.extra`) |
| **`#card=<base64url json>` fragment loader** — the Edit Art entry point; `loadInitial` refactored into `applyCard`, fragment wins over page-embedded card | `card_maker.js` (`loadFromFragment`) |
| `get_card` falls back to matching the **id stored inside** each library json (uuid ids vs slug filenames) | `webapp/app/cards.py` |

**Tests run**: `node --check`; 9-assertion fragment/uuid round-trip suite
(unicode, nested objects, uuid shape/uniqueness, passthrough semantics);
booted the FastAPI app and probed `/card-maker`, `/cards`, statics, APIs (all
200); `get_card` filename + uuid lookup; **C#→JS cross-language fragment
round-trip** including unicode. All pass.

## 2. Module Editor (done, compiled, model/import/report/docgen tested)

New files:
- `models/Card.cs` — `CollectionCard`, `CardEffectGroup`, `CardEffect`,
  `CardPack`, `PackEntry`, `CollectionFile` (cards.json load/save, ordering,
  next-number, RFID payload builder, rarity weights 70/25/5, template sizes).
- `tabs/CollectionTab.cs` — the whole Collection tab (after Item):
  - **Cards**: filter combo (All/Soul/DDP/iD/Custom — Custom also matches
    custom-art cards), owner-drawn list with sprite thumbs (ordered type →
    number, Souls alphabetical), Add (type dialog, next sequential number),
    **Import** (multi-ZIP: parses card-maker json, keeps it verbatim in `art`,
    downscales front/back to template-native sizes, DDP back → shared
    `DDP Chip_back.png`, uuid conflicts asked **once per batch**,
    type+number+name conflicts asked per card override/new/skip, legacy slug
    ids get a fresh uuid, custom-art detection via `artwork.url == null`),
    **Edit Art** (syncs edited fields into the art json and opens
    `{db}/card-maker#card=…`; blocked for Custom/custom-art with the specced
    messages), **Remove** (deletes sprites; shared DDP back only with the last
    DDP card; pack entries cleaned), editable fields with the
    "won't change the artwork" warning, click-to-upload front/back previews
    (DDP back = shared, warned), **Export RFID Data** button.
  - **Effects**: list of binary values (1–10 bits validated), L/R combo enabled
    only for 5-bit values (`Any` default), per-group effect list with
    Item (module items) / DNA (X-of-each + 8 souls) / Encounter (area/round) /
    Unlock (module unlocks) editors and version (-1 = all).
  - **Card Packs**: name, sprite (click-to-upload `cards/pack_<id>.png`),
    cards-per-pack, shine chance (0.00–100.00 %), card/odds grid (combo per
    row, rows deletable), "Add All of Type/Series…" bulk add with
    rarity-weighted odds.
  - `ImportFromModuleFlow()` — used by **Tools ▸ Import Collection from
    Module** (checkbox picker for cards/effects/packs, uuid/(value,lr)/pack-id
    matching, one replace confirmation, sprite files copied).
- `docgenerators/CollectionGenerator.cs` + `template/collection.html` — card
  gallery (sprite, name, number, series, rarity, RFID value), effects table,
  packs table with normalized percentages; nav link added to
  `template/index.html`; wired into `HTMLGenerator`.

Modified: `ModuleEditorForm(.Designer).cs` (tab after Item; Tools menu item),
`reports/ModuleReportGenerator.cs` (**Collection section**: duplicate ids
[error], duplicate type+number [warn], invalid binaries [error], missing front
sprites [warn], cards↔effects cross-coverage [info, honoring the L/R matching
rule], unknown item/unlock refs [error], areas with no enemies [warn],
non-positive amounts [error], versions with no pets [warn], packs referencing
missing cards [error] / empty packs [warn]), `.csproj`, `README.md`.

**Tests run** (headless, via reflection over the built exe):
- 15-assertion model/report suite: load/save round-trip (incl. shine decimals,
  lr), NextNumber, ordering, RFID payload (`-L` suffix, numeric series), and
  all report checks firing correctly on a synthetic bad module — including the
  L/R matching rule (a `01011-L` card correctly matched an `(01011, Any)`
  effect and not an `(01011, R)`-only one).
- 17-assertion import suite with real generated ZIPs: field mapping for iD and
  DDP, uuid preserved / legacy slug → new uuid, rarity passthrough, custom-art
  detection, glb/`_artwork.png` ignored, front downscaled to exactly 205×325,
  DDP back written as the shared file at 250×350, sprite paths recorded.
- Doc generator produced a correct `collection.html` for the synthetic module.
- Full solution build: **0 errors** (one pre-existing unrelated warning).

## 3. What I could NOT test (needs your eyes)

The WinForms **UI itself** — layout, list rendering, the dialogs, the
DataGridView combo behavior, Edit Art actually opening your browser. All logic
behind the UI is tested, but I couldn't drive the GUI headless. Suggested
5-minute check: open the Tutorial module → Collection tab → Add a card,
Import a real card-maker ZIP, click the previews, make a pack, run
Ctrl+R report, Ctrl+G docs.

## 4. Pendencies / decisions I made on your behalf

1. **Spec defaults applied** (flagged as open items in the spec): L/R matching
   rule as specced; rarity weights 70/25/5; DDP shared-back upload allowed with
   an "affects all DDP cards" warning; adventure drop tables untouched.
2. **`fields-unsupported` note**: the Add dialog creates cards with no sprites —
   the preview boxes say "click to set" (per your #6 answer).
3. **Effect items are referenced by item NAME** (like unlocks). Renaming an
   item in the Item tab orphans the reference; the report flags it. If you'd
   rather key by item id, say so — small change.
4. **Edit Art round-trip is manual by design**: card maker opens with current
   data; the user downloads the ZIP and re-imports (matched by uuid). An info
   popup explains this after launching the browser.
5. **Deploy note**: the Digimon Database changes are local — run `deploy.bat`
   (or push) to get them onto the unraid host; `DigimonDbClient.BaseUrl`
   (`https://digimon-db.omnipet.app.br`) is what Edit Art opens.
6. **Module Editor version of "Custom" cards**: value defaults to `0` (1 bit);
   the user sets everything, uploads sprites (auto-fit within 250×350).
7. Scratch test scripts live in the session scratchpad if you want to re-run
   them (`test_fragment.js`, `test_collection.ps1`, `test_import.ps1`,
   `test_docgen.ps1`).

## 5. Next stages (unchanged)

Omnipet game (shop packs, adventure drops, NFID reading, save-file collection)
→ Omninet (player card storage, trading, pack shop for Progress Mode).

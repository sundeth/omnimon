# Omnipet

A Python/pygame virtual-pet platform that reproduces original Digimon V-Pet
devices (and a few crossovers). Each device is a self-contained **module** of
JSON data plus sprites; the engine reads those and enforces the shared rules.

Entry point is `main.py`, which puts `src/` on the path and hands off to
`VirtualPetGame` in `src/vpet.py`. Python 3.10.

## Layout

| path | what |
|---|---|
| `src/` | the game — `models/`, `battle/`, `scenes/`, `ui/`, `utils/`, `core/` |
| `modules/<NAME>/` | one device each: `module.json`, `monster.json`, `battle.json`, plus optional `devices.json`, `item.json`, `quests.json`, `events.json`, `codes.json`, `cards.json` (card collection) and sprite folders |
| `utilities/` | one-off scripts; `utilities/claude/` holds the module parsers/validators/fixers described below |
| `utilities/<MODULE>/` | reference material for that device (firmware dumps, saved pages) |
| `Documentation/` | generated module docs |

Related working directories outside this repo: `e:\Omnipet Module Editor`
(the C# editor), `e:\Omninet`, `e:\Digimon Database`, `e:\Omnipet PCB Boards`.

**`modules/` is gitignored** (`modules/*`). There is no git undo for module
data — copy a file before rewriting it.

## The Module Editor

A separate WinForms app that edits module JSON and generates the HTML docs.

- **.NET Framework 4.8** — `dotnet build` fails on it. Build with
  `"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe" OmnipetModuleEditor.sln`
- Its `.cs` files are **UTF-16LE with BOM and CRLF**. Any patch must write
  them back that way (`New-Object System.Text.UnicodeEncoding($false,$true)`),
  or the build breaks. `grep` misses them; use ripgrep/the Grep tool.
- Adding a field to a module means adding it to `models/*.cs` **and** the
  relevant tab, or the editor silently drops it on the next save.
- `reports/ModuleReportGenerator.cs` produces the module validation report.
  Its checks have to match what the game actually does, or they push module
  data the wrong way: the "inaccessible round" warning is keyed on the **area**,
  not on (area, version), because the game fills a round from any version that
  has one.
- Unlock `type` is a fixed combo list: `egg, adventure, evolution, digidex,
  battle, group, pvp, versus`. Any other value makes the Unlocks tab throw
  "invalid value".
- The evolution canvas lays itself out through `OrganizeCanvas()`, which both
  the initial build and the Organize button call, so the chart always opens
  in the arrangement the button gives. One row per stage in use, barycentre
  sweeps for ordering, then one pass up and one back down for coordinates —
  ending downwards is what puts an only target under its source. A second
  round only widens the sheet; the alignment has already settled. Panels
  pressed together are shifted by their own run's average error rather than
  the whole row's, so a panel with room keeps the spot it asked for.
  `AutoScrollMinSize` tracks the content plus one margin — it must never grow
  by multiplying, which is what let the scrollbars run away before.

## Module data — things that are easy to get wrong

**Stages** `0` Egg, `1` Baby I, `2` Baby II, `3` Child, `4` Adult,
`5` Perfect, `6` Ultimate, `7` Super Ultimate, `8` Super Ultimate+.

**Attack sprites are stored +1.** Device/firmware ids are 0-based; the module
reserves `0` for "no attack sprite", so a firmware value of 19 is stored as
20. `65535` in a dump means none.

**Evolution is first-match-wins.** `update_evolution()` walks the `evolve`
list in order and takes the first entry whose criteria all pass. A broad entry
placed above a narrow one silently shadows it. **Never sort or reorder an
`evolve` list** — ordering is load-bearing, and modules deliberately put the
gated route first so the ungated one acts as the fallback. Requirement ranges
are `[min, max]`, with `999999` meaning "or more".

**A gap in the evolution table is legal.** Real devices fail evolution when
nothing matches (humulos charts show this as "Evo Fail"), and the engine
already does nothing in that case. Don't invent a route to fill a hole.

**`version` vs `device_version`.** `version` is the gameplay line (which
evolutions and unlocks apply). `device_version` is the physical hardware
revision, declared in `devices.json`, and is what battle protocols and
connection requirements key off. Anything about *which device you connected
to* belongs on `device_version`.

**Sprites.** `name_format` (usually `$_dmc`) builds the set name — `$` is the
pet name, then `:` becomes `_` so the path is valid. The loader looks for
`monsters/<Name>_dmc/` first, then `monsters/<Name>_dmc.zip`, then the global
`assets/`. Frame slots:

```
0 IDDLE1  1 IDLE2  2 HAPPY  3 ANGRY   4 TRAIN1  5 TRAIN2  6 ATK1   7 ATK2
8 EAT1    9 EAT2  10 NOPE  11 NAP1   12 NAP2   13 SICK   14 LOSE  15 SPECIAL
```

Missing frames should be **left out of the set**, not filled with a stand-in,
so they stay easy to find. Slot 15 in particular must be absent when the
device has no special frame — the in-game special animation keys off that.
A Digitama only animates between slots 0–2, so the full table does not apply
to stage 0.

**A gap the Color library shipped with.** 102 of the shared `assets/monsters`
sets were missing exactly slots **4 TRAIN1, 5 TRAIN2 and 6 ATK1** — always
those three, so it was a property of how that library was built rather than of
any one Digimon. They are filled from frames the set already has: `TRAIN1` and
`ATK1` from `1 IDLE2`, `TRAIN2` from `7 ATK2`
(`utilities/claude/fix_color_frames.py`, `--publish` pushes the same repair to
the database). Worth re-running if a new Color set turns up short; the Dot
library has never had the gap, and `monsters_hidef` has its own unrelated one
(20 sets missing `12 NAP2, 13 SICK, 14 LOSE`).

**Sprite formats.** Three parallel libraries — `monsters` (Color),
`monsters_dot` (Dot), `monsters_hidef` (HD) — each searched in the module
first, then in the shared `assets/` copy. `module.json` names a
`primary_sprite_format` and a `secondary_sprite_format`. Players can turn old
sprites off, which drops a **Dot-primary module through to its secondary
(Color) set**, so those modules have to carry both complete; the Module Editor
report checks for it. `utilities/claude/check_sprite_formats.py` reports the
same thing outside the editor.

**Backgrounds.** `bg_<slug>[_day|_dusk|_night][_high].png` in `backgrounds/`,
with a matching entry in `module.json`'s `backgrounds` list (`name` has no
`bg_` prefix). Every background also needs an unlock saying how it is earned;
an `egg` unlock with a **null version** is the idiom for "available from the
start on every version". `get_unlocked_backgrounds` pairs the two **by name**,
so the unlock has to be called exactly what the background is called — the
Pendulums use `ver1`…`ver5` plus `ver0` for Virus Busters, for both. A
background whose unlock is named anything else never appears, however
complete its artwork.

## Systems

**Unlocks** are module-global and permanent, stored in
`game_globals.unlocks[module]`. A monster with `special: true` and a
`special_key` can only be evolved into once that unlock is held — that is how
"clear area N to unlock X" works, and it matches the hardware (one clear is
enough, forever). Don't model those as an `area` criterion. The same pair
gates a **Digitama**: `_get_available_eggs` hides a stage-0 monster whose
`special_key` is not yet held, which is how a device that ships three eggs and
earns the rest is modelled. An `egg`-type unlock is the opposite thing — it is
*granted* on hatching, for the album.

Each unlock type is earned differently: `digidex` + `amount` counts distinct
Digimon raised, `battle` + `amount` counts total victories, `adventure` +
`area` fires on clearing that area, `versus`/`pvp` on connection battles, and
`evolution` on reaching a target — either one named in `to`, or **any monster
at or above `stage`**, which is what "unlocked by evolving into Child" needs.

**Boolean conditions out of unlocks.** A `versus` unlock naming both
`device_version` and `opponent_device_version` matches a device *pair*, and
the engine's test is symmetric, so one record covers the connection either way
round. Three properties then compose anything needed:

- **OR** — the versus loop visits every record without breaking, so declaring
  one name **twice** with different opponents means "connect with A or B";
- **AND** — a `group` unlock fires once every name in its `list` is held, and
  is re-checked after each unlock, so it cascades;
- **OR of ANDs** — declaring the *group* several times under one name, each
  with its own `list`, fires when any one list completes.

PENZ uses all three: its library slots open by connecting to the other devices
in the same release wave, slot 6 per device ("connect with either sibling") and
slots 7/8 per wave ("connect with both"). Since those two always open
together, both their Digimon share one `special_key`.

**Area locks** (`Module.get_area_locks` / `is_area_unlocked`): an unlock
declaring `unlocks_area` keeps that area shut until it is earned, scoped by
the unlock's `version`. Used for devices that gate their last area behind a
connection battle. Modules that declare none are unaffected.

**Temporary evolutions** (`temporary-evolution` on a pet, `src/utils/xros_utils.py`):
battle-only DigiXros / Mode Change forms with `to`, `type`, `strength`,
`megahit`, `unlock`, `friend`, `background`, `animation`. The pet keeps the
form for the battle and reverts afterwards. These forms are reached *only*
this way, so nothing should `evolve` into them and they need no `special_key`.

**Jogress comes in two shapes.** An *attribute* jogress
(`{"to":X,"stage":N,"attribute":"Va","jogress":"PenC"}`) is 2-in-2-out —
both pets evolve. A *named* jogress (`{"to":X,"version":N,"jogress":"Partner"}`)
is 2-in-1-out: the partner is absorbed. `version` is the **partner's**
version. `jogress_prefix: true` matches any partner whose name starts with
the string, and ignores the version entirely.

**A named jogress must be declared on both sides, and its target must exist
on both versions.** `jogress_view._perform_jogress` runs
`pet2.evolve_to(evo["to"], pet2.version)` on the absorbed partner *before*
removing it, and `evolve_to` indexes straight into the result of
`get_monster` — so a target missing on the partner's version is a hard
crash, not a quiet no-op. Separately, `_check_pet_compatibility` only tests
the routes of whichever pet was selected **first**, so a pairing declared on
one side alone reads as "not compatible" half the time. Both directions,
always. `utilities/claude/check_jogress.py` audits a module for all of it.
Note `jogress_avaliable` on a pet is stored but never read — it gates
nothing.

**Friends** are declared on the pet side — a monster with
`avaliability: "Friend"` — and matched to a special encounter by name.
Beating that encounter registers it in `game_globals.friends`, which
DigiXros requirements read. Clearing an adventure area on a module that has
friends queues a guaranteed encounter via `game_globals.friend_event_pending`.

**Random events** fire on an idle timer in `scene_maingame.py` (~45-75 min),
gated by the daily XAI roll, one at a time, with a 1-minute window to answer.

**Battle minigames** are chosen by `module.json`'s `battle_minigame`, never by
the ruleset: `"None"`, `"Dummy Bar"`, `"Count Match Classic"/"Color"/"Z"`,
`"Xai Roll+Bar"`, `"Xai Bar"`, `"Punch"`, `"Mogera"`. It drives the charge
phase, `get_minigame_strength`, and the ready phase. Count Match Color and Z
draw the ready phase themselves — they show an attribute-specific sprite, or
the arrows to match, before the count — which they declare with
`HAS_READY_PHASE = True`; `battle_encounter.READY_PHASE_MINIGAMES` is built
from that flag, so giving another minigame a ready phase is one line in the
minigame itself. Everything else falls through to the animated ready sprite.
The *training* minigames are a separate thing again: they are player-owned
purchases picked from a menu, not a module setting.

**Enemies are resolved per round, not per version.** `load_enemies` asks
`get_enemy_versions(area, round)` for every version present on that round and,
when the pet's own version is not among them, **picks one at random**. So
battle.json does not need a record for every version — a version with no entry
for a round still gets a fight. Two consequences: a device with more than one
battle region (Pendulum Z fields two) deliberately leaves gaps in any single
version's sequence, and a pet can be handed the other region's enemy. Giving
each region's enemy a record on every version of its own wave is what makes a
pet always draw its own region, since the random pick only happens on a miss.

**Traited egg and power bonus rules.** These were one `ruleset` field per
device family (`dm`/`pen`/`dmx`/`vb`) until it stopped being able to describe
them — the four Pendulums alone want four different power models. They are now
two independent module.json fields, each a fixed combo list in the editor.

`traited_egg_rule` — how a Traited Egg is earned (`game_pet.set_traited_egg`):

| value | condition | devices |
|---|---|---|
| `None` | never | DM, VB, VBE, VH |
| `Stage V Chance` | stage V+, 30% roll — 15%/15% split when the module has a G-Cell Fragment egg | DMC, DMGZ, DMH |
| `Win Ratio (Stage 4)` / `(Stage 5)` | that stage or higher **and** a 60% win ratio | DMXW / PENC, D-3 |
| `Evolution Timer` | 48 h since the last evolution | DM20, DMRV, PEN20, PENZ |
| `Evolution Timer (Area 45)` | the same, gated on the X clearing Area 45 | DMX |
| `Outlive Lifespan` | still alive past its listed lifespan | PEN |

`power_bonus_rule` — where battle power above the species base comes from
(`game_pet.get_power`). Every table is keyed on a **full Strength meter** and
pays the Traited Egg column independently, which is what the manuals say:

| value | formula | devices |
|---|---|---|
| `None` | base only | DM |
| `Stage Table` | +5/8/15/25/25 by stage, again for a Traited Egg | DMC, DMGZ, DMH |
| `Stage Table + Shaken` | +5/8/15/20/20, again for Traited, +10 flat for Shaken | PENC, D-3 |
| `Stage Table Xros` | +5/+10/+20 across its three stages | DMXW |
| `Strength and Level` | +16 (device 1–2) or +15, plus +10 at levels 3/6/9 | DMX, PENZ |
| `Strength Hearts` | +4 a heart, +16 at full | DM20, DMRV, PEN20 |
| `Effort` | the original Pendulum's hidden 0–40 stat | PEN |
| `Star` | base plus 16 per star | VB, VBE, VH |

A module written before these fields falls back through
`game_module.LEGACY_RULESET_RULES`, which maps an old `ruleset` onto whichever
pair reproduces what it used to do. The editor does the same on load and then
drops the field, so opening and saving an old module migrates it.

`battle_atribute_advantage` was never part of this — it is a plain number the
battle simulator reads, with `battle_atribute_advantage_power` deciding whether
it is spent on Power or on hit rate.

**Still missing: the evolution chance.** PEN and PEN20 describe their Traited
and Shaken eggs as **+10 percentage points on the chance to evolve** to
Perfect/Ultimate, and nothing implements that, so those two bonuses are inert.
The ladders differ by era — the original Pendulum is `80/70/40 → 50/25/12.5%`
with the sub-40 band immune to bonuses, while DM20 and PEN20 are
`80/60/40 → 100/50/25%` — so the bands have to be data, not one threshold.

## The Vital Bracelet modules — VB, VBE, VH

Three modules built from the Vital Bracelet line, and the only ones whose
source is a binary card dump rather than a chart. **VB** is every Digimon DIM
card (37 versions), **VH** every non-Digimon DIM — Kamen Rider, Ultraman, DC
(23), **VBE** every BE Memory including the crossovers (22).

Two deliberate departures from the hardware: vital points are earned by
feeding rather than passively by wearing the device, and lost when the hunger
hearts empty; and the phone app's battles and strengthening items are in the
game directly, capped so they don't unbalance other modules.

### The dumps

Firmware and extracted sprites live on the share under
`\\192.168.100.250\Storage\My Projects\Digimon\DIMS` — `Sprites` is VB,
`Sprites2` VBE, `SpriteB` VH, one folder per card. Each holds
`data/character_NN.json` (the full card record) and
`sprites/characters/character_NN/`.

Sprite slots in a dump: `sprite_00` is an 80×15 **name plate** (the Japanese
name as an image — the only ground truth for who a character is),
`sprite_01`–`12` the 64×56 animation frames on a green chroma key, and the
**last** frame an 80×160 illustrated card portrait.

### Reading a card record

| card | module | note |
|---|---|---|
| `stage` | `stage` **+ 1** | see below |
| `bp` | `power` | |
| `hp` | `hp` | |
| `stars` | `star` | |
| `ap` | `attack` | |
| `smallAttack` | `atk_main` **+ 1** | 0 is "no sprite", hence the +1 |
| `bigAttack` | `atk_alt` **+ 41** | second sprite bank |
| `attribute` | `1` Vi, `2` Da, `3` Va, `4` Free (`""`) | `0` = none |

`65535` means "none" in every field. The conversions are in
`utilities/VBUtils/vb_complete_importer.py`, which is what built the modules.

**The stage offset is because Omnipet adds the egg.** A DIM hatches straight
into the Baby, so the card has no stage-0 record; Omnipet inserts one per
line, named after the card (or "…Starter", where a human being hatching from
an egg would make no sense). Every roster therefore holds exactly one more
record than its card.

Evolutions come from three fields, and **all of them are on the card — none
of it is Omnipet's invention**:

- `transformations` → the raised routes. `battlesRequirement`→`battles`,
  `winRatioRequirement`→`win_ratio`, **`ppRequirement`→`trophies`**,
  `vitalityRequirement`→`vital_values`.
- `attributeFusions` → PenC jogress. `typeN` keys on the **partner's
  attribute code**, `0` meaning no fusion for that attribute.
- `specificFusions` → named jogress. Values are sometimes an id, sometimes a
  record carrying one.

### VBE is on a different scale

`utilities/VBE/normalize_stats.py` rescales BEM `hp`, `ap` and `bp` from
their own range onto the range VB uses (`power` card 1500–9999 → module
26–230, `hp` 1800–7000 → 3–22, `attack` 800–3000 → 2–12). **Comparing VBE's
numbers to its cards directly matches nothing** — recover the min-max line
first. The same script sets `critical_turn` with `random.randint`, so that
field cannot be validated against a card at all.

VBE also carries **custom attack sprites** appended past the defaults in its
`atk/` folder — small 1–39, big 41–62, everything above that hand-assigned.
Attack ids that disagree with the card on a non-Digimon character are
expected, not errors.

### Names

Modules carry the Digimon Database's **English** name. The dumps and humulos
carry Japanese romanisations — `V-mon`, `Holy Angemon`, `Tyranomon`,
`Mercuremon` — so **comparing raw strings invents differences that are not
there**. Everything that joins on a name goes through
`utilities/claude/vb_names.py` (`canon` / `same`), which also handles
compound names (`Atlur Kabuterimon (Red)` → `MegaKabuterimon (Red)`).

**Non-Digimon characters were never normalised.** Kamen Rider, Ultraman, DC
and the crossover BEM cast keep the names they shipped with, and have no
database record — `canon` leaves anything it does not recognise alone rather
than guessing, and that is load-bearing.

### Record order and indexes

`index` is the character's id on the card; eggs are `-1`. Because these
devices carry **several evolution lines on one version**, the file is not one
stage-ordered run — it reads

```
egg > 1 > 2 > 3 …   egg > 1 > 2 > 3 …
```

with each egg emitted immediately **before the record it evolves into**. That
is not always a stage 1: VBE's crossover cards have no stage 1 or 2 at all
and hatch a Starter straight into a stage-3 character.

`devices.json` for these three has **no background** — the device sprite is
the DIM card itself, so there is no shell for one to sit in.

### Matching a dump to a module, in order of trust

1. **Order.** VH alone was written in card order (372/372). VB shuffles
   within a stage and VBE does not line up at all — check before trusting it.
2. **Names**, through the database, where a table exists
   (`utilities/VBUtils/character_names.json` for VH,
   `utilities/VBE/character_names copy.json` for VBE — VB has none).
3. **Stats.** `power`+`hp` tie constantly, since the values are standardised
   per stage; `attribute` and then the two attack ids break almost every tie.
4. **The name plate**, for what survives all of that.

**An import that walked the wrong order writes the stats *and* the attack ids
across**, so those fields carry the same mistake and cannot expose it — the
evolution routes stay put and are what caught VB v22's Zubamon/Ryudamon
transposition. Prefer routes over attack ids when the two disagree.

Joining packs to versions has two traps: pack folder names need aliasing
(`AGNIMON` is `Agnimon EX`, `DIM_Renamon` is `Renamon EX`, `01. Guilmon` is
Guilmon **GP** not Guilmon EX), and **VBE's `dim_NNN.png` device art is not in
version order** — card 126 is v4, card 128 is v3. humulos'
`/digimon/vbbe/list/` numbers its rows `<card>-<index>` using the same card
numbers, which is how they are matched.

### Personality, and the rest of the battle model

`activityType` on the card is the pet's **personality**, and it is on all
1428 characters. It is a schedule rather than a stat: it decides which round
the special move fires, and that round the pet gets **+2 AP**.

| value | name | round |
|---|---|---|
| 0 | Stoic | 1 |
| 1 | Active | 2 |
| 2 | Normal | 3 |
| 3 | Indoor | 4 |
| 4 | Lazy | 5 |

Stored as `personality` on the pet, a fixed combo in the editor, defaulting to
**Normal** — the middle round — for every device with no card to read it
from. The value/name alignment follows the ordering in GMMan's battle-logic
notes (`gist.github.com/GMMan/0f1233f4c095e51934d8ee062eb85e83`) rather than a
decoded enum, so it is worth confirming against DIM-Modifier before anything
depends on the exact labels.

The same notes give the device's whole battle model, none of which is
implemented yet beyond the pieces below:

```
hit rate = your DP / (your DP + enemy DP) * 100,  then ±5 by attribute
5 rounds max; exactly one side lands a hit each round
damage  = winner's AP  (+1/-1 by mental state, +2 on their special round)
```

The ±5 is on **hit rate**, not power, which is what
`battle_atribute_advantage_power: false` already selects. "Mental state" is
just the pet's mood.

**Vital Values are capped per stage** — Child 2500, Adult 5000, Perfect 7500,
Ultimate 9999 — not at a flat 9999, so evolving is what raises the ceiling
(`GamePet.VITAL_VALUE_CAPS`). A full bar is worth **+2 HP per quarter filled,
to +6**, applied in `get_hp`. Both are gated on `tracks_vital_values()`,
which keys off `Vital Values` appearing in the module's `visible_stats` the
same way Experience does — so a device without the meter is untouched.

**Evolution timers come from the manual**, in minutes, and the imported ones
were a classic-device template that matched nothing: `1→60`, `2→180`,
`3→960`, `4→1440`, `5→1440`. Stage 6 and up are left alone.

### Frame 15

The last frame of each character's dump — the card portrait — is slot 15
(SPECIAL). It is stored on all 1261 sets but
`enable_special_attack_sprite` is left **off**, so nothing renders it yet:
the engine uses slot 15 for the critical-attack slide-in and pre-scales it to
2× width, which suits a pixel pose rather than an 80×160 illustration.

Sets shared with `assets/monsters_hidef` were **copied into the module**
rather than edited in place, so classic devices using the same Digimon do not
inherit a slot 15 they should not have. 648 sheets were published to the
database's `sprites/monsters_hidef`, Digimon only and only where a sheet
already existed.

## What the Module Editor's report is really telling you

Most findings are real, but a few read the wrong way round:

- **`min_weight: 99` on an egg** is the importer's default, not a rule. Nothing
  hatches with a weight requirement, so eggs belong at `0`. (DMH is the
  opposite case — *every* pet there is 99 because the device ignores weight.)
- **`status_boost` with `boost_time: 0`** is how a *permanent* boost is
  written, as in "Permanently Increases Attack +5"; six items across the
  modules use it. Only a negative time is an error, and the report now says so.
- **A pet evolving to another of the same stage** is normal — Omnimon,
  Susanomon and every other same-stage jogress target look like this.
- **"missing sprites (has some but not all frames)"** on a Color-primary
  module was almost always the `TRAIN1/TRAIN2/ATK1` gap above, not the pet.

**Every `special_key` needs an unlock of the same name.** The convention is
`area_<area>_<version>` for "clear this area on this version", declared as an
`adventure` unlock — so the trailing number has to match the pet's own
version. VB v18's Rapidmon Armor carried `area_15_17`, silently sharing v17's
unlock. `utilities/claude/fix_vb_report.py` checks the pairing, repoints
routes that name a pet from another version, and clears the egg weights.

## Data sources and the validation workflow

humulos.com is the primary reference for every module, backed by firmware
dumps and community manuals where they exist. Two things worth knowing:

- Newer devices serve per-Digimon detail through
  `humulos.com/digimon/php/details.php?digimon=<key>&device=<id>&version=<v>`
  — stat block plus every evolution route with its requirement text. The pages
  themselves are shells that fetch this over AJAX. Requires a browser
  User-Agent. Older devices (DMX) still inline the data as `_card` divs.
- humulos data is **not always complete**. A device-grouped evolution card can
  omit a whole group, so an absent route is not evidence of a missing one.
  Cross-check against a firmware dump when there is one.
- The card-style guides (DMX, PENZ) render one `detailsNew` div per Digimon
  instead. Read a route's requirement from its `<p class="deets">` paragraph,
  not from the `onClick`: some calls carry only two arguments and omit the
  requirement entirely. Alternatives are separated by `&bull;`, and the
  Colosseum pages put the enemies in `list_encounters` / `list_boss` cells as
  images, so the keys come from `digimonDetails('<key>')`.
- **Match on the Japanese `sub`, not the `dub`.** Omnipet names stages the
  Japanese way, and the guides' localised names disagree about which stage is
  which: `Algomon (Perfect)` is dubbed `Argomon (Ultimate)` and
  `Algomon (Ultimate)` is `Argomon (Mega)`. Resolving through the dub, or
  through the database, silently swaps those two Digimon and every stat with
  them — it looks exactly like the module having transposed data. Bind each
  card to a module name once, before any looser spelling gets a chance, or one
  card's dub will claim the name belonging to another.
- Several newer guides (PEN20, DMXW) ship their whole database inline as a
  `result = [...]` array in the page. Parsing that beats scraping the rendered
  chart: it carries stage, attribute, sleep, the eggs a Digimon belongs to and
  every route with its requirement text, and the Digitama records in the same
  array hold the egg unlock conditions and which devices each egg shipped on.

**Names** come from the Digimon Database project — production data at
`https://digimon-db.omnipet.app.br/api/digimon` and
`\\192.168.100.250\appdata\digimon-db` (`output/digimon.json`, 1500+ records
with English, dub and alternative spellings). `normalize_names.py` reports and applies
the difference (dry run by default, `--write` to apply); it renames the sprite
sets alongside the JSON, and refuses a rename that is ambiguous or that would
collide with a name the module already uses. The normalised form is the database's
**English** name — 955 of the shared library's 1033 sprite sets match one,
against 5 that match only a dub. Digitama are excluded: they are each module's
own furniture, not Digimon. Module sprite sheets are also published to that share
under `sprites/<MODULE>/monsters/`, under their normalised names — only
sheets holding every frame 0-14 (15/SPECIAL may be absent), and never eggs.

The established workflow per module is: **parse sources → validate read-only →
report → apply only what was approved.** `utilities/claude/` follows that
shape — `parse_<mod>_sources.py`, `validate_<mod>.py`, `fix_<mod>.py`,
`build_<mod>.py`. Fix scripts default to a dry run and take `--write`.

The Vital Bracelet pipeline in `utilities/claude/` runs in this order, and
each step caches so a re-run is cheap:

| script | what |
|---|---|
| `vb_join.py` | pack ↔ version ↔ device art ↔ firmware, by name |
| `vb_resolve.py` | the same, settled with roster shape and the OCR tables |
| `vb_characters.py` | character ↔ monster, and the `index` values |
| `vb_refine.py` | untangles same-stage mix-ups via the evolution graph |
| `vb_validate.py` | diffs every mapped character against its card |
| `vb_order_report.py` | where record order differs from the card |
| `vb_reorder.py` | applies card order and writes indexes |
| `build_vb_devices.py` | `devices.json` |
| `add_special_frames.py` | frame 15 into the modules |
| `publish_special_frames.py` | frame 15 into the database |
| `vb_names.py` | database-backed name normalisation, used by all of them |

`check_jogress.py` is module-agnostic and worth running on anything with
jogress routes.

**modules/ is gitignored, so back a file up before a rewrite** — every fix
script above writes in place.

### Firmware dumps

Several modules were verified against device dumps in `utilities/<MODULE>/`.
They are flat ROM images with fixed-stride record tables; the reliable way in
is known-plaintext — take stats already known from humulos and search for the
stride that lines them all up. DMXW's is documented in the session notes:
86 monster records of 48 bytes at `0x26574`, a 21-entry DigiXros recipe table
at `0x24310`, and a sprite pointer table at `0x80000` whose offsets are
relative to `0x80004`.

## Conventions

- Match the surrounding code — comment density, naming, structure.
- Prefer fixing the data over widening engine behaviour; prefer a module-aware
  rule over a special case when a check needs relaxing.
- When a device's behaviour and a fan source disagree, the device wins; say
  which one a value came from.

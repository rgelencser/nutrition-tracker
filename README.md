# NutriTool

A local nutrient intake tracker: a small Flask server on your machine that
serves the frontend and stores your data in a JSON file on disk. Log foods,
see running levels of 29 nutrients against personalized targets, with old
intake "decaying" over time and low-trending nutrients flagged. No accounts,
no cloud backend, no external network calls ever — the app never talks to
anything but its own server on `localhost`.

Because the data lives in a plain JSON file rather than browser
`localStorage`, you can point it at a folder synced by Dropbox / Google
Drive / OneDrive / iCloud and reach the exact same dataset from any browser
(Chrome, Firefox, Safari, Edge) on any device — as long as that device is
running its own local copy of this server pointed at the same file. See
[Data storage & multi-device setup](#data-storage--multi-device-setup) below.

## Running it

```bash
pip install -r requirements.txt
python app.py
```

The server prints the URL to open, e.g. `http://localhost:5000` — open that
in any browser. That's the whole setup: no other build step, no account, no
internet access required to run it (only the one-time `pip install`, which
needs internet to download the `Flask` package itself; the app's own runtime
behavior makes zero external network calls — see the Data storage section).

## Data storage & multi-device setup

Your data (settings, custom foods, log history) lives in a single JSON file
on disk, read and written by `app.py` through two endpoints the frontend
calls instead of touching `localStorage`:

- `GET /api/data` — returns the full dataset (`{ config, customFoods, log }`)
- `POST /api/data` — accepts a full or partial update (any of those three
  top-level keys you send replaces that key; anything you omit is left alone)

**Where the file lives**: controlled by `config.json`, created next to
`app.py` the first time you run it if it doesn't already exist, e.g.:

```json
{ "data_file_path": "./data/nutritool_data.json" }
```

That default keeps data local to this folder. To sync across devices, edit
`data_file_path` to point into a cloud-synced folder instead, e.g.:

```json
{ "data_file_path": "~/Dropbox/nutritool/data.json" }
```

`~` expands to your home directory. If the target folder doesn't exist yet,
the server creates it on startup. `config.json` itself is **not** synced or
committed to this repo (it's gitignored) — you set it once per device.

**Multi-device model**: install and run this server independently on each
device (laptop, desktop, etc.), and edit each device's `config.json` to point
at the *same* synced file path. The sync of the file itself is handled
entirely by your existing Dropbox/Drive/OneDrive/iCloud client — this app has
no sync logic of its own and makes no network calls to make that happen.

**Known limitation — last write wins**: this tool does not implement file
locking, conflict detection, or merge logic for simultaneous edits from two
devices at once. If you log food on your phone and laptop in the same few
seconds, whichever save reaches disk last overwrites the other. This is a
deliberate simplicity trade-off for a single-user personal tool — genuinely
concurrent multi-device edits are an edge case, not a design target. In
practice: don't run two devices against the same file at the exact same
moment and you won't notice this.

## Editing your personalization config

Two ways to set your profile:

1. **In-app**: open the **Settings** tab, edit age / sex / weight / height /
   activity level, click **Save Settings**. Takes effect immediately.
2. **In code**: edit the `DEFAULT_CONFIG` object near the top of the
   `<script type="text/babel">` block in `static/index.html`. This is only
   the *first-run default* — once you save via the Settings tab, the saved
   values in your data file (see [Data storage](#data-storage--multi-device-setup))
   take precedence over this block on every subsequent load.

Config fields:

| Field | Meaning |
|---|---|
| `age` | years (RDA tables are adult-only; ages under 19 are clamped to 19) |
| `sex` | `'male'` or `'female'` — several RDAs differ by sex (e.g. iron, due to menstrual losses) |
| `weightKg` | body weight in kg — drives calorie (Mifflin-St Jeor) and protein (0.8 g/kg) targets |
| `heightCm` | height in cm — drives calorie target |
| `activityLevel` | `'sedentary'` \| `'light'` \| `'moderate'` \| `'active'` — activity multiplier on BMR |

## The nutrient panel

29 nutrients, grouped as macronutrients (7), minerals (10), vitamins (12).
(The original spec summarized this as "28 total," but its own vitamin
enumeration lists 12 items — A, C, D, E, K, B1, B2, B3, B6, B12, Folate,
Choline — making 29. This tool follows the explicit enumeration.)

## The decay / target model — three classes

**1. Daily-reset** (7 macros, sodium, potassium, vitamin C, B-complex
vitamins B1/B2/B3/B6/B12/folate): totals reset at local midnight and compare
against that day's RDA. Flagged **LOW** below 70% of target.

Note: for sodium, saturated fat, and sugar, "low" isn't actually a bad
thing nutritionally — these are upper-limit-style nutrients (their "target"
here is really a ceiling: sodium's AI, a 10%-of-calories saturated-fat cap,
a 10%-of-calories added-sugar cap). The tool still applies the same
daily-reset/70%-flag framework to them for consistency, per spec, but a LOW
flag on sodium/satfat/sugar just means "you ate less than the reference
amount," not a deficiency.

**2. Calcium — no decay model.** Calcium is compared directly to its daily
RDA (like the daily-reset class, 70% flag threshold), but is *not* modeled
with any decay or rolling window. Why: calcium is tightly hormonally
regulated (parathyroid hormone, calcitonin, vitamin D) and buffered by bone
stores, so a day or two of low intake doesn't produce a "depleting level"
the way it does for iron or vitamin D. Real calcium deficiency effects (bone
density loss) develop over years. The in-app info icon next to Calcium
carries this explanation; the dashboard number is an intake-tracking
convenience only and does not reflect actual body calcium status.

**3. Slow-decay / lookback-window** (all other minerals + fat-soluble
vitamins): target = RDA × lookback-window-days. Running level = sum of
intake within that window, weighted by exponential decay based on the exact
elapsed time since each entry — a smooth fade, not a hard cliff at the
window edge:

```
contribution = amount_logged * 0.5 ^ (elapsedDays / halfLife)
```

Flagged **LOW** below 60% of the rolling target. Default half-life =
window/2, **except choline**, which uses an explicit 7-day half-life
regardless of its 30-day window (choline turns over faster than the other
nutrients sharing that window length — this is a deliberate override, not
derived from window/2).

| Nutrient | Window (days) | Half-life (days) | Basis |
|---|---|---|---|
| Vitamin D | 60 | 30 (window/2) | Sourced: 25(OH)D plasma half-life ~15-21 days |
| Vitamin A | 180 | 90 (window/2) | Sourced: liver reserve up to ~1yr, conservative half used |
| Vitamin K | 5 | 2.5 (window/2) | Sourced: minimal storage, ~1.5-day body pool turnover |
| Vitamin E | 21 | 10.5 (window/2) | Sourced but ambiguous: plasma half-life ~3 days vs. longer adipose storage |
| Iron | 90 | 45 (window/2) | Sourced: store depletion/repletion is a documented 3-6 month process |
| Zinc | 21 | 10.5 (window/2) | Sourced but ambiguous: plasma pool turns over in ~2 days, but most body zinc is in slower muscle/bone |
| Magnesium | 30 | 15 (window/2) | Unsourced estimate — shared default for minerals lacking turnover data |
| Phosphorus | 30 | 15 (window/2) | Unsourced estimate — shared default |
| Copper | 30 | 15 (window/2) | Unsourced estimate — shared default |
| Manganese | 30 | 15 (window/2) | Unsourced estimate — shared default |
| Selenium | 30 | 15 (window/2) | Unsourced estimate — shared default |
| Choline | 30 | **7 (explicit override, NOT window/2)** | Estimated, user-specified override |

This exact table lives as `LOOKBACK_TABLE` near the top of `static/index.html`,
with each row's basis annotated in code comments. In the dashboard, each
lookback nutrient shows a small badge (e.g. `60d / sourced`, `30d /
estimate`) so you can see at a glance which numbers are grounded in cited
pharmacokinetics versus which are placeholder estimates.

None of this is clinically authoritative — it's a rough personal-tracking
heuristic, not a physiological model validated against real depletion
curves. Treat flags as "worth a look," not a diagnosis.

## Data sources

- **RDA/AI targets**: NIH Office of Dietary Supplements (`ods.od.nih.gov`)
  fact sheets, which summarize the National Academies' Dietary Reference
  Intake (DRI) reports. Calorie target uses the Mifflin-St Jeor equation;
  macro targets (fat/carbs) use AMDR midpoints; saturated fat and added
  sugar use Dietary Guidelines for Americans upper-limit guidance (see
  `computeTargets()` in `static/index.html` for the exact formulas and
  per-nutrient comments).
- **Seed food list** (~100 foods, `SEED_FOODS` in `static/index.html`):
  per-100g values styled after USDA FoodData Central (`fdc.nal.usda.gov`)
  entries, but hand-entered from general nutrition knowledge rather than
  fetched live — this app makes no external network calls at runtime, so
  there's no live FDC API integration. Treat seed values as reasonable
  estimates for personal
  tracking, not lab-grade precision; spot-check anything nutrient-critical
  against FDC directly. Nutrients the assistant wasn't confident about for a
  given food were left as `null` ("no data") rather than defaulted to `0`
  ("no content") — the UI renders `null` as `—`.
- **Decay/lookback table**: see the table above; sourced rows cite the
  general pharmacokinetic literature on each nutrient's storage/turnover,
  unsourced rows are explicitly flagged as estimates.

## Custom foods

Add foods via the **Add Food** tab — name plus any subset of the 29
nutrients per 100g (leave fields blank for unknown values, stored as
`null`/no-data, not zero). Custom foods are stored under `customFoods` in
your data file, separately from the seed list, so they won't be overwritten
if you later update `SEED_FOODS` in `static/index.html`.

## Logging and history

**Log Food** tab: search/select a food, enter grams (or use the quick 50 /
100 / 150 / 200 / 250g buttons), click Log. Each log entry snapshots the
food's per-100g values and the grams logged, so later edits to a food's
nutrient profile don't retroactively change past history.

**History** tab: edit an entry's grams inline (nutrient contributions
recompute automatically) or delete it. Entries show their logged timestamp.

## File layout

- `app.py` — Flask server: serves the frontend and the `/api/data` REST API,
  handles `config.json` / data-file resolution and JSON read/write
- `requirements.txt` — just `Flask`
- `static/index.html` — the entire frontend (nutrient panel, decay model,
  seed food database, UI) — unchanged from the original except its
  persistence layer now calls `/api/data` instead of `localStorage`
- `static/vendor/` — React, ReactDOM, and Babel Standalone, vendored locally
  so the app never fetches them from a CDN at runtime (see Non-goals)
- `config.json` — generated on first run, gitignored (machine-specific: it
  holds the data file path for *this* device)
- `data/` — default local data folder (gitignored); irrelevant once you've
  repointed `config.json` at a synced folder
- `README.md` — this file

## Non-goals

No external API/network calls of any kind at runtime (React/ReactDOM/Babel
are vendored locally rather than loaded from a CDN, specifically so the app
never needs internet access to run — only `localhost`), no accounts, no
cloud backend, no built-in sync or conflict resolution (sync is delegated
entirely to whatever cloud-sync client you already run), no attempt at
clinical authority. All approximations (decay rates, lookback windows, seed
food values) are disclosed above and in-app rather than presented as exact.

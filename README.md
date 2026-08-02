# NutriTool

A local, single-file nutrient intake tracker. Log foods, see running levels of
29 nutrients against personalized targets, with old intake "decaying" over
time and low-trending nutrients flagged. No accounts, no server, no sync, no
network calls at runtime — everything lives in your browser's `localStorage`.

## Running it

Just open [`index.html`](index.html) in a browser. That's it — no install, no
build step. It loads React, ReactDOM, and Babel Standalone from a CDN
(unpkg.com) to transform the in-browser JSX, so you do need an internet
connection the first time a browser loads those scripts (they'll typically be
cached after that); the app itself never sends your data anywhere.

Your data (settings, custom foods, log history) is stored in that browser's
`localStorage` under the `nutritool.*` keys. It's local to one browser on one
machine — there's no sync between devices or browsers.

## Editing your personalization config

Two ways to set your profile:

1. **In-app**: open the **Settings** tab, edit age / sex / weight / height /
   activity level, click **Save Settings**. Takes effect immediately.
2. **In code**: edit the `DEFAULT_CONFIG` object near the top of the
   `<script type="text/babel">` block in `index.html`. This is only the
   *first-run default* — once you save via the Settings tab, your saved
   values in `localStorage` take precedence over this block on every
   subsequent load.

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

This exact table lives as `LOOKBACK_TABLE` near the top of `index.html`,
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
  `computeTargets()` in `index.html` for the exact formulas and per-nutrient
  comments).
- **Seed food list** (~100 foods, `SEED_FOODS` in `index.html`): per-100g
  values styled after USDA FoodData Central (`fdc.nal.usda.gov`) entries,
  but hand-entered from general nutrition knowledge rather than fetched live
  — this app makes no network calls at runtime, so there's no live FDC API
  integration. Treat seed values as reasonable estimates for personal
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
`null`/no-data, not zero). Custom foods are stored separately from the seed
list in `localStorage` (`nutritool.customFoods`), so they won't be
overwritten if you later update the seed list in `index.html`.

## Logging and history

**Log Food** tab: search/select a food, enter grams (or use the quick 50 /
100 / 150 / 200 / 250g buttons), click Log. Each log entry snapshots the
food's per-100g values and the grams logged, so later edits to a food's
nutrient profile don't retroactively change past history.

**History** tab: edit an entry's grams inline (nutrient contributions
recompute automatically) or delete it. Entries show their logged timestamp.

## File layout

- `index.html` — the entire app (config, data, decay model, UI)
- `README.md` — this file

## Non-goals

No external API calls, no accounts, no sync, no server, no attempt at
clinical authority. All approximations (decay rates, lookback windows, seed
food values) are disclosed above and in-app rather than presented as exact.

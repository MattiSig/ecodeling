# Public web component

`<ecodeling-experience>` is the browser boundary for immutable replay-v1 results. It validates a
bundle before exposing timeline or selection state and never calculates an economic transition.

## Embed API

Import the generated module, then provide a replay URL:

```html
<link rel="stylesheet" href="/assets/ecodeling-experience.css" />
<script type="module" src="/assets/ecodeling-experience.js"></script>
<ecodeling-experience
  src="/replays/canonical-v1.json.gz"
  initial-month="2025-04"
></ecodeling-experience>
```

Attributes:

- `src`: JSON or gzip-compressed replay-v1 URL. Omitting it renders the safe empty state.
- `initial-month`: an optional replay month selected after validation.
- `static`: disables nonessential motion independently of the operating-system preference.
- `api-base`: simulation API prefix used by Laboratory mode. Omitting it keeps Laboratory hidden,
  which is appropriate for static hosts; set it to `/api/v1` when the simulation service is
  available on the same origin.

Public methods are `reload()`, `setMonth(index)`, `select(selection)`, `play()`, `pause()`, and
`restart()`. Story, Explore, and Compare share the selected month, playback state, and selection,
so changing modes does not rewind the replay. Playback speed changes presentation timing only;
every step advances to the next recorded month. The element emits
composed, bubbling `ecodeling-ready`, `ecodeling-month-change`,
`ecodeling-selection-change`, and `ecodeling-error` custom events. Error details distinguish
network, decoding, and replay-compatibility failures. A host may provide static content through
`slot="fallback"`; a failed replay never removes that fallback.

## Visual system

The Industrial system inherits a host's `--bg`, `--fg`, `--muted`, `--rule`, and `--accent`
properties, with the profile site's warm black, off-white, grey, and gold as fallbacks. JetBrains
Mono is used throughout, numerals are tabular, panels are flat, and one-pixel rules replace rounded
cards and shadows. The economy circuit is the single signal field: recorded flows, the CPI marker,
active controls, and indexed comparison lines use gold. Nominal lines remain solid and indexed
lines dashed, so color is never the only regime cue. Reduced-motion and `static` replace continuous
movement with discrete state changes.

## Story and inspection

The six guided scenes are derived from replay contents: the first month, first `FX_SHOCK`, first
post-shock import flow, first CPI movement, first `CPI_REVALUATION`, and first recorded feedback
event. Scene copy names the underlying table or event, and selecting a scene moves the shared
timeline to that source month. The nominal story explicitly reports the absence of CPI principal
revaluation rather than inventing an equivalent event.

The economic circuit renders aggregate flows for the active regime and month. Line width is a
presentation scale of recorded ISK amounts; direction, amount, counterpart sectors, and ledger
entry remain available in exact-value labels and the flow table. Sector stocks, typed events, and
representative-household tracks come directly from the replay. Government and central-bank stocks
say “not modeled” when the bundle contains `null`; the interface never substitutes zero.

## Paired comparison

Compare mode validates the replay's nominal/indexed run IDs, shared seed, initialization, shock
path, named random streams, aggregate-series timelines, and units before rendering. Nominal,
indexed, and split-screen views all use the component's one timeline state. Sector selection is a
shared camera target across split panels, and one selected metric drives the chart and its exact
month readout.

The seven synchronized charts are CPI, policy rate, mortgage principal, debt service, consumption,
defaults, and bank equity. Solid nominal and dashed indexed paths share a time axis; the ochre time
rail follows the replay month. Every difference is explicitly `indexed − nominal`, names nominal as
the baseline, and retains the replay unit. Distribution tables compare the declared cohort keys and
label their values as cohort totals. Representative households are compared as individuals only
when counterpart IDs are reciprocal; otherwise the interface says that identities do not
correspond and falls back to the declared cohort rather than pairing unrelated people.

## Laboratory mode

Laboratory mode submits only the server's allowlisted bounded parameters, reports queued/running
progress, offers safe queued cancellation and retry after structured failures, and loads the
completed replay through the same replay-v1 validator as the canonical article. A custom result is
not installed until validation succeeds. Failures therefore leave the canonical replay intact,
and “Restore canonical replay” returns to the published bundle after a successful experiment.

## Commands

```bash
npm run build:web
npm run typecheck:web
npm run lint:web
npm run format:check
npm test
npm run test:browser
```

## Article and reader onboarding

Article is the first-reader default. `initial-mode="story"` (or `article`, `explore`, `compare`,
`laboratory`) explicitly chooses an entry point. Otherwise `?ecodeling-mode=compare` takes
precedence over the per-route, per-element session preference. Laboratory still requires
`api-base`. Storage failure does not prevent reading. Give multiple embeds stable `id` values to
keep their preferences independent.

The tablist uses Arrow Left/Right and Home/End with a single tab stop; touch and pointer actions
select the same panels. Article pauses playback. Its scroll position survives evidence links and
ordinary tab changes within the mounted component. Evidence links select the recorded month and,
where relevant, metric, sector, regime, or actual representative household. They preserve other
shared state. Returning to Article restores the previous reading position; it does not rewind the
clock. The article's charts and current-month cohort table follow that same clock. Opening and
closing evidence stays explicitly labeled with its own source months.

`reader-article.ts` reads the installed validated replay for every numerical claim. It contains no
copied canonical result constants or alternate chart source. A custom Laboratory replay is labeled
as such and offers canonical restoration. Missing values remain unavailable. The before/after
balance-sheet view uses month-end snapshots, which include settlement and defaults, and explicitly
does not equate their difference with the separate recorded revaluation event.

`reader-glossary.ts` is the authoritative browser glossary, adapted from `specs/21_glossary.md`.
Inline terms and the complete glossary share definitions and accessible descriptions. Pointer
hover, keyboard focus, touch activation, and Escape dismissal do not depend on native title
attributes. The introduction, glossary, and model limitations remain available during loading or
failure. Static and reduced-motion readers see the same tables, charts, and interpretation.

Reader verification includes every-month replay-to-claim reconciliation, missing/changed-value
fixtures, acronym coverage, keyboard/touch interaction, playback pause, state handoff, restored
scroll, all-tab axe audits, and desktop/mobile dark/light screenshots. To also test the real CV
route, use a disposable CV checkout (the test starts its Go server locally):

```bash
scripts/export-cv-assets.sh /path/to/disposable-cv/web/static/ecodeling
ECODELING_CV_CHECKOUT=/path/to/disposable-cv npm run test:cv
```

The CV gate verifies `/work/ecodeling`, Article-to-Story/Explore/Compare handoffs and returns,
host themes, accessibility, responsive containment, and absence of Laboratory/API requests. It
uses the exported production bundle; it does not publish or modify the CV source templates.

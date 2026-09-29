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

Public methods are `reload()`, `setMonth(index)`, `select(selection)`, `play()`, `pause()`, and
`restart()`. Story and Explore share the selected month, so leaving a guided scene for inspection
does not rewind the replay. Playback speed changes presentation timing only; every step advances
to the next recorded month. The element emits
composed, bubbling `ecodeling-ready`, `ecodeling-month-change`,
`ecodeling-selection-change`, and `ecodeling-error` custom events. Error details distinguish
network, decoding, and replay-compatibility failures. A host may provide static content through
`slot="fallback"`; a failed replay never removes that fallback.

## Visual system

The Organic system uses sand and oat surfaces, sage and moss structure, and clay, terracotta, or
ochre signals. Fraunces is packaged locally. Rounded sector silhouettes stay stable: households
are leaf-like, firms are shouldered, banks are arched, government is grounded, the central bank is
a ring, and the foreign sector is an angled seed. Stock marks are filled stable shapes; future
flow marks are paths with directional endpoints. Charts use moss axes, exact tabular labels, solid
nominal lines, and dashed indexed lines so color is never the only regime cue. Spacing follows a
4/8/16/32-pixel rhythm and motion uses gentle 300–500 ms easing. Reduced-motion and `static`
replace continuous movement with discrete state changes.

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

## Commands

```bash
npm run build:web
npm run typecheck:web
npm run lint:web
npm run format:check
npm test
npm run test:browser
```

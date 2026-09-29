# Interactive Web Experience

## Purpose

The public experience should let a reader watch an inflation shock propagate through the modeled economy, inspect the underlying mechanisms, and compare indexation regimes. Where a Laboratory service is explicitly enabled, a reader may also reproduce or vary the experiment within its public bounds.

The animation is a view of completed simulation results. It is not a second implementation of the economic model.

## Experience principles

1. **Truth before spectacle.** Every displayed stock, flow, and event comes from a versioned replay bundle.
2. **Mechanisms before verdicts.** The experience explains how outcomes arise without precommitting to a policy conclusion.
3. **Overview and inspection.** Readers can understand the system at a glance and inspect exact values and provenance.
4. **Comparison by construction.** Nominal and indexed runs use aligned timelines and intended common random streams.
5. **Animation is optional.** The same claims remain available through text, tables, and static charts.

## Economy scene

Use a stylized economic circuit rather than a literal geographic simulation. The scene should contain:

- a household district with a small set of representative households;
- domestic firms and shops;
- two banks;
- government and central bank;
- a harbor or boundary for imports, foreign prices, and exchange rates;
- a CPI indicator and simulation month;
- synchronized analytical charts.

Animated lines or tokens may represent aggregate wages, consumption, taxes, transfers, imports, credit, interest, and principal payments. Stock variables such as mortgage balances, deposits, and bank equity should use stable visual encodings distinct from flows.

Do not render all 1,000 households individually. Show deterministic representatives from declared cohorts and use distributions or aggregate marks for the population.

## Guided story

The canonical story should make this chain visible:

```text
foreign-price or exchange-rate shock
        -> import costs
        -> firm prices
        -> CPI
        -> indexed mortgage principal
        -> household and bank balance sheets
        -> consumption, credit, defaults, and policy response
```

Guided scenes should pause at important events, explain the mechanism in plain language, and allow the reader to leave the guide for free exploration without losing the current month.

## Reader controls

The canonical replay should provide:

- play, pause, restart, and playback speed;
- a month scrubber with visible shock and policy markers;
- nominal, indexed, and split-screen comparison views;
- sector and representative-household inspection;
- exact-value tooltips and links from visible events to their type and source month;
- chart selection for CPI, policy rate, mortgage principal, debt service, consumption, defaults, and bank equity;
- a reset action that restores the published canonical view.

Controls must remain usable on touch devices and by keyboard.

## Replay contract

Each replay bundle should have a schema version and contain these logical tables or equivalent structures:

```text
manifest
timeline
sector_snapshots
sector_flows
events
representative_agents
aggregate_series
distribution_series
scenario_pairing
```

The manifest identifies the model version, code commit, run ID, scenario, seed, parameter set, units, and available months. Events use explicit types such as `FX_SHOCK`, `CPI_REVALUATION`, `POLICY_RATE_CHANGE`, `ARREARS`, and `DEFAULT` rather than presentation-specific animation names.

Visual components should depend only on the replay contract, not on internal Python classes or database layouts.

## Representative agents

Representative tracks should be selected by a deterministic rule declared in run metadata. Initial cohorts should include, when available:

- low-income/high-LTV indexed borrower;
- other indexed borrower;
- nominal borrower;
- renter;
- debt-free homeowner or saver.

Selection should occur from the simulated population without rewriting histories or combining attributes from different agents. Stable IDs let a representative be followed across the full replay.

## Comparison behavior

Split-screen playback should keep paired runs locked to the same month. Camera, selected metric, and playback controls should remain synchronized. Differences should be calculated from authoritative outputs and labeled with direction, units, and baseline.

If a representative agent cannot be matched across regimes because the model changes population membership, compare declared cohorts instead of implying that two unrelated agents are the same person.

## Web architecture

The public visualization should be an embeddable browser component that consumes immutable replay data. SVG is appropriate for crisp sectors, labels, and interactive links; Canvas may be used for numerous transient flow particles. Analytical charts may share the same timeline state.

### Publication topology

The public release is hosted by the personal-site repository `MattiSig/cv`, not by a standalone
Ecodeling web service. The ownership boundary is:

```text
MattiSig/ecodeling
        -> build custom-element JavaScript and CSS
        -> select the immutable canonical replay
        -> export checksummed publication assets
MattiSig/cv
        -> vendor those assets under web/static/ecodeling/
        -> render /work/ecodeling in the native profile-site layout
        -> embed <ecodeling-experience>
        -> deploy the existing web service on Railway
```

`scripts/export-cv-assets.sh` is the reproducible handoff. It builds and copies
`ecodeling-experience.js`, `ecodeling-experience.css`, `canonical-v1.json.gz`, and `SHA256SUMS` to
the CV static tree. The CV application embeds the files in its Go binary and applies its existing
content-hash query parameters. A publication update must verify the exported checksums and commit
the vendored assets in both repositories. Ecodeling does not require a second Railway service for
canonical playback.

### Host and visual contract

The custom element must feel native inside the profile site rather than present a second visual
identity. Its default system is Industrial and inherits these host custom properties:

| Property | Profile default | Purpose |
|---|---:|---|
| `--bg` | `#121316` | page and instrument background |
| `--fg` | `#e7e5df` | primary text and nominal series |
| `--muted` | `#8e9199` | secondary labels and metadata |
| `--rule` | `#2b2e34` | one-pixel panel and control rules |
| `--accent` | `#d8a955` | active state, CPI, recorded flows, and indexed series |

JetBrains Mono is the sole interface family and numeric output uses tabular figures. Surfaces are
flat, with one-pixel rules instead of rounded cards, shadows, grain, or a separate paper palette.
Gold is the single signal color and must not become general decoration. The component follows the
host's light-mode token changes automatically; it does not ship its own font or a competing theme.
The full-width ruled model window is the one deliberate break from the profile site's narrow
reading column.

The default article loads a precomputed, compressed canonical replay. A custom experiment follows this sequence:

```text
validated reader parameters
        -> server-side Python simulation job
        -> cached analytical outputs
        -> validated replay export
        -> browser playback
```

Cache identity must include the model version and all result-affecting parameters. The server should allowlist exposed parameters, cap months and population size, rate-limit submissions, and return structured validation errors.

Laboratory is progressive enhancement, not a requirement of the published CV page. The
`api-base` attribute is opt-in: when it is absent or blank, Laboratory is not rendered and the
component makes no experiment API requests. The development host explicitly sets
`api-base="/api/v1"`. The CV publication omits it because Railway currently hosts only the static
canonical experience. A future public simulation service must be deployed and verified before the
CV host supplies an API base.

## States and failures

The canonical interface should explicitly handle loading, replay compatibility, missing optional
data, and static fallback. When Laboratory is enabled, it must additionally handle its job states:

- initial loading;
- simulation queued/running progress;
- invalid parameter input;
- failed or numerically invalid runs;
- incompatible replay schema versions;
- missing optional series;
- offline or static fallback for the canonical article.

A failed custom experiment must not disturb the canonical replay.

## Accessibility and responsive behavior

- Honor `prefers-reduced-motion` by replacing continuous movement with discrete state changes.
- Provide text summaries and static chart alternatives for guided scenes.
- Do not encode regime or direction using color alone.
- Maintain readable labels and controls at narrow mobile widths.
- Expose exact values and control names to assistive technology.
- Pause nonessential animation when the experience is off-screen.

## Export and publication

The canonical experience should support a reproducible static figure set and a recorded video or image sequence for channels that cannot embed the interactive component. These exports must identify the same run, commit, parameters, seed, and scenario used by the web replay.

The primary interactive publication is `/work/ecodeling` on the CV site. Its native page copy,
metadata, sitemap entry, and source link remain owned by `MattiSig/cv`; the custom element owns only
the replay interface inside the model window. Railway deploys the CV repository's `main` branch to
the existing `web` service. Publication verification must cover the live health endpoint, page,
JavaScript, CSS, replay asset, custom-element upgrade, browser console, and both host themes.

## Acceptance criteria

The first public release is complete when:

- the canonical replay loads without running the model;
- Story, Explore, and Compare modes work on desktop and mobile;
- the nominal/indexed pair stays aligned throughout playback;
- visible values reconcile with authoritative analytical outputs;
- each notable animation can be traced to a replay event or recorded flow;
- reduced-motion and static fallbacks communicate the same conclusions;
- a custom run, if enabled, executes only on the server and returns reproducibility metadata;
- malformed, oversized, or incompatible requests fail safely;
- `/work/ecodeling` loads the vendored canonical replay without a Python service;
- the component inherits the CV site's dark and light tokens without a second font or theme;
- omitting `api-base` hides Laboratory and produces no failed API requests;
- exported publication assets pass `SHA256SUMS` verification and are content-versioned by the host.

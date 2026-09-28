---
name: build
description: Execute exactly one phase from Ecodeling's root build.md checklist, including implementation, scientific invariant tests, verification, checklist updates, and a phase commit. Use only when explicitly asked to run the next Ecodeling build pass; do not use for planning, status questions, reviews, or unrelated web development.
---

# Build

Advance Ecodeling by exactly one verified phase. This is a scientific agent-based macroeconomic model with an explanatory web replay, not a conventional CRUD application. Correct accounting, causal timing, determinism, experiment design, and replay provenance take priority over UI velocity.

## Start the pass

1. Resolve the repository root and read `build.md` completely.
2. Read `README.md`, applicable repository instructions, and every specification named by the first unchecked phase.
3. Inspect Git status, the current commit, existing code, and tests. Treat the current commit as the build-log baseline.
4. Select the first heading matching `## [ ] Phase`. Do not select a later phase even if it appears easier or more visible.
5. If no unchecked phase remains, run the repository's final documented verification without editing and report that the build is complete.

Existing user changes are not phase progress unless they satisfy the phase requirements and verification. Preserve unrelated changes and stop for direction only if they overlap in a way that cannot be resolved safely.

## Execute one phase

- Implement every unchecked subtask belonging to the active phase and nothing from later phases.
- Use the specifications as requirements. `build.md` controls order and gates; it does not override economic definitions or invariants.
- Prefer a thin end-to-end scientific slice over disconnected scaffolding, but remain inside the active phase.
- Add or update tests with the implementation. For economic rules, make the relevant test or fixture fail before implementing the rule whenever practical.
- Update subtask checkboxes only after the corresponding behavior and evidence exist.
- Do not check the phase heading until its full verification gate and acceptance statement pass.

Do not introduce generic web-app infrastructure early. Python model phases precede the public frontend. The frontend consumes versioned replay outputs and must never become a second economic engine.

## Scientific gates

Apply the gates relevant to the active phase:

- **Accounting:** every financial asset has a mirrored liability; transactions and revaluations reconcile; balance changes are never hidden mutations.
- **Time:** monthly stages follow the specified order; no rule reads future or same-period data before it becomes available.
- **Money and units:** use the project's declared exact monetary representation, rounding rules, real/nominal status, and price base.
- **Randomness:** derive named streams from the master seed; identical code, configuration, and seed reproduce authoritative outputs.
- **Comparison:** paired regimes share the intended initialization, matching, and shock streams; only declared structural differences vary.
- **Traceability:** important divergence is attributable to a rule, ledger event, behavioral response, or feedback channel.
- **Replay integrity:** browser data reconciles with analytical outputs; visible flows and events are recorded simulation results, never frontend inventions.
- **Research discipline:** distinguish assumptions, mechanisms, simulated results, interpretations, and empirical claims.

A pretty output, plausible trajectory, snapshot match, or passing UI test cannot substitute for these gates.

## Verify and close

1. Run the active phase's verification gate exactly as documented, plus any narrower tests used during development.
2. Run `git diff --check` and inspect the complete diff for scope, generated artifacts, secrets, and accidental output data.
3. If verification fails, diagnose and fix failures caused by the phase. Do not weaken an invariant, tolerance, seed assertion, or test merely to make the gate green.
4. When every subtask, gate, and acceptance criterion passes:
   - check all active-phase subtasks;
   - change its heading from `## [ ]` to `## [x]`;
   - append a dated `COMPLETE` build-log entry with the pre-phase baseline, verification commands, and material decisions;
   - commit the phase with subject `phase NN: <outcome>`;
   - stop without starting the next phase.
5. Push only when the user explicitly authorizes publishing during that invocation.

## Blocked or interrupted passes

If the phase cannot be completed safely:

- leave the phase heading unchecked;
- leave subtask boxes in their truthful state;
- append a dated `BLOCKED` entry with the baseline, checks performed, exact blocker, and safe next action;
- do not create a completion commit or start another phase;
- report the blocker concisely.

Do not mark a phase blocked merely because implementation is difficult. Exhaust in-scope diagnostics and documented alternatives first.

## Handoff

Report only what matters for the next pass:

- active phase and completion status;
- implemented scientific or product behavior;
- verification evidence;
- commit hash when completed;
- next unchecked phase, without beginning it;
- any residual risk or blocker.

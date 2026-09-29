import "@fontsource-variable/fraunces";

import { scaleLinear, scaleSqrt } from "d3";
import { LitElement, css, html, nothing, svg, type PropertyValues } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type {
  ReplayBundleV1,
  ReplayRegime,
  ReplaySector,
} from "../../replay/replay-v1-contract.d.ts";
import { loadReplay, ReplayLoadError } from "./replay-loader.js";
import {
  FLOW_LABELS,
  formatValue,
  SECTOR_LABELS,
  seriesValue,
  storyScenes,
  type StoryScene,
} from "./replay-presenter.js";
import { ReplayState, type ReplaySelection } from "./replay-state.js";

type LoadStatus = "empty" | "loading" | "ready" | "error";
type ExperienceMode = "story" | "explore";

export interface EcodelingReadyDetail {
  bundleId: string;
  months: number;
}

export interface EcodelingMonthChangeDetail {
  index: number;
  month: string;
}

const SECTORS: ReplaySector[] = [
  "households",
  "firms",
  "banks",
  "government",
  "central_bank",
  "foreign",
];
const SECTOR_POSITIONS: Record<ReplaySector, [number, number]> = {
  households: [16, 58],
  firms: [46, 25],
  banks: [47, 76],
  government: [72, 25],
  central_bank: [73, 76],
  foreign: [84, 50],
};
const METRICS = [
  ["cpi_level", "CPI"],
  ["monthly_inflation", "Monthly inflation"],
  ["mortgage_principal", "Mortgage principal"],
  ["consumption", "Consumption"],
] as const;

@customElement("ecodeling-experience")
export class EcodelingExperience extends LitElement {
  @property({ type: String }) src = "";
  @property({ type: String, attribute: "initial-month" }) initialMonth = "";
  @property({ type: Boolean, attribute: "static" }) staticMode = false;

  @state() private status: LoadStatus = "empty";
  @state() private replay: ReplayBundleV1 | null = null;
  @state() private message = "";
  @state() private revision = 0;
  @state() private reducedMotion = false;
  @state() private mode: ExperienceMode = "story";
  @state() private playing = false;
  @state() private speed = 1;
  @state() private storyIndex = 0;
  @state() private activeRegime: ReplayRegime = "indexed";
  @state() private visible = true;

  readonly replayState = new ReplayState();
  #abortController?: AbortController;
  #motionQuery?: MediaQueryList;
  #playbackTimer: number | null = null;
  #intersectionObserver?: IntersectionObserver;

  constructor() {
    super();
    this.replayState.addEventListener("change", (event) => {
      this.revision += 1;
      const reason = (event as CustomEvent<{ reason: string }>).detail.reason;
      if (reason === "month" && this.replayState.month !== null) {
        this.dispatchEvent(
          new CustomEvent<EcodelingMonthChangeDetail>(
            "ecodeling-month-change",
            {
              bubbles: true,
              composed: true,
              detail: {
                index: this.replayState.monthIndex,
                month: this.replayState.month,
              },
            },
          ),
        );
      }
      if (reason === "selection") {
        this.dispatchEvent(
          new CustomEvent<ReplaySelection | null>(
            "ecodeling-selection-change",
            {
              bubbles: true,
              composed: true,
              detail: this.replayState.selection,
            },
          ),
        );
      }
    });
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.setAttribute("role", "region");
    this.setAttribute("aria-label", "Ecodeling economic replay");
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    if (typeof window.matchMedia === "function") {
      this.#motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.reducedMotion = this.#motionQuery.matches;
      this.#motionQuery.addEventListener("change", this.#handleMotionChange);
    }
    if (typeof IntersectionObserver !== "undefined") {
      this.#intersectionObserver = new IntersectionObserver(([entry]) => {
        this.visible = entry?.isIntersecting ?? true;
        this.#syncPlayback();
      });
      this.#intersectionObserver.observe(this);
    }
    this.addEventListener("keydown", this.#handleKeydown);
  }

  override disconnectedCallback(): void {
    this.#abortController?.abort();
    this.#stopTimer();
    this.#intersectionObserver?.disconnect();
    this.#motionQuery?.removeEventListener("change", this.#handleMotionChange);
    this.removeEventListener("keydown", this.#handleKeydown);
    super.disconnectedCallback();
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has("src")) void this.#load();
    if (
      changed.has("playing" as never) ||
      changed.has("speed" as never) ||
      changed.has("staticMode") ||
      changed.has("reducedMotion" as never)
    )
      this.#syncPlayback();
  }

  async reload(): Promise<void> {
    await this.#load();
  }

  setMonth(index: number): void {
    this.replayState.setMonthIndex(index);
    if (index >= this.replayState.months.length - 1) this.playing = false;
  }

  select(selection: ReplaySelection | null): void {
    this.replayState.select(selection);
  }

  play(): void {
    if (this.staticMode || this.replayState.months.length === 0) return;
    if (this.replayState.monthIndex >= this.replayState.months.length - 1)
      this.setMonth(0);
    this.playing = true;
  }

  pause(): void {
    this.playing = false;
  }

  restart(): void {
    this.pause();
    this.setMonth(0);
  }

  #handleMotionChange = (event: MediaQueryListEvent): void => {
    this.reducedMotion = event.matches;
  };

  #handleKeydown = (event: KeyboardEvent): void => {
    if (this.status !== "ready") return;
    if (event.key === "ArrowLeft")
      this.setMonth(this.replayState.monthIndex - 1);
    else if (event.key === "ArrowRight")
      this.setMonth(this.replayState.monthIndex + 1);
    else if (event.key === "Home") this.setMonth(0);
    else if (event.key === "End")
      this.setMonth(this.replayState.months.length - 1);
    else if (event.key === " ") {
      if (this.playing) this.pause();
      else this.play();
    } else return;
    event.preventDefault();
  };

  #stopTimer(): void {
    if (this.#playbackTimer !== null) window.clearInterval(this.#playbackTimer);
    this.#playbackTimer = null;
  }

  #syncPlayback(): void {
    this.#stopTimer();
    if (!this.playing || !this.visible || this.staticMode) return;
    const interval = (this.reducedMotion ? 1400 : 900) / this.speed;
    this.#playbackTimer = window.setInterval(() => {
      const next = this.replayState.monthIndex + 1;
      if (next >= this.replayState.months.length) {
        this.pause();
        return;
      }
      this.setMonth(next);
    }, interval);
  }

  async #load(): Promise<void> {
    this.#abortController?.abort();
    this.#stopTimer();
    this.replay = null;
    this.message = "";
    this.playing = false;
    if (this.src.trim() === "") {
      this.status = "empty";
      return;
    }
    const controller = new AbortController();
    this.#abortController = controller;
    this.status = "loading";
    try {
      const replay = await loadReplay(this.src, { signal: controller.signal });
      if (controller.signal.aborted) return;
      this.replay = replay;
      this.replayState.configure(
        replay.manifest.months,
        this.initialMonth || undefined,
      );
      this.activeRegime = replay.runs.some((run) => run.regime === "indexed")
        ? "indexed"
        : (replay.runs[0]?.regime ?? "nominal");
      this.status = "ready";
      this.dispatchEvent(
        new CustomEvent<EcodelingReadyDetail>("ecodeling-ready", {
          bubbles: true,
          composed: true,
          detail: {
            bundleId: replay.manifest.bundle_id,
            months: replay.manifest.months.length,
          },
        }),
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const loadError =
        error instanceof ReplayLoadError
          ? error
          : new ReplayLoadError("decode", "The replay could not be prepared.", {
              cause: error,
            });
      this.status = "error";
      this.message = loadError.message;
      this.dispatchEvent(
        new CustomEvent("ecodeling-error", {
          bubbles: true,
          composed: true,
          detail: { kind: loadError.kind, message: loadError.message },
        }),
      );
    }
  }

  protected override render() {
    void this.revision;
    return html`
      <div
        class="frame"
        data-status=${this.status}
        data-motion=${this.reducedMotion || this.staticMode
          ? "reduced"
          : "normal"}
        aria-labelledby="experience-title"
        aria-busy=${this.status === "loading" ? "true" : "false"}
      >
        <div class="masthead">
          <div>
            <p class="eyebrow">Ecodeling replay</p>
            <h1 id="experience-title">
              Follow an inflation shock through the economy
            </h1>
          </div>
          <p class="principle">
            Recorded simulation results. No economics runs in this browser.
          </p>
        </div>
        ${this.#renderBody()}
      </div>
    `;
  }

  #renderBody() {
    if (this.status === "loading")
      return html`<section class="state" aria-live="polite">
        <span class="seed" aria-hidden="true"></span>
        <div>
          <h2>Loading replay</h2>
          <p>Reading and validating the published result bundle.</p>
        </div>
      </section>`;
    if (this.status === "error")
      return html`<section class="state error" role="alert">
        <div>
          <h2>Replay unavailable</h2>
          <p>${this.message}</p>
          <button type="button" @click=${() => void this.reload()}>
            Try again
          </button>
        </div>
        <slot name="fallback"
          ><p class="fallback">
            A static summary can be supplied in the fallback slot.
          </p></slot
        >
      </section>`;
    if (this.status === "empty" || this.replay === null)
      return html`<section class="state empty">
        <div>
          <h2>Replay not loaded</h2>
          <p>
            Set the <code>src</code> attribute to a validated replay v1 bundle.
          </p>
        </div>
        <slot name="fallback"></slot>
      </section>`;
    return this.#renderReady(this.replay);
  }

  #renderReady(replay: ReplayBundleV1) {
    const lastIndex = replay.manifest.months.length - 1;
    const progress = scaleLinear()
      .domain([0, Math.max(lastIndex, 1)])
      .range([0, 100])(this.replayState.monthIndex);
    const month = this.replayState.month ?? replay.manifest.months[0]!;
    const currentTimeline = replay.timeline[this.replayState.monthIndex];
    const scenes = storyScenes(replay, this.activeRegime);
    const scene = scenes[this.storyIndex] ?? scenes[0]!;
    return html`
      <section class="ready">
        <nav class="mode-tabs" aria-label="Experience mode">
          ${(["story", "explore"] as const).map(
            (mode) =>
              html`<button
                type="button"
                class=${this.mode === mode ? "active" : ""}
                aria-current=${this.mode === mode ? "page" : nothing}
                @click=${() => (this.mode = mode)}
              >
                ${mode === "story" ? "Story" : "Explore"}
              </button>`,
          )}
          <span
            >${this.reducedMotion || this.staticMode
              ? "Reduced motion"
              : "Motion on"}</span
          >
        </nav>

        <div class="month-ribbon">
          <div class="month-copy">
            <span>Simulation month</span><strong>${month}</strong>
          </div>
          <div class="timeline-wrap">
            <input
              aria-label="Simulation month"
              type="range"
              min="0"
              max=${lastIndex}
              .value=${String(this.replayState.monthIndex)}
              @input=${(event: InputEvent) =>
                this.setMonth(
                  Number((event.currentTarget as HTMLInputElement).value),
                )}
              style=${`--progress: ${progress}%`}
            />
            <div class="range-labels" aria-hidden="true">
              <span>${replay.manifest.months[0]}</span
              ><span>${replay.manifest.months[lastIndex]}</span>
            </div>
          </div>
          <div class="playback-controls" aria-label="Playback controls">
            <button type="button" @click=${() => this.restart()}>
              Restart
            </button>
            <button
              type="button"
              class="primary"
              ?disabled=${this.staticMode}
              @click=${() => (this.playing ? this.pause() : this.play())}
            >
              ${this.playing ? "Pause" : "Play"}
            </button>
            <label
              >Speed<select
                aria-label="Playback speed"
                .value=${String(this.speed)}
                @change=${(event: Event) =>
                  (this.speed = Number(
                    (event.currentTarget as HTMLSelectElement).value,
                  ))}
              >
                <option value="0.5">0.5×</option>
                <option value="1">1×</option>
                <option value="2">2×</option>
              </select></label
            >
          </div>
        </div>

        <div class="marker-row" aria-label="Timeline markers">
          ${replay.timeline.map((point) =>
            point.shock || point.policy_decision
              ? html`<button
                  type="button"
                  @click=${() => this.setMonth(point.index)}
                  title=${`${point.month}: ${
                    point.shock ? "shock" : "policy decision"
                  }`}
                >
                  <span>${point.shock ? "Shock" : "Policy"}</span
                  ><small>${point.month}</small>
                </button>`
              : nothing,
          )}
          ${!currentTimeline?.shock && !currentTimeline?.policy_decision
            ? html`<span class="quiet-marker">No event marker this month</span>`
            : nothing}
        </div>

        ${this.mode === "story" ? this.#renderStory(scenes, scene) : nothing}
        <div class="shell-grid">
          ${this.#renderEconomy(replay, month, scene)}
          ${this.#renderInspector(replay, month)}
        </div>
        ${this.#renderMetrics(replay, month)} ${this.#renderProvenance(replay)}
      </section>
    `;
  }

  #renderStory(scenes: StoryScene[], scene: StoryScene) {
    return html`<section class="story-panel" aria-labelledby="story-title">
      <div class="story-copy">
        <p class="eyebrow">Scene ${this.storyIndex + 1} of ${scenes.length}</p>
        <h2 id="story-title">${scene.title}</h2>
        <p>${scene.summary}</p>
        <small>Replay trace: ${scene.trace}</small>
      </div>
      <ol>
        ${scenes.map(
          (candidate, index) =>
            html`<li>
              <button
                type="button"
                class=${index === this.storyIndex ? "active" : ""}
                aria-current=${index === this.storyIndex ? "step" : nothing}
                @click=${() => {
                  this.storyIndex = index;
                  this.setMonth(
                    this.replayState.months.indexOf(candidate.month),
                  );
                }}
              >
                <span>${index + 1}</span>${candidate.title}<small
                  >${candidate.month}</small
                >
              </button>
            </li>`,
        )}
      </ol>
    </section>`;
  }

  #renderEconomy(replay: ReplayBundleV1, month: string, scene: StoryScene) {
    const flows = replay.sector_flows.filter(
      (flow) => flow.regime === this.activeRegime && flow.month === month,
    );
    const maxFlow = Math.max(...flows.map((flow) => flow.amount_isk), 1);
    const width = scaleSqrt().domain([0, maxFlow]).range([0.8, 2.4]);
    const focused = new Set(this.mode === "story" ? scene.focus : []);
    return html`<section class="stage" aria-labelledby="stage-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">${this.activeRegime} economy</p>
          <h2 id="stage-title">Recorded economic circuit</h2>
        </div>
        <div class="regime-toggle" aria-label="Run selection">
          ${replay.runs.map(
            (run) =>
              html`<button
                type="button"
                aria-pressed=${run.regime === this.activeRegime
                  ? "true"
                  : "false"}
                @click=${() => {
                  this.activeRegime = run.regime;
                  this.select({ kind: "run", id: run.run_id });
                }}
              >
                ${run.regime === "nominal" ? "Nominal" : "Indexed"}
              </button>`,
          )}
        </div>
      </div>
      <div class="circuit-wrap">
        <svg
          class="flow-layer"
          viewBox="0 0 100 100"
          width="100%"
          height="100%"
          preserveAspectRatio="none"
          role="img"
          aria-label=${`${flows.length} recorded aggregate flows in ${month}`}
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="3"
              markerHeight="3"
              markerUnits="userSpaceOnUse"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#c66b3d"></path>
            </marker>
          </defs>
          ${flows.map((flow) => {
            const [x1, y1] = SECTOR_POSITIONS[flow.source_sector];
            const [x2, y2] = SECTOR_POSITIONS[flow.target_sector];
            const label = `${FLOW_LABELS[flow.flow_type]}: ${formatValue(
              flow.amount_isk,
              "ISK",
            )}; ${SECTOR_LABELS[flow.source_sector]} to ${
              SECTOR_LABELS[flow.target_sector]
            }; ledger entry ${flow.ledger_entry_id}`;
            return svg`<g class="flow">
              <line
                x1=${x1}
                y1=${y1}
                x2=${x2}
                y2=${y2}
                style=${`stroke:#c66b3d;stroke-width:${width(flow.amount_isk)}px;opacity:.58`}
                marker-end="url(#arrow)"
                ><title>${label}</title></line
              >
              ${
                !this.reducedMotion && !this.staticMode
                  ? svg`<circle r="1.25">
                    <title>${label}</title>
                    <animateMotion
                      dur=${`${3 / this.speed}s`}
                      repeatCount="indefinite"
                      path=${`M ${x1} ${y1} L ${x2} ${y2}`}
                    ></animateMotion>
                  </circle>`
                  : nothing
              }
            </g>`;
          })}
        </svg>
        <div class="sector-field">
          ${SECTORS.map((sector) => {
            const snapshot = replay.sector_snapshots.find(
              (item) =>
                item.regime === this.activeRegime &&
                item.month === month &&
                item.sector === sector,
            );
            const selected =
              this.replayState.selection?.kind === "sector" &&
              this.replayState.selection.id === sector;
            return html`<button
              type="button"
              class=${`sector ${sector.replace("_", "-")} ${focused.has(sector) ? "focused" : ""}`}
              style=${`--x:${SECTOR_POSITIONS[sector][0]}%;--y:${SECTOR_POSITIONS[sector][1]}%`}
              aria-pressed=${selected ? "true" : "false"}
              @click=${() => this.select({ kind: "sector", id: sector })}
              title=${`${SECTOR_LABELS[sector]}. Equity: ${formatValue(
                snapshot?.equity_isk ?? null,
                "ISK",
              )}`}
            >
              <span aria-hidden="true"></span
              ><strong>${SECTOR_LABELS[sector]}</strong
              ><small
                >${snapshot?.equity_isk === null || snapshot === undefined
                  ? "Stock not modeled"
                  : formatValue(snapshot.equity_isk, "ISK") + " equity"}</small
              >
            </button>`;
          })}
          <div class="cpi-orbit" title="Consumer price index">
            <span>CPI</span
            ><strong
              >${formatValue(
                seriesValue(replay, this.activeRegime, "cpi_level", month)
                  ?.value ?? null,
                "index",
              )}</strong
            >
          </div>
        </div>
      </div>
      <details class="flow-table">
        <summary>Exact flows for ${month}</summary>
        <table>
          <thead>
            <tr>
              <th>Flow</th>
              <th>Route</th>
              <th>Amount</th>
              <th>Ledger entry</th>
            </tr>
          </thead>
          <tbody>
            ${flows.map(
              (flow) =>
                html`<tr>
                  <td>${FLOW_LABELS[flow.flow_type]}</td>
                  <td>
                    ${SECTOR_LABELS[flow.source_sector]} →
                    ${SECTOR_LABELS[flow.target_sector]}
                  </td>
                  <td>${formatValue(flow.amount_isk, "ISK")}</td>
                  <td><code>${flow.ledger_entry_id}</code></td>
                </tr>`,
            )}
          </tbody>
        </table>
      </details>
    </section>`;
  }

  #renderInspector(replay: ReplayBundleV1, month: string) {
    const events = replay.events.filter(
      (event) => event.regime === this.activeRegime && event.month === month,
    );
    const selectedSector =
      this.replayState.selection?.kind === "sector"
        ? (this.replayState.selection.id as ReplaySector)
        : null;
    const representatives = replay.representative_agents.filter(
      (agent) => agent.regime === this.activeRegime,
    );
    const selectedAgent =
      this.replayState.selection?.kind === "agent"
        ? representatives.find(
            (agent) => agent.household_id === this.replayState.selection?.id,
          )
        : undefined;
    const track = selectedAgent?.track.find((point) => point.month === month);
    const snapshot = selectedSector
      ? replay.sector_snapshots.find(
          (item) =>
            item.regime === this.activeRegime &&
            item.month === month &&
            item.sector === selectedSector,
        )
      : undefined;
    return html`<section class="inspector" aria-labelledby="inspector-title">
      <p class="eyebrow">Inspect ${month}</p>
      <h2 id="inspector-title">Exact recorded values</h2>
      ${selectedSector && snapshot
        ? html`<div class="inspection-card">
            <h3>${SECTOR_LABELS[selectedSector]}</h3>
            <dl>
              <div>
                <dt>Financial assets</dt>
                <dd>${formatValue(snapshot.financial_assets_isk, "ISK")}</dd>
              </div>
              <div>
                <dt>Liabilities</dt>
                <dd>${formatValue(snapshot.liabilities_isk, "ISK")}</dd>
              </div>
              <div>
                <dt>Equity</dt>
                <dd>${formatValue(snapshot.equity_isk, "ISK")}</dd>
              </div>
              <div>
                <dt>Inventory</dt>
                <dd>
                  ${formatValue(snapshot.inventory_units, "physical_units")}
                </dd>
              </div>
            </dl>
          </div>`
        : nothing}
      ${selectedAgent && track
        ? html`<div class="inspection-card">
            <h3>${selectedAgent.cohort.replaceAll("_", " ")}</h3>
            <p><code>${selectedAgent.household_id}</code></p>
            <dl>
              <div>
                <dt>Income</dt>
                <dd>${formatValue(track.wage_income_isk, "ISK")}</dd>
              </div>
              <div>
                <dt>Consumption</dt>
                <dd>${formatValue(track.consumption_isk, "ISK")}</dd>
              </div>
              <div>
                <dt>Mortgage</dt>
                <dd>${formatValue(track.mortgage_principal_isk, "ISK")}</dd>
              </div>
              <div>
                <dt>Revaluation</dt>
                <dd>${formatValue(track.mortgage_revaluation_isk, "ISK")}</dd>
              </div>
            </dl>
          </div>`
        : nothing}
      ${!selectedSector && !selectedAgent
        ? html`<p class="instruction">
            Select a sector or representative household. Values remain tied to
            this replay month.
          </p>`
        : nothing}
      <h3>Representative households</h3>
      <div class="agent-list">
        ${representatives.map(
          (agent) =>
            html`<button
              type="button"
              aria-pressed=${selectedAgent?.household_id === agent.household_id
                ? "true"
                : "false"}
              @click=${() =>
                this.select({ kind: "agent", id: agent.household_id })}
            >
              <span>${agent.cohort.replaceAll("_", " ")}</span
              ><small>${agent.household_id}</small>
            </button>`,
        )}
      </div>
      <h3>Events this month</h3>
      ${events.length === 0
        ? html`<p>No typed event is recorded this month.</p>`
        : html`<ul class="event-list">
            ${events.map(
              (event) =>
                html`<li>
                  <button
                    type="button"
                    @click=${() => this.select({ kind: "event", id: event.id })}
                  >
                    <strong>${event.event_type.replaceAll("_", " ")}</strong
                    ><span>${formatValue(event.amount, event.unit)}</span
                    ><small>Source: ${event.source_id}</small>
                  </button>
                </li>`,
            )}
          </ul>`}
    </section>`;
  }

  #renderMetrics(replay: ReplayBundleV1, month: string) {
    return html`<section class="metric-strip" aria-label="Recorded indicators">
      ${METRICS.map(([name, label]) => {
        const point = seriesValue(replay, this.activeRegime, name, month);
        return html`<div>
          <span>${label}</span
          ><strong
            >${formatValue(point?.value ?? null, point?.unit ?? null)}</strong
          ><small>${this.activeRegime}, ${month}</small>
        </div>`;
      })}
    </section>`;
  }

  #renderProvenance(replay: ReplayBundleV1) {
    return html`<details class="provenance">
      <summary>Replay provenance — ${replay.manifest.scenario_id}</summary>
      <dl>
        <div>
          <dt>Bundle</dt>
          <dd>${replay.manifest.bundle_id}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>${replay.manifest.model_version}</dd>
        </div>
        <div>
          <dt>Seed</dt>
          <dd>${replay.manifest.seed}</dd>
        </div>
        <div>
          <dt>Commit</dt>
          <dd><code>${replay.manifest.git_commit}</code></dd>
        </div>
      </dl>
    </details>`;
  }

  static override styles = css`
    :host {
      --sand: #e8dcc7;
      --oat: #d4b895;
      --sage: #8b9d83;
      --clay: #b08b6e;
      --terracotta: #c66b3d;
      --ochre: #c08e3a;
      --moss: #606c38;
      display: block;
      color: var(--moss);
      font-family: "Fraunces Variable", Fraunces, serif;
      font-variation-settings:
        "SOFT" 32,
        "WONK" 0;
      container-type: inline-size;
      outline-color: var(--terracotta);
    }
    *,
    *::before,
    *::after {
      box-sizing: border-box;
    }
    button,
    select,
    input {
      font: inherit;
    }
    button {
      color: inherit;
      cursor: pointer;
    }
    button:focus-visible,
    input:focus-visible,
    select:focus-visible,
    summary:focus-visible {
      outline: 0.22rem solid var(--terracotta);
      outline-offset: 0.2rem;
    }
    .frame {
      position: relative;
      overflow: hidden;
      min-height: 38rem;
      padding: clamp(1rem, 3.5cqi, 3.5rem);
      border-radius: clamp(1rem, 3cqi, 2rem);
      background: var(--sand);
      isolation: isolate;
    }
    .frame::before {
      position: absolute;
      z-index: -1;
      inset: 0;
      opacity: 0.025;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.82' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
      content: "";
      pointer-events: none;
    }
    .masthead {
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(15rem, 1fr);
      gap: 2rem;
      align-items: end;
      margin-bottom: clamp(1.5rem, 4cqi, 3.5rem);
    }
    h1,
    h2,
    h3,
    p {
      margin-top: 0;
    }
    h1 {
      max-width: 18ch;
      margin-bottom: 0;
      font-size: clamp(2.6rem, 7cqi, 6.5rem);
      font-weight: 670;
      letter-spacing: -0.055em;
      line-height: 0.88;
    }
    h2 {
      margin-bottom: 0.5rem;
      font-size: clamp(1.25rem, 2.6cqi, 2rem);
      line-height: 1.05;
    }
    h3 {
      margin: 1.4rem 0 0.65rem;
      font-size: 1rem;
    }
    .eyebrow {
      margin-bottom: 0.65rem;
      color: var(--terracotta);
      font-size: 0.75rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .principle {
      max-width: 27rem;
      margin-bottom: 0;
      padding-left: 1rem;
      border-left: 0.3rem solid var(--terracotta);
      line-height: 1.5;
    }
    .state {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 1.5rem;
      align-items: center;
      min-height: 14rem;
      padding: clamp(1.25rem, 4cqi, 3rem);
      border-radius: 2rem;
      background: var(--oat);
    }
    .state p {
      margin-bottom: 0;
      line-height: 1.5;
    }
    .seed {
      width: 3rem;
      aspect-ratio: 1;
      border-radius: 65% 35% 60% 40%;
      background: var(--moss);
      animation: breathe 1.8s ease-in-out infinite alternate;
    }
    .state.error {
      grid-template-columns: minmax(0, 1fr) minmax(12rem, 0.6fr);
      background: var(--clay);
    }
    .state button,
    .primary {
      min-height: 2.7rem;
      padding: 0.6rem 1rem;
      border: 0;
      border-radius: 1rem;
      color: var(--sand);
      background: var(--moss);
      font-weight: 700;
    }
    .fallback {
      padding: 1rem;
      border-radius: 1rem;
      background: var(--oat);
    }
    code {
      overflow-wrap: anywhere;
      font-family: inherit;
      font-variant-numeric: tabular-nums;
    }
    .mode-tabs {
      display: flex;
      gap: 0.4rem;
      align-items: center;
      margin-bottom: 0.6rem;
    }
    .mode-tabs button,
    .regime-toggle button {
      min-height: 2.65rem;
      padding: 0.55rem 1rem;
      border: 1px solid var(--moss);
      border-radius: 1rem;
      background: transparent;
      font-weight: 700;
    }
    .mode-tabs button.active,
    .regime-toggle button[aria-pressed="true"] {
      color: var(--sand);
      background: var(--moss);
    }
    .mode-tabs > span {
      margin-left: auto;
      padding: 0.45rem 0.7rem;
      border-radius: 1rem;
      background: var(--sage);
      font-size: 0.75rem;
      font-weight: 700;
    }
    .month-ribbon {
      display: grid;
      grid-template-columns: minmax(8rem, auto) minmax(12rem, 1fr) auto;
      gap: clamp(1rem, 3cqi, 2.5rem);
      align-items: center;
      padding: 1rem 1.25rem;
      border-radius: 1.5rem;
      color: var(--sand);
      background: var(--moss);
    }
    .month-copy span {
      display: block;
      color: var(--oat);
      font-size: 0.7rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .month-copy strong {
      font-size: clamp(1.35rem, 3cqi, 2.2rem);
      font-variant-numeric: tabular-nums;
    }
    input[type="range"] {
      width: 100%;
      accent-color: var(--terracotta);
      cursor: pointer;
    }
    .range-labels {
      display: flex;
      justify-content: space-between;
      color: var(--oat);
      font-size: 0.7rem;
      font-variant-numeric: tabular-nums;
    }
    .playback-controls {
      display: flex;
      gap: 0.4rem;
      align-items: center;
    }
    .playback-controls button {
      min-height: 2.55rem;
      padding: 0.5rem 0.75rem;
      border: 1px solid var(--sand);
      border-radius: 0.85rem;
      color: var(--sand);
      background: transparent;
    }
    .playback-controls button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .playback-controls .primary {
      color: var(--moss);
      background: var(--sand);
    }
    .playback-controls label {
      display: grid;
      gap: 0.1rem;
      color: var(--oat);
      font-size: 0.66rem;
    }
    .playback-controls select {
      min-height: 2rem;
      border: 0;
      border-radius: 0.65rem;
      color: var(--moss);
      background: var(--sand);
    }
    .marker-row {
      display: flex;
      gap: 0.45rem;
      min-height: 3.2rem;
      padding: 0.55rem 1rem;
      overflow-x: auto;
    }
    .marker-row button {
      display: grid;
      flex: 0 0 auto;
      padding: 0.35rem 0.7rem;
      border: 0;
      border-radius: 1rem;
      background: var(--oat);
      text-align: left;
    }
    .marker-row small,
    .quiet-marker {
      font-size: 0.7rem;
    }
    .quiet-marker {
      align-self: center;
    }
    .story-panel {
      display: grid;
      grid-template-columns: minmax(16rem, 0.7fr) minmax(0, 1.3fr);
      gap: 1rem;
      margin-bottom: 1rem;
      padding: clamp(1.2rem, 3cqi, 2rem);
      border-radius: 2rem;
      background: var(--clay);
    }
    .story-copy p {
      max-width: 42rem;
      margin-bottom: 0.7rem;
      line-height: 1.45;
    }
    .story-copy small {
      display: block;
      max-width: 38rem;
    }
    .story-panel ol {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.5rem;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .story-panel li button {
      display: grid;
      grid-template-columns: 1.5rem 1fr;
      gap: 0.15rem 0.45rem;
      align-items: center;
      width: 100%;
      min-height: 4.6rem;
      padding: 0.6rem;
      border: 1px solid var(--moss);
      border-radius: 1.1rem;
      background: var(--sand);
      text-align: left;
      line-height: 1.05;
    }
    .story-panel li button > span {
      display: grid;
      place-items: center;
      width: 1.5rem;
      aspect-ratio: 1;
      border-radius: 50%;
      color: var(--sand);
      background: var(--moss);
    }
    .story-panel li button small {
      grid-column: 2;
    }
    .story-panel li button.active {
      box-shadow: inset 0 0 0 0.18rem var(--moss);
      transform: translateY(-0.15rem);
    }
    .shell-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.75fr) minmax(18rem, 0.65fr);
      gap: 1rem;
    }
    .stage,
    .inspector,
    .provenance {
      min-width: 0;
      padding: clamp(1.2rem, 3cqi, 2rem);
      border-radius: 2rem;
    }
    .stage {
      background: var(--sage);
    }
    .inspector {
      background: var(--oat);
    }
    .section-heading {
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      align-items: start;
    }
    .regime-toggle {
      display: flex;
      gap: 0.35rem;
    }
    .circuit-wrap {
      position: relative;
      min-height: clamp(30rem, 54cqi, 48rem);
      margin-top: 1rem;
      overflow: hidden;
      border-radius: 1.7rem;
      background: var(--sand);
    }
    .flow-layer,
    .sector-field {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }
    .flow-layer {
      z-index: 1;
      overflow: visible;
      pointer-events: none;
    }
    .flow-layer line {
      stroke-linecap: round;
    }
    .flow-layer circle {
      fill: var(--ochre);
      stroke: var(--moss);
      stroke-width: 0.35;
    }
    .sector-field {
      z-index: 2;
      pointer-events: none;
    }
    .sector {
      position: absolute;
      left: var(--x);
      top: var(--y);
      display: grid;
      justify-items: center;
      width: clamp(7rem, 15cqi, 11rem);
      padding: 0.45rem;
      border: 0;
      border-radius: 1.4rem;
      background: transparent;
      text-align: center;
      transform: translate(-50%, -50%);
      pointer-events: auto;
    }
    .sector > span {
      display: block;
      width: clamp(3.3rem, 7cqi, 5.5rem);
      aspect-ratio: 1;
      margin-bottom: 0.35rem;
      border: 0.28rem solid var(--sand);
      background: var(--moss);
      box-shadow: 0 0.35rem 0 color-mix(in srgb, var(--moss) 30%, transparent);
      transition: transform 400ms ease;
    }
    .sector:hover > span,
    .sector.focused > span,
    .sector[aria-pressed="true"] > span {
      transform: scale(1.13);
    }
    .sector.focused {
      background: var(--oat);
      animation: breathe 1.8s ease-in-out infinite alternate;
    }
    .sector strong {
      font-size: clamp(0.75rem, 1.5cqi, 1rem);
    }
    .sector small {
      max-width: 13ch;
      font-size: 0.65rem;
      line-height: 1.15;
    }
    .sector.households > span {
      border-radius: 70% 30% 55% 45%;
    }
    .sector.firms > span {
      border-radius: 22% 22% 42% 42%;
      background: var(--terracotta);
    }
    .sector.banks > span {
      border-radius: 45% 45% 25% 25%;
      background: var(--clay);
    }
    .sector.government > span {
      border-radius: 1.4rem 1.4rem 0.45rem 0.45rem;
      background: var(--ochre);
    }
    .sector.central-bank > span {
      border: 0.55rem solid var(--moss);
      border-radius: 50%;
      background: transparent;
      box-shadow: none;
    }
    .sector.foreign > span {
      border-radius: 35% 65% 60% 40%;
      background: var(--terracotta);
      transform: rotate(-12deg);
    }
    .sector.foreign:hover > span,
    .sector.foreign.focused > span {
      transform: rotate(-12deg) scale(1.13);
    }
    .cpi-orbit {
      position: absolute;
      z-index: 3;
      left: 49%;
      top: 50%;
      display: grid;
      place-items: center;
      width: clamp(5rem, 10cqi, 7rem);
      aspect-ratio: 1;
      border: 0.45rem solid var(--ochre);
      border-radius: 50%;
      background: var(--sand);
      transform: translate(-50%, -50%);
    }
    .cpi-orbit span {
      font-size: 0.7rem;
      font-weight: 800;
      letter-spacing: 0.08em;
    }
    .cpi-orbit strong {
      font-size: clamp(1rem, 2.2cqi, 1.5rem);
    }
    .flow-table {
      margin-top: 1rem;
    }
    summary {
      cursor: pointer;
      font-weight: 750;
    }
    table {
      width: 100%;
      margin-top: 0.75rem;
      border-collapse: collapse;
      font-size: 0.75rem;
    }
    th,
    td {
      padding: 0.45rem;
      border-bottom: 1px solid var(--moss);
      text-align: left;
      vertical-align: top;
    }
    .instruction {
      line-height: 1.45;
    }
    .inspection-card {
      padding: 0.9rem;
      border-radius: 1.2rem;
      background: var(--sand);
    }
    .inspection-card h3 {
      margin-top: 0;
      text-transform: capitalize;
    }
    dl {
      margin: 0.7rem 0;
    }
    dl div {
      display: grid;
      grid-template-columns: minmax(6rem, 0.8fr) minmax(0, 1fr);
      gap: 0.6rem;
      padding: 0.4rem 0;
      border-bottom: 1px solid var(--clay);
    }
    dt {
      font-size: 0.74rem;
      font-weight: 750;
    }
    dd {
      min-width: 0;
      margin: 0;
      overflow-wrap: anywhere;
      font-size: 0.78rem;
      font-variant-numeric: tabular-nums;
    }
    .agent-list {
      display: grid;
      gap: 0.35rem;
    }
    .agent-list button,
    .event-list button {
      display: grid;
      gap: 0.15rem;
      width: 100%;
      padding: 0.55rem 0.65rem;
      border: 1px solid var(--moss);
      border-radius: 0.9rem;
      background: transparent;
      text-align: left;
      text-transform: capitalize;
    }
    .agent-list button[aria-pressed="true"] {
      color: var(--sand);
      background: var(--moss);
    }
    .agent-list small,
    .event-list small {
      overflow-wrap: anywhere;
      font-size: 0.65rem;
      text-transform: none;
    }
    .event-list {
      display: grid;
      gap: 0.4rem;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .event-list button {
      background: var(--sand);
    }
    .metric-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0.7rem;
      margin-top: 1rem;
    }
    .metric-strip > div {
      display: grid;
      gap: 0.2rem;
      min-width: 0;
      padding: 1rem;
      border-radius: 1.35rem;
      background: var(--clay);
    }
    .metric-strip span,
    .metric-strip small {
      font-size: 0.7rem;
    }
    .metric-strip strong {
      overflow-wrap: anywhere;
      font-size: clamp(1rem, 2cqi, 1.5rem);
      font-variant-numeric: tabular-nums;
    }
    .provenance {
      margin-top: 1rem;
      background: var(--oat);
    }
    @keyframes breathe {
      to {
        transform: scale(1.04) rotate(2deg);
      }
    }
    @container (max-width: 800px) {
      .masthead,
      .shell-grid,
      .story-panel {
        grid-template-columns: 1fr;
      }
      .month-ribbon {
        grid-template-columns: 1fr;
      }
      .story-panel ol {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .metric-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .circuit-wrap {
        min-height: 34rem;
      }
    }
    @container (max-width: 480px) {
      .frame {
        padding: 0.75rem;
      }
      .masthead {
        margin-bottom: 1.5rem;
      }
      h1 {
        font-size: clamp(2.35rem, 14cqi, 4rem);
      }
      .mode-tabs {
        flex-wrap: wrap;
      }
      .mode-tabs > span {
        margin-left: 0;
      }
      .playback-controls {
        flex-wrap: wrap;
      }
      .story-panel ol,
      .metric-strip {
        grid-template-columns: 1fr;
      }
      .section-heading {
        display: grid;
      }
      .circuit-wrap {
        min-height: 39rem;
      }
      .sector {
        width: 6.2rem;
      }
      .sector small {
        display: none;
      }
      .cpi-orbit {
        left: 50%;
      }
      .state,
      .state.error {
        grid-template-columns: 1fr;
      }
      .flow-table {
        overflow-x: auto;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
      }
    }
    [data-motion="reduced"] .seed,
    [data-motion="reduced"] .sector.focused {
      animation: none;
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    "ecodeling-experience": EcodelingExperience;
  }
}

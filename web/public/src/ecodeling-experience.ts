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
import {
  cohortDifferences,
  COMPARISON_METRICS,
  pairedSeries,
  representativeComparison,
  type CohortMeasure,
} from "./replay-comparison.js";
import { ReplayState, type ReplaySelection } from "./replay-state.js";
import {
  cancelLaboratoryExperiment,
  createLaboratoryExperiment,
  LaboratoryError,
  waitForLaboratoryExperiment,
  type LaboratoryParameters,
} from "./laboratory-client.js";

type LoadStatus = "empty" | "loading" | "ready" | "error";
type ExperienceMode = "story" | "explore" | "compare" | "laboratory";
type ComparisonView = ReplayRegime | "split";

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
  @property({ type: String, attribute: "api-base" }) apiBase = "/api/v1";

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
  @state() private comparisonView: ComparisonView = "split";
  @state() private selectedMetric = "cpi_level";
  @state() private cohortDimension = "income_quintile";
  @state() private cohortMeasure: CohortMeasure = "consumption_isk";
  @state() private cameraSector: ReplaySector = "households";
  @state() private visible = true;
  @state() private laboratoryStatus:
    | "idle"
    | "submitting"
    | "queued"
    | "running"
    | "completed"
    | "failed" = "idle";
  @state() private laboratoryProgress = 0;
  @state() private laboratoryMessage = "";
  @state() private customReplay = false;

  readonly replayState = new ReplayState();
  #canonicalReplay: ReplayBundleV1 | null = null;
  #laboratoryController?: AbortController;
  #laboratoryStatusUrl = "";
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
    this.#laboratoryController?.abort();
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
      this.#canonicalReplay = replay;
      this.customReplay = false;
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
          ${(["story", "explore", "compare", "laboratory"] as const).map(
            (mode) =>
              html`<button
                type="button"
                class=${this.mode === mode ? "active" : ""}
                aria-current=${this.mode === mode ? "page" : nothing}
                @click=${() => (this.mode = mode)}
              >
                ${mode === "story"
                  ? "Story"
                  : mode === "explore"
                    ? "Explore"
                    : mode === "compare"
                      ? "Compare"
                      : "Laboratory"}
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

        ${this.mode === "laboratory"
          ? this.#renderLaboratory()
          : this.mode === "compare"
            ? this.#renderComparison(replay, month)
            : html`${this.mode === "story"
                  ? this.#renderStory(scenes, scene)
                  : nothing}
                <div class="shell-grid">
                  ${this.#renderEconomy(replay, month, scene)}
                  ${this.#renderInspector(replay, month)}
                </div>
                ${this.#renderMetrics(replay, month)}`}
        ${this.#renderProvenance(replay)}
      </section>
    `;
  }

  #laboratoryParameters(form: HTMLFormElement): LaboratoryParameters {
    const data = new FormData(form);
    const number = (name: string): number => Number(data.get(name));
    return {
      months: number("months"),
      seed: number("seed"),
      households: number("households"),
      firms: number("firms"),
      indexation_lag_months: number("indexation_lag_months"),
      shock_kind: String(
        data.get("shock_kind"),
      ) as LaboratoryParameters["shock_kind"],
      shock_month: number("shock_month"),
      shock_magnitude_bps: number("shock_magnitude_bps"),
      shock_persistence: String(
        data.get("shock_persistence"),
      ) as LaboratoryParameters["shock_persistence"],
      import_share_bps: number("import_share_bps"),
      price_adjustment_bps: number("price_adjustment_bps"),
    };
  }

  async #submitLaboratory(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    this.#laboratoryController?.abort();
    const controller = new AbortController();
    this.#laboratoryController = controller;
    this.laboratoryStatus = "submitting";
    this.laboratoryProgress = 0;
    this.laboratoryMessage = "Validating the public parameter set.";
    try {
      const job = await createLaboratoryExperiment(
        this.apiBase,
        this.#laboratoryParameters(event.currentTarget as HTMLFormElement),
        { signal: controller.signal },
      );
      this.#laboratoryStatusUrl = job.links.status;
      this.laboratoryStatus = job.status === "completed" ? "running" : "queued";
      this.laboratoryMessage = job.cached
        ? "Loading the immutable cached result."
        : "The experiment is in the bounded worker queue.";
      const progress = await waitForLaboratoryExperiment(job.links.status, {
        signal: controller.signal,
        onProgress: (update) => {
          this.laboratoryStatus =
            update.status === "queued" ? "queued" : "running";
          this.laboratoryProgress = update.progress_percent;
          this.laboratoryMessage =
            update.status === "queued"
              ? "Waiting for a worker process."
              : "Python is running the paired simulation and replay checks.";
        },
      });
      const replay = await loadReplay(progress.result_url ?? job.links.result, {
        signal: controller.signal,
      });
      this.replay = replay;
      this.replayState.configure(replay.manifest.months);
      this.customReplay = true;
      this.laboratoryStatus = "completed";
      this.laboratoryProgress = 100;
      this.laboratoryMessage = `Loaded ${replay.manifest.bundle_id}. Reproducibility metadata is shown below.`;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      this.laboratoryStatus = "failed";
      this.laboratoryMessage =
        error instanceof LaboratoryError || error instanceof Error
          ? error.message
          : "The custom experiment failed.";
    }
  }

  async #cancelLaboratory(): Promise<void> {
    if (this.#laboratoryStatusUrl === "") return;
    try {
      await cancelLaboratoryExperiment(this.#laboratoryStatusUrl);
      this.#laboratoryController?.abort();
      this.laboratoryStatus = "idle";
      this.laboratoryMessage = "The queued experiment was cancelled safely.";
    } catch (error) {
      this.laboratoryMessage =
        error instanceof Error
          ? `${error.message} The canonical replay is still available.`
          : "The job could not be cancelled safely.";
    }
  }

  #restoreCanonical(): void {
    if (this.#canonicalReplay === null) return;
    this.replay = this.#canonicalReplay;
    this.replayState.configure(
      this.#canonicalReplay.manifest.months,
      this.initialMonth || undefined,
    );
    this.customReplay = false;
    this.laboratoryStatus = "idle";
    this.laboratoryMessage = "Restored the published canonical replay.";
  }

  #renderLaboratory() {
    const busy = ["submitting", "queued", "running"].includes(
      this.laboratoryStatus,
    );
    return html`<section class="laboratory" aria-labelledby="laboratory-title">
      <div class="compare-heading">
        <div>
          <p class="eyebrow">Bounded public experiment</p>
          <h2 id="laboratory-title">Laboratory</h2>
        </div>
        <p>
          Runs execute in isolated Python workers. The browser only receives a
          validated replay.
        </p>
      </div>
      <form
        @submit=${(event: SubmitEvent) => void this.#submitLaboratory(event)}
      >
        <label
          >Months<input
            name="months"
            type="number"
            min="6"
            max="60"
            value="18"
            required
        /></label>
        <label
          >Seed<input name="seed" type="number" min="0" value="1010" required
        /></label>
        <label
          >Households<input
            name="households"
            type="number"
            min="10"
            max="250"
            value="20"
            required
        /></label>
        <label
          >Firms<input
            name="firms"
            type="number"
            min="2"
            max="50"
            value="4"
            required
        /></label>
        <label
          >Indexation lag (months)<input
            name="indexation_lag_months"
            type="number"
            min="0"
            max="24"
            value="1"
            required
        /></label>
        <label
          >Shock
          <select name="shock_kind">
            <option value="fx_depreciation">FX depreciation</option>
            <option value="foreign_price_increase">
              Foreign-price increase
            </option>
          </select>
        </label>
        <label
          >Shock month<input
            name="shock_month"
            type="number"
            min="1"
            max="59"
            value="3"
            required
        /></label>
        <label
          >Shock magnitude (basis points)<input
            name="shock_magnitude_bps"
            type="number"
            min="-5000"
            max="5000"
            value="1000"
            required
        /></label>
        <label
          >Persistence
          <select name="shock_persistence">
            <option value="permanent">Permanent</option>
            <option value="one_off">One month</option>
          </select>
        </label>
        <label
          >Import share (basis points)<input
            name="import_share_bps"
            type="number"
            min="0"
            max="7500"
            value="2500"
            required
        /></label>
        <label
          >Price adjustment (basis points)<input
            name="price_adjustment_bps"
            type="number"
            min="100"
            max="10000"
            value="2500"
            required
        /></label>
        <div class="laboratory-actions">
          <button class="primary" type="submit" ?disabled=${busy}>
            ${this.laboratoryStatus === "failed"
              ? "Retry experiment"
              : "Run experiment"}
          </button>
          ${busy
            ? html`<button
                type="button"
                @click=${() => void this.#cancelLaboratory()}
              >
                Cancel if queued
              </button>`
            : nothing}
          ${this.customReplay
            ? html`<button
                type="button"
                @click=${() => this.#restoreCanonical()}
              >
                Restore canonical replay
              </button>`
            : nothing}
        </div>
      </form>
      <div class="laboratory-status" role="status" aria-live="polite">
        <strong>${this.laboratoryStatus}</strong>
        <progress max="100" .value=${this.laboratoryProgress}></progress>
        <span
          >${this.laboratoryMessage ||
          "Choose bounded parameters; the canonical replay remains untouched until a result validates."}</span
        >
      </div>
    </section>`;
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

  #renderComparison(replay: ReplayBundleV1, month: string) {
    const paired = pairedSeries(replay, this.selectedMetric);
    const point = paired?.points[this.replayState.monthIndex];
    const dimensions = [
      ...new Set(replay.distribution_series.map((item) => item.dimension)),
    ];
    const cohorts = cohortDifferences(
      replay,
      month,
      this.cohortDimension,
      this.cohortMeasure,
    );
    const selectedAgentId =
      this.replayState.selection?.kind === "agent"
        ? this.replayState.selection.id
        : null;
    const selectedAgent = selectedAgentId
      ? replay.representative_agents.find(
          (agent) => agent.household_id === selectedAgentId,
        )
      : undefined;
    const representative = selectedAgent
      ? representativeComparison(
          replay,
          selectedAgent.regime,
          selectedAgent.household_id,
        )
      : null;
    return html`<section class="comparison" aria-labelledby="compare-title">
      <div class="compare-heading">
        <div>
          <p class="eyebrow">Paired experiment</p>
          <h2 id="compare-title">One clock, two contract structures</h2>
          <p>
            Indexed minus nominal differences use the nominal run as the
            baseline. Both runs share seed
            ${replay.scenario_pairing.shared_seed} and the recorded shock path.
          </p>
        </div>
        <div class="view-toggle" aria-label="Comparison view">
          ${(["nominal", "split", "indexed"] as const).map(
            (view) =>
              html`<button
                type="button"
                aria-pressed=${this.comparisonView === view ? "true" : "false"}
                @click=${() => {
                  this.comparisonView = view;
                  if (view !== "split") this.activeRegime = view;
                }}
              >
                ${view === "split"
                  ? "Split screen"
                  : view === "nominal"
                    ? "Nominal"
                    : "Indexed"}
              </button>`,
          )}
        </div>
      </div>

      <div class=${`paired-scenes ${this.comparisonView}`}>
        ${this.comparisonView !== "indexed"
          ? this.#renderComparisonRun(replay, "nominal", month)
          : nothing}
        ${this.comparisonView !== "nominal"
          ? this.#renderComparisonRun(replay, "indexed", month)
          : nothing}
      </div>

      <section class="chart-panel" aria-labelledby="chart-title">
        <div class="chart-heading">
          <div>
            <p class="eyebrow">Synchronized analytical chart</p>
            <h3 id="chart-title">
              ${COMPARISON_METRICS.find(
                (metric) => metric.name === this.selectedMetric,
              )?.label}
            </h3>
          </div>
          <label
            >Metric<select
              aria-label="Comparison metric"
              .value=${this.selectedMetric}
              @change=${(event: Event) =>
                (this.selectedMetric = (
                  event.currentTarget as HTMLSelectElement
                ).value)}
            >
              ${COMPARISON_METRICS.map(
                (metric) =>
                  html`<option value=${metric.name}>${metric.label}</option>`,
              )}
            </select></label
          >
        </div>
        ${paired
          ? html`${this.#renderPairedChart(paired.points, paired.unit, month)}
              <div class="difference-readout" aria-live="polite">
                <div>
                  <span>Nominal</span
                  ><strong
                    >${formatValue(point?.nominal ?? null, paired.unit)}</strong
                  >
                </div>
                <div>
                  <span>Indexed</span
                  ><strong
                    >${formatValue(point?.indexed ?? null, paired.unit)}</strong
                  >
                </div>
                <div class="difference">
                  <span>Indexed − nominal</span
                  ><strong
                    >${this.#formatDifference(
                      point?.difference ?? null,
                      paired.unit,
                    )}</strong
                  ><small>Nominal baseline, ${month}</small>
                </div>
              </div>`
          : html`<p>This paired metric is not available in the replay.</p>`}
      </section>

      <div class="comparison-detail-grid">
        <section class="cohort-panel" aria-labelledby="cohort-title">
          <div class="chart-heading">
            <div>
              <p class="eyebrow">Declared cohort comparison</p>
              <h3 id="cohort-title">Distribution at ${month}</h3>
            </div>
            <div class="cohort-controls">
              <label
                >Cohort dimension<select
                  aria-label="Cohort dimension"
                  .value=${this.cohortDimension}
                  @change=${(event: Event) =>
                    (this.cohortDimension = (
                      event.currentTarget as HTMLSelectElement
                    ).value)}
                >
                  ${dimensions.map(
                    (dimension) =>
                      html`<option value=${dimension}>
                        ${dimension.replaceAll("_", " ")}
                      </option>`,
                  )}
                </select></label
              >
              <label
                >Measure<select
                  aria-label="Cohort measure"
                  .value=${this.cohortMeasure}
                  @change=${(event: Event) =>
                    (this.cohortMeasure = (
                      event.currentTarget as HTMLSelectElement
                    ).value as CohortMeasure)}
                >
                  <option value="consumption_isk">Consumption</option>
                  <option value="mortgage_principal_isk">
                    Mortgage principal
                  </option>
                  <option value="debt_service_isk">Debt service</option>
                  <option value="net_worth_isk">Net worth</option>
                  <option value="defaults">Defaults</option>
                </select></label
              >
            </div>
          </div>
          <div class="cohort-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Cohort</th>
                  <th>Nominal</th>
                  <th>Indexed</th>
                  <th>Indexed − nominal</th>
                </tr>
              </thead>
              <tbody>
                ${cohorts.map(
                  (cohort) =>
                    html`<tr>
                      <td>${cohort.cohort.replaceAll("_", " ")}</td>
                      <td>
                        ${formatValue(
                          cohort.nominal,
                          this.cohortMeasure === "defaults"
                            ? "households"
                            : "ISK",
                        )}
                      </td>
                      <td>
                        ${formatValue(
                          cohort.indexed,
                          this.cohortMeasure === "defaults"
                            ? "households"
                            : "ISK",
                        )}
                      </td>
                      <td>
                        ${this.#formatDifference(
                          cohort.difference,
                          this.cohortMeasure === "defaults"
                            ? "households"
                            : "ISK",
                        )}
                      </td>
                    </tr>`,
                )}
              </tbody>
            </table>
          </div>
          <p class="baseline-note">
            Values are recorded cohort totals; differences use nominal as the
            baseline. Units are
            ${this.cohortMeasure === "defaults"
              ? "households"
              : "nominal whole ISK"}.
          </p>
        </section>

        <section class="matching-panel" aria-labelledby="matching-title">
          <p class="eyebrow">Representative correspondence</p>
          <h3 id="matching-title">Identity check</h3>
          <p>
            Select a nominal representative to verify whether the same simulated
            household exists in both runs.
          </p>
          <div class="agent-list">
            ${replay.representative_agents
              .filter((agent) => agent.regime === "nominal")
              .map(
                (agent) =>
                  html`<button
                    type="button"
                    aria-pressed=${selectedAgentId === agent.household_id
                      ? "true"
                      : "false"}
                    @click=${() =>
                      this.select({ kind: "agent", id: agent.household_id })}
                  >
                    <span>${agent.cohort.replaceAll("_", " ")}</span>
                    <small>${agent.household_id}</small>
                  </button>`,
              )}
          </div>
          ${representative
            ? html`<div class="match-result" role="status">
                <strong
                  >${representative.kind === "individual"
                    ? "Matched individual"
                    : "Cohort comparison only"}</strong
                >
                <p>
                  ${representative.kind === "individual"
                    ? `Stable identity ${representative.nominalId} is present in both regimes.`
                    : `The identities do not correspond. Comparing the declared ${representative.cohort.replaceAll("_", " ")} cohort instead.`}
                </p>
              </div>`
            : nothing}
        </section>
      </div>
    </section>`;
  }

  #renderComparisonRun(
    replay: ReplayBundleV1,
    regime: ReplayRegime,
    month: string,
  ) {
    const run = replay.runs.find((candidate) => candidate.regime === regime)!;
    return html`<article
      class=${`run-panel ${regime}`}
      aria-label=${`${regime} economy at ${month}`}
    >
      <div class="run-heading">
        <div>
          <span>${regime === "nominal" ? "Nominal" : "Indexed"}</span>
          <strong>${month}</strong>
        </div>
        <small>${run.run_id}</small>
      </div>
      <p class="camera-label">
        Shared camera: ${SECTOR_LABELS[this.cameraSector]}
      </p>
      <div class="sector-comparison" aria-label="Shared sector camera">
        ${SECTORS.map((sector) => {
          const snapshot = replay.sector_snapshots.find(
            (item) =>
              item.regime === regime &&
              item.month === month &&
              item.sector === sector,
          );
          return html`<button
            type="button"
            aria-pressed=${this.cameraSector === sector ? "true" : "false"}
            @click=${() => {
              this.cameraSector = sector;
              this.select({ kind: "sector", id: sector });
            }}
          >
            <span>${SECTOR_LABELS[sector]}</span>
            <strong>${formatValue(snapshot?.equity_isk ?? null, "ISK")}</strong>
            <small>equity</small>
          </button>`;
        })}
      </div>
    </article>`;
  }

  #renderPairedChart(
    points: Array<{
      month: string;
      nominal: number | null;
      indexed: number | null;
    }>,
    unit: string,
    month: string,
  ) {
    const values = points.flatMap((point) =>
      [point.nominal, point.indexed].filter(
        (value): value is number => value !== null,
      ),
    );
    const minimum = values.length > 0 ? Math.min(...values) : 0;
    const maximum = values.length > 0 ? Math.max(...values) : 1;
    const spread = maximum - minimum || 1;
    const path = (key: "nominal" | "indexed") => {
      let started = false;
      return points
        .map((point, index) => {
          const value = point[key];
          if (value === null) {
            started = false;
            return "";
          }
          const x = 6 + (index / Math.max(points.length - 1, 1)) * 88;
          const y = 90 - ((value - minimum) / spread) * 76;
          const command = started ? "L" : "M";
          started = true;
          return `${command}${x.toFixed(2)},${y.toFixed(2)}`;
        })
        .join(" ");
    };
    const cursorX =
      6 + (this.replayState.monthIndex / Math.max(points.length - 1, 1)) * 88;
    return html`<div class="paired-chart">
      <svg
        viewBox="0 0 100 100"
        role="img"
        aria-label=${`Nominal and indexed ${this.selectedMetric} across ${points.length} aligned months; current month ${month}`}
        preserveAspectRatio="none"
      >
        <line class="chart-axis" x1="6" y1="90" x2="94" y2="90"></line>
        <line class="chart-axis" x1="6" y1="14" x2="6" y2="90"></line>
        <path class="nominal-line" d=${path("nominal")}></path>
        <path class="indexed-line" d=${path("indexed")}></path>
        <line
          class="shared-cursor"
          x1=${cursorX}
          x2=${cursorX}
          y1="10"
          y2="94"
        ></line>
      </svg>
      <div class="chart-legend">
        <span class="nominal-key">Nominal — solid</span>
        <span class="indexed-key">Indexed — dashed</span>
        <span>${unit}</span>
      </div>
    </div>`;
  }

  #formatDifference(value: number | null, unit: string): string {
    if (value === null) return "Not available";
    if (value === 0) return formatValue(0, unit);
    return `${value > 0 ? "+" : "−"}${formatValue(Math.abs(value), unit)}`;
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
    .comparison {
      display: grid;
      gap: 1rem;
    }
    .compare-heading,
    .chart-heading,
    .run-heading {
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      align-items: start;
    }
    .compare-heading {
      padding: clamp(1.2rem, 3cqi, 2rem);
      border-radius: 2rem;
      background: var(--clay);
    }
    .compare-heading p:not(.eyebrow) {
      max-width: 48rem;
      margin-bottom: 0;
      line-height: 1.45;
    }
    .laboratory {
      display: grid;
      gap: 1rem;
      padding: clamp(1rem, 2.5cqi, 1.7rem);
      border: 1px solid var(--line);
      border-radius: 2rem;
      background: var(--oat);
    }
    .laboratory form {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
      gap: 0.75rem;
    }
    .laboratory label {
      display: grid;
      gap: 0.3rem;
      color: var(--moss-dark);
      font-size: 0.78rem;
      font-weight: 700;
    }
    .laboratory input,
    .laboratory select {
      min-width: 0;
      padding: 0.65rem;
      border: 1px solid var(--line);
      border-radius: 0.7rem;
      background: var(--sand);
      color: var(--ink);
      font: inherit;
      font-variant-numeric: tabular-nums;
    }
    .laboratory-actions,
    .laboratory-status {
      grid-column: 1 / -1;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.65rem;
    }
    .laboratory-status {
      padding: 0.8rem;
      border-radius: 0.8rem;
      background: var(--sage);
    }
    .laboratory-status strong {
      text-transform: capitalize;
    }
    .laboratory-status progress {
      width: min(14rem, 100%);
      accent-color: var(--clay);
    }
    .view-toggle {
      display: flex;
      flex: 0 0 auto;
      gap: 0.35rem;
    }
    .view-toggle button {
      min-height: 2.65rem;
      padding: 0.55rem 0.85rem;
      border: 1px solid var(--moss);
      border-radius: 1rem;
      background: var(--sand);
      font-weight: 700;
    }
    .view-toggle button[aria-pressed="true"] {
      color: var(--sand);
      background: var(--moss);
    }
    .paired-scenes {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1rem;
    }
    .paired-scenes.nominal,
    .paired-scenes.indexed {
      grid-template-columns: 1fr;
    }
    .run-panel,
    .chart-panel,
    .cohort-panel,
    .matching-panel {
      min-width: 0;
      padding: clamp(1rem, 2.5cqi, 1.7rem);
      border-radius: 2rem;
    }
    .run-panel.nominal {
      background: var(--sage);
    }
    .run-panel.indexed {
      background: var(--oat);
    }
    .run-heading > div {
      display: grid;
    }
    .run-heading span {
      font-size: 0.72rem;
      font-weight: 750;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .run-heading strong {
      font-size: clamp(1.45rem, 3cqi, 2.25rem);
      font-variant-numeric: tabular-nums;
    }
    .run-heading small {
      max-width: 18rem;
      overflow-wrap: anywhere;
      text-align: right;
    }
    .camera-label {
      margin: 0.8rem 0 0.45rem;
      font-size: 0.75rem;
      font-weight: 700;
    }
    .sector-comparison {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.45rem;
    }
    .sector-comparison button {
      display: grid;
      gap: 0.25rem;
      min-width: 0;
      min-height: 6rem;
      padding: 0.65rem;
      border: 1px solid var(--moss);
      border-radius: 1.2rem;
      background: var(--sand);
      text-align: left;
    }
    .sector-comparison button[aria-pressed="true"] {
      box-shadow: inset 0 0 0 0.2rem var(--moss);
      transform: scale(1.02);
    }
    .sector-comparison span,
    .sector-comparison small {
      font-size: 0.68rem;
    }
    .sector-comparison strong {
      overflow-wrap: anywhere;
      font-size: clamp(0.78rem, 1.4cqi, 1rem);
      font-variant-numeric: tabular-nums;
    }
    .chart-panel {
      background: var(--sage);
    }
    .chart-heading label,
    .cohort-controls label {
      display: grid;
      gap: 0.2rem;
      font-size: 0.7rem;
      font-weight: 700;
    }
    .chart-heading select,
    .cohort-controls select {
      min-height: 2.5rem;
      padding: 0.35rem 0.55rem;
      border: 1px solid var(--moss);
      border-radius: 0.85rem;
      color: var(--moss);
      background: var(--sand);
    }
    .paired-chart {
      margin-top: 0.8rem;
      padding: 0.6rem;
      border-radius: 1.5rem;
      background: var(--sand);
    }
    .paired-chart svg {
      display: block;
      width: 100%;
      height: clamp(12rem, 26cqi, 21rem);
      overflow: visible;
    }
    .paired-chart path,
    .paired-chart line {
      vector-effect: non-scaling-stroke;
    }
    .chart-axis {
      stroke: var(--moss);
      stroke-width: 1;
      opacity: 0.45;
    }
    .nominal-line,
    .indexed-line {
      fill: none;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .nominal-line {
      stroke: var(--moss);
    }
    .indexed-line {
      stroke: var(--terracotta);
      stroke-dasharray: 8 5;
    }
    .shared-cursor {
      stroke: var(--ochre);
      stroke-width: 3;
    }
    .chart-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1rem;
      padding: 0.4rem 0.3rem 0;
      font-size: 0.72rem;
      font-weight: 700;
    }
    .chart-legend span:last-child {
      margin-left: auto;
    }
    .difference-readout {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.55rem;
      margin-top: 0.65rem;
    }
    .difference-readout > div {
      display: grid;
      gap: 0.15rem;
      padding: 0.75rem;
      border-radius: 1rem;
      background: var(--sand);
    }
    .difference-readout .difference {
      background: var(--oat);
    }
    .difference-readout span,
    .difference-readout small {
      font-size: 0.68rem;
    }
    .difference-readout strong {
      overflow-wrap: anywhere;
      font-size: clamp(1rem, 2cqi, 1.45rem);
      font-variant-numeric: tabular-nums;
    }
    .comparison-detail-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(16rem, 0.5fr);
      gap: 1rem;
    }
    .cohort-panel {
      background: var(--clay);
    }
    .matching-panel {
      background: var(--oat);
    }
    .cohort-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
    }
    .cohort-table-wrap {
      overflow-x: auto;
    }
    .cohort-table-wrap td:not(:first-child) {
      font-variant-numeric: tabular-nums;
    }
    .cohort-table-wrap td:first-child {
      text-transform: capitalize;
    }
    .baseline-note,
    .matching-panel > p:not(.eyebrow),
    .match-result p {
      margin: 0.75rem 0 0;
      font-size: 0.78rem;
      line-height: 1.4;
    }
    .match-result {
      margin-top: 0.75rem;
      padding: 0.8rem;
      border-radius: 1rem;
      background: var(--sand);
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
      .story-panel,
      .comparison-detail-grid {
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
      .compare-heading,
      .chart-heading,
      .run-heading {
        display: grid;
      }
      .view-toggle {
        flex-wrap: wrap;
      }
      .paired-scenes,
      .difference-readout {
        grid-template-columns: 1fr;
      }
      .sector-comparison {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .run-heading small {
        text-align: left;
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

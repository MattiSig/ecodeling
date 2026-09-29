import "@fontsource-variable/fraunces";

import { scaleLinear } from "d3";
import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import { customElement, property, state } from "lit/decorators.js";

import type { ReplayBundleV1 } from "../../replay/replay-v1-contract.d.ts";
import { loadReplay, ReplayLoadError } from "./replay-loader.js";
import { ReplayState, type ReplaySelection } from "./replay-state.js";

type LoadStatus = "empty" | "loading" | "ready" | "error";

export interface EcodelingReadyDetail {
  bundleId: string;
  months: number;
}

export interface EcodelingMonthChangeDetail {
  index: number;
  month: string;
}

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

  readonly replayState = new ReplayState();
  #abortController?: AbortController;
  #motionQuery?: MediaQueryList;

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
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    if (typeof window.matchMedia === "function") {
      this.#motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.reducedMotion = this.#motionQuery.matches;
      this.#motionQuery.addEventListener("change", this.#handleMotionChange);
    }
    this.addEventListener("keydown", this.#handleKeydown);
  }

  override disconnectedCallback(): void {
    this.#abortController?.abort();
    this.#motionQuery?.removeEventListener("change", this.#handleMotionChange);
    this.removeEventListener("keydown", this.#handleKeydown);
    super.disconnectedCallback();
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has("src")) void this.#load();
  }

  async reload(): Promise<void> {
    await this.#load();
  }

  setMonth(index: number): void {
    this.replayState.setMonthIndex(index);
  }

  select(selection: ReplaySelection | null): void {
    this.replayState.select(selection);
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
    else return;
    event.preventDefault();
  };

  async #load(): Promise<void> {
    this.#abortController?.abort();
    this.replay = null;
    this.message = "";
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
    if (this.status === "loading") {
      return html`
        <section class="state" aria-live="polite">
          <span class="seed" aria-hidden="true"></span>
          <div>
            <h2>Loading replay</h2>
            <p>Reading and validating the published result bundle.</p>
          </div>
        </section>
      `;
    }
    if (this.status === "error") {
      return html`
        <section class="state error" role="alert">
          <div>
            <h2>Replay unavailable</h2>
            <p>${this.message}</p>
            <button type="button" @click=${() => void this.reload()}>
              Try again
            </button>
          </div>
          <slot name="fallback">
            <p class="fallback">
              A static summary can be supplied in the fallback slot.
            </p>
          </slot>
        </section>
      `;
    }
    if (this.status === "empty" || this.replay === null) {
      return html`
        <section class="state empty">
          <div>
            <h2>Replay not loaded</h2>
            <p>
              Set the <code>src</code> attribute to a validated replay v1
              bundle.
            </p>
          </div>
          <slot name="fallback"></slot>
        </section>
      `;
    }
    return this.#renderReady(this.replay);
  }

  #renderReady(replay: ReplayBundleV1) {
    const lastIndex = replay.manifest.months.length - 1;
    const progress = scaleLinear()
      .domain([0, Math.max(lastIndex, 1)])
      .range([0, 100])(this.replayState.monthIndex);
    const currentTimeline = replay.timeline[this.replayState.monthIndex];
    return html`
      <section class="ready" aria-live="polite">
        <div class="month-ribbon">
          <div class="month-copy">
            <span>Simulation month</span>
            <strong>${this.replayState.month}</strong>
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
              <span>${replay.manifest.months[0]}</span>
              <span>${replay.manifest.months[lastIndex]}</span>
            </div>
          </div>
          <div class="markers" aria-label="Events this month">
            ${currentTimeline?.shock ? html`<span>Shock</span>` : nothing}
            ${currentTimeline?.policy_decision
              ? html`<span>Policy decision</span>`
              : nothing}
            ${!currentTimeline?.shock && !currentTimeline?.policy_decision
              ? html`<span>No timeline marker</span>`
              : nothing}
          </div>
        </div>

        <div class="shell-grid">
          <section class="stage" aria-labelledby="stage-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Economy view</p>
                <h2 id="stage-title">The recorded circuit will appear here</h2>
              </div>
              <span class="motion-state"
                >${this.reducedMotion || this.staticMode
                  ? "Reduced motion"
                  : "Motion ready"}</span
              >
            </div>
            <div class="sector-field" aria-label="Sector visual vocabulary">
              ${[
                ["households", "Households"],
                ["firms", "Firms"],
                ["banks", "Banks"],
                ["government", "Government"],
                ["central-bank", "Central bank"],
                ["foreign", "Foreign sector"],
              ].map(
                ([kind, label]) => html`
                  <div class="sector ${kind}">
                    <span aria-hidden="true"></span><small>${label}</small>
                  </div>
                `,
              )}
            </div>
            <p class="stage-note">
              Sector geometry is stable; later animation layers will use
              recorded flows and events.
            </p>
          </section>

          <section class="provenance" aria-labelledby="provenance-title">
            <p class="eyebrow">Replay provenance</p>
            <h2 id="provenance-title">${replay.manifest.scenario_id}</h2>
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
                <dd><code>${replay.manifest.git_commit.slice(0, 12)}</code></dd>
              </div>
            </dl>
            <div class="run-choices" aria-label="Replay runs">
              ${replay.runs.map(
                (run) => html`
                  <button
                    type="button"
                    aria-pressed=${this.replayState.selection?.id === run.run_id
                      ? "true"
                      : "false"}
                    @click=${() => this.select({ kind: "run", id: run.run_id })}
                  >
                    <span
                      >${run.regime === "nominal" ? "Nominal" : "Indexed"}</span
                    >
                    <small>${run.run_id}</small>
                  </button>
                `,
              )}
            </div>
          </section>
        </div>
      </section>
    `;
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

    .frame {
      position: relative;
      overflow: hidden;
      min-height: 38rem;
      padding: clamp(1rem, 4cqi, 3.5rem);
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
      margin-bottom: clamp(2rem, 6cqi, 5rem);
    }

    h1,
    h2,
    p {
      margin-top: 0;
    }

    h1 {
      max-width: 18ch;
      margin-bottom: 0;
      color: var(--moss);
      font-size: clamp(2.6rem, 7cqi, 6.5rem);
      font-weight: 670;
      letter-spacing: -0.055em;
      line-height: 0.88;
    }

    h2 {
      margin-bottom: 0.5rem;
      font-size: clamp(1.25rem, 2.6cqi, 2rem);
      font-weight: 620;
      line-height: 1.05;
    }

    .eyebrow {
      margin-bottom: 0.75rem;
      color: var(--terracotta);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .principle {
      max-width: 27rem;
      margin-bottom: 0;
      padding-left: 1rem;
      border-left: 0.3rem solid var(--terracotta);
      font-size: 1rem;
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

    button {
      min-height: 2.75rem;
      margin-top: 1rem;
      padding: 0.65rem 1rem;
      border: 0;
      border-radius: 1rem;
      color: var(--sand);
      background: var(--moss);
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }

    button:focus-visible,
    input:focus-visible {
      outline: 0.22rem solid var(--terracotta);
      outline-offset: 0.2rem;
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

    .month-ribbon {
      display: grid;
      grid-template-columns: minmax(8rem, auto) minmax(12rem, 1fr) minmax(
          8rem,
          auto
        );
      gap: clamp(1rem, 3cqi, 2.5rem);
      align-items: center;
      margin-bottom: 1rem;
      padding: 1rem 1.25rem;
      border-radius: 1.5rem;
      background: var(--moss);
      color: var(--sand);
    }

    .month-copy span {
      display: block;
      color: var(--oat);
      font-size: 0.72rem;
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
      font-size: 0.72rem;
      font-variant-numeric: tabular-nums;
    }

    .markers {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
      justify-content: flex-end;
    }

    .markers span,
    .motion-state {
      padding: 0.45rem 0.65rem;
      border-radius: 1rem;
      background: var(--sage);
      color: var(--moss);
      font-size: 0.75rem;
      font-weight: 650;
    }

    .shell-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(17rem, 0.7fr);
      gap: 1rem;
    }

    .stage,
    .provenance {
      min-width: 0;
      padding: clamp(1.2rem, 3cqi, 2.25rem);
      border-radius: 2rem;
    }

    .stage {
      background: var(--sage);
    }

    .provenance {
      background: var(--oat);
    }

    .section-heading {
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      align-items: start;
    }

    .sector-field {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1rem;
      margin-block: clamp(2rem, 6cqi, 4rem);
    }

    .sector {
      display: grid;
      justify-items: center;
      gap: 0.55rem;
      text-align: center;
    }

    .sector > span {
      display: block;
      width: clamp(2.4rem, 6cqi, 4.5rem);
      aspect-ratio: 1;
      background: var(--moss);
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
      border: 0.42rem solid var(--moss);
      border-radius: 50%;
      background: transparent;
    }

    .sector.foreign > span {
      border-radius: 35% 65% 60% 40%;
      background: var(--terracotta);
      transform: rotate(-12deg);
    }

    .sector small,
    .run-choices small {
      font-size: 0.74rem;
      line-height: 1.2;
    }

    .stage-note {
      max-width: 46rem;
      margin-bottom: 0;
      line-height: 1.5;
    }

    dl {
      margin-block: 1.5rem;
    }

    dl div {
      display: grid;
      grid-template-columns: 5rem minmax(0, 1fr);
      gap: 0.75rem;
      padding-block: 0.55rem;
      border-bottom: 1px solid var(--clay);
    }

    dt {
      font-size: 0.78rem;
      font-weight: 700;
    }

    dd {
      min-width: 0;
      margin: 0;
      overflow-wrap: anywhere;
      font-size: 0.84rem;
      font-variant-numeric: tabular-nums;
    }

    .run-choices {
      display: grid;
      gap: 0.55rem;
    }

    .run-choices button {
      display: grid;
      gap: 0.2rem;
      justify-items: start;
      width: 100%;
      margin: 0;
      text-align: left;
    }

    .run-choices button[aria-pressed="true"] {
      color: var(--moss);
      background: var(--sage);
    }

    @keyframes breathe {
      to {
        transform: scale(1.08) rotate(5deg);
      }
    }

    @container (max-width: 760px) {
      .masthead,
      .shell-grid {
        grid-template-columns: 1fr;
      }

      .masthead {
        align-items: start;
      }

      .month-ribbon {
        grid-template-columns: 1fr;
      }

      .markers {
        justify-content: flex-start;
      }
    }

    @container (max-width: 430px) {
      .frame {
        padding: 1rem;
      }

      .masthead {
        margin-bottom: 2rem;
      }

      h1 {
        font-size: clamp(2.45rem, 14cqi, 4rem);
      }

      .section-heading {
        display: block;
      }

      .motion-state {
        display: inline-block;
        margin-top: 0.5rem;
      }

      .sector-field {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .state,
      .state.error {
        grid-template-columns: 1fr;
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

    [data-motion="reduced"] .seed {
      animation: none;
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    "ecodeling-experience": EcodelingExperience;
  }
}

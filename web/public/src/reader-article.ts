import { html, nothing, type TemplateResult } from "lit";
import type {
  ReplayBundleV1,
  ReplayRegime,
  ReplaySector,
} from "../../replay/replay-v1-contract.d.ts";
import {
  pairedSeries,
  cohortDifferences,
  type PairedPoint,
} from "./replay-comparison.js";
import { formatValue } from "./replay-presenter.js";
import { METRIC_GUIDES, term } from "./reader-glossary.js";

export type ReaderMode =
  | "article"
  | "story"
  | "explore"
  | "compare"
  | "laboratory";
export const MODE_DESCRIPTIONS: Record<ReaderMode, string> = {
  article:
    "Start here: read the question, evidence, and conclusion at your own pace.",
  story:
    "Follow guided scenes through the recorded shock and its consequences.",
  explore: "Choose a month, then inspect a sector or an actual household.",
  compare:
    "Read both contract regimes at the same month and compare exact values.",
  laboratory:
    "Choose bounded parameters and ask the server to run a new experiment.",
};
export interface EvidenceTarget {
  mode: ReaderMode;
  month: string;
  metric?: string;
  regime?: ReplayRegime;
  sector?: ReplaySector;
  agent?: string;
  event?: string;
}

export function introduction() {
  return html`<section
    class="reader-intro"
    aria-labelledby="reader-intro-title"
  >
    <h2 id="reader-intro-title">When inflation changes the debt itself</h2>
    <p>
      Ecodeling is an educational agent-based model (${term("ABM", "intro")}):
      synthetic households, firms, and banks interact under explicit rules. We
      ask how mortgage price indexation changes <em>when</em> an
      imported-inflation shock reaches payments and <em>where</em> it appears on
      balance sheets.
    </p>
    <p>
      These are simulated results, not observations or forecasts of Iceland. The
      paired runs start from the same population and random seed and receive the
      same shock. Nominal loans price expected inflation into their coupon;
      indexed loans instead add realized price changes to principal after a lag,
      with a different coupon and rate pass-through.
    </p>
    <p>
      Look for the gap between cash paid now and debt left later. Begin with
      Article, then open the evidence in Story, Explore, or Compare.
    </p>
    <details class="reading-guide">
      <summary>How to read this model</summary>
      <p>
        The six sectors are households (work and spend), firms (hire and sell),
        banks (hold loans and deposits), government, the central bank (sets the
        policy rate), and the foreign sector (supplies imports). Government and
        central-bank balance-sheet values are unavailable, not zero.
      </p>
      <p>
        Stocks are balances at month end: debt, deposits, and equity. Flows are
        amounts during a month: wages, purchases, and payments. A revaluation
        changes a balance without moving cash. The scene uses stable sector
        shapes for stocks and moving or static lines for recorded flows.
      </p>
      <p>
        One shared clock controls all views. A shock marker locates the recorded
        external change. Nominal trajectories are solid; indexed trajectories
        are dashed. Compare the same month to avoid confusing the passage of
        time with the contract difference. Positive differences mean indexed
        exceeds the nominal baseline.
      </p>
      <p>
        Monetary values use nominal whole Icelandic krónur
        (${term("ISK", "guide")}). The Consumer Price Index
        (${term("CPI", "guide")}) chart uses a base of 100; raw replay indices
        use 100,000. Rates display percentages; the replay records basis points,
        with 100 basis points equal to one percentage point.
      </p>
      <p>
        Stock-flow consistency (${term("SFC", "guide")}) means each financial
        asset has a matching liability. Loan-to-value (${term("LTV", "guide")})
        describes debt relative to housing value; debt-service-to-income
        (${term("DSTI", "guide")}) describes the current payment burden. Foreign
        exchange (${term("FX", "guide")}) describes currency conversion. An
        impulse response function (${term("IRF", "guide")}) compares a shock
        with its own no-shock counterfactual; this reader's paired difference
        compares contract regimes.
      </p>
    </details>
    <p class="reader-limits">
      Interpretation: this is a mechanism experiment, not a policy verdict.
      Simplified housing, firms, expectations, default recovery, and bank
      payouts limit what can be concluded. Results depend on the chosen rules
      and seed.
    </p>
  </section>`;
}

// Every numerical result is selected from replay tables. These descriptors also drive reconciliation tests.
export function articleClaims(replay: ReplayBundleV1) {
  const first = replay.manifest.months[0]!;
  const last = replay.manifest.months.at(-1)!;
  return [
    "cpi_level",
    "mortgage_principal",
    "debt_service",
    "consumption",
    "defaults",
    "bank_equity",
  ].flatMap((metric) => {
    const series = pairedSeries(replay, metric);
    return series
      ? [first, last].map((month) => ({
          metric,
          unit: series.unit,
          ...series.points.find((p) => p.month === month)!,
        }))
      : [];
  });
}
export function evidenceValue(value: number | null, unit: string) {
  return unit === "index" && value !== null
    ? `${formatValue(value, unit)} index (base 100)`
    : formatValue(value, unit);
}
function direction(value: number | null) {
  return value === null
    ? "unavailable"
    : value > 0
      ? "higher"
      : value < 0
        ? "lower"
        : "equal";
}
export function article(
  replay: ReplayBundleV1,
  currentMonth: string,
  open: (target: EvidenceTarget) => void,
  chart: (
    points: PairedPoint[],
    unit: string,
    month: string,
    metric: string,
  ) => TemplateResult,
) {
  const first = replay.manifest.months[0]!;
  const last = replay.manifest.months.at(-1)!;
  const shock = replay.events.find(
    (e) =>
      e.regime === "indexed" &&
      ["FX_SHOCK", "FOREIGN_PRICE_SHOCK"].includes(e.event_type),
  );
  const revaluation = replay.events.find(
    (e) => e.regime === "indexed" && e.event_type === "CPI_REVALUATION",
  );
  const prior = revaluation
    ? replay.manifest.months[
        replay.manifest.months.indexOf(revaluation.month) - 1
      ]
    : undefined;
  const claims = articleClaims(replay);
  const action = (label: string, target: EvidenceTarget) =>
    html`<button type="button" @click=${() => open(target)}>${label}</button>`;
  const evidence = (metric: string, month: string) => {
    const series = pairedSeries(replay, metric);
    const p = series?.points.find((p) => p.month === month);
    if (!p || !series) return html`<p>Recorded ${metric} unavailable.</p>`;
    return html`<div
      class="article-evidence"
      data-metric=${metric}
      data-month=${month}
    >
      <p>${METRIC_GUIDES[metric]} Recorded simulated result at ${month}.</p>
      <dl class="evidence-values">
        <div>
          <dt>Nominal baseline</dt>
          <dd data-value="nominal">${evidenceValue(p.nominal, series.unit)}</dd>
        </div>
        <div>
          <dt>Indexed</dt>
          <dd data-value="indexed">${evidenceValue(p.indexed, series.unit)}</dd>
        </div>
        <div>
          <dt>Indexed − nominal (${direction(p.difference)})</dt>
          <dd data-value="difference">
            ${evidenceValue(p.difference, series.unit)}
          </dd>
        </div>
      </dl>
      <small
        >Source: aggregate_series / ${metric} / ${month};
        ${replay.manifest.bundle_id}</small
      >
      ${action("Compare this result", { mode: "compare", month, metric })}
    </div>`;
  };
  const trajectory = (metric: string) => {
    const series = pairedSeries(replay, metric);
    return series
      ? html`<figure>
          ${chart(series.points, series.unit, currentMonth, metric)}
          <figcaption>
            ${METRIC_GUIDES[metric]} Interval ${first} to ${last}; cursor
            ${currentMonth}. Source: aggregate_series / ${metric}. Solid nominal
            baseline; dashed indexed.
          </figcaption>
          ${evidence(metric, currentMonth)}
        </figure>`
      : nothing;
  };
  return html`<article class="reader-article" aria-label="Evidence walkthrough">
    <section id="article-question">
      <h2>The research question</h2>
      <p>
        Inflation changes what money buys. An indexed mortgage also lets it
        rewrite the debt contract. Does a smaller cash payment today coexist
        with a larger balance later? Following payments alone cannot answer that
        question.
      </p>
    </section>
    <section id="article-setup">
      <h2>The experimental setup</h2>
      <p>
        Assumption: index contracts, not people. Both runs use the same
        initialized population and shock path. Nominal coupons include expected
        inflation compensation and an inflation risk premium; indexed coupons
        combine a real rate and spreads with later principal indexation. The
        comparison therefore changes the documented contract structure, not just
        the label on an identical interest rate.
      </p>
      <p>
        Replay interval: ${first} to ${last}. Seed: ${replay.manifest.seed}.
        Structural difference:
        ${replay.scenario_pairing.structural_difference.replaceAll("_", " ")}.
        Named streams and common initialization are checked when loading this
        replay.
      </p>
      ${action("View in Story", { mode: "story", month: first })}
    </section>
    <section id="article-shock">
      <h2>The imported-inflation shock</h2>
      <p>
        Assumption: the foreign path changes outside the domestic economy. Firms
        buy imported inputs and adjust prices from their costs; the model then
        measures prices from actual simulated purchases.
      </p>
      ${shock
        ? html`<p class="article-event" data-event=${shock.id}>
              Recorded simulated event: ${shock.event_type.replaceAll("_", " ")}
              at ${shock.month}, ${formatValue(shock.amount, shock.unit)}.
              Source: ${shock.source_id}. The timeline shock marker identifies
              this same month.
            </p>
            <ol class="article-timeline" aria-label="Recorded shock timeline">
              <li>Replay begins ${first}</li>
              <li class="shock-marker">Shock ${shock.month}</li>
              <li>Replay ends ${last}</li>
            </ol>
            ${action("View shock in Story", {
              mode: "story",
              month: shock.month,
              event: shock.id,
              sector: "foreign",
            })}`
        : html`<p>No external shock event is recorded in this replay.</p>`}
    </section>
    <section id="article-prices">
      <h2>Firm prices and the consumer price response</h2>
      <p>
        Mechanism: more costly inputs can move firms' target prices, but prices
        adjust gradually. The recorded price index summarizes transactions,
        rather than imposing an inflation path on households.
      </p>
      ${trajectory("cpi_level")}
    </section>
    <section id="article-mortgages">
      <h2>Mortgage balances diverge</h2>
      <p>
        Mechanism: lagged prices change indexed principal before settlement. The
        borrower owes more and the bank holds a larger claim. This revaluation
        itself transfers no cash. The month-end view below also includes
        payments and any defaults; its before/after difference is not the
        isolated revaluation.
      </p>
      ${revaluation
        ? html`<p class="article-event" data-event=${revaluation.id}>
              Recorded first indexed revaluation: ${revaluation.month};
              ${formatValue(revaluation.amount, revaluation.unit)}. Source:
              ${revaluation.source_id}.
            </p>
            <div
              class="table-scroll"
              tabindex="0"
              role="region"
              aria-label="Mortgage balance-sheet comparison"
            >
              <table>
                <caption>
                  Balance-sheet before/after: indexed month-end stocks, nominal
                  whole Icelandic krónur (ISK). Source: sector_snapshots.
                </caption>
                <thead>
                  <tr>
                    <th>Position</th>
                    <th>Before: ${prior ?? "unavailable"}</th>
                    <th>After: ${revaluation.month}</th>
                  </tr>
                </thead>
                <tbody>
                  ${(
                    [
                      [
                        "households",
                        "liabilities_isk",
                        "Household liabilities",
                      ],
                      [
                        "banks",
                        "financial_assets_isk",
                        "Bank financial assets",
                      ],
                    ] as const
                  ).map(
                    ([sector, field, label]) =>
                      html`<tr>
                        <th>${label}</th>
                        ${[prior, revaluation.month].map(
                          (month) =>
                            html`<td
                              data-stock=${`${sector}:${field}:${month}`}
                            >
                              ${formatValue(
                                replay.sector_snapshots.find(
                                  (s) =>
                                    s.regime === "indexed" &&
                                    s.sector === sector &&
                                    s.month === month,
                                )?.[field] ?? null,
                                "ISK",
                              )}
                            </td>`,
                        )}
                      </tr>`,
                  )}
                </tbody>
              </table>
            </div>
            ${action("Inspect revaluation in Explore", {
              mode: "explore",
              month: revaluation.month,
              regime: "indexed",
              sector: "banks",
              event: revaluation.id,
            })}`
        : html`<p>No indexed revaluation is recorded.</p>`}
      ${trajectory("mortgage_principal")}
    </section>
    <section id="article-households">
      <h2>Household cash and bank effects</h2>
      <p>
        Interpretation: a lower payment can leave more cash available today. It
        does not establish lower lifetime cost. Default write-downs can reduce
        nominal principal, so the final principal gap is not all accumulated
        indexation.
      </p>
      ${trajectory("debt_service")}${evidence("consumption", last)}${evidence(
        "defaults",
        last,
      )}${evidence("bank_equity", last)}
    </section>
    <section id="article-distribution">
      <h2>Who experiences the difference?</h2>
      <p>
        Recorded simulated results: totals by initial income quintile at
        ${currentMonth}, in nominal whole Icelandic krónur (ISK). These are
        declared groups, not five illustrative people. Higher consumption
        expenditure does not distinguish higher prices from more goods.
      </p>
      <div
        class="table-scroll"
        tabindex="0"
        role="region"
        aria-label="Consumption by income cohort"
      >
        <table>
          <caption>
            Consumption by income cohort. Nominal baseline; difference is
            indexed − nominal. Source: distribution_series / income_quintile /
            ${currentMonth}.
          </caption>
          <thead>
            <tr>
              <th>Cohort</th>
              <th>Nominal</th>
              <th>Indexed</th>
              <th>Difference</th>
            </tr>
          </thead>
          <tbody>
            ${cohortDifferences(
              replay,
              currentMonth,
              "income_quintile",
              "consumption_isk",
            ).map(
              (c) =>
                html`<tr data-cohort=${c.cohort}>
                  <th>${c.cohort}</th>
                  <td>${formatValue(c.nominal, "ISK")}</td>
                  <td>${formatValue(c.indexed, "ISK")}</td>
                  <td>${formatValue(c.difference, "ISK")}</td>
                </tr>`,
            )}
          </tbody>
        </table>
      </div>
      <p>
        Representatives below are actual recorded households selected by
        declared cohort. Their histories are not cohort averages. “High LTV”
        means a high loan-to-value ratio.
      </p>
      ${replay.representative_agents
        .filter((a) => a.regime === "indexed")
        .map((a) =>
          action(`Inspect household: ${a.cohort.replaceAll("_", " ")}`, {
            mode: "explore",
            month: currentMonth,
            regime: "indexed",
            agent: a.household_id,
          }),
        )}
    </section>
    <section id="article-conclusion">
      <h2>Interpretation, limitations, and conclusion</h2>
      <p>
        Recorded simulated results: the table collects the opening and closing
        evidence for this paired run. Every difference is indexed minus the
        nominal baseline; negative means lower, positive means higher. Monetary
        values are nominal whole Icelandic krónur (ISK).
      </p>
      <div
        class="table-scroll"
        tabindex="0"
        role="region"
        aria-label="Opening and closing results"
      >
        <table>
          <caption>
            Opening versus closing paired results. Source: aggregate_series;
            ${replay.manifest.bundle_id}.
          </caption>
          <thead>
            <tr>
              <th>Metric / month</th>
              <th>Nominal</th>
              <th>Indexed</th>
              <th>Difference</th>
            </tr>
          </thead>
          <tbody>
            ${claims.map(
              (c) =>
                html`<tr data-claim=${`${c.metric}:${c.month}`}>
                  <th>${c.metric.replaceAll("_", " ")} / ${c.month}</th>
                  <td>${evidenceValue(c.nominal, c.unit)}</td>
                  <td>${evidenceValue(c.indexed, c.unit)}</td>
                  <td>${evidenceValue(c.difference, c.unit)}</td>
                </tr>`,
            )}
          </tbody>
        </table>
      </div>
      <p>
        In this run, indexed opening debt service is
        ${direction(
          claims.find((c) => c.metric === "debt_service" && c.month === first)
            ?.difference ?? null,
        )}
        than nominal; indexed closing principal is
        ${direction(
          claims.find(
            (c) => c.metric === "mortgage_principal" && c.month === last,
          )?.difference ?? null,
        )}.
        The cash-flow distinction is present at ${first};
        ${revaluation
          ? `the first recorded indexed principal revaluation arrives at ${revaluation.month}`
          : "no indexed principal revaluation is recorded"}.
        Final consumption, defaults, and bank equity above show why a mortgage
        calculator alone misses the wider response.
      </p>
      <p>
        Interpretation: contract design shifts the timing and location of
        exposure. A smaller early cash burden can coexist with more debt later.
        This conditional comparison does not identify real-world causal effects,
        rank household welfare, or show that either regime is preferable.
      </p>
      <p>
        Limitations: one generic good; stylized firms and expectations;
        initialized housing values without a housing market; no refinancing,
        prepayment, or demographics; zero-recovery defaults; bank interest
        returned to households; unavailable government and central-bank balance
        sheets. A short path with one seed is not a measure of uncertainty or
        long-run persistence.
      </p>
      <p>
        Next experiment: repeat across seeds and contract lags, then investigate
        wage indexation as a possible household hedge and wage-price feedback.
        Wage indexation is a research direction, not a result established here.
      </p>
      ${action("Compare closing results", {
        mode: "compare",
        month: last,
        metric: "mortgage_principal",
      })}
    </section>
    <p class="article-source">
      Replay provenance: ${replay.manifest.bundle_id}; model
      ${replay.manifest.model_version}; source commit
      ${replay.manifest.git_commit}. Run configurations:
      ${replay.runs
        .map((r) => `${r.regime}: ${r.configuration_hash}`)
        .join("; ")}.
      Analytical outputs and ledger records remain authoritative.
    </p>
  </article>`;
}

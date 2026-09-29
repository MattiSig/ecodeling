import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { afterEach, describe, expect, it, vi } from "vitest";
import { html, render } from "lit";
import { validateReplayV1 } from "../../replay/replay-v1-contract.mjs";
import {
  article,
  articleClaims,
  evidenceValue,
  introduction,
} from "../src/reader-article.js";
import { GLOSSARY, glossary } from "../src/reader-glossary.js";
import { formatValue } from "../src/replay-presenter.js";
import "../src/ecodeling-experience.js";

const replay: import("../../replay/replay-v1-contract.d.ts").ReplayBundleV1 =
  validateReplayV1(
    JSON.parse(
      gunzipSync(readFileSync("web/replay/canonical-v1.json.gz")).toString(),
    ),
  );
afterEach(() => {
  document.body.replaceChildren();
  sessionStorage.clear();
  vi.restoreAllMocks();
});
function renderArticle(
  bundle = replay,
  month = replay.manifest.months.at(-1)!,
) {
  const root = document.createElement("div");
  document.body.append(root);
  render(
    html`${introduction()}${glossary()}${article(
      bundle,
      month,
      () => {},
      () => html`<svg></svg>`,
    )}`,
    root,
  );
  return root;
}

describe("reader evidence", () => {
  it("orders the complete walkthrough and retains assumptions without replay loading", () => {
    const root = renderArticle();
    expect(
      [...root.querySelectorAll("article section")].map((s) => s.id),
    ).toEqual([
      "article-question",
      "article-setup",
      "article-shock",
      "article-prices",
      "article-mortgages",
      "article-households",
      "article-distribution",
      "article-conclusion",
    ]);
    expect(root.textContent).toContain("not observations or forecasts");
    expect(root.textContent).toContain("zero-recovery defaults");
    expect(root.textContent?.replace(/\s+/g, " ")).toContain(
      "not all accumulated indexation",
    );
  });

  it("reconciles every result cell, event and before/after stock with authoritative replay tables at every month", () => {
    for (const month of replay.manifest.months) {
      const root = renderArticle(replay, month);
      for (const cell of root.querySelectorAll<HTMLElement>(
        "[data-claim], [data-metric]",
      )) {
        const [metric, pointMonth] = cell.dataset.claim?.split(":") ?? [
          cell.dataset.metric,
          cell.dataset.month,
        ];
        const nominalSeries = replay.aggregate_series.find(
          (s) => s.regime === "nominal" && s.name === metric,
        )!;
        const nominal = nominalSeries.points.find(
          (p) => p.month === pointMonth,
        )!.value;
        const indexed = replay.aggregate_series
          .find((s) => s.regime === "indexed" && s.name === metric)!
          .points.find((p) => p.month === pointMonth)!.value;
        const difference =
          nominal === null || indexed === null ? null : indexed - nominal;
        const values = [...cell.querySelectorAll("td, dd")].map((c) =>
          c.textContent?.trim(),
        );
        expect(values).toEqual(
          [nominal, indexed, difference].map((v) =>
            evidenceValue(v, nominalSeries.unit),
          ),
        );
      }
      for (const row of root.querySelectorAll<HTMLElement>("[data-cohort]")) {
        const points = replay.distribution_series.filter(
          (p) =>
            p.month === month &&
            p.dimension === "income_quintile" &&
            p.cohort === row.dataset.cohort,
        );
        const n = points.find((p) => p.regime === "nominal")!.consumption_isk;
        const i = points.find((p) => p.regime === "indexed")!.consumption_isk;
        expect(
          [...row.querySelectorAll("td")].map((c) => c.textContent?.trim()),
        ).toEqual([n, i, i - n].map((v) => formatValue(v, "ISK")));
      }
      for (const cell of root.querySelectorAll<HTMLElement>("[data-stock]")) {
        const [sector, field, month] = cell.dataset.stock!.split(":");
        const snapshot = replay.sector_snapshots.find(
          (s) =>
            s.regime === "indexed" && s.sector === sector && s.month === month,
        )!;
        expect(cell.textContent?.trim()).toBe(
          formatValue(
            snapshot[field as "liabilities_isk" | "financial_assets_isk"],
            "ISK",
          ),
        );
      }
      for (const cell of root.querySelectorAll<HTMLElement>("[data-event]")) {
        const event = replay.events.find((e) => e.id === cell.dataset.event)!;
        expect(cell.textContent).toContain(event.month);
        expect(cell.textContent).toContain(event.source_id);
        expect(cell.textContent).toContain(
          formatValue(event.amount, event.unit),
        );
      }
      root.remove();
    }
  });

  it("changes claims with replay values and preserves missing values without a fabricated result", () => {
    const changed = structuredClone(replay);
    changed.aggregate_series
      .find((s) => s.name === "mortgage_principal" && s.regime === "indexed")!
      .points.at(-1)!.value = 123456;
    expect(
      articleClaims(changed).find(
        (c) =>
          c.metric === "mortgage_principal" &&
          c.month === changed.manifest.months.at(-1),
      )!.indexed,
    ).toBe(123456);
    changed.aggregate_series.find(
      (s) => s.name === "debt_service" && s.regime === "indexed",
    )!.points[0]!.value = null;
    const root = renderArticle(changed);
    expect(
      root.querySelector('[data-claim="debt_service:2025-01"]')?.textContent,
    ).toContain("Not available");
    expect(root.textContent).toContain("123,456 ISK");
  });

  it("covers every reader acronym with one authoritative, expanded and described glossary entry", () => {
    const root = renderArticle();
    const abbreviations = [
      "ABM",
      "CPI",
      "FX",
      "ISK",
      "LTV",
      "DSTI",
      "SFC",
      "IRF",
    ] as const;
    const specification = readFileSync("specs/21_glossary.md", "utf8");
    for (const term of abbreviations) {
      expect(specification).toContain(term);
      expect(root.textContent).toContain(GLOSSARY[term][0]);
      const trigger = root.querySelector(
        `[aria-describedby="definition-${term}"]`,
      )!;
      expect(trigger.textContent).toContain(GLOSSARY[term][0]);
      expect(root.querySelector(`#definition-${term}`)?.textContent).toBe(
        GLOSSARY[term][1],
      );
      expect(trigger.hasAttribute("title")).toBe(false);
    }
    // Fail if copy introduces a specialist uppercase abbreviation without an expansion.
    const withoutProvenance = root.cloneNode(true) as HTMLElement;
    withoutProvenance
      .querySelectorAll("small, .article-source, [data-event]")
      .forEach((n) => n.remove());
    for (const acronym of withoutProvenance.textContent!.match(
      /\b[A-Z]{2,5}\b/g,
    ) ?? []) {
      expect(Object.keys(GLOSSARY), `Unexpanded acronym: ${acronym}`).toContain(
        acronym,
      );
    }
  });

  it("keeps baseline introduction and glossary available when replay fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("missing", { status: 404 }),
    );
    const element = document.createElement("ecodeling-experience");
    element.src = "/missing";
    document.body.append(element);
    await vi.waitFor(() =>
      expect(element.shadowRoot?.textContent).toContain("Replay unavailable"),
    );
    expect(element.shadowRoot?.textContent).toContain(
      "When inflation changes the debt itself",
    );
    expect(element.shadowRoot?.querySelector("#definition-CPI")).not.toBeNull();
    expect(element.shadowRoot?.textContent).toContain("not a policy verdict");
  });
});

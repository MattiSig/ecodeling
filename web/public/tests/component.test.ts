import { afterEach, describe, expect, it, vi } from "vitest";

import "../src/ecodeling-experience.js";
import type { EcodelingExperience } from "../src/ecodeling-experience.js";

const replay = {
  manifest: {
    schema_version: 1,
    bundle_id: "embedded-test",
    model_version: "0.0.0",
    git_commit: "abcdef1234567890",
    scenario_id: "component-test",
    seed: 10,
    months: ["2025-01", "2025-02"],
    maximum_uncompressed_bytes: 20_000,
  },
  timeline: [
    { index: 0, month: "2025-01", shock: false, policy_decision: false },
    { index: 1, month: "2025-02", shock: true, policy_decision: false },
  ],
  runs: [
    { regime: "nominal", run_id: "nominal-run", configuration_hash: "n" },
    { regime: "indexed", run_id: "indexed-run", configuration_hash: "i" },
  ],
  sector_snapshots: [],
  sector_flows: [],
  events: [],
  representative_agents: [],
  aggregate_series: [],
  distribution_series: [],
  scenario_pairing: {
    nominal_run_id: "nominal-run",
    indexed_run_id: "indexed-run",
    shared_seed: 10,
    shared_initialization: true,
    shared_shock_path: true,
    shared_random_streams: ["shocks"],
    structural_difference: "mortgage_indexation_topology",
    matching: "stable_household_id",
  },
};

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("ecodeling-experience", () => {
  it("renders an embeddable empty state", async () => {
    const element = document.createElement("ecodeling-experience");
    document.body.append(element);
    await element.updateComplete;
    expect(element.shadowRoot?.textContent).toContain("Replay not loaded");
    expect(element.getAttribute("role")).toBe("region");
  });

  it("loads replay state and emits stable public events", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(replay)),
    );
    const element = document.createElement(
      "ecodeling-experience",
    ) as EcodelingExperience;
    const ready = vi.fn();
    const monthChanged = vi.fn();
    element.addEventListener("ecodeling-ready", ready);
    element.addEventListener("ecodeling-month-change", monthChanged);
    element.src = "/canonical.json";
    document.body.append(element);
    await vi.waitFor(() => expect(ready).toHaveBeenCalledOnce());
    element.setMonth(1);
    await element.updateComplete;
    expect(monthChanged).toHaveBeenCalledOnce();
    expect(element.shadowRoot?.textContent).toContain("2025-02");
    expect(element.shadowRoot?.textContent).toContain("Shock");
  });

  it("contains loader failures and retains slotted fallback content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("missing", { status: 404 }),
    );
    const element = document.createElement(
      "ecodeling-experience",
    ) as EcodelingExperience;
    const fallback = document.createElement("p");
    fallback.slot = "fallback";
    fallback.textContent = "Static published summary";
    element.append(fallback);
    element.src = "/missing.json";
    document.body.append(element);
    await vi.waitFor(() =>
      expect(element.shadowRoot?.textContent).toContain("Replay unavailable"),
    );
    expect(element.textContent).toContain("Static published summary");
  });

  it("keeps the canonical replay installed when a Laboratory request fails", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(replay)))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: { code: "queue_full", message: "Try again shortly." },
          }),
          { status: 429, headers: { "Content-Type": "application/json" } },
        ),
      );
    const element = document.createElement(
      "ecodeling-experience",
    ) as EcodelingExperience;
    element.src = "/canonical.json";
    document.body.append(element);
    await vi.waitFor(() =>
      expect(element.shadowRoot?.textContent).toContain("embedded-test"),
    );
    const laboratory = [...element.shadowRoot!.querySelectorAll("button")].find(
      (button) => button.textContent?.trim() === "Laboratory",
    );
    laboratory?.click();
    await element.updateComplete;
    element.shadowRoot?.querySelector("form")?.requestSubmit();
    await vi.waitFor(() =>
      expect(element.shadowRoot?.textContent).toContain("Try again shortly."),
    );
    expect(element.shadowRoot?.textContent).toContain("embedded-test");
    expect(element.shadowRoot?.textContent).toContain("2025-01");
  });
});

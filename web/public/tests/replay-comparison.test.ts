import { describe, expect, it } from "vitest";

import type { ReplayBundleV1 } from "../../replay/replay-v1-contract.d.ts";
import {
  cohortDifferences,
  pairedSeries,
  representativeComparison,
} from "../src/replay-comparison.js";

const bundle = {
  aggregate_series: [
    {
      regime: "nominal",
      name: "consumption",
      unit: "ISK",
      points: [
        { month: "2025-01", value: 100 },
        { month: "2025-02", value: null },
      ],
    },
    {
      regime: "indexed",
      name: "consumption",
      unit: "ISK",
      points: [
        { month: "2025-01", value: 90 },
        { month: "2025-02", value: 95 },
      ],
    },
  ],
  distribution_series: [
    {
      regime: "nominal",
      month: "2025-01",
      dimension: "income_quintile",
      cohort: "q1",
      consumption_isk: 80,
    },
    {
      regime: "indexed",
      month: "2025-01",
      dimension: "income_quintile",
      cohort: "q1",
      consumption_isk: 72,
    },
  ],
  representative_agents: [
    {
      regime: "nominal",
      household_id: "household-a",
      matched_household_id: "household-a",
      cohort: "borrower",
    },
    {
      regime: "indexed",
      household_id: "household-a",
      matched_household_id: "household-a",
      cohort: "borrower",
    },
    {
      regime: "nominal",
      household_id: "household-b",
      matched_household_id: "missing-household",
      cohort: "renter",
    },
    {
      regime: "indexed",
      household_id: "household-c",
      matched_household_id: "other-household",
      cohort: "renter",
    },
  ],
} as ReplayBundleV1;

describe("paired replay presentation", () => {
  it("derives labeled indexed-minus-nominal series without filling missing data", () => {
    expect(pairedSeries(bundle, "consumption")).toEqual({
      name: "consumption",
      unit: "ISK",
      points: [
        { month: "2025-01", nominal: 100, indexed: 90, difference: -10 },
        {
          month: "2025-02",
          nominal: null,
          indexed: 95,
          difference: null,
        },
      ],
    });
  });

  it("compares like-for-like declared cohorts against the nominal baseline", () => {
    expect(
      cohortDifferences(
        bundle,
        "2025-01",
        "income_quintile",
        "consumption_isk",
      ),
    ).toEqual([{ cohort: "q1", nominal: 80, indexed: 72, difference: -8 }]);
  });

  it("uses individuals only for reciprocal identities and otherwise falls back to cohorts", () => {
    expect(
      representativeComparison(bundle, "nominal", "household-a")?.kind,
    ).toBe("individual");
    expect(
      representativeComparison(bundle, "nominal", "household-b"),
    ).toMatchObject({
      kind: "cohort",
      cohort: "renter",
      nominalId: "household-b",
      indexedId: "household-c",
    });
  });
});

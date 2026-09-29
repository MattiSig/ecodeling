import assert from "node:assert/strict";
import test from "node:test";

import { formatISK, renderEvent, validateReplay, viewAt } from "../app.mjs";

const bundle = {
  manifest: { schema_version: 0 },
  timeline: [{ index: 0, month: "2025-01" }],
  snapshots: [
    { month: "2025-01", sector: "households", mortgage_principal: 90, net_worth: 10 },
    { month: "2025-01", sector: "banks", mortgage_principal: 90, equity: 5 },
  ],
  events: [
    {
      id: "event-1",
      event_type: "CPI_REVALUATION",
      ledger_entry_id: "entry-1",
      ledger_sides: [
        { role: "borrower_liability", amount: 2, account_id: "borrower:mortgage" },
        { role: "lender_asset", amount: 2, account_id: "bank:mortgage" },
      ],
    },
  ],
  representative_agents: [
    {
      household_id: "household-1",
      track: [{ month: "2025-01", mortgage_principal: 90, revaluation_event_id: "event-1" }],
    },
  ],
};

test("validates schema v0 and rejects incompatible bundles", () => {
  assert.equal(validateReplay(bundle), bundle);
  assert.throws(() => validateReplay({ manifest: { schema_version: 1 } }), /version 0/);
});

test("joins aligned stock, agent, and source event tables", () => {
  const view = viewAt(bundle, 0, "household-1");
  assert.equal(view.month, "2025-01");
  assert.equal(view.household.mortgage_principal, 90);
  assert.equal(view.bank.mortgage_principal, 90);
  assert.equal(view.event.ledger_entry_id, "entry-1");
});

test("renders exact money and both revaluation claim sides", () => {
  assert.match(formatISK(1234567), /1[,.]234[,.]567 ISK/);
  const html = renderEvent(bundle.events[0]);
  assert.match(html, /borrower liability/);
  assert.match(html, /lender asset/);
  assert.match(html, /entry-1/);
});

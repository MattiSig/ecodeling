import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { gunzipSync } from "node:zlib";

import type { ReplayBundleV1 } from "../replay-v1-contract.d.ts";
import { validateReplayV1 } from "../replay-v1-contract.mjs";

const compressed = readFileSync(new URL("../canonical-v1.json.gz", import.meta.url));
const canonical = gunzipSync(compressed);
const bundle = JSON.parse(canonical.toString("utf8")) as ReplayBundleV1;
const schema = JSON.parse(
  readFileSync(new URL("../replay-v1.schema.json", import.meta.url), "utf8"),
) as { title: string; required: string[] };

test("TypeScript contract accepts the canonical Python replay", () => {
  assert.equal(validateReplayV1(bundle, canonical.byteLength), bundle);
  assert.deepEqual(bundle.runs.map((run) => run.regime), ["nominal", "indexed"]);
  assert.ok(bundle.sector_flows.some((flow) => flow.flow_type === "imports"));
  assert.ok(bundle.events.some((event) => event.event_type === "FX_SHOCK"));
  assert.equal(schema.title, "ReplayBundleV1");
  assert.deepEqual(schema.required.sort(), Object.keys(bundle).sort());
});

test("contract rejects incompatible, oversized, and drifting bundles", () => {
  assert.throws(
    () => validateReplayV1({ manifest: { schema_version: 0 } }),
    /cannot be losslessly migrated/,
  );
  assert.throws(
    () =>
      validateReplayV1(
        { ...bundle, manifest: { ...bundle.manifest, maximum_uncompressed_bytes: 1 } },
        canonical.byteLength,
      ),
    /payload-size limit/,
  );
  assert.throws(
    () => validateReplayV1({ ...bundle, timeline: bundle.timeline.slice(1) }),
    /not aligned/,
  );
});

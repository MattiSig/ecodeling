import { describe, expect, it, vi } from "vitest";

import { ReplayState } from "../src/replay-state.js";

describe("ReplayState", () => {
  it("selects an initial month and clamps timeline movement", () => {
    const state = new ReplayState();
    state.configure(["2025-01", "2025-02", "2025-03"], "2025-02");
    expect(state.month).toBe("2025-02");
    state.setMonthIndex(99);
    expect(state.month).toBe("2025-03");
    state.setMonthIndex(-10);
    expect(state.month).toBe("2025-01");
  });

  it("announces meaningful selection changes once", () => {
    const state = new ReplayState();
    const listener = vi.fn();
    state.addEventListener("change", listener);
    state.select({ kind: "run", id: "nominal" });
    state.select({ kind: "run", id: "nominal" });
    expect(listener).toHaveBeenCalledTimes(1);
  });
});

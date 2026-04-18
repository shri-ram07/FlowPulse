import { describe, expect, it } from "vitest";
import { edgeFlow, KIND_ICON, pressureScale, scoreBand, scoreColor } from "./scoring";
import type { ZoneState } from "./types";

describe("scoreBand", () => {
  it("returns good for 80+", () => {
    expect(scoreBand(100)).toBe("good");
    expect(scoreBand(80)).toBe("good");
  });
  it("returns ok for 50-79", () => {
    expect(scoreBand(79)).toBe("ok");
    expect(scoreBand(50)).toBe("ok");
  });
  it("returns bad for <50", () => {
    expect(scoreBand(49)).toBe("bad");
    expect(scoreBand(0)).toBe("bad");
  });
});

describe("scoreColor", () => {
  it("assigns the right ink colour per band", () => {
    expect(scoreColor(90).ink).toBe("#065f46");
    expect(scoreColor(60).ink).toBe("#78350f");
    expect(scoreColor(20).ink).toBe("#7f1d1d");
  });
});

describe("KIND_ICON", () => {
  it("covers every zone kind", () => {
    for (const kind of [
      "gate",
      "seating",
      "food",
      "restroom",
      "concourse",
      "exit",
      "merch",
    ] as const) {
      expect(KIND_ICON[kind]).toBeTruthy();
    }
  });
});

describe("pressureScale", () => {
  it("is 0.85 when empty", () => {
    expect(pressureScale({ occupancy: 0, capacity: 100 })).toBeCloseTo(0.85);
  });
  it("grows with occupancy but is clamped", () => {
    const full = pressureScale({ occupancy: 100, capacity: 100 });
    const over = pressureScale({ occupancy: 500, capacity: 100 });
    expect(full).toBeCloseTo(1.1);
    // 1.25 cap → 0.85 + 0.25*1.25 = 1.1625
    expect(over).toBeLessThanOrEqual(1.1625 + 1e-9);
  });
  it("handles zero capacity without dividing by zero", () => {
    expect(() => pressureScale({ occupancy: 10, capacity: 0 })).not.toThrow();
  });
});

describe("edgeFlow", () => {
  const mk = (p: Partial<ZoneState>): ZoneState => ({
    id: "x",
    name: "X",
    kind: "food",
    capacity: 100,
    occupancy: 0,
    density: 0,
    inflow_per_min: 0,
    outflow_per_min: 0,
    wait_minutes: 0,
    trend: "steady",
    score: 100,
    level: "calm",
    x: 0,
    y: 0,
    ...p,
  });
  it("returns zero when either zone is missing", () => {
    expect(edgeFlow(undefined, mk({}))).toBe(0);
    expect(edgeFlow(mk({}), undefined)).toBe(0);
  });
  it("averages in/out flow of both zones", () => {
    const a = mk({ outflow_per_min: 10, inflow_per_min: 2 });
    const b = mk({ outflow_per_min: 4, inflow_per_min: 8 });
    // (10 + 8 + 2 + 4) / 4 = 6
    expect(edgeFlow(a, b)).toBe(6);
  });
});

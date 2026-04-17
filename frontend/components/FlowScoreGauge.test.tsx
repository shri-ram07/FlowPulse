// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import FlowScoreGauge from "./FlowScoreGauge";
import type { ZoneState } from "@/lib/types";

const mkZone = (score: number, level: ZoneState["level"] = "calm"): ZoneState => ({
  id: `z${score}`, name: "Z", kind: "food",
  capacity: 100, occupancy: 0, density: 0,
  inflow_per_min: 0, outflow_per_min: 0,
  wait_minutes: 0, trend: "steady", score, level, x: 0, y: 0,
});

describe("FlowScoreGauge", () => {
  it("matches snapshot for a healthy venue", () => {
    const zones = [mkZone(90), mkZone(85), mkZone(88)];
    const html = renderToString(<FlowScoreGauge zones={zones} />);
    expect(html).toMatchSnapshot();
  });

  it("counts critical and congested zones", () => {
    const zones = [
      mkZone(20, "critical"),
      mkZone(30, "critical"),
      mkZone(55, "congested"),
      mkZone(95, "calm"),
    ];
    const html = renderToString(<FlowScoreGauge zones={zones} />);
    // Avg = 50; 2 critical; 1 congested.
    expect(html).toMatch(/>2<\/div>/);   // the critical counter
    expect(html).toMatch(/>1<\/div>/);   // the congested counter
  });

  it("handles an empty zone list without NaN", () => {
    const html = renderToString(<FlowScoreGauge zones={[]} />);
    expect(html).toContain(">0<");
    expect(html).not.toContain("NaN");
  });
});

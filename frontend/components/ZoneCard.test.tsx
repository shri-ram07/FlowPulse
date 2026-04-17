// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import ZoneCard from "./ZoneCard";
import type { ZoneState } from "@/lib/types";

const base: ZoneState = {
  id: "food_1", name: "Food Court 1", kind: "food",
  capacity: 180, occupancy: 100,
  density: 0.55, inflow_per_min: 8.2, outflow_per_min: 4.1,
  wait_minutes: 6.3, trend: "rising",
  score: 72, level: "building",
  x: 340, y: 155,
};

describe("ZoneCard", () => {
  it("matches the snapshot for a watch-band zone", () => {
    const html = renderToString(<ZoneCard z={base} />);
    expect(html).toMatchSnapshot();
  });

  it("renders the score pill with `good` class when score >= 80", () => {
    const html = renderToString(<ZoneCard z={{ ...base, score: 95, level: "calm" }} />);
    expect(html).toContain("score-pill good");
  });

  it("renders `bad` class and red progress when score < 50", () => {
    const html = renderToString(<ZoneCard z={{ ...base, score: 30, level: "critical" }} />);
    expect(html).toContain("score-pill bad");
  });
});

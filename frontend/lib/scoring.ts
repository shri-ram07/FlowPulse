import type { ZoneKind, ZoneState } from "./types";

/** Flow-Score colour band. Same breakpoints as the backend scoring.py. */
export function scoreBand(score: number): "good" | "ok" | "bad" {
  if (score >= 80) return "good";
  if (score >= 50) return "ok";
  return "bad";
}

export function scoreColor(score: number): { fill: string; soft: string; ink: string } {
  switch (scoreBand(score)) {
    case "good":
      return { fill: "#16a34a", soft: "#dcfce7", ink: "#065f46" };
    case "ok":
      return { fill: "#d97706", soft: "#fef3c7", ink: "#78350f" };
    default:
      return { fill: "#dc2626", soft: "#fee2e2", ink: "#7f1d1d" };
  }
}

export const KIND_ICON: Record<ZoneKind, string> = {
  gate: "\u{1F6AA}",
  seating: "\u{1FA91}",
  food: "\u{1F354}",
  restroom: "\u{1F6BB}",
  concourse: "\u{1F6B6}",
  exit: "\u{1F6AA}",
  merch: "\u{1F3DF}",
};

/**
 * Scale factor applied to a zone badge's dimensions based on occupancy
 * pressure. Clamped so the badge never grows or shrinks by more than ~30%.
 */
export function pressureScale(z: Pick<ZoneState, "occupancy" | "capacity">): number {
  const ratio = Math.min(1.25, z.occupancy / Math.max(z.capacity, 1));
  return 0.85 + 0.25 * ratio;
}

/** Combined flow magnitude for an edge (used to drive particle density/speed). */
export function edgeFlow(a?: ZoneState, b?: ZoneState): number {
  if (!a || !b) return 0;
  return (a.outflow_per_min + b.inflow_per_min + a.inflow_per_min + b.outflow_per_min) / 4;
}

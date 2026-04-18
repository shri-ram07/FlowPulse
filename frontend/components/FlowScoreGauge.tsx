import type { ZoneState } from "@/lib/types";

function band(avg: number) {
  if (avg >= 80) return "good";
  if (avg >= 50) return "ok";
  return "bad";
}

export default function FlowScoreGauge({ zones }: { zones: ZoneState[] }) {
  const avg = zones.length ? Math.round(zones.reduce((a, z) => a + z.score, 0) / zones.length) : 0;
  const critical = zones.filter((z) => z.level === "critical").length;
  const congested = zones.filter((z) => z.level === "congested").length;
  const avgBand = band(avg);

  return (
    <div className="panel" style={{ padding: 14 }}>
      <h2>Stadium Pulse</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        <div>
          <div className="gauge-num">
            <span className={`score-pill ${avgBand}`} style={{ fontSize: 22, padding: "4px 14px" }}>
              {avg}
            </span>
          </div>
          <div className="gauge-sub">Average Flow Score</div>
        </div>
        <div>
          <div className="gauge-num" style={{ color: critical ? "var(--bad)" : "var(--muted)" }}>
            {critical}
          </div>
          <div className="gauge-sub">Critical zones</div>
        </div>
        <div>
          <div className="gauge-num" style={{ color: congested ? "var(--ok)" : "var(--muted)" }}>
            {congested}
          </div>
          <div className="gauge-sub">Congested</div>
        </div>
      </div>
      <div className="meta" style={{ marginTop: 8 }}>
        Higher is healthier. Any red cluster on the map is where attention is needed.
      </div>
    </div>
  );
}

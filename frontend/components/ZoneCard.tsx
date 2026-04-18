import type { ZoneState } from "@/lib/types";

function bandClass(score: number) {
  if (score >= 80) return "good";
  if (score >= 50) return "ok";
  return "bad";
}

const KIND_LABEL: Record<string, string> = {
  gate: "Gate",
  seating: "Seating",
  food: "Food court",
  restroom: "Restroom",
  concourse: "Concourse",
  exit: "Exit",
  merch: "Merch stand",
};

export default function ZoneCard({ z }: { z: ZoneState }) {
  const cls = bandClass(z.score);
  const pct = Math.round(z.density * 100);
  return (
    <div className="card">
      <div
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}
      >
        <div>
          <h3>{z.name}</h3>
          <div className="meta">
            {KIND_LABEL[z.kind] ?? z.kind} · {z.level}
          </div>
        </div>
        <span className={`score-pill ${cls}`}>{z.score}/100</span>
      </div>
      <div
        style={{
          marginTop: 8,
          height: 6,
          background: "var(--panel-soft)",
          borderRadius: 999,
          overflow: "hidden",
          border: "1px solid var(--border)",
        }}
        aria-label={`Occupancy ${pct}%`}
      >
        <div
          style={{
            width: `${Math.min(100, pct)}%`,
            height: "100%",
            background: cls === "good" ? "#16a34a" : cls === "ok" ? "#d97706" : "#dc2626",
          }}
        />
      </div>
      <div className="meta-row">
        <span>
          <b>{z.occupancy}</b>/{z.capacity} people
        </span>
        <span>
          <b>{z.wait_minutes}</b> min wait
        </span>
        <span>
          trend <b>{z.trend}</b>
        </span>
      </div>
      <div className="meta-row">
        <span>
          in <b>{z.inflow_per_min}</b>/min
        </span>
        <span>
          out <b>{z.outflow_per_min}</b>/min
        </span>
        <span>
          density <b>{pct}%</b>
        </span>
      </div>
    </div>
  );
}

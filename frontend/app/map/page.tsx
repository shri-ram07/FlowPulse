"use client";
import { useMemo, useState } from "react";
import StadiumMap from "@/components/StadiumMap";
import ZoneCard from "@/components/ZoneCard";
import FlowScoreGauge from "@/components/FlowScoreGauge";
import { useFlowPulse } from "@/lib/ws";

export default function MapPage() {
  const { tick, connected } = useFlowPulse();
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const zones = tick?.zones ?? [];
  const selected = useMemo(() => zones.find((z) => z.id === selectedId), [zones, selectedId]);
  const worst = useMemo(
    () => [...zones].sort((a, b) => a.score - b.score).slice(0, 5),
    [zones],
  );

  const latestAlert = tick?.alerts?.[0];
  const hotspots = useMemo(
    () => zones.filter(z => z.level === "critical" || z.level === "congested")
              .sort((a, b) => a.score - b.score).slice(0, 6),
    [zones],
  );

  return (
    <main className="layout">
      <section className="panel">
        <div className="panel-head">
          <h2>Live Stadium Map</h2>
          <span className="status-chip" aria-live="polite">
            <span className={`status-dot ${connected ? "on" : ""}`} aria-hidden />
            {connected ? "Streaming live" : "Reconnecting…"}
          </span>
        </div>

        {latestAlert && (
          <div className="alert-banner" role="alert">
            <span aria-hidden>⚠</span>
            <span><b>Alert:</b> {latestAlert.message}</span>
          </div>
        )}

        <div className="map-wrap">
          {zones.length === 0 ? (
            <div style={{ color: "var(--muted)" }}>Waiting for first tick…</div>
          ) : (
            <StadiumMap zones={zones} selectedId={selectedId} onSelect={setSelectedId} />
          )}
        </div>

        {hotspots.length > 0 && (
          <div className="hot-ticker" aria-label="Hotspots">
            {hotspots.map(z => (
              <button key={z.id}
                      className={`hot ${z.level}`}
                      onClick={() => setSelectedId(z.id)}
                      title={`Click to inspect ${z.name}`}>
                {z.name} · {z.score}/100 · {z.wait_minutes}m wait
              </button>
            ))}
          </div>
        )}

        <div className="legend" aria-hidden>
          <span className="tag"><span className="dot" style={{background:"#16a34a"}}/> 80–100 Healthy</span>
          <span className="tag"><span className="dot" style={{background:"#d97706"}}/> 50–79 Watch</span>
          <span className="tag"><span className="dot" style={{background:"#dc2626"}}/> 0–49 Action</span>
          <span className="tag">Size = occupancy</span>
          <span className="tag">Pulsing outline = critical</span>
        </div>
      </section>

      <aside style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
        <FlowScoreGauge zones={zones} />
        <div className="panel" style={{ flex: 1, overflowY: "auto" }}>
          <div className="panel-head">
            <h2>{selected ? "Selected Zone" : "Top Hotspots"}</h2>
            {selected && (
              <button className="btn ghost small" onClick={() => setSelectedId(undefined)}>Clear</button>
            )}
          </div>
          {selected ? <ZoneCard z={selected} /> :
            worst.length > 0 ? worst.map((z) => <ZoneCard key={z.id} z={z} />) :
            <div className="info-banner">All zones are healthy right now 🎉</div>}
        </div>
      </aside>
    </main>
  );
}

"use client";
import { useState } from "react";
import StadiumMap from "@/components/StadiumMap";
import ChatPanel from "@/components/ChatPanel";
import { useFlowPulse } from "@/lib/ws";

export default function ChatPage() {
  const { tick } = useFlowPulse();
  const [location, setLocation] = useState<string | undefined>();
  const zones = tick?.zones ?? [];
  const locName = zones.find((z) => z.id === location)?.name;

  return (
    <main className="layout">
      <section className="panel">
        <div className="panel-head">
          <h2>Pick your location</h2>
          <span className="status-chip" aria-live="polite">
            {locName ? (
              <>📍 You are at <b>&nbsp;{locName}</b></>
            ) : (
              "Tap a zone →"
            )}
          </span>
        </div>

        {!location ? (
          <div className="info-banner" style={{ marginBottom: 10 }}>
            <span aria-hidden>💡</span>
            <span>
              Click any zone on the map so the concierge can give you a walking route.
              Without a location it can still answer general questions like "which food court is calmest?".
            </span>
          </div>
        ) : (
          <div className="info-banner" style={{ marginBottom: 10 }}>
            <span aria-hidden>✅</span>
            <span>
              Location set to <b>{locName}</b>. Every recommendation now includes a walking time
              via the <code>get_best_route</code> tool.{" "}
              <button
                className="btn ghost small"
                style={{ marginLeft: 8 }}
                onClick={() => setLocation(undefined)}
              >
                Clear
              </button>
            </span>
          </div>
        )}

        <div className="map-wrap">
          {zones.length > 0 ? (
            <StadiumMap
              zones={zones}
              selectedId={location}
              onSelect={setLocation}
              youAreHereId={location}
            />
          ) : (
            <div style={{ color: "var(--muted)" }}>Waiting for first tick…</div>
          )}
        </div>
      </section>
      <ChatPanel location={location} />
    </main>
  );
}

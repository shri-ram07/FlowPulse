"use client";
import { useEffect, useRef, useState } from "react";
import type { TickPayload, ZoneState, AlertMsg } from "./types";

/**
 * Subscribe to the FlowPulse WebSocket.
 *
 * Server sends a `full=true` tick on connect, then `full=false` diffs
 * containing only zones whose score/occupancy/level/wait changed. We merge
 * diffs by id so the rendered state is always complete.
 */
export function useFlowPulse(): { tick: TickPayload | null; connected: boolean } {
  const [tick, setTick] = useState<TickPayload | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let backoff = 500;
    // Persist the full zone map across diffs without re-rendering on every merge.
    let zones: Record<string, ZoneState> = {};
    let alerts: AlertMsg[] = [];

    const connect = () => {
      if (cancelled) return;
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const url =
        process.env.NEXT_PUBLIC_WS_URL || `${proto}://${window.location.host}/ws`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => { setConnected(true); backoff = 500; };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as TickPayload;
          if (msg.type !== "tick") return;
          if (msg.full) zones = {};
          for (const z of msg.zones) zones[z.id] = z;
          // Keep recent alerts first; drop anything older than 5 min.
          const cutoff = Date.now() / 1000 - 300;
          alerts = [...msg.alerts, ...alerts].filter(a => a.ts >= cutoff).slice(0, 20);
          setTick({ type: "tick", ts: msg.ts, full: msg.full, zones: Object.values(zones), alerts });
        } catch { /* ignore malformed frame */ }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 5000);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return { tick, connected };
}

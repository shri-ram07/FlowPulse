"use client";
import { useEffect, useState } from "react";
import { fetchGraph } from "@/lib/api";
import { KIND_ICON, edgeFlow, pressureScale, scoreColor } from "@/lib/scoring";
import type { Graph, ZoneKind, ZoneState } from "@/lib/types";

/**
 * Stadium map with concentric ring layout.
 *  - Outer wall, seating bowl rings, pitch with centre circle.
 *  - Connecting PATHS drawn between neighbour zones.
 *  - FLOW PARTICLES — small circles animated along paths where the pair of
 *    zones is actively exchanging people (size/speed ∝ flow rate).
 *  - Every zone is a compact rounded badge: icon + name + Flow Score.
 */

const KIND_SIZE: Record<ZoneKind, { w: number; h: number }> = {
  seating:   { w: 92, h: 32 },
  concourse: { w: 90, h: 34 },
  gate:      { w: 62, h: 30 },
  exit:      { w: 80, h: 30 },
  food:      { w: 70, h: 38 },
  restroom:  { w: 52, h: 34 },
  merch:     { w: 60, h: 34 },
};

export default function StadiumMap({
  zones,
  selectedId,
  onSelect,
  youAreHereId,
}: {
  zones: ZoneState[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  /** When set, renders a distinct "you are here" pin on that zone. */
  youAreHereId?: string;
}) {
  const [graph, setGraph] = useState<Graph | null>(null);

  useEffect(() => {
    fetchGraph().then(setGraph).catch(() => { /* fail silently */ });
  }, []);

  const byId: Record<string, ZoneState> = Object.fromEntries(zones.map(z => [z.id, z]));
  const nodePos = graph
    ? Object.fromEntries(graph.nodes.map(n => [n.id, { x: n.x, y: n.y }]))
    : Object.fromEntries(zones.map(z => [z.id, { x: z.x, y: z.y }]));

  return (
    <svg viewBox="0 0 1000 1000" role="img"
         aria-label="Live stadium map. Zones are coloured by Flow Score: green (80+) healthy, amber (50–79) watch, red (<50) action. Thin dashed lines show pedestrian paths between zones; animated dots represent people flowing along those paths.">
      <defs>
        <radialGradient id="bowl" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor="#eef2f7" />
          <stop offset="70%" stopColor="#d7e0ea" />
          <stop offset="100%" stopColor="#b8c3d1" />
        </radialGradient>
        <linearGradient id="pitch" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%"  stopColor="#16a34a" />
          <stop offset="50%" stopColor="#15803d" />
          <stop offset="100%" stopColor="#166534" />
        </linearGradient>
        <pattern id="stripes" x="0" y="0" width="48" height="48" patternUnits="userSpaceOnUse">
          <rect width="48" height="48" fill="url(#pitch)" />
          <rect x="0"  width="24" height="48" fill="rgba(255,255,255,.04)" />
        </pattern>
        <filter id="drop" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodColor="#0f172a" floodOpacity="0.18" />
        </filter>
      </defs>

      {/* ---- Stadium shell ---- */}
      <ellipse cx={500} cy={500} rx={470} ry={470} fill="#94a3b8" />
      <ellipse cx={500} cy={500} rx={455} ry={455} fill="url(#bowl)" stroke="#94a3b8" strokeWidth={1.5} />
      <ellipse cx={500} cy={500} rx={380} ry={350} fill="none" stroke="#cbd5e1" strokeWidth={1} strokeDasharray="2 5" />
      <ellipse cx={500} cy={500} rx={300} ry={260} fill="none" stroke="#cbd5e1" strokeWidth={1} strokeDasharray="2 5" />

      {/* ---- Pitch ---- */}
      <g transform="translate(280, 360)">
        <rect width={440} height={280} rx={6} fill="url(#stripes)" stroke="#fff" strokeWidth={3} />
        <line x1={220} y1={0} x2={220} y2={280} stroke="#fff" strokeWidth={2} />
        <circle cx={220} cy={140} r={34} fill="none" stroke="#fff" strokeWidth={2} />
        <circle cx={220} cy={140} r={3}  fill="#fff" />
        <rect x={0}   y={70}  width={60}  height={140} fill="none" stroke="#fff" strokeWidth={2} />
        <rect x={380} y={70}  width={60}  height={140} fill="none" stroke="#fff" strokeWidth={2} />
        <text x={220} y={156} textAnchor="middle" fill="rgba(255,255,255,.65)" fontSize={20} fontWeight={700} letterSpacing=".2em">PITCH</text>
      </g>

      {/* ---- Compass labels ---- */}
      <text x={500} y={60}  textAnchor="middle" fill="#475569" fontSize={13} fontWeight={600} letterSpacing=".3em">N</text>
      <text x={500} y={955} textAnchor="middle" fill="#475569" fontSize={13} fontWeight={600} letterSpacing=".3em">S</text>
      <text x={45}  y={506} textAnchor="middle" fill="#475569" fontSize={13} fontWeight={600} letterSpacing=".3em">W</text>
      <text x={960} y={506} textAnchor="middle" fill="#475569" fontSize={13} fontWeight={600} letterSpacing=".3em">E</text>

      {/* ---- Edges (paths) ---- */}
      {graph?.edges.map((e, i) => {
        const a = nodePos[e.from]; const b = nodePos[e.to];
        if (!a || !b) return null;
        return (
          <line key={`edge-${i}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke="#94a3b8" strokeOpacity={0.35} strokeWidth={1.2}
                strokeDasharray="3 4" />
        );
      })}

      {/* ---- Flow particles ---- */}
      {graph?.edges.map((e, i) => {
        const za = byId[e.from]; const zb = byId[e.to];
        const a = nodePos[e.from]; const b = nodePos[e.to];
        if (!a || !b) return null;
        const flow = edgeFlow(za, zb);
        if (flow < 1.5) return null;
        // Intensity buckets: 1..3 particles, faster = more flow.
        const particles = Math.min(3, Math.max(1, Math.round(flow / 15)));
        const dur = Math.max(1.8, 10 - flow / 8);
        const dir = (za?.outflow_per_min ?? 0) >= (zb?.outflow_per_min ?? 0)
          ? { fx: a.x, fy: a.y, tx: b.x, ty: b.y }
          : { fx: b.x, fy: b.y, tx: a.x, ty: a.y };
        const colour = flow > 40 ? "#dc2626" : flow > 20 ? "#d97706" : "#0284c7";
        return Array.from({ length: particles }).map((_, j) => (
          <circle key={`flow-${i}-${j}`} r={3.2} fill={colour} opacity={0.85}>
            <animate attributeName="cx"
                     values={`${dir.fx};${dir.tx}`}
                     dur={`${dur}s`} begin={`${(j / particles) * dur}s`}
                     repeatCount="indefinite"/>
            <animate attributeName="cy"
                     values={`${dir.fy};${dir.ty}`}
                     dur={`${dur}s`} begin={`${(j / particles) * dur}s`}
                     repeatCount="indefinite"/>
            <animate attributeName="opacity"
                     values="0;0.85;0.85;0"
                     dur={`${dur}s`} begin={`${(j / particles) * dur}s`}
                     repeatCount="indefinite"/>
          </circle>
        ));
      })}

      {/* ---- "You are here" pin ---- */}
      {youAreHereId && (() => {
        const p = nodePos[youAreHereId];
        if (!p) return null;
        return (
          <g aria-label="Your current location" style={{ pointerEvents: "none" }}>
            <circle cx={p.x} cy={p.y - 40} r={10} fill="#0284c7" stroke="#fff" strokeWidth={2}>
              <animate attributeName="r" values="10;13;10" dur="1.8s" repeatCount="indefinite" />
            </circle>
            <text x={p.x} y={p.y - 36} textAnchor="middle" fill="#fff" fontSize={11} fontWeight={700}>
              YOU
            </text>
            <polygon points={`${p.x - 4},${p.y - 30} ${p.x + 4},${p.y - 30} ${p.x},${p.y - 22}`} fill="#0284c7"/>
          </g>
        );
      })()}

      {/* ---- Zones ---- */}
      {zones.map((z) => {
        const size = KIND_SIZE[z.kind];
        const s = pressureScale(z);
        const w = size.w * s;
        const h = size.h * s;
        const col = scoreColor(z.score);
        const selected = selectedId === z.id;
        const x = z.x - w / 2;
        const y = z.y - h / 2;
        const pulse = z.level === "critical";
        const isExit = z.kind === "exit";
        const icon = KIND_ICON[z.kind] ?? "\u25CF";

        return (
          <g key={z.id} className="zone" tabIndex={0} role="button"
             aria-label={`${z.name}. Flow Score ${z.score} out of 100. ${z.level}. ${z.occupancy} of ${z.capacity} people. ${z.wait_minutes} minute wait.`}
             onClick={() => onSelect?.(z.id)}
             onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect?.(z.id); } }}>
            {pulse && (
              <rect x={x - 4} y={y - 4} width={w + 8} height={h + 8} rx={10}
                    fill="none" stroke={col.fill} strokeWidth={2} opacity={0.6}>
                <animate attributeName="opacity" values="0.7;0.05;0.7" dur="1.6s" repeatCount="indefinite" />
              </rect>
            )}
            <rect className="zone-hit"
                  x={x} y={y} width={w} height={h} rx={8}
                  fill={col.soft} stroke={selected ? "#0284c7" : col.fill}
                  strokeWidth={selected ? 2.5 : 1.3}
                  strokeDasharray={isExit ? "5 3" : undefined}
                  filter="url(#drop)"/>
            <text x={z.x - w/2 + 10} y={y + h/2 + 4} fontSize={13} aria-hidden>
              {icon}
            </text>
            <text x={z.x + 8} y={y + h/2 - 2} textAnchor="middle" fill={col.ink} fontSize={9} fontWeight={600}>
              {z.name}
            </text>
            <text x={z.x + 8} y={y + h/2 + 9} textAnchor="middle" fill={col.ink} fontSize={10} fontWeight={800}>
              {z.score}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

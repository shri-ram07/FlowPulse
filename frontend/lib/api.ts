import type { AttendeeReply, Graph, OpsPlan, ZoneState } from "./types";

const BASE = "";

export async function listZones(kind?: string): Promise<ZoneState[]> {
  const q = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  const r = await fetch(`${BASE}/api/zones${q}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`listZones ${r.status}`);
  return r.json();
}

export async function fetchGraph(): Promise<Graph> {
  const r = await fetch(`${BASE}/api/zones/graph`, { cache: "force-cache" });
  if (!r.ok) throw new Error(`fetchGraph ${r.status}`);
  return r.json();
}

export async function askAttendee(
  message: string,
  location?: string,
  sessionId?: string,
): Promise<AttendeeReply> {
  const r = await fetch(`${BASE}/api/agent/attendee`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message, location, session_id: sessionId }),
  });
  if (!r.ok) throw new Error(`askAttendee ${r.status}`);
  return r.json();
}

export async function resetAttendeeSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/api/agent/attendee/reset`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function login(username: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username, password });
  const r = await fetch(`${BASE}/api/auth/login`, { method: "POST", body });
  if (!r.ok) throw new Error("login_failed");
  const j = await r.json();
  return j.access_token as string;
}

export async function opsPlan(token: string): Promise<OpsPlan> {
  const r = await fetch(`${BASE}/api/agent/operations`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`opsPlan ${r.status}`);
  return r.json();
}

export interface ApplyResult {
  ok: boolean;
  action_id: string;
  type: string;
  target: string;
  message: string;
  relief_pct?: number;
  to?: string;
  fcm?: { dry_run?: boolean; message_id?: string };
}

export async function applyOpsAction(
  token: string,
  action: {
    type: string;
    target: string;
    rationale?: string;
    title?: string;
    body?: string;
    severity?: string;
  },
): Promise<ApplyResult> {
  const r = await fetch(`${BASE}/api/ops/apply`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify(action),
  });
  if (!r.ok) throw new Error(`apply ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function setChaos(token: string, chaos: number): Promise<void> {
  await fetch(`${BASE}/api/sim/chaos`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ chaos }),
  });
}

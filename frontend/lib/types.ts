export type ZoneKind = "gate" | "seating" | "food" | "restroom" | "concourse" | "exit" | "merch";

export type CongestionLevel = "calm" | "building" | "congested" | "critical";

export interface ZoneState {
  id: string;
  name: string;
  kind: ZoneKind;
  capacity: number;
  occupancy: number;
  density: number;
  inflow_per_min: number;
  outflow_per_min: number;
  wait_minutes: number;
  trend: "rising" | "falling" | "steady";
  score: number;
  level: CongestionLevel;
  x: number;
  y: number;
}

export interface AlertMsg {
  id: string;
  zone_id: string;
  severity: "info" | "warn" | "critical";
  message: string;
  ts: number;
}

export interface TickPayload {
  type: "tick";
  ts: number;
  /** true for the initial full snapshot, false for per-tick diffs. */
  full: boolean;
  zones: ZoneState[];
  alerts: AlertMsg[];
}

export interface OpsPlan {
  engine: string;
  situation: string;
  root_cause: string;
  confidence: number;
  actions: Array<{
    type: "open_gate" | "push_notification" | "dispatch_staff" | "redirect" | "monitor";
    target: string;
    eta_minutes: number;
    rationale: string;
  }>;
  error?: string;
}

export interface AttendeeReply {
  reply: string;
  tool_calls: Array<{ name: string; args: Record<string, unknown>; result: unknown }>;
  engine: string;
}

export interface GraphNode {
  id: string;
  name: string;
  kind: ZoneKind;
  x: number;
  y: number;
}
export interface GraphEdge {
  from: string;
  to: string;
  walk_seconds: number;
}
export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

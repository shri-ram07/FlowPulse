"use client";
import { useState } from "react";
import { applyOpsAction, opsPlan, setChaos } from "@/lib/api";
import { useToast } from "@/components/Toast";
import type { OpsPlan } from "@/lib/types";

const ACTION_LABEL: Record<string, { icon: string; label: string }> = {
  open_gate: { icon: "🚪", label: "Open gate" },
  push_notification: { icon: "📣", label: "Push notification" },
  dispatch_staff: { icon: "👷", label: "Dispatch staff" },
  redirect: { icon: "↪", label: "Redirect crowd" },
  monitor: { icon: "👁", label: "Monitor" },
};

type ActionStatus = "pending" | "applying" | "applied" | "dismissed" | "failed";

export default function OpsActionFeed({ token }: { token: string | null }) {
  const [plan, setPlan] = useState<OpsPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [chaos, setChaosVal] = useState(0);
  const [statuses, setStatuses] = useState<Record<number, ActionStatus>>({});
  const [messages, setMessages] = useState<Record<number, string>>({});
  const toast = useToast();

  async function generate() {
    if (!token) {
      setErr("Log in first");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const p = await opsPlan(token);
      setPlan(p);
      setStatuses({});
      setMessages({});
      toast.push(
        "info",
        `Plan ready — ${p.actions.length} action${p.actions.length === 1 ? "" : "s"}`,
      );
    } catch (e) {
      setErr((e as Error).message);
      toast.push("error", "Could not fetch plan");
    } finally {
      setLoading(false);
    }
  }

  async function applyChaos(v: number) {
    setChaosVal(v);
    if (token) await setChaos(token, v);
  }

  async function onApply(i: number) {
    if (!token || !plan) return;
    const a = plan.actions[i];
    setStatuses((s) => ({ ...s, [i]: "applying" }));
    try {
      const res = await applyOpsAction(token, {
        type: a.type,
        target: a.target,
        rationale: a.rationale,
      });
      setStatuses((s) => ({ ...s, [i]: "applied" }));
      setMessages((m) => ({ ...m, [i]: res.message }));
      toast.push("success", res.message);
    } catch (e) {
      setStatuses((s) => ({ ...s, [i]: "failed" }));
      const msg = (e as Error).message;
      setMessages((m) => ({ ...m, [i]: msg }));
      toast.push("error", `Apply failed: ${msg}`);
    }
  }

  function onDismiss(i: number) {
    setStatuses((s) => ({ ...s, [i]: "dismissed" }));
    toast.push("info", "Action dismissed");
  }

  return (
    <div className="panel" style={{ flex: 1, minHeight: 0 }}>
      <div className="panel-head">
        <h2>Ops Agent</h2>
        <span className="status-chip">JSON action plan</span>
      </div>

      <div className="info-banner" style={{ marginBottom: 10 }}>
        <span aria-hidden>💡</span>
        <span>
          Drag <b>Chaos</b> to force congestion, then click <b>Propose Actions</b>. Apply any action
          to dispatch it live — the map reacts on the next tick.
        </span>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <button className="btn" onClick={generate} disabled={loading || !token}>
          {loading ? "Thinking…" : "Propose Actions"}
        </button>
      </div>

      <label>
        Chaos injection: <b>{Math.round(chaos * 100)}%</b>
        <input
          className="slider"
          type="range"
          min={0}
          max={100}
          value={chaos * 100}
          onChange={(e) => applyChaos(Number(e.target.value) / 100)}
          disabled={!token}
        />
      </label>

      {err && (
        <div className="alert-banner" role="alert">
          ⚠ {err}
        </div>
      )}

      {plan && (
        <div style={{ overflowY: "auto", marginTop: 10, paddingRight: 4 }}>
          <div className="card">
            <h3>Situation</h3>
            <div className="meta" style={{ marginTop: 4, color: "var(--text-2)" }}>
              {plan.situation}
            </div>
            <div className="meta">
              <b>Root cause:</b> {plan.root_cause}
            </div>
            <div className="meta">
              Confidence <b>{Math.round(plan.confidence * 100)}%</b> · engine:{" "}
              <span className="kbd">{plan.engine}</span>
            </div>
          </div>
          {plan.actions.map((a, i) => {
            const info = ACTION_LABEL[a.type] ?? { icon: "•", label: a.type };
            const status = statuses[i] ?? "pending";
            const cls =
              status === "applied"
                ? "card applied"
                : status === "dismissed"
                  ? "card dismissed"
                  : "card";
            return (
              <div key={i} className={cls}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                    gap: 8,
                  }}
                >
                  <h3>
                    <span aria-hidden>{info.icon}</span>&nbsp;{info.label} ·{" "}
                    <span style={{ color: "var(--muted)" }}>{a.target}</span>
                  </h3>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    {status === "applied" && <span className="applied-badge">Applied ✓</span>}
                    {status === "failed" && (
                      <span className="applied-badge" style={{ background: "#dc2626" }}>
                        Failed
                      </span>
                    )}
                    <span className="meta">ETA {a.eta_minutes}m</span>
                  </div>
                </div>
                <div className="meta" style={{ marginTop: 6, color: "var(--text-2)" }}>
                  {a.rationale}
                </div>
                {messages[i] && (
                  <div className="meta" style={{ marginTop: 6, fontStyle: "italic" }}>
                    → {messages[i]}
                  </div>
                )}
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  <button
                    className="btn small"
                    onClick={() => onApply(i)}
                    disabled={
                      status === "applying" || status === "applied" || status === "dismissed"
                    }
                  >
                    {status === "applying"
                      ? "Applying…"
                      : status === "applied"
                        ? "Applied"
                        : status === "failed"
                          ? "Retry"
                          : "Apply"}
                  </button>
                  <button
                    className="btn ghost small"
                    onClick={() => onDismiss(i)}
                    disabled={status === "applied" || status === "dismissed"}
                  >
                    {status === "dismissed" ? "Dismissed" : "Dismiss"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

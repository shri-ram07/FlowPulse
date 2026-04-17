"use client";
import { useRef, useState } from "react";
import { askAttendee, resetAttendeeSession } from "@/lib/api";
import { useToast } from "@/components/Toast";
import type { AttendeeReply } from "@/lib/types";

interface Msg { role: "user" | "bot"; text: string; tools?: AttendeeReply["tool_calls"]; engine?: string; }

const SEEDS = [
  "Where should I grab food?",
  "Nearest restroom?",
  "How busy is Gate B?",
  "What's the forecast in 5 minutes?",
];

/** Crypto-random session id generated once per tab. Kept in a ref so it
 *  survives re-renders but resets on page reload — perfect for the demo. */
function makeSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `att-${crypto.randomUUID()}`;
  }
  return `att-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

export default function ChatPanel({ location }: { location?: string }) {
  const sessionIdRef = useRef<string>(makeSessionId());
  const toast = useToast();

  const [log, setLog] = useState<Msg[]>([
    { role: "bot", text: location
        ? "Hi! I know where you are. Ask away — food, restrooms, routes, forecasts."
        : "Hi! I can answer general questions right now. Tap a zone on the map to get walking routes personalised to your spot." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setLog((l) => [...l, { role: "user", text }]);
    setInput("");
    try {
      const r = await askAttendee(text, location, sessionIdRef.current);
      setLog((l) => [...l, { role: "bot", text: r.reply, tools: r.tool_calls, engine: r.engine }]);
    } catch (e) {
      setLog((l) => [...l, { role: "bot", text: `Sorry — ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  }

  async function resetConversation() {
    try {
      await resetAttendeeSession(sessionIdRef.current);
    } catch { /* ignore network errors, we'll reset locally anyway */ }
    sessionIdRef.current = makeSessionId();
    setLog([{ role: "bot", text: location
        ? "Fresh conversation. Ask me anything."
        : "Fresh conversation. Tap a zone on the map if you want walking routes." }]);
    toast.push("info", "Conversation reset");
  }

  return (
    <div className="panel" style={{ flex: 1 }}>
      <div className="panel-head">
        <h2>Concierge</h2>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span className="status-chip" title="Every answer is grounded in a tool call shown as a chip">
            Grounded AI
          </span>
          <button className="btn ghost small" onClick={resetConversation}
                  title="Start a fresh conversation — the agent forgets previous turns">
            Reset
          </button>
        </div>
      </div>

      <div className="chat-log" role="log" aria-live="polite">
        {log.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div>{m.text}</div>
            {m.tools && m.tools.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {m.tools.map((t, j) => (
                  <span key={j} className="tool-chip" title={JSON.stringify(t.args)}>
                    {t.name}()
                  </span>
                ))}
                {m.engine && <span className="tool-chip" title="Reasoning engine">engine: {m.engine}</span>}
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "10px 0 4px" }}>
        {SEEDS.map((s) => (
          <button key={s} className="btn ghost small" onClick={() => send(s)} disabled={busy}>
            {s}
          </button>
        ))}
      </div>
      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <label htmlFor="chat-input" className="visually-hidden">Ask the concierge</label>
        <input id="chat-input" type="text" value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="Ask about food, restrooms, routes…" disabled={busy}
               autoComplete="off" aria-describedby="chat-help" />
        <button type="submit" className="btn" disabled={busy || !input.trim()}>
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}

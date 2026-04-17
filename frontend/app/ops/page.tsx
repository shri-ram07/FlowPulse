"use client";
import { useMemo, useState } from "react";
import StadiumMap from "@/components/StadiumMap";
import FlowScoreGauge from "@/components/FlowScoreGauge";
import OpsActionFeed from "@/components/OpsActionFeed";
import { login } from "@/lib/api";
import { useFlowPulse } from "@/lib/ws";

export default function OpsPage() {
  const { tick } = useFlowPulse();
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("ops");
  const [password, setPassword] = useState("ops-demo");
  const [err, setErr] = useState<string | null>(null);
  const zones = tick?.zones ?? [];
  const alerts = tick?.alerts ?? [];

  async function doLogin(e: React.FormEvent) {
    e.preventDefault();
    try { setToken(await login(username, password)); setErr(null); }
    catch { setErr("Invalid credentials"); }
  }

  const situation = useMemo(() => {
    const crit = zones.filter(z => z.level === "critical").length;
    const cong = zones.filter(z => z.level === "congested").length;
    return { crit, cong };
  }, [zones]);

  if (!token) {
    return (
      <main className="welcome" style={{ maxWidth: 440, paddingTop: 48 }}>
        <form className="panel" onSubmit={doLogin}>
          <h1 style={{ fontSize: 22, marginBottom: 4 }}>Staff sign in</h1>
          <p className="meta" style={{ marginBottom: 14 }}>
            Demo credentials: <span className="kbd">ops</span> / <span className="kbd">ops-demo</span>
          </p>
          {err && <div className="alert-banner">⚠ {err}</div>}
          <label htmlFor="u">Username</label>
          <input id="u" type="text" value={username} onChange={(e) => setUsername(e.target.value)} />
          <label htmlFor="p" style={{ marginTop: 10 }}>Password</label>
          <input id="p" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className="btn" type="submit" style={{ marginTop: 14, width: "100%" }}>Sign in</button>
        </form>
      </main>
    );
  }

  return (
    <main className="layout">
      <section className="panel">
        <div className="panel-head">
          <h2>Operations Console</h2>
          <span className="status-chip">
            {situation.crit} critical · {situation.cong} congested · {zones.length} zones
          </span>
        </div>

        {alerts.length > 0 && (
          <div className="alert-banner" role="alert">
            <span aria-hidden>⚠</span>
            <span><b>{alerts.length}</b> new alert(s) — latest: {alerts[0].message}</span>
          </div>
        )}

        <div className="map-wrap">
          {zones.length > 0 ? <StadiumMap zones={zones} /> :
            <div style={{ color: "var(--muted)" }}>Waiting for first tick…</div>}
        </div>
      </section>
      <aside style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
        <FlowScoreGauge zones={zones} />
        <OpsActionFeed token={token} />
      </aside>
    </main>
  );
}

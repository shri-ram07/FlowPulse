import Link from "next/link";

export default function WelcomePage() {
  return (
    <main className="welcome">
      <section className="hero">
        <div>
          <h1>Welcome to FlowPulse</h1>
          <p className="lede">
            FlowPulse is a live crowd-orchestration platform for stadiums. It treats the venue
            as a <b>flow system</b> — every gate, concourse, food court, restroom and exit is a
            zone with a live <b>Crowd Flow Score</b> from 0 to 100. Two AI agents (a fan concierge
            and an operations agent, built with Google ADK) turn that live state into
            recommendations for fans and actions for staff.
          </p>
          <div className="cta-row">
            <Link href="/map" className="btn">Open Live Map</Link>
            <Link href="/chat" className="btn secondary">Try the Concierge</Link>
            <Link href="/ops" className="btn ghost">Ops Console</Link>
          </div>
        </div>
        <div aria-hidden style={{ fontSize: 88, lineHeight: 1 }}>🏟️</div>
      </section>

      <section>
        <div className="step-grid">
          <div className="step">
            <div className="num">1</div>
            <h3>Watch the live map</h3>
            <p>
              Every zone is a coloured badge. Green = healthy, amber = watch, red = action needed.
              The number inside each badge is the <b>Crowd Flow Score</b> — a single number
              combining density, wait time, pressure and risk.
            </p>
            <div className="tip">Tip: click or tab onto a zone to pin it and see full details on the right.</div>
          </div>
          <div className="step">
            <div className="num">2</div>
            <h3>Ask the concierge</h3>
            <p>
              On the Concierge page, tap a zone to set <i>where you are</i>, then ask questions like
              <span className="kbd">"Where should I grab food?"</span> or
              <span className="kbd">"How busy is Gate B?"</span>. Every reply is grounded in a
              tool call, shown as a chip so you can see which data was used.
            </p>
            <div className="tip">The agent never invents numbers. It always queries the live engine first.</div>
          </div>
          <div className="step">
            <div className="num">3</div>
            <h3>Run the ops console</h3>
            <p>
              Sign in as staff (<span className="kbd">ops</span> / <span className="kbd">ops-demo</span>),
              drag the <b>Chaos</b> slider to force congestion, then hit <b>Propose Actions</b>. The
              Ops agent returns a JSON plan — situation, root cause, 1-4 concrete actions with
              rationales citing live numbers.
            </p>
            <div className="tip">Apply an action and watch the map react on the next tick. That's the closed loop.</div>
          </div>
        </div>
      </section>

      <section className="legend-section" aria-labelledby="legend-heading">
        <h2 id="legend-heading">Crowd Flow Score — how to read the map</h2>
        <div className="legend-grid">
          <div className="legend-item">
            <div className="swatch" style={{ background: "#16a34a" }}>80+</div>
            <div className="txt"><b>Healthy.</b> Plenty of headroom, short waits, flow is even. Safe to recommend.</div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#d97706" }}>50–79</div>
            <div className="txt"><b>Watch.</b> Density is climbing or waits are noticeable. Good candidate for nudges.</div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#dc2626" }}>0–49</div>
            <div className="txt"><b>Action.</b> Congested or overpressured. The Ops agent will usually propose a redirect or gate-opening here.</div>
          </div>
        </div>
      </section>

      <section className="legend-section" aria-labelledby="kinds-heading">
        <h2 id="kinds-heading">Zone types on the map</h2>
        <div className="legend-grid">
          <div className="legend-item"><div className="swatch" style={{ background: "#64748b" }}>🚪</div>
            <div className="txt"><b>Gate.</b> Entry points. Congestion here usually triggers "open an adjacent gate".</div></div>
          <div className="legend-item"><div className="swatch" style={{ background: "#64748b" }}>🚶</div>
            <div className="txt"><b>Concourse.</b> Circulation rings. High-throughput; spikes spill to food/restrooms.</div></div>
          <div className="legend-item"><div className="swatch" style={{ background: "#64748b" }}>🪑</div>
            <div className="txt"><b>Seating.</b> The bowl itself, split into N/S/E/W rings.</div></div>
          <div className="legend-item"><div className="swatch" style={{ background: "#64748b" }}>🍔</div>
            <div className="txt"><b>Food court.</b> Queues build at halftime. Concierge will route you to the greenest one.</div></div>
          <div className="legend-item"><div className="swatch" style={{ background: "#64748b" }}>🚻</div>
            <div className="txt"><b>Restroom.</b> Small capacity, spikes fast. Wait time is the key metric.</div></div>
          <div className="legend-item"><div className="swatch" style={{ background: "#64748b" }}>🏟</div>
            <div className="txt"><b>Merch.</b> Souvenir stands. Lower traffic, but pressure at match start/end.</div></div>
          <div className="legend-item"><div className="swatch" style={{ background: "#64748b" }}>🚪</div>
            <div className="txt"><b>Exit ramp.</b> Dashed border. High-risk during full-time surge.</div></div>
        </div>
      </section>

      <section className="legend-section" aria-labelledby="how-heading">
        <h2 id="how-heading">How FlowPulse actually reduces congestion & waiting time</h2>
        <p style={{ color: "var(--text-2)", margin: "0 0 14px", lineHeight: 1.6 }}>
          Giving a fan "the best route" is only step one. The system closes the loop — detecting
          pressure early, pushing demand to where there's headroom, and increasing service capacity
          when needed. Four levers run continuously:
        </p>
        <div className="legend-grid">
          <div className="legend-item">
            <div className="swatch" style={{ background: "#0284c7" }}>1</div>
            <div className="txt">
              <b>Personal routing (pull).</b> When a fan asks the Concierge,
              <span className="kbd">get_best_route</span> runs Dijkstra on the zone graph
              with edges weighted by walk-seconds <i>× density penalty</i>. A red zone's
              weight jumps 2.5×, so the path automatically skirts it. The fan walks a bit
              longer — but waits far less.
            </div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#0284c7" }}>2</div>
            <div className="txt">
              <b>Broadcast redirect (push).</b> The Ops Agent spots a hot zone, calls
              <span className="kbd">suggest_redirect(from, to)</span> to confirm the alternative
              has headroom, and fires <span className="kbd">dispatch_alert</span> to push fans
              from the hotspot toward a greener zone. <i>"Food Court 2 is 18 min — Food Court 5 is
              3 min walk and 85/100"</i>. Typical relief: <b>20–40%</b> of the queue shifts.
            </div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#0284c7" }}>3</div>
            <div className="txt">
              <b>Capacity actions (supply-side).</b> Routing only works if alternatives exist.
              When a gate or concourse saturates, Ops proposes
              <span className="kbd">open_gate</span> (add a sibling lane) or
              <span className="kbd">dispatch_staff</span> (increase service rate). More
              parallel throughput → shorter queues, period.
            </div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#0284c7" }}>4</div>
            <div className="txt">
              <b>Pre-emptive forecast.</b> <span className="kbd">forecast_zone</span> extrapolates
              occupancy 2–5 min ahead using EWMA inflow/outflow. The risk rule fires when
              density &gt; 0.9 <i>and</i> inflow &gt; 2× outflow for 15 s — so alerts go out
              <i>before</i> a zone goes critical, not after. That's the difference between
              "managing" crowding and "preventing" it.
            </div>
          </div>
        </div>
        <div className="info-banner" style={{ marginTop: 14 }}>
          <span aria-hidden>🔁</span>
          <span>
            <b>Why this works:</b> it's a closed loop. Action applied → simulator/real sensors
            reflect the new state → engine recomputes Flow Scores → agent re-plans. You can
            watch this on the Ops page: apply an action, wait one tick, click
            <i> Propose Actions</i> again — the plan has evolved because reality has.
          </span>
        </div>
      </section>

      <section className="legend-section">
        <h2>What you can do right now</h2>
        <div className="legend-grid">
          <div className="legend-item">
            <div className="swatch" style={{ background: "#0284c7" }}>▶</div>
            <div className="txt">
              <b>Open the <Link href="/map">Live Map</Link>.</b> The simulator is already running a 10-minute
              match cycle. Watch pre-match surge, halftime rush, and exit pressure form and resolve.
            </div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#0284c7" }}>💬</div>
            <div className="txt">
              <b>Ask the <Link href="/chat">Concierge</Link>.</b> Questions like
              <i> "quick snack?"</i>, <i>"nearest restroom from Gate A"</i>, <i>"forecast in 5 minutes"</i>.
            </div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#0284c7" }}>🛠</div>
            <div className="txt">
              <b>Run <Link href="/ops">Ops Console</Link>.</b> Log in as <span className="kbd">ops</span> / <span className="kbd">ops-demo</span>,
              drag Chaos, propose actions, apply them, watch the map heal.
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

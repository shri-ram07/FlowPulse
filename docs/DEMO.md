# FlowPulse — 5-minute demo script

## Setup
```bash
py -3 -m pip install -r backend/requirements.txt
py -3 -m uvicorn backend.main:app --port 8000 &

cd frontend && npm install && npm run dev
```

Open three tabs:
- **Fan map**: http://localhost:3000/
- **Concierge**: http://localhost:3000/chat
- **Ops console**: http://localhost:3000/ops (login `ops` / `ops-demo`)

## Beat 1 — The living map (45 s)
- Point at the stadium map. Each circle = one zone. Size = occupancy, colour = Flow Score.
- Zones pulse when they go *critical*. The banner at the top is the latest alert.
- Explain the **Crowd Flow Score** gauge (top right): one number for the whole venue.

## Beat 2 — The fan concierge (60 s)
- Switch to the Concierge tab. Click a zone on the map to set *your location*.
- Type **"quick snack"**. The agent calls `get_all_zones(kind=food)` + `get_best_route` — chips visible.
- Point out the chips: "Every number in that reply came from a tool call. The agent is not allowed to make up wait times."

## Beat 3 — The ops agent & closed loop (90 s)
- Switch to Ops console. Drag the **Chaos slider** to 60%. Watch a couple of zones go red within 30 s.
- Click **Propose Actions**. A JSON plan appears — situation, root cause, 1–4 actions with rationales citing specific numbers.
- Tap **Apply** on an action. Alert hits both maps simultaneously.
- Wait ~15 s and click **Propose Actions** again. Notice the plan evolved — the closed loop.

## Beat 4 — Why it matters (30 s)
- *"No ML infra, no Kafka, no giant models. A flow-system view of the venue + Gemini 2.0 via Google ADK with disciplined tool use."*
- *"Every agent claim is traceable to a tool call. That's the difference between a chatbot and a decision-support system."*
- *"Simulator in; real sensors out — the same engine ingests Wi-Fi probes or LiDAR counters tomorrow."*

## Fallback
If `GOOGLE_API_KEY` isn't set, both agents silently use the deterministic fallback — demo still works end-to-end and tool chips still render. Great for offline or flaky-network demos.

# FlowPulse — 3-minute submission video script

Target length: **2:45–3:00**. Captions **ON**. Keep pace brisk; judges scrub.

## Scene structure

| Time | Scene | What's on screen | Narration |
|---|---|---|---|
| 00:00-00:10 | Hook | Stadium exterior → slow zoom on a long beer queue. Title card: **"FlowPulse — the nervous system for live venues."** | *"At a stadium tonight, someone will wait 47 minutes for a beer. Two zones over, a food court sits empty. No one told them."* |
| 00:10-00:30 | Problem | Mermaid architecture diagram of "stadium apps today" (tickets, seat map, payments — none connected to reality) | *"Today's stadium apps know your seat. They do not know which queue is shortest, where pressure is building, or how to route around it."* |
| 00:30-00:50 | Insight | Animated switch: container view → graph view. Cut to live FlowPulse `/map` with pulsing zones. | *"FlowPulse treats the stadium as a flow system, not a container. Every gate, concourse, food court, restroom and exit becomes a live node with one number — the Crowd Flow Score from zero to one hundred."* |
| 00:50-01:30 | Live demo 1 — Fan view | Open `/chat`. Tap Gate A on map. Type "Quick snack?". Agent replies: "Food Court 5 — Score 85, 3-min walk." Hover over tool-chip so viewer sees `get_best_route()`. | *"The fan concierge, running on Google ADK with Gemini 2.0 Flash, answers by calling live tools on our Crowd Flow Engine. Every chip under an answer is a tool call — the agent can't make up numbers."* |
| 01:30-02:10 | Live demo 2 — Ops view | Switch to `/ops`. Log in (demo creds). Drag Chaos slider to 70. Wait for red zones. Click "Propose Actions". Plan appears. Click Apply. Toast fires. Map shows alert banner. | *"The operations agent monitors the whole venue. When pressure builds, it proposes concrete interventions — open a gate, redirect flow, dispatch staff, send a push. Staff hits Apply and the system closes the loop: the action feeds back into the engine, the map reacts on the next tick."* |
| 02:10-02:30 | Multi-agent architecture | Quick Mermaid: Orchestrator → Forecast / Routing / Safety / Comms agents. Switch to Cloud Trace flamegraph screenshot showing spans per tool call. Then Cloud Monitoring chart of `flowpulse/crowd_flow_score`. Then BigQuery table row count growing live. | *"Under the hood: five specialised ADK agents, Gemini response-schema-validated JSON output, every tool call traced in Cloud Trace, every tick streamed to BigQuery, every score tracked in Cloud Monitoring. Fourteen Google Cloud services wired end-to-end."* |
| 02:30-02:50 | Accessibility demo | Toggle "Accessible Mode" in the nav. Watch the UI shift — shapes appear on score pills, animations stop, text-only map view. Then switch to Hindi locale on Welcome. | *"A stadium serves forty thousand people. Some use screen readers, some use wheelchairs, some don't read English. Accessible Mode is not a checkbox — it's a toggle the user owns. Hindi locale out of the box."* |
| 02:50-03:00 | Close + CTA | Logo + URL card: **`flowpulse-frontend.run.app` · GitHub: shri-ram07/flowpulse**. Final line over stadium b-roll. | *"FlowPulse. The operating system for the building itself. Live right now."* |

## Capture checklist

- [ ] Record at 1920×1080, 30 fps, MP4 (H.264)
- [ ] Mic + de-noise; no background music during demo voice-over
- [ ] **Captions burned in** (not a sidecar .srt — judges sometimes scrub silently)
- [ ] Cursor visible, browser chrome hidden (F11 before recording)
- [ ] No sensitive data on screen — use incognito, scrub `.env` before any over-the-shoulder frames
- [ ] Upload unlisted to YouTube; paste link in Devpost submission

## Alternative 60-second cut (for LinkedIn)

Drop scenes 1, 7; compress 3 and 4; keep live demo + closing shot. Better auto-play performance.

## Shot-list for b-roll

- Stadium exterior (stock / generic)
- Close-up of a beer queue / busy concourse
- Phone unlock + `/map` load (device frame preferred — iPhone 15 Pro mock)
- Two-shot of Chaos slider drag + red zones appearing (screen rec)
- Cloud Trace flamegraph (zoom into one trace)
- BigQuery Preview tab with rows appearing
- Cloud Monitoring line chart with the custom metric
- Lighthouse score readout (95+ on accessibility)

## Post-production

- Opening title card: 2-second hold, fade
- Lower-third for each Google service used (pops in bottom-left, 1-second hold)
- Use the Google Cloud + Firebase + Gemini brand colours in overlays (not the logos — just the palette)
- Export: YouTube 1080p preset + a second 1080×1350 portrait export for LinkedIn native video

## Thumbnail

- Stadium overhead, flow-particle overlay screenshot
- Text: **"AI-Orchestrated Crowd Flow"**
- Google Cloud + ADK badges bottom-left

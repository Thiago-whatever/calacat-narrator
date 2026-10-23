# Roadmap

Deadline: **Oct 27 2026, 11:59 pm PT**. Internal target: **Oct 27 noon PT**. Keep the deployment live until **Nov 10** (judging).

## MVP (must ship)
- Simulator (seeded, 10×) + baseline
- `/ingest` → Event Hubs → Capture → ADLS
- Interpreter: match state, aggregates, threshold-gated signals
- Service Bus fan-out → 4 specialist agents + Editor + DLQ fallback
- MCP match-stats server
- Reporter feed + send-to-air + `/overlay` (transparent, timed JSON)
- Fan mode: language (EN/ES), depth (casual/analyst), favorite club/player, player-focus
- Heatmap + zone control views with text alternatives
- Audio narration (AI Speech)
- `azd up`

## Stretch (in order)
1. HT/FT recap agent (*required by the brief, so this is the first stretch item*)
2. Ask-the-match agent (fan Q&A → text + Vega-Lite)
3. Control room page (agent health)
4. Scenario director (LLM storylines)
5. Fabric Eventstream → Eventhouse
6. PT/FR

## Cut
Market value, contracts, injuries, trophies, auto-eventing from video, APIM.

## Day plan
| Day | Work |
|---|---|
| D1 Oct 22–23 | Docs, schemas, simulator, Bicep/azd infra, `/ingest` |
| D2 Oct 24 | Interpreter + signals + baseline, MCP server |
| D3 Oct 25 | Specialist agents, Editor, fallback, Web PubSub |
| D4 Oct 26 | UI: Reporter, Overlay, Fan, viz, TTS, ES |
| D5 Oct 27 AM | Recap, failure demo, README/pitch, video, submit |

## Submission checklist (Rules 4.4)
- [ ] Public GitHub repo
- [ ] Pitch naming the Microsoft/Azure tech used
- [ ] Demo video **< 2 min** on YouTube/Vimeo, with no third-party trademarks or copyrighted music
- [ ] Working demo URL + testing instructions (credentials if private)
- [ ] All materials in English

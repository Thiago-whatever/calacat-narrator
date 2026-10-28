# Calacat Narrator docs

Start with the [project README](../README.md) for what the project does, how to try it and how to run the checks. These docs are for contributors.

| Doc | What's in it |
|---|---|
| [architecture.md](architecture.md) | The pipeline, the agents, failure handling and the Editor's budget |
| [data-model.md](data-model.md) | Event, signal, candidate and card contracts; the simulator; the HTTP API |
| [decisions.md](decisions.md) | The decision log (ADRs): what we decided, why, and when to revisit it |
| [delivery.md](delivery.md) | Infrastructure, deployment, hosting, CI, security, cost and observability |
| [design.md](design.md) | The visual system and the Reporter console spec |
| [accessibility.md](accessibility.md) | Accessibility: what's built and what isn't yet |
| [submission.md](submission.md) | Hackathon submission kit: pre-submit checklist, video script, form text |
| [evidence/](evidence/README.md) | Screenshots of GitHub Copilot agent mode using the Azure MCP Server |

## Status

**Built and deployed:** the seeded simulator; ingest, interpret and the read API on Azure Functions; threshold-gated signals on Service Bus; four agents (Goal & Shot, Build-up & Passing, Historian, Recap) whose facts tools are served by an MCP server; the Editor's budget, the Reviewer agent with Spanish, and template fallbacks; Web PubSub push; the Reporter console with an on-air output view; judge-started matches; OpenTelemetry tracing; optional Event Hubs Capture; CI.

**Not built yet:** these are open [GitHub issues](https://github.com/Thiago-whatever/calacat-narrator/issues), each with its ID in the title:

- **Agents:** Player and milestones (C19), Tactical (C28), ask-the-match (C29), half-time recap (C27).
- **Console:** fan mode (C15), control room (C20), heatmaps and zone control (C21), audio narration (C22), Portuguese and French (C34).
- **Data and quality:** baseline curves for the signal gate (C23), scenario director (C31), groundedness evaluations (C32), Fabric (C33).
- **Delivery:** continuous deployment (C30).

## Hackathon pipeline → our implementation

| Required stage | Where it lives |
|---|---|
| Ingest | Simulator or `POST /api/matches` → `ingest` Function → Event Hubs (optional Capture to ADLS Gen2) |
| Interpret | `interpret` Function: match state in Cosmos DB, threshold-gated signals on Service Bus |
| Explain | Specialist agents call facts tools over MCP; the Editor ranks; the Reviewer approves, revises or rejects |
| Render | Web PubSub → Reporter console on GitHub Pages, with an on-air output view |
| Personalize | English or Spanish, high contrast, larger text, reduced motion |

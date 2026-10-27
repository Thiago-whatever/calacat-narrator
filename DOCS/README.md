# Calacat Narrator — Docs

**Pitch:** Calacat Narrator turns a live stream of synthetic football events into explainable "did you know?" insight cards. A team of specialist AI agents produces candidate insights. An Editor agent ranks them by how much they matter *right now*. Broadcasters pick one to send to air, and fans get the same intelligence personalized by language, depth (casual ↔ analyst), favorite club or player, and accessibility needs.

Built on Azure (Event Hubs, Functions, Service Bus, Cosmos DB, Container Apps, Web PubSub, AI Speech) with Microsoft Foundry + Microsoft Agent Framework and a custom MCP stats server. The web console is an open demo on GitHub Pages (ADR-043).

## Index
| Doc | What's in it |
|---|---|
| [architecture.md](architecture.md) | Pipeline diagram, AWS→Azure mapping, agents, failure handling |
| [decisions.md](decisions.md) | ADR log: every important decision, why, how it could be wrong |
| [data-model.md](data-model.md) | Event schemas, coordinates, zones, simulator, signal thresholds |
| [accessibility.md](accessibility.md) | Language, visual, cognitive accessibility, empowerment |
| [design.md](design.md) | Visual system and Reporter console spec |
| [roadmap.md](roadmap.md) | MVP vs stretch vs cut, day plan, submission checklist |
| [delivery.md](delivery.md) | Copilot workflow, CI/CD, hosting, judge access, cost, security |
| [progress.md](progress.md) | What is done, what is missing, setup commands |
| [backlog.md](backlog.md) | All issues by priority (P0/P1/P2) and type (Azure/Code/IaC) |

## Hackathon pipeline → our implementation
| Required stage (Rules 4.1(i)) | Where it lives |
|---|---|
| Ingest | Simulator → `/ingest` Function → Event Hubs (+ Capture → ADLS) |
| Interpret | Interpreter Function: match state, aggregates, threshold-gated signals |
| Explain | Specialist agents (via MCP stats tools) → Editor agent; each card cites evidence |
| Render | Web PubSub → Reporter feed, OBS-ready `/overlay`, Fan UI |
| Personalize | Personalizer: language, depth, club, player-focus, audio mode |

## Rubric → features (each criterion is 20%)
| Criterion | What we show |
|---|---|
| Technological Implementation | Seeded simulator + baseline, `azd up` IaC, typed schemas, tests, these docs |
| Agentic Design & Innovation | 4 specialists + Editor, MCP tool use, salience ranking, failure fallback |
| Real-World Impact | Human-in-the-loop broadcast workflow, timed machine-readable overlay JSON |
| UX & Presentation | Reporter feed, overlay, fan mode, accessibility, <2 min demo |
| Category (Best Multi-Agent System) | Distinct roles, shared state (Cosmos), handoffs (Service Bus), recovery (DLQ + templated fallback) |

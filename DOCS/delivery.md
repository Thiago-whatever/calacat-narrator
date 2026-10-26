# Delivery: dev workflow, CI/CD, hosting, security

The rubric's "Technological Implementation" lists hero technologies by name: Microsoft Foundry, Agent Framework, **Azure MCP**, **GitHub Copilot Agent Mode**, Fabric, **GitHub SDK**, **GitHub CLI**, Azure Apps and AI Services, and Azure databases. Judges can only credit what they can **see**, so every tool we use leaves evidence in the repo, and the README has a "Built with" section that links to it. We never claim a tool we didn't use.

## Development with GitHub Copilot (ADR-014)
| Use | Visible evidence |
|---|---|
| Copilot **Agent Mode** in VS Code to build features | Commits / PR descriptions noting it |
| Copilot **coding agent**: assign small, well-scoped issues (e.g. "add `corner` event to the simulator") | PRs authored by Copilot in repo history |
| Copilot **code review** on PRs | Review comments on PRs |
| `.github/copilot-instructions.md` | Repo conventions (schemas, ADR rule, a11y rules) shared with every agent |
| **Azure MCP Server** inside Copilot to inspect resources and logs | README note + a screenshot/clip |
| **GitHub CLI** (`gh`) for issues, PRs and releases | Issues and milestones in the repo |

Work through **issues → PRs**, not straight to `main`. The history becomes evidence of process.

## CI/CD with GitHub Actions (ADR-015)
- **CI on every PR:** `ruff` + `pytest` (stats engine and signal-gate self-checks), schema validation, `markdownlint-cli2`, frontend build, and an `axe` smoke test.
- **CD:** `azd pipeline config` generates a GitHub Actions workflow that runs `azd provision` + `azd deploy` on merge to `main`.
- **Auth:** OIDC federated credentials, so no Azure secrets are stored in GitHub.
- Use GitHub Actions rather than Azure Pipelines: the repo is already on GitHub, and GitHub is a hero tech.

## Infrastructure as code (ADR-020)
- `azure.yaml` selects the Bicep entry point in `infra/main.bicep`; `infra/main.parameters.json` maps the azd environment and location.
- Provision MVP resources in East US. The template references the existing Foundry account/project in `rg-calacat`; it does not create another Foundry resource.
- Cosmos DB includes the serverless `calacat/match-state` database/container used by the interpreter.
- Cosmos DB also includes `calacat/cards`, partitioned by `match_id`, with per-item TTL. The Editor Container App writes append-only card documents using the shared workload identity; the cards contract and push seam are documented in `DOCS/data-model.md`.
- Runtime access uses managed identities and scoped data-plane roles. Local/shared-key authentication is disabled where supported; public endpoints remain enabled for the MVP and `.azure/` environment state is ignored by Git (ADR-021).
- The Container Apps user-assigned identity receives Cognitive Services OpenAI User on the existing Foundry account for model calls (ADR-024).
- The Goal & Shot and Build-up & Passing specialists run as separate Docker-built Container Apps, each consuming its filtered Service Bus signal subscription and publishing candidates. They scale to zero and share the workload managed identity for Foundry, messaging, and ACR pull (ADR-025). Install the Foundry provider with the project dependencies using `python -m pip install --pre -e .`.
- Register the Event Hub, Service Bus, App, Web, SignalR Service, and Operational Insights providers before provisioning (A1).

## Hosting (what runs where)
| Component | Service | Scale |
|---|---|---|
| Web UI | Static Web Apps (Free) | — |
| Simulator, agents, Editor, MCP server | Container Apps | Editor stays at one replica to monitor signal DLQs; other workloads scale to zero when idle |
| Ingest, Interpreter | Functions (Linux Consumption, Y1) | event-driven |
| Stream | Event Hubs Standard, 1 TU | Capture needs Standard |
| Fan-out | Service Bus Standard | topics need Standard |
| State | Cosmos DB serverless | pay per request |
| Push | Web PubSub | Free tier = 20 connections / 20k msgs/day: **send cards only, never 1 Hz positions** |
| Models | Foundry deployment | TPM quota set low |
| Logs/traces | Application Insights | OpenTelemetry from Agent Framework |

## Judges' access: "replay on demand" (ADR-016)
Judging runs Oct 27 – Nov 10 and judges can show up at any time, so the deployed app has to work without us being there (Rule 4.8: free, unrestricted access).
- The landing page has a **"Kick off a match"** button that starts a seeded match at 10× (about 9 min).
- At most **2 concurrent matches**. A third viewer joins a match already running.
- No login. If we add one, the credentials go in the testing instructions.

## Cost guardrails (ADR-017)
- An **Azure budget + alert** on the resource group.
- A low TPM quota on the Foundry deployment, the concurrency cap above, and scale-to-zero.
- Rough estimate: tens of USD for the whole period, mostly Event Hubs and Service Bus Standard plus tokens. *Verify in the Azure Pricing Calculator; this is a guess.*

## Security and the public repo (ADR-018)
- The repo **must be public**, so: no keys in code or `.env` committed, **Managed Identity** between services, and Key Vault for anything that can't use identity.
- Turn on GitHub **secret scanning + push protection**.
- Foundry default **content filters** stay on. Agent prompts treat event data as data, not instructions.
- Add a LICENSE (MIT).

## Observability (ADR-019)
- OpenTelemetry traces span ingest → signal → agent → card, viewable in App Insights and Foundry tracing.
- The trace for one card is a demo-worthy "explainability" artifact.
- Stretch: **Foundry evaluations** check card *groundedness* (every number in the text matches the evidence metrics).

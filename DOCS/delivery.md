# Delivery: infrastructure, deployment, CI, security

## Infrastructure as code

- `azure.yaml` lists the services: `api` (the Function App) and one Container App each for `editor` and the agents (`agent-runtime-goal-shot`, `-buildup-passing`, `-historian`, `-recap`). All the Container Apps use the root `Dockerfile` and pick their worker with `WORKER_MODULE`.
- `infra/main.bicep` is the entry point. Its modules are `messaging`, `data`, `compute`, `observability`, `registry` and `roles`, plus `foundry-role`. `infra/main.parameters.json` maps the azd environment, location and each service's image, so a later `azd provision` keeps the deployed images.
- Resources are in **East US**. The template references the existing Foundry account and project in `rg-calacat` (deployment `narrator-chat`, `gpt-5-mini`); it doesn't create one (ADR-020, ADR-030).
- Optional: `azd env set ENABLE_CAPTURE true` turns on Event Hubs Capture to an ADLS Gen2 lake (ADR-050).

## Deploying

```bash
azd auth login
azd up            # provision + build + deploy everything, about 5 minutes
```

- Run `azd` from a **clean checkout of `main`**. `azd deploy` packages whatever is in the working folder, uncommitted changes included.
- Use `azd up`, not `azd deploy`, after any change to `infra/` or `azure.yaml`, such as a new subscription or Container App.
- There is no continuous deployment yet (C30): deploys are manual.

## Hosting

| Component | Service | Scale |
|---|---|---|
| Reporter console | GitHub Pages, published by `.github/workflows/pages.yml`; a receive-only demo with no sign-in (ADR-043) | — |
| `ingest`, `interpret`, read API, kickoff | Azure Functions, Flex Consumption (FC1), Python 3.12 | Event-driven |
| Agents | Container Apps, KEDA-scaled on their Service Bus subscription | 0–2 replicas |
| Editor and Reviewer | Container App | Exactly 1 replica (it holds the in-memory queue and watches the dead letters) |
| Stream | Event Hubs Standard | Capture needs Standard |
| Fan-out | Service Bus Standard | Topics need Standard |
| State and cards | Cosmos DB, serverless | Pay per request |
| Push | Web PubSub, Free tier | 20 connections and 20k messages a day, so it carries cards only |
| Model | Foundry `narrator-chat` (`gpt-5-mini`), 50K tokens per minute | — |
| Logs and traces | Application Insights | OpenTelemetry (ADR-049) |

## Judges' access (ADR-016, ADR-044)

Judges can visit at any time without us there, so the deployed app has to work on its own.

- The console's **Start live match** button calls `POST /api/matches`, which starts a match with a server-chosen seed at 10× speed (about 9 minutes).
- At most 2 matches run at once, and 20 start per UTC day. A request that arrives while both are busy, or within a minute of a kickoff, joins the running match instead.
- There's no login.

## CI

`.github/workflows/ci.yml` runs on every pull request and every push to `main`:

- **Python and Bicep:** `ruff check`, `pytest`, `az bicep build`.
- **Web console:** `npm test`, `npm run lint`, `npm run build`.

## Security (ADR-018, ADR-021)

- Services talk to each other with **managed identities** and scoped data-plane roles. Shared keys and local auth are off where the service supports it. No secrets are in the repo or in GitHub.
- `POST /api/ingest` needs a Function key. The simulator reads it from `INGEST_FUNCTION_KEY`. The read endpoints and `POST /api/matches` are anonymous, and the latter is behind the caps above.
- Endpoints are public (TLS only). Private networking is future work.
- Foundry's default content filters are on. Agent prompts treat match facts as data, never as instructions.
- `.azure/` (the azd environment) and `.env*` files are ignored by Git.

## Cost (ADR-017)

- A monthly budget alert on the subscription, a low model quota, scale-to-zero agents and the match caps above.
- When idle, the deployment costs a few USD a day, mostly Event Hubs and Service Bus Standard. Capture adds a per-hour charge, which is why it's off by default.

## Observability (ADR-049)

- One trace per `interpret` batch, from Event Hubs processing through the signals, the agents (including their model and tool calls) and the Editor. Look for it in Application Insights under the card's `calacat.signal_id` or `calacat.match_id`.
- For a quick look without traces, `az containerapp logs show -n <app> -g rg-calacat-dev` shows the Editor's `Review failed` and `Dead-lettering` warnings.

## Development with GitHub Copilot (ADR-014)

- `.github/copilot-instructions.md` holds the repo's conventions for every agent.
- `.vscode/mcp.json` registers the `calacat-match-stats` MCP server for Copilot agent mode.
- [evidence/](evidence/README.md) shows Copilot agent mode using the Azure MCP Server against the deployed resource group.

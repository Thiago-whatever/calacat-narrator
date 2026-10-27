# Progress log

What we're doing, what's done, and what's missing. Setup last checked **2026-10-27** with the CLI commands shown; build checklist last checked **2026-10-27** against `main` and GitHub.

## What we're doing
We're building **Calacat Narrator**, an entry for the Microsoft × Premier League "Inside the Game" hackathon (deadline **Oct 27 2026, 11:59 pm PT**). A simulator plays a fictional football match. Azure moves the events through a pipeline. AI agents turn stats into "did you know?" cards that a TV reporter can put on air and fans can personalize (language, depth, favorite club/player, accessibility). See [README.md](README.md) and [architecture.md](architecture.md).

Right now we're in the **submission phase**. The pipeline, the agents (specialists with the facts tool, Reviewer and Spanish) and the console are merged on `main` (C1–C13, C36–C39). Open PRs: Pages (C40, #61), Start a match (C16, #68), overlay view (C14, #69), CI (C25, #70) and the submission docs (S1). What's left is merging them, a full `azd deploy`, making the repo public, the video and the form ([submission.md](submission.md)).

## Setup checklist
| # | Step | Status | Verified with |
|---|---|---|---|
| 1a | Install Azure CLI, azd, GitHub CLI, Functions Core Tools | ✅ Done: az 2.91.0, azd 1.37.1, gh 2.103.1, func 4.15.2 | `az version`, `azd version`, `gh --version`, `func --version` |
| 1b | Python | ✅ 3.12.4 (Anaconda) | `python --version` |
| 1c | `az login` | ✅ Visual Studio Enterprise Subscription | `az account show -o table` |
| 1d | `azd auth login` | ✅ Logged in | `azd auth login --check-status` |
| 1e | `gh auth login` | ✅ Logged in as `Thiago-whatever` (scopes: repo, workflow, read:org, gist) | `gh auth status` |
| 2 | Register Azure resource providers | ✅ All registered, including EventHub, ServiceBus, App, Web, SignalRService, OperationalInsights | `az provider list --query "[?namespace=='Microsoft.App'].registrationState"` |
| 3a | Resource group `rg-calacat` | ✅ East US 2, Succeeded | `az group show -n rg-calacat` |
| 3b | Foundry project `calacat-narrator` | ✅ Created. Resource is in **East US** (not East US 2) | `az cognitiveservices account list -g rg-calacat` |
| 3c | Model deployment `narrator-chat` | ✅ `gpt-5-mini` 2025-08-07, GlobalStandard, 50K TPM, NoAutoUpgrade, DefaultV2, Succeeded (see ADR-030) | `az cognitiveservices account deployment list -g rg-calacat -n calacat-narrator` |
| 3d | Test call to the model with Entra ID (no key) | ❌ Not yet. Needs the role *Cognitive Services OpenAI User* for your account | — |
| 4 | Budget alert | ✅ `calacat-monthly-budget`, 60 per month | `az consumption budget list` |
| 5a | GitHub Copilot plan checked | ❌ Unknown (Free or Pro?) | github.com/settings/copilot |
| 5b | Repo public + secret scanning + push protection | ❌ Repo is **PRIVATE**. Must be public by submission. | `gh repo view --json visibility` |

**Endpoint** (not a secret): `https://calacat-narrator.cognitiveservices.azure.com/` · deployment: `narrator-chat`.

### To finish setup
```powershell
# 2. Register the missing providers (takes a few minutes)
foreach ($ns in 'Microsoft.EventHub','Microsoft.ServiceBus','Microsoft.App','Microsoft.Web','Microsoft.SignalRService','Microsoft.OperationalInsights') { az provider register --namespace $ns }

# 3d. Allow your own account to call the model without a key
$me = az ad signed-in-user show --query id -o tsv
$ai = az cognitiveservices account show -g rg-calacat -n calacat-narrator --query id -o tsv
az role assignment create --assignee $me --role "Cognitive Services OpenAI User" --scope $ai
```
- Step 4: Portal → Cost Management → Budgets → Add (monthly, ~50–70% of your VS credit; alerts at 50/80/100% actual + 100% forecast).
- Step 5: Check your Copilot plan. Make the repo public, then Settings → Advanced Security → turn on secret scanning + push protection.

## Build checklist (from roadmap.md)
| Item | Status |
|---|---|
| Docs: README, architecture, decisions (ADR-001…044), data-model, accessibility, roadmap, delivery, progress, backlog | ✅ On `main` (ADR-044 in #68) · submission kit in review |
| Repo hygiene: `RULES/` case, `.github/copilot-instructions.md`, MIT LICENSE (C1) | ✅ #43 |
| GitHub issues | ✅ #1–#42 |
| Event schemas + fictional data (C2) | ✅ #44 |
| Simulator, seeded, `--speed` (C3) | ✅ #45 · baseline curves (C23) ❌ |
| Bicep / azd infra (C4) | ✅ #46 in code · ❌ not provisioned (`azd up`); Capture (C24) ❌ |
| `/ingest` Function → Event Hubs (C5) | ✅ #47 |
| Interpreter (C6) + signal gate (C7) | ✅ #48, #49 |
| Model access for the runtime identity (A2) + agent runtime (C8) | ✅ #50, #51 (role assignment needs provisioning) |
| Specialists: Goal & Shot (C9), Build-up & Passing (C10) | ✅ #52, #53 · Player (C19), Tactical (C28) ❌ |
| Editor + recovery fallback (C11) | ✅ #54 |
| MCP stats server (C18) | ❌ |
| Push cards to browsers (C12) | ✅ |
| UI: Reporter (C13) | ✅ (`web/`; GitHub Pages deploy pending, ADR-043) |
| Facts-only realistic simulator (C36) | ✅ #63 (2.8 goals, 27 shots per match over 20 seeds) |
| Facts tool + validated captions (C37) | ✅ #64 |
| Reviewer agent + Spanish (C38) | ✅ #65 · full `azd deploy` + 10-card review still to do |
| Console: player, team, minute, avatar, EN/ES (C39) | ✅ #66 |
| GitHub Pages receive-only demo, CORS, CSP (C40) | ✅ #61 · needs public repo (G1), Pages enabled, and `azd provision` for CORS |
| UI: Overlay (C14), Fan (C15) | ✅ C14 #69 (in-console view, ADR-043) · C15 ❌ |
| Kick-off endpoint (C16), FT recap (C17) | ✅ C16 #68 (ADR-044) · needs `azd deploy` · C17 ❌ |
| CI (C25) | ✅ #70, green on main |
| Deploy + smoke test (D1), public repo (G1), submission (S1) | ❌ · S1 docs in review ([submission.md](submission.md)) |

**Critical path left:** the pre-submit checklist in [submission.md](submission.md): secret scan, repo public (G1), Pages, merge #61 and the open PRs, a full `azd deploy` (D1) with the 10-card review, then the video and the form (S1). The target is Oct 27 noon PT (ADR-042).

## What Claude has helped with so far
- Read the hackathon rules and rubric. Flagged the deadline, scope, data-generator, persona, trademark and missing-requirement issues.
- Translated the AWS design to Azure and designed the architecture, agents, Editor budget and threshold-gated signals.
- Wrote all DOCS files and ADR-001…020.
- Walked through the tool installs. Diagnosed the "command not found" error (VS Code kept the old PATH) and the `!` parse error (`!` only works in the Claude Code prompt, not in PowerShell).
- Explained the Visual Studio Enterprise subscription's credit and spending limit.
- Diagnosed "Cuota insuficiente" (insufficient quota) for `gpt-5.4-mini` with `az cognitiveservices usage list`, found `gpt-5-mini` quota (500K TPM), and guided the deployment settings.
- Verified the whole setup state with the CLI for this log. That's how we found the unregistered providers and the East US region mismatch.

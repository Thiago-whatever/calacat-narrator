# Progress log

What we're doing, what's done, and what's missing. Setup last checked **2026-10-25** with the CLI commands shown; build checklist last checked **2026-10-26** against `main` and GitHub.

## What we're doing
We're building **Calacat Narrator**, an entry for the Microsoft × Premier League "Inside the Game" hackathon (deadline **Oct 27 2026, 11:59 pm PT**). A simulator plays a fictional football match. Azure moves the events through a pipeline. AI agents turn stats into "did you know?" cards that a TV reporter can put on air and fans can personalize (language, depth, favorite club/player, accessibility). See [README.md](README.md) and [architecture.md](architecture.md).

Right now we're in the **build phase**: the backend pipeline through the Editor (C1–C11) is merged on `main`; next are push-to-browser, the UIs, deploy and submission.

## Setup checklist
| # | Step | Status | Verified with |
|---|---|---|---|
| 1a | Install Azure CLI, azd, GitHub CLI, Functions Core Tools | ✅ Done: az 2.91.0, azd 1.37.1, gh 2.103.1, func 4.15.2 | `az version`, `azd version`, `gh --version`, `func --version` |
| 1b | Python | ✅ 3.12.4 (Anaconda) | `python --version` |
| 1c | `az login` | ✅ Visual Studio Enterprise Subscription | `az account show -o table` |
| 1d | `azd auth login` | ✅ Logged in | `azd auth login --check-status` |
| 1e | `gh auth login` | ✅ Logged in as `Thiago-whatever` (scopes: repo, workflow, read:org, gist) | `gh auth status` |
| 2 | Register Azure resource providers | ⚠️ **Partly.** Registered: DocumentDB, CognitiveServices, Storage, Insights, KeyVault. **Not registered:** EventHub, ServiceBus, App, Web, SignalRService, OperationalInsights | `az provider show -n <ns> --query registrationState` |
| 3a | Resource group `rg-calacat` | ✅ East US 2, Succeeded | `az group show -n rg-calacat` |
| 3b | Foundry project `calacat-narrator` | ✅ Created. Resource is in **East US** (not East US 2) | `az cognitiveservices account list -g rg-calacat` |
| 3c | Model deployment `narrator-chat` | ✅ `gpt-5-mini` 2025-08-07, GlobalStandard, 50K TPM, NoAutoUpgrade, DefaultV2, Succeeded (see ADR-030) | `az cognitiveservices account deployment list -g rg-calacat -n calacat-narrator` |
| 3d | Test call to the model with Entra ID (no key) | ❌ Not yet. Needs the role *Cognitive Services OpenAI User* for your account | — |
| 4 | Budget alert | ❌ Not created | `az consumption budget list` (empty) |
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
| Docs: README, architecture, decisions (ADR-001…030), data-model, accessibility, roadmap, delivery | ✅ On `main` (progress + backlog not committed yet) |
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
| UI: Reporter (C13), Overlay (C14), Fan (C15) | ❌ |
| Kick-off endpoint (C16), FT recap (C17) | ❌ |
| CI (C25) | ❌ (tests only run locally: 74 passing, ruff clean) |
| Deploy + smoke test (D1), public repo (G1), submission (S1) | ❌ |

**Critical path left:** C12 → C13 → D1 → S1, plus G1. It's Oct 26 and the deadline is Oct 27 11:59 pm PT, so treat everything outside that path as optional.

## What Claude has helped with so far
- Read the hackathon rules and rubric. Flagged the deadline, scope, data-generator, persona, trademark and missing-requirement issues.
- Translated the AWS design to Azure and designed the architecture, agents, Editor budget and threshold-gated signals.
- Wrote all DOCS files and ADR-001…020.
- Walked through the tool installs. Diagnosed the "command not found" error (VS Code kept the old PATH) and the `!` parse error (`!` only works in the Claude Code prompt, not in PowerShell).
- Explained the Visual Studio Enterprise subscription's credit and spending limit.
- Diagnosed "Cuota insuficiente" (insufficient quota) for `gpt-5.4-mini` with `az cognitiveservices usage list`, found `gpt-5-mini` quota (500K TPM), and guided the deployment settings.
- Verified the whole setup state with the CLI for this log. That's how we found the unregistered providers and the East US region mismatch.

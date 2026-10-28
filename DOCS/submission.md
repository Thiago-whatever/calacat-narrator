# Submission kit

Everything needed to submit by **Oct 27 2026, 11:59 pm PT**. The order is: the checklist below, the video, and then the form. Keep the deployment running until judging ends on **Nov 10**, and don't change the submission after the deadline.

## Pre-submit checklist

Do these in order. Each one depends on the step before it.

1. **Secret scan of everything on GitHub** (the repo is about to become public). Scan `--remotes`, not `--all`: local-only refs such as the agent's checkpoints never get published. GitHub also keeps a `refs/pull/<n>/head` ref for every pull request, merged or closed, even after its branch is deleted, and those become public too. A plain fetch skips them, so fetch them into `--remotes` first:
   ```bash
   git fetch --prune origin
   git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'
   git log --remotes --name-only --format= | sort -u | grep -E '(^|/)\.env|match\.jsonl|\.pem$|\.pfx$' | grep -v '\.env\.example$'
   git grep -nIE 'AccountKey=|SharedAccessKey=|sig=[A-Za-z0-9%]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key\s*[:=]\s*\S{16,}' $(git rev-list --remotes)
   ```
   Both should print nothing. If either finds something, stop. Rotate the secret first, then remove it from history, before going public. A hit that is only reachable through a `pr/*` ref can't be removed by rewriting branches: deleting PR refs needs GitHub Support, so rotating the secret is the fix.
   One hit is known and expected: `match.jsonl` and `.claude/launch.json` in one old pull-request ref. They are fictional simulator output and a local dev-server config, and the content scan finds no secrets in them.
2. **Make the repo public.** Settings → General → Danger Zone → Change visibility.
3. **Turn on secret scanning and push protection.** Settings → Advanced Security.
4. **Set up Pages.**
   - Settings → Pages → Source: **GitHub Actions**.
   - Settings → Secrets and variables → Actions → **Variables**: `VITE_API_BASE_URL` = `https://fn-calacatdevzehkqyrl.azurewebsites.net/api`. It's a variable, not a secret.
5. **Deploy once, from a clean checkout of `main`:** `azd up`. It provisions the CORS rule for the Pages origin (`webConsoleOrigin`), without which the Pages console can't call `/api/negotiate` or `/api/cards`, and deploys every service.
6. **Publish the console:** Actions → **Deploy web to GitHub Pages** → **Run workflow** (it also runs on every push to `main` that touches `web/`).
7. **Logged-out check**, in a private window with no GitHub session:
   - The repo page and README load. The Mermaid diagram renders.
   - https://thiago-whatever.github.io/calacat-narrator/ loads. Play demo → go live → pull works, and **Open on-air output** shows the card with the ON AIR tally.
   - A live match shows cards. Use **Start live match** (the judges' path). The README's simulator option needs your Function key, so it only works for you or in a reader's own subscription.
   - The video link plays without signing in.
8. **Submit** the form with the text below.

## Demo video script (≈ 1:50)

Record at 1080p. Use the console in a light theme, at 10× match speed and with a live match. Don't use music with a copyright or any real club or league marks. All data is fictional.

| Time | On screen | Voice-over |
| --- | --- | --- |
| 0:00–0:12 | Console in English, empty feed. Press **Start live match** (or run the simulator) | "This is Calacat Narrator. A team of AI agents watches a live football match and writes the insight cards a broadcaster can put on air, and checks them first." |
| 0:12–0:30 | Mermaid diagram from the README, zooming along the flow | "Events go through Azure Functions into Event Hubs. The interpreter keeps the match state in Cosmos DB and fires a signal only when something is worth saying. Service Bus routes each signal to a specialist agent." |
| 0:30–0:50 | First cards arrive in the feed; point at the agent badge on one | "Four agents on Microsoft Agent Framework and a Foundry model each take one kind of moment: goals and shots, passing, the club's history, and the full-time recap. None gets numbers in its prompt: each calls a facts tool, served over MCP, and writes a caption in a broadcast voice." |
| 0:50–1:08 | A goal card arrives. Point at the minute and score | "The Editor, in code, decides what's worth the airtime. Then a Reviewer agent approves, fixes or rejects each card and writes the Spanish in the same call. Every number has to match the facts." |
| 1:08–1:25 | Click the card, drag and resize it, then Go live → countdown → on air. Open the overlay tab | "The reporter stays in control. They pick a card, place it, go live on any of three outputs, and pull it when they're done." |
| 1:25–1:38 | Switch to **ES**; turn on high contrast and larger text | "The same cards in Spanish, plus high contrast, larger text and reduced motion, all keyboard-operable." |
| 1:38–1:50 | Code view: `azd up`, the CI badge or run, then the console with the logo | "If an agent fails, a template built from the same facts goes out, so the feed never goes quiet. It's all deployed with Bicep and azd. Calacat Narrator: live insight, checked before air." |

## Submission form text

**Project name:** Calacat Narrator

**Category:** Best Multi-Agent System

**Tagline (one line):** Live football insight cards written by a team of AI agents, checked by a Reviewer agent, and put on air by a human.

**Description:**
> Calacat Narrator turns a live stream of football events into short broadcast captions a reporter can put on air. A seeded simulator plays a fictional match into Azure Functions and Event Hubs. An interpreter keeps the match state in Cosmos DB and fires threshold-gated signals on Service Bus.
>
> Four agents built on Microsoft Agent Framework with a Microsoft Foundry model each take one kind of moment: Goal & Shot, Build-up & Passing, a Historian that puts a goal in the context of a fictional club archive, and a full-time Recap. Each calls a facts tool, served by an MCP server, instead of reading numbers from the prompt, and returns a structured, length-checked caption.
>
> An Editor in code ranks candidates by importance, rarity and recency, and keeps to an on-air budget. A Reviewer agent then approves, revises or rejects each card and writes the Spanish version, and code checks every number against the facts. When an agent fails or times out, a templated card built from the same facts goes out instead, so goals are never missed.
>
> Cards reach a React console on GitHub Pages through Web PubSub in seconds. The reporter previews, edits, places and goes live on one of three outputs. English and Spanish, high contrast, larger text, reduced motion and full keyboard control are built in.
>
> All infrastructure is Bicep deployed with azd and uses managed identities. OpenTelemetry traces each card from the event to the Editor, and CI runs on every pull request. All teams, players and matches are fictional.

**Microsoft / Azure technology used:** Microsoft Foundry (gpt-5-mini), Microsoft Agent Framework, Azure Functions (Flex Consumption), Azure Event Hubs, Azure Service Bus, Azure Cosmos DB, Azure Container Apps, Azure Web PubSub, Azure Container Registry, Application Insights with OpenTelemetry, Model Context Protocol (MCP), Bicep, Azure Developer CLI, GitHub Actions, GitHub Pages.

**Repository:** https://github.com/Thiago-whatever/calacat-narrator

**Demo URL:** https://thiago-whatever.github.io/calacat-narrator/

**Testing instructions:** No sign-in is needed. See the README's [Testing instructions](../README.md#testing-instructions): demo mode in one click, and a live, agent-narrated match from the Start live match button or one simulator command.

**Video:** *(add the YouTube or Vimeo link after uploading; under 2 minutes)*

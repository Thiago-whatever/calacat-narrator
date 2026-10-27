# Decision log (ADRs)

Format: **Decision** / **Why** / **How it could be wrong** / **Revisit when**. Add new entries at the bottom; never delete. Mark replaced ones *Superseded by ADR-NNN*.

---

## ADR-001 — Thin vertical slice before breadth
- **Decision:** Get all 5 pipeline stages working end-to-end with a few insight types before adding more.
- **Why:** Judges score a complete pipeline (Rules 4.1(i)) and a working demo (4.3). We have ~5 days solo, and a stat that never reaches the screen scores nothing.
- **How it could be wrong:** The demo may feel thin on football depth compared with stats-heavy entries.
- **Revisit when:** The slice runs end-to-end. Then add insight types in order of demo value.

## ADR-002 — Deterministic seeded simulator, not an LLM data generator
- **Decision:** A Python possession/Markov model over pitch zones emits events plus 1 Hz positions. An LLM "scenario director" may inject storylines (optional).
- **Why:** LLMs are slow and costly per event, drift on consistency (score, positions), and can't replay. Seeds give reproducible demos and tests.
- **How it could be wrong:** Simple models produce unrealistic play (wrong pass lengths, odd shapes), and judges who know football may notice.
- **Revisit when:** Baseline distributions look off compared with known football norms (passes/match ~900–1100, shots ~25).

## ADR-003 — Deterministic stats, LLM only on signals
- **Decision:** The Interpreter computes all metrics in code. Agents are invoked only on threshold-gated signals and must cite evidence event IDs.
- **Why:** Cost, latency, and **explainability**: numbers are verifiable, so agents can't hallucinate stats.
- **How it could be wrong:** Rigid signals can miss emergent stories that an LLM watching everything would catch.
- **Revisit when:** Replays show obviously interesting moments with no card. Then add agent-proposed context signals (see ADR-013).

## ADR-004 — Event Hubs + Service Bus topics (over Event Grid)
- **Decision:** Event Hubs for the raw stream, and a Service Bus topic with SQL-filtered subscriptions for fan-out to agents.
- **Why:** This is the closest match to Kinesis + SNS filter policies. DLQ and retries support the failure-recovery story the Multi-Agent category asks for.
- **How it could be wrong:** It's two messaging services to provision and pay for (both Standard tier). Event Grid alone might be simpler.
- **Revisit when:** Provisioning eats more than half a day, or cost is a problem.

## ADR-005 — Continuous coordinates, grid at query time
- **Decision:** Store x/y in meters on a 105×68 pitch. The 5×9 zone grid (finer in the boxes) is a binning function applied at query time.
- **Why:** The grid can change without regenerating data, and it supports heatmaps, Voronoi control, and convex hulls.
- **How it could be wrong:** Query-time binning on 125k rows/match could be slow in Cosmos.
- **Revisit when:** Zone queries take more than ~500 ms. Then precompute per-zone aggregates in the Interpreter.

## ADR-006 — Fictional clubs and players only
- **Decision:** All teams, players, crests and names are invented. No real market values, injuries or contracts.
- **Why:** Rules 4.4 and 4.7 (no third-party trademarks, synthetic data only) and IP safety.
- **How it could be wrong:** Fictional names reduce emotional pull in the demo.
- **Revisit when:** Never for the submission.

## ADR-007 — Target Grand Prize + Best Multi-Agent System
- **Decision:** Optimize the design and demo for the Multi-Agent category.
- **Why:** The idea is already a specialist-plus-editor system. The judging checklist (roles, shared state, handoffs, recovery) maps one to one.
- **How it could be wrong:** Many entries may pick this category. Cloud Native might be less crowded.
- **Revisit when:** It's fixed at submission. The architecture still earns Cloud Native credit, and judges can reassign.

## ADR-008 — Editor budget: salience score + rate limit
- **Decision:** `salience = event_weight × rarity × recency_decay × relevance(focus)`. Critical events preempt. Otherwise max 1 card per 20–30 s, a visible queue of 6–8, TTL 2–3 min, dedupe by topic.
- **Why:** A reporter can't read hundreds of cards. Broadcast needs a few high-value, timely options.
- **How it could be wrong:** Weights are guesses, and a quiet spell may produce no cards while a chaotic spell buries good ones.
- **Revisit when:** Tune by watching 10× replays. All values live in `editor.yaml`.

## ADR-009 — Custom MCP server for match stats
- **Decision:** Agents read stats through an MCP server (`get_player_stats`, `zone_control`, `pass_network`, …) over Cosmos.
- **Why:** It's one tool surface for all agents and for outside developers (empowerment), and it counts toward the MCP rubric item.
- **How it could be wrong:** An extra hop adds latency and another service to deploy.
- **Revisit when:** Tool latency exceeds ~300 ms p95. Then embed the queries directly in agents.

## ADR-010 — Functions HTTP ingest instead of API Management
- **Decision:** The simulator POSTs to a Function that validates the schema and forwards to Event Hubs.
- **Why:** It's a realistic HTTP ingest with validation at the trust boundary, with far less setup than APIM.
- **How it could be wrong:** The public demo endpoint has no rate limiting or API keys. Schema validation and a bounded request size limit malformed input, but production use needs an authenticated, rate-limited gateway.
- **Revisit when:** For enterprise readiness, put APIM in front (documented, not built).

## ADR-011 — Fabric deferred
- **Decision:** No Fabric in the MVP. Event Hubs Capture → ADLS keeps the lake ready for it.
- **Why:** It's a hero tech but would cost about a day we don't have.
- **How it could be wrong:** It loses points on "effective use of hero technologies".
- **Revisit when:** The MVP is done by D4. Then add Eventstream → Eventhouse for fan analytics.

## ADR-012 — Personas: Reporter and Fan (Casual ↔ Analyst)
- **Decision:** Two modes. Reporter is a ranked feed plus send-to-air. Fan has a depth switch (casual/analyst), favorite club, favorite player, player-focus, and language.
- **Why:** The rules explicitly contrast a "data-hungry analyst" and a "casual fan" and also name broadcast scenarios.
- **How it could be wrong:** Three audiences in one UI may blur the demo story.
- **Revisit when:** The UX test shows confusion. Then split into separate routes.

## ADR-013 — Threshold-gated signals vs a per-minute baseline
- **Decision:** A stat becomes a signal only when it passes its rule in `signals.yaml`: minimum sample, minimum match time, deviation from the expected-at-minute baseline (≥2σ or top/bottom 5%), absolute milestones, change held over a window with hysteresis, and a per-(metric, entity) cooldown. Goals, red cards and penalties bypass the gate. The baseline comes from ~50 seeded simulated matches.
- **Why:** Raw stats early in a match are noise ("100% pass completion at 1'"). Significance depends on time and context.
- **How it could be wrong:** Hand-picked thresholds miss context-driven stories ("first shot on target after 70 minutes"). The baseline is only as realistic as the simulator.
- **Revisit when:** Replays show missed moments. Let agents propose context signals; tune the thresholds.

## ADR-014 — Develop with GitHub Copilot, and leave evidence
- **Decision:** Use Copilot Agent Mode, the Copilot coding agent (on issues), Copilot code review, `.github/copilot-instructions.md`, Azure MCP Server and `gh`. Work through issues → PRs.
- **Why:** These are named hero technologies in the rubric, and judges only credit what they can see in the repo.
- **How it could be wrong:** Issue/PR ceremony costs time solo, and Copilot-agent PRs need review time.
- **Revisit when:** The PR overhead exceeds ~10% of the day. Then batch small changes.

## ADR-015 — GitHub Actions + azd for CI/CD, OIDC auth
- **Decision:** CI runs lint, tests, build and an a11y smoke test on PRs. CD comes from `azd pipeline config` on merge to `main`. Federated credentials, no stored secrets.
- **Why:** Quality-practices criterion, reproducibility, GitHub hero tech, and no secrets in a public repo.
- **How it could be wrong:** Setting up the pipeline can eat hours.
- **Revisit when:** It isn't green by end of D2. Then deploy manually with `azd up` and keep CI only.

## ADR-016 — Replay on demand for judges
- **Decision:** A "Kick off a match" button starts a seeded 10× match, capped at 2 concurrent. No login.
- **Why:** Judges test asynchronously Oct 27 – Nov 10 (Rule 4.8). A live-only demo would be empty when they visit.
- **How it could be wrong:** Abuse could burn tokens and budget.
- **Revisit when:** The budget alert fires. Then serve cached cards for replayed seeds.

## ADR-017 — Cost guardrails
- **Decision:** Budget alert, low Foundry TPM quota, scale-to-zero, and Web PubSub carries cards only.
- **Why:** The deployment must stay up ~3 weeks on a personal subscription.
- **How it could be wrong:** Low quota could throttle agents mid-demo.
- **Revisit when:** Before recording the video, raise the quota temporarily.

## ADR-018 — Security for a public repo
- **Decision:** Managed Identity, Key Vault, secret scanning + push protection, Foundry content filters on, MIT license.
- **Why:** The repo must be public, and these items also count toward enterprise readiness.
- **How it could be wrong:** Managed Identity role assignments in Bicep are fiddly and can slow D1.
- **Revisit when:** Never skip for secrets. If MI blocks progress, use Key Vault references temporarily.

## ADR-019 — End-to-end OpenTelemetry tracing
- **Decision:** One trace per card across ingest → signal → agent → Editor, in App Insights / Foundry tracing.
- **Why:** It's cheap with Agent Framework, makes debugging possible, and doubles as an explainability demo.
- **How it could be wrong:** Trace propagation across Service Bus needs manual context passing.
- **Revisit when:** Propagation takes more than an hour. Then trace per hop and correlate by `signal_id`.

## ADR-020 — East US infrastructure and low-reasoning Foundry calls
- **Decision:** Deploy MVP Azure resources in East US (`eastus`), reference the existing `calacat-narrator/proj-default` Foundry project, and use low reasoning effort for agent calls.
- **Why:** The existing Foundry account and project are in East US; keeping dependent resources in that region avoids creating a second AI resource. Low reasoning effort keeps routine narrative calls responsive and cost-conscious.
- **How it could be wrong:** East US capacity or service availability may change, and low reasoning effort may reduce narrative quality for complex moments.
- **Revisit when:** Required service capacity is unavailable in East US or evaluation shows that a higher reasoning effort materially improves grounded cards.

## ADR-021 — Public endpoints for the MVP

**Decision:** Keep Azure service endpoints public for the MVP; require TLS and managed-identity/RBAC access, and disable shared-key, local, anonymous, or public-blob access where supported.

**Why:** The public demo needs reachable app and Web PubSub endpoints, while a private network would add infrastructure and deployment dependencies outside this slice.

**How it could be wrong:** Public endpoints increase network exposure even when data access requires identity-based authorization.

**Revisit when:** Before production use or when a private network boundary is available; add private endpoints and restrict public access then.

## ADR-022 — Match-keyed event ordering and aggregate persistence

**Decision:** Partition Event Hubs by `match_id`; persist one Cosmos DB aggregate document per match, deduplicating by event sequence and using ETags for concurrent updates.

**Why:** The interpreter needs ordered, replay-safe state updates while keeping its query and storage model small for the MVP.

**How it could be wrong:** A partition key concentrates one match's traffic on one partition, and a single document may become a contention point at higher event rates.

**Revisit when:** Per-match throughput or Cosmos conflict rates become material; then partition aggregates by match plus entity or use an append-only event ledger.

## ADR-023 — Publish gated signals before committing match state

**Decision:** Evaluate signal gates from the proposed state and publish to Service Bus before committing the corresponding Cosmos update; use deterministic signal IDs with the topic's duplicate detection.

**Why:** A failed publish leaves the Event Hubs event uncheckpointed and retryable, avoiding a committed aggregate with a silently lost signal.

**How it could be wrong:** Service Bus may accept a signal before a later Cosmos conflict or failure; duplicate detection limits but does not eliminate duplicates beyond its configured history window.

**Revisit when:** The pipeline requires stronger exactly-once behavior; replace this ordering with a transactional outbox and Cosmos change-feed publisher.

## ADR-024 — Grant model access to the agent workload identity

**Decision:** Assign Cognitive Services OpenAI User on the existing Foundry account to the user-assigned identity intended for Container Apps, not the ingest/interpreter Function identity.

**Why:** The Container Apps agent runtime calls Foundry; granting only that workload identity follows least privilege and avoids giving model access to unrelated Functions.

**How it could be wrong:** If the agent service uses a different managed identity, the deployment will need to attach and authorize that identity instead.

**Revisit when:** The Container App identity or Foundry account changes; verify the deployed agent uses this exact identity before rollout.

## ADR-025 — Keep agent provenance and message settlement in the application

**Decision:** Run the reusable Agent Framework worker in Container Apps. Set `AZURE_CLIENT_ID` to its attached user-assigned identity so the shared `DefaultAzureCredential` selects that identity for Foundry and Service Bus in Azure, while leaving local developer credential fallback intact. Consume one configured, filtered Service Bus signal subscription; renew each peek lock for up to five minutes; use the Foundry `narrator-chat` deployment at low reasoning effort and structured output for narrative text only. Attach metrics and evidence IDs from the validated signal in application code, publish a deterministic candidate before completing its input, and scale on the subscription with KEDA and managed identity.

**Why:** This keeps narrative claims traceable, lets later specialists reuse the runtime, and ensures failed inference or candidate publication leaves the signal retryable without secrets.

**How it could be wrong:** The generic prompt may be too broad for specialist-quality analysis, and retries can still duplicate work or output after Service Bus duplicate detection expires.

**Revisit when:** Adding a specialist prompt, changing the Foundry deployment, or moving to transactional outbox semantics.

## ADR-026 — Ground Goal & Shot narratives in bounded event evidence
- **Decision:** Goal and penalty signals carry a typed copy of their source event's relevant shot or set-piece context. The Goal & Shot specialist receives a role-specific prompt, while application code attaches shot speed and xG to candidate metrics.
- **Why:** Aggregate goal counts alone cannot support chance-quality or shot-speed narration; keeping event context tied to an evidence ID allows those claims without giving the model authority over metrics or provenance.
- **How it could be wrong:** Copying context into signals duplicates a small amount of event data, and shot-volume signals still summarize counts rather than every underlying shot.
- **Revisit when:** The specialist receives match-stat MCP tools or a new signal contract provides richer evidence.

## ADR-027 — Ground Build-up & Passing narratives in pass evidence
- **Decision:** Passing signals carry typed context from their triggering pass, and the Build-up & Passing specialist receives role-specific instructions. Application code attaches pass difficulty and the inside-opponent-shape flag to candidate metrics; separate filtered Container Apps workers consume the goal-shot and build-up-passing subscriptions.
- **Why:** A pass streak alone cannot support claims about difficulty or where a reception occurred. Linking these bounded details to an evidence event keeps the narrative specific to what the signal proves and preserves the existing Goal & Shot worker.
- **How it could be wrong:** The triggering pass's context does not describe every pass in the streak, so this specialist cannot make aggregate claims about the sequence.
- **Revisit when:** The interpreter computes deterministic sequence-level pass metrics or the specialist receives validated match-stat tools.

## ADR-028 — Rank, persist, and recover Editor cards deterministically
- **Decision:** The Editor ranks candidates using application-owned topic weights, rarity, match-clock recency decay, and optional focus relevance from `editor.yaml`; critical goal, red-card, and penalty topics preempt the normal rate limit and are not topic-deduped against one another, so every critical event can surface. Stable card IDs make retries idempotent. Normal cards are topic-deduped per match and emitted no more than once per 25 seconds from a queue capped at eight; noncritical fallback cards use this same budget. The Editor writes append-only `Card` documents to `calacat/cards`, partitioned by `match_id`, with Cosmos `id=card_id` and item TTL copied from `ttl_s`. Valid signals and candidates in their respective dead-letter queues produce deterministic templated fallback cards.
- **Why:** A bounded, reproducible editorial budget prevents a live feed from being overwhelmed, while a stable append-only card contract supports downstream push and DLQ recovery without trusting model-authored metrics or provenance.
- **How it could be wrong:** The in-memory editorial queue and deduplication state are reset on worker restart, so candidates still locked in Service Bus are redelivered but topic history is not durable; configured topic weights and relevance also need replay-based tuning.
- **Revisit when:** Multiple editor replicas or durable cross-restart topic deduplication are required, or replay evaluation shows the configured ranking obscures important stories.

## ADR-029 — Possession-scoped pass streaks
- **Decision:** A current pass streak and its evidence event IDs cover only completed passes in one uninterrupted possession. Possession-change and other event contracts that indicate lost possession or new control reset the affected team and player streaks.
- **Why:** A team must not accumulate a pass-streak signal across turnovers, and the evidence must explain exactly the current streak.
- **How it could be wrong:** Some event types such as a foul, shot, or goalkeeper action can have ambiguous possession outcomes in real football.
- **Revisit when:** Event producers provide more explicit possession outcomes or replay validation shows the interruption policy is too broad or too narrow.

## ADR-030 — Model: `gpt-5-mini` deployed as `narrator-chat`
- **Extends:** ADR-020 (East US region, low reasoning effort).
- **Decision:** Deploy `gpt-5-mini` (version 2025-08-07) in Microsoft Foundry, project `calacat-narrator`, resource group `rg-calacat`. The Foundry resource landed in **East US** (`https://calacat-narrator.cognitiveservices.azure.com/`), even though the resource group is in East US 2. Quota is the same in both, so we keep it and deploy the rest of the stack to East US too, keeping traffic in one region.
  | Parameter | Value | Why |
  |---|---|---|
  | Deployment name | `narrator-chat` | Code refers to a role, not a model, so we can swap models without code changes |
  | Deployment type | Global Standard | Pay per call, highest rate limits, no reserved capacity |
  | Version | 2025-08-07 | Newest offered for this model |
  | Auto version upgrade | Off | Behavior must not change during judging (Oct 27 – Nov 10) |
  | Rate limit | 50K tokens/min (of 500K quota) | Cost brake on the Visual Studio credit; a runaway loop can't drain it |
  | Content filter | DefaultV2 | Microsoft's standard safety guardrails stay on |
  | Spillover / PTU | Not used | Not needed at hackathon scale; PTU is expensive |
  | Auth | Entra ID (no API keys in code) | Public repo; see ADR-018 |
  | Reasoning effort (in code) | minimal / low | It's a reasoning model; low effort keeps card latency to a few seconds |
- **Why:** Agents write short, structured, multilingual cards many times per match and call MCP tools, so speed, cost, tool calling and JSON output matter more than raw intelligence. First choice `gpt-5.4-mini` failed with "Cuota insuficiente" (insufficient quota): the Visual Studio Enterprise subscription has 0 quota for it. `az cognitiveservices usage list` showed `gpt-5-mini` at 500K TPM in East US 2, Sweden Central and East US. Rejected: `gpt-5` (slower, costlier, overkill for cards), `o3-mini`/`o4-mini` (reasoning latency hurts live), and requesting `gpt-5.4-mini` quota (approval can take days).
- **How it could be wrong:** Even at minimal effort, a reasoning model may be too slow for goal cards. 50K TPM may throttle when 4 agents + Editor fire at once after a goal. Spanish quality is unverified.
- **Revisit when:** p95 card latency is over ~5 s. Then add a `gpt-4.1-mini` deployment (200K quota, non-reasoning) and point the fast agents at it. On 429 throttling, raise TPM toward 150K, especially before recording the video. If quality falls short for HT/FT recaps, add a second, larger deployment just for the recap agent.

## ADR-031 — Editorial design system adapted for a control room
- **Decision:** Base the UI on the "Agence Foudre" style reference (warm chalk canvas, forest-green text, magenta accent, condensed display type) with Antonio for display and Instrument Sans for UI. Darken the magenta to `#c0256f`, add a separate live red `#d7261e`, and drop the reference's "no cards, extreme whitespace" rules. Tokens are in `design.md`.
- **Why:** It gives a premium, recognisable look, but the original magenta fails 4.5:1 with white text and a live console needs density and an unambiguous on-air color.
- **How it could be wrong:** Pink, red and team colors can compete on one screen, and a light theme may glare in a dark gallery.
- **Revisit when:** Broadcast users ask for a dark theme, or contrast checks fail on new components.

## ADR-032 — Single-screen Reporter console with edit-in-place on the monitor
- **Decision:** The Reporter page fits one viewport: program monitor in the middle, ranked feed on the right, a fixed control bar under the monitor. There is no separate editor panel; the reporter edits, drags (free placement, center snap) and resizes the card directly on the monitor, with S/M/L presets. Card geometry is stored as percentages of the monitor.
- **Why:** The reporter works live and cannot scroll to find controls; editing where the card will appear removes a mental mapping step and frees space for a larger monitor.
- **How it could be wrong:** Small laptop screens shrink the monitor, and in-place text editing on a busy picture can be fiddly.
- **Revisit when:** Testing on 13-inch screens or with touch shows mis-hits.

## ADR-033 — Five-second cancellable go-live, and live cards are locked
- **Decision:** Go live starts a 5-second countdown (Cancel / Esc, or Go live now); only then does the card go on air and a success toast appear. A live card cannot be clicked, edited, moved or removed; the only action is Pull from air, which is immediate.
- **Why:** The countdown is a last chance to catch a mistake before it reaches viewers, while pulling is the safe action and must never be delayed. Locking prevents accidental edits to what is already broadcast.
- **How it could be wrong:** Five seconds may feel slow for a goal moment, and locking forces a pull-and-resend to fix a typo on air.
- **Revisit when:** Reporters routinely press Go live now, or ask to correct live cards.

## ADR-034 — Multiple transmissions, game filter and exclusive focus
- **Decision:** The console targets one of several outputs (demo: TV 1, TV 2, Stream), each carrying one match and holding its own on-air card. The feed can be filtered by game, and a team or player focus shows only that entity's cards.
- **Why:** Concurrent matches and parallel feeds are normal in broadcast, and a reporter covering a story needs to cut the feed down to it.
- **How it could be wrong:** An exclusive focus can hide a critical card from another team; per-output state adds complexity to the backend contract.
- **Revisit when:** Critical cards are missed under focus (then let goals bypass it), or the overlay delivery contract is designed.

## ADR-035 — Team color only in the silhouette; grey preview, red live
- **Decision:** On cards, team color appears only in the player silhouette (with jersey number) or the team shield; text, chips and borders stay neutral. Preview cards are grey with a "Preview" badge; live cards keep their colors and get a pulsing red ring and a "Live" badge.
- **Why:** One color cue per card reads cleanly and avoids clashes with the brand and live colors, while grey vs red makes the on-air state obvious at a glance. Badges keep state readable without color.
- **How it could be wrong:** Similar team palettes (two blues) lose their distinction in a small silhouette.
- **Revisit when:** Real fixtures include clashing kits; then add a second kit color or pattern.

## ADR-036 — Reporter console on Static Web Apps with a linked backend and the `reporter` role (*Superseded by ADR-043*)
- **Decision:** Host `web/` on Azure Static Web Apps with the Function App as a linked backend, so the console calls `/api/*` on its own origin (`host.json` `routePrefix` is `api`). `staticwebapp.config.json` restricts every route to a `reporter` role (built-in auth, invitations), redirects `401` to sign-in, and sets a CSP of `'self'` plus `wss://*.webpubsub.azure.com` with `frame-ancestors 'none'`. Fonts are bundled, so nothing loads from a third party. When C14 broadcasts go-live, its endpoint checks the `reporter` role in `x-ms-client-principal` itself, not just the SWA route; the public overlay (C14) gets its own anonymous route.
- **Why:** Same-origin removes CORS and per-environment API URLs. The console is an operator surface: once go-live reaches the overlay, anyone with the URL could otherwise put text on air. A strict CSP limits what injected content could reach, and self-hosted fonts keep working on locked-down broadcast networks.
- **How it could be wrong:** Linked backends need the Standard SKU, and judges need an invitation to the role. Emotion's inline styles force `style-src 'unsafe-inline'`.
- **Revisit when:** Inviting reviewers becomes friction (add a read-only demo route), or Emotion gets a CSP nonce.

## ADR-037 — Facts-only event stream; realistic simulator calibrated by fact checks
- **Decision:** The simulator acts like a camera: it emits only observable facts (who, where, when, outcome, speed, body part). Derived opinions such as `xg`, pass `difficulty` and `inside_opp_shape` are removed from event payloads and are either computed downstream by the Interpreter or dropped. The simulator may still use internal probabilities to decide outcomes, but never emits them. Realism fixes: the ball can move backwards; incomplete passes and passes out of play hand possession to the opponent (throw-in or corner); shot frequency depends on distance; kickoff goes to the conceding team; a foul in the box can become a penalty; a goalkeeper save follows only `saved` shots. Unit checks over ~20 seeds × 90 min: 2.2–3.4 goals/match (none above 8), 18–32 shots/match, ≥150 possession changes/match, ≥1 penalty across seeds, same seed gives the same match, every event passes its schema. Amends ADR-002 and the payload table in data-model.md.
- **Why:** Measured over 20 seeds, the simulator produced 20.3 goals, 83 shots and 0.38 mean xG per shot per match, against real values of about 2.8, 25 and 0.10. Goal cards drowned out everything else, and the `penalty` signal could never fire. Keeping the stream to pure facts separates "what happened" from "what it means", which is the Interpreter's and the agents' job and is easier to test.
- **How it could be wrong:** Dropping `difficulty` and `inside_opp_shape` loses the brief's "pass difficulty rating" unless the Interpreter recomputes it from positions. Calibrating to averages can still produce dull or odd individual matches.
- **Revisit when:** Pass-quality cards are needed for the demo (then compute difficulty in the Interpreter from distance, pressure and positions), or the checks pass but replays still look unrealistic.

## ADR-038 — Specialists query a facts tool and return structured JSON
- **Decision:** Specialists no longer receive raw signal JSON in the prompt. Each one gets a single function tool, `get_event_facts`, that returns human-readable facts built in code from the catalog and match state: minute and half, team and opponent names, player name, score after the event, what happened, and speed/body part as phrases. No IDs and no internal field names. The model returns `{headline ≤60, description ≤180, player_id, team_id, salience}`. The application attaches signal, evidence and metrics, so the model can't change provenance. A validator rejects snake_case tokens, IDs and words like `match_clock` or `evidence`; a rejected draft goes through the existing retry/fallback path. The tool starts in-process and can later move into the MCP server (ADR-009) without changing the agents.
- **Why:** Live cards read like debug output ("PERIOD 2 GOAL (MATCH_CLOCK_S 3741)") because the model only saw field names and wasn't allowed to use names. An agent that queries for context matches the intended event-driven design: wake on a signal, look up the facts, write. The length limits match the console (60/180), so nothing gets truncated.
- **Latency trade-off (decided, PR #64 review):** The facts are fully known in code before the call, so putting them in the prompt would cost one model call instead of two (call `get_event_facts`, then write), and with the ADR-039 Reviewer a goal goes through three sequential calls. We keep the tool anyway: querying for context is the agent behaviour this design is meant to show, and it lets the facts source move into the MCP server (ADR-009) unchanged. The call is **forced** (`tool_choice` = required, `get_event_facts`), so the model can never caption without the facts; agent_framework resets a required tool choice after the first round, so it can't loop. Goal latency is bounded downstream instead: critical topics get a shorter Reviewer timeout and fall back to the deterministic template (ADR-039).
- **How it could be wrong:** Two sequential calls plus the Reviewer can exceed the 5 s goal → card budget under load or 429s; then most critical cards arrive as templates rather than specialist text.
- **Revisit when:** Measured goal → card p95 goes over ~5 s in the D1 smoke test (then pass the facts in the prompt for critical topics only, keeping the tool for the rest), or the MCP server lands.

## ADR-039 — Editor = code budget, then a Reviewer agent (approve / revise / reject)
- **Decision:** The Editor keeps its deterministic salience, rate limit, TTL and dedupe (ADR-008). A candidate that wins a slot then goes to a **Reviewer** agent, which returns `approve | revise | reject` with final text that must obey the same schema and validator. A timeout, error or invalid output publishes the existing templated fallback card; a reject drops a non-critical card and frees the slot, but a **critical** card (goal, red card, penalty) is never dropped: a reject publishes its template instead (PR #65 review). Critical reviews use a shorter timeout (`critical_review_timeout_s`, 3 s vs 10 s) so a goal stays within the ~5 s budget after the two specialist calls (ADR-038). Only reviewed or fallback cards are stored and pushed.
- **Why:** It's a real second agent with a distinct role (critic/editor) and a handoff, and the system recovers when it fails, which is what the Multi-Agent category judges. Running it only after the budget limits calls to about one every 20–30 s, keeping cost and latency low.
- **How it could be wrong:** It adds a model call before every card, which could delay goal cards. The Reviewer could reject too often and leave the feed empty. Reviews run inline in the single Editor loop and share the `narrator-chat` TPM quota with the specialists, so a slow review or a burst of 429s holds back other routes or turns cards into templates.
- **Revisit when:** Goal cards take more than ~5 s (then skip review for critical topics and review afterwards), the reject rate goes over ~30%, or reviews visibly stall the loop (then give the Reviewer its own deployment or raised TPM, and run reviews as `asyncio` tasks that settle their message when done).

## ADR-040 — Translation happens in the Reviewer call; cards carry EN + ES
- **Decision:** English is the canonical card language. When the Reviewer approves or revises, the same call also returns Spanish text, stored as `i18n.es = {headline, description}` in the card. The UI picks the viewer's language, and audio mode reads the same field. Names, numbers and the minute come from the facts tool, and the validator checks the translated text too. Fallback cards use templates in both languages. Supersedes accessibility.md's "agent writes natively in each target language" for the MVP.
- **Why:** It costs one call for both review and translation, with no extra service or on-demand endpoint, and the card arrives at the UI ready in both languages over the existing Web PubSub push.
- **How it could be wrong:** Each extra language makes the Reviewer output bigger and slower. Spanish quality from `gpt-5-mini` is unverified (ADR-030).
- **Revisit when:** A third language is needed (then add an on-demand Azure AI Translator function with a per-(card, lang) cache), or a native speaker flags quality problems.

## ADR-041 — Cards carry `player_id`; the UI resolves player images
- **Decision:** Cards include `player_id` and `team_id`, never an image URL. The UI renders the existing team-colored silhouette with the jersey number (ADR-035). If a generated avatar exists at `web/public/players/{player_id}.png`, served by the Static Web App CDN, it is shown instead, with a text alternative. No real photos, because players are fictional (ADR-006). Azure Blob Storage, Azure's equivalent of S3, is not used for now.
- **Why:** It keeps event payloads small and stable, and the place images are stored can change without changing the card contract. Static images need no extra Azure resource, and the silhouette already works.
- **How it could be wrong:** Generated avatars can look uncanny or inconsistent, and adding images later means a UI deploy.
- **Revisit when:** Images become dynamic or user-uploaded (then use a Blob Storage container behind the CDN).

## ADR-042 — Final-day order and cut line
- **Decision:** The order on Oct 26–27 is: (1) facts-only, realistic simulator with unit checks; (2) facts tool + structured agent JSON + stricter schema; (3) Reviewer + Spanish, then a single full `azd deploy`; (4) UI shows player, team, minute, avatar and an EN/ES switch; (5) "Kick off a match" in Azure (C16); (6) README, video under 2 min, public repo, submit by Oct 27 noon PT. If time runs short, cut step 5 first: the demo match is started from a laptop for the video, and the README tells judges how to run the simulator themselves.
- **Why:** About one working day remains. Steps 1–3 fix what judges will see in every card, and step 6 can't slip.
- **How it could be wrong:** Without step 5, judges who don't run the simulator see an empty feed (Rule 4.8).
- **Revisit when:** Steps 1–4 are done before Oct 27 morning PT; then do step 5.

## ADR-043 — Reporter console on GitHub Pages: a receive-only demo with no sign-in
- **Decision:** Host `web/` on **GitHub Pages** at `https://thiago-whatever.github.io/calacat-narrator/`, built and published by a GitHub Actions workflow. Vite `base` is `/calacat-narrator/`, `VITE_API_BASE_URL` points at the Function App's `/api` at build time, and the Function App allows that origin through CORS. The console is a **receive-only** frontend:
  - **One shared feed.** Every open browser gets the same cards from the backend: the read endpoints `/cards` and `/negotiate`, then the Web PubSub push. There are no per-user sessions or isolation in the backend.
  - **Nothing is sent back.** There are no edit, go-live or write endpoints. Selecting, editing, previewing and "going live" with a card (ADR-032, ADR-033) happen only in that browser's memory, aren't visible to anyone else, and reset on refresh.
  - **The overlay is local too.** It's shown inside the console page (or another tab of the same browser). An external program such as OBS can't see a browser-local go-live.
  - **No authentication or authorization**, and no `reporter` role; `staticwebapp.config.json` is dropped. Security headers are reduced to what a `<meta>` CSP can express.
  - **Later (not in the MVP):** the only write the UI may gain is "start a simulation if none is running" (C16).
  - The README and the submission's testing instructions say clearly that this is a demo build, not a production broadcast tool.

  Supersedes ADR-036.
- **Why:** Judges are anonymous: we can't invite them to a role or send them credentials, and Rule 4.8 asks for free, unrestricted access. With no write path, an open link can't change what anyone else sees, so sign-in isn't needed to keep the demo safe. GitHub Pages is free, needs no extra Azure resource, and the publish workflow is visible GitHub evidence.
- **How it could be wrong:**
  - The read API is public and callable cross-origin, so anyone can read the demo's fictional cards (acceptable for a demo).
  - Without real response headers there's no `frame-ancestors` or similar protection.
  - Because go-live is local, the overlay can't drive a separate broadcast tool, so "on air" in the demo is a simulation of the workflow.
  - Free Pages requires the repo to be public.
- **Revisit when:**
  - The project is used beyond the hackathon or for real broadcast: then add a server-side go-live/overlay channel behind operator sign-in (Entra ID in the SPA, App Service authentication and a role check on every write endpoint).
  - C16 adds "start a simulation": then that endpoint needs a running-match check and a rate limit, since it's the first anonymous write.

## ADR-044 — Judge-started matches run in a queue-triggered Function
- **Decision:** `POST /api/matches` checks the caps, then puts `{seed, speed}` on the `match-kickoffs` queue in the Function App's own storage account. A queue-triggered function in the same Function App plays the match into Event Hubs. The caps are Cosmos documents with ETag-conditional writes: two running-match slots, released when the match's expected end time (90 min ÷ speed + 1 min) passes, and a counter of 20 matches per UTC day. The server picks the seed; the caller can only choose a speed from 5 to 20 (default 10). The queue doesn't retry a run (`maxDequeueCount: 1`).
- **Why:** The HTTP response must return immediately while a 10× match runs for 9 minutes. Flex Consumption allows a non-HTTP function to run 30 minutes by default, enough for the slowest allowed speed (18 min). The Function App already has queue access through its identity, so this needs no new resource, image, role or dependency. A Container Apps job would need its own image settings, and starting it would need an ARM role and a management SDK.
- **How it could be wrong:**
  - If the instance is recycled mid-match, the match stops and its slot stays taken until the expected end.
  - The slots only measure time, so a match that finishes early still holds its slot until then.
  - A request that loses the race for a slot after the daily count went up still counts against the day.
  - This is the first anonymous write: anyone can use up the day's 20 matches.
- **Revisit when:** Matches need to survive restarts, or the daily cap is regularly hit by abuse. Then use a Durable Functions orchestration or a Container Apps job, and add a per-client rate limit.


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

## ADR-029 — Possession-scoped pass streaks
- **Decision:** A current pass streak and its evidence event IDs cover only completed passes in one uninterrupted possession. Possession-change and other event contracts that indicate lost possession or new control reset the affected team and player streaks.
- **Why:** A team must not accumulate a pass-streak signal across turnovers, and the evidence must explain exactly the current streak.
- **How it could be wrong:** Some event types such as a foul, shot, or goalkeeper action can have ambiguous possession outcomes in real football.
- **Revisit when:** Event producers provide more explicit possession outcomes or replay validation shows the interruption policy is too broad or too narrow.

# Architecture

Event-driven pipeline. Stats are computed **deterministically** in code. LLM agents run only when a threshold-gated **signal** fires, and they write the *why*. The numbers always come from tools, never from the model.

```mermaid
flowchart LR
  SIM[Simulator<br/>Container Apps] -->|HTTPS POST| ING[/ingest<br/>Function HTTP/]
  ING --> EH[(Event Hubs)]
  EH -->|Capture| LAKE[(ADLS Gen2<br/>raw lake)]
  EH --> INT[Interpreter<br/>Function]
  INT --> COS[(Cosmos DB<br/>state · aggregates)]
  INT -->|signals| SB{{Service Bus signals topic<br/>filtered subscriptions}}
  SB --> A1[Goal & Shot specialist]
  SB --> A2[Build-up & Passing]
  SB --> A3[Tactical]
  SB --> A4[Player / Milestones]
  A1 & A2 & A3 & A4 -.MCP tools.-> MCP[match-stats<br/>MCP server] -.-> COS
  A1 -->|candidates| CT{{Candidates topic}}
  CT --> ED[Editor subscription]
  A2[Build-up & Passing] --> CT
  A3[Tactical] --> CT
  A4[Player / Milestones] --> CT
  SB -->|DLQ| ED
  ED --> CARDS[(Cosmos cards)]
  CARDS -->|change feed| PUB[Web PubSub]
  PUB --> UI[Reporter · Overlay · Fan<br/>GitHub Pages]
  UI --> PER[Personalizer<br/>lang · depth · focus · TTS]
```

## AWS → Azure mapping
| AWS (original idea) | Azure | Difference worth knowing |
|---|---|---|
| Data-generating agent | Simulator on **Container Apps** | Deterministic and seeded instead of LLM-driven (ADR-002) |
| API Gateway | **Functions HTTP trigger** | APIM is the true equivalent but overkill here (ADR-010) |
| Kinesis Data Streams | **Event Hubs** | Kafka-compatible; partitions + consumer groups like shards + consumers |
| Firehose → S3 | **Event Hubs Capture → ADLS Gen2** | Built-in, no code; Avro files |
| "S3 for NoSQL" | **Cosmos DB** (serverless) | S3 ≈ ADLS (lake). NoSQL serving is a separate store. |
| Lambda | **Azure Functions** | Same model; Event Hub trigger ≈ Kinesis trigger |
| SNS + filter policies | **Service Bus topics + SQL filters** | Adds dead-letter queues and sessions; Event Grid is the lighter alternative (ADR-004) |
| Agents (unspecified) | **Microsoft Agent Framework** + **Foundry** models | Foundry gives model hosting, tracing, evals |
| WebSocket push | **Web PubSub** | ≈ API Gateway WebSocket APIs |
| Static site | **GitHub Pages** (not Azure) | Azure equivalent would be Static Web Apps ≈ S3 + CloudFront / Amplify; Pages chosen for an open demo (ADR-043) |
| Polly | **AI Speech** | Neural TTS in many languages |
| CloudFormation/CDK | **Bicep + azd** | `azd up` provisions and deploys |

## Agents
| Agent | Subscribes to | Produces |
|---|---|---|
| Goal & Shot | `goal`, `shot_volume`, `penalty` | Chance quality, shot speed, goal timing context |
| Build-up & Passing | `pass_streak`, `pass_milestone`, `progression` | Passing sequences and who kept the ball |
| Tactical | `pressure_shift`, `attack_side_shift`, `rhythm_change` | Control vs chaos, point-of-attack changes, fullback inversion |
| Player / Milestones | `speed_threshold`, `distance_threshold`, `record` | Player tagging, records |
| Editor | all candidates + DLQ | Ranked, deduped, rate-limited cards; HT/FT recap trigger |

**Candidate schema:** `{candidate_id, signal_id, match_id, headline, why_it_matters, metrics{}, evidence_event_ids[], entity_ids[], topic, self_salience, ttl_s, match_clock_s}`. Each specialist Container App consumes its configured filtered subscription and publishes candidates for the Editor.

## Failure handling
- Each signal has a delivery timeout. After max retries it goes to the **DLQ**.
- The Editor watches the DLQ and emits a **templated deterministic card** ("Goal — Rivas, 67', 104 km/h"), so the feed never goes silent.
- Agent health (last heartbeat, error rate) is shown on the **Control room** page.
- Traces go to Application Insights / Foundry tracing.

## Editor budget (see ADR-008)
`salience = event_weight × rarity × recency_decay × relevance(focus)`. The Editor computes this from its packaged `data/editor.yaml`; the specialist's `self_salience` is not treated as evidence or used to override the configured score. Critical topics preempt the normal budget and are not deduped against other critical events, so successive goals remain visible; stable card IDs suppress their retries. Otherwise at most 1 card per 20–30 s is persisted, from a ranked queue of 6–8, with a TTL of 2–3 min and topic deduplication per match. Noncritical fallback cards share the same budget; critical fallback cards preempt it. The Editor consumes the `candidates/editor` subscription plus its DLQ and the dead-letter subqueues of signal subscriptions. Valid dead-lettered signals or candidates become deterministic, templated fallback cards with their original evidence IDs and verified metrics; malformed dead-letter payloads are logged and completed rather than narrated.

The `calacat/cards` Cosmos container is partitioned by `/match_id` and has TTL enabled. A card is stored as its complete JSON contract, with Cosmos `id` equal to `card_id` and per-document `ttl` equal to `ttl_s`. Writes are append-only (`create_item`); a repeated card ID is treated as an already-persisted retry, not an update. Downstream push consumers should filter on `expires_at`, since Cosmos TTL deletion is not a card-publication event. Web PubSub can group clients by `match-{match_id}` and clients should deduplicate on `card_id`.

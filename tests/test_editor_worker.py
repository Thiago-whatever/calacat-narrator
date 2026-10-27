import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from azure.cosmos.exceptions import CosmosResourceExistsError

from calacat_narrator import editor_worker
from calacat_narrator.agent_runtime import Candidate, Card, LocalizedCaption, ReviewDecision
from calacat_narrator.cosmos import persist_card
from calacat_narrator.editor import Editor, EditorConfig, fallback_card
from calacat_narrator.signals import Signal


def candidate_json() -> bytes:
    return (
        Candidate(
            candidate_id="candidate-1",
            signal_id="signal-1",
            match_id="m-0007",
            headline="A passing update",
            why_it_matters="The team reached five shots.",
            metrics={"shot_volume": 5},
            evidence_event_ids=["evt-1"],
            entity_ids=["t-home"],
            team_id="t-home",
            topic="shot_volume",
            self_salience=0.8,
            match_clock_s=1000,
        )
        .model_dump_json()
        .encode()
    )


def signal_json() -> bytes:
    return (
        Signal(
            signal_id="signal-1",
            match_id="m-0007",
            kind="goal",
            match_clock_s=4020,
            entity={"team_id": "t-home"},
            value=1,
            evidence_event_ids=["evt-1"],
            tier=1,
        )
        .model_dump_json()
        .encode()
    )


class FakeMessage:
    message_id = "message-1"

    def __init__(self, body: bytes) -> None:
        self.body = body


class FakeReceiver:
    def __init__(self) -> None:
        self.completed: list[FakeMessage] = []
        self.abandoned: list[FakeMessage] = []
        self.dead_lettered: list[tuple[FakeMessage, str]] = []

    async def complete_message(self, message: FakeMessage) -> None:
        self.completed.append(message)

    async def abandon_message(self, message: FakeMessage) -> None:
        self.abandoned.append(message)

    async def dead_letter_message(
        self,
        message: FakeMessage,
        *,
        reason: str,
        error_description: str,
    ) -> None:
        assert error_description
        self.dead_lettered.append((message, reason))


class FakeContainer:
    def __init__(self, error: Exception | None = None) -> None:
        self.documents = []
        self.error = error

    def create_item(self, *, body: dict[str, object]) -> None:
        if self.error is not None:
            raise self.error
        self.documents.append(body)


def test_card_cosmos_document_uses_card_id_ttl_and_create_only() -> None:
    card = fallback_card(
        Signal.model_validate_json(signal_json()),
        EditorConfig.load(),
        now=datetime(2026, 10, 25, tzinfo=UTC),
    )
    container = FakeContainer()

    assert persist_card(container, card)
    assert container.documents[0]["id"] == card.card_id
    assert container.documents[0]["card_id"] == card.card_id
    assert container.documents[0]["ttl"] == card.ttl_s
    assert container.documents[0]["evidence_event_ids"] == ["evt-1"]

    container.error = CosmosResourceExistsError()
    assert not persist_card(container, card)
    assert len(container.documents) == 1


def test_candidate_is_held_until_queued_card_can_be_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receiver = FakeReceiver()
    message = FakeMessage(candidate_json())
    editor = Editor(EditorConfig.load())
    pending = {}
    now = datetime(2026, 10, 25, tzinfo=UTC)

    asyncio.run(
        editor_worker.process_candidate_message(
            receiver,
            message,
            editor,
            pending,
            now=now,  # type: ignore[arg-type]
        )
    )

    assert receiver.completed == []
    assert pending["candidate-1"] == (receiver, message)
    assert editor.peek_due(now=now) is not None


def test_critical_candidate_is_completed_only_after_card_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receiver = FakeReceiver()
    message = FakeMessage(
        candidate_json().replace(b"shot_volume", b"goal").replace(b"candidate-1", b"candidate-goal")
    )
    container = FakeContainer()
    monkeypatch.setattr(editor_worker, "get_cards_container", lambda: container)
    editor = Editor(EditorConfig.load())

    asyncio.run(
        editor_worker.process_candidate_message(
            receiver,
            message,
            editor,
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )
    )

    assert len(container.documents) == 1
    assert receiver.completed == [message]
    assert receiver.abandoned == []


def test_deadletter_signal_persists_fallback_before_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receiver = FakeReceiver()
    message = FakeMessage(signal_json())
    container = FakeContainer()
    monkeypatch.setattr(editor_worker, "get_cards_container", lambda: container)

    asyncio.run(
        editor_worker.process_deadletter_message(
            receiver,
            message,
            Editor(EditorConfig.load()),
            EditorConfig.load(),
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )
    )

    assert len(container.documents) == 1
    assert container.documents[0]["source"] == "fallback"
    assert receiver.completed == [message]


def test_deadletter_signal_is_abandoned_when_fallback_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receiver = FakeReceiver()
    message = FakeMessage(signal_json())
    container = FakeContainer(RuntimeError("Cosmos unavailable"))
    monkeypatch.setattr(editor_worker, "get_cards_container", lambda: container)

    asyncio.run(
        editor_worker.process_deadletter_message(
            receiver,
            message,
            Editor(EditorConfig.load()),
            EditorConfig.load(),
            {},
        )
    )

    assert receiver.abandoned == [message]
    assert receiver.completed == []


def test_deadletter_candidate_is_replaced_with_template_card() -> None:
    receiver = FakeReceiver()
    message = FakeMessage(candidate_json())
    config = EditorConfig.load()
    editor = Editor(config)
    now = datetime(2026, 10, 25, tzinfo=UTC)
    existing = Candidate.model_validate_json(
        candidate_json().replace(b"shot_volume", b"pass_streak")
    )
    editor.submit(existing, now=now)
    first_card = editor.peek_due(now=now)
    assert first_card is not None
    editor.mark_published(first_card.candidate_id, now=now)
    pending = {}

    asyncio.run(
        editor_worker.process_candidate_deadletter_message(
            receiver,
            message,
            editor,
            config,
            pending,
            now=now + timedelta(seconds=1),
        )
    )

    assert receiver.completed == []
    assert len(pending) == 1
    assert editor.peek_due(now=now + timedelta(seconds=24)) is None
    card = editor.peek_due(now=now + timedelta(seconds=25))
    assert card is not None
    assert card.source == "fallback"
    assert card.candidate_id in pending
    assert card.candidate_id != "candidate-1"
    assert card.signal_id == "signal-1"
    assert card.evidence_event_ids == ["evt-1"]
    assert "Northbridge Comets have now taken 5 shots" in card.body


def test_editor_worker_settings_require_candidate_and_dlq_routes() -> None:
    settings = editor_worker.EditorWorkerSettings.from_environment(
        {
            "SERVICEBUS_FULLY_QUALIFIED_NAMESPACE": "example.servicebus.windows.net",
            "SERVICEBUS_CANDIDATES_TOPIC_NAME": "candidates",
            "SERVICEBUS_EDITOR_SUBSCRIPTION_NAME": "editor",
            "SERVICEBUS_TOPIC_NAME": "signals",
            "EDITOR_DEADLETTER_SUBSCRIPTIONS": "goal-shot, buildup-passing",
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/p",
            "FOUNDRY_MODEL": "narrator-chat",
        }
    )

    assert settings.deadletter_subscriptions == ("goal-shot", "buildup-passing")
    assert settings.foundry_model == "narrator-chat"
    with pytest.raises(RuntimeError, match="EDITOR_DEADLETTER_SUBSCRIPTIONS"):
        editor_worker.EditorWorkerSettings.from_environment(
            {
                "SERVICEBUS_FULLY_QUALIFIED_NAMESPACE": "example.servicebus.windows.net",
                "SERVICEBUS_CANDIDATES_TOPIC_NAME": "candidates",
                "SERVICEBUS_EDITOR_SUBSCRIPTION_NAME": "editor",
                "SERVICEBUS_TOPIC_NAME": "signals",
            }
        )


def test_stored_card_is_pushed_and_a_failed_push_still_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = FakeContainer()
    monkeypatch.setattr(editor_worker, "get_cards_container", lambda: container)
    pushed: list[str] = []

    def failing_push(cards: list) -> None:
        pushed.extend(card.card_id for card in cards)
        raise RuntimeError("Web PubSub down")

    monkeypatch.setattr(editor_worker, "publish_cards", failing_push)
    receiver = FakeReceiver()
    message = FakeMessage(
        candidate_json().replace(b"shot_volume", b"goal").replace(b"candidate-1", b"candidate-goal")
    )

    asyncio.run(
        editor_worker.process_candidate_message(
            receiver,
            message,
            Editor(EditorConfig.load()),
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )
    )

    assert len(container.documents) == 1
    assert pushed == [container.documents[0]["id"]]
    assert receiver.completed == [message]


class RejectingReviewer:
    async def review(self, card, facts):
        return ReviewDecision(
            decision="reject",
            headline=card.headline,
            body=card.body,
            es=LocalizedCaption(headline="Sin novedad", body="Nada que contar."),
        )


def goal_candidate_message() -> FakeMessage:
    return FakeMessage(
        candidate_json().replace(b"shot_volume", b"goal").replace(b"candidate-1", b"candidate-goal")
    )


def test_rejected_goal_still_publishes_the_template(monkeypatch: pytest.MonkeyPatch) -> None:
    receiver, message, container = FakeReceiver(), goal_candidate_message(), FakeContainer()
    monkeypatch.setattr(editor_worker, "get_cards_container", lambda: container)
    monkeypatch.setattr(editor_worker, "publish_cards", lambda cards: None)

    asyncio.run(
        editor_worker.process_candidate_message(
            receiver,
            message,
            Editor(EditorConfig.load()),
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
            reviewer=RejectingReviewer(),
        )
    )

    # A goal must never vanish because the Reviewer called it not newsworthy.
    assert [document["source"] for document in container.documents] == ["fallback"]
    assert container.documents[0]["i18n"]["es"]["body"]
    assert receiver.completed == [message]


def test_rejected_non_critical_card_is_not_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(editor_worker, "get_cards_container", lambda: container)
    card = Card.from_candidate(
        Candidate.model_validate_json(candidate_json()),
        created_at=datetime(2026, 10, 25, tzinfo=UTC),
    )

    stored = asyncio.run(
        editor_worker._review_and_store(card, Editor(EditorConfig.load()), RejectingReviewer())
    )

    # Not stored, so _settle leaves the publish slot free for the next card.
    assert stored is False
    assert container.documents == []


@pytest.mark.parametrize(
    ("topic", "field"), [("goal", "critical_review_timeout_s"), ("shot_volume", "review_timeout_s")]
)
def test_critical_cards_get_the_shorter_review_timeout(
    monkeypatch: pytest.MonkeyPatch, topic: str, field: str
) -> None:
    seen: dict[str, object] = {}

    async def spy(card, reviewer, *, timeout_s, critical_topics):
        seen.update(timeout_s=timeout_s, critical_topics=critical_topics)

    monkeypatch.setattr(editor_worker, "review_card", spy)
    config = EditorConfig.load()
    body = candidate_json().replace(b"shot_volume", topic.encode())
    card = Card.from_candidate(
        Candidate.model_validate_json(body), created_at=datetime(2026, 10, 25, tzinfo=UTC)
    )

    asyncio.run(editor_worker._review_and_store(card, Editor(config), RejectingReviewer()))

    assert seen == {"timeout_s": getattr(config, field), "critical_topics": config.critical_topics}
    assert config.critical_review_timeout_s < config.review_timeout_s


def test_every_stored_card_carries_spanish(monkeypatch: pytest.MonkeyPatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(editor_worker, "get_cards_container", lambda: container)
    monkeypatch.setattr(editor_worker, "publish_cards", lambda cards: None)

    asyncio.run(
        editor_worker.process_candidate_message(
            FakeReceiver(),
            goal_candidate_message(),
            Editor(EditorConfig.load()),
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )
    )

    assert container.documents
    assert all(document["i18n"]["es"]["body"] for document in container.documents)


def unknown_team_signal_json() -> bytes:
    # Passes the EntityId pattern but isn't in the catalog: the poison message from review.
    return signal_json().replace(b'"t-home"', b'"t-ghost"')


def test_unknown_team_in_dlq_is_completed_instead_of_crashing_the_editor() -> None:
    receiver = FakeReceiver()
    message = FakeMessage(unknown_team_signal_json())

    asyncio.run(
        editor_worker.process_message(
            receiver,
            "signal_dlq",
            message,
            Editor(EditorConfig.load()),
            EditorConfig.load(),
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )
    )

    # A DLQ message can't be dead-lettered again, so completing it is the only way out.
    assert receiver.completed == [message]
    assert receiver.dead_lettered == []


@pytest.mark.parametrize(
    ("route", "processor"),
    [
        ("candidate", "process_candidate_message"),
        ("signal_dlq", "process_deadletter_message"),
        ("candidate_dlq", "process_candidate_deadletter_message"),
    ],
)
def test_any_processing_error_settles_the_message(
    monkeypatch: pytest.MonkeyPatch, route: str, processor: str
) -> None:
    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(editor_worker, processor, boom)
    receiver = FakeReceiver()
    message = FakeMessage(b"{}")

    asyncio.run(
        editor_worker.process_message(
            receiver,
            route,
            message,
            Editor(EditorConfig.load()),
            EditorConfig.load(),
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )
    )

    if route == "candidate":
        assert receiver.dead_lettered == [(message, "EditorError")]
    else:
        assert receiver.completed == [message]


def test_settle_failure_is_logged_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected")

    class LostLockReceiver(FakeReceiver):
        async def complete_message(self, message: FakeMessage) -> None:
            raise RuntimeError("lock lost")

    monkeypatch.setattr(editor_worker, "process_deadletter_message", boom)

    asyncio.run(
        editor_worker.process_message(
            LostLockReceiver(),
            "signal_dlq",
            FakeMessage(b"{}"),
            Editor(EditorConfig.load()),
            EditorConfig.load(),
            {},
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )
    )

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from azure.cosmos.exceptions import CosmosResourceExistsError

from calacat_narrator import editor_worker
from calacat_narrator.agent_runtime import Candidate
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
            receiver, message, editor, pending, now=now  # type: ignore[arg-type]
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
        candidate_json()
        .replace(b"shot_volume", b"goal")
        .replace(b"candidate-1", b"candidate-goal")
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
    assert "verified shot_volume is 5" in card.body


def test_editor_worker_settings_require_candidate_and_dlq_routes() -> None:
    settings = editor_worker.EditorWorkerSettings.from_environment(
        {
            "SERVICEBUS_FULLY_QUALIFIED_NAMESPACE": "example.servicebus.windows.net",
            "SERVICEBUS_CANDIDATES_TOPIC_NAME": "candidates",
            "SERVICEBUS_EDITOR_SUBSCRIPTION_NAME": "editor",
            "SERVICEBUS_TOPIC_NAME": "signals",
            "EDITOR_DEADLETTER_SUBSCRIPTIONS": "goal-shot, buildup-passing",
        }
    )

    assert settings.deadletter_subscriptions == ("goal-shot", "buildup-passing")
    with pytest.raises(RuntimeError, match="EDITOR_DEADLETTER_SUBSCRIPTIONS"):
        editor_worker.EditorWorkerSettings.from_environment(
            {
                "SERVICEBUS_FULLY_QUALIFIED_NAMESPACE": "example.servicebus.windows.net",
                "SERVICEBUS_CANDIDATES_TOPIC_NAME": "candidates",
                "SERVICEBUS_EDITOR_SUBSCRIPTION_NAME": "editor",
                "SERVICEBUS_TOPIC_NAME": "signals",
            }
        )

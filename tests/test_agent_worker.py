import asyncio

import pytest

from calacat_narrator import agent_worker
from calacat_narrator.agent_runtime import Candidate
from calacat_narrator.agent_worker import WorkerSettings, consume_signals, process_signal_message
from calacat_narrator.signals import Signal


def signal_json() -> bytes:
    return (
        Signal(
            signal_id="82808bb1-7817-51a4-8a04-cdff8dc5d04e",
            match_id="m-0007",
            kind="goal",
            match_clock_s=4020,
            entity={"team_id": "t-home"},
            value=2,
            evidence_event_ids=["evt-0042"],
            tier=1,
        )
        .model_dump_json()
        .encode()
    )


class FakeMessage:
    message_id = "signal-message-1"

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


class FakeSender:
    def __init__(self, error: Exception | None = None) -> None:
        self.messages = []
        self.error = error

    async def send_messages(self, message) -> None:
        if self.error is not None:
            raise self.error
        self.messages.append(message)


class FakeGenerator:
    async def create_candidate(self, signal: Signal) -> Candidate:
        return Candidate(
            candidate_id="b6bb4751-38fc-57ae-b4f4-2635502b9ec4",
            signal_id=signal.signal_id,
            match_id=signal.match_id,
            headline="Goal",
            why_it_matters="The home team scores.",
            metrics={"goal": signal.value},
            evidence_event_ids=signal.evidence_event_ids,
            entity_ids=list(signal.entity.values()),
            topic=signal.kind,
            self_salience=1,
            match_clock_s=signal.match_clock_s,
        )


def test_consumer_publishes_before_completing_signal() -> None:
    receiver = FakeReceiver()
    sender = FakeSender()
    message = FakeMessage(signal_json())

    asyncio.run(process_signal_message(receiver, sender, message, FakeGenerator()))  # type: ignore[arg-type]

    assert len(sender.messages) == 1
    assert sender.messages[0].message_id == "b6bb4751-38fc-57ae-b4f4-2635502b9ec4"
    assert sender.messages[0].content_type == "application/json"
    assert receiver.completed == [message]
    assert receiver.abandoned == []


def test_consumer_dead_letters_invalid_signals_without_invoking_agent() -> None:
    receiver = FakeReceiver()
    sender = FakeSender()
    message = FakeMessage(b'{"not":"a signal"}')

    asyncio.run(process_signal_message(receiver, sender, message, FakeGenerator()))  # type: ignore[arg-type]

    assert receiver.dead_lettered == [(message, "InvalidSignal")]
    assert receiver.completed == []
    assert sender.messages == []


def test_consumer_abandons_message_when_candidate_publish_fails() -> None:
    receiver = FakeReceiver()
    sender = FakeSender(RuntimeError("Service Bus unavailable"))
    message = FakeMessage(signal_json())

    asyncio.run(process_signal_message(receiver, sender, message, FakeGenerator()))  # type: ignore[arg-type]

    assert receiver.abandoned == [message]
    assert receiver.completed == []


def test_consumer_renews_message_lock_during_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    class StopLoop(Exception):
        pass

    class OneMessageReceiver(FakeReceiver):
        received = False

        async def receive_messages(self, *, max_message_count: int, max_wait_time: int):
            assert max_message_count == 1
            assert max_wait_time == 5
            if self.received:
                raise StopLoop
            self.received = True
            return [message]

    class FakeAutoLockRenewer:
        instance = None

        def __init__(self, *, max_lock_renewal_duration: int) -> None:
            self.max_lock_renewal_duration = max_lock_renewal_duration
            self.registrations = []
            FakeAutoLockRenewer.instance = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback) -> None:
            return None

        def register(self, registered_receiver, registered_message) -> None:
            self.registrations.append((registered_receiver, registered_message))

    receiver = OneMessageReceiver()
    sender = FakeSender()
    message = FakeMessage(signal_json())
    monkeypatch.setattr(agent_worker, "AutoLockRenewer", FakeAutoLockRenewer)

    with pytest.raises(StopLoop):
        asyncio.run(consume_signals(receiver, sender, FakeGenerator()))  # type: ignore[arg-type]

    assert FakeAutoLockRenewer.instance.max_lock_renewal_duration == 300
    assert FakeAutoLockRenewer.instance.registrations == [(receiver, message)]
    assert receiver.completed == [message]


def test_worker_settings_require_all_runtime_endpoints() -> None:
    with pytest.raises(RuntimeError, match="FOUNDRY_PROJECT_ENDPOINT"):
        WorkerSettings.from_environment({})


def test_worker_settings_read_all_required_environment_variables() -> None:
    settings = WorkerSettings.from_environment(
        {
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/demo",
            "FOUNDRY_MODEL": "narrator-chat",
            "SERVICEBUS_FULLY_QUALIFIED_NAMESPACE": "example.servicebus.windows.net",
            "SERVICEBUS_TOPIC_NAME": "signals",
            "SERVICEBUS_SUBSCRIPTION_NAME": "goal-shot",
            "SERVICEBUS_CANDIDATES_TOPIC_NAME": "candidates",
            "AGENT_NAME": "goal-shot",
        }
    )

    assert settings.foundry_model == "narrator-chat"
    assert settings.signals_subscription == "goal-shot"

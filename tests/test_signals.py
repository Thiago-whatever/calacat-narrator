from datetime import UTC, datetime

import function_app
from calacat_narrator.interpreter import EntityAggregate, MatchState, apply_event
from calacat_narrator.schemas import MatchEvent
from calacat_narrator.servicebus import publish_signals
from calacat_narrator.signals import evaluate_signals, load_signal_rules


def make_event(
    seq: int,
    event_type: str,
    payload: dict[str, object],
    *,
    clock_s: int = 600,
    team_id: str | None = "t-home",
    player_id: str | None = "p-nbr-10",
) -> MatchEvent:
    return MatchEvent.model_validate(
        {
            "event_id": f"evt-{seq:04d}",
            "match_id": "m-0007",
            "seq": seq,
            "type": event_type,
            "period": 1,
            "match_clock_s": clock_s,
            "wall_ts": datetime(2026, 10, 23, 18, 30, 34, tzinfo=UTC),
            "team_id": team_id,
            "player_id": player_id,
            "x": 61.2,
            "y": 22.4,
            "payload": payload,
        }
    )


def test_rules_load_from_packaged_yaml() -> None:
    rules = load_signal_rules()

    assert {rule.kind for rule in rules} == {
        "goal",
        "red_card",
        "penalty",
        "pass_streak",
        "shot_volume",
    }


def test_critical_goal_bypasses_clock_and_sample_gates() -> None:
    event = make_event(
        1,
        "shot",
        {
            "speed_kmh": 90,
            "outcome": "goal",
            "goal_y": 3.66,
            "goal_z": 1.2,
            "xg": 0.4,
            "body_part": "foot",
        },
        clock_s=30,
    )
    state, _ = apply_event(None, event)

    signal = evaluate_signals(state, event, load_signal_rules())[0]

    assert signal.kind == "goal"
    assert signal.tier == 1
    assert signal.evidence_event_ids == [event.event_id]
    assert signal.event_context is not None
    assert signal.event_context.event_type == "shot"
    assert signal.event_context.event_id == event.event_id
    assert signal.event_context.speed_kmh == 90
    assert signal.event_context.xg == 0.4
    assert signal.event_context.period == 1
    repeated_state, _ = apply_event(None, event)
    repeated = evaluate_signals(repeated_state, event, load_signal_rules())[0]
    assert repeated.signal_id == signal.signal_id


def test_critical_penalty_includes_evidenced_award_context() -> None:
    event = make_event(
        1,
        "set_piece",
        {
            "kind": "penalty",
            "intent": "shot",
            "first_contact_x": 95,
            "first_contact_y": 34,
            "first_contact_player_id": "p-nbr-10",
        },
    )
    state, _ = apply_event(None, event)

    signal = evaluate_signals(state, event, load_signal_rules())[0]

    assert signal.kind == "penalty"
    assert signal.event_context is not None
    assert signal.event_context.event_type == "set_piece"
    assert signal.event_context.event_id == event.event_id
    assert signal.event_context.kind == "penalty"
    assert signal.event_context.intent == "shot"


def test_pass_streak_uses_sample_gate_hysteresis_and_cooldown() -> None:
    rule = next(rule for rule in load_signal_rules() if rule.kind == "pass_streak")
    stats = EntityAggregate(
        passes_attempted=25,
        current_pass_streak=8,
        current_pass_streak_event_ids=[f"pass-{index}" for index in range(8)],
    )
    state = MatchState(
        id="m-0007",
        match_id="m-0007",
        event_count=40,
        match_clock_s=600,
        team_stats={"t-home": stats},
        updated_at="2026-10-23T18:30:34+00:00",
    )
    event = make_event(
        1,
        "pass",
        {
            "receiver_id": "p-nbr-09",
            "end_x": 72,
            "end_y": 20,
            "speed_kmh": 63,
            "outcome": "complete",
            "height": "ground",
            "difficulty": 0.4,
            "inside_opp_shape": True,
        },
    )

    first = evaluate_signals(state, event, (rule,))
    repeated = evaluate_signals(state, event, (rule,))
    assert len(first) == 1
    assert first[0].evidence_event_ids == [f"pass-{index}" for index in range(8)]
    assert repeated == []

    stats.current_pass_streak = 6
    state.match_clock_s = 800
    cooldown_event = make_event(
        2,
        "pass",
        {
            "receiver_id": "p-nbr-09",
            "end_x": 72,
            "end_y": 20,
            "speed_kmh": 63,
            "outcome": "complete",
            "height": "ground",
            "difficulty": 0.4,
            "inside_opp_shape": True,
        },
        clock_s=800,
    )
    assert evaluate_signals(state, cooldown_event, (rule,)) == []

    stats.current_pass_streak = 8
    stats.current_pass_streak_event_ids = [f"pass-again-{index}" for index in range(8)]
    state.match_clock_s = 1200
    second_event = make_event(
        3,
        "pass",
        {
            "receiver_id": "p-nbr-09",
            "end_x": 72,
            "end_y": 20,
            "speed_kmh": 63,
            "outcome": "complete",
            "height": "ground",
            "difficulty": 0.4,
            "inside_opp_shape": True,
        },
        clock_s=1200,
    )
    second = evaluate_signals(state, second_event, (rule,))

    assert len(second) == 1
    assert second[0].signal_id != first[0].signal_id


def test_interpreter_publishes_critical_signal_before_persist(monkeypatch) -> None:
    event = make_event(
        1,
        "shot",
        {
            "speed_kmh": 90,
            "outcome": "goal",
            "goal_y": 3.66,
            "goal_z": 1.2,
            "xg": 0.4,
            "body_part": "foot",
        },
    )
    state, _ = apply_event(None, event)
    published = []

    class ReceivedEvent:
        def get_body(self) -> bytes:
            return event.model_dump_json().encode()

    def update_with_callback(_container, _event, before_persist):
        before_persist(state, event)
        return True

    monkeypatch.setattr(function_app, "get_match_container", lambda: object())
    monkeypatch.setattr(function_app, "update_match_state", update_with_callback)
    monkeypatch.setattr(function_app, "publish_signals", published.extend)

    function_app.interpret([ReceivedEvent()])

    assert [signal.kind for signal in published] == ["goal"]


def test_service_bus_messages_use_signal_ids_for_duplicate_detection(monkeypatch) -> None:
    event = make_event(
        1,
        "shot",
        {
            "speed_kmh": 90,
            "outcome": "goal",
            "goal_y": 3.66,
            "goal_z": 1.2,
            "xg": 0.4,
            "body_part": "foot",
        },
    )
    state, _ = apply_event(None, event)
    signal = evaluate_signals(state, event, load_signal_rules())[0]
    sent_messages = []

    class Sender:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def send_messages(self, messages):
            sent_messages.extend(messages)

    class Client:
        def get_topic_sender(self, *, topic_name):
            assert topic_name == "signals"
            return Sender()

    monkeypatch.setenv("SERVICEBUS_TOPIC_NAME", "signals")
    monkeypatch.setattr("calacat_narrator.servicebus._client", lambda: Client())

    publish_signals([signal])

    assert len(sent_messages) == 1
    assert sent_messages[0].message_id == signal.signal_id
    assert sent_messages[0].content_type == "application/json"

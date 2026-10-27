from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from calacat_narrator.schemas import MatchEvent, PassPayload, PositionSnapshot


def make_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "event_id": "evt-0001",
        "match_id": "m-0007",
        "seq": 1,
        "type": "pass",
        "period": 1,
        "match_clock_s": 1834,
        "wall_ts": datetime(2026, 10, 23, 18, 30, 34, tzinfo=UTC),
        "team_id": "t-home",
        "player_id": "p-nbr-10",
        "x": 61.2,
        "y": 22.4,
        "payload": {
            "receiver_id": "p-nbr-09",
            "end_x": 72.3,
            "end_y": 20.4,
            "speed_kmh": 63.0,
            "outcome": "complete",
            "height": "ground",
        },
    }
    event.update(overrides)
    return event


def test_match_event_validates_typed_payload() -> None:
    event = MatchEvent.model_validate(make_event())

    assert event.type == "pass"
    assert event.payload.receiver_id == "p-nbr-09"


def test_match_event_rejects_payload_for_different_event_type() -> None:
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(make_event(type="shot"))


def test_match_event_rejects_a_prevalidated_payload_for_another_type() -> None:
    payload = PassPayload.model_validate(make_event()["payload"])

    with pytest.raises(ValidationError, match="payload must match event type 'shot'"):
        MatchEvent.model_validate(make_event(type="shot", payload=payload))


def test_match_event_rejects_non_string_event_type_without_crashing() -> None:
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(make_event(type=[]))


def test_match_event_rejects_out_of_bounds_pitch_coordinates() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 105"):
        MatchEvent.model_validate(make_event(x=106))


def test_match_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="wall_ts must include a timezone"):
        MatchEvent.model_validate(make_event(wall_ts=datetime(2026, 10, 23, 18, 30, 34)))


def test_position_snapshot_rejects_duplicate_player_ids() -> None:
    with pytest.raises(ValidationError, match="unique ids"):
        PositionSnapshot.model_validate(
            {
                "match_id": "m-0007",
                "period": 1,
                "match_clock_s": 5,
                "players": [
                    {"id": "p-nbr-01", "x": 10, "y": 20, "speed_kmh": 0},
                    {"id": "p-nbr-01", "x": 11, "y": 20, "speed_kmh": 1},
                ],
                "ball": {"x": 10, "y": 20, "z": 0},
            }
        )

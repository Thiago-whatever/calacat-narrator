import json
from datetime import UTC, datetime

import azure.functions as func
import pytest
from pydantic import ValidationError

import function_app
from calacat_narrator.ingest import MAX_INGEST_BODY_BYTES, IngestPayloadTooLarge, parse_event
from calacat_narrator.schemas import MatchEvent


def event_body() -> bytes:
    return json.dumps(
        {
            "event_id": "evt-0001",
            "match_id": "m-0007",
            "seq": 1,
            "type": "pass",
            "period": 1,
            "match_clock_s": 1834,
            "wall_ts": datetime(2026, 10, 23, 18, 30, 34, tzinfo=UTC).isoformat(),
            "team_id": "t-home",
            "player_id": "p-nbr-10",
            "x": 61.2,
            "y": 22.4,
            "payload": {
                "receiver_id": "p-nbr-09",
                "end_x": 72.3,
                "end_y": 20.4,
                "speed_kmh": 63,
                "outcome": "complete",
                "height": "ground",
            },
        }
    ).encode()


def request(body: bytes, content_type: str = "application/json") -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="https://example.test/api/ingest",
        headers={"content-type": content_type},
        params={},
        route_params={},
        body=body,
    )


def test_parse_event_validates_a_contract_event() -> None:
    event = parse_event(event_body())

    assert isinstance(event, MatchEvent)
    assert event.event_id == "evt-0001"


def test_parse_event_rejects_invalid_or_extra_fields() -> None:
    event = json.loads(event_body())
    event["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        parse_event(json.dumps(event).encode())


def test_parse_event_rejects_oversized_payload() -> None:
    with pytest.raises(IngestPayloadTooLarge):
        parse_event(b" " * (MAX_INGEST_BODY_BYTES + 1))


def test_ingest_rejects_bad_input_without_publishing(monkeypatch) -> None:
    published = []
    monkeypatch.setattr(function_app, "publish_event", published.append)

    response = function_app.ingest(request(b'{"type":"unknown"}'))

    assert response.status_code == 400
    assert published == []


def test_ingest_rejects_non_json_content_type(monkeypatch) -> None:
    published = []
    monkeypatch.setattr(function_app, "publish_event", published.append)

    response = function_app.ingest(request(event_body(), "text/plain"))

    assert response.status_code == 415
    assert published == []


def test_ingest_publishes_valid_event_and_returns_accepted(monkeypatch) -> None:
    published = []
    monkeypatch.setattr(function_app, "publish_event", published.append)

    response = function_app.ingest(request(event_body()))

    assert response.status_code == 202
    assert published[0].event_id == "evt-0001"
    assert json.loads(response.get_body()) == {
        "event_id": "evt-0001",
        "status": "accepted",
    }


def test_ingest_returns_service_unavailable_when_event_hubs_fails(monkeypatch) -> None:
    def fail_publish(_event: MatchEvent) -> None:
        raise RuntimeError("missing Event Hubs configuration")

    monkeypatch.setattr(function_app, "publish_event", fail_publish)

    response = function_app.ingest(request(event_body()))

    assert response.status_code == 503
    assert json.loads(response.get_body()) == {"error": "event_hub_unavailable"}

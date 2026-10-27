import json
from datetime import UTC, datetime, timedelta

import azure.functions as func
import pytest
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

import function_app
from calacat_narrator import kickoff
from calacat_narrator.kickoff import (
    DAILY_MATCH_CAP,
    KickoffLimit,
    KickoffMessage,
    claim_kickoff,
    parse_kickoff,
    run_match,
)

NOW = datetime(2026, 10, 27, 18, 0, tzinfo=UTC)


class FakeContainer:
    """Just enough of a Cosmos container: reads, creates and ETag-checked replaces."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.version = 0

    def read_item(self, item: str, partition_key: str) -> dict:
        if item not in self.items:
            raise CosmosResourceNotFoundError(status_code=404, message="not found")
        return dict(self.items[item])

    def _store(self, body: dict) -> None:
        self.version += 1
        self.items[body["id"]] = {**body, "_etag": str(self.version)}

    def create_item(self, body: dict) -> None:
        if body["id"] in self.items:
            raise CosmosHttpResponseError(status_code=409, message="exists")
        self._store(body)

    def replace_item(self, item: str, body: dict, etag: str, match_condition: object) -> None:
        if self.items[item]["_etag"] != etag:
            raise CosmosHttpResponseError(status_code=412, message="precondition failed")
        self._store(body)


class FakeOut:
    def __init__(self) -> None:
        self.value: str | None = None

    def set(self, value: str) -> None:
        self.value = value


def message(seed: int = 1, speed: int = 10) -> KickoffMessage:
    return KickoffMessage(seed=seed, speed=speed)


def post(body: bytes = b"", content_type: str = "") -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="https://example.test/api/matches",
        headers={"content-type": content_type} if content_type else {},
        params={},
        route_params={},
        body=body,
    )


# ---- Validation


def test_empty_body_uses_the_default_speed() -> None:
    assert parse_kickoff(b"").speed == 10


@pytest.mark.parametrize(
    "body",
    [
        b'{"speed": 4}',
        b'{"speed": 21}',
        b'{"speed": "10"}',
        b'{"speed": 10.5}',
        b'{"seed": 7}',
        b"[]",
    ],
)
def test_out_of_bounds_or_unknown_fields_are_rejected(body: bytes) -> None:
    with pytest.raises(ValueError):
        parse_kickoff(body)


def test_oversized_body_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_kickoff(b"{" + b" " * 2000 + b"}")


def test_endpoint_returns_400_for_invalid_body_without_claiming(monkeypatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(function_app, "get_match_container", lambda: container)
    out = FakeOut()

    response = function_app.start_match(post(b'{"speed": 99}', "application/json"), out)

    assert response.status_code == 400
    assert out.value is None and container.items == {}


def test_endpoint_requires_json_content_type_for_a_body() -> None:
    response = function_app.start_match(post(b'{"speed": 10}', "text/plain"), FakeOut())
    assert response.status_code == 415


def test_endpoint_queues_a_server_picked_seed(monkeypatch) -> None:
    monkeypatch.setattr(function_app, "get_match_container", FakeContainer)
    out = FakeOut()

    response = function_app.start_match(post(), out)

    body = json.loads(response.get_body())
    queued = KickoffMessage.model_validate_json(out.value)
    assert response.status_code == 202
    assert body == {"match_id": queued.match_id, "speed": 10, "status": "starting"}


# ---- Running cap


def test_a_third_match_gets_busy_until_a_slot_frees() -> None:
    container = FakeContainer()
    claim_kickoff(container, message(1), now=NOW)
    claim_kickoff(container, message(2), now=NOW + timedelta(seconds=30))

    with pytest.raises(KickoffLimit) as limit:
        claim_kickoff(container, message(3), now=NOW + timedelta(seconds=60))
    assert limit.value.reason == "busy"
    assert limit.value.retry_after_s == message().run_s - 60

    claim_kickoff(container, message(3), now=NOW + timedelta(seconds=message().run_s))
    assert container.items["slot-0"]["running"] == "m-seed-3"


def test_endpoint_returns_429_with_retry_after(monkeypatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(function_app, "get_match_container", lambda: container)
    for _ in range(2):
        assert function_app.start_match(post(), FakeOut()).status_code == 202
    out = FakeOut()

    response = function_app.start_match(post(), out)

    assert response.status_code == 429
    assert json.loads(response.get_body())["error"] == "busy"
    assert int(response.headers["Retry-After"]) > 0
    assert out.value is None


def test_racing_requests_for_the_last_slot_have_one_winner(monkeypatch) -> None:
    container = FakeContainer()
    claim_kickoff(container, message(1), now=NOW)
    real_count = kickoff._count_today

    def count_then_lose_the_race(target, now):
        real_count(target, now)
        # Another request takes slot-1 meanwhile.
        monkeypatch.setattr(kickoff, "_count_today", real_count)
        claim_kickoff(target, message(9), now=now)

    monkeypatch.setattr(kickoff, "_count_today", count_then_lose_the_race)
    with pytest.raises(KickoffLimit) as limit:
        claim_kickoff(container, message(2), now=NOW)
    assert limit.value.reason == "busy"
    assert container.items["slot-1"]["running"] == "m-seed-9"


# ---- Daily cap


def test_daily_cap_stops_matches_until_utc_midnight() -> None:
    container = FakeContainer()
    for seed in range(DAILY_MATCH_CAP):
        # Each match has finished before the next starts, so only the daily cap applies.
        claim_kickoff(container, message(seed), now=NOW + timedelta(hours=seed % 6, minutes=seed))
        container.items.pop(f"slot-{0}", None)
        container.items.pop(f"slot-{1}", None)

    with pytest.raises(KickoffLimit) as limit:
        claim_kickoff(container, message(99), now=NOW)
    assert limit.value.reason == "daily_cap"
    assert limit.value.retry_after_s == 6 * 3600

    claim_kickoff(container, message(99), now=NOW + timedelta(hours=6))
    assert container.items["day-2026-10-28"]["count"] == 1


# ---- Run


def test_run_streams_every_event_at_the_requested_speed() -> None:
    published, slept = [], []

    count = run_match(message(7, speed=20), published.append, slept.append)

    assert count == len(published) > 0
    assert {event.match_id for event in published} == {"m-seed-7"}
    assert sum(slept) == pytest.approx(5400 / 20)

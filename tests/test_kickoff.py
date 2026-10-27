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
    release_kickoff,
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


def test_when_both_slots_are_busy_a_third_request_joins_the_latest_match() -> None:
    container = FakeContainer()
    assert claim_kickoff(container, message(1), now=NOW) is None
    assert claim_kickoff(container, message(2), now=NOW + timedelta(minutes=2)) is None

    joined = claim_kickoff(container, message(3), now=NOW + timedelta(minutes=3))

    # The latest-ending match has the most game left; joining doesn't use the daily cap.
    assert joined == "m-seed-2"
    assert container.items[f"day-{NOW.date().isoformat()}"]["count"] == 2

    after_first = NOW + timedelta(seconds=message().run_s)
    assert claim_kickoff(container, message(3), now=after_first) is None
    assert container.items["slot-0"]["running"] == "m-seed-3"


def test_a_click_right_after_a_kickoff_joins_it_even_with_a_free_slot() -> None:
    container = FakeContainer()
    claim_kickoff(container, message(1), now=NOW)

    assert claim_kickoff(container, message(2), now=NOW + timedelta(seconds=30)) == "m-seed-1"
    assert claim_kickoff(container, message(2), now=NOW + timedelta(seconds=90)) is None
    assert container.items[f"day-{NOW.date().isoformat()}"]["count"] == 2


def test_endpoint_joins_instead_of_queuing_a_second_match(monkeypatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(function_app, "get_match_container", lambda: container)
    first = FakeOut()
    started = json.loads(function_app.start_match(post(), first).get_body())
    out = FakeOut()

    response = function_app.start_match(post(), out)

    assert response.status_code == 202
    assert json.loads(response.get_body()) == {"match_id": started["match_id"], "status": "joined"}
    assert out.value is None


def test_racing_requests_for_the_last_slot_have_one_winner(monkeypatch) -> None:
    container = FakeContainer()
    # Started long enough ago that the next request races for slot-1 instead of joining it.
    claim_kickoff(container, message(1), now=NOW - timedelta(minutes=2))
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


def test_a_failed_publish_skips_that_event_and_the_match_goes_on() -> None:
    published = []
    failures = iter([RuntimeError("token refresh hiccup")])

    def flaky(event):
        if not published and (error := next(failures, None)):
            raise error
        published.append(event)

    count = run_match(message(7, speed=20), flaky, lambda seconds: None)
    every = run_match(message(7, speed=20), lambda event: None, lambda seconds: None)

    assert count == len(published) == every - 1


def test_release_frees_only_that_matchs_slot() -> None:
    container = FakeContainer()
    claim_kickoff(container, message(1), now=NOW - timedelta(minutes=5))
    claim_kickoff(container, message(2), now=NOW - timedelta(minutes=3))

    release_kickoff(container, "m-seed-1", now=NOW)

    assert container.items["slot-0"]["busy_until"] == NOW.isoformat()
    assert datetime.fromisoformat(container.items["slot-1"]["busy_until"]) > NOW
    assert claim_kickoff(container, message(3), now=NOW + timedelta(seconds=1)) is None
    assert container.items["slot-0"]["running"] == "m-seed-3"


def test_run_kickoff_releases_the_slot_even_when_the_run_crashes(monkeypatch) -> None:
    container = FakeContainer()
    monkeypatch.setattr(function_app, "get_match_container", lambda: container)
    claim_kickoff(container, message(4))

    def crash(*args, **kwargs):
        raise ValueError("bug")

    monkeypatch.setattr(function_app, "run_match", crash)
    queued = func.QueueMessage(body=message(4).model_dump_json().encode())

    with pytest.raises(ValueError):
        function_app.run_kickoff(queued)

    slot = container.items["slot-0"]
    assert datetime.fromisoformat(slot["busy_until"]) <= datetime.now(UTC)

import json
from datetime import UTC, datetime

import azure.functions as func
import pytest
from azure.core.exceptions import ServiceRequestError
from azure.cosmos.exceptions import CosmosResourceNotFoundError

import function_app
from calacat_narrator import webpubsub
from calacat_narrator.agent_runtime import Candidate, Card

CREATED_AT = datetime(2026, 10, 23, 18, 30, tzinfo=UTC)


def card(
    candidate_id: str = "candidate-1",
    match_id: str = "m-0007",
    created_at: datetime = CREATED_AT,
) -> Card:
    candidate = Candidate(
        candidate_id=candidate_id,
        signal_id="signal-1",
        match_id=match_id,
        headline="A passing update",
        why_it_matters="The team reached five shots.",
        metrics={"shot_volume": 5},
        evidence_event_ids=["evt-1"],
        entity_ids=["t-home"],
        topic="shot_volume",
        self_salience=0.8,
        match_clock_s=1000,
    )
    return Card.from_candidate(candidate, created_at=created_at)


def cosmos_document(stored: Card) -> dict[str, object]:
    document = stored.model_dump(mode="json")
    document.update(id=stored.card_id, ttl=stored.ttl_s, _rid="rid", _etag="etag", _ts=1, _lsn=2)
    return document


@pytest.fixture(autouse=True)
def clear_url_cache():
    webpubsub._cached_client_access_url.cache_clear()
    yield
    webpubsub._cached_client_access_url.cache_clear()


class FakeClient:
    def __init__(self, fail_groups: tuple[str, ...] = ()) -> None:
        self.sent: list[tuple[str, dict[str, object], str]] = []
        self.token_kwargs: dict[str, object] = {}
        self.token_calls = 0
        self.fail_groups = fail_groups

    def send_to_group(self, group: str, message: dict[str, object], *, content_type: str) -> None:
        if group in self.fail_groups:
            raise ServiceRequestError("down")
        self.sent.append((group, message, content_type))

    def get_client_access_token(self, **kwargs: object) -> dict[str, str]:
        self.token_kwargs = kwargs
        self.token_calls += 1
        return {"url": "wss://example.webpubsub.azure.com/client/hubs/cards?access_token=t"}


def negotiate_request(match_id: str | None) -> func.HttpRequest:
    params = {} if match_id is None else {"match_id": match_id}
    return func.HttpRequest(method="GET", url="/negotiate", body=b"", params=params)


def test_publish_cards_sends_the_rest_then_raises_when_one_fails(monkeypatch) -> None:
    client = FakeClient(fail_groups=("match-m-0007",))
    monkeypatch.setattr(webpubsub, "_client", lambda: client)
    bad = card("candidate-bad", match_id="m-0007")
    good = card("candidate-good", match_id="m-0008")

    with pytest.raises(RuntimeError):
        webpubsub.publish_cards([bad, good])

    assert [group for group, _, _ in client.sent] == ["match-m-0008"]


def test_negotiate_reuses_one_url_per_match(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(webpubsub, "_client", lambda: client)

    for _ in range(3):
        assert function_app.negotiate(negotiate_request("m-0007")).status_code == 200

    assert client.token_calls == 1


def test_negotiate_issues_receive_only_token_for_one_group(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(webpubsub, "_client", lambda: client)

    response = function_app.negotiate(negotiate_request("m-0007"))

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert json.loads(response.get_body())["group"] == "match-m-0007"
    assert client.token_kwargs == {"groups": ["match-m-0007"], "minutes_to_expire": 60}


def test_negotiate_rejects_invalid_match_ids(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(webpubsub, "_client", lambda: client)

    for match_id in (None, "", "M-0007", "m-1/../admin", "x" * 65):
        response = function_app.negotiate(negotiate_request(match_id))
        assert response.status_code == 400
    assert client.token_kwargs == {}


def test_negotiate_returns_503_when_web_pubsub_fails(monkeypatch) -> None:
    def fail(match_id: str) -> str:
        raise ServiceRequestError("down")

    monkeypatch.setattr(function_app, "client_access_url", fail)

    response = function_app.negotiate(negotiate_request("m-0007"))

    assert response.status_code == 503


class FakeContainer:
    def __init__(self, documents: list[dict[str, object]], state: dict[str, object] | None) -> None:
        self.documents = documents
        self.state = state
        self.partition_keys: list[str] = []

    def query_items(self, *, query: str, parameters: list[dict[str, str]], partition_key: str):
        self.partition_keys.append(partition_key)
        return [d for d in self.documents if d["match_id"] == partition_key]

    def read_item(self, *, item: str, partition_key: str) -> dict[str, object]:
        if self.state is None:
            raise CosmosResourceNotFoundError(message="missing")
        return self.state


def cards_request(match_id: str) -> func.HttpRequest:
    return func.HttpRequest(method="GET", url="/api/cards", body=b"", params={"match_id": match_id})


def test_cards_returns_live_cards_and_authoritative_score(monkeypatch) -> None:
    live = card("candidate-live", created_at=datetime.now(UTC))
    expired = card("candidate-old")
    cards_container = FakeContainer([cosmos_document(live), cosmos_document(expired)], None)
    match_container = FakeContainer([], {"score": {"t-home": 2}, "match_clock_s": 4020})
    monkeypatch.setattr(function_app, "get_cards_container", lambda: cards_container)
    monkeypatch.setattr(function_app, "get_match_container", lambda: match_container)

    response = function_app.cards(cards_request("m-0007"))

    body = json.loads(response.get_body())
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert [c["card_id"] for c in body["cards"]] == [live.card_id]
    assert body["score"] == {"t-home": 2}
    assert body["match_clock_s"] == 4020
    assert cards_container.partition_keys == ["m-0007"]


def test_cards_before_kickoff_has_empty_score(monkeypatch) -> None:
    monkeypatch.setattr(function_app, "get_cards_container", lambda: FakeContainer([], None))
    monkeypatch.setattr(function_app, "get_match_container", lambda: FakeContainer([], None))

    body = json.loads(function_app.cards(cards_request("m-0007")).get_body())

    assert body == {"cards": [], "score": {}, "match_clock_s": 0}


def test_cards_rejects_invalid_match_id_and_reports_cosmos_failure(monkeypatch) -> None:
    assert function_app.cards(cards_request("M-0007")).status_code == 400

    def fail() -> None:
        raise RuntimeError("COSMOS_ENDPOINT setting is required")

    monkeypatch.setattr(function_app, "get_cards_container", fail)
    assert function_app.cards(cards_request("m-0007")).status_code == 503

"""Azure Functions entry point."""

import json
import logging
from typing import List  # noqa: UP035 - see interpret()

import azure.functions as func
from azure.core.exceptions import AzureError
from azure.cosmos.exceptions import CosmosHttpResponseError
from pydantic import ValidationError

from calacat_narrator.cosmos import (
    get_cards_container,
    get_match_container,
    live_cards,
    query_match_cards,
    read_match_state,
)
from calacat_narrator.eventhub import publish_event
from calacat_narrator.ingest import MAX_INGEST_BODY_BYTES, parse_event
from calacat_narrator.interpreter import MatchState, update_match_state
from calacat_narrator.schemas import MatchEvent
from calacat_narrator.servicebus import publish_signals
from calacat_narrator.signals import evaluate_signals, load_signal_rules
from calacat_narrator.webpubsub import (
    client_access_url,
    match_group,
    validate_match_id,
)

logger = logging.getLogger(__name__)
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _json_response(
    body: dict[str, object], status_code: int, headers: dict[str, str] | None = None
) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
        headers=headers,
    )


@app.route(route="ingest", methods=["POST"])
def ingest(req: func.HttpRequest) -> func.HttpResponse:
    """Validate one event envelope, then enqueue it to Event Hubs."""
    content_type = req.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return _json_response({"error": "content_type_must_be_application_json"}, 415)

    body = req.get_body()
    if len(body) > MAX_INGEST_BODY_BYTES:
        return _json_response({"error": "payload_too_large"}, 413)

    try:
        event = parse_event(body)
    except ValidationError as error:
        details = [
            {"location": list(issue["loc"]), "message": issue["msg"], "type": issue["type"]}
            for issue in error.errors(include_input=False, include_context=False)[:20]
        ]
        return _json_response({"error": "invalid_event", "details": details}, 400)
    try:
        publish_event(event)
    except (AzureError, RuntimeError, ValueError):
        logger.exception("Failed to publish event %s to Event Hubs", event.event_id)
        return _json_response({"error": "event_hub_unavailable"}, 503)

    return _json_response({"event_id": event.event_id, "status": "accepted"}, 202)


@app.event_hub_message_trigger(
    arg_name="events",
    event_hub_name="%EVENTHUB_NAME%",
    connection="EVENTHUB_CONNECTION",
    cardinality="many",
)
def interpret(events: List[func.EventHubEvent]) -> None:  # noqa: UP006 - Functions worker rejects builtin list[...]
    """Update durable match aggregates from an ordered Event Hubs batch."""
    container = get_match_container()
    for received_event in events:
        try:
            event = MatchEvent.model_validate_json(received_event.get_body())
        except ValidationError as error:
            logger.error(
                "Discarding invalid Event Hubs event: %s",
                error.errors(include_input=False, include_context=False)[:10],
            )
            continue

        def publish_for_state(state: MatchState, match_event: MatchEvent) -> None:
            signals = evaluate_signals(state, match_event, load_signal_rules())
            publish_signals(signals)

        try:
            applied = update_match_state(container, event, before_persist=publish_for_state)
        except CosmosHttpResponseError:
            logger.exception("Failed to update match state for %s", event.match_id)
            raise
        if not applied:
            logger.info("Skipping duplicate or stale event %s", event.event_id)


@app.route(route="negotiate", methods=["GET"])
def negotiate(req: func.HttpRequest) -> func.HttpResponse:
    """Return a short-lived, receive-only Web PubSub URL for one match's card group."""
    try:
        match_id = validate_match_id(req.params.get("match_id", ""))
    except ValidationError:
        return _json_response({"error": "invalid_match_id"}, 400)
    try:
        url = client_access_url(match_id)
    except (AzureError, RuntimeError):
        logger.exception("Failed to issue Web PubSub client token for %s", match_id)
        return _json_response({"error": "web_pubsub_unavailable"}, 503)
    return _json_response(
        {"url": url, "group": match_group(match_id)},
        200,
        headers={"Cache-Control": "no-store"},
    )


@app.route(route="cards", methods=["GET"])
def cards(req: func.HttpRequest) -> func.HttpResponse:
    """Catch-up for a (re)connecting console: unexpired cards plus the interpreter's score."""
    try:
        match_id = validate_match_id(req.params.get("match_id", ""))
    except ValidationError:
        return _json_response({"error": "invalid_match_id"}, 400)
    try:
        documents = query_match_cards(get_cards_container(), match_id)
        state = read_match_state(get_match_container(), match_id) or {}
    except (AzureError, RuntimeError):
        logger.exception("Failed to load catch-up for %s", match_id)
        return _json_response({"error": "cosmos_unavailable"}, 503)
    return _json_response(
        {
            "cards": [card.model_dump(mode="json") for card in live_cards(documents)],
            "score": state.get("score", {}),
            "match_clock_s": state.get("match_clock_s", 0),
        },
        200,
        headers={"Cache-Control": "no-store"},
    )

"""Azure Functions entry point."""

import json
import logging

import azure.functions as func
from azure.core.exceptions import AzureError
from pydantic import ValidationError

from calacat_narrator.eventhub import publish_event
from calacat_narrator.ingest import MAX_INGEST_BODY_BYTES, parse_event

logger = logging.getLogger(__name__)
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _json_response(body: dict[str, object], status_code: int) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
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

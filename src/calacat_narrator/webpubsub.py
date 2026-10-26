"""Managed-identity Web PubSub delivery of persisted cards to browsers."""

import logging
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from pydantic import TypeAdapter, ValidationError

from .agent_runtime import Card
from .schemas import MatchId

logger = logging.getLogger(__name__)

CLIENT_TOKEN_MINUTES = 60
_match_id_adapter = TypeAdapter(MatchId)


@lru_cache(maxsize=1)
def _client() -> WebPubSubServiceClient:
    host_name = os.environ.get("WEBPUBSUB_HOST_NAME")
    hub = os.environ.get("WEBPUBSUB_HUB")
    if not host_name or not hub:
        raise RuntimeError("WEBPUBSUB_HOST_NAME and WEBPUBSUB_HUB settings are required")
    return WebPubSubServiceClient(
        endpoint=f"https://{host_name}",
        hub=hub,
        credential=DefaultAzureCredential(),
    )


def match_group(match_id: str) -> str:
    return f"match-{match_id}"


def validate_match_id(match_id: str) -> str:
    """Reject IDs outside the event contract before they become group names."""
    return _match_id_adapter.validate_python(match_id)


def live_cards(documents: Iterable[Mapping[str, Any]], now: datetime | None = None) -> list[Card]:
    """Keep valid, unexpired cards; Cosmos system fields are dropped before validation."""
    current = now or datetime.now(UTC)
    cards = []
    for document in documents:
        fields = {key: value for key, value in document.items() if key in Card.model_fields}
        try:
            card = Card.model_validate(fields)
        except ValidationError as error:
            logger.error(
                "Skipping invalid card document %s: %s",
                document.get("id"),
                error.errors(include_input=False, include_context=False)[:10],
            )
            continue
        if card.expires_at > current:
            cards.append(card)
    return cards


def publish_cards(cards: Iterable[Card]) -> None:
    """Send each card to its match group; clients deduplicate retries by card_id."""
    client = _client()
    for card in cards:
        client.send_to_group(
            match_group(card.match_id),
            card.model_dump(mode="json"),
            content_type="application/json",
        )


def client_access_url(match_id: str) -> str:
    """Issue a receive-only URL: the client joins one match group and gets no roles."""
    token = _client().get_client_access_token(
        groups=[match_group(match_id)],
        minutes_to_expire=CLIENT_TOKEN_MINUTES,
    )
    return token["url"]

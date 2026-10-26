"""Managed-identity Cosmos DB clients for match state and published cards."""

import logging
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from azure.cosmos import ContainerProxy, CosmosClient
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential
from pydantic import ValidationError

from .agent_runtime import Card

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client() -> CosmosClient:
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        raise RuntimeError("COSMOS_ENDPOINT setting is required")
    return CosmosClient(endpoint, credential=DefaultAzureCredential())


def _get_container(container_setting: str) -> ContainerProxy:
    database_name = os.environ.get("COSMOS_DATABASE")
    container_name = os.environ.get(container_setting)
    if not database_name or not container_name:
        raise RuntimeError(f"COSMOS_DATABASE and {container_setting} settings are required")
    return _client().get_database_client(database_name).get_container_client(container_name)


@lru_cache(maxsize=1)
def get_match_container() -> ContainerProxy:
    return _get_container("COSMOS_CONTAINER")


@lru_cache(maxsize=1)
def get_cards_container() -> ContainerProxy:
    return _get_container("COSMOS_CARDS_CONTAINER")


def persist_card(container: ContainerProxy, card: Card) -> bool:
    """Create a card once; the stable document ID makes Service Bus retries idempotent."""
    document = card.model_dump(mode="json")
    document["id"] = card.card_id
    document["ttl"] = card.ttl_s
    try:
        container.create_item(body=document)
    except CosmosResourceExistsError:
        return False
    return True


def query_match_cards(container: ContainerProxy, match_id: str) -> list[dict[str, Any]]:
    """Single-partition read; the container TTL already removes expired cards."""
    return list(
        container.query_items(
            query="SELECT * FROM c WHERE c.match_id = @match_id",
            parameters=[{"name": "@match_id", "value": match_id}],
            partition_key=match_id,
        )
    )


def read_match_state(container: ContainerProxy, match_id: str) -> dict[str, Any] | None:
    try:
        return container.read_item(item=match_id, partition_key=match_id)
    except CosmosResourceNotFoundError:
        return None


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

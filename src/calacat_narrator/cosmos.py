"""Managed-identity Cosmos DB clients for match state and published cards."""

import os
from functools import lru_cache

from azure.cosmos import ContainerProxy, CosmosClient
from azure.cosmos.exceptions import CosmosResourceExistsError
from azure.identity import DefaultAzureCredential

from .agent_runtime import Card


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

"""Cosmos DB client setup for the match-state container."""

import os
from functools import lru_cache

from azure.cosmos import ContainerProxy, CosmosClient
from azure.identity import DefaultAzureCredential


@lru_cache(maxsize=1)
def get_match_container() -> ContainerProxy:
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    database_name = os.environ.get("COSMOS_DATABASE")
    container_name = os.environ.get("COSMOS_CONTAINER")
    if not endpoint or not database_name or not container_name:
        raise RuntimeError("Cosmos DB endpoint, database, and container settings are required")

    client = CosmosClient(endpoint, credential=DefaultAzureCredential())
    return client.get_database_client(database_name).get_container_client(container_name)

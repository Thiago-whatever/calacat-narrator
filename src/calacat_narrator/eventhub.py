"""Managed-identity Event Hubs publisher."""

import json
import os
from functools import lru_cache

from azure.eventhub import EventData, EventHubProducerClient
from azure.identity import DefaultAzureCredential

from .schemas import MatchEvent


@lru_cache(maxsize=1)
def _producer() -> EventHubProducerClient:
    namespace = os.environ.get("EVENTHUB_FULLY_QUALIFIED_NAMESPACE")
    eventhub_name = os.environ.get("EVENTHUB_NAME")
    if not namespace or not eventhub_name:
        raise RuntimeError("Event Hubs namespace and event hub settings are required")
    return EventHubProducerClient(
        fully_qualified_namespace=namespace,
        eventhub_name=eventhub_name,
        credential=DefaultAzureCredential(),
    )


def publish_event(event: MatchEvent) -> None:
    """Send one validated event using the Function App's managed identity."""
    producer = _producer()
    batch = producer.create_batch(partition_key=event.match_id)
    batch.add(EventData(json.dumps(event.model_dump(mode="json", exclude_none=True))))
    producer.send_batch(batch)

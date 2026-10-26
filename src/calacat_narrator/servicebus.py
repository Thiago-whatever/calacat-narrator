"""Managed-identity Service Bus signal publisher."""

import os
from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from .signals import Signal


@lru_cache(maxsize=1)
def _client() -> ServiceBusClient:
    namespace = os.environ.get("SERVICEBUS_FULLY_QUALIFIED_NAMESPACE")
    if not namespace:
        raise RuntimeError("Service Bus namespace setting is required")
    return ServiceBusClient(
        fully_qualified_namespace=namespace,
        credential=DefaultAzureCredential(),
    )


def publish_signals(signals: list[Signal]) -> None:
    """Publish signals with stable IDs so retries use Service Bus duplicate detection."""
    if not signals:
        return
    topic_name = os.environ.get("SERVICEBUS_TOPIC_NAME")
    if not topic_name:
        raise RuntimeError("Service Bus topic setting is required")

    messages = [
        ServiceBusMessage(
            signal.model_dump_json(),
            content_type="application/json",
            subject=signal.kind,
            message_id=signal.signal_id,
        )
        for signal in signals
    ]
    with _client().get_topic_sender(topic_name=topic_name) as sender:
        sender.send_messages(messages)

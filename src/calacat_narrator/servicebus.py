"""Managed-identity Service Bus signal publisher."""

import os
from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from .signals import Signal
from .telemetry import card_span, trace_properties


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

    messages = []
    for signal in signals:
        # Each signal starts its card's trace; the message carries it on (ADR-049).
        with card_span(
            f"signal {signal.kind}",
            new_trace=True,
            signal_id=signal.signal_id,
            match_id=signal.match_id,
            kind=signal.kind,
            event_id=signal.evidence_event_ids[-1],
            match_clock_s=signal.match_clock_s,
        ):
            messages.append(
                ServiceBusMessage(
                    signal.model_dump_json(),
                    content_type="application/json",
                    subject=signal.kind,
                    message_id=signal.signal_id,
                    application_properties=trace_properties(),
                )
            )
    with _client().get_topic_sender(topic_name=topic_name) as sender:
        sender.send_messages(messages)

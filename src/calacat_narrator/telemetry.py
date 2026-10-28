"""OpenTelemetry tracing (ADR-019, ADR-049): one trace per card, signal → specialist → Editor.

Each published signal starts its own trace. Its W3C `traceparent` travels in the Service Bus
message's application properties to the specialist, then on the candidate to the Editor, so
the agent's model and tool calls (Agent Framework spans) and the Reviewer sit under one trace.
Spans carry `calacat.*` attributes (`signal_id`, `match_id`, `event_id`, …) to find them.
Without `APPLICATIONINSIGHTS_CONNECTION_STRING` nothing is exported and spans are no-ops.
"""

import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from opentelemetry import context as otel_context
from opentelemetry import propagate, trace

tracer = trace.get_tracer("calacat_narrator")


def configure_tracing(service_name: str) -> bool:
    """Export to Application Insights, with Agent Framework's model and tool spans (workers)."""
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return False
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    from agent_framework.observability import enable_instrumentation
    from azure.monitor.opentelemetry import configure_azure_monitor

    # Live metrics polls every second, and the SDK logs each HTTP call at INFO: both flood the
    # container logs. Traces and app logs still export.
    configure_azure_monitor(enable_live_metrics=False)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    enable_instrumentation()
    return True


def _attributes(values: Mapping[str, object]) -> dict[str, str | int | float]:
    return {
        f"calacat.{key}": value if isinstance(value, (int, float)) else str(value)
        for key, value in values.items()
        if value is not None
    }


@contextmanager
def card_span(
    name: str,
    *,
    parent: otel_context.Context | None = None,
    new_trace: bool = False,
    **attributes: object,
) -> Iterator[trace.Span]:
    """A span under `parent` (a message's context), or the root of a new card trace.

    A new trace links back to the span that was current (the `interpret` invocation).
    """
    links = []
    if new_trace:
        current = trace.get_current_span().get_span_context()
        links = [trace.Link(current)] if current.is_valid else []
        parent = otel_context.Context()
    with tracer.start_as_current_span(
        name, context=parent, links=links, attributes=_attributes(attributes)
    ) as span:
        yield span


def trace_properties() -> dict[str, str]:
    """The current context as message application properties (`traceparent`, …)."""
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier


def message_context(properties: Mapping[str | bytes, object] | None) -> otel_context.Context:
    """The trace context a Service Bus message carries in its application properties."""
    carrier = {
        _text(key): _text(value)
        for key, value in (properties or {}).items()
        if isinstance(value, (str, bytes))
    }
    return propagate.extract(carrier)


def _text(value: str | bytes | object) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)

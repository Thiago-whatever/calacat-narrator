import asyncio

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from test_agent_worker import FakeGenerator, FakeMessage, FakeReceiver, FakeSender, signal_json

from calacat_narrator.agent_worker import process_signal_message
from calacat_narrator.telemetry import (
    card_span,
    configure_tracing,
    message_context,
    trace_properties,
)

EXPORTER = InMemorySpanExporter()


@pytest.fixture(autouse=True)
def spans() -> InMemorySpanExporter:
    # The global provider can be set once per process; the module tracer is a proxy to it.
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
        trace.set_tracer_provider(provider)
    EXPORTER.clear()
    return EXPORTER


def as_service_bus(properties: dict[str, str]) -> dict[bytes, bytes]:
    """Received Service Bus application properties come back with bytes keys and values."""
    return {key.encode(): value.encode() for key, value in properties.items()}


def test_each_signal_starts_its_own_trace_linked_to_the_invocation(spans) -> None:
    with (
        card_span("interpret"),
        card_span("signal goal", new_trace=True, signal_id="s-1", event_id="evt-1"),
    ):
        properties = trace_properties()

    signal, interpret = spans.get_finished_spans()
    assert signal.context.trace_id != interpret.context.trace_id
    assert signal.parent is None and signal.links[0].context == interpret.context
    assert signal.attributes == {"calacat.signal_id": "s-1", "calacat.event_id": "evt-1"}
    assert properties["traceparent"].split("-")[1] == f"{signal.context.trace_id:032x}"


def test_specialist_continues_the_signal_trace_and_passes_it_on(spans) -> None:
    with card_span("signal goal", new_trace=True):
        properties = trace_properties()
    message = FakeMessage(signal_json())
    message.application_properties = as_service_bus(properties)
    sender = FakeSender()

    asyncio.run(process_signal_message(FakeReceiver(), sender, message, FakeGenerator()))  # type: ignore[arg-type]

    signal, specialist = spans.get_finished_spans()
    assert specialist.name == "specialist"
    assert specialist.context.trace_id == signal.context.trace_id
    assert specialist.parent.span_id == signal.context.span_id
    assert specialist.attributes["calacat.candidate_id"] == "b6bb4751-38fc-57ae-b4f4-2635502b9ec4"
    # The candidate carries the trace to the Editor.
    sent = sender.messages[0].application_properties
    editor_parent = trace.get_current_span(message_context(as_service_bus(sent)))
    assert editor_parent.get_span_context().span_id == specialist.context.span_id


def test_a_message_without_trace_properties_starts_fresh(spans) -> None:
    with card_span("editor candidate", parent=message_context(None)):
        pass
    (span,) = spans.get_finished_spans()
    assert span.parent is None


def test_tracing_is_off_without_a_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    assert configure_tracing("editor") is False

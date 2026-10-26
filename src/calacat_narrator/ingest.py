"""Validation boundary for HTTP event ingestion."""

from .schemas import MatchEvent

MAX_INGEST_BODY_BYTES = 64 * 1024


class IngestPayloadTooLarge(ValueError):
    """Raised when an incoming request exceeds the event payload limit."""


def parse_event(body: bytes) -> MatchEvent:
    """Parse one bounded JSON event envelope into its validated contract."""
    if len(body) > MAX_INGEST_BODY_BYTES:
        raise IngestPayloadTooLarge(f"event payload exceeds {MAX_INGEST_BODY_BYTES} bytes")
    return MatchEvent.model_validate_json(body)

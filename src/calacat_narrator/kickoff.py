"""Judge-started matches (ADR-016, ADR-044): request validation, the running and daily caps,
and the server-side run that streams one seeded match into Event Hubs."""

import json
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from azure.core import MatchConditions
from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from pydantic import BaseModel, ConfigDict, Field

from .schemas import MatchEvent, PositionSnapshot
from .simulator import MATCH_DURATION_S, simulate_match

KICKOFF_QUEUE = "match-kickoffs"
MAX_KICKOFF_BODY_BYTES = 1024
MAX_RUNNING_MATCHES = 2
# ponytail: fixed demo budget (ADR-017); move to an app setting if it needs changing without a deploy.
DAILY_MATCH_CAP = 20
MIN_SPEED, DEFAULT_SPEED, MAX_SPEED = 5, 10, 20
# Slot and counter documents live in the match-state container under their own partition.
KICKOFF_PARTITION = "kickoffs"
SLOT_MARGIN_S = 60
MAX_WRITE_ATTEMPTS = 3


class KickoffRequest(BaseModel):
    """Optional body of POST /api/matches; an empty body means the default speed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    speed: int = Field(default=DEFAULT_SPEED, ge=MIN_SPEED, le=MAX_SPEED, strict=True)


class KickoffMessage(BaseModel):
    """Queue message from the HTTP function to the runner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int = Field(ge=0)
    speed: int = Field(ge=MIN_SPEED, le=MAX_SPEED)

    @property
    def match_id(self) -> str:
        return f"m-seed-{self.seed}"  # The simulator's own match ID for this seed.

    @property
    def run_s(self) -> int:
        return MATCH_DURATION_S // self.speed + SLOT_MARGIN_S


class KickoffLimit(Exception):
    def __init__(self, reason: Literal["busy", "daily_cap"], retry_after_s: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after_s = max(1, retry_after_s)


def parse_kickoff(body: bytes) -> KickoffRequest:
    """Validate the request body; raises ValueError (pydantic's ValidationError included)."""
    if len(body) > MAX_KICKOFF_BODY_BYTES:
        raise ValueError("kickoff body is too large")
    if not body.strip():
        return KickoffRequest()
    return KickoffRequest.model_validate(json.loads(body))


def new_kickoff(request: KickoffRequest) -> KickoffMessage:
    """The server picks the seed, so a caller can't replay a match that is already running."""
    return KickoffMessage(seed=secrets.randbelow(2**31), speed=request.speed)


def _read(container: ContainerProxy, item_id: str) -> dict[str, Any] | None:
    try:
        return container.read_item(item=item_id, partition_key=KICKOFF_PARTITION)
    except CosmosResourceNotFoundError:
        return None


def _write(container: ContainerProxy, body: dict[str, Any], etag: str | None) -> bool:
    """Create, or replace only if unchanged since read; False when another request won."""
    try:
        if etag is None:
            container.create_item(body=body)
        else:
            container.replace_item(
                item=body["id"],
                body=body,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
            )
    except CosmosHttpResponseError as error:
        if error.status_code not in {409, 412}:
            raise
        return False
    return True


def _clean(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _count_today(container: ContainerProxy, now: datetime) -> None:
    """Add one to today's (UTC) counter, or raise once the daily cap is reached."""
    day = now.date().isoformat()
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)
    for _ in range(MAX_WRITE_ATTEMPTS):
        document = _read(container, f"day-{day}")
        count = int(document["count"]) if document else 0
        if count >= DAILY_MATCH_CAP:
            raise KickoffLimit("daily_cap", int((tomorrow - now).total_seconds()))
        body = {"id": f"day-{day}", "match_id": KICKOFF_PARTITION, "count": count + 1}
        if _write(container, body, document["_etag"] if document else None):
            return
    raise KickoffLimit("busy", SLOT_MARGIN_S)


def claim_kickoff(
    container: ContainerProxy, message: KickoffMessage, *, now: datetime | None = None
) -> None:
    """Take one of the running-match slots and count the match against today's cap.

    A slot is free when it was never used or its match has finished; ETags make two requests
    racing for the last slot settle on one winner.
    """
    current = now or datetime.now(UTC)
    slots = [(f"slot-{i}", _read(container, f"slot-{i}")) for i in range(MAX_RUNNING_MATCHES)]
    free = [
        (slot_id, document)
        for slot_id, document in slots
        if document is None or datetime.fromisoformat(document["busy_until"]) <= current
    ]
    if not free:
        soonest = min(datetime.fromisoformat(document["busy_until"]) for _, document in slots)
        raise KickoffLimit("busy", int((soonest - current).total_seconds()))

    _count_today(container, current)
    slot_id, document = free[0]
    body = {
        **(_clean(document) if document else {}),
        "id": slot_id,
        "match_id": KICKOFF_PARTITION,
        "running": message.match_id,
        "busy_until": (current + timedelta(seconds=message.run_s)).isoformat(),
    }
    if not _write(container, body, document["_etag"] if document else None):
        raise KickoffLimit("busy", SLOT_MARGIN_S)


def run_match(
    message: KickoffMessage,
    publish: Callable[[MatchEvent], None],
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Stream the seeded match at its speed, like the simulator CLI's --ingest-url mode."""
    published = 0
    previous_s: int | None = None
    for record in simulate_match(message.seed):
        if isinstance(record, MatchEvent):
            publish(record)
            published += 1
        elif isinstance(record, PositionSnapshot):
            if previous_s is not None:
                sleep((record.match_clock_s - previous_s) / message.speed)
            previous_s = record.match_clock_s
    return published

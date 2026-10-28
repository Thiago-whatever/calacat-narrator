"""Service Bus Editor worker for candidate ranking and DLQ recovery."""

import asyncio
import logging
import os
from collections.abc import Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import UTC, datetime

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusReceivedMessage, ServiceBusSubQueue
from azure.servicebus.aio import (
    AutoLockRenewer,
    ServiceBusClient,
    ServiceBusReceiver,
)
from opentelemetry import trace
from pydantic import ValidationError

from .agent_runtime import Candidate, Card, FoundryReviewer
from .cosmos import get_cards_container, persist_card
from .editor import (
    Editor,
    EditorConfig,
    Reviewer,
    fallback_candidate_card,
    fallback_card,
    review_card,
)
from .signals import Signal
from .telemetry import card_span, configure_tracing, message_context
from .webpubsub import publish_cards

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EditorWorkerSettings:
    servicebus_namespace: str
    candidates_topic: str
    candidates_subscription: str
    signals_topic: str
    deadletter_subscriptions: tuple[str, ...]
    foundry_project_endpoint: str
    foundry_model: str
    focus: str | None = None

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "EditorWorkerSettings":
        values = os.environ if environ is None else environ

        def required(name: str) -> str:
            value = values.get(name, "").strip()
            if not value:
                raise RuntimeError(f"{name} setting is required")
            return value

        deadletter_subscriptions = tuple(
            item.strip()
            for item in required("EDITOR_DEADLETTER_SUBSCRIPTIONS").split(",")
            if item.strip()
        )
        if not deadletter_subscriptions:
            raise RuntimeError("EDITOR_DEADLETTER_SUBSCRIPTIONS must include a subscription")
        return cls(
            servicebus_namespace=required("SERVICEBUS_FULLY_QUALIFIED_NAMESPACE"),
            candidates_topic=required("SERVICEBUS_CANDIDATES_TOPIC_NAME"),
            candidates_subscription=required("SERVICEBUS_EDITOR_SUBSCRIPTION_NAME"),
            signals_topic=required("SERVICEBUS_TOPIC_NAME"),
            deadletter_subscriptions=deadletter_subscriptions,
            foundry_project_endpoint=required("FOUNDRY_PROJECT_ENDPOINT"),
            foundry_model=required("FOUNDRY_MODEL"),
            focus=values.get("EDITOR_FOCUS"),
        )


async def process_candidate_message(
    receiver: ServiceBusReceiver,
    message: ServiceBusReceivedMessage,
    editor: Editor,
    pending: dict[str, tuple[ServiceBusReceiver, ServiceBusReceivedMessage]],
    *,
    now: datetime | None = None,
    reviewer: Reviewer | None = None,
) -> None:
    try:
        candidate = Candidate.model_validate_json(_message_body(message))
    except (TypeError, ValueError, ValidationError):
        logger.warning("Dead-lettering invalid candidate message %s", message.message_id)
        await receiver.dead_letter_message(
            message,
            reason="InvalidCandidate",
            error_description="The message body does not match the candidate schema.",
        )
        return

    submission = editor.submit(candidate, now=now)
    for candidate_id in submission.dropped_candidate_ids:
        dropped = pending.pop(candidate_id, None)
        editor.remove(candidate_id)
        if dropped is not None:
            await dropped[0].complete_message(dropped[1])

    if submission.immediate_card is not None:
        try:
            stored = await _review_and_store(submission.immediate_card, editor, reviewer)
        except Exception:
            logger.exception(
                "Failed to persist critical card %s", submission.immediate_card.card_id
            )
            editor.remove(candidate.candidate_id)
            await receiver.abandon_message(message)
            return
        _settle(editor, candidate.candidate_id, stored, now=now)
        await receiver.complete_message(message)
        return

    if submission.accepted:
        pending[candidate.candidate_id] = (receiver, message)
    else:
        await receiver.complete_message(message)


async def process_deadletter_message(
    receiver: ServiceBusReceiver,
    message: ServiceBusReceivedMessage,
    editor: Editor,
    config: EditorConfig,
    pending: dict[str, tuple[ServiceBusReceiver, ServiceBusReceivedMessage]],
    *,
    now: datetime | None = None,
) -> None:
    try:
        signal = Signal.model_validate_json(_message_body(message))
    except (TypeError, ValueError, ValidationError):
        logger.error("Completing unusable dead-letter message %s", message.message_id)
        await receiver.complete_message(message)
        return

    await _submit_fallback_card(
        receiver,
        message,
        fallback_card(signal, config, now=now),
        editor,
        pending,
        now=now,
    )


async def process_candidate_deadletter_message(
    receiver: ServiceBusReceiver,
    message: ServiceBusReceivedMessage,
    editor: Editor,
    config: EditorConfig,
    pending: dict[str, tuple[ServiceBusReceiver, ServiceBusReceivedMessage]],
    *,
    now: datetime | None = None,
    reviewer: Reviewer | None = None,
) -> None:
    try:
        candidate = Candidate.model_validate_json(_message_body(message))
    except (TypeError, ValueError, ValidationError):
        logger.error("Completing unusable candidate DLQ message %s", message.message_id)
        await receiver.complete_message(message)
        return

    await _submit_fallback_card(
        receiver,
        message,
        fallback_candidate_card(candidate, config, now=now),
        editor,
        pending,
        now=now,
    )


async def _submit_fallback_card(
    receiver: ServiceBusReceiver,
    message: ServiceBusReceivedMessage,
    card: Card,
    editor: Editor,
    pending: dict[str, tuple[ServiceBusReceiver, ServiceBusReceivedMessage]],
    *,
    now: datetime | None,
) -> None:
    candidate = Candidate(
        candidate_id=card.candidate_id,
        signal_id=card.signal_id,
        match_id=card.match_id,
        headline=card.headline,
        why_it_matters=card.body,
        metrics=card.metrics,
        evidence_event_ids=card.evidence_event_ids,
        entity_ids=card.entity_ids,
        team_id=card.team_id,
        player_id=card.player_id,
        body_part=card.body_part,
        score=card.score,
        topic=card.topic,
        self_salience=card.salience,
        agent=card.agent,
        ttl_s=card.ttl_s,
        match_clock_s=card.match_clock_s,
    )
    submission = editor.submit(candidate, now=now, source="fallback")
    for candidate_id in submission.dropped_candidate_ids:
        dropped = pending.pop(candidate_id, None)
        editor.remove(candidate_id)
        if dropped is not None:
            await dropped[0].complete_message(dropped[1])
    if submission.immediate_card is not None:
        try:
            stored = await _review_and_store(submission.immediate_card, editor, None)
        except Exception:
            logger.exception(
                "Failed to persist fallback card %s", submission.immediate_card.card_id
            )
            await receiver.abandon_message(message)
            return
        _settle(editor, candidate.candidate_id, stored, now=now)
        await receiver.complete_message(message)
    elif submission.accepted:
        pending[candidate.candidate_id] = (receiver, message)
    else:
        await receiver.complete_message(message)


async def process_message(
    receiver: ServiceBusReceiver,
    route: str,
    message: ServiceBusReceivedMessage,
    editor: Editor,
    config: EditorConfig,
    pending: dict[str, tuple[ServiceBusReceiver, ServiceBusReceivedMessage]],
    *,
    now: datetime,
    reviewer: Reviewer | None = None,
) -> None:
    """Route one message; a failure settles that message instead of stopping the Editor.

    The Editor runs as a single replica, and a DLQ message can't be dead-lettered again, so
    an unhandled error here would crash-loop on the same message and stop every card.
    """
    try:
        with card_span(
            f"editor {route}",
            parent=message_context(message.application_properties),
            message_id=message.message_id,
        ):
            if route == "signal_dlq":
                await process_deadletter_message(
                    receiver, message, editor, config, pending, now=now
                )
            elif route == "candidate_dlq":
                await process_candidate_deadletter_message(
                    receiver, message, editor, config, pending, now=now
                )
            else:
                await process_candidate_message(
                    receiver, message, editor, pending, now=now, reviewer=reviewer
                )
    except Exception:
        logger.exception("Editor failed on %s message %s; settling it", route, message.message_id)
        try:
            if route in {"signal_dlq", "candidate_dlq"}:
                await receiver.complete_message(message)
            else:
                await receiver.dead_letter_message(
                    message,
                    reason="EditorError",
                    error_description="The Editor raised while processing this message.",
                )
        except Exception:
            logger.exception("Could not settle %s message %s", route, message.message_id)


async def consume_editor(
    receivers: list[tuple[ServiceBusReceiver, str]],
    editor: Editor,
    config: EditorConfig,
    reviewer: Reviewer | None,
) -> None:
    """Keep deferred candidates locked until they are stored or intentionally dropped."""
    pending: dict[str, tuple[ServiceBusReceiver, ServiceBusReceivedMessage]] = {}
    async with AutoLockRenewer(max_lock_renewal_duration=300) as renewer:
        while True:
            batches = await asyncio.gather(
                *(
                    receiver.receive_messages(max_message_count=1, max_wait_time=1)
                    for receiver, _ in receivers
                )
            )
            current = datetime.now(UTC)
            for (receiver, route), messages in zip(receivers, batches, strict=True):
                for message in messages:
                    renewer.register(receiver, message)
                    await process_message(
                        receiver,
                        route,
                        message,
                        editor,
                        config,
                        pending,
                        now=current,
                        reviewer=reviewer,
                    )

            for candidate_id in editor.expire_queue(now=current):
                expired = pending.pop(candidate_id, None)
                if expired is not None:
                    await expired[0].complete_message(expired[1])

            card = editor.peek_due(now=current)
            if card is None:
                continue
            source = pending.get(card.candidate_id)
            if source is None:
                editor.remove(card.candidate_id)
                continue
            try:
                # Back under the candidate's trace: the Reviewer's spans join the card's trace.
                with card_span(
                    "editor publish",
                    parent=message_context(source[1].application_properties),
                    candidate_id=card.candidate_id,
                ):
                    stored = await _review_and_store(card, editor, reviewer)
            except Exception:
                logger.exception("Failed to persist Editor card %s", card.card_id)
                editor.remove(card.candidate_id)
                pending.pop(card.candidate_id, None)
                await source[0].abandon_message(source[1])
                continue
            _settle(editor, card.candidate_id, stored, now=current)
            pending.pop(card.candidate_id, None)
            await source[0].complete_message(source[1])


def create_reviewer_agent(
    settings: EditorWorkerSettings,
    credential: AsyncTokenCredential,
) -> Agent:
    return Agent(
        client=FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model,
            credential=credential,
        ),
        name="reviewer",
        instructions=(
            "You review live football captions before they go on air, and translate them "
            "into Spanish. Use only the facts you are given."
        ),
    )


async def run_editor(settings: EditorWorkerSettings) -> None:
    config = EditorConfig.load()
    editor = Editor(config, focus=settings.focus)
    async with (
        DefaultAzureCredential() as credential,
        ServiceBusClient(
            fully_qualified_namespace=settings.servicebus_namespace,
            credential=credential,
        ) as client,
        AsyncExitStack() as stack,
    ):
        receivers: list[tuple[ServiceBusReceiver, str]] = []
        candidate_receiver = client.get_subscription_receiver(
            topic_name=settings.candidates_topic,
            subscription_name=settings.candidates_subscription,
            max_wait_time=1,
        )
        receivers.append(
            (
                await stack.enter_async_context(candidate_receiver),
                "candidate",
            )
        )
        candidate_dlq_receiver = client.get_subscription_receiver(
            topic_name=settings.candidates_topic,
            subscription_name=settings.candidates_subscription,
            sub_queue=ServiceBusSubQueue.DEAD_LETTER,
            max_wait_time=1,
        )
        receivers.append(
            (
                await stack.enter_async_context(candidate_dlq_receiver),
                "candidate_dlq",
            )
        )
        for subscription in settings.deadletter_subscriptions:
            deadletter_receiver = client.get_subscription_receiver(
                topic_name=settings.signals_topic,
                subscription_name=subscription,
                sub_queue=ServiceBusSubQueue.DEAD_LETTER,
                max_wait_time=1,
            )
            receivers.append(
                (
                    await stack.enter_async_context(deadletter_receiver),
                    "signal_dlq",
                )
            )
        reviewer_agent = await stack.enter_async_context(
            create_reviewer_agent(settings, credential)
        )
        await consume_editor(receivers, editor, config, FoundryReviewer(reviewer_agent))


async def _review_and_store(card: Card, editor: Editor, reviewer: Reviewer | None) -> bool:
    """Review (or localize a fallback), then store. False means the Reviewer rejected it."""
    config = editor.config
    critical = card.topic in config.critical_topics
    final = await review_card(
        card,
        reviewer,
        timeout_s=config.critical_review_timeout_s if critical else config.review_timeout_s,
        critical_topics=config.critical_topics,
    )
    if final is None:
        return False
    _store_card(final)
    return True


def _settle(editor: Editor, candidate_id: str, stored: bool, *, now: datetime | None) -> None:
    """A stored card uses the publish slot; a rejected one leaves the slot free."""
    if stored:
        editor.mark_published(candidate_id, now=now)
    else:
        editor.remove(candidate_id)


def _store_card(card: Card) -> None:
    """Persist, then push to browsers. A failed push only logs: the card is already stored."""
    if card.i18n is None:
        raise ValueError(f"card {card.card_id} has no Spanish text and must not be published")
    span = trace.get_current_span()
    span.set_attribute("calacat.card_id", card.card_id)
    span.set_attribute("calacat.source", card.source)
    span.set_attribute("calacat.review", card.review or "none")
    persist_card(get_cards_container(), card)
    try:
        publish_cards([card])
    except Exception:
        logger.exception("Stored card %s but failed to push it", card.card_id)


def _message_body(message: ServiceBusReceivedMessage) -> bytes:
    body = message.body
    if isinstance(body, (bytes, bytearray, memoryview)):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    return b"".join(bytes(part) for part in body)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    configure_tracing("editor")
    asyncio.run(run_editor(EditorWorkerSettings.from_environment()))


if __name__ == "__main__":
    main()

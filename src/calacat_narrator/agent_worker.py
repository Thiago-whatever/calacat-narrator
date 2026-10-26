"""Service Bus worker for Foundry-backed candidate generation."""

import asyncio
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage, ServiceBusReceivedMessage
from azure.servicebus.aio import (
    AutoLockRenewer,
    ServiceBusClient,
    ServiceBusReceiver,
    ServiceBusSender,
)

from .agent_runtime import FoundryCandidateGenerator
from .signals import Signal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerSettings:
    foundry_project_endpoint: str
    foundry_model: str
    servicebus_namespace: str
    signals_topic: str
    signals_subscription: str
    candidates_topic: str
    agent_name: str

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "WorkerSettings":
        values = os.environ if environ is None else environ

        def required(name: str) -> str:
            value = values.get(name, "").strip()
            if not value:
                raise RuntimeError(f"{name} setting is required")
            return value

        return cls(
            foundry_project_endpoint=required("FOUNDRY_PROJECT_ENDPOINT"),
            foundry_model=required("FOUNDRY_MODEL"),
            servicebus_namespace=required("SERVICEBUS_FULLY_QUALIFIED_NAMESPACE"),
            signals_topic=required("SERVICEBUS_TOPIC_NAME"),
            signals_subscription=required("SERVICEBUS_SUBSCRIPTION_NAME"),
            candidates_topic=required("SERVICEBUS_CANDIDATES_TOPIC_NAME"),
            agent_name=required("AGENT_NAME"),
        )


def create_candidate_agent(
    settings: WorkerSettings,
    credential: AsyncTokenCredential,
) -> Agent:
    """Build the Agent Framework client using the runtime's Entra credential."""
    return Agent(
        client=FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model,
            credential=credential,
        ),
        name=settings.agent_name,
        instructions=(
            "You create brief, evidence-grounded candidate narratives for live football. "
            "Only describe the supplied signal; do not calculate or infer statistics."
        ),
    )


async def process_signal_message(
    receiver: ServiceBusReceiver,
    sender: ServiceBusSender,
    message: ServiceBusReceivedMessage,
    generator: FoundryCandidateGenerator,
) -> None:
    """Validate, generate, and publish before completing the source message."""
    try:
        signal = Signal.model_validate_json(_message_body(message))
    except (TypeError, ValueError):
        logger.warning("Dead-lettering invalid signal message %s", message.message_id)
        await receiver.dead_letter_message(
            message,
            reason="InvalidSignal",
            error_description="The message body does not match the signal schema.",
        )
        return

    try:
        candidate = await generator.create_candidate(signal)
        await sender.send_messages(
            ServiceBusMessage(
                candidate.model_dump_json(),
                content_type="application/json",
                subject=candidate.topic,
                message_id=candidate.candidate_id,
            )
        )
    except Exception:
        logger.exception("Failed to create or publish candidate for signal %s", signal.signal_id)
        await receiver.abandon_message(message)
        return

    await receiver.complete_message(message)


def _message_body(message: ServiceBusReceivedMessage) -> bytes:
    body = message.body
    if isinstance(body, (bytes, bytearray, memoryview)):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    return b"".join(bytes(part) for part in body)


async def consume_signals(
    receiver: ServiceBusReceiver,
    sender: ServiceBusSender,
    generator: FoundryCandidateGenerator,
) -> None:
    """Consume one message at a time to keep its peek lock bounded during inference."""
    async with AutoLockRenewer(max_lock_renewal_duration=300) as renewer:
        while True:
            messages = await receiver.receive_messages(max_message_count=1, max_wait_time=5)
            for message in messages:
                renewer.register(receiver, message)
                await process_signal_message(receiver, sender, message, generator)


async def run_worker(settings: WorkerSettings) -> None:
    async with DefaultAzureCredential() as credential:
        agent = create_candidate_agent(settings, credential)
        async with agent:
            generator = FoundryCandidateGenerator(agent, settings.agent_name)
            async with ServiceBusClient(
                fully_qualified_namespace=settings.servicebus_namespace,
                credential=credential,
            ) as client:
                receiver = client.get_subscription_receiver(
                    topic_name=settings.signals_topic,
                    subscription_name=settings.signals_subscription,
                    max_wait_time=5,
                )
                sender = client.get_topic_sender(topic_name=settings.candidates_topic)
                async with receiver, sender:
                    await consume_signals(receiver, sender, generator)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    asyncio.run(run_worker(WorkerSettings.from_environment()))


if __name__ == "__main__":
    main()

import asyncio
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from test_agent_runtime import GOAL_DRAFT, FakeAgent, make_signal

from calacat_narrator.agent_runtime import (
    FoundryCandidateGenerator,
    local_facts,
    signal_facts,
    signal_history_facts,
)
from calacat_narrator.interpreter import EntityAggregate, MatchState
from calacat_narrator.mcp_stats import McpFacts, match_stats, open_mcp_facts, server


async def _over_mcp(tool_name: str):
    async with create_connected_server_and_client_session(server) as session:
        tools = {tool.name for tool in (await session.list_tools()).tools}
        return tools, await McpFacts(session)(tool_name, make_signal())


def test_server_lists_its_tools_and_serves_the_same_facts() -> None:
    tools, facts = asyncio.run(_over_mcp("get_event_facts"))

    assert tools == {"get_event_facts", "get_history_facts", "get_match_stats"}
    assert facts == signal_facts(make_signal())


def test_history_facts_over_mcp_match_the_local_ones() -> None:
    _, facts = asyncio.run(_over_mcp("get_history_facts"))

    signal = make_signal()
    assert facts == signal_facts(signal) | signal_history_facts(signal)
    assert facts == asyncio.run(local_facts("get_history_facts", signal))


def test_specialist_tool_call_goes_through_the_server() -> None:
    async def run():
        async with create_connected_server_and_client_session(server) as session:
            agent = FakeAgent(GOAL_DRAFT)
            generator = FoundryCandidateGenerator(agent, "goal-shot", McpFacts(session))  # type: ignore[arg-type]
            await generator.create_candidate(make_signal())
            return agent

    agent = asyncio.run(run())

    assert agent.tool_names == ["get_event_facts"]
    assert agent.facts == signal_facts(make_signal())


def test_bad_signal_is_a_tool_error() -> None:
    async def run():
        async with create_connected_server_and_client_session(server) as session:
            return await session.call_tool("get_event_facts", {"signal": "{}"})

    assert asyncio.run(run()).isError


def test_match_stats_are_plain_words() -> None:
    state = MatchState(
        id="m-0007",
        match_id="m-0007",
        match_clock_s=3401,
        score={"t-home": 2},
        team_stats={
            "t-home": EntityAggregate(
                shots=14, shots_on_target=6, passes_attempted=480, passes_completed=412,
                longest_pass_streak=17, yellow_cards=1,
            )
        },
        updated_at="2026-10-27T20:00:00+00:00",
    )

    assert match_stats(state) == {
        "minute": "57'",
        "Northbridge Comets": (
            "2 goals, 14 shots (6 on target), 412 of 480 passes completed, longest passing run "
            "17, 1 yellow and 0 red cards"
        ),
        "Southmere Foxes": "no events yet",
    }


def test_workers_start_the_server_as_a_child_process(monkeypatch: pytest.MonkeyPatch) -> None:
    # The container has the package installed; here the child finds it through PYTHONPATH.
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).parents[1] / "src"))

    async def run():
        async with open_mcp_facts() as facts:
            return await facts("get_event_facts", make_signal())

    assert asyncio.run(run()) == signal_facts(make_signal())

"""MCP match-stats server (ADR-009, ADR-048): the agents' facts tools over the Model Context Protocol.

The specialists' tools are served here: their in-process `get_event_facts` / `get_history_facts` /
`get_recap_facts`
forward the current signal to this server, which builds the plain-word facts (ADR-038).
`get_match_stats` reads a match's durable state from Cosmos DB, for anyone with access.

Run it over stdio: `python -m calacat_narrator.mcp_stats` (the agent workers start it this way,
and `.vscode/mcp.json` registers it for Copilot agent mode).
"""

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import FastMCP

from .agent_runtime import (
    _catalog,
    broadcast_minute,
    signal_facts,
    signal_history_facts,
    signal_recap_facts,
)
from .cosmos import get_match_container, read_match_state
from .interpreter import MatchState
from .schemas import MatchId
from .signals import Signal

server = FastMCP(
    "calacat-match-stats",
    instructions=(
        "Facts about fictional football matches in plain words. The facts tools take a signal "
        "as JSON; get_match_stats takes a match ID such as m-seed-123."
    ),
)


@server.tool()
def get_event_facts(signal: str) -> dict[str, str]:
    """The moment a signal describes, in plain words: minute, half, teams, player, score."""
    return signal_facts(Signal.model_validate_json(signal))


@server.tool()
def get_history_facts(signal: str) -> dict[str, str]:
    """The moment plus the fictional club and player archive the Historian consults (ADR-046)."""
    parsed = Signal.model_validate_json(signal)
    return signal_facts(parsed) | signal_history_facts(parsed)


@server.tool()
def get_recap_facts(signal: str) -> dict[str, str]:
    """The final whistle plus the result, scorers, shots and passing for the Recap (ADR-047)."""
    parsed = Signal.model_validate_json(signal)
    return signal_facts(parsed) | signal_recap_facts(parsed)


@server.tool()
def get_match_stats(match_id: MatchId) -> dict[str, str]:
    """Score, shots, passing and cards so far for both teams of a match, from Cosmos DB."""
    document = read_match_state(get_match_container(), match_id)
    if document is None:
        raise ValueError(f"no match {match_id!r}")
    return match_stats(MatchState.model_validate(_state_fields(document)))


def match_stats(state: MatchState) -> dict[str, str]:
    stats = {"minute": broadcast_minute(state.match_clock_s)}
    for team in _catalog().teams:
        team_stats = state.team_stats.get(team.id)
        if team_stats is None:
            stats[team.name] = "no events yet"
            continue
        stats[team.name] = (
            f"{state.score.get(team.id, 0)} goals, {team_stats.shots} shots "
            f"({team_stats.shots_on_target} on target), {team_stats.passes_completed} of "
            f"{team_stats.passes_attempted} passes completed, longest passing run "
            f"{team_stats.longest_pass_streak}, {team_stats.yellow_cards} yellow and "
            f"{team_stats.red_cards} red cards"
        )
    return stats


def _state_fields(document: dict) -> dict:
    """Drop Cosmos system fields (`_rid`, `_etag`, …) before validation."""
    return {key: value for key, value in document.items() if not key.startswith("_")}


class McpFacts:
    """A specialist's facts source (agent_runtime.FactsSource) that calls this server's tools."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def __call__(self, tool_name: str, signal: Signal) -> dict[str, str]:
        result = await self._session.call_tool(tool_name, {"signal": signal.model_dump_json()})
        if result.isError or not isinstance(result.structuredContent, dict):
            raise RuntimeError(f"MCP tool {tool_name} failed: {result.content}")
        # FastMCP wraps non-object return types in "result"; dict[str, str] arrives as is.
        return {str(key): str(value) for key, value in result.structuredContent.items()}


@asynccontextmanager
async def open_mcp_facts() -> AsyncIterator[McpFacts]:
    """Start this server as a child process over stdio and hand back a facts source."""
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "calacat_narrator.mcp_stats"], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        yield McpFacts(session)


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()

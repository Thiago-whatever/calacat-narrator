"""Full-time recap facts (ADR-047): the final match statistics in plain words.

Cards live 3 minutes in Cosmos, so the recap is built from the durable match state instead:
the `full_time` signal carries the final per-team and per-scorer numbers, the candidate and
card keep them in `metrics` as `<entity>.<stat>`, and these facts are rebuilt from there for
the Recap agent, the Reviewer, the number check and the template alike.
"""

from collections.abc import Mapping
from typing import Literal

from .catalog import FootballCatalog

Lang = Literal["en", "es"]

FULL_TIME = "full_time"
# Per-team aggregates the full_time signal carries (interpreter.EntityAggregate fields).
TEAM_STATS = (
    "goals",
    "shots",
    "shots_on_target",
    "passes_attempted",
    "passes_completed",
    "longest_pass_streak",
    "red_cards",
)


def _stat(metrics: Mapping[str, int | float], entity_id: str, name: str) -> int:
    return int(metrics.get(f"{entity_id}.{name}", 0))


def recap_facts(
    catalog: FootballCatalog,
    metrics: Mapping[str, int | float],
    lang: Lang = "en",
) -> dict[str, str]:
    """Result, scorers, shots, passing and red cards for both teams, in English or Spanish."""
    home, away = catalog.teams[0], catalog.teams[1]
    goals = {team.id: _stat(metrics, team.id, "goals") for team in (home, away)}
    final = f"{home.name} {goals[home.id]}, {away.name} {goals[away.id]}"
    if goals[home.id] == goals[away.id]:
        result = (
            f"{home.name} y {away.name} empataron"
            if lang == "es"
            else f"{home.name} and {away.name} drew"
        )
    else:
        winner, loser = (home, away) if goals[home.id] > goals[away.id] else (away, home)
        result = f"{winner.name} venció a {loser.name}" if lang == "es" else (
            f"{winner.name} beat {loser.name}"
        )

    scorers = [
        f"{player.name} ({next(t.name for t in catalog.teams if t.id == player.club_id)})"
        + (f" x{count}" if (count := _stat(metrics, player.id, "goals")) > 1 else "")
        for player in catalog.players
        if _stat(metrics, player.id, "goals") > 0
    ]

    def per_team(text: str) -> str:
        return ", ".join(text.format(team=team.name, **_team(metrics, team.id)) for team in (home, away))

    if lang == "es":
        facts = {
            "event": f"sonó el pitido final: {result}",
            "final": final,
            "shots": per_team("{team} {shots} ({shots_on_target} al arco)"),
            "passes": per_team("{team} completó {passes_completed} de {passes_attempted}"),
            "longest_run": per_team("{team} {longest_pass_streak} pases seguidos"),
        }
    else:
        facts = {
            "event": f"the final whistle went: {result}",
            "final": final,
            "shots": per_team("{team} {shots} ({shots_on_target} on target)"),
            "passes": per_team("{team} completed {passes_completed} of {passes_attempted}"),
            "longest_run": per_team("{team} {longest_pass_streak} passes in a row"),
        }
    if scorers:
        facts["scorers"] = ", ".join(scorers)
    if any(_stat(metrics, team.id, "red_cards") for team in (home, away)):
        facts["red_cards"] = per_team("{team} {red_cards}")
    return facts


def _team(metrics: Mapping[str, int | float], team_id: str) -> dict[str, int]:
    return {name: _stat(metrics, team_id, name) for name in TEAM_STATS}

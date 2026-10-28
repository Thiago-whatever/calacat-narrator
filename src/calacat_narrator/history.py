"""The fictional club and player archive the Historian consults (ADR-046)."""

import json
from collections.abc import Mapping
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from pydantic import Field

from .schemas import ContractModel, PlayerId, TeamId

Lang = Literal["en", "es"]

# Signal kinds the Historian covers; its cards use the topic "history_<kind>".
HISTORY_KINDS = ("goal", "pass_streak")
HISTORY_PREFIX = "history_"


class TeamHistory(ContractModel):
    founded: int = Field(ge=1850, le=2026)
    league_titles: int = Field(ge=0)
    season_goals_before: int = Field(ge=0)
    record_goals: int = Field(ge=1)
    record_season: str = Field(min_length=7, max_length=7)
    longest_pass_run: int = Field(ge=1)
    longest_pass_run_season: str = Field(min_length=7, max_length=7)


class PlayerHistory(ContractModel):
    career_goals: int = Field(ge=0)
    appearances: int = Field(ge=1)
    note_en: str = Field(min_length=1, max_length=100)
    note_es: str = Field(min_length=1, max_length=100)


class Archive(ContractModel):
    season: str = Field(min_length=7, max_length=7)
    teams: dict[TeamId, TeamHistory]
    players: dict[PlayerId, PlayerHistory]


@lru_cache(maxsize=1)
def load_archive() -> Archive:
    text = files("calacat_narrator").joinpath("data", "history.json").read_text(encoding="utf-8")
    return Archive.model_validate(json.loads(text))


def history_kind(topic: str) -> str | None:
    """The signal kind behind a Historian topic, or None for any other topic."""
    kind = topic.removeprefix(HISTORY_PREFIX)
    return kind if topic.startswith(HISTORY_PREFIX) and kind in HISTORY_KINDS else None


def history_facts(
    *,
    kind: str,
    value: int,
    team_id: str,
    team: str,
    player_id: str | None,
    player: str | None,
    score: Mapping[str, int] | None,
    lang: Lang = "en",
) -> dict[str, str]:
    """Archive facts for one moment; every comparison is computed here, never by the model."""
    archive = load_archive()
    club = archive.teams.get(team_id)
    if club is None:
        return {}
    es = lang == "es"
    facts = {
        "club history": (
            f"{team} se fundó en {club.founded} y tiene {club.league_titles} títulos de liga"
            if es
            else f"{team} were founded in {club.founded} and have won {club.league_titles} "
            "league titles"
        )
    }
    if kind == "goal":
        goals = club.season_goals_before + (score or {}).get(team_id, 0)
        record, season = club.record_goals, club.record_season
        if goals > record:
            status = (
                f"supera el récord del club de {record} goles en una temporada ({season})"
                if es
                else f"breaks the club record of {record} goals in a season ({season})"
            )
        elif goals == record:
            status = (
                f"iguala el récord del club de {record} goles en una temporada ({season})"
                if es
                else f"equals the club record of {record} goals in a season ({season})"
            )
        else:
            status = (
                f"queda a {record - goals} del récord del club de {record} ({season})"
                if es
                else f"is {record - goals} short of the club record of {record} ({season})"
            )
        facts["record"] = (
            f"{team} suma {goals} goles de liga en la temporada {archive.season}; {status}"
            if es
            else f"{team} now have {goals} league goals in {archive.season}, which {status}"
        )
    elif kind == "pass_streak":
        facts["record"] = (
            f"la racha de pases más larga registrada de {team} es de "
            f"{club.longest_pass_run} pases ({club.longest_pass_run_season}); hoy van {value}"
            if es
            else f"{team}'s longest passing run on record is {club.longest_pass_run} passes "
            f"({club.longest_pass_run_season}); today's run was {value}"
        )
    if player and (career := archive.players.get(player_id or "")):
        facts["player history"] = (
            f"{player} llegó al partido con {career.career_goals} goles en "
            f"{career.appearances} partidos y {career.note_es}"
            if es
            else f"{player} came into today with {career.career_goals} goals in "
            f"{career.appearances} games and {career.note_en}"
        )
    return facts

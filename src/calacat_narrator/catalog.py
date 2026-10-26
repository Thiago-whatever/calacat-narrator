"""Loading and cross-validating the fictional team and player catalog."""

import json
from importlib.resources import files
from typing import Self

from pydantic import Field, model_validator

from .schemas import ContractModel, PlayerId, TeamId


class Team(ContractModel):
    id: TeamId
    name: str = Field(min_length=1, max_length=80)
    short_name: str = Field(min_length=1, max_length=12)
    colors: list[str] = Field(min_length=1)
    squad: list[PlayerId] = Field(min_length=1)
    form: list[str] = Field(min_length=1, max_length=5)
    table_position: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_team_fields(self) -> Self:
        if any(
            len(color) != 7
            or color[0] != "#"
            or any(character not in "0123456789abcdefABCDEF" for character in color[1:])
            for color in self.colors
        ):
            raise ValueError("team colors must use #RRGGBB hex notation")
        if any(result not in {"W", "D", "L"} for result in self.form):
            raise ValueError("team form entries must be W, D, or L")
        if len(self.squad) != len(set(self.squad)):
            raise ValueError("team squad must not contain duplicate player ids")
        return self


class Player(ContractModel):
    id: PlayerId
    name: str = Field(min_length=1, max_length=80)
    number: int = Field(ge=1, le=99)
    position: str = Field(pattern=r"^(goalkeeper|defender|midfielder|forward)$")
    club_id: TeamId
    nationality: str = Field(min_length=2, max_length=3)
    height_cm: int = Field(ge=140, le=220)
    preferred_foot: str = Field(pattern=r"^(left|right|both)$")


class FootballCatalog(ContractModel):
    teams: list[Team] = Field(min_length=2)
    players: list[Player] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_rosters(self) -> Self:
        team_ids = [team.id for team in self.teams]
        player_ids = [player.id for player in self.players]
        if len(team_ids) != len(set(team_ids)):
            raise ValueError("team ids must be unique")
        if len(player_ids) != len(set(player_ids)):
            raise ValueError("player ids must be unique")

        players_by_id = {player.id: player for player in self.players}
        assigned_players: set[str] = set()
        for team in self.teams:
            team_players: list[Player] = []
            for player_id in team.squad:
                player = players_by_id.get(player_id)
                if player is None:
                    raise ValueError(f"team '{team.id}' references unknown player '{player_id}'")
                if player.club_id != team.id:
                    raise ValueError(
                        f"player '{player_id}' club_id does not match team '{team.id}'"
                    )
                if player_id in assigned_players:
                    raise ValueError(f"player '{player_id}' appears on multiple team rosters")
                assigned_players.add(player_id)
                team_players.append(player)
            numbers = [player.number for player in team_players]
            if len(numbers) != len(set(numbers)):
                raise ValueError(f"player numbers must be unique within team '{team.id}'")

        if assigned_players != set(player_ids):
            raise ValueError("every catalog player must appear on exactly one team roster")
        return self


def load_catalog() -> FootballCatalog:
    """Load the packaged fictional catalog and validate its roster references."""
    package_data = files("calacat_narrator").joinpath("data")
    teams = json.loads(package_data.joinpath("teams.json").read_text(encoding="utf-8"))
    players = json.loads(package_data.joinpath("players.json").read_text(encoding="utf-8"))
    return FootballCatalog(teams=teams["teams"], players=players["players"])

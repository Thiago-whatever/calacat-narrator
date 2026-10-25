import pytest
from pydantic import ValidationError

from calacat_narrator.catalog import FootballCatalog, load_catalog


def test_load_catalog_has_two_complete_fictional_rosters() -> None:
    catalog = load_catalog()

    assert [team.id for team in catalog.teams] == ["t-home", "t-away"]
    assert len(catalog.players) == 22
    assert all(len(team.squad) == 11 for team in catalog.teams)


def test_catalog_rejects_player_on_wrong_team_roster() -> None:
    catalog = load_catalog()
    teams = [team.model_dump() for team in catalog.teams]
    teams[0]["squad"][0] = "p-smf-01"

    with pytest.raises(ValidationError, match="club_id does not match"):
        FootballCatalog(teams=teams, players=[player.model_dump() for player in catalog.players])

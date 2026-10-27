import asyncio

import pytest
from test_agent_runtime import FakeAgent, make_pass_streak_signal, make_signal

from calacat_narrator.agent_runtime import (
    CandidateDraft,
    Card,
    FoundryCandidateGenerator,
    _catalog,
    card_facts,
    signal_history_facts,
)
from calacat_narrator.editor import check_against_facts, localized_fallback_card
from calacat_narrator.history import history_facts, history_kind, load_archive

HISTORY_DRAFT = CandidateDraft(
    headline="Elsen sends Northbridge into history",
    why_it_matters="57' Bram Elsen's goal gives Northbridge Comets 73 this season, a club record.",
    self_salience=0.85,
)


def goal_record(home_goals: int) -> str:
    return history_facts(
        kind="goal",
        value=home_goals,
        team_id="t-home",
        team="Northbridge Comets",
        player_id=None,
        player=None,
        score={"t-home": home_goals},
    )["record"]


@pytest.mark.parametrize(
    ("home_goals", "status"),
    [
        (2, "breaks the club record of 72 goals in a season (1998-99)"),
        (1, "equals the club record of 72 goals in a season (1998-99)"),
        (0, "is 1 short of the club record of 72 (1998-99)"),
    ],
)
def test_record_status_is_computed_in_code(home_goals: int, status: str) -> None:
    assert goal_record(home_goals).endswith(status)


def test_archive_matches_the_catalog() -> None:
    archive, catalog = load_archive(), _catalog()
    assert set(archive.teams) == {team.id for team in catalog.teams}
    assert set(archive.players) <= {player.id for player in catalog.players}


def test_historian_consults_the_archive_and_gets_its_own_topic() -> None:
    fake_agent = FakeAgent(HISTORY_DRAFT)
    signal = make_signal()

    candidate = asyncio.run(
        FoundryCandidateGenerator(fake_agent, "historian").create_candidate(signal)  # type: ignore[arg-type]
    )

    assert fake_agent.tool_names == ["get_event_facts", "get_history_facts"]
    assert fake_agent.options["tool_choice"] == {
        "mode": "required",
        "required_function_name": "get_history_facts",
    }
    assert "Historian" in fake_agent.prompt
    assert candidate.topic == "history_goal" and candidate.agent == "historian"
    assert history_kind(candidate.topic) == "goal"
    # The Reviewer's facts for the card include the same archive facts the agent consulted.
    facts = card_facts(Card.from_candidate(candidate))
    assert signal_history_facts(signal).items() <= facts.items()
    assert "73 league goals" in facts["record"]
    assert "186 goals in 297 games" in facts["player history"]


@pytest.mark.parametrize("signal", [make_signal(), make_pass_streak_signal()], ids=["goal", "pass"])
def test_historian_fallback_is_bilingual_and_grounded(signal) -> None:
    candidate = asyncio.run(
        FoundryCandidateGenerator(FakeAgent(HISTORY_DRAFT), "historian").create_candidate(signal)  # type: ignore[arg-type]
    )

    card = localized_fallback_card(Card.from_candidate(candidate))

    assert card.source == "fallback" and card.i18n is not None
    assert card.i18n.es.headline != card.headline
    check_against_facts(card, card_facts(card))

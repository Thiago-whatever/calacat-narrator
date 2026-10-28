import asyncio
from datetime import UTC, datetime

from test_agent_runtime import FakeAgent

from calacat_narrator.agent_runtime import (
    CandidateDraft,
    Card,
    FoundryCandidateGenerator,
    _catalog,
    card_facts,
    signal_recap_facts,
)
from calacat_narrator.editor import EditorConfig, check_against_facts, localized_fallback_card
from calacat_narrator.interpreter import EntityAggregate, MatchState
from calacat_narrator.recap import recap_facts
from calacat_narrator.schemas import MatchEvent
from calacat_narrator.signals import evaluate_signals, load_signal_rules

RECAP_DRAFT = CandidateDraft(
    headline="Northbridge beat Southmere 2-1",
    why_it_matters="Full time at 90': Bram Elsen scores twice as Northbridge Comets win 2-1.",
    self_salience=0.9,
)


def period_event(action: str, period: int, clock_s: int = 5400) -> MatchEvent:
    return MatchEvent.model_validate(
        {
            "event_id": f"evt-{period}-{action}",
            "match_id": "m-0007",
            "seq": 900,
            "type": "period",
            "period": period,
            "match_clock_s": clock_s,
            "wall_ts": datetime(2026, 10, 27, 20, 0, tzinfo=UTC),
            "team_id": None,
            "player_id": None,
            "x": 52.5,
            "y": 34,
            "payload": {"action": action},
        }
    )


def final_state() -> MatchState:
    return MatchState(
        id="m-0007",
        match_id="m-0007",
        match_clock_s=5400,
        period=2,
        score={"t-home": 2, "t-away": 1},
        team_stats={
            "t-home": EntityAggregate(
                goals=2, shots=14, shots_on_target=6, passes_attempted=480,
                passes_completed=412, longest_pass_streak=17,
            ),
            "t-away": EntityAggregate(
                goals=1, shots=9, shots_on_target=3, passes_attempted=431,
                passes_completed=350, longest_pass_streak=11, red_cards=1,
            ),
        },
        player_stats={"p-nbr-09": EntityAggregate(goals=2), "p-nbr-04": EntityAggregate(shots=3)},
        updated_at="2026-10-27T20:00:00+00:00",
    )


def full_time_signal():
    signals = evaluate_signals(final_state(), period_event("end", 2), load_signal_rules())
    assert [signal.kind for signal in signals] == ["full_time"]
    return signals[0]


def test_only_the_second_half_whistle_is_full_time() -> None:
    state, rules = final_state(), load_signal_rules()
    assert evaluate_signals(state, period_event("end", 1, 2700), rules) == []
    assert evaluate_signals(state, period_event("start", 2, 2701), rules) == []

    signal = full_time_signal()
    assert signal.entity == {"team_id": "t-home"} and signal.value == 3 and signal.tier == 1
    assert signal.stats["t-home"]["shots"] == 14 and signal.stats["t-away"]["red_cards"] == 1
    # Only scorers are carried per player.
    assert signal.stats["p-nbr-09"] == {"goals": 2} and "p-nbr-04" not in signal.stats


def test_recap_facts_name_the_result_scorers_and_numbers() -> None:
    facts = signal_recap_facts(full_time_signal())
    assert facts["event"] == "the final whistle went: Northbridge Comets beat Southmere Foxes"
    assert facts["final"] == "Northbridge Comets 2, Southmere Foxes 1"
    assert facts["scorers"] == "Bram Elsen (Northbridge Comets) x2"
    assert facts["shots"] == "Northbridge Comets 14 (6 on target), Southmere Foxes 9 (3 on target)"
    assert facts["red_cards"] == "Northbridge Comets 0, Southmere Foxes 1"


def test_a_draw_has_no_winner_and_spanish_is_translated() -> None:
    metrics = {"t-home.goals": 1, "t-away.goals": 1}
    assert "drew" in recap_facts(_catalog(), metrics)["event"]
    es = recap_facts(_catalog(), metrics, "es")
    assert es["event"] == "sonó el pitido final: Northbridge Comets y Southmere Foxes empataron"
    assert "scorers" not in es and "red_cards" not in es


def test_recap_agent_writes_from_the_final_numbers() -> None:
    fake_agent = FakeAgent(RECAP_DRAFT)
    signal = full_time_signal()

    candidate = asyncio.run(
        FoundryCandidateGenerator(fake_agent, "recap").create_candidate(signal)  # type: ignore[arg-type]
    )

    assert fake_agent.tool_names == ["get_recap_facts"]
    assert "Recap agent" in fake_agent.prompt and "Call get_recap_facts first" in fake_agent.prompt
    assert fake_agent.facts["minute"] == "90'" and fake_agent.facts["scorers"]
    assert candidate.topic == "full_time" and candidate.agent == "recap"
    assert candidate.metrics["t-home.shots"] == 14 and candidate.metrics["p-nbr-09.goals"] == 2
    # The Reviewer and the number check see the same numbers the agent wrote from.
    facts = card_facts(Card.from_candidate(candidate))
    assert signal_recap_facts(signal).items() <= facts.items()


def test_recap_fallback_is_bilingual_grounded_and_critical() -> None:
    candidate = asyncio.run(
        FoundryCandidateGenerator(FakeAgent(RECAP_DRAFT), "recap").create_candidate(full_time_signal())  # type: ignore[arg-type]
    )

    card = localized_fallback_card(Card.from_candidate(candidate))

    assert card.headline == "Full time: Northbridge Comets 2, Southmere Foxes 1"
    assert card.i18n is not None and card.i18n.es.headline.startswith("Final: ")
    check_against_facts(card, card_facts(card))
    assert "full_time" in EditorConfig.load().critical_topics

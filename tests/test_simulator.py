import json

import pytest

from calacat_narrator.catalog import load_catalog
from calacat_narrator.interpreter import apply_event
from calacat_narrator.schemas import MatchEvent, PositionSnapshot
from calacat_narrator.signals import evaluate_signals, load_signal_rules
from calacat_narrator.simulator import SeededMatch, main, serialize_record, simulate_match


def test_seeded_match_output_is_reproducible() -> None:
    first = [serialize_record(record) for record in simulate_match(seed=42, duration_s=24)]
    second = [serialize_record(record) for record in simulate_match(seed=42, duration_s=24)]

    assert first == second


def test_different_seeds_produce_distinct_matches() -> None:
    first = [serialize_record(record) for record in simulate_match(seed=42, duration_s=24)]
    second = [serialize_record(record) for record in simulate_match(seed=43, duration_s=24)]

    assert first != second


def test_match_has_a_position_snapshot_every_second_for_both_squads() -> None:
    records = list(simulate_match(seed=3, duration_s=12))
    snapshots = [record for record in records if isinstance(record, PositionSnapshot)]

    assert [snapshot.match_clock_s for snapshot in snapshots] == list(range(13))
    assert all(len(snapshot.players) == 22 for snapshot in snapshots)


def test_match_emits_valid_events_with_monotonic_sequences() -> None:
    events = [
        record for record in simulate_match(seed=8, duration_s=40) if isinstance(record, MatchEvent)
    ]

    assert [event.seq for event in events] == list(range(1, len(events) + 1))
    assert events[0].type == "period"
    assert events[-1].type == "period"
    assert {event.type for event in events}.issuperset({"period", "pass"})


def test_jsonl_records_identify_events_and_positions() -> None:
    records = list(simulate_match(seed=3, duration_s=3))
    decoded = [json.loads(serialize_record(record)) for record in records]

    assert {record["record_type"] for record in decoded} == {"event", "positions"}
    assert all("data" in record for record in decoded)


def test_simulator_rejects_too_short_match() -> None:
    with pytest.raises(ValueError, match="at least 2 seconds"):
        SeededMatch(seed=1, duration_s=1, catalog=load_catalog())


def test_cli_writes_complete_offline_jsonl(tmp_path) -> None:
    output_file = tmp_path / "match.jsonl"

    assert main(["--seed", "3", "--duration-s", "4", "--output", str(output_file)]) == 0

    records = [json.loads(line) for line in output_file.read_text(encoding="utf-8").splitlines()]
    assert sum(record["record_type"] == "positions" for record in records) == 5
    assert any(record["record_type"] == "event" for record in records)


def test_cli_rejects_zero_speed() -> None:
    with pytest.raises(SystemExit):
        main(["--speed", "0", "--duration-s", "4"])


# ---- Realism and facts-only checks over 20 full matches (ADR-037)

CALIBRATION_SEEDS = range(20)
ON_BALL_EVENTS = {"pass", "duel", "possession_change", "shot"}


@pytest.fixture(scope="module")
def full_matches() -> dict[int, list[MatchEvent]]:
    catalog = load_catalog()
    return {
        seed: [
            record
            for record in simulate_match(seed, catalog=catalog)
            if isinstance(record, MatchEvent)
        ]
        for seed in CALIBRATION_SEEDS
    }


def _count(events: list[MatchEvent], event_type: str, **payload: object) -> int:
    return sum(
        1
        for event in events
        if event.type == event_type
        and all(getattr(event.payload, key) == value for key, value in payload.items())
    )


def test_full_matches_have_realistic_goals_and_shots(full_matches) -> None:
    goals = [_count(events, "shot", outcome="goal") for events in full_matches.values()]
    shots = [_count(events, "shot") for events in full_matches.values()]

    assert 2.2 <= sum(goals) / len(goals) <= 3.4
    assert max(goals) <= 8
    assert 18 <= sum(shots) / len(shots) <= 32


def test_full_matches_turn_the_ball_over_and_award_penalties(full_matches) -> None:
    assert all(_count(events, "possession_change") >= 150 for events in full_matches.values())
    assert sum(_count(events, "set_piece", kind="penalty") for events in full_matches.values()) >= 1


def test_goalkeeper_saves_follow_only_saved_shots(full_matches) -> None:
    for events in full_matches.values():
        shots = {event.event_id: event for event in events if event.type == "shot"}
        for event in events:
            if event.type == "gk_action":
                assert shots[event.payload.shot_event_id].payload.outcome == "saved"


def test_conceding_team_kicks_off_after_a_goal(full_matches) -> None:
    for events in full_matches.values():
        for index, event in enumerate(events):
            if event.type == "shot" and event.payload.outcome == "goal":
                # Pressure and fouls carry the defending team's ID, so look at on-ball actions.
                restart = next((e for e in events[index + 1 :] if e.type in ON_BALL_EVENTS), None)
                if restart is not None and restart.period == event.period:
                    assert restart.team_id != event.team_id


def test_ball_can_move_backwards(full_matches) -> None:
    events = full_matches[0]
    backward = [
        event
        for event in events
        if event.type == "pass"
        and (event.payload.end_x - event.x) * (1 if event.team_id == "t-home" else -1) < 0
    ]
    assert backward


def test_events_are_facts_only_and_validate(full_matches) -> None:
    for events in full_matches.values():
        for event in events:
            dumped = event.model_dump(mode="json")
            assert MatchEvent.model_validate(dumped) == event
            assert {"xg", "difficulty", "inside_opp_shape"}.isdisjoint(dumped["payload"])


def test_full_match_is_byte_identical_for_a_seed() -> None:
    first = "\n".join(serialize_record(record) for record in simulate_match(seed=11))
    second = "\n".join(serialize_record(record) for record in simulate_match(seed=11))
    assert first == second


def test_threshold_signals_fire_beyond_goals() -> None:
    kinds: set[str] = set()
    rules = load_signal_rules()
    for seed in (101, 202, 303):
        state = None
        for record in simulate_match(seed):
            if isinstance(record, MatchEvent):
                state, _ = apply_event(state, record)
                kinds.update(signal.kind for signal in evaluate_signals(state, record, rules))
    assert {"goal", "shot_volume", "pass_streak"} <= kinds

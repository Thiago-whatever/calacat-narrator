import json

import pytest

from calacat_narrator.catalog import load_catalog
from calacat_narrator.schemas import MatchEvent, PositionSnapshot
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

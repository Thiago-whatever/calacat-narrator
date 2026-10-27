from datetime import UTC, datetime

from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosHttpResponseError

from calacat_narrator.interpreter import MatchState, apply_event, update_match_state
from calacat_narrator.schemas import MatchEvent


def make_event(
    seq: int,
    event_type: str,
    payload: dict[str, object],
    *,
    team_id: str | None = "t-home",
    player_id: str | None = "p-nbr-10",
) -> MatchEvent:
    return MatchEvent.model_validate(
        {
            "event_id": f"evt-{seq:04d}",
            "match_id": "m-0007",
            "seq": seq,
            "type": event_type,
            "period": 1,
            "match_clock_s": seq * 10,
            "wall_ts": datetime(2026, 10, 23, 18, 30, seq, tzinfo=UTC),
            "team_id": team_id,
            "player_id": player_id,
            "x": 61.2,
            "y": 22.4,
            "payload": payload,
        }
    )


def make_pass(
    seq: int,
    *,
    team_id: str = "t-home",
    player_id: str = "p-nbr-10",
) -> MatchEvent:
    return make_event(
        seq,
        "pass",
        {
            "receiver_id": "p-nbr-09",
            "end_x": 72,
            "end_y": 20,
            "speed_kmh": 63,
            "outcome": "complete",
            "height": "ground",
        },
        team_id=team_id,
        player_id=player_id,
    )


def test_interpreter_reduces_hand_built_event_list_to_match_and_entity_stats() -> None:
    events = [
        make_event(
            1,
            "pass",
            {
                "receiver_id": "p-nbr-09",
                "end_x": 72,
                "end_y": 20,
                "speed_kmh": 63,
                "outcome": "complete",
                "height": "ground",
            },
        ),
        make_event(
            2,
            "pass",
            {
                "receiver_id": "p-nbr-09",
                "end_x": 75,
                "end_y": 22,
                "speed_kmh": 57,
                "outcome": "complete",
                "height": "ground",
            },
        ),
        make_event(
            3,
            "shot",
            {
                "speed_kmh": 88,
                "outcome": "goal",
                "goal_y": 3.66,
                "goal_z": 1.2,
                "body_part": "foot",
            },
        ),
        make_event(4, "card", {"card": "yellow", "reason": "unsporting conduct"}),
        make_event(
            5,
            "possession_change",
            {"from_team": "t-home", "to_team": "t-away", "cause": "tackle"},
        ),
    ]

    state = None
    for event in events:
        state, applied = apply_event(state, event)
        assert applied

    assert isinstance(state, MatchState)
    assert state.event_count == 5
    assert state.last_seq == 5
    assert state.possession_team_id == "t-away"
    assert state.score == {"t-home": 1}
    assert state.team_stats["t-home"].passes_attempted == 2
    assert state.team_stats["t-home"].longest_pass_streak == 2
    assert state.team_stats["t-home"].shots_on_target == 1
    assert state.team_stats["t-home"].yellow_cards == 1
    assert state.player_stats["p-nbr-10"].goals == 1


def test_interpreter_skips_duplicate_and_stale_sequences() -> None:
    event = make_event(
        1,
        "pass",
        {
            "receiver_id": "p-nbr-09",
            "end_x": 72,
            "end_y": 20,
            "speed_kmh": 63,
            "outcome": "complete",
            "height": "ground",
        },
    )

    state, applied = apply_event(None, event)
    replayed_state, replayed = apply_event(state, event)

    assert applied
    assert not replayed
    assert replayed_state.event_count == 1
    assert replayed_state.team_stats["t-home"].passes_attempted == 1


def test_interpreter_tracks_sequence_gaps_and_rejects_cross_match_state() -> None:
    first = make_event(
        1,
        "period",
        {"action": "start"},
        team_id=None,
        player_id=None,
    )
    third = make_event(
        3,
        "period",
        {"action": "end"},
        team_id=None,
        player_id=None,
    )
    state, _ = apply_event(None, first)
    state, _ = apply_event(state, third)

    assert state.sequence_gaps == 1

    other_match = MatchEvent.model_validate(
        {
            **first.model_dump(mode="json"),
            "event_id": "evt-other",
            "match_id": "m-0008",
        }
    )
    try:
        apply_event(state, other_match)
    except ValueError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("cross-match updates must be rejected")


def test_pass_streak_and_evidence_are_scoped_to_each_possession() -> None:
    events = [
        make_pass(1),
        make_pass(2, player_id="p-nbr-09"),
        make_event(
            3,
            "possession_change",
            {"from_team": "t-home", "to_team": "t-away", "cause": "tackle"},
        ),
        make_pass(4, team_id="t-away", player_id="p-nbr-20"),
        make_event(
            5,
            "possession_change",
            {"from_team": "t-away", "to_team": "t-home", "cause": "interception"},
            team_id="t-away",
            player_id="p-nbr-20",
        ),
        make_pass(6),
    ]

    state = None
    for event in events:
        state, applied = apply_event(state, event)
        assert applied

    assert isinstance(state, MatchState)
    assert state.team_stats["t-home"].current_pass_streak == 1
    assert state.team_stats["t-home"].longest_pass_streak == 2
    assert state.team_stats["t-home"].current_pass_streak_event_ids == ["evt-0006"]
    assert state.team_stats["t-away"].current_pass_streak == 0
    assert state.team_stats["t-away"].current_pass_streak_event_ids == []
    assert state.player_stats["p-nbr-10"].current_pass_streak == 1
    assert state.player_stats["p-nbr-10"].current_pass_streak_event_ids == ["evt-0006"]
    assert state.player_stats["p-nbr-09"].current_pass_streak == 0
    assert state.player_stats["p-nbr-09"].current_pass_streak_event_ids == []

    replayed_state, applied = apply_event(state, events[-1])
    assert not applied
    assert replayed_state.team_stats["t-home"].current_pass_streak == 1
    assert replayed_state.team_stats["t-home"].current_pass_streak_event_ids == ["evt-0006"]


def test_interpreter_resets_streak_when_duel_is_lost_or_goalkeeper_takes_possession() -> None:
    state, _ = apply_event(None, make_pass(1))
    duel = make_event(
        2,
        "duel",
        {"opponent_id": "p-nbr-20", "kind": "tackle", "won": False},
    )
    state, _ = apply_event(state, duel)
    assert state.team_stats["t-home"].current_pass_streak == 0
    assert state.team_stats["t-home"].current_pass_streak_event_ids == []
    assert state.player_stats["p-nbr-10"].current_pass_streak == 0
    assert state.player_stats["p-nbr-10"].current_pass_streak_event_ids == []

    state, _ = apply_event(state, make_pass(3, team_id="t-away", player_id="p-nbr-20"))
    goalkeeper_action = make_event(
        4,
        "gk_action",
        {"kind": "claim", "shot_event_id": "evt-shot"},
        team_id="t-home",
        player_id="p-nbr-01",
    )
    state, _ = apply_event(state, goalkeeper_action)
    assert state.team_stats["t-away"].current_pass_streak == 0
    assert state.team_stats["t-away"].current_pass_streak_event_ids == []
    assert state.possession_team_id == "t-home"


def test_foul_ends_the_active_pass_streak() -> None:
    state, _ = apply_event(None, make_pass(1))
    foul = make_event(2, "foul", {"reason": "late challenge"})
    state, _ = apply_event(state, foul)
    state, _ = apply_event(state, make_pass(3))

    assert state.team_stats["t-home"].current_pass_streak == 1
    assert state.team_stats["t-home"].current_pass_streak_event_ids == ["evt-0003"]
    assert state.player_stats["p-nbr-10"].current_pass_streak == 1
    assert state.player_stats["p-nbr-10"].current_pass_streak_event_ids == ["evt-0003"]


class MemoryContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {}
        self.version = 0

    def read_item(self, *, item: str, partition_key: str) -> dict[str, object]:
        assert item == partition_key
        if item not in self.items:
            raise CosmosHttpResponseError(status_code=404, message="not found")
        return self.items[item]

    def create_item(self, *, body: dict[str, object]) -> None:
        item_id = str(body["id"])
        if item_id in self.items:
            raise CosmosHttpResponseError(status_code=409, message="already exists")
        self.version += 1
        self.items[item_id] = {**body, "_etag": str(self.version)}

    def replace_item(
        self,
        *,
        item: str,
        body: dict[str, object],
        etag: str,
        match_condition: object,
    ) -> None:
        assert match_condition == MatchConditions.IfNotModified
        current = self.items[item]
        if current["_etag"] != etag:
            raise CosmosHttpResponseError(status_code=412, message="etag changed")
        self.version += 1
        self.items[item] = {**body, "_etag": str(self.version)}


def test_cosmos_persistence_is_idempotent_and_replaces_with_etag() -> None:
    container = MemoryContainer()
    first = make_event(1, "period", {"action": "start"}, team_id=None, player_id=None)
    second = make_event(2, "period", {"action": "end"}, team_id=None, player_id=None)

    assert update_match_state(container, first)
    assert not update_match_state(container, first)
    assert update_match_state(container, second)

    stored = MatchState.model_validate(
        {key: value for key, value in container.items["m-0007"].items() if not key.startswith("_")}
    )
    assert stored.event_count == 2
    assert stored.last_seq == 2

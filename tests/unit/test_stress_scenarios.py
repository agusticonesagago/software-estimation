"""Unit tests for CAG stress-test scenario profiles."""

import pytest

from evals.stress.scenarios import (
    ALL_N_TURNS,
    DEFAULT_N_TURNS,
    SCENARIO_NAMES,
    TurnSpec,
    build_scenario,
    get_profile,
    iter_scenario_matrix,
)


def test_all_profiles_expose_twenty_turns() -> None:
    """Each profile script must support N up to 20.

    :return: None.
    :raises AssertionError: If a profile is shorter than 20 turns.
    """
    for name in SCENARIO_NAMES:
        profile = get_profile(name)
        assert len(profile) == 20
        assert [turn.turn_index for turn in profile] == list(range(1, 21))


def test_build_scenario_truncates_to_requested_n() -> None:
    """``build_scenario`` returns the prefix of length ``n_turns``.

    :return: None.
    :raises AssertionError: If truncation or facts are wrong.
    """
    turns = build_scenario("growing", 3)
    assert len(turns) == 3
    assert turns[0] == TurnSpec(
        turn_index=1,
        transcript=turns[0].transcript,
        fact_to_remember="project name: Nimbus",
    )
    assert "Nimbus" in turns[0].transcript
    assert all(isinstance(item, TurnSpec) for item in turns)


def test_growing_fact_is_project_name_nimbus() -> None:
    """Growing profile anchors the durable project-name fact on turn 1.

    :return: None.
    :raises AssertionError: If the fact tracker is wrong.
    """
    assert get_profile("growing")[0].fact_to_remember == "project name: Nimbus"


def test_pivot_introduces_flutter_on_turn_five() -> None:
    """Pivot profile switches the client stack to Flutter at turn 5.

    :return: None.
    :raises AssertionError: If turn 5 does not encode the Flutter fact.
    """
    turn = get_profile("pivot")[4]
    assert turn.turn_index == 5
    assert turn.fact_to_remember == "stack includes Flutter"
    assert "Flutter" in turn.transcript
    assert "React" in turn.transcript


def test_contradiction_locks_budget_then_raises_it() -> None:
    """Contradiction profile locks 30k EUR then claims 80k EUR later.

    :return: None.
    :raises AssertionError: If budget facts are missing on turns 3 and 8.
    """
    profile = get_profile("contradiction")
    turn3 = profile[2]
    turn8 = profile[7]
    assert turn3.fact_to_remember == "budget locked: 30000 EUR"
    assert "30000" in turn3.transcript
    assert turn8.fact_to_remember == "budget claimed: 80000 EUR"
    assert "80000" in turn8.transcript


@pytest.mark.parametrize("n", DEFAULT_N_TURNS)
def test_default_n_values_build_for_every_profile(n: int) -> None:
    """Default stress lengths must build for all three profiles.

    :arg n: Turn count under test.
    :return: None.
    :raises AssertionError: If build fails or length mismatches.
    """
    for name in SCENARIO_NAMES:
        turns = build_scenario(name, n)
        assert len(turns) == n


def test_iter_scenario_matrix_default_shape() -> None:
    """Default matrix is 3 scenarios × default N values.

    :return: None.
    :raises AssertionError: If matrix size or contents are unexpected.
    """
    matrix = iter_scenario_matrix()
    assert len(matrix) == len(SCENARIO_NAMES) * len(DEFAULT_N_TURNS)
    names = {row[0] for row in matrix}
    assert names == set(SCENARIO_NAMES)


def test_build_scenario_rejects_unknown_and_oob_n() -> None:
    """Unknown profiles and out-of-range ``n`` raise clearly.

    :return: None.
    :raises AssertionError: If the wrong exception type is raised.
    """
    with pytest.raises(KeyError):
        get_profile("unknown")
    with pytest.raises(ValueError):
        build_scenario("growing", 0)
    with pytest.raises(ValueError):
        build_scenario("growing", 21)
    assert ALL_N_TURNS[-1] == 20

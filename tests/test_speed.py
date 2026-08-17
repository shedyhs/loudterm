import pytest

from loudterm.speed import (
    DEFAULT_SPEED,
    MAX_SPEED,
    MIN_SPEED,
    SPEED_STEP,
    adjust_speed,
    clamp_speed,
    faster,
    parse_speed_arg,
    slower,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.0, 1.0),
        (MAX_SPEED + 5, MAX_SPEED),
        (MIN_SPEED - 5, MIN_SPEED),
        (1.234, 1.23),
    ],
)
def test_clamp_speed_keeps_value_inside_range(value: float, expected: float):
    assert clamp_speed(value) == expected


def test_faster_increases_by_one_step():
    assert faster(1.0) == round(1.0 + SPEED_STEP, 2)


def test_slower_decreases_by_one_step():
    assert slower(1.0) == round(1.0 - SPEED_STEP, 2)


def test_faster_never_exceeds_max():
    assert faster(MAX_SPEED) == MAX_SPEED


def test_slower_never_goes_below_min():
    assert slower(MIN_SPEED) == MIN_SPEED


def test_adjust_speed_applies_delta():
    expected = 1.5
    assert adjust_speed(1.0, 0.5) == expected


@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ("", 1.0),
        ("1.5", 1.5),
        ("+", 1.1),
        ("-", 0.9),
        ("+0.3", 1.3),
        ("-0.4", 0.6),
        ("  1.5  ", 1.5),
        ("3", MAX_SPEED),
        ("0.1", MIN_SPEED),
        ("reset", DEFAULT_SPEED),
        ("NORMAL", DEFAULT_SPEED),
    ],
)
def test_parse_speed_arg_resolves_supported_forms(arg: str, expected: float):
    assert parse_speed_arg(arg, current=1.0) == expected


@pytest.mark.parametrize("arg", ["abc", "1.5x", "++", "fast"])
def test_parse_speed_arg_returns_none_for_invalid_input(arg: str):
    assert parse_speed_arg(arg, current=1.0) is None

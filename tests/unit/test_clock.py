"""Tests for the immutable monthly simulation clock."""

from dataclasses import FrozenInstanceError

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ecodeling.model.clock import ClockExhaustedError, SimulationClock, YearMonth


def test_clock_advances_without_mutating_prior_state() -> None:
    """Advancing returns a new clock and retains explicit inclusive boundaries."""
    clock = SimulationClock.create(start=YearMonth(2026, 11), months=3)

    december = clock.advance()
    january = december.advance()

    assert clock.current == YearMonth(2026, 11)
    assert clock.stop == YearMonth(2027, 1)
    assert december.current == YearMonth(2026, 12)
    assert january.current == clock.stop
    assert january.is_final_month
    with pytest.raises(ClockExhaustedError):
        january.advance()


def test_clock_rejects_invalid_bounds_and_mutation() -> None:
    """Clock construction rejects impossible ranges and instances are frozen."""
    with pytest.raises(ValueError, match="stop"):
        SimulationClock(
            start=YearMonth(2026, 2),
            stop=YearMonth(2026, 1),
            current=YearMonth(2026, 2),
        )

    clock = SimulationClock.create(start=YearMonth(2026, 1), months=1)
    with pytest.raises(FrozenInstanceError):
        clock.current = YearMonth(2026, 2)  # type: ignore[misc]


@given(
    start_year=st.integers(min_value=1900, max_value=2200),
    start_month=st.integers(min_value=1, max_value=12),
    duration=st.integers(min_value=1, max_value=1_200),
)
def test_clock_has_exact_configured_number_of_months(
    start_year: int,
    start_month: int,
    duration: int,
) -> None:
    """Inclusive clock bounds span exactly the requested number of months."""
    clock = SimulationClock.create(YearMonth(start_year, start_month), duration)

    assert clock.total_months == duration
    assert clock.stop == clock.start.add_months(duration - 1)

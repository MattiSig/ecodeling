"""Immutable monthly clock primitives for staged simulations."""

from __future__ import annotations

from dataclasses import dataclass


class ClockExhaustedError(RuntimeError):
    """Raised when code attempts to advance beyond the configured final month."""


@dataclass(frozen=True, order=True, slots=True)
class YearMonth:
    """A calendar month without an accidental day or time component."""

    year: int
    month: int

    def __post_init__(self) -> None:
        """Validate the Gregorian year and month components."""
        if self.year < 1:
            raise ValueError("year must be positive")
        if not 1 <= self.month <= 12:
            raise ValueError("month must be between 1 and 12")

    def add_months(self, offset: int) -> YearMonth:
        """Return the month at a signed offset from this month."""
        absolute_month = self.year * 12 + self.month - 1 + offset
        year, zero_based_month = divmod(absolute_month, 12)
        return YearMonth(year=year, month=zero_based_month + 1)

    def months_until(self, other: YearMonth) -> int:
        """Return the signed number of monthly steps from this month to another."""
        return (other.year - self.year) * 12 + other.month - self.month

    def __str__(self) -> str:
        """Render the canonical calendar representation."""
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True, slots=True)
class SimulationClock:
    """An immutable monthly cursor with inclusive start and stop months."""

    start: YearMonth
    stop: YearMonth
    current: YearMonth

    def __post_init__(self) -> None:
        """Require the current month to remain inside the configured interval."""
        if self.stop < self.start:
            raise ValueError("stop month must not precede start month")
        if not self.start <= self.current <= self.stop:
            raise ValueError("current month must be between start and stop")

    @classmethod
    def create(cls, start: YearMonth, months: int) -> SimulationClock:
        """Create a clock spanning exactly ``months`` inclusive calendar months."""
        if months < 1:
            raise ValueError("months must be positive")
        return cls(start=start, stop=start.add_months(months - 1), current=start)

    @property
    def total_months(self) -> int:
        """Return the total number of configured simulation months."""
        return self.start.months_until(self.stop) + 1

    @property
    def elapsed_months(self) -> int:
        """Return the zero-based index of the current month."""
        return self.start.months_until(self.current)

    @property
    def is_final_month(self) -> bool:
        """Report whether the cursor is at the inclusive stop month."""
        return self.current == self.stop

    def advance(self) -> SimulationClock:
        """Return the next clock state without mutating this instance."""
        if self.is_final_month:
            raise ClockExhaustedError(f"cannot advance beyond final month {self.stop}")
        return SimulationClock(start=self.start, stop=self.stop, current=self.current.add_months(1))

"""Property tests proving the configured Hypothesis runner is operational."""

from hypothesis import given
from hypothesis import strategies as st


@given(st.text())
def test_text_round_trip(value: str) -> None:
    """UTF-8 round trips preserve arbitrary Unicode text."""
    assert value.encode().decode() == value

"""Tests for deterministic, independent named random streams."""

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from ecodeling.randomness import NamedRandomStreams, RandomStream


@given(seed=st.integers(min_value=0, max_value=2**64 - 1))
def test_same_seed_and_name_repeat_primitive_sequence(seed: int) -> None:
    """Reconstructing a stream exactly repeats its primitive uint64 sequence."""
    first = NamedRandomStreams(seed).generator(RandomStream.SHOCKS)
    second = NamedRandomStreams(seed).generator(RandomStream.SHOCKS)

    assert np.array_equal(first.bit_generator.random_raw(32), second.bit_generator.random_raw(32))


def test_streams_are_independent_and_request_order_does_not_matter() -> None:
    """Stable name derivation isolates streams from values and lookup order."""
    streams = NamedRandomStreams(123)
    initialization = streams.generator(RandomStream.INITIALIZATION).bit_generator.random_raw(16)
    shocks = streams.generator(RandomStream.SHOCKS).bit_generator.random_raw(16)

    reversed_streams = NamedRandomStreams(123)
    reversed_shocks = reversed_streams.generator(RandomStream.SHOCKS).bit_generator.random_raw(16)
    reversed_initialization = reversed_streams.generator(
        RandomStream.INITIALIZATION
    ).bit_generator.random_raw(16)

    assert not np.array_equal(initialization, shocks)
    assert np.array_equal(initialization, reversed_initialization)
    assert np.array_equal(shocks, reversed_shocks)


def test_seeded_primitive_sequence_is_regression_stable() -> None:
    """The locked generator and derivation algorithm retain a primitive golden sequence."""
    values = NamedRandomStreams(123).generator(RandomStream.SHOCKS).bit_generator.random_raw(5)

    assert values.tolist() == [
        11945417327296255645,
        3157638039082764628,
        2315230429338035115,
        10484011189345292908,
        3038562778398489809,
    ]

"""Order-independent deterministic random streams derived from one seed."""

from __future__ import annotations

import hashlib
from enum import StrEnum

import numpy as np
from numpy.random import PCG64, Generator, SeedSequence


class RandomStream(StrEnum):
    """Stable stream names for stochastic model mechanisms."""

    INITIALIZATION = "initialization"
    LABOR_MATCHING = "labor_matching"
    CONSUMPTION_MATCHING = "consumption_matching"
    SHOCKS = "shocks"
    DEFAULTS = "defaults"
    BEHAVIORAL_NOISE = "behavioral_noise"


class NamedRandomStreams:
    """Derive fresh, reproducible NumPy generators from stable stream names."""

    def __init__(self, master_seed: int) -> None:
        """Validate and retain an unsigned 64-bit master seed."""
        if not 0 <= master_seed <= 2**64 - 1:
            raise ValueError("master_seed must be an unsigned 64-bit integer")
        self._master_seed = master_seed

    @property
    def master_seed(self) -> int:
        """Return the seed from which every named stream is derived."""
        return self._master_seed

    def generator(self, stream: RandomStream) -> Generator:
        """Return a fresh generator at the deterministic start of ``stream``."""
        digest = hashlib.sha256(f"ecodeling:{stream.value}".encode()).digest()
        name_entropy = np.frombuffer(digest, dtype="<u4")
        entropy = [
            self._master_seed & 0xFFFF_FFFF,
            self._master_seed >> 32,
            *(int(word) for word in name_entropy),
        ]
        return Generator(PCG64(SeedSequence(entropy)))

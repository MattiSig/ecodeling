"""Opaque identifier types used across model and persistence boundaries."""

from typing import NewType

AgentId = NewType("AgentId", str)
"""Identifier for any economic agent."""

AccountId = NewType("AccountId", str)
"""Identifier for a ledger account."""

LedgerEntryId = NewType("LedgerEntryId", str)
"""Identifier for an immutable transaction or revaluation journal entry."""

ContractId = NewType("ContractId", str)
"""Identifier for an economic contract."""

RunId = NewType("RunId", str)
"""Identifier for one reproducible model run."""

ScenarioId = NewType("ScenarioId", str)
"""Identifier for a scenario definition."""

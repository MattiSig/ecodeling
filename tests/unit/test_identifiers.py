"""Tests for domain-specific identifier types."""

from ecodeling.identifiers import (
    AccountId,
    AgentId,
    ContractId,
    ReferenceIndexId,
    RunId,
    ScenarioId,
)


def test_identifier_constructors_preserve_external_values() -> None:
    """Typed identifiers remain stable strings at persistence boundaries."""
    assert AgentId("household-1") == "household-1"
    assert AccountId("deposit-1") == "deposit-1"
    assert ContractId("mortgage-1") == "mortgage-1"
    assert ReferenceIndexId("cpi") == "cpi"
    assert RunId("run-1") == "run-1"
    assert ScenarioId("indexed") == "indexed"

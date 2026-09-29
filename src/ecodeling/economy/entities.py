"""Typed firms and workers for the endogenous real-economy simulation."""

from dataclasses import dataclass

from ecodeling.accounting import ISK
from ecodeling.identifiers import AgentId


@dataclass(frozen=True, slots=True)
class WorkerHousehold:
    """A household supplying at most one unit of labor per month."""

    id: AgentId
    opening_deposits: ISK


@dataclass(frozen=True, slots=True)
class Firm:
    """A producer with explicit technology, capacity, pricing, and cash."""

    id: AgentId
    productivity_units_per_worker: int
    capacity_units: int
    opening_wage: ISK
    opening_price: ISK
    markup_bps: int
    opening_deposits: ISK

"""Options data models."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class Greeks:
    """Option Greeks."""

    delta: float
    gamma: float
    theta: float
    vega: float
    implied_volatility: float
    rho: float | None = None


@dataclass
class OptionContract:
    """Single option contract."""

    code: str
    strike_price: float
    option_type: OptionType
    expiration: date
    underlying: str = "SPX"
    greeks: Greeks | None = None
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    mid: float | None = None
    volume: int | None = None
    open_interest: int | None = None


@dataclass
class OptionsChain:
    """Options chain for an underlying."""

    underlying: str
    underlying_price: float
    expiration: date
    contracts: list[OptionContract] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    def get_calls(self) -> list[OptionContract]:
        return [c for c in self.contracts if c.option_type == OptionType.CALL]

    def get_puts(self) -> list[OptionContract]:
        return [c for c in self.contracts if c.option_type == OptionType.PUT]

    def find_by_delta(
        self, target_delta: float, option_type: OptionType, tolerance: float = 0.05
    ) -> OptionContract | None:
        candidates = (
            self.get_calls() if option_type == OptionType.CALL else self.get_puts()
        )
        candidates = [c for c in candidates if c.greeks is not None]
        if not candidates:
            return None

        def delta_diff(c: OptionContract) -> float:
            return (
                abs(abs(c.greeks.delta) - abs(target_delta))
                if c.greeks
                else float("inf")
            )

        best = min(candidates, key=delta_diff)
        return best if delta_diff(best) <= tolerance else None

    def find_atm(self, option_type: OptionType) -> OptionContract | None:
        candidates = (
            self.get_calls() if option_type == OptionType.CALL else self.get_puts()
        )
        if not candidates:
            return None
        return min(
            candidates, key=lambda c: abs(c.strike_price - self.underlying_price)
        )

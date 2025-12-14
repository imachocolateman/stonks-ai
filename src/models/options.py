"""Options data models."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class OptionType(str, Enum):
    """Option type."""

    CALL = "call"
    PUT = "put"


class Greeks(BaseModel):
    """Option Greeks for risk analysis."""

    delta: float = Field(..., ge=-1, le=1, description="Delta")
    gamma: float = Field(..., ge=0, description="Gamma")
    theta: float = Field(..., description="Theta (time decay)")
    vega: float = Field(..., ge=0, description="Vega")
    rho: float | None = Field(default=None, description="Rho")
    implied_volatility: float = Field(..., ge=0, description="IV as decimal")


class OptionContract(BaseModel):
    """Single option contract."""

    code: str = Field(..., description="Moomoo option code")
    underlying: str = Field(default="SPX", description="Underlying symbol")
    strike_price: float = Field(..., gt=0, description="Strike price")
    option_type: OptionType = Field(..., description="Call or put")
    expiration: date = Field(..., description="Expiration date")

    # Greeks (may be None if not fetched)
    greeks: Greeks | None = Field(default=None, description="Option Greeks")

    # Pricing
    bid: float | None = Field(default=None, ge=0, description="Bid price")
    ask: float | None = Field(default=None, ge=0, description="Ask price")
    last: float | None = Field(default=None, ge=0, description="Last trade price")
    mid: float | None = Field(default=None, ge=0, description="Mid price")

    # Volume/interest
    volume: int | None = Field(default=None, ge=0, description="Today's volume")
    open_interest: int | None = Field(default=None, ge=0, description="Open interest")

    @property
    def spread(self) -> float | None:
        """Bid-ask spread."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def spread_pct(self) -> float | None:
        """Spread as percentage of mid."""
        if self.spread is not None and self.mid and self.mid > 0:
            return (self.spread / self.mid) * 100
        return None


class OptionsChain(BaseModel):
    """Options chain for an underlying."""

    underlying: str = Field(..., description="Underlying symbol")
    underlying_price: float = Field(..., gt=0, description="Current underlying price")
    expiration: date = Field(..., description="Expiration date")
    contracts: list[OptionContract] = Field(default_factory=list, description="Option contracts")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="Fetch timestamp")

    def get_calls(self) -> list[OptionContract]:
        """Get all call options."""
        return [c for c in self.contracts if c.option_type == OptionType.CALL]

    def get_puts(self) -> list[OptionContract]:
        """Get all put options."""
        return [c for c in self.contracts if c.option_type == OptionType.PUT]

    def find_by_delta(
        self,
        target_delta: float,
        option_type: OptionType,
        tolerance: float = 0.05,
    ) -> OptionContract | None:
        """Find contract closest to target delta."""
        candidates = self.get_calls() if option_type == OptionType.CALL else self.get_puts()
        candidates = [c for c in candidates if c.greeks is not None]

        if not candidates:
            return None

        # For puts, delta is negative, so compare absolute values
        def delta_diff(c: OptionContract) -> float:
            if c.greeks is None:
                return float("inf")
            return abs(abs(c.greeks.delta) - abs(target_delta))

        best = min(candidates, key=delta_diff)
        if delta_diff(best) <= tolerance:
            return best
        return None

    def find_atm(self, option_type: OptionType) -> OptionContract | None:
        """Find at-the-money contract."""
        candidates = self.get_calls() if option_type == OptionType.CALL else self.get_puts()
        if not candidates:
            return None

        return min(candidates, key=lambda c: abs(c.strike_price - self.underlying_price))

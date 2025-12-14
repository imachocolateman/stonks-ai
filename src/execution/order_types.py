"""Order and position data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from src.models.options import OptionType
from src.models.suggestions import TradeSuggestion, TradeType


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CLOSING = "closing"


@dataclass
class Fill:
    """Order fill/execution details."""

    order_id: str
    quantity: int
    price: float
    fill_id: str = field(default_factory=lambda: str(uuid4())[:8])
    filled_at: datetime = field(default_factory=datetime.utcnow)
    commission: float = 0.0
    broker_fill_id: str | None = None


@dataclass
class Order:
    """Trade order."""

    option_code: str
    strike: float
    option_type: OptionType
    trade_type: TradeType
    side: OrderSide
    quantity: int
    order_id: str = field(default_factory=lambda: str(uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    suggestion_id: str | None = None
    underlying: str = "SPX"
    order_type: OrderType = OrderType.LIMIT
    limit_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    stop_loss_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING_APPROVAL
    status_reason: str | None = None
    filled_quantity: int = 0
    avg_fill_price: float | None = None
    fills: list[Fill] = field(default_factory=list)
    broker_order_id: str | None = None
    submitted_at: datetime | None = None
    parent_order_id: str | None = None
    stop_order_id: str | None = None
    target_order_id: str | None = None

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        return self.status in (
            OrderStatus.PENDING_APPROVAL,
            OrderStatus.APPROVED,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIAL_FILL,
        )

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    def add_fill(self, fill: Fill) -> None:
        self.fills.append(fill)
        self.filled_quantity += fill.quantity
        self.updated_at = datetime.utcnow()
        total_cost = sum(f.price * f.quantity for f in self.fills)
        total_qty = sum(f.quantity for f in self.fills)
        self.avg_fill_price = total_cost / total_qty if total_qty > 0 else None
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIAL_FILL

    @classmethod
    def from_suggestion(cls, suggestion: TradeSuggestion) -> "Order":
        if not suggestion.contracts:
            raise ValueError("Suggestion has no contracts")
        contract = suggestion.contracts[0]
        return cls(
            suggestion_id=suggestion.id,
            option_code=contract.code,
            underlying=contract.underlying,
            strike=contract.strike_price,
            option_type=contract.option_type,
            trade_type=suggestion.trade_type,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=suggestion.quantity,
            limit_price=suggestion.entry_price,
            target_price=suggestion.target_price,
            stop_loss_price=suggestion.stop_loss,
        )


@dataclass
class Position:
    """Open position."""

    option_code: str
    strike: float
    option_type: OptionType
    trade_type: TradeType
    quantity: int
    entry_price: float
    entry_order_id: str
    position_id: str = field(default_factory=lambda: str(uuid4())[:8])
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    underlying: str = "SPX"
    status: PositionStatus = PositionStatus.OPEN
    target_price: float | None = None
    stop_loss_price: float | None = None
    exit_price: float | None = None
    exit_order_id: str | None = None
    closed_at: datetime | None = None
    stop_order_id: str | None = None
    target_order_id: str | None = None
    suggestion_id: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status == PositionStatus.OPEN

    def realized_pnl(self) -> float | None:
        if self.exit_price is None:
            return None
        return (self.exit_price - self.entry_price) * self.quantity * 100

    def realized_pnl_percent(self) -> float | None:
        if self.exit_price is None or self.entry_price <= 0:
            return None
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100

    @classmethod
    def from_filled_order(cls, order: Order) -> "Position":
        if not order.is_filled or order.avg_fill_price is None:
            raise ValueError("Order must be filled")
        return cls(
            option_code=order.option_code,
            underlying=order.underlying,
            strike=order.strike,
            option_type=order.option_type,
            trade_type=order.trade_type,
            quantity=order.filled_quantity,
            entry_price=order.avg_fill_price,
            entry_order_id=order.order_id,
            target_price=order.target_price,
            stop_loss_price=order.stop_loss_price,
            suggestion_id=order.suggestion_id,
        )

    def close(self, exit_price: float, exit_order_id: str) -> None:
        self.exit_price = exit_price
        self.exit_order_id = exit_order_id
        self.closed_at = datetime.utcnow()
        self.status = PositionStatus.CLOSED
        self.updated_at = datetime.utcnow()

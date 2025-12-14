"""Order lifecycle management with manual approval flow."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from src.config import get_settings
from src.execution.order_types import Fill, Order, OrderSide, OrderStatus, Position
from src.models.suggestions import TradeSuggestion
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.execution.executor import MoomooExecutor


class OrderManager:
    """Manages order lifecycle with manual approval flow."""

    def __init__(self, executor: "MoomooExecutor | None" = None):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.executor = executor
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}

    @property
    def orders(self) -> list[Order]:
        return list(self._orders.values())

    @property
    def positions(self) -> list[Position]:
        return list(self._positions.values())

    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self._positions.values() if p.is_open]

    @property
    def active_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if o.is_active]

    @property
    def pending_approval(self) -> list[Order]:
        return [
            o for o in self._orders.values() if o.status == OrderStatus.PENDING_APPROVAL
        ]

    def can_open_position(self) -> tuple[bool, str]:
        max_positions = self.settings.max_positions
        current = len(self.open_positions)
        if current >= max_positions:
            return False, f"Max positions ({max_positions}) reached"
        return True, ""

    def create_order_from_suggestion(self, suggestion: TradeSuggestion) -> Order | None:
        can_open, reason = self.can_open_position()
        if not can_open:
            self.logger.warning(f"Cannot create order: {reason}")
            return None

        try:
            order = Order.from_suggestion(suggestion)
            self._orders[order.order_id] = order
            self.logger.info(
                f"ORDER PENDING: {order.order_id} | {order.side.value} {order.trade_type.value} | "
                f"{order.option_code} | qty={order.quantity} @ ${order.limit_price}"
            )
            return order
        except Exception as e:
            self.logger.error(f"Failed to create order: {e}")
            return None

    def approve_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order:
            self.logger.error(f"Order not found: {order_id}")
            return False
        if order.status != OrderStatus.PENDING_APPROVAL:
            self.logger.warning(f"Order {order_id} not pending: {order.status}")
            return False

        order.status = OrderStatus.APPROVED
        order.updated_at = datetime.utcnow()
        self.logger.info(f"ORDER APPROVED: {order_id}")
        return True

    def reject_order(self, order_id: str, reason: str = "User rejected") -> bool:
        order = self._orders.get(order_id)
        if not order:
            self.logger.error(f"Order not found: {order_id}")
            return False

        order.status = OrderStatus.CANCELLED
        order.status_reason = reason
        order.updated_at = datetime.utcnow()
        self.logger.info(f"ORDER REJECTED: {order_id} - {reason}")
        return True

    async def submit_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order:
            self.logger.error(f"Order not found: {order_id}")
            return False
        if order.status != OrderStatus.APPROVED:
            self.logger.warning(f"Order {order_id} not approved: {order.status}")
            return False
        if not self.executor:
            self.logger.error("No executor configured")
            order.status = OrderStatus.REJECTED
            order.status_reason = "No executor"
            return False

        try:
            broker_order_id = await self.executor.submit_order(order)
            if broker_order_id:
                order.broker_order_id = broker_order_id
                order.status = OrderStatus.SUBMITTED
                order.submitted_at = datetime.utcnow()
                order.updated_at = datetime.utcnow()
                self.logger.info(f"ORDER SUBMITTED: {order_id} → {broker_order_id}")
                return True
            else:
                order.status = OrderStatus.REJECTED
                order.status_reason = "Broker rejected"
                order.updated_at = datetime.utcnow()
                self.logger.error(f"ORDER REJECTED by broker: {order_id}")
                return False
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.status_reason = str(e)
            order.updated_at = datetime.utcnow()
            self.logger.error(f"ORDER FAILED: {order_id} - {e}")
            return False

    def record_fill(self, order_id: str, fill: Fill) -> Position | None:
        order = self._orders.get(order_id)
        if not order:
            self.logger.error(f"Order not found for fill: {order_id}")
            return None

        order.add_fill(fill)
        self.logger.info(f"FILL: {fill.quantity}x @ ${fill.price} for {order_id}")

        if order.is_filled and order.side == OrderSide.BUY:
            position = Position.from_filled_order(order)
            self._positions[position.position_id] = position
            self.logger.info(
                f"POSITION OPENED: {position.position_id} | {position.option_code} | "
                f"qty={position.quantity} @ ${position.entry_price}"
            )
            return position
        return None

    def close_position(
        self, position_id: str, exit_price: float, exit_order_id: str
    ) -> bool:
        position = self._positions.get(position_id)
        if not position:
            self.logger.error(f"Position not found: {position_id}")
            return False

        position.close(exit_price, exit_order_id)
        pnl = position.realized_pnl()
        self.logger.info(
            f"POSITION CLOSED: {position_id} | exit=${exit_price} | P&L=${pnl:+,.2f}"
            if pnl
            else f"POSITION CLOSED: {position_id} | exit=${exit_price}"
        )
        return True

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_position(self, position_id: str) -> Position | None:
        return self._positions.get(position_id)

    def find_position_by_option(self, option_code: str) -> Position | None:
        for p in self._positions.values():
            if p.option_code == option_code and p.is_open:
                return p
        return None

"""Position tracking and auto-exit management."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.config import get_settings
from src.execution.order_types import Order, OrderSide, OrderStatus, OrderType, Position
from src.utils.logger import get_logger
from src.utils.time_utils import (
    SessionPhase,
    get_session_phase,
    minutes_to_exit_deadline,
)

if TYPE_CHECKING:
    from src.execution.executor import MoomooExecutor
    from src.execution.order_manager import OrderManager


class PositionTracker:
    """Tracks open positions and handles auto-exit at 3:45 PM."""

    def __init__(
        self, order_manager: "OrderManager", executor: "MoomooExecutor | None" = None
    ):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.order_manager = order_manager
        self.executor = executor
        self.auto_exit_enabled = True
        self._daily_pnl: float = 0.0
        self._daily_trades: int = 0
        self._daily_wins: int = 0
        self._monitor_task: asyncio.Task | None = None
        self._running = False

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def daily_win_rate(self) -> float:
        return self._daily_wins / self._daily_trades if self._daily_trades else 0.0

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Position monitoring started")

    def stop_monitoring(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        self.logger.info("Position monitoring stopped")

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                phase = get_session_phase()
                if phase == SessionPhase.DANGER_ZONE and self.auto_exit_enabled:
                    await self._execute_auto_exit()

                mins = minutes_to_exit_deadline()
                if mins is not None and mins <= 5:
                    positions = self.order_manager.open_positions
                    if positions:
                        self.logger.warning(
                            f"EXIT DEADLINE: {mins}min - {len(positions)} positions"
                        )

                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
                await asyncio.sleep(5)

    async def _execute_auto_exit(self) -> None:
        positions = self.order_manager.open_positions
        if not positions:
            return

        self.logger.warning(f"DANGER ZONE: Auto-closing {len(positions)} positions")
        for position in positions:
            await self.close_position_market(position)

    async def close_position_market(self, position: Position) -> bool:
        if not position.is_open:
            return False

        self.logger.info(f"Closing position {position.position_id} at market")
        exit_order = Order(
            option_code=position.option_code,
            underlying=position.underlying,
            strike=position.strike,
            option_type=position.option_type,
            trade_type=position.trade_type,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=position.quantity,
            status=OrderStatus.APPROVED,
        )

        self.order_manager._orders[exit_order.order_id] = exit_order
        position.exit_order_id = exit_order.order_id
        position.status = "closing"

        if self.executor:
            success = await self.order_manager.submit_order(exit_order.order_id)
            if success:
                self.logger.info(f"Exit order submitted: {position.position_id}")
                return True
            self.logger.error(f"Exit order failed: {position.position_id}")
            return False
        else:
            self.logger.warning(
                f"No executor - manual exit required: {position.position_id}"
            )
            return False

    def record_closed_position(self, position: Position) -> None:
        pnl = position.realized_pnl()
        if pnl is not None:
            self._daily_pnl += pnl
            self._daily_trades += 1
            if pnl > 0:
                self._daily_wins += 1
            self.logger.info(f"P&L: ${pnl:+,.2f} | Daily: ${self._daily_pnl:+,.2f}")

    def reset_daily_stats(self) -> None:
        self._daily_pnl = 0.0
        self._daily_trades = 0
        self._daily_wins = 0
        self.logger.info("Daily stats reset")

    def get_daily_summary(self) -> dict:
        return {
            "pnl": self._daily_pnl,
            "trades": self._daily_trades,
            "wins": self._daily_wins,
            "losses": self._daily_trades - self._daily_wins,
            "win_rate": self.daily_win_rate,
        }

    def check_daily_loss_limit(self) -> tuple[bool, str]:
        max_loss = self.settings.account_size * self.settings.max_daily_risk
        if self._daily_pnl <= -max_loss:
            return True, f"Daily loss limit hit: ${self._daily_pnl:,.2f}"
        return False, ""

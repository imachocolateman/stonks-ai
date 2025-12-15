"""Moomoo trade API wrapper for order execution."""

from datetime import datetime

from moomoo import (
    OrderType as MooOrderType,
    RET_OK,
    SecurityFirm,
    TrdSide,
    TrdEnv,
    TrdMarket,
    OpenSecTradeContext,
)

from src.config import get_settings
from src.execution.order_types import (
    Fill,
    Order,
    OrderSide,
    OrderType,
)
from src.utils.logger import get_logger


class MoomooExecutor:
    """
    Executes trades via Moomoo OpenD trade API.

    Supports paper trading (SIMULATE) and live trading (REAL).
    """

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self._trade_ctx: OpenSecTradeContext | None = None
        self._trade_env = (
            TrdEnv.SIMULATE
            if self.settings.moomoo_trading_env == "SIMULATE"
            else TrdEnv.REAL
        )

    @property
    def is_paper_trading(self) -> bool:
        return self._trade_env == TrdEnv.SIMULATE

    def connect(self) -> bool:
        """Connect to Moomoo trade API."""
        try:
            self._trade_ctx = OpenSecTradeContext(
                host=self.settings.moomoo_host,
                port=self.settings.moomoo_port,
                security_firm=SecurityFirm.FUTUINC,
                filter_trdmarket=TrdMarket.US,
            )
            self.logger.info(
                f"Connected to Moomoo Trade API "
                f"(env: {self.settings.moomoo_trading_env})"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Moomoo Trade API: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Moomoo trade API."""
        if self._trade_ctx:
            self._trade_ctx.close()
            self._trade_ctx = None
            self.logger.info("Disconnected from Moomoo Trade API")

    def _ensure_connected(self) -> bool:
        """Ensure trade context is connected."""
        if self._trade_ctx is None:
            return self.connect()
        return True

    def _map_order_type(self, order_type: OrderType) -> MooOrderType:
        """Map our order type to Moomoo order type."""
        mapping = {
            OrderType.MARKET: MooOrderType.MARKET,
            OrderType.LIMIT: MooOrderType.NORMAL,  # NORMAL = limit order
            OrderType.STOP: MooOrderType.STOP,
            OrderType.STOP_LIMIT: MooOrderType.STOP_LIMIT,
        }
        return mapping.get(order_type, MooOrderType.NORMAL)

    def _map_trade_side(self, side: OrderSide) -> TrdSide:
        """Map our order side to Moomoo trade side."""
        return TrdSide.BUY if side == OrderSide.BUY else TrdSide.SELL

    async def submit_order(self, order: Order) -> str | None:
        """
        Submit an order to Moomoo.

        Returns broker order ID on success, None on failure.
        """
        if not self._ensure_connected():
            self.logger.error("Not connected to Moomoo Trade API")
            return None

        try:
            # Unlock trade (required for placing orders)
            # In production, use actual unlock password from env
            unlock_pwd = self.settings.moomoo_api_secret or ""
            if self._trade_env == TrdEnv.REAL:
                ret, data = self._trade_ctx.unlock_trade(unlock_pwd)
                if ret != RET_OK:
                    self.logger.error(f"Failed to unlock trade: {data}")
                    return None

            # Map order parameters
            moo_order_type = self._map_order_type(order.order_type)
            moo_side = self._map_trade_side(order.side)

            # Place order
            ret, data = self._trade_ctx.place_order(
                price=order.limit_price or 0,
                qty=order.quantity,
                code=order.option_code,
                trd_side=moo_side,
                order_type=moo_order_type,
                trd_env=self._trade_env,
                adjust_limit=0.05,  # Allow 5% price adjustment for fills
            )

            if ret == RET_OK:
                broker_order_id = str(data["order_id"].iloc[0])
                self.logger.info(
                    f"Order placed: {order.order_id} → broker {broker_order_id}"
                )
                return broker_order_id
            else:
                self.logger.error(f"Failed to place order: {data}")
                return None

        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")
            return None

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order by broker order ID."""
        if not self._ensure_connected():
            return False

        try:
            ret, data = self._trade_ctx.cancel_order(
                order_id=int(broker_order_id),
                trd_env=self._trade_env,
            )

            if ret == RET_OK:
                self.logger.info(f"Order cancelled: {broker_order_id}")
                return True
            else:
                self.logger.error(f"Failed to cancel order: {data}")
                return False

        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False

    async def get_order_status(self, broker_order_id: str) -> dict | None:
        """Get current status of an order."""
        if not self._ensure_connected():
            return None

        try:
            ret, data = self._trade_ctx.order_list_query(
                order_id=int(broker_order_id),
                trd_env=self._trade_env,
            )

            if ret == RET_OK and not data.empty:
                row = data.iloc[0]
                return {
                    "order_id": str(row.get("order_id")),
                    "status": str(row.get("order_status")),
                    "filled_qty": int(row.get("dealt_qty", 0)),
                    "avg_price": float(row.get("dealt_avg_price", 0)),
                    "create_time": row.get("create_time"),
                    "update_time": row.get("updated_time"),
                }
            return None

        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            return None

    async def get_fills(self, broker_order_id: str) -> list[Fill]:
        """Get fills for an order."""
        if not self._ensure_connected():
            return []

        try:
            ret, data = self._trade_ctx.deal_list_query(
                trd_env=self._trade_env,
            )

            if ret != RET_OK:
                self.logger.error(f"Failed to query deals: {data}")
                return []

            fills = []
            for _, row in data.iterrows():
                if str(row.get("order_id")) == broker_order_id:
                    fill = Fill(
                        order_id=broker_order_id,
                        quantity=int(row.get("qty", 0)),
                        price=float(row.get("price", 0)),
                        broker_fill_id=str(row.get("deal_id")),
                        filled_at=datetime.utcnow(),  # Would parse from row
                    )
                    fills.append(fill)

            return fills

        except Exception as e:
            self.logger.error(f"Error getting fills: {e}")
            return []

    async def get_positions(self) -> list[dict]:
        """Get all current positions from broker."""
        if not self._ensure_connected():
            return []

        try:
            ret, data = self._trade_ctx.position_list_query(
                trd_env=self._trade_env,
            )

            if ret != RET_OK:
                self.logger.error(f"Failed to query positions: {data}")
                return []

            positions = []
            for _, row in data.iterrows():
                pos = {
                    "code": str(row.get("code")),
                    "qty": int(row.get("qty", 0)),
                    "cost_price": float(row.get("cost_price", 0)),
                    "market_val": float(row.get("market_val", 0)),
                    "pl_val": float(row.get("pl_val", 0)),
                    "pl_ratio": float(row.get("pl_ratio", 0)),
                }
                positions.append(pos)

            return positions

        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []

    async def get_account_balance(self) -> dict | None:
        """Get account balance and buying power."""
        if not self._ensure_connected():
            return None

        try:
            ret, data = self._trade_ctx.accinfo_query(
                trd_env=self._trade_env,
            )

            if ret == RET_OK and not data.empty:
                row = data.iloc[0]
                
                def safe_float(val):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0.0

                return {
                    "cash": safe_float(row.get("cash")),
                    "total_assets": safe_float(row.get("total_assets")),
                    "market_val": safe_float(row.get("market_val")),
                    "frozen_cash": safe_float(row.get("frozen_cash")),
                    "available_funds": safe_float(row.get("available_funds")),
                }
            return None

        except Exception as e:
            self.logger.error(f"Error getting account balance: {e}")
            return None

    async def test_connection(self) -> dict:
        """Test trade API connection and return status."""
        result = {
            "connected": False,
            "environment": self.settings.moomoo_trading_env,
            "host": self.settings.moomoo_host,
            "port": self.settings.moomoo_port,
            "error": None,
        }

        try:
            if self.connect():
                result["connected"] = True

                # Try to get account info
                balance = await self.get_account_balance()
                if balance:
                    result["account"] = balance
            else:
                result["error"] = "Connection failed"

        except Exception as e:
            result["error"] = str(e)
        finally:
            self.disconnect()

        return result

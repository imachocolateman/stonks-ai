"""Moomoo OpenD API client for options data."""

from datetime import date, datetime
from typing import Any

import yfinance as yf
from moomoo import (
    Market,
    OptionCondType,
    OptionType as MooOptionType,
    OpenQuoteContext,
    RET_ERROR,
    RET_OK,
)

from src.config import get_settings
from src.models.options import Greeks, OptionContract, OptionsChain, OptionType
from src.utils.logger import get_logger


class MoomooClient:
    """Wrapper for Moomoo OpenD API for options data, with yfinance for SPX index."""

    # Yahoo Finance symbol for S&P 500 index
    SPX_YF_SYMBOL = "^GSPC"

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self._quote_ctx: OpenQuoteContext | None = None

    def connect(self) -> bool:
        """Connect to Moomoo OpenD."""
        try:
            self._quote_ctx = OpenQuoteContext(
                host=self.settings.moomoo_host,
                port=self.settings.moomoo_port,
            )
            self.logger.info(
                f"Connected to Moomoo OpenD at "
                f"{self.settings.moomoo_host}:{self.settings.moomoo_port}"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Moomoo OpenD: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Moomoo OpenD."""
        if self._quote_ctx:
            self._quote_ctx.close()
            self._quote_ctx = None
            self.logger.info("Disconnected from Moomoo OpenD")

    def _ensure_connected(self) -> bool:
        """Ensure connection is active."""
        if self._quote_ctx is None:
            return self.connect()
        return True

    def get_spx_price(self) -> float | None:
        """Get current SPX index price via Yahoo Finance."""
        try:
            ticker = yf.Ticker(self.SPX_YF_SYMBOL)
            # Get latest price from fast_info or history
            price = ticker.fast_info.get("lastPrice")
            if price:
                self.logger.debug(f"SPX price from yfinance: {price}")
                return float(price)

            # Fallback to history if fast_info doesn't have it
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                self.logger.debug(f"SPX price from history: {price}")
                return price

            self.logger.error("Failed to get SPX price from yfinance")
            return None
        except Exception as e:
            self.logger.error(f"Error getting SPX price: {e}")
            return None

    def get_spx_history(
        self,
        period: str = "1mo",
        interval: str = "1d",
    ) -> "pd.DataFrame | None":
        """
        Get SPX historical data for backtesting.

        Args:
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo)

        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            import pandas as pd

            ticker = yf.Ticker(self.SPX_YF_SYMBOL)
            hist = ticker.history(period=period, interval=interval)
            if not hist.empty:
                self.logger.info(f"Fetched {len(hist)} bars of SPX history ({period}/{interval})")
                return hist
            return None
        except Exception as e:
            self.logger.error(f"Error getting SPX history: {e}")
            return None

    def get_options_chain(
        self,
        underlying: str = "US.SPX",
        expiration: date | None = None,
        option_type: str = "ALL",
        delta_min: float | None = None,
        delta_max: float | None = None,
    ) -> OptionsChain | None:
        """
        Fetch options chain for underlying.

        Args:
            underlying: Symbol (default US.SPX)
            expiration: Expiration date (default today for 0DTE)
            option_type: "CALL", "PUT", or "ALL"
            delta_min: Minimum delta filter
            delta_max: Maximum delta filter

        Returns:
            OptionsChain or None if failed
        """
        if not self._ensure_connected():
            return None

        # Default to today for 0DTE
        if expiration is None:
            expiration = date.today()

        try:
            # Get current underlying price
            underlying_price = self.get_spx_price()
            if underlying_price is None:
                return None

            # Get option expiration dates first
            ret, exp_data = self._quote_ctx.get_option_expiration_date(underlying)
            if ret != RET_OK:
                self.logger.error(f"Failed to get expiration dates: {exp_data}")
                return None

            # Find matching expiration
            exp_str = expiration.strftime("%Y-%m-%d")
            if exp_str not in exp_data["strike_time"].values:
                self.logger.warning(f"No options for expiration {exp_str}")
                # Use nearest expiration
                dates = exp_data["strike_time"].tolist()
                if dates:
                    exp_str = dates[0]
                    self.logger.info(f"Using nearest expiration: {exp_str}")
                else:
                    return None

            # Map option type
            opt_type_filter = None
            if option_type == "CALL":
                opt_type_filter = MooOptionType.CALL
            elif option_type == "PUT":
                opt_type_filter = MooOptionType.PUT

            # Get option chain
            ret, chain_data = self._quote_ctx.get_option_chain(
                underlying,
                index_option_type=Market.US,
                start=exp_str,
                end=exp_str,
                option_type=opt_type_filter,
                option_cond_type=OptionCondType.ALL,
            )

            if ret != RET_OK:
                self.logger.error(f"Failed to get option chain: {chain_data}")
                return None

            # Convert to our models
            contracts = []
            for _, row in chain_data.iterrows():
                contract = self._parse_option_contract(row, expiration)
                if contract:
                    # Apply delta filter if specified
                    if delta_min is not None or delta_max is not None:
                        if contract.greeks is None:
                            continue
                        delta = abs(contract.greeks.delta)
                        if delta_min is not None and delta < delta_min:
                            continue
                        if delta_max is not None and delta > delta_max:
                            continue
                    contracts.append(contract)

            return OptionsChain(
                underlying=underlying,
                underlying_price=underlying_price,
                expiration=expiration,
                contracts=contracts,
                fetched_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(f"Error getting options chain: {e}")
            return None

    def _parse_option_contract(
        self,
        row: Any,
        expiration: date,
    ) -> OptionContract | None:
        """Parse Moomoo option data row to OptionContract."""
        try:
            # Determine option type from code
            code = str(row.get("code", ""))
            opt_type = OptionType.CALL if "C" in code.upper() else OptionType.PUT

            # Parse Greeks if available
            greeks = None
            if all(
                col in row.index
                for col in ["option_delta", "option_gamma", "option_theta", "option_vega"]
            ):
                greeks = Greeks(
                    delta=float(row.get("option_delta", 0)),
                    gamma=float(row.get("option_gamma", 0)),
                    theta=float(row.get("option_theta", 0)),
                    vega=float(row.get("option_vega", 0)),
                    implied_volatility=float(row.get("option_implied_volatility", 0)),
                )

            return OptionContract(
                code=code,
                underlying="SPX",
                strike_price=float(row.get("strike_price", 0)),
                option_type=opt_type,
                expiration=expiration,
                greeks=greeks,
                bid=float(row.get("bid_price", 0)) if row.get("bid_price") else None,
                ask=float(row.get("ask_price", 0)) if row.get("ask_price") else None,
                last=float(row.get("last_price", 0)) if row.get("last_price") else None,
                volume=int(row.get("volume", 0)) if row.get("volume") else None,
                open_interest=int(row.get("open_interest", 0)) if row.get("open_interest") else None,
            )
        except Exception as e:
            self.logger.debug(f"Failed to parse option contract: {e}")
            return None

    def get_option_quote(self, option_code: str) -> OptionContract | None:
        """Get quote for a single option contract."""
        if not self._ensure_connected():
            return None

        try:
            ret, data = self._quote_ctx.get_market_snapshot([option_code])
            if ret == RET_OK and not data.empty:
                row = data.iloc[0]
                # Parse basic quote data
                return OptionContract(
                    code=option_code,
                    underlying="SPX",
                    strike_price=float(row.get("strike_price", 0)),
                    option_type=OptionType.CALL if row.get("option_type") == "CALL" else OptionType.PUT,
                    expiration=date.today(),  # Would need to parse from code
                    bid=float(row.get("bid_price", 0)) if row.get("bid_price") else None,
                    ask=float(row.get("ask_price", 0)) if row.get("ask_price") else None,
                    last=float(row.get("last_price", 0)) if row.get("last_price") else None,
                    volume=int(row.get("volume", 0)) if row.get("volume") else None,
                )
            else:
                self.logger.error(f"Failed to get option quote: {data}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting option quote: {e}")
            return None

    def test_connection(self) -> dict:
        """Test connection and return status info."""
        result = {
            "moomoo_connected": False,
            "host": self.settings.moomoo_host,
            "port": self.settings.moomoo_port,
            "spx_price": None,
            "spx_source": "yfinance",
            "error": None,
        }

        # Test SPX price via yfinance (doesn't need Moomoo)
        try:
            price = self.get_spx_price()
            if price:
                result["spx_price"] = price
        except Exception as e:
            result["error"] = f"yfinance error: {e}"

        # Test Moomoo connection for options
        try:
            if self.connect():
                result["moomoo_connected"] = True
            else:
                if result["error"]:
                    result["error"] += "; Moomoo connection failed"
                else:
                    result["error"] = "Moomoo connection failed"
        except Exception as e:
            if result["error"]:
                result["error"] += f"; Moomoo: {e}"
            else:
                result["error"] = f"Moomoo: {e}"
        finally:
            self.disconnect()

        return result

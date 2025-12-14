"""Risk management and position sizing calculations."""

from src.config import get_settings
from src.models.signals import SignalType, TradingViewSignal
from src.models.suggestions import SuggestionConfidence
from src.utils.logger import get_logger
from src.utils.time_utils import SessionPhase

logger = get_logger(__name__)


class RiskCalculator:
    """Calculate position sizing and risk metrics per strategy rules."""

    def __init__(self):
        self.settings = get_settings()

    def calculate_position_size(
        self,
        max_loss_per_contract: float,
        account_size: float | None = None,
    ) -> int:
        """
        Calculate position size based on max risk per trade.

        Per strategy doc:
        - Max risk per trade: 1-2% of account
        - Example: $25k account, 2% = $500 max risk
        - If spread max loss is $880, size = 500/880 = 0.57 = 1 contract
        """
        if account_size is None:
            account_size = self.settings.account_size

        max_risk = account_size * self.settings.max_risk_per_trade

        if max_loss_per_contract <= 0:
            logger.warning("Invalid max loss per contract")
            return 1

        size = int(max_risk / max_loss_per_contract)
        return max(1, size)  # Minimum 1 contract

    def calculate_account_risk_percent(
        self,
        max_loss: float,
        quantity: int,
        account_size: float | None = None,
    ) -> float:
        """Calculate what % of account is at risk."""
        if account_size is None:
            account_size = self.settings.account_size

        total_risk = max_loss * quantity
        return total_risk / account_size if account_size > 0 else 0

    def calculate_risk_reward(
        self,
        entry: float,
        target: float,
        stop: float,
    ) -> float:
        """
        Calculate risk/reward ratio.

        Per strategy doc: Minimum 1:1.5, ideally 1:2
        Returns the reward multiple (e.g., 1.5 means 1:1.5)
        """
        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk <= 0:
            return 0

        return reward / risk

    def calculate_targets(
        self,
        entry_price: float,
        is_credit_spread: bool = False,
        credit_received: float | None = None,
    ) -> tuple[float, float]:
        """
        Calculate profit target and stop loss.

        Per strategy doc:
        - Profit target: 50-60% of credit received (or max profit)
        - Stop loss: 2-2.5x credit received

        For long options:
        - Target: 40-50% gain
        - Stop: 25-30% loss

        Returns: (target_price, stop_loss_price)
        """
        if is_credit_spread and credit_received:
            # Credit spread: target 55% of credit, stop at 2.25x credit
            target = entry_price - (credit_received * 0.55)  # Buying back cheaper
            stop = entry_price + (credit_received * 1.25)  # Buying back at 2.25x
            return (target, stop)
        else:
            # Long option: target 45% gain, stop 27% loss
            target = entry_price * 1.45
            stop = entry_price * 0.73
            return (target, stop)

    def assess_confidence(
        self,
        signal: TradingViewSignal,
        session: SessionPhase,
        rr_ratio: float,
        spx_price: float,
    ) -> SuggestionConfidence:
        """
        Assess confidence level based on multiple factors.

        HIGH confidence requires:
        - Prime time or mid session
        - R:R >= 1.5
        - RSI confirmation (if available)
        - At support/resistance level

        MEDIUM confidence:
        - Acceptable session
        - R:R >= 1.2
        - Some confirmations

        LOW confidence:
        - Lunch doldrums
        - R:R < 1.2
        - Weak confirmations
        """
        score = 0

        # Session scoring
        if session == SessionPhase.PRIME_TIME:
            score += 3
        elif session == SessionPhase.MID_SESSION:
            score += 2
        elif session == SessionPhase.LUNCH_DOLDRUMS:
            score += 0

        # R:R scoring
        if rr_ratio >= 2.0:
            score += 3
        elif rr_ratio >= 1.5:
            score += 2
        elif rr_ratio >= 1.2:
            score += 1

        # RSI confirmation
        if signal.rsi is not None:
            if signal.signal_type in [SignalType.RSI_OVERSOLD_LONG, SignalType.V_DIP_LONG]:
                if signal.rsi <= 20:
                    score += 2
                elif signal.rsi <= 30:
                    score += 1
            elif signal.signal_type == SignalType.RSI_OVERBOUGHT_SHORT:
                if signal.rsi >= 80:
                    score += 2
                elif signal.rsi >= 70:
                    score += 1

        # Support/resistance confirmation
        if signal.pivot_level:
            score += 1

        # VWAP proximity
        if signal.vwap_distance is not None and abs(signal.vwap_distance) <= 0.5:
            score += 1

        # Determine confidence
        if score >= 7:
            return SuggestionConfidence.HIGH
        elif score >= 4:
            return SuggestionConfidence.MEDIUM
        else:
            return SuggestionConfidence.LOW

    def get_risk_warnings(
        self,
        session: SessionPhase,
        minutes_to_close: int,
        rr_ratio: float,
        account_risk_pct: float,
    ) -> list[str]:
        """Generate risk warnings based on conditions."""
        warnings = []

        # Time-based warnings
        if minutes_to_close <= 30:
            warnings.append("Less than 30 minutes to close - extreme gamma risk")
        elif minutes_to_close <= 60:
            warnings.append("Less than 1 hour to close - elevated gamma risk")

        if session == SessionPhase.LUNCH_DOLDRUMS:
            warnings.append("Lunch doldrums - lower volatility, wider spreads")

        # R:R warning
        if rr_ratio < 1.5:
            warnings.append(f"R:R ratio ({rr_ratio:.1f}) below recommended 1.5")

        # Account risk warning
        if account_risk_pct > self.settings.max_risk_per_trade:
            warnings.append(
                f"Account risk ({account_risk_pct:.1%}) exceeds max ({self.settings.max_risk_per_trade:.1%})"
            )

        return warnings

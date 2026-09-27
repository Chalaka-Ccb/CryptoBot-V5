from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.enums.order import OrderSide, OrderStatus, OrderType
from core.enums.position import PositionSide
from core.models.candle import Candle
from core.models.order import Order
from core.models.signal import SignalSide, TradingSignal

from engine.execution_engine import ExecutionEngine
from engine.position_manager import PositionManager
from engine.risk_manager import RiskManager
from engine.state import EngineState
from engine.strategy_coordinator import StrategyCoordinator
from risk.daily_drawdown import DailyDrawdownGuard


@dataclass(frozen=True)
class EngineDecision:
    symbol: str
    timeframe: Optional[str]
    signal: Optional[TradingSignal]
    order: Optional[Order]
    executed: bool
    reason: str = ""


class TradingEngine:

    def __init__(
        self,
        state: EngineState,
        strategy_coordinator: StrategyCoordinator,
        risk_manager: RiskManager,
        position_manager: PositionManager,
        execution_engine: ExecutionEngine,
        daily_drawdown_guard: DailyDrawdownGuard,
    ):
        self.state = state
        self.strategy_coordinator = strategy_coordinator
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.execution_engine = execution_engine
        self.daily_drawdown_guard = daily_drawdown_guard

    def process_symbol(
        self,
        symbol: str,
        candles_15m: list[Candle],
        candles_5m: list[Candle],
        timestamp: datetime,
    ) -> EngineDecision:

        # Rule: one active order/position per symbol.
        if self.state.symbol_is_busy(symbol):
            return EngineDecision(
                symbol=symbol,
                timeframe=None,
                signal=None,
                order=None,
                executed=False,
                reason="Symbol already has an active order or position",
            )

        # Global daily drawdown protection.
        drawdown_status = self.daily_drawdown_guard.check(
            current_balance=self.state.account.balance,
            timestamp=timestamp,
        )

        if drawdown_status.triggered:
            return EngineDecision(
                symbol=symbol,
                timeframe=None,
                signal=None,
                order=None,
                executed=False,
                reason="Daily drawdown limit reached",
            )

        # 15m gets priority. 5m is checked only if 15m has no signal.
        evaluation = self.strategy_coordinator.evaluate(
            candles_15m=candles_15m,
            candles_5m=candles_5m,
        )

        if evaluation.signal is None:
            return EngineDecision(
                symbol=symbol,
                timeframe=None,
                signal=None,
                order=None,
                executed=False,
                reason="No strategy signal",
            )

        signal = evaluation.signal

        # Resolve the actual entry price.
        entry_price = self._resolve_entry_price(
            signal=signal,
            candles_15m=candles_15m,
            candles_5m=candles_5m,
        )

        if entry_price is None:
            return EngineDecision(
                symbol=symbol,
                timeframe=evaluation.timeframe,
                signal=signal,
                order=None,
                executed=False,
                reason="Entry price could not be resolved",
            )

        # Global risk management.
        risk_decision = self.risk_manager.evaluate(
            signal=signal,
            entry_price=entry_price,
        )

        if not risk_decision.approved:
            return EngineDecision(
                symbol=symbol,
                timeframe=evaluation.timeframe,
                signal=signal,
                order=None,
                executed=False,
                reason=risk_decision.reason,
            )

        position_size = risk_decision.position_size

        if position_size is None:
            return EngineDecision(
                symbol=symbol,
                timeframe=evaluation.timeframe,
                signal=signal,
                order=None,
                executed=False,
                reason="Position size was not calculated",
            )

        risk_reward = risk_decision.risk_reward

        if risk_reward is None:
            return EngineDecision(
                symbol=symbol,
                timeframe=evaluation.timeframe,
                signal=signal,
                order=None,
                executed=False,
                reason="Risk/reward calculation was not produced",
            )

        order = self._build_order(
            symbol=symbol,
            signal=signal,
            quantity=position_size.position_size,
            entry_price=entry_price,
            timestamp=timestamp,
        )

        submitted_order = self.execution_engine.submit(order)

        if submitted_order.status != OrderStatus.FILLED:
            return EngineDecision(
                symbol=symbol,
                timeframe=evaluation.timeframe,
                signal=signal,
                order=submitted_order,
                executed=False,
                reason="Order was not filled",
            )

        # The actual filled price takes priority over planned entry.
        filled_price = (
            submitted_order.average_fill_price
            or entry_price
        )

        # If strategy did not define TP, RiskManager calculated
        # the exact default 3:1 target.
        take_profit = (
            signal.take_profit
            if signal.take_profit is not None
            else risk_reward.take_profit
        )

        self.position_manager.open_position(
            symbol=symbol,
            side=self._position_side(signal.side),
            quantity=submitted_order.filled_quantity
            or submitted_order.quantity,
            entry_price=filled_price,
            stop_loss=signal.stop_loss,
            take_profit=take_profit,
            strategy=signal.strategy,
            timestamp=timestamp,
        )

        return EngineDecision(
            symbol=symbol,
            timeframe=evaluation.timeframe,
            signal=signal,
            order=submitted_order,
            executed=True,
            reason="Order filled and position opened",
        )

    @staticmethod
    def _position_side(side: SignalSide) -> PositionSide:
        if side == SignalSide.LONG:
            return PositionSide.LONG

        if side == SignalSide.SHORT:
            return PositionSide.SHORT

        raise ValueError(f"Unsupported signal side: {side}")

    @staticmethod
    def _order_side(side: SignalSide) -> OrderSide:
        if side == SignalSide.LONG:
            return OrderSide.BUY

        if side == SignalSide.SHORT:
            return OrderSide.SELL

        raise ValueError(f"Unsupported signal side: {side}")

    @staticmethod
    def _resolve_entry_price(
        signal: TradingSignal,
        candles_15m: list[Candle],
        candles_5m: list[Candle],
    ) -> Optional[float]:

        if signal.trigger_price is not None:
            return signal.trigger_price

        if signal.entry_timing.value == "current_close":
            candles = candles_15m or candles_5m

            if not candles:
                return None

            return candles[-1].close

        if signal.entry_timing.value == "next_open":
            candles = candles_15m or candles_5m

            if len(candles) < 2:
                return None

            return candles[-1].open

        return None

    def _build_order(
        self,
        symbol: str,
        signal: TradingSignal,
        quantity: float,
        entry_price: float,
        timestamp: datetime,
    ) -> Order:

        order_id = (
            f"ORD-{len(self.state.active_orders) + 1:06d}"
        )

        if signal.trigger_price is not None:
            order_type = OrderType.STOP
            stop_price = signal.trigger_price
            price = None
        else:
            order_type = OrderType.MARKET
            stop_price = None
            price = entry_price

        return Order(
            order_id=order_id,
            symbol=symbol,
            side=self._order_side(signal.side),
            order_type=order_type,
            quantity=quantity,
            created_at=timestamp,
            price=price,
            stop_price=stop_price,
            status=OrderStatus.PENDING,
            strategy=signal.strategy,
            reason=signal.reason,
        )
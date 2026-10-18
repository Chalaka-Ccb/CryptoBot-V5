"""Use the SAME RiskManager and position sizing as the backtester."""
from core.models.account import Account
from engine.risk_manager import RiskManager
from risk.limits import RiskLimits, QuantityLimits
from live.models import TradePlan


def size_trade(signal, timeframe, entry_price, balance, market_limits, cfg):
    if signal.strategy != "bollinger_channel_rebound":
        raise ValueError("Only Channel Rebound is permitted")
    available = balance.available * (1 - cfg.margin_buffer)
    account = Account(account_id="BITGET", currency="USDT", initial_balance=max(balance.equity, 0.01),
                      balance=balance.equity, available_balance=available)
    limits = RiskLimits(leverage=cfg.leverage, max_position_notional=cfg.max_notional)
    manager = RiskManager(account, risk_percentage=cfg.risk_percentage, default_risk_reward=3.0,
                          limits=limits, quantity_limits={cfg.symbol: market_limits})
    decision = manager.evaluate(signal, entry_price, symbol=cfg.symbol)
    if not decision.approved:
        raise ValueError(decision.reason)
    return TradePlan(side=signal.side.value, qty=decision.position_size.position_size,
                     sl=signal.stop_loss, tp=decision.risk_reward.take_profit,
                     signal=signal, timeframe=timeframe, entry_price=entry_price)

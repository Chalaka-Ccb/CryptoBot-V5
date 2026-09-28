from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestConfig:
    exchange: str = "bybit"

    symbol: str = "BTC/USDT:USDT"

    timeframe_15m: str = "15m"
    timeframe_5m: str = "5m"

    limit: int = 200

    # Number of historical candles to request initially.
    # The loader will paginate when more data is requested later.
    candles: int = 1000

    # Futures / perpetual market
    market_type: str = "swap"
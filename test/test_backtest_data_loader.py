from backtesting.data_loader import ExchangeDataLoader


def main():
    loader = ExchangeDataLoader(
        exchange_name="bybit",
        market_type="swap",
    )

    market_data = loader.load_market_data(
        symbol="BTC/USDT:USDT",
        candles=2500,
    )

    print()
    print("===== BACKTEST DATA =====")

    print(f"Symbol: {market_data.symbol}")

    print(
        f"15m candles: "
        f"{len(market_data.candles_15m)}"
    )

    print(
        f"5m candles: "
        f"{len(market_data.candles_5m)}"
    )

    print(
        f"Start: "
        f"{market_data.start_time}"
    )

    print(
        f"End:   "
        f"{market_data.end_time}"
    )

    print()
    print("===== FIRST 15m CANDLE =====")
    print(market_data.candles_15m[0])

    print()
    print("===== LAST 15m CANDLE =====")
    print(market_data.candles_15m[-1])

    print()
    print("===== FIRST 5m CANDLE =====")
    print(market_data.candles_5m[0])

    print()
    print("===== LAST 5m CANDLE =====")
    print(market_data.candles_5m[-1])


if __name__ == "__main__":
    main()
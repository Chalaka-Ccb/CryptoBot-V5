"""Read-only smoke test: python -m live.check_bitget [--private]."""
import argparse
from live.bitget_gateway import BitgetGateway
from live.config import LiveConfig


def main():
    parser = argparse.ArgumentParser(description="Read-only Bitget connection check")
    parser.add_argument("--private", action="store_true", help="Read account balance and positions (requires env credentials)")
    args = parser.parse_args()
    gateway = BitgetGateway(LiveConfig())
    market = gateway.connect()
    print(f"Connected: {market['symbol']} | active={market.get('active')}")
    for tf in ("15m", "5m"):
        candles = gateway.fetch_closed_candles(tf)
        print(f"{tf}: {len(candles)} closed candles; last={candles[-1].timestamp if candles else 'none'}")
    if args.private:
        snapshot = gateway.fetch_available_balance()
        print(f"USDT available={snapshot.free_usdt:.4f}, total={snapshot.total_usdt:.4f}, used={snapshot.used_usdt:.4f}")
        print(f"Positions returned: {len(gateway.fetch_positions())}")
    print("Read-only check complete. No orders placed.")


if __name__ == "__main__":
    main()

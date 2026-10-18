"""Entry point for Bitget live V1. Defaults to read-only checks."""
import argparse
import signal
from live.config import LiveConfig
from live.controls import Controls
from live.exchange import BitgetExchange
from live.order_manager import OrderManager
from live.recorder import Recorder
from live.state import StateStore
from live.engine import LiveEngine


def build_engine(cfg):
    recorder = Recorder(cfg.data_dir, cfg.log_dir)
    controls = Controls()
    exchange = BitgetExchange(cfg, recorder)
    exchange.load_markets()
    orders = OrderManager(exchange, controls, recorder, cfg)
    state = StateStore(cfg.data_dir + "/live_state.json")
    return LiveEngine(exchange, orders, recorder, state, controls, cfg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Read-only exchange diagnostics")
    parser.add_argument("--flatten", action="store_true", help="Close live position and lock trading")
    args = parser.parse_args()
    cfg = LiveConfig.from_env()
    if args.check:
        recorder = Recorder(cfg.data_dir, cfg.log_dir)
        ex = BitgetExchange(cfg, recorder)
        ex.load_markets()
        print("Symbol:", cfg.symbol)
        print("Limits:", ex.market_limits())
        print("Last price:", ex.get_price())
        print("Position:", ex.get_position())
        print("Balance:", ex.get_balance())
        print("Protection:", ex.get_protection())
        print("Closed 5m candles:", len(ex.get_candles("5m")))
        print("Closed 15m candles:", len(ex.get_candles("15m")))
        return
    cfg.require_trading_confirmation()
    engine = build_engine(cfg)
    if args.flatten:
        engine.orders.ensure_flat()
        return
    signal.signal(signal.SIGTERM, lambda *_: engine.stop())
    signal.signal(signal.SIGINT, lambda *_: engine.stop())
    engine.exchange.setup_account()
    engine.run()


if __name__ == "__main__":
    main()

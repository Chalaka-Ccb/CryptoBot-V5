"""Bitget public-candle driven paper runner. NEVER submits exchange orders.

This is a local smoke-test runner, not a restart-safe trading daemon.
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from live.bitget_gateway import BitgetGateway
from live.config import LiveConfig
from live.paper_execution import PaperState, SingleSymbolPaperExecution
from engine.strategy_coordinator import StrategyCoordinator
from strategies.bollinger.channel_rebound import ChannelReboundStrategy

LOG = logging.getLogger(__name__)


class PaperRunner:
    def __init__(self, gateway, paper, coordinator=None, stop_file='live_stop.request'):
        self.gateway = gateway
        self.paper = paper
        self.coordinator = coordinator or StrategyCoordinator(
            [ChannelReboundStrategy()], [ChannelReboundStrategy()]
        )
        self.stop_file = Path(stop_file)
        self.last_5m = None
        self.last_15m = None
        self.started = False

    def request_stop(self):
        self.paper.request_stop()
        LOG.warning('Stop requested; state=%s', self.paper.state.value)

    @staticmethod
    def _evaluate_strategies(strategies, candles):
        if not candles:
            return None
        index = len(candles) - 1
        for strategy in strategies:
            signal = strategy.generate_signal(candles, index)
            if signal is not None:
                return signal
        return None

    def tick(self):
        if self.stop_file.exists() and not self.paper.stop_requested:
            self.request_stop()
        if self.paper.state == PaperState.STOPPED:
            return
        candles_5m = self.gateway.fetch_closed_candles('5m')
        candles_15m = self.gateway.fetch_closed_candles('15m')
        if not candles_5m or not candles_15m:
            LOG.warning('Not enough candle data')
            return
        current_5m = candles_5m[-1].timestamp
        current_15m = candles_15m[-1].timestamp
        if not self.started:
            self.last_5m, self.last_15m = current_5m, current_15m
            self.started = True
            LOG.info('Initialized from last closed candles; no historical orders replayed')
            return
        new_5m = current_5m > self.last_5m
        new_15m = current_15m > self.last_15m
        if not new_5m and not new_15m:
            return
        # Never backfill missing intervals as if they had been observed in real time.
        # Stop rather than silently skip possible fills/exits.
        if new_5m and (current_5m - self.last_5m).total_seconds() > 300:
            raise RuntimeError('Missed 5m candle(s); stop and reconcile paper state manually')
        if new_15m and (current_15m - self.last_15m).total_seconds() > 900:
            raise RuntimeError('Missed 15m candle(s); stop and reconcile paper state manually')
        if new_5m:
            closed = self.paper.on_candle(candles_5m[-1])
            if closed:
                LOG.info('Closed %s gross=%.4f fees=%.4f net=%.4f balance=%.4f',
                         closed.reason, closed.gross_pnl, closed.fees, closed.net_pnl, self.paper.balance)
        self.last_5m, self.last_15m = current_5m, current_15m
        if self.paper.stop_requested or self.paper.state != PaperState.IDLE:
            return
        # Evaluate a new 15m signal first, otherwise a new 5m signal.
        # Separate strategy instances avoid indicator cache interference.
        signal = None
        timeframe = None
        if new_15m:
            signal = self._evaluate_strategies(
                self.coordinator.strategies_15m,
                candles_15m,
            )
            timeframe = '15m'
        if signal is None and new_5m:
            signal = self._evaluate_strategies(
                self.coordinator.strategies_5m,
                candles_5m,
            )
            timeframe = '5m'
        if signal:
            self.paper.submit(signal, reference_price=candles_5m[-1].close)
            LOG.info('Paper %s pending %s trigger=%s SL=%s TP=%s',
                     timeframe, signal.side.value, signal.trigger_price, signal.stop_loss, signal.take_profit)

    def run(self, poll_seconds=15):
        if poll_seconds < 5:
            raise ValueError('poll_seconds must be at least 5')
        self.gateway.connect()
        LOG.info('PAPER ONLY: exchange used exclusively for public OHLCV')
        while self.paper.state != PaperState.STOPPED:
            try:
                self.tick()
                if self.paper.state != PaperState.STOPPED:
                    time.sleep(poll_seconds)
            except KeyboardInterrupt:
                self.request_stop()
                if self.paper.state != PaperState.STOPPED:
                    LOG.warning('Position open: waiting for SL/TP. Do not terminate process.')
        LOG.info('Paper runner stopped; final balance=%.4f', self.paper.balance)


def main():
    parser = argparse.ArgumentParser(description='Single-symbol Bitget PAPER runner; never sends orders')
    parser.add_argument('--balance', type=float, default=100.0)
    parser.add_argument('--risk', type=float, default=0.02)
    parser.add_argument('--leverage', type=float, default=5.0)
    parser.add_argument('--poll-seconds', type=int, default=15)
    parser.add_argument('--stop-file', default='live_stop.request')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = LiveConfig(mode='paper', risk_percentage=args.risk, leverage=args.leverage)
    paper = SingleSymbolPaperExecution(balance=args.balance, risk_fraction=config.risk_percentage,
                                       leverage=config.leverage)
    runner = PaperRunner(BitgetGateway(config), paper, stop_file=args.stop_file)
    if runner.stop_file.exists():
        raise SystemExit(f'Remove stale stop file before starting: {runner.stop_file}')
    runner.run(args.poll_seconds)


if __name__ == '__main__':
    main()
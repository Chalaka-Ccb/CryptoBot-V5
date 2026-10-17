"""Read-only account compatibility diagnostic. Never submits orders."""
import argparse
from live.config import LiveConfig
from live.bitget_gateway import BitgetGateway
from live.bitget_order_adapter import BitgetOrderAdapter
from live.bitget_plan_inspector import BitgetPlanInspector


def check(gateway):
    market = gateway.connect()
    print('Market:', market.get('symbol'), '| id:', market.get('id'))
    exchange = gateway.exchange
    print('CCXT exchange:', exchange.id)
    print('Ordinary orders:', len(BitgetOrderAdapter(gateway).fetch_open_orders()))
    positions = gateway.fetch_positions()
    if not isinstance(positions, list):
        raise RuntimeError('Invalid positions response')
    print('Position records:', len(positions))
    plans = BitgetPlanInspector(gateway).fetch_all()
    print('Classic V2 pending plan records:', len(plans))
    print('READ-ONLY DIAGNOSTIC COMPLETE; no orders submitted')


def main():
    parser = argparse.ArgumentParser(description='Read-only Bitget futures API compatibility check')
    parser.parse_args()
    check(BitgetGateway(LiveConfig(mode='paper')))


if __name__ == '__main__':
    main()

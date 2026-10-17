"""Phase 6R: verify Classic V2 account modes from the real read-only endpoint.

Bitget GET /api/v2/mix/account/account returns marginMode and posMode
together in data. Never use a write endpoint to discover these settings.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedAccountMode:
    margin_mode: str
    position_mode: str
    source: str = 'verified_exchange_response'
    live_execution_authorized: bool = False


class BitgetVerifiedAccountMode:
    METHOD = 'privateMixGetV2MixAccountAccount'

    def __init__(self, gateway):
        self.gateway = gateway

    def fetch(self):
        market = self.gateway.connect()
        if self.gateway.config.symbol != 'SOL/USDT:USDT' or market.get('id') != 'SOLUSDT':
            raise RuntimeError('Unsupported account symbol')
        method = getattr(self.gateway.exchange, self.METHOD, None)
        if not callable(method):
            raise RuntimeError('Classic V2 single-account read method unavailable')
        raw = method({'symbol':'SOLUSDT','productType':'USDT-FUTURES','marginCoin':'USDT'})
        if not isinstance(raw, dict) or raw.get('code') != '00000':
            raise RuntimeError('Bitget single-account read failed')
        data = raw.get('data')
        if not isinstance(data, dict) or data.get('marginCoin') != 'USDT':
            raise RuntimeError('Unexpected account data')
        if data.get('marginMode') != 'isolated':
            raise RuntimeError('Account margin mode is not verified isolated')
        if data.get('posMode') != 'one_way_mode':
            raise RuntimeError('Account position mode is not verified one-way')
        return VerifiedAccountMode('isolated','one_way')


if __name__ == '__main__':
    from live.bitget_gateway import BitgetGateway
    from live.config import LiveConfig
    print(BitgetVerifiedAccountMode(BitgetGateway(LiveConfig())).fetch())

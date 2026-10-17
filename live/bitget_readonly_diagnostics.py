"""Phase 6P: read-only Bitget compatibility diagnostics.

No private endpoint is invoked by this module. Reports capabilities and
safe metadata only; no credentials, balances, positions or raw API responses.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DiagnosticReport:
    symbol: str
    exchange_id: str
    ccxt_version: str
    market_id: str
    swap: bool
    linear: bool
    active: bool
    read_methods: tuple[str, ...]
    missing_methods: tuple[str, ...]
    live_execution_authorized: bool = False


READ_METHODS = (
    'fetch_positions',
    'fetch_open_orders',
    'privateMixGetV2MixOrderOrdersPlanPending',
)
# This is intentionally a capability inventory, not proof of endpoint correctness.


class BitgetReadOnlyDiagnostics:
    def __init__(self, gateway):
        self.gateway = gateway

    def inspect(self):
        if self.gateway.config.symbol != 'SOL/USDT:USDT':
            raise RuntimeError('Unexpected symbol')
        market = self.gateway.connect()  # load_markets is public
        exchange = self.gateway.exchange
        if getattr(exchange, 'id', None) != 'bitget':
            raise RuntimeError('Expected Bitget exchange')
        if not isinstance(market, dict) or market.get('swap') is not True or market.get('linear') is not True or market.get('settle') != 'USDT' or market.get('active') is False:
            raise RuntimeError('Invalid market metadata')
        market_id = market.get('id')
        if not isinstance(market_id, str) or not market_id:
            raise RuntimeError('Missing market ID')
        present = tuple(name for name in READ_METHODS if callable(getattr(exchange, name, None)))
        missing = tuple(name for name in READ_METHODS if name not in present)
        return DiagnosticReport(
            symbol='SOL/USDT:USDT', exchange_id='bitget',
            ccxt_version=self._version(exchange), market_id=market_id,
            swap=True, linear=True, active=True,
            read_methods=present, missing_methods=missing)

    @staticmethod
    def _version(exchange):
        # Do not import CCXT here; fake exchanges in tests are supported.
        version = getattr(exchange, 'version', None)
        return version if isinstance(version, str) and version else 'unknown'

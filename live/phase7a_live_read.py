"""Run a real authenticated read-only Bitget probe, no journal mutations."""
from live.bitget_gateway import BitgetGateway
from live.config import LiveConfig
from live.bitget_verified_account_mode import BitgetVerifiedAccountMode
from live.bitget_live_read_probe import BitgetLiveReadProbe


def main():
    gateway = BitgetGateway(LiveConfig(risk_percentage=0.005, leverage=5))
    print('Account mode:', BitgetVerifiedAccountMode(gateway).fetch())
    print('Exchange snapshot:', BitgetLiveReadProbe(gateway).run())
    print('Live execution authorized: False')


if __name__ == '__main__':
    main()

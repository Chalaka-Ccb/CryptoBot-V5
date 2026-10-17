import unittest
from live.bitget_account_mode_reader import BitgetAccountModeReader


def account(**changes):
    return {"code": "00000", "data": dict(symbol="SOLUSDT", marginMode="isolated", **changes)}


def mode(value="one_way_mode"):
    return {"code": "00000", "data": {"posMode": value}}


class ReaderTests(unittest.TestCase):
    def test_verified_modes(self):
        evidence = BitgetAccountModeReader(account, mode).fetch()
        self.assertEqual(evidence.margin_mode, "isolated")
        self.assertEqual(evidence.position_mode, "one_way")
        self.assertEqual(evidence.source, "verified_exchange_response")

    def test_hedge_mode_rejected(self):
        with self.assertRaises(RuntimeError):
            BitgetAccountModeReader(account, lambda: mode("hedge_mode")).fetch()

    def test_cross_margin_rejected(self):
        with self.assertRaises(RuntimeError):
            BitgetAccountModeReader(lambda: {"code":"00000","data":{"symbol":"SOLUSDT","marginMode":"crossed"}}, mode).fetch()

    def test_wrong_symbol_rejected(self):
        with self.assertRaises(RuntimeError):
            BitgetAccountModeReader(lambda: {"code":"00000","data":{"symbol":"BTCUSDT","marginMode":"isolated"}}, mode).fetch()

    def test_bad_response_code_rejected(self):
        with self.assertRaises(RuntimeError):
            BitgetAccountModeReader(lambda: {"code":"40001","data":{}}, mode).fetch()

    def test_missing_fields_rejected(self):
        with self.assertRaises(RuntimeError):
            BitgetAccountModeReader(lambda: {"code":"00000","data":{}}, mode).fetch()

    def test_missing_data_rejected(self):
        with self.assertRaises(RuntimeError):
            BitgetAccountModeReader(lambda: {"code":"00000"}, mode).fetch()

    def test_requires_read_functions(self):
        with self.assertRaises(TypeError):
            BitgetAccountModeReader(None, mode)


if __name__ == "__main__":
    unittest.main()

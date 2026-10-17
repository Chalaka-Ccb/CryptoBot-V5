"""Phase 6O: read-only Bitget account-mode evidence reader.

Requires explicit authenticated response from a caller-provided READ function.
Never guesses mode from empty positions, leverage, or configuration.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedModeEvidence:
    margin_mode: str
    position_mode: str
    source: str = "verified_exchange_response"


class BitgetAccountModeReader:
    """Strict parser of independently retrieved Bitget account-mode data.

    The caller must supply an authenticated read-only function returning a
    mapping with code='00000' and data containing exact mode fields.
    API endpoint selection and response schema must be checked against the
    installed Bitget/CCXT version before using live responses.
    """
    def __init__(self, read_account, read_position_mode):
        if not callable(read_account) or not callable(read_position_mode):
            raise TypeError("Two read-only account query functions required")
        self._read_account = read_account
        self._read_position_mode = read_position_mode

    @staticmethod
    def _data(response, label):
        if not isinstance(response, dict) or response.get("code") != "00000":
            raise RuntimeError(f"Unverified {label} response")
        data = response.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"Missing {label} response data")
        return data

    def fetch(self):
        account = self._data(self._read_account(), "account")
        mode = self._data(self._read_position_mode(), "position mode")
        # Exact keys only. Do not infer defaults from absence or synonyms.
        if account.get("symbol") != "SOLUSDT":
            raise RuntimeError("Unexpected account symbol")
        if account.get("marginMode") != "isolated":
            raise RuntimeError("Isolated margin not verified")
        if mode.get("posMode") != "one_way_mode":
            raise RuntimeError("One-way position mode not verified")
        return VerifiedModeEvidence("isolated", "one_way")

import unittest
from unittest.mock import patch

import pandas as pd

from barchart_data import (
    BarchartInteractiveChartError,
    ImportedHistory,
    download_history,
    history_quality_report,
)
from barchart_data.yahoo import (
    _download_yahoo_futures_history,
    yahoo_futures_symbol,
)


class FakeResponse:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/ZCU26.CBT"

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def yahoo_payload():
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "symbol": "ZCU26.CBT",
                        "instrumentType": "FUTURE",
                        "exchangeTimezoneName": "America/New_York",
                    },
                    "timestamp": [
                        1787356800,
                        1787443200,
                    ],
                    "indicators": {
                        "quote": [
                            {
                                "open": [480.0, 481.0],
                                "high": [485.0, 486.0],
                                "low": [479.0, 480.0],
                                "close": [483.0, 484.0],
                                "volume": [1000, 2000],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


class PublicFuturesTests(unittest.TestCase):
    def test_barchart_contract_maps_to_public_exact_contract_symbol(self):
        self.assertEqual(yahoo_futures_symbol("ZCU26"), "ZCU26.CBT")
        self.assertEqual(yahoo_futures_symbol("ZCU26.CBT"), "ZCU26.CBT")

    def test_public_exact_contract_is_normalized_in_memory(self):
        session = FakeSession(FakeResponse(yahoo_payload()))

        imported = _download_yahoo_futures_history("ZCU26", session=session)

        self.assertIsNone(imported.path)
        self.assertEqual(imported.frame["symbol"].unique().tolist(), ["ZCU26"])
        self.assertEqual(imported.frame["close"].tolist(), [483.0, 484.0])
        self.assertEqual(imported.frame["date"].dt.strftime("%Y-%m-%d").tolist(), [
            "2026-08-21",
            "2026-08-22",
        ])
        self.assertTrue(imported.quality.is_usable)
        self.assertIn("ZCU26.CBT", imported.source)
        self.assertEqual(session.calls[0][0].rsplit("/", 1)[-1], "ZCU26.CBT")

    def test_barchart_denial_uses_public_futures_fallback(self):
        error = BarchartInteractiveChartError(
            "denied",
            status_code=403,
            url="https://www.barchart.com/futures/quotes/ZCU26/interactive-chart",
        )
        imported = ImportedHistory(
            path=None,
            frame=pd.DataFrame({"date": ["2026-09-21"], "close": [483.0]}),
            quality=history_quality_report(
                pd.DataFrame({"date": ["2026-09-21"], "close": [483.0]})
            ),
            source="https://query1.finance.yahoo.com/v8/finance/chart/ZCU26.CBT",
        )

        with patch(
            "barchart_data.browser.BarchartInteractiveChartWorkflow.capture_history",
            side_effect=error,
        ), patch(
            "barchart_data.browser._download_yahoo_futures_history",
            return_value=imported,
        ) as fallback:
            result = download_history("ZCU26", verbosity=0)

        self.assertIs(result, imported)
        fallback.assert_called_once_with("ZCU26", timeout_seconds=30.0)

    def test_browser_session_failure_uses_public_futures_fallback(self):
        error = BarchartInteractiveChartError("sync API unavailable")
        imported = ImportedHistory(
            path=None,
            frame=pd.DataFrame({"date": ["2026-09-21"], "close": [483.0]}),
            quality=history_quality_report(
                pd.DataFrame({"date": ["2026-09-21"], "close": [483.0]})
            ),
            source="https://query1.finance.yahoo.com/v8/finance/chart/ZCU26.CBT",
        )

        with patch(
            "barchart_data.browser.BarchartInteractiveChartWorkflow.capture_history",
            side_effect=error,
        ), patch(
            "barchart_data.browser._download_yahoo_futures_history",
            return_value=imported,
        ):
            result = download_history("ZCU26", verbosity=0)

        self.assertIs(result, imported)


if __name__ == "__main__":
    unittest.main()

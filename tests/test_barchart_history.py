import io
import unittest

import pandas as pd

from barchart_data import (
    BarchartDecodeError,
    normalize_barchart_history,
    read_barchart_history_csv,
    read_barchart_history_text,
)


class BarchartHistoryTests(unittest.TestCase):
    def test_csv_import_supports_website_column_names(self):
        frame = read_barchart_history_csv(
            io.StringIO(
                "Date,Open,High,Low,Last,Volume,Open Interest\n"
                "2026/08/21,480,485,479,483.75,10,20\n"
            ),
            symbol="ZCU26",
        )

        self.assertEqual(frame.loc[0, "symbol"], "ZCU26")
        self.assertEqual(frame.loc[0, "date"], pd.Timestamp("2026-08-21"))
        self.assertEqual(frame.loc[0, "close"], 483.75)
        self.assertEqual(frame.loc[0, "openInterest"], 20)

    def test_api_names_are_normalized_without_losing_source_fields(self):
        frame = normalize_barchart_history(
            pd.DataFrame(
                {
                    "symbol": ["ZCU26"],
                    "timestamp": ["2026-08-21T12:00:00-05:00"],
                    "tradingDay": ["2026-08-21"],
                    "open": [480],
                    "high": [485],
                    "low": [479],
                    "close": [483.75],
                    "openInterest": [20],
                }
            )
        )

        self.assertEqual(frame.loc[0, "date"], pd.Timestamp("2026-08-21"))
        self.assertIn("tradingDay", frame.columns)
        self.assertEqual(frame.loc[0, "close"], 483.75)

    def test_invalid_dates_raise_typed_error(self):
        with self.assertRaises(BarchartDecodeError):
            read_barchart_history_csv(
                io.StringIO("Date,Close\nnot-a-date,1\n")
            )

    def test_read_text_decodes_raw_chart_feed_rows(self):
        frame = read_barchart_history_text(
            "ZCU26,2026-08-20,480,485,479,483,1000,1200\n"
            "ZCU26,2026-08-21,481,486,480,484,2000,1300\n",
            symbol="ZCU26",
        )

        self.assertEqual(
            frame["date"].dt.strftime("%Y-%m-%d").tolist(),
            ["2026-08-20", "2026-08-21"],
        )
        self.assertEqual(frame["close"].tolist(), [483, 484])
        self.assertEqual(frame["openInterest"].tolist(), [1200, 1300])

    def test_read_text_decodes_headered_chart_feed_rows(self):
        frame = read_barchart_history_text(
            "timestamp,open,high,low,last,volume\n"
            "2026-08-21T00:00:00Z,481,486,480,484,2000\n",
            symbol="ZCU26",
        )

        self.assertEqual(frame.loc[0, "symbol"], "ZCU26")
        self.assertEqual(frame.loc[0, "close"], 484)


if __name__ == "__main__":
    unittest.main()

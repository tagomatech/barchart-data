import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from barchart_data import (
    BarchartWebsiteWorkflow,
    history_quality_report,
    historical_download_url,
)


class BarchartWebsiteWorkflowTests(unittest.TestCase):
    def test_historical_download_url_encodes_symbol_safely(self):
        self.assertEqual(
            historical_download_url("^GSPC", asset_class="stocks"),
            "https://www.barchart.com/stocks/quotes/%5EGSPC/historical-download",
        )

    def test_workflow_rejects_path_injection(self):
        with self.assertRaises(ValueError):
            historical_download_url("ZC/../private")
        with self.assertRaises(ValueError):
            historical_download_url("ZCU26", asset_class="futures/private")

    def test_open_page_only_hands_url_to_browser(self):
        workflow = BarchartWebsiteWorkflow(base_url="https://example.test")
        with patch("barchart_data.website.webbrowser.open") as open_page:
            url = workflow.open_historical_download_page("ZCU26")

        self.assertEqual(
            url,
            "https://example.test/futures/quotes/ZCU26/historical-download",
        )
        open_page.assert_called_once_with(url, new=2)

    def test_latest_csv_is_filtered_and_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ZCU26-old.csv").write_text(
                "Date,Open,High,Low,Last,Volume\n"
                "2026-08-20,480,485,479,483,1000\n",
                encoding="utf-8",
            )
            latest = root / "ZCU26-latest.csv"
            latest.write_text(
                "\ufeffDate;Open;High;Low;Last;Volume\n"
                "2026-08-21;481;486;480;484;2,000\n",
                encoding="utf-8",
            )

            imported = BarchartWebsiteWorkflow(root).import_latest_csv(
                symbol="ZCU26"
            )

        self.assertEqual(imported.path, latest)
        self.assertEqual(imported.frame.loc[0, "close"], 484)
        self.assertEqual(imported.frame.loc[0, "volume"], 2000)
        self.assertTrue(imported.quality.is_usable)
        self.assertEqual(imported.quality.rows, 1)

    def test_quality_report_identifies_missing_values_and_duplicates(self):
        report = history_quality_report(
            pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-21", "2026-08-21"]),
                    "close": [484.0, None],
                }
            )
        )

        self.assertEqual(report.duplicate_dates, 1)
        self.assertEqual(report.missing_values["close"], 1)
        self.assertFalse(report.is_usable)

    def test_missing_download_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "Download it"):
                BarchartWebsiteWorkflow(directory).latest_csv_path(symbol="ZCU26")

    def test_wait_for_csv_returns_a_stable_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "ZCU26-download.csv"
            path.write_text(
                "Date,Last\n2026-08-21,484\n",
                encoding="utf-8",
            )

            result = BarchartWebsiteWorkflow(root).wait_for_csv(
                symbol="ZCU26",
                since=0,
                timeout=1,
                poll_interval=0.001,
            )

        self.assertEqual(result, path)


if __name__ == "__main__":
    unittest.main()

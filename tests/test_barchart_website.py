import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from barchart_data import (
    BarchartInteractiveChartWorkflow,
    BarchartWebsiteWorkflow,
    history_quality_report,
    interactive_chart_url,
    historical_download_url,
    read_barchart_history_bytes,
)
from barchart_data.browser import _decode_chart_response


class BarchartWebsiteWorkflowTests(unittest.TestCase):
    def test_historical_download_url_encodes_symbol_safely(self):
        self.assertEqual(
            historical_download_url("^GSPC", asset_class="stocks"),
            "https://www.barchart.com/stocks/quotes/%5EGSPC/historical-download",
        )

    def test_interactive_chart_url_encodes_symbol_safely(self):
        self.assertEqual(
            interactive_chart_url("^GSPC", asset_class="stocks"),
            "https://www.barchart.com/stocks/quotes/%5EGSPC/interactive-chart",
        )

    def test_interactive_workflow_identifies_same_origin_chart_history(self):
        class Response:
            def __init__(self):
                self.url = "https://www.barchart.com/proxies/timeseries/queryeod.ashx"
                self.status = 200
                self.headers = {"content-type": "text/csv"}

        self.assertTrue(
            BarchartInteractiveChartWorkflow._is_chart_response(
                Response(),
                "https://www.barchart.com/futures/quotes/ZCU26/interactive-chart",
            )
        )

    def test_chart_response_parser_accepts_json_rows(self):
        frame = _decode_chart_response(
            '[["ZCU26","2026-08-20",480,485,479,483,1000,1200],'
            '["ZCU26","2026-08-21",481,486,480,484,2000,1300]]',
            symbol="ZCU26",
        )

        self.assertEqual(frame["close"].tolist(), [483, 484])
        self.assertEqual(frame["openInterest"].tolist(), [1200, 1300])

    def test_in_memory_bytes_import_has_no_path(self):
        payload = (
            b"Date,Open,High,Low,Last,Volume\n"
            b"2026-08-21,481,486,480,484,2000\n"
        )

        imported = BarchartWebsiteWorkflow().import_bytes(
            payload,
            symbol="ZCU26",
            source_name="ZCU26-export.csv",
        )

        self.assertIsNone(imported.path)
        self.assertEqual(imported.source, "ZCU26-export.csv")
        self.assertEqual(imported.frame.loc[0, "close"], 484)
        self.assertEqual(
            read_barchart_history_bytes(payload, symbol="ZCU26").loc[0, "close"],
            484,
        )

    def test_interactive_download_defaults_to_memory(self):
        class FakeResponse:
            status = 200

        class FakeDownload:
            def __init__(self, path):
                self.path_value = path
                self.deleted = False

            def path(self):
                return str(self.path_value)

            def suggested_filename(self):
                return "ZCU26-export.csv"

            def delete(self):
                self.deleted = True
                self.path_value.unlink()

        class FakePage:
            def __init__(self, download):
                self.download = download
                self.closed = False

            def goto(self, url, *, wait_until, timeout):
                self.url = url
                return FakeResponse()

            def locator(self, selector):
                return types.SimpleNamespace(inner_text=lambda timeout: "")

            def wait_for_event(self, event, *, timeout):
                return self.download

            def close(self):
                self.closed = True

        class FakeBrowser:
            def __init__(self, page):
                self.page = page
                self.closed = False

            def new_page(self):
                return self.page

            def close(self):
                self.closed = True

        class FakeChromium:
            def __init__(self, browser):
                self.browser = browser

            def launch(self, **kwargs):
                return self.browser

        class FakePlaywright:
            def __init__(self, chromium):
                self.chromium = chromium

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

        with tempfile.TemporaryDirectory() as directory:
            download_path = Path(directory) / "temporary.csv"
            download_path.write_bytes(
                b"Date,Open,High,Low,Last,Volume\n"
                b"2026-08-21,481,486,480,484,2000\n"
            )
            download = FakeDownload(download_path)
            page = FakePage(download)
            browser = FakeBrowser(page)
            playwright = FakePlaywright(FakeChromium(browser))
            sync_api = types.ModuleType("playwright.sync_api")
            sync_api.TimeoutError = TimeoutError
            sync_api.sync_playwright = lambda: playwright
            playwright_package = types.ModuleType("playwright")
            with patch.dict(
                sys.modules,
                {
                    "playwright": playwright_package,
                    "playwright.sync_api": sync_api,
                },
            ):
                imported = BarchartInteractiveChartWorkflow(
                    base_url="https://example.test",
                    timeout_seconds=1,
                ).download_interactive_csv("ZCU26", timeout=1)

        self.assertIsNone(imported.path)
        self.assertEqual(imported.source, "ZCU26-export.csv")
        self.assertEqual(imported.frame.loc[0, "close"], 484)
        self.assertFalse(download_path.exists())
        self.assertTrue(download.deleted)
        self.assertTrue(page.closed)
        self.assertTrue(browser.closed)

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

            old_mtime = (root / "ZCU26-old.csv").stat().st_mtime
            os.utime(latest, (old_mtime + 1, old_mtime + 1))

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
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(
            FileNotFoundError, "Download it"
        ):
            BarchartWebsiteWorkflow(directory).latest_csv_path(symbol="ZCU26")

    def test_default_workflow_does_not_configure_a_download_directory(self):
        workflow = BarchartWebsiteWorkflow()

        self.assertIsNone(workflow.directory)
        with self.assertRaisesRegex(FileNotFoundError, "download_dir"):
            workflow.latest_csv_path(symbol="ZCU26")

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

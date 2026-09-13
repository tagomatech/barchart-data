"""Browser-assisted access to data naturally loaded by Barchart charts.

This module does not call undocumented endpoints, automate sign-in, inspect
cookies, or defeat bot protection. It opens the official chart in a browser
context and records only successful same-origin timeseries responses that the
page itself produces.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import pandas as pd

from .exceptions import BarchartDecodeError, BarchartInteractiveChartError
from .history import (
    HistoryQualityReport,
    history_quality_report,
    read_barchart_history_text,
)
from .website import (
    PUBLIC_BARCHART_URL,
    ImportedHistory,
    _validated_base_url,
    _validated_segment,
)


def interactive_chart_url(
    symbol: str,
    *,
    asset_class: str = "futures",
    base_url: str = PUBLIC_BARCHART_URL,
) -> str:
    """Build an official Barchart interactive-chart URL."""

    base = _validated_base_url(base_url)
    asset_path = _validated_segment(asset_class, "asset_class")
    symbol_path = _validated_segment(symbol, "symbol")
    encoded_symbol = quote(symbol_path, safe="*._-")
    return f"{base}/{asset_path}/quotes/{encoded_symbol}/interactive-chart"


def download_history(
    symbol: str,
    *,
    asset_class: str = "futures",
    base_url: str = PUBLIC_BARCHART_URL,
    browser_executable: str | None = None,
    headless: bool = True,
    timeout_seconds: float = 120.0,
) -> ImportedHistory:
    """Load history from the official interactive chart into memory.

    The chart page makes the history request itself. This function observes
    that successful same-origin response, parses it, and closes the browser.
    It does not click controls, save files, automate sign-in, or call a
    separate historical endpoint.
    """

    captured = BarchartInteractiveChartWorkflow(
        base_url=base_url,
        browser_executable=browser_executable,
        headless=headless,
        timeout_seconds=timeout_seconds,
    ).capture_history(symbol, asset_class=asset_class)
    return ImportedHistory(
        path=None,
        frame=captured.frame,
        quality=captured.quality,
        source=captured.response_url,
    )


@dataclass(frozen=True)
class CapturedChartHistory:
    """Normalized history captured from one browser response."""

    frame: pd.DataFrame
    quality: HistoryQualityReport
    page_url: str
    response_url: str
    status_code: int


@dataclass(frozen=True)
class BarchartInteractiveChartWorkflow:
    """Implementation used by download_history.

    The browser extra is optional:

        python -m pip install "barchart-data[browser]"

    Barchart may still block a client/IP. In that case the workflow raises a
    descriptive error and does not attempt to bypass the restriction.
    """

    base_url: str = PUBLIC_BARCHART_URL
    browser_executable: str | None = None
    headless: bool = True
    timeout_seconds: float = 120.0

    def interactive_chart_url(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
    ) -> str:
        """Return the official interactive chart URL."""

        return interactive_chart_url(
            symbol,
            asset_class=asset_class,
            base_url=self.base_url,
        )

    def capture_history(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
    ) -> CapturedChartHistory:
        """Capture the history response naturally loaded by the chart page.

        The page's default chart range and interval are used. Only a successful
        same-origin response whose body parses as history is accepted.
        """

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BarchartInteractiveChartError(
                'Install the optional browser dependency with '
                '"python -m pip install \'barchart-data[browser]\'".'
            ) from exc

        chart_url = self.interactive_chart_url(symbol, asset_class=asset_class)
        candidates: list[tuple[Any, str]] = []
        page_status: int | None = None
        page_text = ""
        started = time.monotonic()

        def on_response(response: Any) -> None:
            if not self._is_chart_response(response, chart_url):
                return
            try:
                body = response.text()
            except (AttributeError, PlaywrightError):
                return
            candidates.append((response, body))

        with sync_playwright() as playwright:
            launch_kwargs: dict[str, Any] = {"headless": self.headless}
            executable = self.browser_executable or _installed_chrome()
            if executable:
                launch_kwargs["executable_path"] = executable
            try:
                browser = playwright.chromium.launch(**launch_kwargs)
            except Exception as exc:
                raise BarchartInteractiveChartError(
                    "Could not start the optional Playwright browser. "
                    "Install Chrome or run 'python -m playwright install chromium'."
                ) from exc
            try:
                page = browser.new_page()
                page.on("response", on_response)
                try:
                    response = page.goto(
                        chart_url,
                        wait_until="domcontentloaded",
                        timeout=int(self.timeout_seconds * 1000),
                    )
                    page_status = response.status if response else None
                    page_text = page.locator("body").inner_text(timeout=5000)
                except PlaywrightTimeoutError:
                    page_text = _safe_page_text(page)

                while time.monotonic() - started < self.timeout_seconds:
                    for response, body in tuple(candidates):
                        frame = _try_decode_chart_response(body, symbol=symbol)
                        if frame is None:
                            continue
                        return CapturedChartHistory(
                            frame=frame,
                            quality=history_quality_report(frame),
                            page_url=page.url,
                            response_url=response.url,
                            status_code=response.status,
                        )
                    page.wait_for_timeout(250)
            finally:
                browser.close()

        message = _access_message(
            chart_url,
            page_status=page_status,
            page_text=page_text,
        )
        raise BarchartInteractiveChartError(
            message,
            status_code=page_status,
            url=chart_url,
        )

    @staticmethod
    def _is_chart_response(response: Any, page_url: str) -> bool:
        """Return whether a page response looks like a chart history feed."""

        parsed_response = urlsplit(response.url)
        parsed_page = urlsplit(page_url)
        if parsed_response.netloc != parsed_page.netloc:
            return False
        path = parsed_response.path.casefold()
        if not any(token in path for token in ("timeseries", "historical", "queryeod")):
            return False
        content_type = response.headers.get("content-type", "").casefold()
        return response.status == 200 and (
            "csv" in content_type
            or "json" in content_type
            or "text/" in content_type
            or "octet-stream" in content_type
            or not content_type
        )


def _decode_chart_response(text: str, *, symbol: str | None) -> pd.DataFrame:
    if text.lstrip().startswith(("{", "[")):
        frame = _decode_json_chart_response(text, symbol=symbol)
        if frame is not None:
            return frame
    return read_barchart_history_text(text, symbol=symbol)


def _decode_json_chart_response(
    text: str,
    *,
    symbol: str | None,
) -> pd.DataFrame | None:
    import json

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    rows = _find_row_list(payload)
    if not rows:
        return None
    frame = _frame_from_json_rows(rows)
    if frame is None:
        return None
    try:
        return read_barchart_history_text(
            frame.to_csv(index=False),
            symbol=symbol,
        )
    except (BarchartDecodeError, TypeError, ValueError):
        return None


def _find_row_list(value: Any) -> list[Any] | None:
    if isinstance(value, list) and value and all(
        isinstance(row, (dict, list, tuple)) for row in value
    ):
        return value
    if isinstance(value, dict):
        for child in value.values():
            found = _find_row_list(child)
            if found:
                return found
    return None


def _frame_from_json_rows(rows: list[Any]) -> pd.DataFrame | None:
    if isinstance(rows[0], dict):
        return pd.DataFrame(rows)
    if not isinstance(rows[0], (list, tuple)):
        return None
    columns = {
        8: ["symbol", "date", "open", "high", "low", "close", "volume", "openInterest"],
        7: ["symbol", "date", "open", "high", "low", "close", "volume"],
        6: ["date", "open", "high", "low", "close", "volume"],
    }.get(len(rows[0]))
    if columns is None or any(len(row) != len(columns) for row in rows):
        return None
    return pd.DataFrame(rows, columns=columns)


def _safe_page_text(page: Any) -> str:
    try:
        return page.locator("body").inner_text(timeout=1000)
    except Exception:  # noqa: BLE001 - page text is best-effort diagnostics
        return ""


def _installed_chrome() -> str | None:
    """Find a normal installed Chrome binary without inspecting its profile."""

    windows_candidates = (
        Path(environ.get("PROGRAMFILES", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(environ.get("PROGRAMFILES(X86)", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(environ.get("LOCALAPPDATA", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
    )
    for candidate in windows_candidates:
        if candidate.is_file():
            return str(candidate)
    for command in ("google-chrome", "google-chrome-stable", "chrome"):
        executable = shutil.which(command)
        if executable:
            return executable
    return None


def _try_decode_chart_response(
    text: str,
    *,
    symbol: str | None,
) -> pd.DataFrame | None:
    try:
        return _decode_chart_response(text, symbol=symbol)
    except (BarchartDecodeError, TypeError, ValueError):
        return None


def _access_message(url: str, *, page_status: int | None, page_text: str) -> str:
    lowered = page_text.casefold()
    if page_status in {401, 403} or "cloudfront" in lowered or "not a robot" in lowered:
        return (
            f"Barchart did not provide chart data to this browser session "
            f"(HTTP {page_status or 403}). The package will not bypass CloudFront "
            f"or automate access controls. The official chart did not expose "
            f"history to this session: {url}"
        )
    return (
        "The interactive chart opened but no readable history response was "
        f"observed within the timeout: {url}"
    )


__all__ = [
    "download_history",
    "interactive_chart_url",
]

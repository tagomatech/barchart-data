"""Browser-assisted access to data naturally loaded by Barchart charts.

This module does not call undocumented endpoints, automate sign-in, inspect
cookies, or defeat bot protection. It opens the official chart in a normal
browser context and records only successful same-origin timeseries responses
that the page itself produces.
"""

from __future__ import annotations

import time
import webbrowser
from dataclasses import dataclass
from os import PathLike
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
    BarchartWebsiteWorkflow,
    ImportedHistory,
    PUBLIC_BARCHART_URL,
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
    """Capture chart history using a normal, user-visible browser session.

    The browser extra is optional:

        python -m pip install "barchart-data[browser]"

    Barchart may still require a permitted account or may block a client/IP.
    In that case the workflow raises a descriptive error and the manual CSV
    workflow remains the supported fallback.
    """

    download_dir: PathLike[str] | str | None = None
    base_url: str = PUBLIC_BARCHART_URL
    browser_executable: str | None = None
    cdp_endpoint: str | None = None
    headless: bool = False
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

    def open_interactive_chart(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
    ) -> str:
        """Open the official chart in the user's default browser."""

        url = self.interactive_chart_url(symbol, asset_class=asset_class)
        webbrowser.open(url, new=2)
        return url

    def download_interactive_csv(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
        timeout: float = 180.0,
        save_path: PathLike[str] | str | None = None,
    ) -> ImportedHistory:
        """Load a CSV downloaded through the chart UI into memory.

        The user remains in control of Barchart's chart menus and Download
        control. Playwright temporarily receives the browser download so it
        can be parsed in memory. The temporary artifact is deleted before the
        method returns. Set save_path, or the legacy download_dir option, to
        explicitly retain a local copy.
        """

        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BarchartInteractiveChartError(
                'Install the optional browser dependency with '
                '"python -m pip install \'barchart-data[browser]\'" '
                "and then run playwright install chromium."
            ) from exc

        chart_url = self.interactive_chart_url(symbol, asset_class=asset_class)
        page_status: int | None = None
        page_text = ""
        connected = self.cdp_endpoint is not None
        try:
            with sync_playwright() as playwright:
                launch_kwargs: dict[str, Any] = {"headless": self.headless}
                if self.browser_executable:
                    launch_kwargs["executable_path"] = self.browser_executable
                try:
                    if connected:
                        browser = playwright.chromium.connect_over_cdp(
                            self.cdp_endpoint
                        )
                    else:
                        browser = playwright.chromium.launch(**launch_kwargs)
                except Exception as exc:
                    raise BarchartInteractiveChartError(
                        "Could not start or connect to the optional Playwright "
                        "browser. Install its browser runtime, set "
                        "browser_executable, or check cdp_endpoint."
                    ) from exc

                page = None
                try:
                    if connected:
                        contexts = browser.contexts
                        if not contexts:
                            raise BarchartInteractiveChartError(
                                "The CDP browser has no usable browser context."
                            )
                        page = contexts[0].new_page()
                    else:
                        page = browser.new_page()

                    response = page.goto(
                        chart_url,
                        wait_until="domcontentloaded",
                        timeout=int(self.timeout_seconds * 1000),
                    )
                    page_status = response.status if response else None
                    page_text = _safe_page_text(page)
                    if page_status in {401, 403}:
                        raise BarchartInteractiveChartError(
                            _access_message(
                                chart_url,
                                page_status=page_status,
                                page_text=page_text,
                            ),
                            status_code=page_status,
                            url=chart_url,
                        )
                    download = page.wait_for_event(
                        "download",
                        timeout=int(timeout * 1000),
                    )
                    try:
                        temporary_path = download.path()
                        if temporary_path is None:
                            raise BarchartInteractiveChartError(
                                "Barchart reported a download without a readable "
                                "temporary file."
                            )
                        payload = Path(temporary_path).read_bytes()
                        workflow = BarchartWebsiteWorkflow(base_url=self.base_url)
                        filename = download.suggested_filename()
                        target = (
                            Path(save_path).expanduser()
                            if save_path is not None
                            else (
                                Path(self.download_dir).expanduser() / filename
                                if self.download_dir is not None
                                else None
                            )
                        )
                        if target is None:
                            return workflow.import_bytes(
                                payload,
                                symbol=symbol,
                                source_name=filename,
                            )
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(payload)
                        return workflow.import_csv(target, symbol=symbol)
                    finally:
                        download.delete()
                except PlaywrightTimeoutError as exc:
                    raise BarchartInteractiveChartError(
                        "No browser download was observed. Set the chart options "
                        "in Barchart's own UI and press its Download control.",
                        status_code=page_status,
                        url=chart_url,
                    ) from exc
                finally:
                    if page is not None:
                        page.close()
                    if not connected:
                        browser.close()
        except BarchartInteractiveChartError:
            raise
        except Exception as exc:
            raise BarchartInteractiveChartError(
                _access_message(
                    chart_url,
                    page_status=page_status,
                    page_text=page_text,
                ),
                status_code=page_status,
                url=chart_url,
            ) from exc

    def capture_history(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
        wait_for_user: bool = True,
    ) -> CapturedChartHistory:
        """Capture a chart history response from a normal browser page.

        The page is opened visibly by default. The caller may use Barchart's
        own chart menus while this method waits. Only a successful same-origin
        response whose body parses as history is accepted.
        """

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        try:
            from playwright.sync_api import (
                Error as PlaywrightError,
                TimeoutError as PlaywrightTimeoutError,
                sync_playwright,
            )
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
            if self.browser_executable:
                launch_kwargs["executable_path"] = self.browser_executable
            connected = self.cdp_endpoint is not None
            try:
                if connected:
                    browser = playwright.chromium.connect_over_cdp(self.cdp_endpoint)
                else:
                    browser = playwright.chromium.launch(**launch_kwargs)
            except Exception as exc:
                raise BarchartInteractiveChartError(
                    "Could not start or connect to the optional Playwright browser. "
                    "Install its browser runtime, set browser_executable, or "
                    "check cdp_endpoint."
                ) from exc
            try:
                if connected:
                    contexts = browser.contexts
                    if not contexts:
                        raise BarchartInteractiveChartError(
                            "The CDP browser has no usable browser context."
                        )
                    page = contexts[0].new_page()
                else:
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
                    if not wait_for_user and candidates:
                        break
                    page.wait_for_timeout(250)
            finally:
                if not connected:
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
            f"or automate access controls. Open the chart normally in your browser "
            f"or use the official CSV export, then import it locally: {url}"
        )
    return (
        "The interactive chart opened but no readable history response was "
        f"observed within the timeout. Use the chart's own controls or the "
        f"official CSV export: {url}"
    )


__all__ = [
    "BarchartInteractiveChartWorkflow",
    "CapturedChartHistory",
    "interactive_chart_url",
]

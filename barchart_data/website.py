"""Helpers for Barchart's supported manual historical CSV workflow.

This module deliberately stops at the website boundary. It can open the
official historical-download page and process a file already downloaded by
the user, but it does not sign in, click private controls, or call
undocumented download endpoints.
"""

from __future__ import annotations

import time
import webbrowser
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import pandas as pd

from .history import (
    HistoryQualityReport,
    history_quality_report,
    read_barchart_history_bytes,
    read_barchart_history_csv,
    read_barchart_history_text,
)

PUBLIC_BARCHART_URL = "https://www.barchart.com"


def historical_download_url(
    symbol: str,
    *,
    asset_class: str = "futures",
    base_url: str = PUBLIC_BARCHART_URL,
) -> str:
    """Build an official Barchart historical-download page URL."""

    base = _validated_base_url(base_url)
    asset_path = _validated_segment(asset_class, "asset_class")
    symbol_path = _validated_segment(symbol, "symbol")
    encoded_symbol = quote(symbol_path, safe="*._-")
    return f"{base}/{asset_path}/quotes/{encoded_symbol}/historical-download"


@dataclass(frozen=True)
class ImportedHistory:
    """A normalized history with optional local-file provenance."""

    path: Path | None
    frame: pd.DataFrame
    quality: HistoryQualityReport
    source: str | None = None


@dataclass(frozen=True)
class BarchartWebsiteWorkflow:
    """Coordinate the user-led website export and local CSV import steps."""

    download_dir: PathLike[str] | str | None = None
    base_url: str = PUBLIC_BARCHART_URL

    @property
    def directory(self) -> Path | None:
        """Return the configured browser download directory, if any."""

        if self.download_dir is None:
            return None
        return Path(self.download_dir).expanduser()

    def historical_download_url(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
    ) -> str:
        """Return the official historical-download page for symbol."""

        return historical_download_url(
            symbol,
            asset_class=asset_class,
            base_url=self.base_url,
        )

    def open_historical_download_page(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
    ) -> str:
        """Open the official page in the user's default browser.

        The caller remains responsible for any account interaction and for
        pressing Barchart's Download control.
        """

        url = self.historical_download_url(symbol, asset_class=asset_class)
        webbrowser.open(url, new=2)
        return url

    def find_csv(
        self,
        *,
        symbol: str | None = None,
        since: float | None = None,
    ) -> tuple[Path, ...]:
        """Find local CSV files, newest first, optionally filtered by symbol."""

        directory = self.directory
        if directory is None or not directory.is_dir():
            return ()
        symbol_token = symbol.casefold() if symbol else None
        matches: list[tuple[float, Path]] = []
        for path in directory.glob("*.csv"):
            if not path.is_file() or path.name.startswith("~$"):
                continue
            if symbol_token and symbol_token not in path.stem.casefold():
                continue
            try:
                modified = path.stat().st_mtime
            except OSError:
                continue
            if since is not None and modified < since:
                continue
            matches.append((modified, path))
        matches.sort(
            key=lambda item: (item[0], item[1].name.casefold()),
            reverse=True,
        )
        return tuple(path for _, path in matches)

    def latest_csv_path(
        self,
        *,
        symbol: str | None = None,
        since: float | None = None,
    ) -> Path:
        """Return the newest matching local CSV or raise a useful error."""

        matches = self.find_csv(symbol=symbol, since=since)
        if not matches:
            location = self.directory
            qualifier = f" for {symbol}" if symbol else ""
            if location is None:
                raise FileNotFoundError(
                    f"No Barchart CSV{qualifier} was searched for because "
                    "download_dir is not configured. Pass an explicit CSV path "
                    "to import_csv or set download_dir for local-file watching."
                )
            raise FileNotFoundError(
                f"No Barchart CSV{qualifier} found in {location}. "
                "Download it from the official historical-data page first."
            )
        return matches[0]

    def wait_for_csv(
        self,
        *,
        symbol: str | None = None,
        since: float | None = None,
        timeout: float = 180.0,
        poll_interval: float = 1.0,
    ) -> Path:
        """Wait for a new CSV to appear and stop changing.

        This watches only the local download directory. It is useful after the
        user has opened the page and clicked Download manually. Temporary
        browser files are ignored and a file must have the same size and
        modification time across two observations.
        """

        if timeout <= 0 or poll_interval <= 0:
            raise ValueError("timeout and poll_interval must be positive")
        if self.directory is None:
            raise ValueError(
                "download_dir is required when waiting for a local browser download"
            )
        started = time.monotonic()
        observed: dict[Path, tuple[int, int]] = {}
        minimum_mtime = time.time() if since is None else since
        while time.monotonic() - started < timeout:
            for path in self.find_csv(symbol=symbol, since=minimum_mtime):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                state = (stat.st_size, stat.st_mtime_ns)
                if state[0] > 0 and observed.get(path) == state:
                    return path
                observed[path] = state
            time.sleep(poll_interval)
        raise TimeoutError(
            f"No stable Barchart CSV appeared in {self.directory} within {timeout:g}s."
        )

    def import_csv(
        self,
        source: PathLike[str] | str,
        *,
        symbol: str | None = None,
        sort: bool = True,
        sep: str | None = None,
    ) -> ImportedHistory:
        """Import one local export and attach a quality report."""

        path = Path(source).expanduser()
        frame = read_barchart_history_csv(
            path,
            symbol=symbol,
            sort=sort,
            sep=sep,
        )
        quality = history_quality_report(frame)
        return ImportedHistory(path=path, frame=frame, quality=quality)

    def import_text(
        self,
        text: str,
        *,
        symbol: str | None = None,
        sort: bool = True,
        source: str | None = None,
    ) -> ImportedHistory:
        """Parse a Barchart export held in memory without creating a file."""

        frame = read_barchart_history_text(text, symbol=symbol, sort=sort)
        quality = history_quality_report(frame)
        return ImportedHistory(
            path=None,
            frame=frame,
            quality=quality,
            source=source,
        )

    def import_bytes(
        self,
        source: bytes,
        *,
        symbol: str | None = None,
        sort: bool = True,
        encoding: str = "utf-8-sig",
        source_name: str | None = None,
    ) -> ImportedHistory:
        """Parse an in-memory Barchart download without creating a file."""

        frame = read_barchart_history_bytes(
            source,
            symbol=symbol,
            sort=sort,
            encoding=encoding,
        )
        quality = history_quality_report(frame)
        return ImportedHistory(
            path=None,
            frame=frame,
            quality=quality,
            source=source_name,
        )

    def import_latest_csv(
        self,
        *,
        symbol: str | None = None,
        since: float | None = None,
        sort: bool = True,
        sep: str | None = None,
    ) -> ImportedHistory:
        """Import the newest matching CSV from the configured directory."""

        path = self.latest_csv_path(symbol=symbol, since=since)
        return self.import_csv(path, symbol=symbol, sort=sort, sep=sep)


def _validated_segment(value: str, name: str) -> str:
    text = str(value).strip()
    if not text or "/" in text or chr(92) in text or any(
        char.isspace() for char in text
    ):
        raise ValueError(f"{name} must be one non-empty URL path segment")
    return text


def _validated_base_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


__all__ = [
    "PUBLIC_BARCHART_URL",
    "BarchartWebsiteWorkflow",
    "ImportedHistory",
    "historical_download_url",
]

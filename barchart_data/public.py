"""No-login access to data embedded in public Barchart quote pages.

This adapter reads the JSON block that Barchart publishes in quote-page HTML.
The public page feed is smaller, may be delayed, and can change independently
from Barchart's account-level products.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping, Sequence
from threading import Lock
from time import monotonic, sleep
from typing import Any, Literal, TypeAlias

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    BarchartDecodeError,
    BarchartPublicPageError,
    BarchartTransportError,
)

PUBLIC_ROOT = "https://www.barchart.com"
INLINE_DATA_ID = "barchart-www-inline-data"
DEFAULT_USER_AGENT = (
    "barchart-data/0.7.0 "
    "(+https://github.com/tagomatech/barchart-data)"
)
DEFAULT_MIN_REQUEST_INTERVAL = 1.0
DEFAULT_PAGE_CACHE_TTL = 300.0
PublicOutput = pd.DataFrame | list[dict[str, Any]]
PublicHistoryOutput: TypeAlias = (
    pd.DataFrame | list[dict[str, Any]] | dict[str, Any] | str
)
_OUTPUTS = {"df", "json"}
_HISTORY_OUTPUTS = {"df", "dict", "text"}
_HISTORY_FREQUENCIES = {"daily", "weekly", "monthly"}
_HISTORY_ORDERS = {"asc", "desc"}
_ASSET_CLASS = re.compile(r"^[A-Za-z0-9_-]+$")
_INLINE_SCRIPT = re.compile(
    r"<script(?=[^>]*\bid=[\"']"
    + re.escape(INLINE_DATA_ID)
    + r"[\"'])[^>]*>(.*?)</script>",
    flags=re.IGNORECASE | re.DOTALL,
)


class PublicBarchartClient:
    """Read quote-page data from Barchart without an API key or login.

    The client uses public overview pages such as
    /futures/quotes/ZCU26/overview. It does not bypass authentication or call
    account-only or undocumented endpoints.
    """

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        web_base_url: str = PUBLIC_ROOT,
        user_agent: str | None = None,
        request_timeout: float | tuple[float, float] = 15.0,
        max_retries: int = 2,
        retry_backoff_factor: float = 1.0,
        min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL,
        page_cache_ttl: float | None = DEFAULT_PAGE_CACHE_TTL,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_backoff_factor < 0:
            raise ValueError("retry_backoff_factor must be >= 0")
        if min_request_interval < 0:
            raise ValueError("min_request_interval must be >= 0")
        if page_cache_ttl is not None and page_cache_ttl < 0:
            raise ValueError("page_cache_ttl must be >= 0 or None")
        self.request_timeout = _validate_timeout(request_timeout)
        self.web_base_url = web_base_url.rstrip("/")
        self.min_request_interval = min_request_interval
        self.page_cache_ttl = page_cache_ttl
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent or DEFAULT_USER_AGENT})
        self._configure_retries(max_retries, retry_backoff_factor)
        self._request_lock = Lock()
        self._next_request_at = 0.0
        self._page_cache: dict[
            tuple[str, str], tuple[float, dict[str, Any]]
        ] = {}
        self._cache_lock = Lock()

    def _configure_retries(self, max_retries: int, backoff_factor: float) -> None:
        mount = getattr(self.session, "mount", None)
        if mount is None:
            return
        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        mount("http://", adapter)
        mount("https://", adapter)

    def _wait_for_request_slot(self) -> None:
        """Serialize this client's requests with a small polite delay."""
        if self.min_request_interval == 0:
            return
        with self._request_lock:
            now = monotonic()
            delay = max(0.0, self._next_request_at - now)
            self._next_request_at = max(now, self._next_request_at) + (
                self.min_request_interval
            )
            if delay:
                sleep(delay)

    def clear_cache(
        self,
        symbol: str | None = None,
        *,
        asset_class: str | None = None,
    ) -> None:
        """Clear cached public pages, optionally for one symbol/category."""
        with self._cache_lock:
            if symbol is None and asset_class is None:
                self._page_cache.clear()
                return
            keys = list(self._page_cache)
            for key_symbol, key_asset_class in keys:
                if symbol is not None and key_symbol != symbol:
                    continue
                if asset_class is not None and key_asset_class != asset_class:
                    continue
                self._page_cache.pop((key_symbol, key_asset_class), None)

    def page_url(self, symbol: str, *, asset_class: str = "futures") -> str:
        """Return the public overview URL for a symbol."""
        symbol = _validate_symbol(symbol)
        asset_class = _validate_asset_class(asset_class)
        return f"{self.web_base_url}/{asset_class}/quotes/{symbol}/overview"

    def page(self, symbol: str, *, asset_class: str = "futures") -> dict[str, Any]:
        """Fetch and decode the complete embedded page payload."""
        symbol = _validate_symbol(symbol)
        asset_class = _validate_asset_class(asset_class)
        url = self.page_url(symbol, asset_class=asset_class)
        cache_key = (symbol, asset_class)
        if self.page_cache_ttl != 0:
            with self._cache_lock:
                cached = self._page_cache.get(cache_key)
                if cached is not None:
                    cached_at, payload = cached
                    if (
                        self.page_cache_ttl is None
                        or monotonic() - cached_at < self.page_cache_ttl
                    ):
                        return dict(payload)
                    self._page_cache.pop(cache_key, None)
        try:
            self._wait_for_request_slot()
            response = self.session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = getattr(exc.response, "status_code", None)
            raise BarchartPublicPageError(
                f"Barchart public page returned HTTP status {status_code} for {symbol}.",
                status_code=status_code,
                url=url,
            ) from exc
        except requests.RequestException as exc:
            raise BarchartTransportError(
                f"Barchart public page request failed for {url}: {exc}"
            ) from exc

        match = _INLINE_SCRIPT.search(response.text)
        if match is None:
            raise BarchartPublicPageError(
                f"Barchart public page has no {INLINE_DATA_ID!r} block for {symbol}.",
                status_code=response.status_code,
                url=url,
            )
        try:
            payload = json.loads(html.unescape(match.group(1).strip()))
        except json.JSONDecodeError as exc:
            raise BarchartDecodeError(
                f"Barchart public page contains invalid embedded JSON for {symbol}."
            ) from exc
        if not isinstance(payload, Mapping):
            raise BarchartDecodeError(
                f"Barchart public page payload for {symbol} must be an object."
            )
        result = dict(payload)
        if self.page_cache_ttl != 0:
            with self._cache_lock:
                self._page_cache[cache_key] = (monotonic(), result)
        return dict(result)

    def quote(
        self,
        symbols: str | Sequence[str],
        *,
        asset_class: str = "futures",
        output: Literal["df", "json"] = "df",
    ) -> PublicOutput:
        """Return current quote fields plus instrument metadata."""
        records = []
        for requested_symbol in _symbols(symbols):
            payload = self.page(requested_symbol, asset_class=asset_class)
            entry = _select_symbol(payload, requested_symbol)
            quote = entry.get("quote", {})
            instrument = entry.get("instrument", {})
            if not isinstance(quote, Mapping) or not isinstance(instrument, Mapping):
                raise BarchartDecodeError(
                    f"Barchart public page payload for {requested_symbol} "
                    "has invalid quote or instrument data."
                )
            record: dict[str, Any] = {
                "symbol": requested_symbol,
                "asset_class": asset_class,
            }
            record.update(dict(quote))
            record.update(
                {f"instrument_{key}": value for key, value in instrument.items()}
            )
            records.append(record)
        return _format_output(records, output)

    def profile(
        self,
        symbols: str | Sequence[str],
        *,
        asset_class: str = "futures",
        output: Literal["df", "json"] = "df",
    ) -> PublicOutput:
        """Return instrument metadata embedded in public quote pages."""
        records = []
        for requested_symbol in _symbols(symbols):
            payload = self.page(requested_symbol, asset_class=asset_class)
            entry = _select_symbol(payload, requested_symbol)
            instrument = entry.get("instrument", {})
            if not isinstance(instrument, Mapping):
                raise BarchartDecodeError(
                    f"Barchart public page payload for {requested_symbol} "
                    "has invalid instrument data."
                )
            record = dict(instrument)
            record["symbol"] = requested_symbol
            record["asset_class"] = asset_class
            records.append(record)
        return _format_output(records, output)

    def history(self, symbol: str, **kwargs: Any) -> Any:
        """Fetch best-effort public historical data without an API key.

        Barchart's current public frontend uses a JSON proxy under
        /proxies/core-api/v1. Anonymous history is limited by Barchart and
        may be denied even though quote pages remain public. A 401/403 is
        surfaced as BarchartPublicPageError with the endpoint and a useful
        explanation.

        The legacy BarchartClient remains available for callers that
        explicitly need its old response decoder or endpoint contract.
        """
        return self._history(
            symbol,
            asset_class=kwargs.pop("asset_class", "futures"),
            **kwargs,
        )

    def _history(
        self,
        symbol: str,
        *,
        asset_class: str = "futures",
        maxrecords: int | None = 640,
        data: Literal["daily", "weekly", "monthly"] = "daily",
        out: Literal["df", "dict", "text"] = "df",
        startDate: str | None = None,
        endDate: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        volume: str | None = None,
        order: Literal["asc", "desc"] = "asc",
        dividends: Literal["true", "false"] = "false",
        backadjust: Literal["true", "false"] = "false",
        daystoexpiration: int | None = 1,
        contractroll: Literal["none", "combined"] = "combined",
        **extra_params: Any,
    ) -> PublicHistoryOutput:
        symbol = _validate_symbol(symbol)
        asset_class = _validate_asset_class(asset_class)
        if data not in _HISTORY_FREQUENCIES:
            raise ValueError(
                f"data must be one of: {sorted(_HISTORY_FREQUENCIES)}"
            )
        if out not in _HISTORY_OUTPUTS:
            raise ValueError(f"out must be one of: {sorted(_HISTORY_OUTPUTS)}")
        if maxrecords is not None and maxrecords < 1:
            raise ValueError("maxrecords must be >= 1 or None")
        if order not in _HISTORY_ORDERS:
            raise ValueError(f"order must be one of: {sorted(_HISTORY_ORDERS)}")
        if daystoexpiration is not None and daystoexpiration < 0:
            raise ValueError("daystoexpiration must be >= 0 or None")

        start = _coalesce_date(start_date, startDate, "start_date", "startDate")
        end = _coalesce_date(end_date, endDate, "end_date", "endDate")
        if start is not None and end is not None:
            if pd.Timestamp(start) > pd.Timestamp(end):
                raise ValueError(
                    "start_date must be earlier than or equal to end_date"
                )

        params: dict[str, Any] = {
            "symbol": symbol,
            "fields": (
                "symbol,tradeTime,openPrice,highPrice,lowPrice,"
                "lastPrice,volume,openInterest"
            ),
            "type": "eod",
            "orderBy": "tradeTime",
            "orderDir": order,
        }
        if start is not None:
            params["startDate"] = start
        if end is not None:
            params["endDate"] = end
        if start is None and end is None:
            params["range"] = 90
        if maxrecords is not None:
            params["limit"] = maxrecords
        if data != "daily":
            params["frequency"] = data
        if volume is not None:
            params["volume"] = volume
        params.update(
            {
                "dividends": dividends,
                "backadjust": backadjust,
                "daystoexpiration": daystoexpiration,
                "contractroll": contractroll,
            }
        )

        conflicts = set(params).intersection(extra_params)
        if conflicts:
            names = ", ".join(sorted(conflicts))
            raise ValueError(f"extra parameters cannot override: {names}")
        params.update(extra_params)

        url = f"{self.web_base_url}/proxies/core-api/v1/historical/get"
        try:
            self._wait_for_request_slot()
            response = self.session.get(
                url,
                params=params,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Referer": self.page_url(symbol, asset_class=asset_class),
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=self.request_timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {401, 403}:
                message = (
                    f"Barchart denied anonymous historical data for {symbol} "
                    f"(HTTP {status_code}). Quote/profile pages are public, "
                    "but this history route may require a Barchart session "
                    "or an eligible Barchart account or subscription."
                )
            else:
                message = (
                    f"Barchart public history returned HTTP status "
                    f"{status_code} for {symbol}."
                )
            raise BarchartPublicPageError(
                message,
                status_code=status_code,
                url=url,
            ) from exc
        except requests.RequestException as exc:
            raise BarchartTransportError(
                f"Barchart public history request failed for {url}: {exc}"
            ) from exc

        body = response.text.strip()
        if not body:
            raise BarchartDecodeError(
                f"Barchart returned an empty history response for {symbol}."
            )
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise BarchartDecodeError(
                f"Barchart returned invalid history JSON for {symbol}."
            ) from exc
        if isinstance(payload, Mapping) and (
            payload.get("error") or payload.get("errors")
        ):
            raise BarchartPublicPageError(
                f"Barchart returned an error for public history of {symbol}: "
                f"{payload}",
                status_code=response.status_code,
                url=url,
            )
        if out == "text":
            return body
        if out == "dict":
            return payload

        records = _history_records(payload)
        frame = _history_frame(records, symbol=symbol)
        return _clip_history_frame(frame, start=start, end=end)


PublicWebClient = PublicBarchartClient
BarchartPublicClient = PublicBarchartClient


def _validate_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    if "/" in symbol or "\\" in symbol:
        raise ValueError("symbol must not contain path separators")
    return symbol.strip()


def _validate_asset_class(asset_class: str) -> str:
    if not isinstance(asset_class, str) or not _ASSET_CLASS.fullmatch(asset_class):
        raise ValueError(
            "asset_class must contain only letters, numbers, underscores, or hyphens"
        )
    return asset_class


def _symbols(symbols: str | Sequence[str]) -> list[str]:
    if isinstance(symbols, str):
        values = [symbols]
    else:
        values = list(symbols)
    if not values:
        raise ValueError("symbols must not be empty")
    return [_validate_symbol(symbol) for symbol in values]


def _select_symbol(payload: Mapping[str, Any], requested_symbol: str) -> Mapping[str, Any]:
    if requested_symbol in payload and isinstance(payload[requested_symbol], Mapping):
        return payload[requested_symbol]
    requested_casefold = requested_symbol.casefold()
    for key, value in payload.items():
        if str(key).casefold() == requested_casefold and isinstance(value, Mapping):
            return value
    if "quote" in payload or "instrument" in payload:
        return payload
    raise BarchartDecodeError(
        f"Barchart public page payload has no entry for {requested_symbol}."
    )


def _format_output(
    records: list[dict[str, Any]], output: Literal["df", "json"]
) -> PublicOutput:
    if output not in _OUTPUTS:
        raise ValueError(f"output must be one of: {sorted(_OUTPUTS)}")
    return pd.DataFrame(records) if output == "df" else records


def _coalesce_date(
    preferred: str | None,
    legacy: str | None,
    preferred_name: str,
    legacy_name: str,
) -> str | None:
    if preferred is not None and legacy is not None and preferred != legacy:
        raise ValueError(f"{preferred_name} and {legacy_name} disagree")
    return preferred if preferred is not None else legacy


def _history_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        records = payload.get("data", payload.get("results", payload.get("rows")))
    else:
        records = payload
    if not isinstance(records, list) or not all(
        isinstance(row, Mapping) for row in records
    ):
        raise BarchartDecodeError(
            "Barchart public history JSON does not contain tabular records."
        )
    return [dict(row) for row in records]


def _history_frame(records: list[dict[str, Any]], *, symbol: str) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame

    aliases = {
        "date": ("date", "tradeTime", "tradeDate", "timestamp"),
        "open": ("open", "openPrice"),
        "high": ("high", "highPrice"),
        "low": ("low", "lowPrice"),
        "close": ("close", "lastPrice"),
        "volume": ("volume", "vol"),
        "openInterest": ("openInterest", "open_interest"),
    }
    normalized: dict[str, Any] = {}
    for target, candidates in aliases.items():
        for candidate in candidates:
            if candidate in frame.columns:
                normalized[target] = frame[candidate]
                break
    if "date" not in normalized:
        raise BarchartDecodeError(
            f"Barchart public history has no date field for {symbol}."
        )

    result = pd.DataFrame(normalized)
    if "symbol" in frame.columns:
        result.insert(0, "symbol", frame["symbol"].fillna(symbol))
    else:
        result.insert(0, "symbol", symbol)
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    if result["date"].isna().any():
        raise BarchartDecodeError(
            f"Barchart public history contains an invalid date for {symbol}."
        )
    for column in ("open", "high", "low", "close", "volume", "openInterest"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _clip_history_frame(
    frame: pd.DataFrame,
    *,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return frame
    dates = pd.to_datetime(frame["date"], errors="coerce")
    mask = dates.notna()
    if start is not None:
        mask &= dates >= pd.Timestamp(start)
    if end is not None:
        mask &= dates <= pd.Timestamp(end)
    return frame.loc[mask].reset_index(drop=True)


def _validate_timeout(
    value: float | tuple[float, float],
) -> float | tuple[float, float]:
    if isinstance(value, tuple):
        if len(value) != 2 or any(part <= 0 for part in value):
            raise ValueError("request_timeout tuple values must be > 0")
        return value
    if value <= 0:
        raise ValueError("request_timeout must be > 0")
    return value


__all__ = [
    "BarchartPublicClient",
    "PublicBarchartClient",
    "PublicWebClient",
]

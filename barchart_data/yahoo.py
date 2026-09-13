"""Public exact-contract history used when Barchart denies a chart session.

This adapter uses Yahoo Finance's public chart response for futures that Yahoo
identifies with an exchange suffix such as ZCU26.CBT. It is deliberately kept
separate from the Barchart browser workflow: it does not claim that the
returned data came from Barchart, and it does not attempt to defeat a Barchart
restriction.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from time import time
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests

from .exceptions import PublicChartError
from .history import history_quality_report, normalize_barchart_history
from .website import ImportedHistory

PUBLIC_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
_SYMBOL = re.compile(r"^[A-Za-z0-9*._-]+$")
_USER_AGENT = (
    "barchart-data/0.10.0 "
    "(+https://github.com/tagomatech/barchart-data)"
)


def yahoo_futures_symbol(symbol: str) -> str:
    """Map a Barchart CBOT contract symbol to Yahoo's exact-contract symbol."""

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    value = symbol.strip()
    if not _SYMBOL.fullmatch(value):
        raise ValueError(
            "futures symbols may contain only letters, numbers, '*', '.', '_', "
            "or '-'."
        )
    if value.casefold().endswith(".cbt"):
        return value
    return f"{value}.CBT"


def _download_yahoo_futures_history(
    symbol: str,
    *,
    timeout_seconds: float = 30.0,
    session: requests.Session | Any | None = None,
) -> ImportedHistory:
    """Read one exact futures contract from the public Yahoo chart response."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    yahoo_symbol = yahoo_futures_symbol(symbol)
    encoded_symbol = quote(yahoo_symbol, safe="._-")
    url = f"{PUBLIC_YAHOO_CHART_URL}/{encoded_symbol}"
    params = {
        "period1": 0,
        "period2": int(time()) + 60,
        "interval": "1d",
        "events": "history",
        "includePrePost": "false",
    }
    client = session or requests.Session()
    try:
        response = client.get(
            url,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        raise PublicChartError(
            f"Public exact-contract chart feed returned HTTP status "
            f"{status_code} for {yahoo_symbol}.",
            status_code=status_code,
            url=url,
        ) from exc
    except requests.RequestException as exc:
        raise PublicChartError(
            f"Public exact-contract chart request failed for {yahoo_symbol}: "
            f"{exc}"
        ) from exc

    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise PublicChartError(
            f"Public exact-contract chart response for {yahoo_symbol} was "
            "not valid JSON.",
            url=url,
        ) from exc

    chart = payload.get("chart") if isinstance(payload, Mapping) else None
    if not isinstance(chart, Mapping):
        raise PublicChartError(
            f"Public exact-contract chart response for {yahoo_symbol} has "
            "no chart object.",
            url=url,
        )
    chart_error = chart.get("error")
    if chart_error:
        description = (
            chart_error.get("description", "unknown chart error")
            if isinstance(chart_error, Mapping)
            else str(chart_error)
        )
        raise PublicChartError(
            f"Public exact-contract chart rejected {yahoo_symbol}: {description}",
            url=url,
        )
    results = chart.get("result")
    if not isinstance(results, list) or not results:
        raise PublicChartError(
            f"Public exact-contract chart returned no result for {yahoo_symbol}.",
            url=url,
        )

    result = results[0]
    try:
        metadata = result["meta"]
        timestamps = result["timestamp"]
        quote_data = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise PublicChartError(
            f"Public exact-contract chart response for {yahoo_symbol} has "
            "an unsupported layout.",
            url=url,
        ) from exc
    if not isinstance(metadata, Mapping) or not isinstance(quote_data, Mapping):
        raise PublicChartError(
            f"Public exact-contract chart response for {yahoo_symbol} has "
            "invalid metadata or quote data.",
            url=url,
        )
    if str(metadata.get("instrumentType", "")).upper() not in {"FUTURE", "FUTURES"}:
        raise PublicChartError(
            f"Public chart symbol {yahoo_symbol} is not identified as a future.",
            url=url,
        )
    if not isinstance(timestamps, list) or not timestamps:
        raise PublicChartError(
            f"Public exact-contract chart returned no daily observations for "
            f"{yahoo_symbol}.",
            url=url,
        )

    frame = pd.DataFrame(
        {
            "date": timestamps,
            "open": _values(quote_data, "open", len(timestamps), url),
            "high": _values(quote_data, "high", len(timestamps), url),
            "low": _values(quote_data, "low", len(timestamps), url),
            "close": _values(quote_data, "close", len(timestamps), url),
            "volume": _values(quote_data, "volume", len(timestamps), url),
        }
    )
    frame = frame.loc[frame["close"].notna()].copy()
    if frame.empty:
        raise PublicChartError(
            f"Public exact-contract chart returned no priced observations for "
            f"{yahoo_symbol}.",
            url=url,
        )
    timezone = metadata.get("exchangeTimezoneName") or "UTC"
    try:
        dates = pd.to_datetime(frame["date"], unit="s", utc=True)
        frame["date"] = (
            dates.dt.tz_convert(str(timezone))
            .dt.normalize()
            .dt.tz_localize(None)
        )
    except (TypeError, ValueError) as exc:
        raise PublicChartError(
            f"Public exact-contract chart returned invalid dates for "
            f"{yahoo_symbol}.",
            url=url,
        ) from exc

    frame.insert(0, "symbol", symbol.strip())
    frame = normalize_barchart_history(frame, symbol=symbol.strip())
    source = getattr(response, "url", None) or url
    return ImportedHistory(
        path=None,
        frame=frame,
        quality=history_quality_report(frame),
        source=str(source),
    )


def _values(
    quote_data: Mapping[str, Any],
    name: str,
    length: int,
    url: str,
) -> list[Any]:
    values = quote_data.get(name)
    if values is None:
        if name == "volume":
            return [None] * length
        raise PublicChartError(
            f"Public exact-contract chart response has no {name!r} column.",
            url=url,
        )
    if not isinstance(values, list) or len(values) != length:
        raise PublicChartError(
            f"Public exact-contract chart response has an invalid {name!r} "
            "column.",
            url=url,
        )
    return values


__all__ = ["PUBLIC_YAHOO_CHART_URL", "yahoo_futures_symbol"]

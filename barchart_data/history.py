"""Normalize historical data returned or downloaded from Barchart."""

from __future__ import annotations

import re
from collections.abc import Mapping
from os import PathLike
from typing import IO, Any, TypeAlias

import pandas as pd

from .exceptions import BarchartDecodeError

HistorySource: TypeAlias = str | PathLike[str] | IO[str]

_COLUMN_ALIASES: Mapping[str, tuple[str, ...]] = {
    "symbol": ("symbol", "ticker", "code"),
    "timestamp": ("timestamp", "datetime", "tradetime", "time"),
    "date": ("date", "tradingday", "tradeday", "tradedate"),
    "open": ("open", "openprice"),
    "high": ("high", "highprice"),
    "low": ("low", "lowprice"),
    "close": ("close", "last", "lastprice"),
    "settlement": ("settlement", "settle", "set"),
    "volume": ("volume", "vol"),
    "openInterest": ("openinterest", "open_interest", "oi"),
}
_NUMERIC_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "settlement",
    "volume",
    "openInterest",
)


def read_barchart_history_csv(
    source: HistorySource,
    *,
    symbol: str | None = None,
    sort: bool = True,
) -> pd.DataFrame:
    """Read a CSV downloaded from Barchart's historical-data page.

    This function is intentionally a local-file importer. It does not log in,
    automate a browser, or call a private Barchart endpoint. It accepts the
    CSV layouts used by Barchart's website and OnDemand API, keeps the source
    columns, and adds stable date/OHLCV column names for downstream code.
    """

    try:
        frame = pd.read_csv(source)
    except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as exc:
        raise BarchartDecodeError(
            f"Could not read Barchart history CSV from {source!r}."
        ) from exc
    return normalize_barchart_history(frame, symbol=symbol, sort=sort)


def normalize_barchart_history(
    frame: pd.DataFrame,
    *,
    symbol: str | None = None,
    sort: bool = True,
) -> pd.DataFrame:
    """Add stable fields to a Barchart historical DataFrame.

    Native Barchart names such as tradingDay, lastPrice and openInterest are
    retained. Canonical aliases are added only when they are not already
    present. Dates are normalized to naive UTC timestamps.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    result = frame.copy()
    if result.empty:
        return result

    lookup = _column_lookup(result.columns)

    def source(*aliases: str) -> pd.Series | None:
        for alias in aliases:
            column = lookup.get(_normalize_header(alias))
            if column is not None:
                return result[column]
        return None

    if "date" not in result.columns:
        dates = source(*_COLUMN_ALIASES["date"])
        if dates is None:
            dates = source(*_COLUMN_ALIASES["timestamp"])
        if dates is None:
            raise BarchartDecodeError(
                "Barchart history does not contain a date or timestamp column."
            )
        result["date"] = dates
    result["date"] = pd.to_datetime(
        result["date"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None)
    if result["date"].isna().any():
        raise BarchartDecodeError(
            "Barchart history contains one or more invalid dates."
        )

    if "symbol" not in result.columns:
        symbols = source(*_COLUMN_ALIASES["symbol"])
        if symbols is not None:
            result["symbol"] = symbols
    if symbol is not None:
        normalized_symbol = str(symbol).strip()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if "symbol" not in result.columns:
            result.insert(0, "symbol", normalized_symbol)
        else:
            result["symbol"] = result["symbol"].fillna(normalized_symbol)

    for target in _NUMERIC_COLUMNS:
        if target in result.columns:
            continue
        values = source(*_COLUMN_ALIASES[target])
        if values is not None:
            result[target] = values

    if "close" not in result.columns and "settlement" in result.columns:
        result["close"] = result["settlement"]

    for column in _NUMERIC_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    if not any(
        column in result.columns
        for column in ("open", "high", "low", "close", "settlement")
    ):
        raise BarchartDecodeError(
            "Barchart history does not contain a supported price column."
        )

    if sort:
        result = result.sort_values("date", kind="stable")
    return result.reset_index(drop=True)

def _column_lookup(columns: Any) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for column in columns:
        lookup.setdefault(_normalize_header(column), column)
    return lookup


def _normalize_header(value: Any) -> str:
    text = str(value).strip().lstrip("\ufeff").lower()
    return re.sub(r"[^a-z0-9]+", "", text)


read_barchart_csv = read_barchart_history_csv


__all__ = [
    "HistorySource",
    "normalize_barchart_history",
    "read_barchart_csv",
    "read_barchart_history_csv",
]

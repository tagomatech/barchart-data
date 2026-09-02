"""Normalize historical CSV data downloaded from Barchart."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class HistoryQualityReport:
    """Small, serializable summary of a normalized history frame."""

    rows: int
    columns: tuple[str, ...]
    start_date: pd.Timestamp | None
    end_date: pd.Timestamp | None
    duplicate_dates: int
    missing_columns: tuple[str, ...]
    missing_values: Mapping[str, int]

    @property
    def is_usable(self) -> bool:
        """Return whether the frame has complete required fields."""

        return (
            self.rows > 0
            and not self.missing_columns
            and not any(self.missing_values.values())
        )

    def as_dict(self) -> dict[str, Any]:
        """Return values suitable for display or JSON serialization."""

        return {
            "rows": self.rows,
            "columns": list(self.columns),
            "start_date": (
                self.start_date.isoformat() if self.start_date is not None else None
            ),
            "end_date": (
                self.end_date.isoformat() if self.end_date is not None else None
            ),
            "duplicate_dates": self.duplicate_dates,
            "missing_columns": list(self.missing_columns),
            "missing_values": dict(self.missing_values),
            "is_usable": self.is_usable,
        }


def read_barchart_history_csv(
    source: HistorySource,
    *,
    symbol: str | None = None,
    sort: bool = True,
    sep: str | None = None,
    encoding: str = "utf-8-sig",
) -> pd.DataFrame:
    """Read a CSV downloaded from Barchart's historical-data page.

    This function is intentionally a local-file importer. It does not log in,
    automate a browser, or make any network request. It accepts common CSV
    layouts used by Barchart's website, keeps source columns, and adds stable
    date/OHLCV column names for downstream code.
    """

    try:
        read_kwargs: dict[str, Any] = {"encoding": encoding}
        if sep is None:
            # Python's CSV sniffer handles comma, semicolon, and tab exports.
            read_kwargs.update(sep=None, engine="python")
        else:
            read_kwargs["sep"] = sep
        frame = pd.read_csv(source, **read_kwargs)
    except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as exc:
        raise BarchartDecodeError(
            f"Could not read Barchart history CSV from {source!r}."
        ) from exc
    return normalize_barchart_history(frame, symbol=symbol, sort=sort)


def history_quality_report(
    frame: pd.DataFrame,
    *,
    required_columns: tuple[str, ...] = ("date", "close"),
) -> HistoryQualityReport:
    """Summarize completeness and ordering of a normalized history frame.

    The default is the common denominator for Barchart asset classes.
    Commodity OHLCV notebooks can request the stricter set of fields.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    missing_columns = tuple(
        column for column in required_columns if column not in frame.columns
    )
    missing_values = {
        column: int(frame[column].isna().sum())
        for column in required_columns
        if column in frame.columns
    }
    if "date" in frame.columns and not frame.empty:
        dates = pd.to_datetime(frame["date"], errors="coerce")
        start_date = dates.min()
        end_date = dates.max()
        duplicate_dates = int(frame["date"].duplicated().sum())
    else:
        start_date = None
        end_date = None
        duplicate_dates = 0

    return HistoryQualityReport(
        rows=len(frame),
        columns=tuple(str(column) for column in frame.columns),
        start_date=start_date,
        end_date=end_date,
        duplicate_dates=duplicate_dates,
        missing_columns=missing_columns,
        missing_values=missing_values,
    )


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
            result[column] = _coerce_numeric(result[column])

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


def _coerce_numeric(values: pd.Series) -> pd.Series:
    """Convert export values while tolerating thousands separators and blanks."""

    cleaned = values
    if pd.api.types.is_object_dtype(values) or pd.api.types.is_string_dtype(values):
        cleaned = (
            values.astype("string")
            .str.strip()
            .str.replace(",", "", regex=False)
            .replace({"": pd.NA, "-": pd.NA, "--": pd.NA, "N/A": pd.NA})
        )
    return pd.to_numeric(cleaned, errors="coerce")


read_barchart_csv = read_barchart_history_csv


__all__ = [
    "HistoryQualityReport",
    "HistorySource",
    "history_quality_report",
    "normalize_barchart_history",
    "read_barchart_csv",
    "read_barchart_history_csv",
]

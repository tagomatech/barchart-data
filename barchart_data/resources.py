"""Resource namespaces built on the generic Barchart transport."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any, TYPE_CHECKING

import pandas as pd

from .client import OutputFormat, RequestMethod, ResponsePayload
from .history import normalize_barchart_history

if TYPE_CHECKING:
    from .client import BarchartDataClient


class _Resource:
    def __init__(self, client: "BarchartDataClient") -> None:
        self.client = client

    def _request(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        output: OutputFormat,
        *,
        method: RequestMethod = "GET",
    ) -> ResponsePayload:
        return self.client.request(
            endpoint,
            params=params,
            output=output,
            method=method,
        )


class MarketResource(_Resource):
    """Quotes and historical time series."""

    def quote(
        self,
        symbols: str | Iterable[str],
        *,
        fields: str | Iterable[str] | None = None,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        query = _merge_params(params, symbols=_join_values(symbols))
        if fields is not None:
            if "fields" in query:
                raise ValueError("fields was supplied twice")
            query["fields"] = _join_values(fields)
        return self._request("getQuote", query, output)

    def history(
        self,
        symbol: str,
        *,
        frequency: str = "daily",
        start_date: str | None = None,
        end_date: str | None = None,
        max_records: int | None = None,
        interval: int | None = None,
        output: OutputFormat = "df",
        method: RequestMethod = "GET",
        **params: Any,
    ) -> ResponsePayload:
        query: dict[str, Any] = {
            "symbol": symbol,
            "type": frequency,
        }
        _set_if_not_none(
            query,
            "startDate",
            _format_barchart_datetime(start_date, "start_date"),
        )
        _set_if_not_none(
            query,
            "endDate",
            _format_barchart_datetime(end_date, "end_date"),
        )
        _set_if_not_none(query, "maxRecords", max_records)
        _set_if_not_none(query, "interval", interval)
        query = _merge_params(params, **query)
        result = self._request("getHistory", query, output, method=method)
        if output == "df" and isinstance(result, pd.DataFrame):
            return normalize_barchart_history(result, symbol=symbol)
        return result

    def close_price(
        self,
        symbols: str | Iterable[str],
        date: str,
        *,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        query = _merge_params(
            params,
            symbols=_join_values(symbols),
            date=date,
        )
        return self._request("getClosePrice", query, output)


class FundamentalResource(_Resource):
    """Company profiles, statements, ratios, and related data."""

    def balance_sheets(
        self,
        symbols: str | Iterable[str],
        *,
        frequency: str = "Quarter",
        count: int | None = None,
        raw_data: bool = True,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        return self._statement(
            "getBalanceSheets",
            symbols,
            frequency=frequency,
            count=count,
            raw_data=raw_data,
            output=output,
            params=params,
        )

    def income_statements(
        self,
        symbols: str | Iterable[str],
        *,
        frequency: str = "Quarter",
        count: int | None = None,
        raw_data: bool = True,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        return self._statement(
            "getIncomeStatements",
            symbols,
            frequency=frequency,
            count=count,
            raw_data=raw_data,
            output=output,
            params=params,
        )

    def cash_flow(
        self,
        symbols: str | Iterable[str],
        *,
        frequency: str = "Quarter",
        count: int | None = None,
        raw_data: bool = True,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        return self._statement(
            "getCashFlow",
            symbols,
            frequency=frequency,
            count=count,
            raw_data=raw_data,
            output=output,
            params=params,
        )

    def _statement(
        self,
        endpoint: str,
        symbols: str | Iterable[str],
        *,
        frequency: str,
        count: int | None,
        raw_data: bool,
        output: OutputFormat,
        params: Mapping[str, Any],
    ) -> ResponsePayload:
        query = _merge_params(
            params,
            symbols=_join_values(symbols),
            frequency=frequency,
            rawData=int(raw_data),
        )
        _set_if_not_none(query, "count", count)
        return self._request(endpoint, query, output)


class MetadataResource(_Resource):
    """Instrument and futures reference data."""

    def instrument_definition(
        self,
        *,
        symbols: str | Iterable[str] | None = None,
        exchange: str | None = None,
        mic: str | None = None,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        query = dict(params)
        if symbols is not None:
            if "symbols" in query:
                raise ValueError("symbols was supplied twice")
            query["symbols"] = _join_values(symbols)
        _set_if_not_none(query, "exchange", exchange)
        _set_if_not_none(query, "mic", mic)
        return self._request("getInstrumentDefinition", query, output)

    def futures_specifications(
        self,
        *,
        symbols: str | Iterable[str] | None = None,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        query = dict(params)
        if symbols is not None:
            if "symbols" in query:
                raise ValueError("symbols was supplied twice")
            query["symbols"] = _join_values(symbols)
        return self._request("getFuturesSpecifications", query, output)

    def futures_expirations(
        self,
        *,
        symbols: str | Iterable[str] | None = None,
        output: OutputFormat = "df",
        **params: Any,
    ) -> ResponsePayload:
        query = dict(params)
        if symbols is not None:
            if "symbols" in query:
                raise ValueError("symbols was supplied twice")
            query["symbols"] = _join_values(symbols)
        return self._request("getFuturesExpirations", query, output)


def _join_values(values: str | Iterable[str]) -> str:
    if isinstance(values, str):
        normalized = values.strip()
        if not normalized:
            raise ValueError("symbol values must not be empty")
        return normalized
    result = ",".join(str(value).strip() for value in values if str(value).strip())
    if not result:
        raise ValueError("symbol values must not be empty")
    return result


def _set_if_not_none(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _merge_params(params: Mapping[str, Any], **explicit: Any) -> dict[str, Any]:
    conflicts = set(params).intersection(explicit)
    if conflicts:
        names = ", ".join(sorted(conflicts))
        raise ValueError(f"parameters cannot override explicit arguments: {names}")
    return {**explicit, **params}


def _format_barchart_datetime(
    value: str | date | datetime | pd.Timestamp | None,
    name: str,
) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        timestamp = pd.Timestamp(value)
        has_time = True
    elif isinstance(value, (date, pd.Timestamp)):
        timestamp = pd.Timestamp(value)
        has_time = not timestamp == timestamp.normalize()
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{name} must not be empty")
        if text.isdigit() and len(text) in {8, 14}:
            return text
        has_time = any(separator in text for separator in ("T", ":"))
        try:
            timestamp = pd.Timestamp(text)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} is not a valid date or datetime") from exc
    else:
        raise TypeError(f"{name} must be a date, datetime, or string")

    if pd.isna(timestamp):
        raise ValueError(f"{name} is not a valid date or datetime")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.strftime("%Y%m%d%H%M%S" if has_time else "%Y%m%d")

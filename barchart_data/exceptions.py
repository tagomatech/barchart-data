"""Exceptions raised by the barchart-data client."""

from __future__ import annotations


class BarchartDataError(Exception):
    """Base class for package errors."""


class BarchartTransportError(BarchartDataError):
    """Raised when an HTTP request cannot be completed."""


class PublicChartError(BarchartDataError):
    """Raised when the public exact-contract chart feed cannot be read."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class BarchartDecodeError(BarchartDataError):
    """Raised when an API response cannot be decoded."""


class BarchartPublicPageError(BarchartDataError):
    """Raised when a public Barchart quote page cannot be read."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class BarchartInteractiveChartError(BarchartDataError):
    """Raised when a normal interactive-chart browser session cannot provide data."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url

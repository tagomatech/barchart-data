"""Domain exceptions for the Barchart data clients."""

from __future__ import annotations


class BarchartError(RuntimeError):
    """Base class for failures raised by the Barchart clients."""


class FuturesDataError(BarchartError):
    """A futures contract history could not be fetched or normalized."""

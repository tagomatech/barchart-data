"""Credential-free Barchart market-data and analysis utilities.

The public client reads data exposed by Barchart quote pages without an API
key or login. Historical CSV files downloaded through Barchart can be parsed
locally with the history helpers.
"""

from .catalog import (
    AGRICULTURAL_CATALOG,
    CommodityRoot,
    agricultural_catalog,
    catalog_frame,
)
from .exceptions import (
    BarchartDataError,
    BarchartDecodeError,
    BarchartPublicPageError,
    BarchartTransportError,
)
from .history import (
    HistoryQualityReport,
    history_quality_report,
    normalize_barchart_history,
    read_barchart_csv,
    read_barchart_history_csv,
)
from .legacy import PublicWebHistoryClient
from .normalization import rebase_frame, rebase_many, rebase_to_base
from .public import BarchartPublicClient, PublicBarchartClient, PublicWebClient
from .website import (
    BarchartWebsiteWorkflow,
    ImportedHistory,
    historical_download_url,
)

__all__ = [
    "BarchartDataError",
    "BarchartDecodeError",
    "BarchartPublicClient",
    "BarchartPublicPageError",
    "BarchartTransportError",
    "AGRICULTURAL_CATALOG",
    "CommodityRoot",
    "HistoryQualityReport",
    "ImportedHistory",
    "BarchartWebsiteWorkflow",
    "history_quality_report",
    "historical_download_url",
    "normalize_barchart_history",
    "PublicWebHistoryClient",
    "PublicBarchartClient",
    "PublicWebClient",
    "agricultural_catalog",
    "catalog_frame",
    "rebase_frame",
    "rebase_many",
    "rebase_to_base",
    "read_barchart_csv",
    "read_barchart_history_csv",
]

__version__ = "0.7.0"

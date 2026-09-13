"""Credential-free Barchart market-data and analysis utilities.

The public client reads data exposed by Barchart quote pages without an API
key or login. Historical CSV files downloaded through Barchart can be parsed
locally with the history helpers.
"""

from .browser import (
    BarchartInteractiveChartWorkflow,
    CapturedChartHistory,
    interactive_chart_url,
)
from .catalog import (
    AGRICULTURAL_CATALOG,
    CommodityRoot,
    agricultural_catalog,
    catalog_frame,
)
from .exceptions import (
    BarchartDataError,
    BarchartDecodeError,
    BarchartInteractiveChartError,
    BarchartPublicPageError,
    BarchartTransportError,
)
from .history import (
    HistoryQualityReport,
    history_quality_report,
    normalize_barchart_history,
    read_barchart_csv,
    read_barchart_history_bytes,
    read_barchart_history_csv,
    read_barchart_history_text,
)
from .normalization import rebase_frame, rebase_many, rebase_to_base
from .public import BarchartPublicClient, PublicBarchartClient, PublicWebClient
from .website import (
    BarchartWebsiteWorkflow,
    ImportedHistory,
    historical_download_url,
)

__all__ = [
    "AGRICULTURAL_CATALOG",
    "BarchartDataError",
    "BarchartDecodeError",
    "BarchartInteractiveChartError",
    "BarchartInteractiveChartWorkflow",
    "BarchartPublicClient",
    "BarchartPublicPageError",
    "BarchartTransportError",
    "BarchartWebsiteWorkflow",
    "CapturedChartHistory",
    "CommodityRoot",
    "HistoryQualityReport",
    "ImportedHistory",
    "PublicBarchartClient",
    "PublicWebClient",
    "agricultural_catalog",
    "catalog_frame",
    "historical_download_url",
    "history_quality_report",
    "interactive_chart_url",
    "normalize_barchart_history",
    "read_barchart_csv",
    "read_barchart_history_bytes",
    "read_barchart_history_csv",
    "read_barchart_history_text",
    "rebase_frame",
    "rebase_many",
    "rebase_to_base",
]

__version__ = "0.9.1"

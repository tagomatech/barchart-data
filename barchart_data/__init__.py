"""Modern Barchart market-data client.

The authenticated client targets Barchart OnDemand endpoint families. The
public client reads public quote pages and provides best-effort anonymous
history access; it does not represent the official API.
"""

from .client import BarchartDataClient, OnDemandClient
from .catalog import (
    AGRICULTURAL_CATALOG,
    CommodityRoot,
    agricultural_catalog,
    catalog_frame,
)
from .exceptions import (
    BarchartAPIError,
    BarchartAuthenticationError,
    BarchartDataError,
    BarchartDecodeError,
    BarchartPublicPageError,
    BarchartTransportError,
)
from .history import (
    normalize_barchart_history,
    read_barchart_csv,
    read_barchart_history_csv,
)
from .legacy import PublicWebHistoryClient
from .normalization import rebase_frame, rebase_many, rebase_to_base
from .public import BarchartPublicClient, PublicBarchartClient, PublicWebClient
from .resources import FundamentalResource, MarketResource, MetadataResource

__all__ = [
    "BarchartAPIError",
    "BarchartAuthenticationError",
    "BarchartDataClient",
    "BarchartDataError",
    "BarchartDecodeError",
    "BarchartPublicClient",
    "BarchartPublicPageError",
    "BarchartTransportError",
    "AGRICULTURAL_CATALOG",
    "CommodityRoot",
    "FundamentalResource",
    "MarketResource",
    "MetadataResource",
    "normalize_barchart_history",
    "OnDemandClient",
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

__version__ = "0.5.0"

# barchart-data

An installable Python toolkit for Barchart market data, with a no-login public
page adapter, an official authenticated OnDemand client, and a parser for
historical CSV files downloaded through the Barchart website.

The package is designed for commodity research first, while keeping the
resource layout extensible to equities, funds, currencies, and fundamentals.

## Install from GitHub

~~~powershell
python -m pip install "git+https://github.com/tagomatech/barchart-data.git"
~~~

For the notebook and Screamer indicators:

~~~powershell
python -m pip install "barchart-data[demo] @ git+https://github.com/tagomatech/barchart-data.git"
~~~

For local development:

~~~powershell
python -m pip install -e ".[dev,demo]"
~~~

The repository is also configured for tokenless PyPI publication through
GitHub Actions. The GitHub install above works immediately. To enable the
standard command python -m pip install barchart-data, create a PyPI trusted
publisher for owner tagomatech, repository barchart-data, workflow
.github/workflows/publish.yml, and environment pypi. Then publish a
version tag:

~~~powershell
git tag v0.5.0
git push origin v0.5.0
~~~

## Access model

The public client reads quote and instrument JSON embedded in Barchart
overview pages. Quotes and profiles do not require a Barchart account, API
key, or login.

~~~python
from barchart_data import BarchartPublicPageError, PublicBarchartClient

client = PublicBarchartClient()
corn_quote = client.quote("ZCU26")
corn_profile = client.profile("ZCU26")
try:
    corn_history = client.history("ZCU26", start_date="2026-06-01")
except BarchartPublicPageError:
    # Anonymous historical access is best-effort and may be denied.
    corn_history = None
~~~

The public adapter is reliable for quote/profile fields embedded in public
overview pages. Its historical method is deliberately best-effort because
Barchart can deny anonymous automated history requests with HTTP 401/403.
The library does not bypass those controls, automate sign-in, or rotate IPs.
For historical data, use the official OnDemand client or download a CSV from
the Barchart historical-data page using an account and plan that permits it.
The available lookback window and download quota depend on the Barchart
product and can change; see the [official download help](https://help.barchart.com/support/solutions/articles/242748-how-can-i-download-historical-data-).

The public client spaces uncached requests by one second, caches overview pages
for five minutes, and honors Barchart's Retry-After response when retrying
transient errors. Increase min_request_interval or use a longer page_cache_ttl
for a longer-lived process. Keep the defaults, or use a longer interval, for
regular research jobs.

## Official historical API

The authenticated client is available when official API coverage is required.
Set BARCHART_API_KEY or pass an explicit key:

~~~python
from barchart_data import BarchartDataClient

client = BarchartDataClient()
corn = client.market.history(
    "ZC*1",
    frequency="dailyNearest",
    start_date="2024-01-01",
    end_date="2026-01-01",
    method="POST",
)
quotes = client.market.quote(["ZC*1", "AAPL"])
quarterly_balance_sheet = client.fundamentals.balance_sheets(
    "AAPL",
    frequency="Quarter",
)
~~~

The OnDemand client is optional; importing and using the public client does
not read or require BARCHART_API_KEY.

The official getHistory API accepts futures, equities, indexes, and other
supported instruments. Dates are normalized to Barchart's documented
YYYYMMDD or YYYYMMDDHHMMSS format, and DataFrame results include a stable
date column even when the API returns tradingDay.

## Website CSV import

The website-supported workflow is manual and auditable:

1. Open the instrument's Barchart historical-data page.
2. Select the permitted frequency and date range, then use Barchart's
   Download control.
3. Read the downloaded file locally:

~~~python
from barchart_data import read_barchart_history_csv

history = read_barchart_history_csv(
    r"downloads\ZCU26-history.csv",
    symbol="ZCU26",
)
~~~

The importer accepts common Barchart website and API column names, retains
source columns, adds canonical date/OHLCV fields, and performs no network or
login operation.

## Commodity utilities

The compatibility Barchart package contains:

- a typed best-effort public quote/history adapter for futures;
- a supported local importer for Barchart historical CSV downloads;
- contract-aware continuous-series construction with auditable roll segments;
- a catalog of grains, oilseeds, livestock, ICE Canada, Euronext Matif, and
  Barchart's palm-oil-related roots;
- rebasing and comparison helpers;
- a CME/CBOT September 2026 Corn notebook using real OHLCV data and Screamer
  indicators.

Open notebooks/commodities/corn_futures_demo.ipynb in Jupyter or VS Code after installing
the demo extra.

The broader agriculture portfolio example is in
notebooks/commodities/agriculture_portfolio_demo.ipynb. It covers current
first-nearby contracts across grains, oilseeds, livestock, vegetable oils,
ICE Canada, and Euronext Matif, plus rebased market-group comparisons.

The equity research example is in
notebooks/equities/equity_research_demo.ipynb. It covers public AAPL page
fields, official historical API or local CSV history, the Barchart S&P 500
index, dividend-adjustment effects, Screamer indicators, risk metrics, and a
small example portfolio.

## Tests

~~~powershell
python -m unittest discover -s Barchart/tests -v
python -m unittest discover -s tests -v
~~~

## Contributions

Contributions are welcome. Please open an issue or pull request for bug fixes,
new data resources, additional asset classes, notebook ideas, and
documentation improvements. Run both test commands above before submitting a
change, and do not commit credentials or downloaded market data.

## Data rights

This project is a client and transformation toolkit, not a data
redistribution service. Use Barchart data only in accordance with the terms
and permissions that apply to your account and use case.

## License

MIT

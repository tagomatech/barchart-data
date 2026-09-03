# barchart-data

An installable Python toolkit for Barchart market data that requires no
Barchart API key or login. It reads public quote pages and parses historical
CSV files downloaded through the Barchart website.

The package is designed for commodity research first, while keeping its public
asset-class handling extensible to equities, funds, currencies, and other
instruments.

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
git tag v0.8.0
git push origin v0.8.0
~~~

## Access model

The public client reads quote and instrument JSON embedded in Barchart
overview pages. Quotes and profiles do not require a Barchart account, API
key, or login.

~~~python
from barchart_data import PublicBarchartClient

client = PublicBarchartClient()
corn_quote = client.quote("ZCU26")
corn_profile = client.profile("ZCU26")
~~~

The public adapter is limited to quote/profile fields embedded in public
overview pages. Historical data is deliberately not fetched through an
anonymous automated endpoint because Barchart can deny that route with HTTP
401/403. For historical data, download a CSV from the Barchart
historical-data page using an account and plan that permits it.
The available lookback window and download quota depend on the Barchart
product and can change; see the [official download help](https://help.barchart.com/support/solutions/articles/242748-how-can-i-download-historical-data-).

The public client spaces uncached requests by one second, caches overview pages
for five minutes, and honors Barchart's Retry-After response when retrying
transient errors. Increase min_request_interval or use a longer page_cache_ttl
for a longer-lived process. Keep the defaults, or use a longer interval, for
regular research jobs.

## Website CSV workflow

The website-supported workflow is manual and auditable:

1. Open the instrument's Barchart historical-data page.
2. Select the permitted frequency and date range, then use Barchart's
   Download control.
3. Read the downloaded file locally:

~~~python
from barchart_data import BarchartWebsiteWorkflow

workflow = BarchartWebsiteWorkflow(download_dir="downloads")
url = workflow.open_historical_download_page("ZCU26")
print(f"Open this page and press Download: {url}")

# Or omit the browser handoff and open the URL yourself.
imported = workflow.import_latest_csv(symbol="ZCU26")
history = imported.frame
print(imported.path)
print(imported.quality.as_dict())
~~~

The workflow opens only the official page in your browser. You complete any
account step and press Barchart's Download control yourself. It can then find
the newest matching local CSV, wait for a browser download to finish, preserve
source columns, add canonical date/OHLCV fields, and report duplicates and
missing values. It performs no login, private-endpoint request, or network
operation during import. The lower-level read_barchart_history_csv function
remains available when an exact path is preferred.

## Commodity utilities

The compatibility Barchart package contains:

- a typed public quote/profile adapter for overview pages;
- a supported local importer for Barchart historical CSV downloads;
- contract-aware continuous-series construction with auditable roll segments;
- a catalog of grains, oilseeds, livestock, ICE Canada, Euronext Matif, and
  Barchart's palm-oil-related roots;
- rebasing and comparison helpers;
- a CME/CBOT September 2026 Corn notebook using real OHLCV data and Screamer
  indicators.

Open notebooks/commodities/corn_futures_demo.ipynb in Jupyter or VS Code after installing
the demo extra.

The supported website workflow is demonstrated end to end in
notebooks/commodities/barchart_csv_workflow_demo.ipynb. It uses the actual
ZCU26 contract, shows the source-file audit, and renders candlesticks,
volume, RSI, Bollinger Bands, and ATR after a local CSV download.

The broader agriculture portfolio example is in
notebooks/commodities/agriculture_portfolio_demo.ipynb. It covers current
first-nearby contracts across grains, oilseeds, livestock, vegetable oils,
ICE Canada, and Euronext Matif, plus rebased market-group comparisons.

The equity research example is in
notebooks/equities/equity_research_demo.ipynb. It covers public AAPL page
fields, local CSV history, the Barchart S&P 500 index, dividend-adjustment
effects, Screamer indicators, risk metrics, and a small example portfolio.

## Tests

~~~powershell
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

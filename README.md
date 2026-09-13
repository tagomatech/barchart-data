# barchart-data

An installable Python toolkit for Barchart market data. It reads public quote
pages, can capture history naturally loaded by the official interactive chart
in a normal browser session, and parses historical CSV files downloaded through
the Barchart website. The package never automates sign-in or stores credentials.

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

For the optional browser-assisted chart capture:

~~~powershell
python -m pip install -e ".[browser]"
playwright install chromium
~~~

The repository is also configured for tokenless PyPI publication through
GitHub Actions. The GitHub install above works immediately. To enable the
standard command python -m pip install barchart-data, create a PyPI trusted
publisher for owner tagomatech, repository barchart-data, workflow
.github/workflows/publish.yml, and environment pypi. Then publish a
version tag:

~~~powershell
git tag v0.9.0
git push origin v0.9.0
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
overview pages. Historical data is not fetched through a separately scripted
anonymous endpoint because Barchart can deny that route with HTTP 401/403.
The interactive-chart workflow below uses the page itself when a normal browser
session receives chart data. Otherwise, download a CSV from the Barchart
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

## Interactive chart workflow

The interactive page is the authoritative place where Barchart applies its
chart menus, frequency, range, and entitlement rules. The optional workflow
opens that page in a visible Playwright browser and listens for a successful
same-origin history response that the page naturally makes:

~~~python
from barchart_data import BarchartInteractiveChartWorkflow

chart = BarchartInteractiveChartWorkflow(
    browser_executable=None,  # or the path to an installed Chrome/Edge
    headless=False,
    timeout_seconds=120,
)
captured = chart.capture_history("ZCU26")
history = captured.frame
print(captured.response_url)
print(captured.quality.as_dict())
~~~

If a fresh Playwright browser receives CloudFront 403 but the chart works in a
browser you started yourself, launch that browser with a local DevTools port
and opt in explicitly:

~~~powershell
& "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP/barchart-data-browser"
~~~

Open the chart in that window, then capture through its normal visible session:

~~~python
chart = BarchartInteractiveChartWorkflow(
    cdp_endpoint="http://127.0.0.1:9222",
    headless=False,
)
captured = chart.capture_history("ZCU26")
~~~

This CDP mode attaches only to the browser endpoint you explicitly provide. It
does not export cookies, passwords, or tokens, and it does not solve a
Barchart entitlement or CloudFront denial.

For the most conservative path, use the browser you already use manually and
let the package watch its download folder:

~~~python
chart = BarchartInteractiveChartWorkflow(download_dir="downloads")
imported = chart.download_interactive_csv("ZCU26")
history = imported.frame
~~~

This opens the official interactive chart in the default browser, waits for
you to choose the chart settings and press Barchart's own Download control,
then imports and quality-checks the completed local CSV. Set download_dir to
the browser's actual download directory.

While the browser is open, use Barchart's own controls if you need a different
range or interval. The package accepts only a readable successful response
from the official page and does not call an undocumented endpoint, replay
tokens, rotate proxies, automate login, or bypass CloudFront. If Barchart
returns a verification or 401/403 response, the method raises
`BarchartInteractiveChartError`; use the official CSV workflow instead.

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

# barchart-data

An installable Python toolkit for Barchart market data, with a no-login public
web adapter and an optional authenticated OnDemand client.

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
git tag v0.4.1
git push origin v0.4.1
~~~

## No-login public data

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
    # Barchart may restrict anonymous history even when the quote page works.
    corn_history = None
~~~

The same page adapter can read other public overview categories by passing
the Barchart page category, for example asset_class="stocks". Its historical
method uses the current browser-facing JSON route and is best-effort: Barchart
may limit anonymous history to a recent window or return HTTP 401/403. In that
case use the official OnDemand client with an API key. The adapter preserves
the field names returned by Barchart instead of silently manufacturing values.

## Optional OnDemand client

The authenticated client is available when official API coverage is required.
Set BARCHART_API_KEY or pass an explicit key:

~~~python
from barchart_data import BarchartDataClient

client = BarchartDataClient()
corn = client.market.history("ZC*1", frequency="daily")
quotes = client.market.quote(["ZC*1", "AAPL"])
quarterly_balance_sheet = client.fundamentals.balance_sheets(
    "AAPL",
    frequency="Quarter",
)
~~~

The OnDemand client is optional; importing and using the public client does
not read or require BARCHART_API_KEY.

## Commodity utilities

The compatibility Barchart package contains:

- a typed best-effort public historical downloader for futures;
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
notebooks/equities/equity_research_demo.ipynb. It covers a no-login AAPL
workflow, the Barchart S&P 500 index, dividend-adjustment effects, Screamer
indicators, risk metrics, and a small example portfolio.

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

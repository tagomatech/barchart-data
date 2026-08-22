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
git tag v0.4.0
git push origin v0.4.0
~~~

## No-login public data

The public client reads quote and instrument JSON embedded in Barchart
overview pages. It does not require a Barchart account, API key, or login.

~~~python
from barchart_data import PublicBarchartClient

client = PublicBarchartClient()
corn_quote = client.quote("ZCU26")
corn_profile = client.profile("ZCU26")
corn_history = client.history(
    "ZCU26",
    start_date="2025-01-01",
    end_date="2026-08-21",
)
~~~

The same page adapter can read other public overview categories by passing
the Barchart page category, for example asset_class="stocks". Public page
data may be delayed or limited, and the page format can change. The adapter
preserves the field names returned by Barchart instead of silently
manufacturing values.

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

- a typed public historical downloader for futures;
- contract-aware continuous-series construction with auditable roll segments;
- a catalog of grains, oilseeds, livestock, ICE Canada, Euronext Matif, and
  Barchart's palm-oil-related roots;
- rebasing and comparison helpers;
- a CME/CBOT September 2026 Corn notebook using real OHLCV data and Screamer
  indicators.

Open Barchart/corn_futures_demo.ipynb in Jupyter or VS Code after installing
the demo extra.

## Tests

~~~powershell
python -m unittest discover -s Barchart/tests -v
python -m unittest discover -s tests -v
~~~

## Data rights

This project is a client and transformation toolkit, not a data
redistribution service. Use Barchart data only in accordance with the terms
and permissions that apply to your account and use case.

## License

MIT

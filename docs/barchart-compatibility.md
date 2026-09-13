# Barchart compatibility

The installable package lives at the repository root. The Barchart directory
is retained for compatibility with the original futures-builder code.

~~~powershell
py -3.13 -m pip install --upgrade --force-reinstall "barchart-data[demo,browser] @ git+https://github.com/tagomatech/barchart-data.git@main"
py -3.13 -m playwright install chromium
~~~

## Historical ingestion

The package has one supported historical acquisition path. It opens the
official interactive chart in a headless browser session, observes a
successful same-origin history response produced by that page, normalizes it,
and returns it in memory:

~~~python
from barchart_data import download_history

imported = download_history("ZCU26")
history = imported.frame
print(imported.quality.as_dict())
print(imported.source)
assert imported.path is None
~~~

The method does not display a browser window, press the website Download
control, create a download directory, or retain a browser artifact. It uses
the chart's default range and interval. Browser configuration is limited to
the optional executable path, headless setting, and timeout:

~~~python
imported = download_history(
    "ZCU26",
    browser_executable=None,
    headless=True,
    timeout_seconds=120,
)
~~~

This workflow uses only requests naturally made by the official page. It does
not automate sign-in, inspect or export credentials, replay tokens, rotate
proxies, or call an undocumented standalone historical endpoint. A
CloudFront, verification, entitlement, or account restriction is reported as
BarchartInteractiveChartError and is not bypassed.

The lower-level history readers remain available for applications that
already possess permitted data in memory. They are parsers, not alternate
downloaders.

## Public quote data

Public quote and profile fields can be read from overview pages:

~~~python
from barchart_data import PublicBarchartClient

client = PublicBarchartClient()
quote = client.quote("ZCU26")
profile = client.profile("ZCU26")
~~~

The public client spaces uncached requests by one second and caches overview
pages for five minutes. Reuse one client instance and increase the interval
for larger jobs.

## Compatibility builder

The original deterministic futures utilities remain available:

~~~python
from Barchart import ContinuousFuturesBuilder

builder = ContinuousFuturesBuilder(verbose=False)
series, rolls = builder.build(
    {
        "ZCZ26": corn_history,
        "ZCH27": next_corn_history,
    },
    line_number=1,
    return_segments=True,
)
~~~

The output keeps source_symbol on every row and returns roll ranges in rolls,
so downstream analytics can audit which contract supplied each value.

## Catalog and analysis

The catalog records roots, exchanges, units, contract months, and notes for
CBOT/CME grains and oilseeds, ICE Canada canola, Euronext Matif milling wheat
and rapeseed, CME livestock, and vegetable-oil-related contracts.

CommodityRoot.barchart_symbol() and barchart_nearby_symbol() create Barchart
symbols for current nearby research. The normalization helpers rebase price
paths for comparison; they do not create synthetic continuous prices.

The notebooks include:

- notebooks/commodities/corn_futures_demo.ipynb for the fixed ZCU26 contract;
- notebooks/commodities/agriculture_portfolio_demo.ipynb for agriculture
  comparisons;
- notebooks/equities/equity_research_demo.ipynb for an equity example.

## Data rights

This project is a client and transformation toolkit, not a data
redistribution service. Use Barchart data only in accordance with the terms
and permissions that apply to the account and use case.

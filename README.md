# barchart-data

An installable Python client for Barchart public market data. The project is
commodity-focused and is designed to grow to other asset classes and data
families without storing credentials or downloaded market data.

## Install

Use the repository version directly. This is the one supported installation
for the browser history client:

~~~powershell
py -3.13 -m pip install --upgrade --force-reinstall "barchart-data[demo,browser] @ git+https://github.com/tagomatech/barchart-data.git@main"
py -3.13 -m playwright install chromium
~~~

Confirm that Python is importing the GitHub checkout:

~~~powershell
py -3.13 -c "import barchart_data; print(barchart_data.__version__); print(barchart_data.__file__)"
~~~

## Historical data

There is one historical acquisition method. The package opens the official
Barchart interactive chart in a headless browser session and observes the
history response that the page naturally requests. No browser window is
displayed. The response is normalized in memory and the browser is closed
automatically.

~~~python
from barchart_data import download_history

result = download_history("ZCU26")
history = result.frame

print(history.tail())
print(result.source)
assert result.path is None
~~~

No Download button needs to be pressed. No file is created by default. The
chart's own default range and interval are used, and the returned source URL
provides provenance for the captured response.

Progress is printed to the terminal in real time. Maximum verbosity is the
default:

~~~python
result = download_history("ZCU26", verbosity=3)
~~~

Use verbosity 2 for progress only, 1 for errors only, or 0 for no output.
At maximum verbosity, the package reports browser startup, navigation,
candidate responses, parsing, cleanup, and a heartbeat while it is waiting.

This is browser automation of the official page, not an attempt to bypass
Barchart controls. The package does not automate sign-in, replay tokens,
rotate proxies, or call a separate anonymous historical endpoint. If
Barchart/CloudFront denies the browser session, the function raises
BarchartInteractiveChartError; that restriction cannot be bypassed by this
package.

The same function accepts another public Barchart asset class:

~~~python
result = download_history("AAPL", asset_class="stocks")
~~~

## Public quote data

Public quote and profile fields embedded in overview pages are available
without a login:

~~~python
from barchart_data import PublicBarchartClient

client = PublicBarchartClient()
quote = client.quote("ZCU26")
profile = client.profile("ZCU26")
~~~

Requests are deliberately paced and overview pages are cached briefly. Reuse
one client instance for a research job and keep the default request interval
or increase it for larger jobs.

## Analysis and demos

The package includes:

- OHLCV normalization and quality reports;
- a catalog of grains, oilseeds, livestock, vegetable oils, ICE Canada, and
  Euronext Matif roots;
- contract-aware nearby and continuous-futures utilities;
- rebasing and comparison helpers;
- Screamer indicators for streaming-style analysis.

The main demonstration is
notebooks/commodities/corn_futures_demo.ipynb. It uses the real CME/CBOT
September 2026 Corn contract, ZCU26, and renders candlesticks, volume,
Bollinger Bands, ATR, RSI, and a rolling volume mean.

The agriculture comparison is in
notebooks/commodities/agriculture_portfolio_demo.ipynb. The equity example is
in notebooks/equities/equity_research_demo.ipynb. These notebooks are
analysis demonstrations; the single historical downloader above is the
source-ingestion path.

The legacy Barchart package remains under Barchart for compatibility with the
original futures-builder imports. New code should import from barchart_data.

## Tests

~~~powershell
py -3.13 -m unittest discover -s tests -v
~~~

## Contributions

Contributions are welcome. Issues and pull requests are useful for bug fixes,
new asset classes, notebook ideas, documentation, and compatibility reports.
Please do not commit credentials or downloaded market data.

## Data rights

This project is a client and transformation toolkit, not a data
redistribution service. Use Barchart data only in accordance with the terms
and permissions that apply to your account and use case.

## License

MIT

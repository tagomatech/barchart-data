# %% [markdown]
# # Equity research without an API key: Apple, S&P 500, and a portfolio
#
# This notebook demonstrates the equity side of barchart-data using public
# Barchart pages and the public historical endpoint. It uses:
#
# - Apple (AAPL) for a company quote, profile, OHLCV chart, and indicators;
# - the Barchart S&P 500 index symbol ($SPX) as a benchmark;
# - an equal-weighted example portfolio of large, liquid equities;
# - Barchart's dividend-adjusted versus unadjusted history option.
#
# No Barchart account, API key, or login is used. Public data can be delayed,
# limited, or changed by the upstream site.

# %%
from pathlib import Path
import sys

candidate_roots = [Path.cwd(), *Path.cwd().parents]
repo_root = next(
    (
        candidate
        for candidate in candidate_roots
        if (candidate / "barchart_data").is_dir()
        and (candidate / "Barchart").is_dir()
    ),
    None,
)
if repo_root is None:
    raise RuntimeError(
        "Run this demo from a checkout containing barchart_data and Barchart."
    )
sys.path.insert(0, str(repo_root))

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import screamer
from IPython.display import display
from matplotlib.patches import Rectangle
from screamer import ATR, BollingerBands, RollingMean, RollingRSI

from barchart_data import PublicBarchartClient
from Barchart import BarchartHistoricalData

EQUITY = "AAPL"
BENCHMARK = "$SPX"
START_DATE = "2021-01-01"
END_DATE = None
PLOT_SESSIONS = 220
PORTFOLIO_WEIGHTS = {
    "AAPL": 0.30,
    "MSFT": 0.25,
    "NVDA": 0.20,
    "JPM": 0.15,
    "XOM": 0.10,
}

public_client = PublicBarchartClient()
history_client = BarchartHistoricalData()

# %% [markdown]
# ## 1. Quote, company profile, and main metrics
#
# The public page adapter returns the fields that Barchart currently embeds in
# the quote page. For example, the latest page may expose previousClose rather
# than an intraday last price when the market is closed. The notebook keeps
# that distinction visible.

# %%
quote = public_client.quote(EQUITY, asset_class="stocks")
profile = public_client.profile(EQUITY, asset_class="stocks")

quote_columns = [
    "symbol",
    "asset_class",
    "previousClose",
    "previousOpen",
    "previousHigh",
    "previousLow",
    "weeklyPreviousClose",
    "monthlyPreviousClose",
    "tradeTime",
]
quote_view = quote[[column for column in quote_columns if column in quote.columns]]
display(quote_view.T.rename(columns={0: "value"}))
display(profile.T.rename(columns={0: "value"}))

print("Data route: Barchart public pages and public historical endpoint")
print("Credentials used: none")

# %% [markdown]
# ## 2. Historical price data and Screamer indicators
#
# Barchart returns stock history as symbol, date, open, high, low, close, and
# volume. The notebook uses the adjusted series for the research chart, then
# compares it with the unadjusted series in the next section.

# %%
def fetch_history(symbol, *, dividends):
    frame = history_client.history(
        symbol,
        start_date=START_DATE,
        end_date=END_DATE,
        out="df",
        dividends=dividends,
    )
    if frame.empty:
        raise ValueError(f"No historical rows returned for {symbol}.")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date")
    frame = frame.drop_duplicates(subset=["date"], keep="last")
    for column in ("open", "high", "low", "close", "volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["close"]).reset_index(drop=True)
    if START_DATE is not None:
        frame = frame.loc[frame["date"] >= pd.Timestamp(START_DATE)]
    if END_DATE is not None:
        frame = frame.loc[frame["date"] <= pd.Timestamp(END_DATE)]
    return frame.reset_index(drop=True)


apple_raw = fetch_history(EQUITY, dividends="false")
apple_adjusted = fetch_history(EQUITY, dividends="true")
benchmark_adjusted = fetch_history(BENCHMARK, dividends="true")

apple_adjusted[["bb_lower", "bb_mid", "bb_upper"]] = BollingerBands(
    window_size=20,
    num_std=2.0,
)(
    apple_adjusted["close"].to_numpy(dtype=float)
)
apple_adjusted["atr14"] = ATR(window_size=14)(
    apple_adjusted["high"].to_numpy(dtype=float),
    apple_adjusted["low"].to_numpy(dtype=float),
    apple_adjusted["close"].to_numpy(dtype=float),
)
apple_adjusted["rsi14"] = RollingRSI(window_size=14)(
    apple_adjusted["close"].to_numpy(dtype=float)
)
apple_adjusted["volume_mean20"] = RollingMean(window_size=20)(
    apple_adjusted["volume"].to_numpy(dtype=float)
)
apple_adjusted["daily_return_pct"] = apple_adjusted["close"].pct_change() * 100

display(
    apple_adjusted[
        ["date", "open", "high", "low", "close", "volume", "daily_return_pct"]
    ].tail(10)
)

# %% [markdown]
# ## 3. Candles, volatility, momentum, and volume
#
# The indicators are calculated over the full downloaded history before the
# last sessions are plotted, so their warm-up state is not restarted at the
# chart boundary.

# %%
navy = "#13233A"
gold = "#F4B942"
green = "#69B578"
red = "#D95D5D"
sky = "#73B7D8"
muted = "#AEB9C6"

plot_data = apple_adjusted.tail(PLOT_SESSIONS).copy()
x_values = mdates.date2num(plot_data["date"].to_numpy(dtype="datetime64[ns]"))
x_step = np.nanmedian(np.diff(x_values))
candle_width = max(float(x_step * 0.65), 0.25)

plt.style.use("dark_background")
fig, axes = plt.subplots(
    3,
    1,
    figsize=(15, 10),
    sharex=True,
    gridspec_kw={"height_ratios": [3.5, 1.1, 1.1]},
)
fig.patch.set_facecolor(navy)
for axis in axes:
    axis.set_facecolor(navy)
    axis.grid(True, color="#3A4A60", alpha=0.35)
    axis.tick_params(colors=muted)
    for spine in axis.spines.values():
        spine.set_color("#3A4A60")

for x_value, (_, row) in zip(x_values, plot_data.iterrows()):
    color = green if row["close"] >= row["open"] else red
    axes[0].vlines(x_value, row["low"], row["high"], color=color, linewidth=0.9)
    body_bottom = min(row["open"], row["close"])
    body_height = max(abs(row["close"] - row["open"]), 0.01)
    axes[0].add_patch(
        Rectangle(
            (x_value - candle_width / 2, body_bottom),
            candle_width,
            body_height,
            facecolor=color,
            edgecolor=color,
            linewidth=0.8,
        )
    )

axes[0].plot(
    x_values,
    plot_data["bb_upper"],
    color=sky,
    linewidth=1.0,
    label="Bollinger upper",
)
axes[0].plot(
    x_values,
    plot_data["bb_mid"],
    color=gold,
    linewidth=1.0,
    label="Bollinger mid",
)
axes[0].plot(
    x_values,
    plot_data["bb_lower"],
    color=sky,
    linewidth=1.0,
    label="Bollinger lower",
)
axes[0].set_title(
    "Barchart public data | Apple (AAPL) | dividend-adjusted candles",
    loc="left",
    color="white",
    fontsize=16,
    pad=14,
)
axes[0].set_ylabel("Price", color=muted)
axes[0].legend(frameon=False, labelcolor="white", loc="upper left", ncol=3)

bar_colors = np.where(
    plot_data["close"].to_numpy() >= plot_data["open"].to_numpy(),
    green,
    red,
)
axes[1].bar(
    x_values,
    plot_data["volume"],
    width=candle_width,
    color=bar_colors,
    alpha=0.8,
)
axes[1].plot(
    x_values,
    plot_data["volume_mean20"],
    color=gold,
    linewidth=1.2,
    label="20-session volume mean",
)
axes[1].set_ylabel("Volume", color=muted)
axes[1].legend(frameon=False, labelcolor="white", loc="upper left")

axes[2].axhspan(30, 70, color=sky, alpha=0.08)
axes[2].axhline(70, color=muted, linewidth=0.8, alpha=0.7)
axes[2].axhline(30, color=muted, linewidth=0.8, alpha=0.7)
axes[2].plot(x_values, plot_data["rsi14"], color=sky, linewidth=1.5, label="RSI(14)")
axes[2].set_ylim(0, 100)
axes[2].set_ylabel("RSI", color=muted)
axes[2].set_xlabel("Trade date", color=muted)
axes[2].legend(frameon=False, labelcolor="white", loc="upper left")

axes[2].xaxis_date()
axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
fig.text(
    0.01,
    0.01,
    "Source: Barchart public historical endpoint | Screamer indicators",
    color=muted,
    fontsize=9,
)
fig.tight_layout(rect=[0, 0.03, 1, 1])
plt.show()

# %% [markdown]
# ## 4. Dividend-adjusted versus unadjusted prices
#
# The no-login Barchart historical route exposes a dividends option that
# changes the historical price series for dividend and split adjustment. It
# does not return a cash dividend event ledger in this public response.
# Therefore this section shows the observable adjustment effect and labels it
# as such rather than presenting it as a cash dividend amount.

# %%
dividend_effect = apple_raw[["date", "close"]].rename(
    columns={"close": "close_unadjusted"}
).merge(
    apple_adjusted[["date", "close"]].rename(columns={"close": "close_adjusted"}),
    on="date",
    how="inner",
)
dividend_effect["adjustment_pct"] = (
    dividend_effect["close_adjusted"] / dividend_effect["close_unadjusted"] - 1
) * 100

display(dividend_effect.tail(12))

fig, axis = plt.subplots(figsize=(15, 4.5))
axis.set_facecolor(navy)
axis.plot(
    dividend_effect["date"],
    dividend_effect["adjustment_pct"],
    color=gold,
    linewidth=1.5,
)
axis.axhline(0, color=muted, linewidth=0.8)
axis.set_title(
    "AAPL historical adjustment effect | dividends=true versus dividends=false",
    loc="left",
    color="white",
)
axis.set_ylabel("Adjustment (%)", color=muted)
axis.set_xlabel("Trade date", color=muted)
axis.grid(True, color="#3A4A60", alpha=0.35)
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 5. Company, benchmark, and risk metrics
#
# Returns below use the adjusted close series. Volatility is annualized from
# daily returns, and maximum drawdown is calculated from the running high.

# %%
def series_metrics(label, symbol, frame):
    close = frame.set_index("date")["close"].dropna().sort_index()
    returns = close.pct_change().dropna()
    running_high = close.cummax()
    drawdown = close / running_high - 1

    def trailing_return(sessions):
        if len(close) <= sessions:
            return np.nan
        return close.iloc[-1] / close.iloc[-sessions - 1] - 1

    year_start = close.loc[close.index >= pd.Timestamp(f"{close.index[-1].year}-01-01")]
    ytd = close.iloc[-1] / year_start.iloc[0] - 1 if not year_start.empty else np.nan
    return {
        "name": label,
        "symbol": symbol,
        "first_date": close.index[0].date(),
        "last_date": close.index[-1].date(),
        "observations": len(close),
        "last_adjusted_close": close.iloc[-1],
        "1m_return": trailing_return(21),
        "3m_return": trailing_return(63),
        "1y_return": trailing_return(252),
        "ytd_return": ytd,
        "annualized_volatility": returns.std() * np.sqrt(252),
        "max_drawdown": drawdown.min(),
    }


metrics = pd.DataFrame(
    [
        series_metrics("Apple", EQUITY, apple_adjusted),
        series_metrics("S&P 500 Index", BENCHMARK, benchmark_adjusted),
    ]
)
display(metrics.style.format(precision=3))

# %% [markdown]
# ## 6. A small equity portfolio
#
# The portfolio is an illustrative research basket, not investment advice.
# Each holding uses the adjusted close returned by Barchart. The portfolio
# index is re-normalized at the first common observation, and failed public
# symbols are reported instead of silently replacing them.

# %%
portfolio_frames = {}
portfolio_failures = []
for symbol in PORTFOLIO_WEIGHTS:
    try:
        portfolio_frames[symbol] = fetch_history(symbol, dividends="true")
    except Exception as exc:
        portfolio_failures.append(
            {"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}
        )

if not portfolio_frames:
    raise RuntimeError("No portfolio histories were returned.")

portfolio_prices = pd.concat(
    {
        symbol: frame.set_index("date")["close"]
        for symbol, frame in portfolio_frames.items()
    },
    axis=1,
).sort_index().dropna()

active_weights = pd.Series(
    {symbol: PORTFOLIO_WEIGHTS[symbol] for symbol in portfolio_prices.columns},
    dtype=float,
)
active_weights = active_weights / active_weights.sum()
normalized_holdings = portfolio_prices / portfolio_prices.iloc[0] * 100
portfolio_index = normalized_holdings.mul(active_weights, axis=1).sum(axis=1)

portfolio_comparison = pd.concat(
    {
        "Portfolio": portfolio_index,
        "S&P 500 ($SPX)": benchmark_adjusted.set_index("date")["close"],
    },
    axis=1,
).dropna()
portfolio_comparison = portfolio_comparison / portfolio_comparison.iloc[0] * 100

display(
    pd.DataFrame(
        {
            "requested_weight": pd.Series(PORTFOLIO_WEIGHTS),
            "effective_weight": active_weights,
        }
    ).fillna(0)
)
if portfolio_failures:
    display(pd.DataFrame(portfolio_failures))

portfolio_frame = portfolio_comparison[["Portfolio"]].rename(
    columns={"Portfolio": "close"}
).reset_index(names="date")
display(
    pd.DataFrame(
        [series_metrics("Example portfolio", "active holdings", portfolio_frame)]
    ).style.format(precision=3)
)

# %% [markdown]
# ## 7. Relative performance

# %%
fig, axis = plt.subplots(figsize=(15, 6))
axis.set_facecolor(navy)
for column, color in [("Portfolio", gold), ("S&P 500 ($SPX)", sky)]:
    axis.plot(
        portfolio_comparison.index,
        portfolio_comparison[column],
        linewidth=2.0,
        color=color,
        label=column,
    )
axis.axhline(100, color=muted, linewidth=0.8)
axis.set_title(
    "Example equity portfolio versus Barchart S&P 500 index",
    loc="left",
    color="white",
    fontsize=16,
)
axis.set_ylabel("Indexed total-return path (first common date = 100)", color=muted)
axis.set_xlabel("Trade date", color=muted)
axis.legend(frameon=False, labelcolor="white")
axis.grid(True, color="#3A4A60", alpha=0.35)
plt.tight_layout()
plt.show()

# %% [markdown]
# ## Takeaways
#
# This notebook demonstrates a useful no-login equity workflow:
#
# 1. Read page-level company metadata and quote fields.
# 2. Download and validate historical OHLCV data.
# 3. Apply causal Screamer indicators.
# 4. Compare dividend-adjusted and unadjusted price histories.
# 5. Calculate transparent performance and risk metrics.
# 6. Build a reproducible, re-based portfolio comparison.
#
# Official Barchart OnDemand endpoints remain the appropriate route for
# licensed fundamentals, cash dividend ledgers, and broader API coverage.

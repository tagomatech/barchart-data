# ruff: noqa: E402

# %% [markdown]
# # Barchart historical CSV workflow
#
# This is a user-led, supported workflow for historical data:
#
# 1. Open the official Barchart historical-download page.
# 2. Choose the permitted frequency and date range.
# 3. Press Download in the normal browser UI.
# 4. Import the resulting local CSV and inspect its provenance and quality.
#
# The example uses CME/CBOT Corn Sep 2026 (ZCU26). It stays on one named
# contract, draws real OHLCV data as candlesticks, and adds causal streaming
# indicators from Screamer. No credentials, private endpoints, or synthetic
# observations are used.

# %%
from pathlib import Path
import sys
import time

candidate_roots = [Path.cwd(), *Path.cwd().parents]
repo_root = next(
    (candidate for candidate in candidate_roots if (candidate / "Barchart").is_dir()),
    None,
)
if repo_root is None:
    raise RuntimeError("Run this demo from a checkout containing the Barchart folder.")
sys.path.insert(0, str(repo_root))

# The imports intentionally follow the checkout bootstrap above.
# ruff: noqa: E402
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display
from matplotlib.patches import Rectangle
from screamer import ATR, BollingerBands, RollingMean, RollingRSI

from barchart_data import BarchartWebsiteWorkflow, history_quality_report

CONTRACT = "ZCU26"
DOWNLOAD_DIR = Path("downloads")
OPEN_BROWSER = False
WAIT_FOR_DOWNLOAD = False
PLOT_SESSIONS = 180
workflow = BarchartWebsiteWorkflow(download_dir=DOWNLOAD_DIR)
download_url = workflow.historical_download_url(CONTRACT)

# %% [markdown]
# ## 1. Open the official page
#
# The default is False so that re-running a notebook never opens a browser
# unexpectedly. Set OPEN_BROWSER to True when you want the notebook to open
# the page for you. Any account step and the Download button remain manual.

# %%
print(download_url)
download_started = time.time()
if OPEN_BROWSER:
    workflow.open_historical_download_page(CONTRACT)

# %% [markdown]
# ## 2. Import the local export
#
# Set WAIT_FOR_DOWNLOAD to True after enabling OPEN_BROWSER if you want the
# notebook to watch the local download folder after you click Download. The
# watcher never contacts Barchart and ignores files that are still changing.
# Alternatively, set CSV_PATH to an exact local file.

# %%
CSV_PATH = None
if CSV_PATH:
    imported = workflow.import_csv(CSV_PATH, symbol=CONTRACT)
elif WAIT_FOR_DOWNLOAD and OPEN_BROWSER:
    csv_path = workflow.wait_for_csv(symbol=CONTRACT, since=download_started)
    imported = workflow.import_csv(csv_path, symbol=CONTRACT)
else:
    try:
        imported = workflow.import_latest_csv(symbol=CONTRACT)
    except FileNotFoundError:
        imported = None

if imported is None:
    print(
        f"No {CONTRACT} CSV was found in {DOWNLOAD_DIR}. "
        "Download one from the page above, then re-run this cell."
    )
else:
    history = imported.frame
    quality = history_quality_report(
        history,
        required_columns=("date", "open", "high", "low", "close", "volume"),
    )
    provenance = pd.DataFrame(
        {
            "field": [
                "contract",
                "source file",
                "rows",
                "first date",
                "last date",
                "duplicate dates",
                "missing required columns",
                "missing required values",
            ],
            "value": [
                CONTRACT,
                str(imported.path),
                quality.rows,
                quality.start_date.date() if quality.start_date is not None else None,
                quality.end_date.date() if quality.end_date is not None else None,
                quality.duplicate_dates,
                ", ".join(quality.missing_columns) or "none",
                quality.missing_values,
            ],
        }
    )
    display(provenance)
    if not quality.is_usable:
        raise ValueError(
            "The downloaded file is not suitable for the OHLCV chart: "
            f"missing {quality.missing_columns}."
        )

# %% [markdown]
# ## 3. Compute streaming indicators
#
# Screamer processes the ordered arrays causally. These are useful descriptive
# tools for price structure and volatility; they are not trading signals.

# %%
if imported is not None:
    history = history.sort_values("date").reset_index(drop=True)
    if "openInterest" in history.columns:
        history["openInterest"] = history["openInterest"].where(
            history["openInterest"] > 0
        )

    close_values = history["close"].to_numpy(dtype=float)
    high_values = history["high"].to_numpy(dtype=float)
    low_values = history["low"].to_numpy(dtype=float)
    volume_values = history["volume"].to_numpy(dtype=float)

    history[["bb_lower", "bb_mid", "bb_upper"]] = BollingerBands(
        window_size=20,
        num_std=2.0,
    )(close_values)
    history["atr14"] = ATR(window_size=14)(
        high_values,
        low_values,
        close_values,
    )
    history["rsi14"] = RollingRSI(window_size=14)(close_values)
    history["volume_mean20"] = RollingMean(window_size=20)(volume_values)
    history["daily_return_pct"] = history["close"].pct_change() * 100

# %% [markdown]
# ## 4. Candlesticks, activity, and volatility

# %%
if imported is not None:
    navy = "#13233A"
    gold = "#F4B942"
    field_green = "#69B578"
    red = "#D95D5D"
    sky = "#73B7D8"
    muted = "#AEB9C6"

    plot_data = history.tail(PLOT_SESSIONS).copy()
    x_values = mdates.date2num(
        plot_data["date"].to_numpy(dtype="datetime64[ns]")
    )
    x_step = np.nanmedian(np.diff(x_values)) if len(x_values) > 1 else 1.0
    candle_width = max(float(x_step * 0.65), 0.25)

    plt.style.use("dark_background")
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(15, 12),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1, 1.1, 1.1]},
    )
    fig.patch.set_facecolor(navy)
    for axis in axes:
        axis.set_facecolor(navy)
        axis.grid(True, color="#3A4A60", alpha=0.35)
        axis.tick_params(colors=muted)
        for spine in axis.spines.values():
            spine.set_color("#3A4A60")

    for x_value, (_, row) in zip(x_values, plot_data.iterrows()):
        bullish = row["close"] >= row["open"]
        color = field_green if bullish else red
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
        "Barchart CSV | CBOT Corn | ZCU26 | September 2026",
        loc="left",
        color="white",
        fontsize=16,
        pad=14,
    )
    axes[0].set_ylabel("Cents/bushel", color=muted)
    axes[0].legend(frameon=False, labelcolor="white", loc="upper left", ncol=3)

    bar_colors = np.where(
        plot_data["close"].to_numpy() >= plot_data["open"].to_numpy(),
        field_green,
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
    axes[2].plot(
        x_values,
        plot_data["rsi14"],
        color=sky,
        linewidth=1.5,
        label="RSI(14)",
    )
    axes[2].set_ylim(0, 100)
    axes[2].set_ylabel("RSI", color=muted)
    axes[2].legend(frameon=False, labelcolor="white", loc="upper left")

    axes[3].plot(
        x_values,
        plot_data["atr14"],
        color=gold,
        linewidth=1.5,
        label="ATR(14)",
    )
    axes[3].set_ylabel("ATR", color=muted)
    axes[3].set_xlabel("Trade date", color=muted)
    axes[3].legend(frameon=False, labelcolor="white", loc="upper left")
    axes[3].xaxis_date()
    axes[3].xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    fig.text(
        0.01,
        0.01,
        "Source: user-downloaded Barchart CSV | "
        "Screamer indicators | fixed contract: ZCU26",
        color=muted,
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    plt.show()

# %% [markdown]
# ## 5. Recent observations

# %%
if imported is not None:
    recent_columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "daily_return_pct",
        "atr14",
        "rsi14",
    ]
    if "openInterest" in history.columns:
        recent_columns.insert(6, "openInterest")
    recent = history.tail(10)[recent_columns].copy()
    recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
    display(recent)

# %% [markdown]
# ## Notes
#
# The page URL is built from the contract symbol and can be reused for other
# Barchart asset classes by passing asset_class to historical_download_url.
# The package never assumes that a website export is current: the notebook
# displays the actual filename, date range, row count, duplicate count, and
# missing-value summary before charting it.

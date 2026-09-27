# Fetches and caches daily prices from yfinance for every purchase ticker plus
# SPY, then applies filters 6-7 of project.md Section 5.2: drop penny stocks
# (as-traded price < $2 on the filing date), drop tickers with no price data, and
# (7b) drop purchases whose filed price is more than 50% away from Yahoo's price.
# Also finds tickers with bad-print spikes (price snaps back within days).

import io
import logging
import re
import time

import numpy as np
import pandas as pd
import yfinance as yf

from utils import PRICE_RAW_DIR, record_row_count

MARKET_BENCHMARK = "SPY"
MINIMUM_PRICE_USD = 2.0  # filter 6
MAXIMUM_FILED_VS_YAHOO_PRICE_GAP = 0.50  # filter 7b
MAX_DAYS_BEFORE_FILING_FOR_PRICE = 5  # closest close on or before the filing date, within 5 calendar days
DOWNLOAD_BATCH_SIZE = 100
SECONDS_BETWEEN_BATCHES = 2.0
SECONDS_TO_WAIT_AFTER_RATE_LIMIT = 60
MAX_ATTEMPTS_PER_BATCH = 5
TICKERS_WITHOUT_DATA_FILE = PRICE_RAW_DIR / "_tickers_without_data.csv"


# ---------------------------------------------------------------------------
# Step A: turn the ticker typed on the filing into a Yahoo symbol
# ---------------------------------------------------------------------------
def clean_ticker(ticker_as_filed):
    """Return a Yahoo-style symbol, or None if the filing has no usable ticker.

    Rules: upper-case; keep only the first symbol if several are listed;
    drop over-the-counter suffixes .OB and .PK; share classes like BRK.B become BRK-B.
    """
    if not isinstance(ticker_as_filed, str):
        return None
    ticker = ticker_as_filed.strip().upper()
    ticker = re.split(r"[,;\s]+", ticker)[0]
    if ticker in ("", "NONE", "N/A", "NA", "NULL"):
        return None
    for suffix in (".OB", ".PK"):
        if ticker.endswith(suffix):
            ticker = ticker[: -len(suffix)]
    ticker = ticker.replace(".", "-").replace("/", "-")
    if not re.fullmatch(r"[A-Z0-9\-]+", ticker):
        return None
    return ticker


# ---------------------------------------------------------------------------
# Step B: download and cache prices
# ---------------------------------------------------------------------------
def price_file_path(ticker):
    """Cache location for one ticker. The 'px_' prefix avoids Windows reserved names like PRN or CON."""
    return PRICE_RAW_DIR / f"px_{ticker}.parquet"


def read_tickers_without_data():
    """Tickers that Yahoo already told us it has no data for (so we don't ask again)."""
    if not TICKERS_WITHOUT_DATA_FILE.exists():
        return set()
    return set(pd.read_csv(TICKERS_WITHOUT_DATA_FILE)["ticker"])


def download_prices(tickers):
    """Download full daily history for every ticker not already cached.

    Each ticker is saved to data/raw/prices/px_<TICKER>.parquet with columns:
    date, close (split-adjusted), adj_close (split- and dividend-adjusted, used for
    returns), volume, stock_split, close_as_traded (the actual price that day).
    """
    PRICE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    tickers_without_data = read_tickers_without_data()
    tickers_to_fetch = sorted(
        ticker
        for ticker in set(tickers)
        if not price_file_path(ticker).exists() and ticker not in tickers_without_data
    )
    print(f"{len(tickers_to_fetch):,} tickers to download")

    for batch_start in range(0, len(tickers_to_fetch), DOWNLOAD_BATCH_SIZE):
        batch = tickers_to_fetch[batch_start : batch_start + DOWNLOAD_BATCH_SIZE]
        empty = download_one_batch(batch)
        tickers_without_data.update(empty)
        pd.DataFrame({"ticker": sorted(tickers_without_data)}).to_csv(
            TICKERS_WITHOUT_DATA_FILE, index=False
        )
        print(f"  {batch_start + len(batch):,}/{len(tickers_to_fetch):,} done")
        time.sleep(SECONDS_BETWEEN_BATCHES)


def download_one_batch(batch):
    """Download one batch, retrying after Yahoo rate limits. Returns tickers with no data.

    Yahoo sometimes rate-limits part of a batch while other tickers succeed, and
    a rate-limited ticker looks the same as a truly missing one. So yfinance's
    log messages are captured, and if any mention a rate limit, the empty tickers
    are retried after a pause instead of being recorded as 'without data'.
    """
    remaining = list(batch)
    for attempt in range(1, MAX_ATTEMPTS_PER_BATCH + 1):
        yfinance_messages = io.StringIO()
        message_catcher = logging.StreamHandler(yfinance_messages)
        logging.getLogger("yfinance").addHandler(message_catcher)
        downloaded = yf.download(
            remaining,
            period="max",
            auto_adjust=False,
            actions=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
        logging.getLogger("yfinance").removeHandler(message_catcher)

        empty = []
        for ticker in remaining:
            history = extract_one_ticker(downloaded, ticker)
            if history is None:
                empty.append(ticker)
            else:
                history.to_parquet(price_file_path(ticker), index=False)

        messages = yfinance_messages.getvalue()
        was_rate_limited = "RateLimit" in messages or "Too Many Requests" in messages
        if not was_rate_limited:
            return empty

        print(f"  rate limited (attempt {attempt}); waiting {SECONDS_TO_WAIT_AFTER_RATE_LIMIT}s")
        time.sleep(SECONDS_TO_WAIT_AFTER_RATE_LIMIT)
        remaining = empty

    print(f"  gave up on {len(remaining)} tickers after rate limits; not cached, will retry next run")
    return []


def extract_one_ticker(downloaded, ticker):
    """Pull one ticker out of a yf.download result. Returns a tidy DataFrame or None."""
    if ticker not in downloaded.columns.get_level_values(0):
        return None
    raw = downloaded[ticker].dropna(subset=["Close"])
    if len(raw) == 0:
        return None
    history = pd.DataFrame(
        {
            "date": raw.index.tz_localize(None) if raw.index.tz is not None else raw.index,
            "close": raw["Close"].to_numpy(),
            "adj_close": raw["Adj Close"].to_numpy(),
            "volume": raw["Volume"].to_numpy(),
            "stock_split": raw["Stock Splits"].fillna(0).to_numpy(),
        }
    )
    history["close_as_traded"] = compute_as_traded_close(history)
    return history


def compute_as_traded_close(history):
    """Undo Yahoo's split adjustment so the close is the price actually traded that day.

    Yahoo divides every close before a split by the split ratio. To undo it,
    multiply each close by the product of all split ratios dated after that day.
    Example: NVDA's 2010 close shows as $0.46 on Yahoo but traded near $18.
    """
    split_ratio = history["stock_split"].where(history["stock_split"] > 0, 1.0)
    product_from_this_day_onward = split_ratio[::-1].cumprod()[::-1]
    product_after_this_day = product_from_this_day_onward / split_ratio
    return history["close"] * product_after_this_day


def load_price_history(ticker):
    """Read one cached ticker, or return None if we have no prices for it."""
    path = price_file_path(ticker)
    if not path.exists():
        return None
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# Step C: filters 6 and 7
# ---------------------------------------------------------------------------
def attach_close_on_filing_date(purchases):
    """Add close_as_traded_on_filing_date and price_match_status to each purchase.

    The price used is the last close on or before the filing date, at most
    MAX_DAYS_BEFORE_FILING_FOR_PRICE calendar days earlier.
    """
    purchases = purchases.copy()
    purchases["close_as_traded_on_filing_date"] = float("nan")
    purchases["price_match_status"] = "matched"
    purchases.loc[purchases["ticker"].isna(), "price_match_status"] = "no usable ticker on filing"

    for ticker, rows in purchases.dropna(subset=["ticker"]).groupby("ticker"):
        history = load_price_history(ticker)
        if history is None:
            purchases.loc[rows.index, "price_match_status"] = "no yfinance data"
            continue

        filing_dates = rows[["filing_date"]].reset_index().sort_values("filing_date")
        matched = pd.merge_asof(
            filing_dates,
            history[["date", "close_as_traded"]].sort_values("date"),
            left_on="filing_date",
            right_on="date",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_DAYS_BEFORE_FILING_FOR_PRICE),
        ).set_index("index")
        purchases.loc[matched.index, "close_as_traded_on_filing_date"] = matched["close_as_traded"]

        no_price_near_filing = matched.index[matched["close_as_traded"].isna()]
        purchases.loc[no_price_near_filing, "price_match_status"] = "no price near filing date"

    return purchases


def apply_price_filters(purchases, row_count_log):
    """Apply filters 6 and 7. Returns (kept purchases, table of dropped tickers).

    Filter 6 can only judge purchases that have a price, so unmatched purchases
    pass through it and are then removed by filter 7.
    """
    purchases = purchases.copy()
    purchases["ticker"] = purchases["ticker_as_filed"].apply(clean_ticker)
    purchases = attach_close_on_filing_date(purchases)
    purchases_needing_price = len(purchases)

    # Filter 6: drop penny stocks (as-traded close below $2 on the filing date).
    is_penny_stock = purchases["close_as_traded_on_filing_date"] < MINIMUM_PRICE_USD
    purchases = purchases[~is_penny_stock]
    record_row_count(row_count_log, "6. as-traded close on filing date >= $2", len(purchases))

    # Filter 7: keep only purchases matched to price data.
    unmatched = purchases[purchases["price_match_status"] != "matched"]
    purchases = purchases[purchases["price_match_status"] == "matched"]
    share_dropped = len(unmatched) / purchases_needing_price
    record_row_count(
        row_count_log,
        "7. matched to yfinance price data",
        len(purchases),
        note=f"{share_dropped:.1%} of purchases after filter 5 had no price match",
    )

    # Filter 7b: the price the insider reported must be within 50% of Yahoo's
    # as-traded close. Larger gaps are filing typos (total value typed as price)
    # or a reused ticker whose Yahoo history belongs to a different company.
    price_gap = (purchases["average_price"] / purchases["close_as_traded_on_filing_date"] - 1).abs()
    purchases = purchases[price_gap <= MAXIMUM_FILED_VS_YAHOO_PRICE_GAP]
    record_row_count(
        row_count_log,
        "7b. filed price within 50% of Yahoo as-traded close",
        len(purchases),
        note="data-quality filter added 26 Sep 2026, before any returns were computed",
    )

    dropped_tickers = (
        unmatched.fillna({"ticker": "(none)"})
        .groupby(["ticker", "price_match_status"])
        .agg(
            purchases_dropped=("accession_number", "size"),
            example_ticker_as_filed=("ticker_as_filed", "first"),
            example_issuer_name=("issuer_name", "first"),
        )
        .reset_index()
        .sort_values("purchases_dropped", ascending=False)
    )
    return purchases.reset_index(drop=True), dropped_tickers


# ---------------------------------------------------------------------------
# Step D: bad-print screen (project.md v3; applies to H1 and H8)
# ---------------------------------------------------------------------------
SPIKE_UP_RATIO = 4.0  # one-day move of 4x or more up...
SPIKE_DOWN_RATIO = 0.25  # ...or 75% or more down
SPIKE_REVERT_TRADING_DAYS = 5  # ...that returns within 5 trading days...
SPIKE_REVERT_TOLERANCE = 0.50  # ...to within 50% of the price before the move


def count_reverting_spikes(adj_close):
    """Number of one-day spikes that snap back: the signature of a bad price print."""
    daily_ratio = adj_close[1:] / adj_close[:-1]
    spike_days = np.flatnonzero((daily_ratio >= SPIKE_UP_RATIO) | (daily_ratio <= SPIKE_DOWN_RATIO))
    reverting_spikes = 0
    for day in spike_days:
        price_before_spike = adj_close[day]
        next_days = adj_close[day + 2 : day + 2 + SPIKE_REVERT_TRADING_DAYS]
        if np.any(np.abs(next_days / price_before_spike - 1) < SPIKE_REVERT_TOLERANCE):
            reverting_spikes += 1
    return reverting_spikes


def find_bad_print_tickers(tickers):
    """Return the set of tickers whose price history contains at least one snap-back spike."""
    bad_print_tickers = set()
    for ticker in tickers:
        history = load_price_history(ticker)
        if history is None:
            continue
        adj_close = history.sort_values("date")["adj_close"].to_numpy()
        if count_reverting_spikes(adj_close) > 0:
            bad_print_tickers.add(ticker)
    return bad_print_tickers

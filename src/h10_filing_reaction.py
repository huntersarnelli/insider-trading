# H10 (project.md Section 3, v4): how much of the insider-filing price reaction is
# still available at the first realistic entry? Uses EDGAR acceptance times and
# Yahoo open prices; entry at the next open (or the close for intraday filings).

import datetime as dt
import io
import logging
import re
import time

import numpy as np
import pandas as pd
import yfinance as yf

from edge_stats import robustness_checks, summarise_edge
from h8_tech import h8_entry_day_rule
from load_prices import MARKET_BENCHMARK, load_price_history
from utils import RAW_DIR, fetch_sec_text

ACCEPTANCE_TIMES_FILE = RAW_DIR / "sec_acceptance_times.csv"
EDGAR_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}-index.htm"
OPEN_PRICE_DIR = RAW_DIR / "prices_open"
TECH_BENCHMARK = "QQQ"
MARKET_OPEN = dt.time(9, 30)
MARKET_CLOSE = dt.time(16, 0)
EXIT_DAYS = [0, 1, 3, 5]  # closes after the entry day; 0 = entry day's close (open entries only)
NUMBER_OF_CONTROL_DRAWS = 200
RANDOM_SEED = 2026
H10_MIN_EDGE = 0.003  # +0.3pp
H10_MIN_T_STAT = 2.0
H10_MIN_EVENTS = 300


# ---------------------------------------------------------------------------
# Step A: acceptance time from each filing's EDGAR index page (Eastern time)
# ---------------------------------------------------------------------------
# The submissions API's acceptanceDateTime mixes UTC and Eastern, so it is not used.
ACCEPTED_PATTERN = re.compile(r'Accepted</div>\s*<div class="info">([^<]+)<')


def fetch_acceptance_times(events):
    """Return accession_number -> acceptance time (naive Eastern) read from EDGAR index pages.
    One request per filing; cached in data/raw/sec_acceptance_times.csv (saved every 25 filings)."""
    columns = ["accession_number", "acceptance_time"]
    cache = pd.read_csv(ACCEPTANCE_TIMES_FILE, dtype=str) if ACCEPTANCE_TIMES_FILE.exists() else pd.DataFrame(columns=columns)
    to_fetch = events[~events["accession_number"].isin(cache["accession_number"])][["accession_number", "issuer_cik"]].drop_duplicates("accession_number")
    print(f"{len(to_fetch)} filings to fetch acceptance times for")
    new_rows = []
    for count, (accession, issuer_cik) in enumerate(zip(to_fetch["accession_number"], to_fetch["issuer_cik"]), start=1):
        url = EDGAR_INDEX_URL.format(cik=int(issuer_cik), folder=accession.replace("-", ""), accession=accession)
        page = fetch_sec_text(url)
        match = ACCEPTED_PATTERN.search(page or "")
        new_rows.append({"accession_number": accession, "acceptance_time": match.group(1).strip() if match else ""})
        if count % 25 == 0 or count == len(to_fetch):
            cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
            cache.to_csv(ACCEPTANCE_TIMES_FILE, index=False)
            new_rows = []
            print(f"  {count}/{len(to_fetch)} done")
    cache = cache[cache["acceptance_time"].fillna("") != ""]
    return pd.Series(pd.to_datetime(cache["acceptance_time"]).to_numpy(), index=cache["accession_number"])


# ---------------------------------------------------------------------------
# Step B: open prices (a separate cache; the main price cache has closes only)
# ---------------------------------------------------------------------------
def open_price_path(ticker):
    return OPEN_PRICE_DIR / f"px_{ticker}.parquet"


def download_open_prices(tickers):
    """Cache date, open, close, adj_close for each ticker. Retries after Yahoo rate limits."""
    OPEN_PRICE_DIR.mkdir(parents=True, exist_ok=True)
    remaining = sorted(ticker for ticker in set(tickers) if not open_price_path(ticker).exists())
    for attempt in range(5):
        if not remaining:
            return
        messages = io.StringIO()
        catcher = logging.StreamHandler(messages)
        logging.getLogger("yfinance").addHandler(catcher)
        downloaded = yf.download(remaining, period="max", auto_adjust=False, group_by="ticker", progress=False, threads=True)
        logging.getLogger("yfinance").removeHandler(catcher)
        for ticker in remaining:
            if ticker not in downloaded.columns.get_level_values(0):
                continue
            raw = downloaded[ticker].dropna(subset=["Open", "Close"])
            if len(raw):
                dates = raw.index.tz_localize(None) if raw.index.tz is not None else raw.index
                pd.DataFrame({"date": dates, "open": raw["Open"].to_numpy(), "close": raw["Close"].to_numpy(), "adj_close": raw["Adj Close"].to_numpy()}).to_parquet(open_price_path(ticker), index=False)
        remaining = [ticker for ticker in remaining if not open_price_path(ticker).exists()]
        if "RateLimit" not in messages.getvalue() and "Too Many Requests" not in messages.getvalue():
            break
        print(f"rate limited; waiting 60s (attempt {attempt + 1})")
        time.sleep(60)
    if remaining:
        print(f"no open prices for {len(remaining)} tickers: {remaining[:10]}")


def load_open_arrays(ticker, benchmarks):
    """Arrays for one ticker: dates, adjusted open/close, SPY/QQQ adjusted open/close on the
    same dates, plus close, volume and close_as_traded (for the H8 day rule)."""
    prices = pd.read_parquet(open_price_path(ticker)).sort_values("date")
    main = load_price_history(ticker)[["date", "close_as_traded", "volume"]]
    prices = prices.merge(main, on="date", how="inner").reset_index(drop=True)
    arrays = {
        "dates": prices["date"].to_numpy(),
        "close": prices["close"].to_numpy(),
        "volume": prices["volume"].to_numpy(),
        "close_as_traded": prices["close_as_traded"].to_numpy(),
        "adj_open": (prices["open"] * prices["adj_close"] / prices["close"]).to_numpy(),
        "adj_close": prices["adj_close"].to_numpy(),
    }
    for name, benchmark in benchmarks.items():
        aligned = benchmark.set_index("date").reindex(prices["date"], method="ffill")
        arrays[f"{name}_adj_open"] = (aligned["open"] * aligned["adj_close"] / aligned["close"]).to_numpy()
        arrays[f"{name}_adj_close"] = aligned["adj_close"].to_numpy()
    return arrays


# ---------------------------------------------------------------------------
# Step C: entry rule and returns
# ---------------------------------------------------------------------------
def entry_point(acceptance_time, trading_days):
    """Return (entry_date, 'open' or 'close') for a filing accepted at acceptance_time (Eastern)."""
    day = pd.Timestamp(acceptance_time.date())
    is_trading_day = day in trading_days
    if is_trading_day and acceptance_time.time() < MARKET_OPEN:
        return day, "open"
    if is_trading_day and acceptance_time.time() < MARKET_CLOSE:
        return day, "close"
    next_position = trading_days.searchsorted(day, side="right")
    if next_position >= len(trading_days):
        return None, None
    return trading_days[next_position], "open"


def window_returns(arrays, entry_days, entry_type, exit_days_after):
    """Raw, SPY- and QQQ-adjusted returns from entry (open or close) to the close exit_days_after later."""
    exit_days = entry_days + exit_days_after
    price_at_entry = "adj_open" if entry_type == "open" else "adj_close"
    raw = arrays["adj_close"][exit_days] / arrays[price_at_entry][entry_days] - 1
    spy = arrays["spy_adj_close"][exit_days] / arrays[f"spy_{price_at_entry}"][entry_days] - 1
    qqq = arrays["qqq_adj_close"][exit_days] / arrays[f"qqq_{price_at_entry}"][entry_days] - 1
    return {"raw": raw, "market_adjusted": raw - spy, "qqq_adjusted": raw - qqq}


def overnight_gap(arrays, entry_days):
    """Market-adjusted gap from the previous close to the entry open (what you miss if you can't trade after hours)."""
    stock = arrays["adj_open"][entry_days] / arrays["adj_close"][entry_days - 1] - 1
    spy = arrays["spy_adj_open"][entry_days] / arrays["spy_adj_close"][entry_days - 1] - 1
    return stock - spy


def add_entry_points(events, acceptance_times, trading_days):
    """Add acceptance_time, entry_date and entry_type to each event; events without a timestamp get NaN."""
    events = events.copy()
    events["acceptance_time"] = events["accession_number"].map(acceptance_times)
    entries = [entry_point(accepted, trading_days) if pd.notna(accepted) else (None, None) for accepted in events["acceptance_time"]]
    events["h10_entry_date"] = [entry for entry, _ in entries]
    events["entry_type"] = [kind for _, kind in entries]
    return events


# ---------------------------------------------------------------------------
# Step D: event returns, random-day controls, tables and verdict
# ---------------------------------------------------------------------------
RETURN_TYPES = ["market_adjusted", "raw", "qqq_adjusted"]


def load_benchmarks():
    return {"spy": pd.read_parquet(open_price_path(MARKET_BENCHMARK)), "qqq": pd.read_parquet(open_price_path(TECH_BENCHMARK))}


def compute_h10_returns(events, benchmarks):
    """Per exit day k: event returns and (events x 200) control returns for each return type,
    plus the overnight gap for open entries. Controls are random H8-eligible days in the
    same ticker with the same entry type and exit."""
    random_generator = np.random.default_rng(RANDOM_SEED)
    n = len(events)
    event_returns = {k: {rt: np.full(n, np.nan) for rt in RETURN_TYPES} for k in EXIT_DAYS}
    controls = {k: {rt: np.full((n, NUMBER_OF_CONTROL_DRAWS), np.nan, dtype=np.float32) for rt in RETURN_TYPES} for k in EXIT_DAYS}
    event_gap = np.full(n, np.nan)
    control_gap = np.full((n, NUMBER_OF_CONTROL_DRAWS), np.nan, dtype=np.float32)

    for ticker, rows in events.groupby("ticker"):
        arrays = load_open_arrays(ticker, benchmarks)
        eligible_days = np.flatnonzero(h8_entry_day_rule(arrays))
        eligible_days = eligible_days[eligible_days >= 1]
        for position, entry_date, entry_type in zip(events.index.get_indexer(rows.index), rows["h10_entry_date"], rows["entry_type"]):
            entry_index = np.searchsorted(arrays["dates"], np.datetime64(entry_date))
            if entry_index >= len(arrays["dates"]) or arrays["dates"][entry_index] != np.datetime64(entry_date):
                continue
            if entry_type == "open" and entry_index >= 1:
                event_gap[position] = overnight_gap(arrays, entry_index)
            for k in EXIT_DAYS:
                if (entry_type == "close" and k == 0) or entry_index + k >= len(arrays["dates"]):
                    continue
                for rt, value in window_returns(arrays, entry_index, entry_type, k).items():
                    event_returns[k][rt][position] = value
                usable = eligible_days[eligible_days + k < len(arrays["dates"])]
                if len(usable) == 0:
                    continue
                random_days = usable[random_generator.integers(0, len(usable), NUMBER_OF_CONTROL_DRAWS)]
                for rt, values in window_returns(arrays, random_days, entry_type, k).items():
                    controls[k][rt][position] = values
                if entry_type == "open" and k == 0:
                    control_gap[position] = overnight_gap(arrays, random_days)
    return event_returns, controls, event_gap, control_gap


def build_h10_tables(events, event_returns, controls, event_gap, control_gap):
    """Edge and robustness tables by exit day, return type and entry type."""
    edge_rows, robustness_rows = [], []
    cohorts = {"all": np.ones(len(events), dtype=bool), "open entries": (events["entry_type"] == "open").to_numpy(), "close entries": (events["entry_type"] == "close").to_numpy()}
    windows = [(f"entry to close +{k}d", event_returns[k], controls[k]) for k in EXIT_DAYS]
    windows.append(("overnight gap (not tradable without after-hours)", {"market_adjusted": event_gap}, {"market_adjusted": control_gap}))
    for window, returns_by_type, controls_by_type in windows:
        for rt in returns_by_type:
            for cohort, in_cohort in cohorts.items():
                summary = summarise_edge(returns_by_type[rt][in_cohort], controls_by_type[rt][in_cohort], events["filing_date"][in_cohort])
                if summary["n"] == 0:
                    continue
                labels = {"window": window, "return_type": rt, "cohort": cohort}
                edge_rows.append({**labels, **summary})
                robustness_rows.append({**labels, **robustness_checks(returns_by_type[rt][in_cohort], controls_by_type[rt][in_cohort], events["filing_date"][in_cohort], events["ticker"][in_cohort])})
    return pd.DataFrame(edge_rows), pd.DataFrame(robustness_rows)


def h10_verdict(edge_table):
    """PASS if, market-adjusted, the open-entry same-day-close window or the all-events +1 day
    window has edge >= +0.3pp, t >= 2.0, positive in both halves and n >= 300."""
    deciding = edge_table[
        (edge_table["return_type"] == "market_adjusted")
        & (((edge_table["window"] == "entry to close +0d") & (edge_table["cohort"] == "open entries"))
           | ((edge_table["window"] == "entry to close +1d") & (edge_table["cohort"] == "all")))
    ].copy()
    deciding["passes_edge"] = deciding["edge"] >= H10_MIN_EDGE
    deciding["passes_t_stat"] = deciding["t_stat"] >= H10_MIN_T_STAT
    deciding["passes_both_halves"] = (deciding["first_half_edge"] > 0) & (deciding["second_half_edge"] > 0)
    deciding["passes_sample_size"] = deciding["n"] >= H10_MIN_EVENTS
    deciding["passes_all"] = deciding[["passes_edge", "passes_t_stat", "passes_both_halves", "passes_sample_size"]].all(axis=1)
    return ("PASS" if deciding["passes_all"].any() else "FAIL"), deciding

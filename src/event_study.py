# Turns purchases into events and measures what happened next: removes
# duplicate events, computes raw and market-adjusted returns from the entry
# close, the price-based tags (H6 Z-score, H7 size), the random-date control,
# and assembles the edge and secondary-test tables.

import numpy as np
import pandas as pd

from edge_stats import compare_tagged_vs_untagged, is_secondary_finding, robustness_checks, summarise_edge
from load_prices import MARKET_BENCHMARK, MINIMUM_PRICE_USD, load_price_history

HORIZONS = [5, 20, 60, 120]  # trading days after the entry close
NUMBER_OF_CONTROL_DRAWS = 200
RANDOM_SEED = 2026
REPEAT_FILING_TRADING_DAYS = 5  # Section 6.1: same insider, same company, within 5 trading days -> keep first
Z_SCORE_WINDOW = 20
AFTER_DROP_Z_THRESHOLD = -1.2  # H6
DOLLAR_VOLUME_WINDOW = 20  # H7
TECH_BENCHMARK = "QQQ"
RETURN_TYPES = ["market_adjusted", "raw", "qqq_adjusted"]  # market_adjusted decides H1 and H8 (project.md)


# ---------------------------------------------------------------------------
# Step A: trading calendar and market prices
# ---------------------------------------------------------------------------
def load_market_history():
    """SPY history (date, adj_close) plus QQQ's adj_close as qqq_adj_close (NaN before 1999).

    SPY's dates are the trading calendar. QQQ is the Nasdaq-100 fund, used for
    the H8 comparison "could I have just bought a tech ETF?".
    """
    spy = load_price_history(MARKET_BENCHMARK)[["date", "adj_close"]]
    qqq = load_price_history(TECH_BENCHMARK)[["date", "adj_close"]].rename(columns={"adj_close": "qqq_adj_close"})
    market_history = spy.merge(qqq, on="date", how="left")
    return market_history.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step B: remove duplicate events
# ---------------------------------------------------------------------------
def remove_duplicate_events(purchases, trading_calendar):
    """Return (events, dedup_log).

    1. Same company, same trade date, same shares and price = the same trade
       reported by related filers (e.g. affiliated funds): keep the earliest filing.
    2. Same insider, same company, filings within 5 trading days: keep the first.
    """
    dedup_log = [{"step": "purchases after Phase 1 filters", "events": len(purchases)}]

    events = purchases.sort_values(["filing_date", "accession_number"]).copy()
    events["rounded_price"] = events["average_price"].round(4)
    events = events.drop_duplicates(["issuer_cik", "first_transaction_date", "shares_purchased", "rounded_price"])
    events = events.drop(columns="rounded_price")
    dedup_log.append({"step": "same trade reported by related filers removed", "events": len(events)})

    events["filing_day_number"] = np.searchsorted(trading_calendar.to_numpy(), events["filing_date"].to_numpy())
    events = events.sort_values(["owner_cik", "issuer_cik", "filing_date", "accession_number"])
    keep = np.zeros(len(events), dtype=bool)
    previous_key = None
    last_kept_day = None
    for position, (owner, issuer, day) in enumerate(
        zip(events["owner_cik"], events["issuer_cik"], events["filing_day_number"])
    ):
        is_new_insider_company = (owner, issuer) != previous_key
        if is_new_insider_company or day - last_kept_day > REPEAT_FILING_TRADING_DAYS:
            keep[position] = True
            last_kept_day = day
        previous_key = (owner, issuer)
    events = events[keep].drop(columns="filing_day_number")
    dedup_log.append({"step": "repeat filings by same insider within 5 trading days removed", "events": len(events)})

    events = events.sort_values(["filing_date", "accession_number"]).reset_index(drop=True)
    return events, pd.DataFrame(dedup_log)


# ---------------------------------------------------------------------------
# Step C: event returns and price-based tags
# ---------------------------------------------------------------------------
def load_ticker_arrays(ticker, market_history):
    """Numpy arrays for one ticker: dates, close, adj_close, volume, close_as_traded,
    and SPY and QQQ adjusted closes on the same dates."""
    history = load_price_history(ticker).sort_values("date").reset_index(drop=True)
    benchmarks_on_ticker_dates = market_history.set_index("date").reindex(history["date"], method="ffill")
    return {
        "dates": history["date"].to_numpy(),
        "close": history["close"].to_numpy(),
        "adj_close": history["adj_close"].to_numpy(),
        "volume": history["volume"].to_numpy(),
        "close_as_traded": history["close_as_traded"].to_numpy(),
        "spy_adj_close": benchmarks_on_ticker_dates["adj_close"].to_numpy(),
        "qqq_adj_close": benchmarks_on_ticker_dates["qqq_adj_close"].to_numpy(),
    }


def period_returns(arrays, entry_days, exit_days):
    """Returns from entry close to exit close: raw, minus SPY, and minus QQQ.

    entry_days and exit_days can be single positions or numpy arrays of positions.
    """
    raw = arrays["adj_close"][exit_days] / arrays["adj_close"][entry_days] - 1
    spy = arrays["spy_adj_close"][exit_days] / arrays["spy_adj_close"][entry_days] - 1
    qqq = arrays["qqq_adj_close"][exit_days] / arrays["qqq_adj_close"][entry_days] - 1
    return {"raw": raw, "market_adjusted": raw - spy, "qqq_adjusted": raw - qqq}


def add_returns_and_price_tags(events, market_history):
    """Add entry_date, z_score_20, is_after_drop, dollar_volume_20, and for each
    horizon h and return type (raw, market_adjusted, qqq_adjusted): return_<type>_h.

    Entry is the close on the first trading day strictly after the filing date.
    A horizon's return is NaN if the price series ends before entry + h.
    """
    events = events.copy()
    new_columns = {"entry_date": np.full(len(events), np.datetime64("NaT"), dtype="datetime64[ns]")}
    for name in ["z_score_20", "dollar_volume_20"]:
        new_columns[name] = np.full(len(events), np.nan)
    for horizon in HORIZONS:
        for return_type in RETURN_TYPES:
            new_columns[f"return_{return_type}_{horizon}"] = np.full(len(events), np.nan)

    for ticker, rows in events.groupby("ticker"):
        arrays = load_ticker_arrays(ticker, market_history)
        row_positions = events.index.get_indexer(rows.index)
        entry_indexes = np.searchsorted(arrays["dates"], rows["filing_date"].to_numpy(), side="right")

        for row_position, entry_index in zip(row_positions, entry_indexes):
            filing_index = entry_index - 1  # last trading day on or before the filing date
            if filing_index >= Z_SCORE_WINDOW - 1:
                window = slice(filing_index - Z_SCORE_WINDOW + 1, filing_index + 1)
                closes = arrays["close"][window]
                if closes.std(ddof=1) > 0:
                    new_columns["z_score_20"][row_position] = (closes[-1] - closes.mean()) / closes.std(ddof=1)
                dollar_volume = arrays["close"][window] * arrays["volume"][window]
                new_columns["dollar_volume_20"][row_position] = dollar_volume.mean()

            if entry_index >= len(arrays["dates"]):
                continue
            new_columns["entry_date"][row_position] = arrays["dates"][entry_index]
            for horizon in HORIZONS:
                exit_index = entry_index + horizon
                if exit_index >= len(arrays["dates"]):
                    continue
                for return_type, value in period_returns(arrays, entry_index, exit_index).items():
                    new_columns[f"return_{return_type}_{horizon}"][row_position] = value

    for name, values in new_columns.items():
        events[name] = values
    events["is_after_drop"] = (events["z_score_20"] <= AFTER_DROP_Z_THRESHOLD).where(events["z_score_20"].notna())
    events["size_tercile"] = size_terciles_within_year(events)
    return events


def size_terciles_within_year(events):
    """H7: 1 = smallest, 3 = largest 20-day dollar volume, ranked within each filing year."""
    filing_year = events["filing_date"].dt.year
    ranks = events.groupby(filing_year)["dollar_volume_20"].rank(pct=True)
    return np.ceil(ranks * 3).clip(1, 3)


# ---------------------------------------------------------------------------
# Step D: random-date control
# ---------------------------------------------------------------------------
def default_entry_day_rule(arrays):
    """H1 control rule: an entry day must pass the same $2 as-traded rule as the events
    (filter 6). Sub-$2 days are where Yahoo's bad prints live (e.g. $0.0001 quotes)."""
    return arrays["close_as_traded"] >= MINIMUM_PRICE_USD


def draw_control_returns(events, market_history, horizon, entry_day_rule=default_entry_day_rule):
    """Return a dict {return_type: array of shape (events, 200)}.

    For each event, 200 random entry days are drawn from the same ticker's
    price history: any day where entry_day_rule(arrays) is True and a price
    exists h days later. Rows are NaN when the event itself has no return at
    this horizon, or the ticker has no eligible day.
    """
    random_generator = np.random.default_rng(RANDOM_SEED + horizon)
    controls = {
        return_type: np.full((len(events), NUMBER_OF_CONTROL_DRAWS), np.nan, dtype=np.float32)
        for return_type in RETURN_TYPES
    }
    has_event_return = events[f"return_raw_{horizon}"].notna().to_numpy()

    for ticker in sorted(events["ticker"].unique()):
        row_positions = np.flatnonzero((events["ticker"] == ticker).to_numpy() & has_event_return)
        if len(row_positions) == 0:
            continue
        arrays = load_ticker_arrays(ticker, market_history)
        last_possible_entry = len(arrays["dates"]) - horizon
        valid_entry_days = np.flatnonzero(entry_day_rule(arrays)[:last_possible_entry])
        if len(valid_entry_days) == 0:
            continue
        picks = random_generator.integers(0, len(valid_entry_days), size=(len(row_positions), NUMBER_OF_CONTROL_DRAWS))
        entry_days = valid_entry_days[picks]
        for return_type, values in period_returns(arrays, entry_days, entry_days + horizon).items():
            controls[return_type][row_positions] = values

    return controls


# ---------------------------------------------------------------------------
# Step E: build the edge table and the secondary-test table
# ---------------------------------------------------------------------------
COHORTS = ["all", "opportunistic", "routine", "unclassified"]
SAMPLE_START_DATES = {"full": None, "2013_onward": "2013-01-01"}  # 2013+ is post-publication (exploratory)


def secondary_test_tags(events):
    """Tag per secondary hypothesis: True = tagged, False = comparison group, NaN = excluded."""
    smallest_vs_largest = (events["size_tercile"] == 1).where(events["size_tercile"].isin([1, 3]))
    return {
        "H3_ceo_or_cfo": events["is_ceo_or_cfo"],
        "H4_large_purchase": events["is_large_purchase"],
        "H5a_cluster_2_trading_days": events["is_cluster_2day"],
        "H5b_cluster_10_calendar_days": events["is_cluster_10day"],
        "H6_after_drop_z20": events["is_after_drop"],
        "H7_smallest_vs_largest_tercile": smallest_vs_largest,
    }


def build_edge_tables(events, market_history):
    """Return (edge_table, secondary_table, robustness_table) over every horizon and return type.

    Robustness diagnostics (never deciding) are for the full sample, 'all' and 'opportunistic'.
    """
    edge_rows = []
    secondary_rows = []
    robustness_rows = []
    filing_dates = events["filing_date"]

    for horizon in HORIZONS:
        controls = draw_control_returns(events, market_history, horizon)
        print(f"controls drawn for {horizon}-day horizon")

        for return_type in RETURN_TYPES:
            event_returns = events[f"return_{return_type}_{horizon}"].to_numpy()

            for sample_name, start_date in SAMPLE_START_DATES.items():
                in_sample = np.ones(len(events), dtype=bool) if start_date is None else (filing_dates >= start_date).to_numpy()
                for cohort in COHORTS:
                    in_cohort = in_sample if cohort == "all" else in_sample & (events["cohort"] == cohort).to_numpy()
                    summary = summarise_edge(event_returns[in_cohort], controls[return_type][in_cohort], filing_dates[in_cohort])
                    edge_rows.append({"sample": sample_name, "cohort": cohort, "horizon": horizon, "return_type": return_type, **summary})
                    if sample_name == "full" and cohort in ("all", "opportunistic"):
                        checks = robustness_checks(event_returns[in_cohort], controls[return_type][in_cohort], filing_dates[in_cohort], events["ticker"][in_cohort])
                        robustness_rows.append({"sample": sample_name, "cohort": cohort, "horizon": horizon, "return_type": return_type, **checks})

            for hypothesis, tag in secondary_test_tags(events).items():
                has_tag = tag.notna().to_numpy()
                comparison = compare_tagged_vs_untagged(
                    event_returns[has_tag], controls[return_type][has_tag], filing_dates[has_tag], tag[has_tag]
                )
                secondary_rows.append({"hypothesis": hypothesis, "horizon": horizon, "return_type": return_type, **comparison})

    secondary_table = pd.DataFrame(secondary_rows)
    secondary_table["is_finding"] = secondary_table.apply(is_secondary_finding, axis=1)
    return pd.DataFrame(edge_rows), secondary_table, pd.DataFrame(robustness_rows)

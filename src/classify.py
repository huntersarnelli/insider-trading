# Labels each insider purchase as routine, opportunistic or unclassified using
# Cohen, Malloy & Pomorski (2012), and adds the filing-based tags for the
# secondary tests: H3 (CEO/CFO), H4 (large purchase), H5a/H5b (cluster purchases).

import zipfile

import numpy as np
import pandas as pd

from load_filings import FIRST_YEAR, download_quarter, parse_sec_date, read_table
from utils import PROCESSED_DIR

TRADE_HISTORY_FILE = PROCESSED_DIR / "trade_history.parquet"
YEARS_OF_HISTORY_REQUIRED = 3
# Data starts in 2006, so 2009 is the first year with three full years of history.
# Earlier years would lean on the few late filings that report pre-2006 trades.
FIRST_CLASSIFIABLE_YEAR = FIRST_YEAR + YEARS_OF_HISTORY_REQUIRED
MAX_YEARS_BETWEEN_TRADE_AND_FILING = 2  # older trade dates on a filing are treated as typos
LARGE_PURCHASE_SHARE_OF_PRIOR_HOLDING = 0.10  # H4
CLUSTER_2DAY_TRADING_DAYS = 2  # H5a window
CLUSTER_2DAY_MIN_INSIDERS = 2
CLUSTER_10DAY_CALENDAR_DAYS = 10  # H5b window
CLUSTER_10DAY_MIN_INSIDERS = 3
CEO_CFO_TITLE_PATTERN = (
    r"\b(?:ceo|cfo|chief executive|chief financial|principal executive|principal financial)\b"
)


# ---------------------------------------------------------------------------
# Step A: trade history (all open-market purchases AND sales, no size filters)
# ---------------------------------------------------------------------------
def build_trade_history(quarters):
    """Return one row per (owner_cik, issuer_cik, trade_date) with an open-market trade.

    Uses every Form 4 code P or S row in common stock, because the paper's
    classification counts all trades. Cached to data/processed/trade_history.parquet.
    """
    if TRADE_HISTORY_FILE.exists():
        return pd.read_parquet(TRADE_HISTORY_FILE)

    all_quarters = []
    for quarter in quarters:
        with zipfile.ZipFile(download_quarter(quarter)) as zip_file:
            submissions = read_table(zip_file, "SUBMISSION", ["ACCESSION_NUMBER", "DOCUMENT_TYPE", "ISSUERCIK", "FILING_DATE"])
            owners = read_table(zip_file, "REPORTINGOWNER", ["ACCESSION_NUMBER", "RPTOWNERCIK"])
            trades = read_table(zip_file, "NONDERIV_TRANS", ["ACCESSION_NUMBER", "SECURITY_TITLE", "TRANS_CODE", "TRANS_DATE"])

        form4_submissions = submissions[submissions["DOCUMENT_TYPE"] == "4"]
        first_owner = owners.drop_duplicates("ACCESSION_NUMBER", keep="first")
        title_lower = trades["SECURITY_TITLE"].str.lower().fillna("")
        is_common = title_lower.str.contains("common") | title_lower.str.contains("ordinary")
        trades = trades[is_common & trades["TRANS_CODE"].isin(["P", "S"])]

        trades = trades.merge(form4_submissions, on="ACCESSION_NUMBER").merge(first_owner, on="ACCESSION_NUMBER")
        all_quarters.append(
            pd.DataFrame(
                {
                    "owner_cik": trades["RPTOWNERCIK"],
                    "issuer_cik": trades["ISSUERCIK"],
                    "trade_date": parse_sec_date(trades["TRANS_DATE"]),
                    "filing_date": parse_sec_date(trades["FILING_DATE"]),
                }
            )
        )

    history = pd.concat(all_quarters, ignore_index=True)
    earliest_believable = history["filing_date"] - pd.DateOffset(years=MAX_YEARS_BETWEEN_TRADE_AND_FILING)
    believable = (history["trade_date"] <= history["filing_date"]) & (history["trade_date"] >= earliest_believable)
    history = history[believable]
    history = history[["owner_cik", "issuer_cik", "trade_date"]].drop_duplicates().reset_index(drop=True)

    TRADE_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    history.to_parquet(TRADE_HISTORY_FILE, index=False)
    return history


# ---------------------------------------------------------------------------
# Step B: routine / opportunistic / unclassified
# ---------------------------------------------------------------------------
def months_traded_by_year(trade_history):
    """Return a dict: (owner_cik, issuer_cik, year) -> set of calendar months traded."""
    table = pd.DataFrame(
        {
            "owner_cik": trade_history["owner_cik"],
            "issuer_cik": trade_history["issuer_cik"],
            "year": trade_history["trade_date"].dt.year,
            "month": trade_history["trade_date"].dt.month,
        }
    )
    grouped = table.groupby(["owner_cik", "issuer_cik", "year"])["month"].apply(set)
    return grouped.to_dict()


def classify_insider_year(months_by_key, owner_cik, issuer_cik, year):
    """Label one insider at one company for one calendar year.

    unclassified: before 2009, or missing a trade in any of the three preceding years.
    routine: at least one calendar month traded in all three preceding years.
    opportunistic: classifiable but not routine.
    """
    if year < FIRST_CLASSIFIABLE_YEAR:
        return "unclassified"
    prior_years = [year - offset for offset in range(1, YEARS_OF_HISTORY_REQUIRED + 1)]
    month_sets = []
    for prior_year in prior_years:
        months = months_by_key.get((owner_cik, issuer_cik, prior_year))
        if not months:
            return "unclassified"
        month_sets.append(months)

    months_in_every_year = set.intersection(*month_sets)
    if len(months_in_every_year) > 0:
        return "routine"
    return "opportunistic"


def add_cohort_labels(events, trade_history):
    """Add a 'cohort' column (routine / opportunistic / unclassified) to each event.

    The label for an event filed in year t comes from trades in years t-1, t-2, t-3.
    """
    months_by_key = months_traded_by_year(trade_history)
    events = events.copy()
    events["cohort"] = [
        classify_insider_year(months_by_key, owner, issuer, filing_date.year)
        for owner, issuer, filing_date in zip(events["owner_cik"], events["issuer_cik"], events["filing_date"])
    ]
    return events


# ---------------------------------------------------------------------------
# Step C: filing-based tags for H3, H4, H5a, H5b
# ---------------------------------------------------------------------------
def tag_ceo_or_cfo(owner_titles):
    """H3: True if the officer title names a CEO or CFO (case-insensitive)."""
    return owner_titles.fillna("").str.lower().str.contains(CEO_CFO_TITLE_PATTERN, regex=True)


def tag_large_purchase(shares_purchased, shares_owned_after):
    """H4: True if shares bought are >= 10% of shares held before the purchase.

    A first-ever position (nothing held before) counts as large. Returns NaN
    when shares owned after the purchase were not reported.
    """
    shares_held_before = shares_owned_after - shares_purchased
    share_of_prior = shares_purchased / shares_held_before.where(shares_held_before > 0)
    is_large = (share_of_prior >= LARGE_PURCHASE_SHARE_OF_PRIOR_HOLDING) | (shares_held_before <= 0)
    return is_large.where(shares_owned_after.notna())


def tag_clusters(events, all_purchases, trading_calendar):
    """H5a and H5b: add is_cluster_2day and is_cluster_10day to each event.

    For an event, count distinct insiders at the same company (the event's own
    insider included) whose trade date is close to the event's trade date AND
    whose filing was public by the event's filing date, so there is no lookahead.
    H5a: trade dates within 2 trading days, at least 2 insiders.
    H5b: trade dates within 10 calendar days, at least 3 insiders.
    An event with no transaction date gets NaN (unknown) for both tags.
    """
    purchases_with_dates = all_purchases[all_purchases["first_transaction_date"].notna()]
    purchases_by_issuer = {issuer: rows for issuer, rows in purchases_with_dates.groupby("issuer_cik")}
    is_cluster_2day = np.full(len(events), np.nan)
    is_cluster_10day = np.full(len(events), np.nan)

    for position, event in enumerate(events.itertuples(index=False)):
        if pd.isna(event.first_transaction_date):
            continue
        others = purchases_by_issuer[event.issuer_cik]
        others = others[others["filing_date"] <= event.filing_date]

        days_apart = (others["first_transaction_date"] - event.first_transaction_date).dt.days.abs()
        within_10_days = others[days_apart <= CLUSTER_10DAY_CALENDAR_DAYS]
        is_cluster_10day[position] = within_10_days["owner_cik"].nunique() >= CLUSTER_10DAY_MIN_INSIDERS

        event_day_number = trading_day_number(trading_calendar, event.first_transaction_date)
        other_day_numbers = trading_day_number(trading_calendar, others["first_transaction_date"])
        within_2_trading_days = others[np.abs(other_day_numbers - event_day_number) <= CLUSTER_2DAY_TRADING_DAYS]
        is_cluster_2day[position] = within_2_trading_days["owner_cik"].nunique() >= CLUSTER_2DAY_MIN_INSIDERS

    events = events.copy()
    events["is_cluster_2day"] = pd.Series(is_cluster_2day, index=events.index).map({1.0: True, 0.0: False})
    events["is_cluster_10day"] = pd.Series(is_cluster_10day, index=events.index).map({1.0: True, 0.0: False})
    return events


def trading_day_number(trading_calendar, dates):
    """Position of each date in the trading calendar (a non-trading day maps to the next trading day)."""
    return np.searchsorted(trading_calendar.to_numpy(), np.asarray(dates, dtype="datetime64[ns]"))


def add_filing_tags(events, all_purchases, trading_calendar):
    """Add all filing-based tags: is_ceo_or_cfo, is_large_purchase, is_cluster_2day, is_cluster_10day."""
    events = events.copy()
    events["is_ceo_or_cfo"] = tag_ceo_or_cfo(events["owner_title"])
    events["is_large_purchase"] = tag_large_purchase(events["shares_purchased"], events["shares_owned_after"])
    return tag_clusters(events, all_purchases, trading_calendar)

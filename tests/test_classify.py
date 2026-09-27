# Unit tests for classify.py: the routine / opportunistic / unclassified rule
# (Cohen, Malloy & Pomorski 2012) on hand-built insider histories, plus the
# CEO/CFO, large-purchase and cluster tags.

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from classify import (  # noqa: E402
    add_cohort_labels,
    classify_insider_year,
    months_traded_by_year,
    tag_ceo_or_cfo,
    tag_clusters,
    tag_large_purchase,
)


def make_history(trade_dates, owner_cik="OWNER1", issuer_cik="FIRM1"):
    """Hand-built trade history for one insider at one company."""
    return pd.DataFrame(
        {
            "owner_cik": owner_cik,
            "issuer_cik": issuer_cik,
            "trade_date": pd.to_datetime(trade_dates),
        }
    )


def label_for(trade_dates, year):
    months_by_key = months_traded_by_year(make_history(trade_dates))
    return classify_insider_year(months_by_key, "OWNER1", "FIRM1", year)


# ---------------------------------------------------------------------------
# Routine / opportunistic / unclassified
# ---------------------------------------------------------------------------
def test_same_month_three_years_is_routine():
    assert label_for(["2015-03-10", "2016-03-02", "2017-03-20"], 2018) == "routine"


def test_different_months_each_year_is_opportunistic():
    assert label_for(["2015-01-10", "2016-02-02", "2017-03-20"], 2018) == "opportunistic"


def test_shared_month_among_several_months_is_routine():
    trades = ["2015-03-01", "2015-07-01", "2016-07-15", "2017-01-05", "2017-07-30"]
    assert label_for(trades, 2018) == "routine"


def test_gap_year_is_unclassified():
    assert label_for(["2015-03-10", "2017-03-20"], 2018) == "unclassified"


def test_only_two_years_of_history_is_unclassified():
    assert label_for(["2016-03-02", "2017-03-20"], 2018) == "unclassified"


def test_trades_in_the_current_year_do_not_count():
    # 2016, 2017, 2018 in March, but classifying 2018 needs 2015, 2016 and 2017.
    assert label_for(["2016-03-02", "2017-03-20", "2018-03-05"], 2018) == "unclassified"


def test_trades_before_the_three_year_window_do_not_count():
    # March in 2014 and 2016 and 2017 does not make 2018 routine: 2015 is missing.
    assert label_for(["2014-03-01", "2016-03-02", "2017-03-20"], 2018) == "unclassified"


def test_history_at_another_company_does_not_count():
    history = pd.concat(
        [
            make_history(["2015-03-10", "2016-03-02"], issuer_cik="FIRM1"),
            make_history(["2017-03-20"], issuer_cik="FIRM2"),
        ]
    )
    months_by_key = months_traded_by_year(history)
    assert classify_insider_year(months_by_key, "OWNER1", "FIRM1", 2018) == "unclassified"


def test_add_cohort_labels_uses_filing_year():
    history = make_history(["2015-03-10", "2016-03-02", "2017-03-20"])
    events = pd.DataFrame(
        {
            "owner_cik": ["OWNER1", "OWNER1", "OWNER2"],
            "issuer_cik": ["FIRM1", "FIRM1", "FIRM1"],
            "filing_date": pd.to_datetime(["2018-06-01", "2017-06-01", "2018-06-01"]),
        }
    )
    labelled = add_cohort_labels(events, history)
    assert labelled["cohort"].tolist() == ["routine", "unclassified", "unclassified"]


# ---------------------------------------------------------------------------
# H3 and H4 tags
# ---------------------------------------------------------------------------
def test_ceo_or_cfo_titles():
    titles = pd.Series(["President and CEO", "Chief Financial Officer", "Director", None, "EVP, Principal Executive Officer"])
    assert tag_ceo_or_cfo(titles).tolist() == [True, True, False, False, True]


def test_large_purchase_rule():
    shares_purchased = pd.Series([100.0, 50.0, 500.0, 100.0])
    shares_owned_after = pd.Series([1100.0, 1050.0, 500.0, np.nan])
    # 100 on 1,000 held = exactly 10% -> large; 50 on 1,000 = 5% -> small;
    # first-ever position -> large; owned-after missing -> unknown.
    result = tag_large_purchase(shares_purchased, shares_owned_after)
    assert result.iloc[0] == True  # noqa: E712
    assert result.iloc[1] == False  # noqa: E712
    assert result.iloc[2] == True  # noqa: E712
    assert pd.isna(result.iloc[3])


# ---------------------------------------------------------------------------
# H5 cluster tags
# ---------------------------------------------------------------------------
def test_clusters_only_count_filings_already_public():
    trading_calendar = pd.Series(pd.bdate_range("2020-01-01", "2020-03-31"))
    purchases = pd.DataFrame(
        {
            "issuer_cik": ["FIRM1"] * 4,
            "owner_cik": ["A", "B", "C", "D"],
            "first_transaction_date": pd.to_datetime(["2020-02-03", "2020-02-04", "2020-02-10", "2020-03-20"]),
            "filing_date": pd.to_datetime(["2020-02-05", "2020-02-06", "2020-02-12", "2020-03-23"]),
        }
    )
    tagged = tag_clusters(purchases, purchases, trading_calendar)
    # A: nobody else public yet -> no cluster.
    # B: A traded 1 trading day earlier and was public -> 2-day cluster; only 2 insiders -> no 10-day cluster.
    # C: A and B within 10 calendar days -> 10-day cluster; A/B are 5-6 trading days away -> no 2-day cluster.
    # D: alone.
    assert tagged["is_cluster_2day"].tolist() == [False, True, False, False]
    assert tagged["is_cluster_10day"].tolist() == [False, False, True, False]


def test_cluster_tags_are_unknown_when_trade_date_missing():
    trading_calendar = pd.Series(pd.bdate_range("2020-01-01", "2020-03-31"))
    purchases = pd.DataFrame(
        {
            "issuer_cik": ["FIRM1", "FIRM1"],
            "owner_cik": ["A", "B"],
            "first_transaction_date": pd.to_datetime(["2020-02-03", None]),
            "filing_date": pd.to_datetime(["2020-02-05", "2020-02-06"]),
        }
    )
    tagged = tag_clusters(purchases, purchases, trading_calendar)
    assert tagged["is_cluster_2day"].iloc[0] == False  # noqa: E712
    assert pd.isna(tagged["is_cluster_2day"].iloc[1])
    assert pd.isna(tagged["is_cluster_10day"].iloc[1])


def test_years_before_2009_are_unclassified():
    # Late filings can report trades from 2004-2005, but history before 2006 is incomplete.
    assert label_for(["2004-03-10", "2005-03-02", "2006-03-20", "2007-03-20"], 2008) == "unclassified"
    assert label_for(["2006-03-20", "2007-03-20", "2008-03-20"], 2009) == "routine"

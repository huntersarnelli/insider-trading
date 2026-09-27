# H8 (project.md Section 3, v3): selects the tech-universe events (seasoned, liquid
# tech companies, 2013 onward) and builds their edge tables. Control days must
# pass the same rules as the events. Run once; rules are fixed in project.md.

import numpy as np
import pandas as pd

from edge_stats import compare_tagged_vs_untagged, is_secondary_finding, robustness_checks, summarise_edge
from event_study import HORIZONS, RETURN_TYPES, draw_control_returns, secondary_test_tags
from load_industry import add_industry
from load_prices import load_price_history

H8_START_DATE = pd.Timestamp("2013-01-01")
H8_MIN_PRICE_USD = 5.0
H8_MIN_DOLLAR_VOLUME_USD = 10_000_000
H8_MIN_YEARS_OF_HISTORY = 3
DOLLAR_VOLUME_WINDOW = 20
H8_SAMPLE_NAME = "h8_tech"
H8_SECONDARY_TAGS = ["H3_ceo_or_cfo", "H4_large_purchase", "H5a_cluster_2_trading_days", "H5b_cluster_10_calendar_days", "H6_after_drop_z20"]


def sic_group(sic_numbers):
    """Label each SIC code as semiconductors, software/IT services, or hardware and other tech."""
    groups = pd.Series("hardware & other tech (3570-3679, 3825, 3827)", index=sic_numbers.index)
    groups[sic_numbers == 3674] = "semiconductors (3674)"
    groups[sic_numbers.between(7370, 7379)] = "software & IT services (7370-7379)"
    return groups


def select_h8_events(events):
    """Apply the H8 rules to the (already bad-print-screened) events. Returns (h8_events, counts)."""
    events = add_industry(events)
    first_price_date = {ticker: load_price_history(ticker)["date"].min() for ticker in events["ticker"].unique()}
    events["years_of_history"] = (events["filing_date"] - events["ticker"].map(first_price_date)).dt.days / 365.25

    rules = [
        ("tech SIC code", events["is_tech_sic"]),
        ("filed 2013 or later", events["filing_date"] >= H8_START_DATE),
        ("as-traded close >= $5", events["close_as_traded_on_filing_date"] >= H8_MIN_PRICE_USD),
        ("dollar volume >= $10M/day", events["dollar_volume_20"] >= H8_MIN_DOLLAR_VOLUME_USD),
        (">= 3 years of price history", events["years_of_history"] >= H8_MIN_YEARS_OF_HISTORY),
    ]
    keep = pd.Series(True, index=events.index)
    counts = [{"step": "events after bad-print screen", "events": len(events), "opportunistic_events": (events["cohort"] == "opportunistic").sum()}]
    for step_name, passes_rule in rules:
        keep = keep & passes_rule.fillna(False)
        counts.append({"step": step_name, "events": keep.sum(), "opportunistic_events": (keep & (events["cohort"] == "opportunistic")).sum()})

    h8_events = events[keep].reset_index(drop=True)
    h8_events["sic_group"] = sic_group(pd.to_numeric(h8_events["sic"], errors="coerce"))
    return h8_events, pd.DataFrame(counts)


def h8_entry_day_rule(arrays):
    """A control entry day qualifies only if the day before it (standing in for the
    filing day) passes the H8 event rules: on or after 2013-01-01, as-traded close
    >= $5, 20-day average dollar volume >= $10M, and >= 3 years of price history."""
    dates = arrays["dates"]
    dollar_volume_20 = pd.Series(arrays["close"] * arrays["volume"]).rolling(DOLLAR_VOLUME_WINDOW).mean().to_numpy()
    years_of_history = (dates - dates[0]) / np.timedelta64(1, "D") / 365.25
    passes_on_day = (
        (dates >= np.datetime64(H8_START_DATE))
        & (arrays["close_as_traded"] >= H8_MIN_PRICE_USD)
        & (dollar_volume_20 >= H8_MIN_DOLLAR_VOLUME_USD)
        & (years_of_history >= H8_MIN_YEARS_OF_HISTORY)
    )
    entry_day_qualifies = np.zeros(len(dates), dtype=bool)
    entry_day_qualifies[1:] = passes_on_day[:-1]
    return entry_day_qualifies


def build_h8_tables(h8_events, market_history):
    """Return (edge_table, secondary_table, robustness_table) for H8.

    Cohorts: 'all' (decides H8), 'opportunistic', and each SIC group (breakdowns).
    """
    edge_rows, secondary_rows, robustness_rows = [], [], []
    filing_dates = h8_events["filing_date"]
    cohorts = {"all": np.ones(len(h8_events), dtype=bool), "opportunistic": (h8_events["cohort"] == "opportunistic").to_numpy()}
    for group_name in sorted(h8_events["sic_group"].unique()):
        cohorts[group_name] = (h8_events["sic_group"] == group_name).to_numpy()
    tags = {name: tag for name, tag in secondary_test_tags(h8_events).items() if name in H8_SECONDARY_TAGS}

    for horizon in HORIZONS:
        controls = draw_control_returns(h8_events, market_history, horizon, entry_day_rule=h8_entry_day_rule)
        print(f"H8 controls drawn for {horizon}-day horizon")
        for return_type in RETURN_TYPES:
            event_returns = h8_events[f"return_{return_type}_{horizon}"].to_numpy()
            labels = {"horizon": horizon, "return_type": return_type}

            for cohort, in_cohort in cohorts.items():
                summary = summarise_edge(event_returns[in_cohort], controls[return_type][in_cohort], filing_dates[in_cohort])
                edge_rows.append({"sample": H8_SAMPLE_NAME, "cohort": cohort, **labels, **summary})

            for hypothesis, tag in tags.items():
                has_tag = tag.notna().to_numpy()
                comparison = compare_tagged_vs_untagged(event_returns[has_tag], controls[return_type][has_tag], filing_dates[has_tag], tag[has_tag])
                secondary_rows.append({"hypothesis": hypothesis, **labels, **comparison})

            checks = robustness_checks(event_returns, controls[return_type], filing_dates, h8_events["ticker"])
            robustness_rows.append({"sample": H8_SAMPLE_NAME, "cohort": "all", **labels, **checks})

    secondary_table = pd.DataFrame(secondary_rows)
    secondary_table["is_finding"] = secondary_table.apply(is_secondary_finding, axis=1)
    return pd.DataFrame(edge_rows), secondary_table, pd.DataFrame(robustness_rows)

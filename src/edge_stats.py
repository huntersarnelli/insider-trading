# Statistics for the event study: edge versus the random-date control,
# month-clustered t-statistics, empirical p-values, split halves, the
# tagged-vs-untagged comparisons, the pass/fail verdict, and robustness diagnostics.

import numpy as np
import pandas as pd
from scipy import stats

# project.md Section 4 (fixed; do not change)
H1_MIN_EDGE = 0.005  # +0.5 percentage points
H1_MIN_T_STAT = 2.0
H1_MIN_EVENTS = 300
H1_HORIZONS = [20, 60]
SECONDARY_MIN_T_STAT = 2.5


def month_clustered_t_stat(values, event_dates):
    """Average values by calendar month of the event, then t-test the monthly means against zero."""
    months = pd.Series(pd.to_datetime(event_dates)).dt.to_period("M").to_numpy()
    monthly_means = pd.Series(values).groupby(months).mean()
    if len(monthly_means) < 2:
        return np.nan
    return stats.ttest_1samp(monthly_means, 0.0).statistic


def summarise_edge(event_returns, control_returns, event_dates):
    """Edge statistics for one group of events at one horizon and return type.

    event_returns: 1-D array; control_returns: (events, 200) array; event_dates: filing dates.
    Rows with no event return are ignored.
    """
    has_return = ~np.isnan(event_returns)
    event_returns = event_returns[has_return]
    control_returns = control_returns[has_return]
    event_dates = pd.to_datetime(pd.Series(event_dates)[has_return]).reset_index(drop=True)

    if len(event_returns) == 0:
        return {"n": 0}

    matched_control = np.nanmean(control_returns, axis=1)
    event_minus_control = event_returns - matched_control
    mean_event = event_returns.mean()
    mean_control = matched_control.mean()

    # Empirical p-value: share of the 200 draws whose control mean is at least the event mean.
    control_mean_per_draw = np.nanmean(control_returns, axis=0)
    p_value = (control_mean_per_draw >= mean_event).mean()

    median_date = event_dates.median()
    in_first_half = (event_dates <= median_date).to_numpy()

    return {
        "n": len(event_returns),
        "mean_event": mean_event,
        "mean_control": mean_control,
        "edge": mean_event - mean_control,
        "t_stat": month_clustered_t_stat(event_minus_control, event_dates),
        "p_value": p_value,
        "first_half_edge": event_minus_control[in_first_half].mean(),
        "second_half_edge": event_minus_control[~in_first_half].mean(),
    }


def compare_tagged_vs_untagged(event_returns, control_returns, event_dates, is_tagged):
    """Secondary tests: does the tagged group's edge beat the untagged group's edge?

    Each event's edge = event return - its matched control. Per calendar month,
    take (mean tagged edge - mean untagged edge); the t-statistic tests those
    monthly differences against zero. Rows with a missing tag or return are ignored.
    """
    has_return = ~np.isnan(event_returns)
    event_returns = event_returns[has_return]
    control_returns = control_returns[has_return]
    event_dates = pd.Series(event_dates)[has_return]
    is_tagged = pd.Series(is_tagged)[has_return]

    matched_control = np.nanmean(control_returns, axis=1)
    table = pd.DataFrame(
        {
            "edge": event_returns - matched_control,
            "date": pd.to_datetime(pd.Series(event_dates)).to_numpy(),
            "is_tagged": pd.Series(is_tagged).to_numpy(),
        }
    ).dropna()
    table["is_tagged"] = table["is_tagged"].astype(bool)
    table["month"] = table["date"].dt.to_period("M")

    tagged = table[table["is_tagged"]]
    untagged = table[~table["is_tagged"]]
    monthly = pd.DataFrame(
        {
            "tagged": tagged.groupby("month")["edge"].mean(),
            "untagged": untagged.groupby("month")["edge"].mean(),
        }
    ).dropna()
    monthly_difference = monthly["tagged"] - monthly["untagged"]
    t_stat = stats.ttest_1samp(monthly_difference, 0.0).statistic if len(monthly_difference) >= 2 else np.nan

    median_date = table["date"].median()
    halves = {}
    for half_name, in_half in [("first_half", table["date"] <= median_date), ("second_half", table["date"] > median_date)]:
        half = table[in_half]
        halves[half_name] = half[half["is_tagged"]]["edge"].mean() - half[~half["is_tagged"]]["edge"].mean()

    return {
        "n_tagged": len(tagged),
        "n_untagged": len(untagged),
        "edge_tagged": tagged["edge"].mean(),
        "edge_untagged": untagged["edge"].mean(),
        "difference": tagged["edge"].mean() - untagged["edge"].mean(),
        "t_stat": t_stat,
        "first_half_difference": halves["first_half"],
        "second_half_difference": halves["second_half"],
    }


def is_secondary_finding(row):
    """project.md Section 4: t >= 2.5 and a positive difference in both halves."""
    return bool(
        row["t_stat"] >= SECONDARY_MIN_T_STAT
        and row["first_half_difference"] > 0
        and row["second_half_difference"] > 0
    )


def h1_verdict(edge_table, sample="full", cohort="opportunistic"):
    """Check the Section 4 criteria on one sample/cohort's market-adjusted rows.

    Defaults are H1 (full sample, opportunistic). H8 uses the same criteria on
    its own table. Returns (verdict_text, criteria_table). Passes if every
    criterion holds at the 20-day OR the 60-day horizon. Under 300 events is 'underpowered'.
    """
    h1_rows = edge_table[
        (edge_table["sample"] == sample)
        & (edge_table["cohort"] == cohort)
        & (edge_table["return_type"] == "market_adjusted")
        & (edge_table["horizon"].isin(H1_HORIZONS))
    ]
    criteria_rows = []
    for row in h1_rows.itertuples(index=False):
        criteria_rows.append(
            {
                "horizon": row.horizon,
                "n": row.n,
                "edge": row.edge,
                "t_stat": row.t_stat,
                "first_half_edge": row.first_half_edge,
                "second_half_edge": row.second_half_edge,
                "passes_edge": row.edge >= H1_MIN_EDGE,
                "passes_t_stat": row.t_stat >= H1_MIN_T_STAT,
                "passes_both_halves": row.first_half_edge > 0 and row.second_half_edge > 0,
                "passes_sample_size": row.n >= H1_MIN_EVENTS,
            }
        )
    criteria = pd.DataFrame(criteria_rows)
    pass_columns = ["passes_edge", "passes_t_stat", "passes_both_halves", "passes_sample_size"]
    criteria["passes_all"] = criteria[pass_columns].all(axis=1)

    if criteria["passes_all"].any():
        verdict = "PASS"
    elif not criteria["passes_sample_size"].any():
        verdict = "UNDERPOWERED"
    else:
        verdict = "FAIL"
    return verdict, criteria


def robustness_checks(event_returns, control_returns, event_dates, companies):
    """Diagnostics reported next to a verdict (never deciding it).

    Shows whether a mean edge is broad-based or carried by a few extreme events
    or companies: median, share of events beating their control, 1%-trimmed mean
    and its t-statistic, and how much of the total edge the top 10 companies supply.
    """
    has_return = ~np.isnan(event_returns)
    edge = event_returns[has_return] - np.nanmean(control_returns[has_return], axis=1)
    dates = pd.to_datetime(pd.Series(event_dates)[has_return]).reset_index(drop=True)
    companies = pd.Series(companies)[has_return].reset_index(drop=True)
    has_control = ~np.isnan(edge)
    edge, dates, companies = edge[has_control], dates[has_control].reset_index(drop=True), companies[has_control].reset_index(drop=True)
    if len(edge) == 0:
        return {"n": 0}

    low, high = np.quantile(edge, [0.01, 0.99])
    in_trim = (edge >= low) & (edge <= high)
    edge_by_company = pd.Series(edge).groupby(companies).sum().sort_values(ascending=False)
    top10 = edge_by_company.head(10).index
    return {
        "n": len(edge),
        "mean_edge": edge.mean(),
        "median_edge": np.median(edge),
        "share_beating_control": (edge > 0).mean(),
        "trimmed_1pct_edge": edge[in_trim].mean(),
        "trimmed_1pct_t_stat": month_clustered_t_stat(edge[in_trim], dates[in_trim]),
        "top10_companies_share_of_total_edge": edge_by_company.head(10).sum() / edge.sum(),
        "edge_excluding_top10_companies": edge[~companies.isin(top10).to_numpy()].mean(),
        "largest_company": edge_by_company.index[0],
        "largest_company_share_of_total_edge": edge_by_company.iloc[0] / edge.sum(),
    }

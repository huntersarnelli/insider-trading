# Runs the whole Phase 2 event study in one go: H1 (plus H2-H7), H8 (tech) and
# H10 (filing reaction). Writes every CSV to results/phase2_event_study/,
# results/phase2_h8_tech/ and results/phase2_h10_filing_reaction/.
# Same steps as notebooks/02_event_study.ipynb, without the explanations.

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from classify import add_cohort_labels, add_filing_tags, build_trade_history  # noqa: E402
from edge_stats import h1_verdict  # noqa: E402
from event_study import (  # noqa: E402
    add_returns_and_price_tags,
    build_edge_tables,
    load_market_history,
    remove_duplicate_events,
)
from h8_tech import H8_SAMPLE_NAME, build_h8_tables, select_h8_events  # noqa: E402
from h10_filing_reaction import (  # noqa: E402
    MARKET_BENCHMARK,
    TECH_BENCHMARK,
    add_entry_points,
    build_h10_tables,
    compute_h10_returns,
    download_open_prices,
    fetch_acceptance_times,
    h10_verdict,
    load_benchmarks,
)
from load_filings import list_quarters  # noqa: E402
from load_prices import find_bad_print_tickers  # noqa: E402
from utils import PROCESSED_DIR, save_results_csv  # noqa: E402

H1_FOLDER = "phase2_event_study"
H8_FOLDER = "phase2_h8_tech"
H10_FOLDER = "phase2_h10_filing_reaction"


def build_events():
    """Purchases -> de-duplicated, bad-print-screened, classified, tagged events with returns."""
    purchases = pd.read_parquet(PROCESSED_DIR / "purchases.parquet")
    market_history = load_market_history()
    trading_calendar = market_history["date"]

    events, dedup_log = remove_duplicate_events(purchases, trading_calendar)
    bad_print_tickers = find_bad_print_tickers(events["ticker"].unique())
    events = events[~events["ticker"].isin(bad_print_tickers)].reset_index(drop=True)
    dedup_log.loc[len(dedup_log)] = {"step": f"bad-print tickers removed ({len(bad_print_tickers)} tickers)", "events": len(events)}
    save_results_csv(dedup_log, H1_FOLDER, "dedup_counts.csv")

    trade_history = build_trade_history(list_quarters())
    events = add_cohort_labels(events, trade_history)
    events = add_filing_tags(events, purchases, trading_calendar)
    events = add_returns_and_price_tags(events, market_history)
    events.to_parquet(PROCESSED_DIR / "events.parquet", index=False)
    return events, market_history


def run_h1(events, market_history):
    events_by_year_cohort = pd.crosstab(events["filing_date"].dt.year, events["cohort"]).reset_index()
    events_by_year_cohort = events_by_year_cohort.rename(columns={"filing_date": "filing_year"})
    save_results_csv(events_by_year_cohort, H1_FOLDER, "events_by_year_cohort.csv")

    edge_table, secondary_table, robustness_table = build_edge_tables(events, market_history)
    save_results_csv(edge_table, H1_FOLDER, "edge_table.csv")
    save_results_csv(secondary_table, H1_FOLDER, "secondary_tests.csv")
    save_results_csv(robustness_table, H1_FOLDER, "robustness_checks.csv")

    verdict, criteria = h1_verdict(edge_table)
    save_results_csv(criteria, H1_FOLDER, "h1_criteria.csv")
    print(f"H1 verdict: {verdict}")
    print(criteria.to_string())


def run_h8(events, market_history):
    h8_events, counts = select_h8_events(events)
    save_results_csv(counts, H8_FOLDER, "h8_event_counts.csv")

    edge_table, secondary_table, robustness_table = build_h8_tables(h8_events, market_history)
    save_results_csv(edge_table, H8_FOLDER, "h8_edge_table.csv")
    save_results_csv(secondary_table, H8_FOLDER, "h8_breakdown_tests.csv")
    save_results_csv(robustness_table, H8_FOLDER, "h8_robustness_checks.csv")

    verdict, criteria = h1_verdict(edge_table, sample=H8_SAMPLE_NAME, cohort="all")
    save_results_csv(criteria, H8_FOLDER, "h8_criteria.csv")
    print(f"H8 verdict: {verdict}")
    print(criteria.to_string())


def run_h10(events, market_history):
    h8_events, _ = select_h8_events(events)
    acceptance_times = fetch_acceptance_times(h8_events)
    download_open_prices(list(h8_events["ticker"].unique()) + [MARKET_BENCHMARK, TECH_BENCHMARK])
    trading_days = pd.DatetimeIndex(market_history["date"])
    h10_events = add_entry_points(h8_events, acceptance_times, trading_days).reset_index(drop=True)

    counts = pd.DataFrame(
        [
            {"step": "H8 events", "events": len(h10_events)},
            {"step": "with SEC acceptance timestamp", "events": h10_events["acceptance_time"].notna().sum()},
            {"step": "entry at open (filed before 9:30 or after 16:00 / non-trading day)", "events": (h10_events["entry_type"] == "open").sum()},
            {"step": "entry at close (filed during market hours)", "events": (h10_events["entry_type"] == "close").sum()},
        ]
    )
    save_results_csv(counts, H10_FOLDER, "h10_event_counts.csv")
    print(counts.to_string(index=False))

    event_returns, controls, event_gap, control_gap = compute_h10_returns(h10_events, load_benchmarks())
    edge_table, robustness_table = build_h10_tables(h10_events, event_returns, controls, event_gap, control_gap)
    save_results_csv(edge_table, H10_FOLDER, "h10_edge_table.csv")
    save_results_csv(robustness_table, H10_FOLDER, "h10_robustness_checks.csv")
    verdict, criteria = h10_verdict(edge_table)
    save_results_csv(criteria, H10_FOLDER, "h10_criteria.csv")
    print(f"H10 verdict: {verdict}")
    print(criteria.to_string())


def main():
    events, market_history = build_events()
    run_h1(events, market_history)
    run_h8(events, market_history)
    run_h10(events, market_history)


if __name__ == "__main__":
    main()

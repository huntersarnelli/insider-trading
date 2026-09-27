# Unit tests for event_study.py and edge_stats.py on small made-up price series
# where the right answer is known in advance: entry timing, returns, dropped
# horizons, the random-date control, duplicate removal and the H1 verdict.

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import event_study  # noqa: E402
from edge_stats import h1_verdict, month_clustered_t_stat, summarise_edge  # noqa: E402

TRADING_DAYS = pd.bdate_range("2020-01-01", periods=200)
DAILY_GROWTH = 1.01  # the made-up stock rises exactly 1% every trading day


def fake_price_history(ticker):
    """Stock grows 1% a day; SPY is flat, so market-adjusted return = raw return."""
    if ticker == "SPY":
        adj_close = np.full(len(TRADING_DAYS), 300.0)
    else:
        adj_close = 10.0 * DAILY_GROWTH ** np.arange(len(TRADING_DAYS))
    return pd.DataFrame(
        {
            "date": TRADING_DAYS,
            "close": adj_close,
            "adj_close": adj_close,
            "volume": np.full(len(TRADING_DAYS), 1000.0),
            "close_as_traded": adj_close,
        }
    )


@pytest.fixture
def fake_prices(monkeypatch):
    monkeypatch.setattr(event_study, "load_price_history", fake_price_history)
    return event_study.load_market_history()


def make_events(filing_dates):
    return pd.DataFrame({"ticker": "FAKE", "filing_date": pd.to_datetime(filing_dates)})


def test_entry_is_the_day_after_filing_and_returns_are_exact(fake_prices):
    events = event_study.add_returns_and_price_tags(make_events(["2020-01-15"]), fake_prices)
    assert events["entry_date"].iloc[0] == pd.Timestamp("2020-01-16")
    for horizon in event_study.HORIZONS:
        expected = DAILY_GROWTH**horizon - 1
        assert events[f"return_raw_{horizon}"].iloc[0] == pytest.approx(expected)
        assert events[f"return_market_adjusted_{horizon}"].iloc[0] == pytest.approx(expected)


def test_horizon_past_end_of_prices_is_dropped_only_for_that_horizon(fake_prices):
    # Filing 30 trading days before the end: 5- and 20-day returns exist, 60 and 120 do not.
    filing_date = TRADING_DAYS[-31]
    events = event_study.add_returns_and_price_tags(make_events([filing_date]), fake_prices)
    assert events["return_raw_5"].notna().iloc[0]
    assert events["return_raw_20"].notna().iloc[0]
    assert events["return_raw_60"].isna().iloc[0]
    assert events["return_raw_120"].isna().iloc[0]


def test_steady_rise_has_positive_z_score(fake_prices):
    events = event_study.add_returns_and_price_tags(make_events(["2020-03-02"]), fake_prices)
    assert events["z_score_20"].iloc[0] > 1.5
    assert events["is_after_drop"].iloc[0] == False  # noqa: E712


def test_controls_on_a_steady_series_equal_the_event_return(fake_prices):
    events = event_study.add_returns_and_price_tags(make_events(["2020-01-15", "2020-02-14"]), fake_prices)
    controls = event_study.draw_control_returns(events, fake_prices, 20)
    assert controls["raw"].shape == (2, event_study.NUMBER_OF_CONTROL_DRAWS)
    assert np.allclose(controls["raw"], DAILY_GROWTH**20 - 1, rtol=1e-5)
    assert np.allclose(controls["market_adjusted"], controls["raw"])


def test_controls_skip_days_below_two_dollars(monkeypatch):
    # First 100 days trade at $1 (flat); after that the price is >= $2 and rises 1% a day.
    # Every control draw must come from the >= $2 part, so every 5-day return is 1.01**5 - 1.
    prices = np.concatenate([np.full(100, 1.0), 2.0 * DAILY_GROWTH ** np.arange(100)])

    def two_part_history(ticker):
        history = fake_price_history(ticker)
        if ticker != "SPY":
            history["close"] = prices
            history["adj_close"] = prices
            history["close_as_traded"] = prices
        return history

    monkeypatch.setattr(event_study, "load_price_history", two_part_history)
    market_history = event_study.load_market_history()
    events = event_study.add_returns_and_price_tags(make_events([TRADING_DAYS[150]]), market_history)
    controls = event_study.draw_control_returns(events, market_history, 5)
    assert np.allclose(controls["raw"], DAILY_GROWTH**5 - 1, rtol=1e-5)


def test_remove_duplicate_events():
    calendar = pd.Series(pd.bdate_range("2020-01-01", "2020-03-31"))
    purchases = pd.DataFrame(
        {
            "accession_number": ["a1", "a2", "a3", "a4", "a5"],
            "owner_cik": ["FUND1", "FUND2", "EXEC", "EXEC", "EXEC"],
            "issuer_cik": ["FIRM"] * 5,
            "first_transaction_date": pd.to_datetime(["2020-01-06", "2020-01-06", "2020-02-03", "2020-02-05", "2020-02-14"]),
            "filing_date": pd.to_datetime(["2020-01-08", "2020-01-08", "2020-02-04", "2020-02-07", "2020-02-18"]),
            "shares_purchased": [5000.0, 5000.0, 100.0, 200.0, 300.0],
            "average_price": [20.0, 20.0, 30.0, 31.0, 29.0],
        }
    )
    events, dedup_log = event_study.remove_duplicate_events(purchases, calendar)
    # a2 is the same trade as a1 (related filer); a4 is 3 trading days after a3;
    # a5 is 10 trading days after a3 and is kept.
    assert sorted(events["accession_number"]) == ["a1", "a3", "a5"]
    assert dedup_log["events"].tolist() == [5, 4, 3]


def test_summarise_edge_known_numbers():
    event_returns = np.array([0.10, 0.20, np.nan])
    control_returns = np.full((3, 200), 0.05)
    dates = pd.to_datetime(["2020-01-10", "2020-02-10", "2020-03-10"])
    summary = summarise_edge(event_returns, control_returns, dates)
    assert summary["n"] == 2
    assert summary["edge"] == pytest.approx(0.10)
    assert summary["p_value"] == 0.0
    assert summary["first_half_edge"] == pytest.approx(0.05)
    assert summary["second_half_edge"] == pytest.approx(0.15)


def test_month_clustered_t_stat_averages_within_month_first():
    # Three events in January (mean 0.02) and one in each of two other months.
    values = np.array([0.01, 0.02, 0.03, 0.04, 0.00])
    dates = pd.to_datetime(["2020-01-02", "2020-01-15", "2020-01-30", "2020-02-10", "2020-03-10"])
    monthly_means = np.array([0.02, 0.04, 0.00])
    expected = monthly_means.mean() / (monthly_means.std(ddof=1) / np.sqrt(3))
    assert month_clustered_t_stat(values, dates) == pytest.approx(expected)


def make_h1_edge_table(edge, t_stat, n, first_half, second_half):
    rows = []
    for horizon in [20, 60]:
        rows.append(
            {
                "sample": "full", "cohort": "opportunistic", "return_type": "market_adjusted",
                "horizon": horizon, "n": n, "edge": edge, "t_stat": t_stat,
                "first_half_edge": first_half, "second_half_edge": second_half,
            }
        )
    return pd.DataFrame(rows)


def test_h1_verdict_pass_fail_underpowered():
    assert h1_verdict(make_h1_edge_table(0.006, 2.1, 500, 0.004, 0.008))[0] == "PASS"
    assert h1_verdict(make_h1_edge_table(0.004, 3.0, 500, 0.004, 0.004))[0] == "FAIL"
    assert h1_verdict(make_h1_edge_table(0.010, 3.0, 500, -0.001, 0.020))[0] == "FAIL"
    assert h1_verdict(make_h1_edge_table(0.010, 3.0, 200, 0.010, 0.010))[0] == "UNDERPOWERED"


def test_bad_print_screen_catches_snap_backs_but_not_real_moves():
    from load_prices import count_reverting_spikes

    bad_print = np.array([10.0, 10.0, 1000.0, 10.0, 10.0, 10.0, 10.0, 10.0])  # 100x for one day, then back
    real_crash = np.array([10.0, 10.0, 2.0, 1.8, 1.9, 1.7, 1.6, 1.5])  # -80% and stays down
    real_jump = np.array([2.0, 2.0, 9.0, 9.5, 10.0, 9.8, 10.2, 10.5])  # 4.5x and holds
    assert count_reverting_spikes(bad_print) >= 1
    assert count_reverting_spikes(real_crash) == 0
    assert count_reverting_spikes(real_jump) == 0


def test_h8_control_days_must_pass_h8_rules():
    from h8_tech import h8_entry_day_rule

    dates = pd.bdate_range("2009-01-01", "2016-12-30").to_numpy()
    n = len(dates)
    close = np.full(n, 20.0)
    close[-200:-150] = 3.0  # a stretch below $5
    arrays = {"dates": dates, "close": close, "close_as_traded": close, "volume": np.full(n, 1_000_000.0)}
    qualifies = h8_entry_day_rule(arrays)
    day_before = pd.to_datetime(dates[np.flatnonzero(qualifies) - 1])
    assert qualifies.any()
    assert (day_before >= pd.Timestamp("2013-01-01")).all()  # 2013 onward, and 3+ years after the 2009 listing
    assert not qualifies[-199:-149].any()  # days after a sub-$5 day do not qualify


def test_build_h8_tables_runs_on_fake_data(fake_prices, monkeypatch):
    import h8_tech

    # The fake series is only 200 days of 2020, so relax the H8 day rules for this test.
    monkeypatch.setattr(h8_tech, "H8_START_DATE", pd.Timestamp("2020-01-01"))
    monkeypatch.setattr(h8_tech, "H8_MIN_YEARS_OF_HISTORY", 0)
    monkeypatch.setattr(h8_tech, "H8_MIN_DOLLAR_VOLUME_USD", 0)
    build_h8_tables = h8_tech.build_h8_tables

    events = event_study.add_returns_and_price_tags(make_events(["2020-03-02", "2020-04-01", "2020-05-01"]), fake_prices)
    events["cohort"] = ["opportunistic", "routine", "unclassified"]
    events["sic_group"] = "software & IT services (7370-7379)"
    for tag in ["is_ceo_or_cfo", "is_large_purchase", "is_cluster_2day", "is_cluster_10day"]:
        events[tag] = [True, False, True]
    edge_table, secondary_table, robustness_table = build_h8_tables(events, fake_prices)
    assert set(edge_table["cohort"]) == {"all", "opportunistic", "software & IT services (7370-7379)"}
    assert set(edge_table["return_type"]) == {"raw", "market_adjusted", "qqq_adjusted"}
    assert (edge_table["n"] > 0).all()
    assert robustness_table["n"].gt(0).all()


def test_h10_entry_rule():
    from h10_filing_reaction import entry_point

    trading_days = pd.DatetimeIndex(pd.bdate_range("2024-05-06", "2024-05-17"))  # Mon 6 May .. Fri 17 May
    # Before the open -> that day's open
    assert entry_point(pd.Timestamp("2024-05-07 08:15"), trading_days) == (pd.Timestamp("2024-05-07"), "open")
    # During market hours -> that day's close
    assert entry_point(pd.Timestamp("2024-05-07 11:00"), trading_days) == (pd.Timestamp("2024-05-07"), "close")
    # After the close -> next trading day's open
    assert entry_point(pd.Timestamp("2024-05-07 17:12"), trading_days) == (pd.Timestamp("2024-05-08"), "open")
    # Friday evening -> Monday open (weekend skipped)
    assert entry_point(pd.Timestamp("2024-05-10 19:00"), trading_days) == (pd.Timestamp("2024-05-13"), "open")
    # Saturday -> Monday open
    assert entry_point(pd.Timestamp("2024-05-11 10:00"), trading_days) == (pd.Timestamp("2024-05-13"), "open")


def test_h10_window_returns_open_to_close():
    from h10_filing_reaction import overnight_gap, window_returns

    arrays = {
        "adj_open": np.array([10.0, 11.0, 12.0]), "adj_close": np.array([10.0, 11.5, 12.0]),
        "spy_adj_open": np.array([100.0, 100.0, 100.0]), "spy_adj_close": np.array([100.0, 101.0, 100.0]),
        "qqq_adj_open": np.array([50.0, 50.0, 50.0]), "qqq_adj_close": np.array([50.0, 50.0, 50.0]),
    }
    same_day = window_returns(arrays, 1, "open", 0)
    assert same_day["raw"] == pytest.approx(11.5 / 11.0 - 1)
    assert same_day["market_adjusted"] == pytest.approx((11.5 / 11.0 - 1) - 0.01)
    assert overnight_gap(arrays, 1) == pytest.approx(0.10)  # 10 -> 11 open, SPY flat overnight

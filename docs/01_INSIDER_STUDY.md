**Verdict: H1 PASSES the pre-registered bar at 60 days, but the edge is fragile and absent after 2013. H8 (established tech, buy the day after filing) FAILS. H10 (established tech, buy at the first open after the filing, hold 0–1 days) PASSES: +0.48pp same day and +0.69pp by the next close, t ≈ 3.**

# Insider Purchase Study: Results (Phase 2)

*26 September 2026. Every number cites the CSV it comes from, under `results/`. Research and educational use only; not investment advice.*

## 1. Bottom line

- **Insider buying across all US stocks** (H1, opportunistic insiders) beat random buy dates in the same stocks by **+1.00pp over 60 trading days** (t = 2.13). That clears all four pre-registered criteria, only just.
- **The pass does not survive scrutiny.**
  - The typical event *lagged* its random dates.
  - The edge comes from a minority of big winners concentrated in a few companies, and before 2013.
  - From 2013 onward there is no edge.
- **In established, liquid tech companies** (H8), insider buying showed **no timing edge** at any horizon, against SPY or QQQ.
- **The one robust pattern is company size.** Insider buys in the smallest companies beat those in the largest by +1.65pp over 60 days (t = 5.6, both halves positive). That is where the published literature says the edge lives, and it is the part of the market this strategy deliberately avoids.

**Practical conclusion:** holding established tech stocks for weeks after an insider buy has no edge (H8). The market's reaction to the filing is real and fast. Most of it happens overnight, but about +0.5pp is still available from the next open, over 1–2 days (H10). That short trade is the only insider signal worth building, and only after paper-trading it.

## 2. What was tested

- **Events** are open-market purchases (Form 4, code P, at least $10,000) filed 2006–2026. Each is bought at the close on the trading day after the filing date.
  - 95,894 purchases went through duplicate removal and a screen for bad Yahoo prices, leaving **74,564 events** (`phase2_event_study/dedup_counts.csv`).
- **Control:** for each event, 200 random buy dates in the same stock, drawn only from days that pass the same price rules as the events. **Edge** = mean event return − mean control return.
- **Deciding return:** stock return minus SPY (market-adjusted). Raw returns and returns minus QQQ are reported alongside.
- **Pass bar (fixed in advance):**
  - At 20 or 60 days: edge ≥ +0.5pp, month-clustered t ≥ 2.0, positive in both halves of the sample, and at least 300 events.
  - Secondary tests need t ≥ 2.5 and a positive result in both halves.

## 3. H1: opportunistic insiders, all stocks (`phase2_event_study/h1_criteria.csv`)

| Horizon | Events | Edge | t | First half | Second half | Result |
|---|---|---|---|---|---|---|
| 20 days | 5,839 | +0.26pp | 1.91 | +0.64pp | −0.13pp | fail |
| 60 days | 5,839 | **+1.00pp** | **2.13** | +1.59pp | +0.42pp | **pass** |

### Why the pass is fragile

From `phase2_event_study/robustness_checks.csv` (opportunistic, 60 days, market-adjusted):

- **Median edge: −0.55pp.** Only **48.0%** of events beat their own random dates.
- **1%-trimmed edge: +0.43pp, t = 1.33.** Without the most extreme 1% of events at each end, the result falls below the bar.
- **The top 10 companies supply 53% of the total edge.** Excluding them, the edge is +0.48pp.

### No edge in the modern era

From `phase2_event_study/edge_table.csv`, sample `2013_onward`, which was fixed before any results:

- 60 days: **+0.24pp, t = 0.35**, with the second half negative.
- 20 days: +0.05pp, t = 0.82.

### The routine vs opportunistic split did not add anything

Also from `edge_table.csv` (full sample, 60 days):

- **Routine insiders (H2):** +0.11pp, t = −0.44. No edge, as expected.
- **Opportunistic insiders:** +1.00pp.
- **Unclassified insiders:** +1.43pp (t = 2.97).
- **All events:** +1.33pp (t = 2.92).

The paper's classification did not isolate a better group here.

### Raw returns tell the same story

Opportunistic, 60 days, raw: +2.55pp, t = 2.98 (`edge_table.csv`). The larger number includes market moves that the market-adjusted version removes.

## 4. Secondary tests H3–H7 (`phase2_event_study/secondary_tests.csv`)

Market-adjusted findings (t ≥ 2.5 and positive in both halves):

- **H7, smallest vs largest companies by trading volume:**

  | Horizon | Difference | t |
  |---|---|---|
  | 5 days | +0.64pp | 5.53 |
  | 20 days | +1.13pp | 4.90 |
  | 60 days | +1.65pp | 5.64 |
  | 120 days | +3.69pp | 7.26 |

  This is the strongest and most consistent result in the study.
- **H3, CEO/CFO buyers vs other insiders:** +1.44pp at 120 days (t = 2.99). Not significant at 20 or 60 days.
- **H5a/H5b, cluster buys:** +0.27pp and +0.35pp at 5 days (t = 3.61 and 2.94). The effect is gone by 20 days.
- **H4 (large purchases) and H6 (buying after a drop):** no findings.

## 5. H8: established tech, 2013 onward (`phase2_h8_tech/`)

**Universe:** tech industry codes, Magnificent 7 included, as-traded price ≥ $5, ≥ $10M a day traded, ≥ 3 years listed, and no bad-print tickers. That leaves **1,125 events at 221 companies** (`h8_event_counts.csv`). The signal is all insider purchases. The rules were fixed in `project.md` v3 before any H8 returns were computed, and the test was run once.

From `h8_criteria.csv`:

| Horizon | Events | Edge | t | First half | Second half | Result |
|---|---|---|---|---|---|---|
| 20 days | 1,125 | +0.23pp | −0.41 | +0.87pp | −0.40pp | fail |
| 60 days | 1,125 | −0.22pp | −0.24 | +1.46pp | −1.90pp | fail |

- **Against QQQ:** 60 days −0.24pp, t = −0.35 (`h8_edge_table.csv`).
- **Robustness at 60 days:** median −0.53pp; 48.5% of events beat their random dates (`h8_robustness_checks.csv`). It is not a hidden edge in the median; there is no edge.
- **By industry at 60 days** (`h8_edge_table.csv`):
  - Semiconductors: +1.34pp, t = 0.28
  - Software and IT services: −0.66pp, t = 0.06
  - Hardware and other tech: −0.45pp, t = −0.64
- **Breakdowns** (`h8_breakdown_tests.csv`): no finding. The closest was CEO/CFO buyers at 60 days, +2.58pp versus other insiders with t = 2.17, below the 2.5 bar.

**Note on the robustness file:** when the total edge is close to zero, the "share of edge from the top 10 companies" columns in `h8_robustness_checks.csv` are meaningless ratios (for example 3.57 or −67). Ignore them for H8.

## 5b. H10: the filing reaction, from the first realistic entry (`phase2_h10_filing_reaction/`)

**Why:** an exploratory check (`phase2_exploratory_short_horizons/short_horizon_edges.csv`) showed established-tech stocks beat their usual day by +1.6pp between the filing-date close and H8's entry. H10 (`project.md` v4) asks how much of that is left for someone who buys at the first open after the filing.

**Setup:**
- **Events:** the same 1,125 H8 events.
- **Public time:** the accepted time on each filing's EDGAR index page, in Eastern time. The SEC API's timestamps mixed UTC and Eastern, so they were not used.
- **Entry types:** 998 filings were accepted outside market hours and are bought at the next open. 127 were accepted during market hours and are bought at that day's close (`h10_event_counts.csv`).

**Result: PASS** (`h10_criteria.csv`, market-adjusted):

| Window | Events | Edge | t | First half | Second half |
|---|---|---|---|---|---|
| Open → same-day close (open entries) | 998 | **+0.48pp** | 3.01 | +0.61pp | +0.35pp |
| Entry → next-day close (all) | 1,125 | **+0.69pp** | 3.05 | +0.54pp | +0.84pp |

**Supporting numbers** (`h10_edge_table.csv`, `h10_robustness_checks.csv`):
- **Overnight gap, previous close → entry open:** +1.33pp (t = 12.5), and 84% of events beat their random days. **About 70% of the reaction happens before a regular-hours buyer can act.**
- **Exits 3 and 5 days after entry:** +0.74pp and +0.70pp, with t below 2. The edge stops growing after about a day.
- **Against QQQ:** +0.47pp (same day) and +0.70pp (next day).
- **Robustness:**
  - 1%-trimmed edge: +0.43pp (t = 3.49) same day; +0.67pp (t = 3.14) next day.
  - Median: +0.23pp and +0.36pp. Events beating their random days: 55% and 56%.
  - **Concentration:** the top 10 companies supply 64–67% of the edge (largest, MDRX, 13–16%). Excluding them, the edge is +0.20pp same day and +0.26pp next day.

**Caveats:**
- H10 was defined after the exploratory look at the filing-day reaction, although the open-to-close window itself was not examined before the bar was set.
- The edge is uneven across companies.
- Execution assumes a market-on-open buy and a sell at the close. A Roth IRA is a cash account, so check the broker's settled-cash rules.
- **Next step:** paper-trade every signal live before real money (Phase 4 logic).

## 6. Caveats

- **Survivor bias.** Yahoo has no prices for 55.1% of purchases, mostly companies that have since delisted (`phase1_filters/row_counts.csv`). The share is 71.8% in 2006–2012 and 28.8% in 2020–2026 (`phase1_filters/price_match_by_year.csv`).
  - Missing failed companies tends to *inflate* results.
  - That makes the H1 pass less trustworthy, and a real H8 edge more likely to be even smaller than measured.
- **Two earlier runs were invalid and are kept on record:**
  - `phase2_invalid_first_run/`: random dates were drawn from sub-$2 bad prints.
  - `phase2_before_bad_print_screen/`: one ticker, BKGM, supplied about 28% of the edge through bad prices.
  - Both fixes are logged in `project.md` Section 12.
- **H8 was defined after H1 results were seen.** A pass would have been weak evidence. A fail is still informative.

## 7. What this means for a buying strategy

- **Do not use insider buying as a timing signal for established tech names.** In this data it did no better than buying on a random day in the same stocks.
- **The edge that exists sits in small, less-watched companies (H7)**, which Hunter has chosen not to trade. Reaching for it would mean relaxing the junk filters. The junk, bad data and survivor bias found in this study all concentrate there, so that is not recommended without a better data source that includes delisted companies.
- **H9 (the Piotroski F-score split) is still pre-registered** and could be run on the H1 events as planned. On these results, the most it could add is a column in an alert tool that has no core edge to support. Whether to run it is Hunter's call.

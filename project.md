# Insider Purchase Signal: Project Plan

**Owner:** Hunter
**Status:** Phase 1 (code written; full run and spot-check pending)
**Last updated:** 26 September 2026 (v2: prior-evidence review added; see Section 11 changelog)

---

## 0. Read this first (instructions for Claude Code)

This file is the source of truth for the project. Follow it literally. When something is ambiguous, **stop and ask**; do not guess and build.

Working rules:

1. **Plan before code.** At the start of each phase, write a short plan (the files you will create, what each function does, what it outputs) and wait for approval.
2. **One phase at a time.** Finish a phase, report results, and stop. Do not start the next phase without a "go."
3. **Code only what this plan asks for.**
   - No speculative features, no "while I'm here" extras.
   - No frameworks, plugin systems, config layers, abstract base classes or class hierarchies.
   - Plain functions and pandas.
4. **I must be able to read every line.**
   - Keep each file under ~300 lines.
   - Open every file with a 2–3 line comment saying what it does.
   - Use descriptive names and no clever one-liners.
5. **No new dependencies without asking.** Allowed from the start: `pandas`, `numpy`, `scipy`, `requests`, `yfinance`, `pyarrow`, `pytest`.
6. **No machine learning models.** This is an event study: averages, differences and t-statistics.
7. **Do not tune thresholds after seeing results.**
   - Every threshold in Section 5 is fixed now.
   - If a result tempts you to change one, report it and ask; do not change it.
8. **Every number in a write-up must trace to a CSV** in `results/`. Name the file next to the number.
9. **Be adversarial.** A clean negative result is a success. Do not soften findings or go hunting for a variant that "works."
10. **Explain as you go.** After each step, say in two or three plain sentences what it did and what came out.
11. **Never commit** downloaded raw data, API keys, or anything under `data/raw/`.

---

## 1. Objective

Answer one question, with a pre-committed pass/fail bar:

> **Do opportunistic open-market insider purchases, acted on the day after they become public, earn more over the next 20–60 trading days than randomly timed purchases of the same stocks?**

If yes, build a small daily alert tool and paper/real-trade it in a Roth individual retirement account (IRA). If no, write it up as a dead end and stop.

---

## 2. Motivation

This project follows an earlier one (repo `huntersarnelli/Service_NOW_analysis`) that tested dip-buying on US large caps. What it found:

- **Dip timing has a real but tiny edge.** Across 17,235 dip events on 124 names (2015–2026), dip entries beat random entries on the same names by +0.16pp at 5 days, +0.34pp at 20 days and +0.40pp at 60 days. By 120 days the edge is zero. (`Service_NOW_analysis/docs/02_OVERREACTION_STUDY.md`)
- **No sell or exit rule survived a control.** The same repo tested eleven exit and sizing ideas; all failed. (`Service_NOW_analysis/docs/DEAD_ENDS.md`)
- **Company-specific news drifts; market-driven dips revert.** This is consistent with Chan (2003), *Stock Price Reaction to News and No-News*.

The natural next question is whether any **information source** carries more edge than price patterns. Two candidates were set aside:

- **"Attention" signals point the wrong way.** Barber & Odean (2008), *All That Glitters*, found retail investors are net buyers of attention-grabbing stocks, which then underperform.
- **Tracking congressional trades is weak.** Eggers & Hainmueller (2013), *Capitol Losses*, found congressional portfolios lagged the market. Disclosures can also arrive up to 45 days after the trade under the STOCK Act (Stop Trading on Congressional Knowledge Act).

Corporate insider purchases have the strongest published evidence of the alternatives:

- **Cohen, Malloy & Pomorski (2012), *Decoding Inside Information*, Journal of Finance 67(3).** They split insider trades into *routine* trades, which recur in the same calendar month year after year, and *opportunistic* trades, which are everything else. Opportunistic trades predicted future returns and news; routine trades did not.
- **Why this is worth testing:**
  - The data is free and public.
  - Filings arrive within two business days of the trade.
  - The claimed effect lives at a 1–6 month horizon, which fits a short-to-medium holding period.

**Calibrate expectations.** McLean & Pontiff (2016), *Does Academic Research Destroy Stock Return Predictability?*, found published anomalies lose roughly half their return after publication. Assume the edge today is smaller than in the paper.

### 2.1 Prior evidence (review of 26 September 2026)

Published magnitudes, as summarised in IBKR Campus, *What Corporate Insider Buying Can Tell Investors* (link in Section 10). **These are secondhand. Confirm any figure against the original paper before quoting it in a write-up.**

| Paper | Finding | Relevance here |
|---|---|---|
| Cohen, Malloy & Pomorski (2012), *Journal of Finance* | Opportunistic trades earned ≈ **0.82% per month** abnormal return; routine trades ≈ **0** | H1 and H2 |
| Alldredge & Blank (2019), *Journal of Financial Research* 42(2) | Purchases clustered **within 2 days** earned ≈ **2.1% per month**, ≈ 0.9pp more than isolated purchases | H5; adds a 2-day cluster window |
| Jeng, Metrick & Zeckhauser (2003), *Review of Economics and Statistics* | Insider purchase portfolios earned ≈ 37–47 basis points per month; sales earned no significant abnormal return. About 1/6 of the return came within 5 days, 1/3 within a month, 3/4 within 6 months | Supports the 20–120 day horizons and ignoring sales |
| Lakonishok & Lee (2001), *Review of Financial Studies* | Predictive power strongest in smaller firms | H7 size split |
| Piotroski & Roulstone (2005), *Journal of Accounting and Economics* | Insiders buy after price declines, and those purchases still predict better future earnings | H6 (buying after a drop) |

**Why our numbers should come in below these:**

1. **Filing lag.** Most of these studies measure from the *trade* date. Before the Sarbanes-Oxley Act of 2002, a Form 4 could be filed as late as the 10th of the following month, so part of the measured return was never available to someone following filings. This study enters after the *filing* date (Section 6.1), which is correct and will give smaller numbers.
2. **Post-publication decay** (McLean & Pontiff, above).
3. **Survivorship bias** runs the other way: missing delisted tickers inflates results (Section 5.3).

A result close to the paper magnitudes should be treated as **suspicious**, not confirming. Check for lookahead before believing it.

### 2.2 Existing tools (for reference, not dependencies)

- **OpenInsider** (http://openinsider.com/). A free Form 4 screener with preset lists (Latest Cluster Buys, Officer Purchases $25k+, CEO/CFO Purchases $25k+) and filters for title, trade value, ownership change %, price and filing delay.
  - It has no API or export, its screener looks back only 4 years, and it blocks automated fetches.
  - **Do not scrape it or build on it.** Use it only as a manual cross-check in Phase 1 (Section 7).
  - Its 1-day / 1-week / 1-month / 6-month return columns are raw returns with no control. They are not evidence.
- **mrshu/openinsider-notifier** (https://github.com/mrshu/openinsider-notifier). An open-source scanner that parses SEC Form 4 XML directly, enriches it with Yahoo Finance prices, and includes a forward-return backtest.
  - It is useful as a **reference** for parsing Form 4 XML in Phase 3.
  - Check its license before copying any code; do not add it as a dependency.
- **Commentary with no backtest behind it.** Setup4Alpha, *Market Edges in 2026, Part 2*, recommends cluster buys as a "shortlist generator" but gives no performance numbers. Treat it as framing, not evidence.

---

## 3. Hypotheses (pre-registered)

**Primary test (this alone decides pass/fail):**

- **H1.** Opportunistic purchases beat a random-date control on the same tickers at 20 and 60 trading days.

**Secondary tests (exploratory; they cannot rescue a failed H1):**

- **H2.** Routine purchases show no edge over the control. This is a sanity check: if routine trades look as good as opportunistic ones, the classification isn't doing anything.
- **H3.** Purchases by the chief executive officer (CEO) or chief financial officer (CFO) beat purchases by other insiders.
- **H4.** Large purchases, at least 10% of the insider's prior holding, beat small ones.
- **H5.** Cluster purchases beat single-insider purchases. Test two windows, both fixed now:
  - **H5a:** two or more distinct insiders at the same company buying within **2 trading days**. This matches Alldredge & Blank (2019).
  - **H5b:** three or more distinct insiders at the same company within **10 calendar days**.
  - The event date for a cluster is the filing date of the filing that completes the cluster.
- **H6.** Purchases made after a price drop, with Z(20) ≤ −1.2 on the filing date, beat others. Here Z(20) = (close − 20-day mean close) / 20-day standard deviation of close. This ties back to the dip study.
- **H7.** The effect is larger in smaller companies (see the size split in Section 6.5).

**Investable-universe test (added in v3, after the first H1 results; see Section 11):**

- **H8 (tech).** Open-market insider purchases in established technology stocks beat a random-date control on the same tickers at 20 or 60 trading days. This is the strategy Hunter would actually trade: real, seasoned tech/AI companies, large caps included, with pop-up junk (shells, pump-and-dumps, fresh listings) kept out. All rules below are fixed before any H8 returns are computed.
  - **Signal:** every open-market purchase event after Phase 1 filters and duplicate removal (all cohorts). Opportunistic-only is reported alongside but does not decide.
  - **Universe:** issuer SEC SIC code in 3570–3579 (computers and office equipment), 3661, 3663, 3669 (communications equipment), 3670–3679 (electronic components, incl. 3674 semiconductors), 3825, 3827 (electronic test and optical instruments), 7370–7379 (software, data processing, IT services, internet). Known gap: SIC 3559 (special industry machinery, e.g. some semiconductor equipment makers) is left out because it is mostly non-tech.
  - **Large caps included** (the Magnificent 7 are in). Note: Amazon (SIC 5961, retail) and Tesla (SIC 3711, autos) fall outside the tech codes.
  - **Filters on the event:** filed 2013-01-01 or later; as-traded close on the filing date ≥ **$5**; 20-day average dollar volume before the filing ≥ **$10M/day**; at least **3 years** of price history before the filing date (seasoned companies only).
  - **Control:** as Section 6.4, but a random entry day must also meet the event rules on that day: on or after 2013-01-01, as-traded close ≥ $5, 20-day average dollar volume ≥ $10M/day, and at least 3 years of price history before it.
  - **Returns:** market-adjusted vs SPY decides. Also reported: raw, and adjusted vs QQQ (the Nasdaq-100 fund, Hunter's realistic alternative).
  - **Breakdowns (reported, never decisive):** H3–H6 tags, opportunistic-only, and each SIC group.
- **H9 (financial health, Piotroski F-score).** Among insider-purchase events, those at companies with a high F-score (**F ≥ 7**) beat those with a low F-score (**F ≤ 3**). Tests Hunter's idea that an insider buying into a healthy company is a different bet from one propping up a struggling one. **Run only after H8 has been run.** Rules fixed now, before any financial data is built:
  - **Score:** Piotroski (2000)'s nine binary signals, exactly as in the paper (confirm each definition against the paper before coding, as for Section 6.2): (1) ROA > 0, (2) operating cash flow > 0, (3) ROA up vs prior year, (4) operating cash flow > net income (accruals), (5) long-term debt / average assets down, (6) current ratio up, (7) no common equity issued in the prior year, (8) gross margin up, (9) asset turnover up. No adjustments for tech or any industry.
  - **Cutoffs:** the paper compares 8–9 with 0–1; this study uses **≥ 7 vs ≤ 3** to keep enough events in each group. Fixed now.
  - **Point-in-time data:** SEC Financial Statement Data Sets (quarterly zips, 2009q1 onward, https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets). For each event, use only annual reports (10-K) **filed before the event's filing date**: the latest one and the one before it. An event is scored only if all nine signals can be computed; unscored events are excluded from H9 and counted.
  - **Samples:** all H1 events (primary, where the F-score fits best), with the H8 tech universe reported alongside.
  - **Bar:** like H3–H7: t ≥ 2.5 on the monthly (high-F edge − low-F edge) and a positive difference in both halves, at 20 or 60 days, market-adjusted. H9 cannot unlock Phase 3 by itself; if it is a finding, the F-score becomes a column in the Phase 3 alerts.
- **H10 (filing reaction, v4).** An exploratory look after the verdicts found that H8 tech stocks beat their usual day by +1.6pp between the filing-date close and our entry close (`results/phase2_exploratory_short_horizons/short_horizon_edges.csv`), which is before our entry. H10 asks **how much of that move is still available to someone who acts at the first realistic moment.** Rules fixed before any timestamps or opening prices were downloaded:
  - **Events:** the H8 events (established tech, 2013 onward).
  - **Public time:** the "Accepted" time on each filing's EDGAR index page, which is Eastern time. Corrected before any H10 returns were computed: the submissions API's `acceptanceDateTime` turned out to be inconsistent. It was UTC for 10 of 11 spot-checked filings but Eastern for others, and one filing appeared with both 17:11 and 21:11.
  - **Entry:**
    - Accepted before 9:30 ET on a trading day: that day's **open**.
    - Accepted 9:30–16:00 ET on a trading day: that day's **close** (conservative; no free intraday prices).
    - Accepted after 16:00 ET, or on a non-trading day: the **next trading day's open**.
  - **Exits:** the close 0, 1, 3 and 5 trading days after the entry day. Exit 0 applies to open entries only.
  - **Returns:** built from Yahoo open and close, adjusted with the same factor as the adjusted close. Market-adjusted (minus SPY over the same open/close window) decides. Raw and QQQ-adjusted are also reported.
  - **Control:** 200 random days in the same ticker passing the H8 day rules, with the same entry type (open or close) and the same exits.
  - **Pass bar:** at exit 0 (open entries) **or** exit 1 (all events): edge ≥ **+0.3pp**, t ≥ 2.0, positive in both halves, n ≥ 300. The bar is lower than H1's because each trade lasts 1–2 days and costs about 0.05% for liquid tech.
  - **Reported, never deciding:** the overnight gap (previous close to the entry open) for open entries, i.e. what someone who can't trade after hours misses.
  - **Stopping rule:** if H10 fails, the insider-signal line of this project ends. No H11.
- **Price-data screen (applies to H1 and H8).** A ticker is excluded if its adjusted close ever moves ≥ 4x up or ≤ 75% down in one day and then returns to within 50% of the pre-move price within 5 trading days. This signature is a bad print, not a real move.

---

## 4. Success and kill criteria (fixed now; do not change)

H1 **passes** only if **all** of these hold at the 20-day **or** 60-day horizon:

| Criterion | Threshold |
|---|---|
| Edge (mean event return minus mean control return) | ≥ **+0.5 percentage points** |
| Month-clustered t-statistic | ≥ **2.0** |
| Split-half stability | Edge positive in **both** halves of the sample |
| Sample size | ≥ **300** opportunistic events after all filters |

If any criterion fails, H1 is dead:

- Record it in `docs/DEAD_ENDS.md` with the numbers.
- Do not build Phase 3.
- If the sample is under 300 events, the result is **"underpowered,"** not "pass."

A secondary hypothesis (H3, H4, H5a, H5b, H6, H7) counts as a finding only with t ≥ 2.5 **and** a positive edge in both halves. The higher bar allows for testing six of them.

**H8** uses the same four criteria as H1 (edge ≥ +0.5pp, t ≥ 2.0, positive in both halves, n ≥ 300 events), on the H8 universe and signal. H8 was defined after H1 results were seen, so a pass is weaker evidence than a clean pre-registration. **Phase 3 may be built if H1 or H8 passes; real money only after Phase 4 paper trading agrees.** H1's verdict is recorded as-is either way. The H8 tech test is run **once**; no further universe or filter changes after its results.

---

## 5. Data

### 5.1 Insider filings

- **Source:** SEC (Securities and Exchange Commission) Insider Transactions Data Sets. These are quarterly structured extracts of all Form 3, 4 and 5 filings.
  - Page: https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets
  - Field definitions: https://www.sec.gov/files/insider_transactions_readme.pdf. **Read this before writing the loader.** Table and column names must come from the readme, not from memory.
- **Use every available quarter.** Confirm the first available year from the page.
- **SEC fair-access rules:**
  - Send a `User-Agent` header with a name and email address.
  - Stay under 10 requests per second.
  - Cache every download in `data/raw/` and never re-download a file that already exists.

### 5.2 Filters (apply in this order; log the row count after each step)

1. Form type 4, including amendments only if the readme says how to de-duplicate them.
2. Non-derivative transactions only (common stock).
3. Transaction code **P**, an open-market purchase. Drop everything else: grants, option exercises, gifts, sales.
4. Drop transactions flagged as made under a Rule 10b5-1 trading plan, where the filing records it. These are pre-scheduled and carry no timing information. The flag exists on filings from 2023 onward; earlier rows keep an "unknown" flag.
5. Drop purchases under $10,000.
6. Drop tickers with a price below $2 on the filing date (penny stocks).
7. Keep only tickers that can be matched to price data. **Report the number and share dropped.**

### 5.3 Prices

- `yfinance` daily adjusted closes for each ticker, plus SPY (the exchange-traded fund, or ETF, that tracks the S&P 500) as a market benchmark.
- **Known bias:** `yfinance` lacks most delisted tickers, so the sample tilts toward survivors. Report how many events were lost to missing prices. If more than 20% are lost, flag it prominently in the write-up; it could inflate results.

---

## 6. Method

### 6.1 Event definition

- **Event date = filing date**, not transaction date. The filing date is the first day the public could act.
- **Entry = close on the first trading day after the filing date.** Filings often arrive after the market closes, so a same-day entry would be lookahead.
- If one insider files several purchases in the same company within 5 trading days, keep only the first. This stops one person from being counted many times.

### 6.2 Routine vs opportunistic

Follow Cohen, Malloy & Pomorski (2012), Section II. **Confirm the exact rule against the paper before coding it.** As commonly stated:

- An insider is **classifiable** in year *t* if they traded in each of the three prior calendar years.
- A classifiable insider is **routine** if they traded in the **same calendar month** in each of those three years.
- A classifiable insider who is not routine is **opportunistic**.
- Everyone else is **unclassified**. Keep unclassified insiders as their own cohort and report them, but they are not part of H1.

Unit-test this classification with a handful of hand-built insider histories.

### 6.3 Returns

- Horizons: **5, 20, 60, 120 trading days** from the entry close.
- Report two returns:
  - **Raw return:** close(entry + h) / close(entry) − 1.
  - **Market-adjusted return:** raw return minus SPY's return over the same days.
- If the price series ends before entry + h, drop the event for that horizon only.

### 6.4 Control: random-date null

This is the most important part of the study.

- For each event, draw a random trading date **for the same ticker** from the period where it has price data. Compute its return at each horizon the same way.
- Repeat for **200 draws**.
- **Edge** = mean event return − mean control return.
- **Empirical p-value** = share of the 200 draws whose control mean is at least the event mean.

### 6.5 Statistics

- **Month-clustered t-statistic.** Events cluster in time, so a naive t-test overstates significance. Instead:
  1. Compute each event's (event return − its matched control return).
  2. Average those by calendar month of the event.
  3. t-test the monthly means.
- **Split-half.** Split events at the median event date and report the edge separately for each half.
- **Size split for H7.** Use the 20-day average dollar volume before the event (price × volume) as a size proxy, because free historical market cap is unreliable. Split into terciles and report the edge per tercile.

### 6.6 Outputs

Save each table as a CSV in `results/<phase>_<name>/`:

- Row counts after every filter.
- Event counts by year and cohort.
- The edge table: cohort × horizon, with columns n, mean event, mean control, edge, t-statistic, p-value, first-half edge and second-half edge.

---

## 7. Phases and deliverables

Each phase ends with a short report to Hunter and a stop.

### Phase 1: Data pipeline

- `src/load_filings.py`: download, cache and parse the SEC data sets, then apply the Section 5.2 filters. Output: `data/processed/purchases.parquet`.
- `src/load_prices.py`: fetch and cache prices for every ticker, plus SPY.
- **Done when** all three are finished:
  - The filter-by-filter row-count table is printed and saved.
  - Hunter has spot-checked 10 random purchases against the original filings on EDGAR (Electronic Data Gathering, Analysis, and Retrieval, the SEC's filing system).
  - Hunter has spot-checked 10 recent purchases (last 3 months) against OpenInsider: same ticker, insider title, share count and dollar value. Any mismatch gets explained before Phase 2 starts.

### Phase 2: Event study

- `src/classify.py`: routine / opportunistic / unclassified labels, plus the H3–H6 tags. Includes unit tests.
- `src/event_study.py`: returns, random-date control, t-statistics, split halves.
- `run_study.py`: one script that produces every CSV in `results/`.
- `docs/01_INSIDER_STUDY.md`: the write-up.
  - Lead with a pass/fail verdict on H1 against Section 4.
  - Then the edge table and the secondary findings.
  - Cite a CSV for every number.
- **Done when:** the write-up exists and the verdict is stated in its first line.

### Phase 3: Daily alert tool (**only if H1 or H8 passes**; see Section 4)

- `src/daily_alerts.py`: pull the latest Form 4 filings from EDGAR, apply the rules that survived, and print or save a short list.
- Each alert shows:
  - ticker, insider name and role
  - dollar amount, and percent of the insider's prior holding
  - routine / opportunistic label, and whether it is a cluster purchase
  - days to next earnings, if available
  - Z(20) on the filing date
- No automated trading. No web dashboard unless Hunter asks for one later.

### Phase 4: Live log (only if Phase 3 exists)

- `trade_log.csv` columns: date, ticker, signal details, acted (yes/no), entry price, exit date, exit price.
- **Every signal gets logged, including the ones skipped.**
- **Rules:**
  - Fixed dollar amount per signal.
  - Exit at the horizon Phase 2 identified. No discretionary exits.
- After six months, compare live results with the backtest edge.

---

## 8. Repo layout (target; do not add folders beyond this without asking)

Updated 26 Sep 2026 (Hunter approved): Jupyter notebooks coordinate each phase; shared helpers live in `src/utils.py`.

```
project.md            ← this file
README.md             ← 10 lines: what this is, how to run
requirements.txt
run_study.py
notebooks/
  01_data_pipeline.ipynb  ← Phase 1 coordinator: calls src/ functions, shows each step
  02_event_study.ipynb    ← Phase 2 coordinator (run_study.py runs the same steps)
src/
  utils.py            ← shared helpers: paths, cached SEC download, row-count logging
  load_filings.py
  load_prices.py
  classify.py
  event_study.py
  edge_stats.py       ← t-statistics, p-values, split halves, H1 verdict (split out to keep files < 300 lines)
  load_industry.py    ← SEC industry (SIC) codes per company; H8 tech universe (v3)
  daily_alerts.py     ← Phase 3 only
tests/
  test_classify.py
  test_event_study.py
data/
  raw/                ← gitignored
  processed/          ← gitignored
results/              ← CSVs, gitignored (regenerate with run_study.py)
docs/
  01_INSIDER_STUDY.md
  DEAD_ENDS.md
```

---

## 9. Out of scope (do not build)

- Selling or shorting on insider **sales**. Sales are mostly for diversification or liquidity and carry far less information. A possible later study, not this one.
- Machine learning or large language model (LLM) scoring of filings or news.
- Options, leverage, position-sizing models.
- Congressional trades, 13F filings (quarterly holdings reports from large institutional managers), social media sentiment.
- Scraping OpenInsider or any other third-party site. The SEC is the only data source for filings.
- A graphical interface, before Phase 3 passes.

---

## 10. References

- Cohen, L., Malloy, C., & Pomorski, L. (2012). Decoding Inside Information. *Journal of Finance*, 67(3). The core method: routine vs opportunistic classification.
- Barber, B. M., & Odean, T. (2008). All That Glitters: The Effect of Attention and News on the Buying Behavior of Individual and Institutional Investors. *Review of Financial Studies*, 21(2). Why attention-based buying was ruled out.
- Eggers, A. C., & Hainmueller, J. (2013). Capitol Losses: The Mediocre Performance of Congressional Stock Portfolios. *Journal of Politics*, 75(2). Why congressional trade tracking was ruled out.
- Chan, W. S. (2003). Stock Price Reaction to News and No-News: Drift and Reversal After Headlines. *Journal of Financial Economics*, 70(2). The news-drifts / no-news-reverts result reproduced in the prior repo.
- McLean, R. D., & Pontiff, J. (2016). Does Academic Research Destroy Stock Return Predictability? *Journal of Finance*, 71(1). Expect post-publication decay.
- Piotroski, J. D. (2000). Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers. *Journal of Accounting Research*, 38 (Supplement). The nine-signal F-score used in H9. Its headline ~23% a year is a long-short spread within high book-to-market stocks (1976–1996), strongest in small, illiquid firms.
- SEC, Financial Statement Data Sets (XBRL, 2009 onward): https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets
- Alldredge, D., & Blank, B. (2019). Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading. *Journal of Financial Research*, 42(2), 331–360. https://onlinelibrary.wiley.com/doi/abs/10.1111/jfir.12172. Source for H5a.
- Jeng, L. A., Metrick, A., & Zeckhauser, R. (2003). Estimating the Returns to Insider Trading: A Performance-Evaluation Perspective. *Review of Economics and Statistics*, 85(2). Purchases informative, sales not; timing of returns.
- Lakonishok, J., & Lee, I. (2001). Are Insider Trades Informative? *Review of Financial Studies*, 14(1). Stronger effect in small firms.
- Piotroski, J. D., & Roulstone, D. T. (2005). Do Insider Trades Reflect Both Contrarian Beliefs and Superior Knowledge About Future Cash Flow Realizations? *Journal of Accounting and Economics*, 39(1). Insiders buy after declines.
- IBKR Campus, *What Corporate Insider Buying Can Tell Investors: Evidence from Academic Research*. Secondhand summary used for the Section 2.1 figures: https://ibkrcampus.com/campus/traders-insight/securities/stocks/what-corporate-insider-buying-can-tell-investors-evidence-from-academic-research/
- OpenInsider: http://openinsider.com/
- mrshu/openinsider-notifier: https://github.com/mrshu/openinsider-notifier
- Setup4Alpha, *Market Edges in 2026, Part 2*: https://setup4alpha.substack.com/p/free-alternative-data-edges
- SEC, Insider Transactions Data Sets: https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets
- SEC, Insider Transactions Data Sets readme (field definitions): https://www.sec.gov/files/insider_transactions_readme.pdf
- SEC, Final Rule 33-11138, Insider Trading Arrangements and Related Disclosures (2022). Adds the Rule 10b5-1 plan checkbox to Form 4: https://www.sec.gov/files/rules/final/2022/33-11138.pdf

---

## 11. Changelog

- **v1 (26 Sep 2026):** initial plan.
- **v2 (26 Sep 2026), after the prior-evidence review.** All changes were made before any data was seen.
  - Added Section 2.1 (published magnitudes and why ours should be lower) and Section 2.2 (existing tools).
  - Split H5 into H5a (2-trading-day cluster, per Alldredge & Blank 2019) and H5b (10-calendar-day cluster). Secondary tests go from five to six.
  - Added the OpenInsider spot-check to the Phase 1 done criteria.
  - Added "no scraping third-party sites" to Section 9.
  - **Unchanged:** the H1 pass/fail bar, horizons, control design and Phase 3 gate.
- **v3 (26 Sep 2026), after the first valid H1 run.** Made after seeing H1 results; H8 returns not yet computed.
  - Why: H1's 60-day "pass" depended on a few tickers, one (BKGM) through bad Yahoo prices. Hunter's goal is to trade established tech/AI stocks (large caps welcome), not microcaps, biotech or pop-up junk.
  - Revised the same day, before any H8 returns: mega-caps put back in (their exclusion was a misreading of Hunter's intent); added the 3-year seasoning rule.
  - Added H9 (Piotroski F-score split), defined before any financial-statement data was downloaded. Kept out of H8 on purpose: several F-score signals penalise typical tech firms (stock-based share issuance, R&D-driven losses), and stacking it onto H8 would shrink the sample below useful size. Order: H8 runs first, once; H9 after.
  - Added the price-data screen (bad-print spikes) for H1 and H8.
  - Added H8 (tech), its pass rule, and "Phase 3 if H1 or H8 passes"; real money only after Phase 4 agrees.
  - **Unchanged:** H1's definition and pass bar, horizons, control design for H1.

---

- **v4 (26 Sep 2026), after H1 and H8 verdicts.** Added H10 (filing reaction) because an exploratory short-window check showed the insider-buy reaction happens before our entry. H10 is scoped to measure whether that reaction is tradable; it has its own pass bar and a stopping rule. Defined before any timestamps or opening prices were downloaded.

---

## 12. Decisions log

Choices made where this plan was ambiguous. Each was asked and approved before coding.

| Date | Topic | Decision |
|---|---|---|
| 26 Sep 2026 | Structure | Notebooks coordinate; functions stay in `src/` modules; `src/utils.py` holds shared helpers only. `ipykernel` added to requirements. |
| 26 Sep 2026 | Data range | SEC page lists 2006q1 to 2026q2. All quarters used. |
| 26 Sep 2026 | Amendments (filter 1) | Neither the PDF readme nor the in-zip readme gives a rule for de-duplicating 4/A, so all 4/A are dropped. |
| 26 Sep 2026 | Common stock (filter 2) | `SECURITY_TITLE` is free text; keep titles containing "common" or "ordinary" (case-insensitive). |
| 26 Sep 2026 | Purchase code (filter 3) | Code P **and** `TRANS_ACQUIRED_DISP_CD` = A. The ~0.5% of P rows marked D (disposed) are dropped as contradictory. |
| 26 Sep 2026 | Lots | A filing's code-P lots are summed into one row before filter 5; the $10,000 minimum applies to the filing total. A lot with no price makes the filing's value missing (fails filter 5). |
| 26 Sep 2026 | Joint filers | When a filing lists several reporting owners, the first-listed owner (file order) is kept. |
| 26 Sep 2026 | 10b5-1 flag (filter 4) | Column `AFF10B5ONE` in SUBMISSION (documented in the in-zip readme). 1/true = yes (dropped), 0/false = no, blank or absent = unknown (kept). The flag is per filing. |
| 26 Sep 2026 | Penny-stock price (filter 6) | Yahoo's close is split-adjusted (e.g. NVDA 2010 shows $0.46 vs ~$18 traded), so the as-traded close is rebuilt from Yahoo's split history before the $2 test. Returns will use adjusted close. |
| 26 Sep 2026 | Price match (filter 7) | Price = last close on or up to 5 calendar days before the filing date. Ticker cleaning: upper-case, first symbol only, strip .OB/.PK, "." → "-". |
| 26 Sep 2026 | SEC User-Agent | "Hunter Sarnelli huntersarnelli1@gmail.com". |
| 26 Sep 2026 | Price sanity check (filter 7b) | Added after Phase 1 and before any returns were computed: drop purchases whose filed average price is more than 50% away from Yahoo's as-traded close on the filing date. Median gap was 2%; 2.4% of purchases exceeded 50% (filing typos such as total value entered as price, or reused tickers). |
| 26 Sep 2026 | H1 deciding return (Phase 2) | **Market-adjusted** return (stock minus SPY) decides H1 pass/fail. Raw returns are reported alongside everywhere. |
| 26 Sep 2026 | Classification rule (Phase 2) | Confirmed against Cohen, Malloy & Pomorski (NBER w16454, pp. 12–13): at the start of each calendar year, an insider (per company) with at least one open-market trade (purchase **or sale**) in each of the three preceding years is routine if they traded in the same calendar month in all three years, otherwise opportunistic. Everyone else is unclassified. History uses all Form 4 code P and S trades in common stock (no $, price or 10b5-1 filters), first-listed owner, and ignores trade dates after the filing date or more than 2 years before it (typos). |
| 26 Sep 2026 | Duplicate events (Phase 2) | Besides Section 6.1's 5-trading-day rule, filings at the same company with identical trade date, share count and price are the same trade reported by related entities (e.g. affiliated funds); the earliest is kept. |
| 26 Sep 2026 | Secondary tests (Phase 2) | H3–H7 compare tagged vs untagged events across all events: t-statistic on monthly means of (tagged edge − untagged edge). H5a/H5b count only other insiders whose filings were already public (no lookahead). H4: a first-ever position counts as large. H7: dollar-volume terciles formed within each filing year; test is smallest minus largest tercile. |
| 26 Sep 2026 | **Post-run bug fixes (Phase 2)** | The first full run was invalid and is kept in `results/phase2_invalid_first_run/`. (1) Control draws had no price rule, so Yahoo bad prints below $2 (e.g. CREG $0.000114 vs $2.88 the next day; VAXX/IONM $0.0001 quotes) produced control returns up to +10,711,500% in 20 days (2,965 draws above +500%), inflating mean control returns. Fix: a control entry day must pass the same $2 as-traded rule as events (filter 6), as Section 6.4 requires the control to be computed "the same way". (2) 73 events in 2007–2008 were classified using incomplete pre-2006 history from late filings. Fix: classification starts in 2009. Both approved by Hunter before re-running. |
| 26 Sep 2026 | v3 implementation | Bad-print screen removes 168 tickers before classification (H1 re-run for the record; the pre-screen H1 run is kept in `results/phase2_before_bad_print_screen/`). H8 control days: the day before a random entry stands in for the filing day and must pass every H8 event rule. QQQ-adjusted returns added for all events. Robustness diagnostics (median, share beating control, 1%-trimmed mean and t, top-10-company share of the edge) are saved next to every verdict and never decide it. H8 was run once, with no peeking: code was tested only on synthetic data. |
| 26 Sep 2026 | Wrap-up | At Hunter's request, no CSVs or downloaded data are kept in git (`results/` and `data/` gitignored) and the local CSVs were deleted. Numbers in `docs/` still name their source CSV; regenerate with `python run_study.py` (several hours, mostly Yahoo rate limits). |
| 26 Sep 2026 | SEC URL | 2026q2 moved to `/files/datastandardsinnovation/...`; loader falls back to that folder on a 404. |
| 26 Sep 2026 | Post-publication split (Phase 2) | Fixed before any results: also report the H1 edge table for events filed **2013-01-01 onward** (Cohen, Malloy & Pomorski published 2012; McLean & Pontiff decay). Exploratory only: the H1 verdict uses the full sample, and this split cannot rescue a failed H1. Also the period with the least survivor bias. |

---

*Research and educational use only. Not investment advice.*

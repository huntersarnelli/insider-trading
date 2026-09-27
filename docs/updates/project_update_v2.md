# Project Update v2: Prior-Evidence Review

**Date:** 26 September 2026
**Applies to:** `project.md` (v1)
**Status:** Read-and-apply. No code changes; plan changes only.

---

## Instructions for Claude Code

1. Read this whole file before touching anything.
2. Apply each change below to `project.md` exactly as written. Do not rephrase, expand or "improve" the inserted text.
3. Do not change anything in `project.md` that this file doesn't mention.
4. After applying, show Hunter a short diff summary (section names and one line each) and stop.
5. Then move this file to `docs/updates/project_update_v2.md` so the history is kept.

**Why this matters:** every change here is made **before any data has been seen**. That keeps the pre-registration honest. Do not use this update as precedent for changing hypotheses or thresholds after results exist.

---

## What changed, in one paragraph

A review of OpenInsider and the insider-trading literature found stronger published evidence for **cluster** purchases in a tighter window (2 days) than v1 assumed, and gave concrete magnitudes to calibrate against. The H1 pass/fail bar, horizons, random-date control and Phase 3 gate are **unchanged**. H5 splits into two pre-registered cluster windows; Phase 1 gains a cross-check against OpenInsider; scraping third-party sites is explicitly out of scope.

---

## Change 1: Update the header

Replace:

```
**Last updated:** 26 September 2026
```

with:

```
**Last updated:** 26 September 2026 (v2: prior-evidence review added; see Section 11 changelog)
```

---

## Change 2: Add Sections 2.1 and 2.2 at the end of Section 2 (Motivation)

Insert after the paragraph beginning "**Calibrate expectations.**":

```markdown
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
```

---

## Change 3: Split H5 in Section 3 (Hypotheses)

Replace the H5 line:

```
- **H5.** Cluster purchases, meaning three or more distinct insiders at the same company within 10 calendar days, beat single-insider purchases.
```

with:

```markdown
- **H5.** Cluster purchases beat single-insider purchases. Test two windows, both fixed now:
  - **H5a:** two or more distinct insiders at the same company buying within **2 trading days**. This matches Alldredge & Blank (2019).
  - **H5b:** three or more distinct insiders at the same company within **10 calendar days**.
  - The event date for a cluster is the filing date of the filing that completes the cluster.
```

---

## Change 4: Update the secondary-test bar in Section 4

Replace:

```
A secondary hypothesis (H3–H7) counts as a finding only with t ≥ 2.5 **and** a positive edge in both halves. The higher bar allows for testing five of them.
```

with:

```
A secondary hypothesis (H3, H4, H5a, H5b, H6, H7) counts as a finding only with t ≥ 2.5 **and** a positive edge in both halves. The higher bar allows for testing six of them.
```

---

## Change 5: Add the OpenInsider cross-check to the Phase 1 done criteria in Section 7

Replace the Phase 1 "Done when" line with:

```markdown
- **Done when** all three are finished:
  - The filter-by-filter row-count table is printed and saved.
  - Hunter has spot-checked 10 random purchases against the original filings on EDGAR (Electronic Data Gathering, Analysis, and Retrieval, the SEC's filing system).
  - Hunter has spot-checked 10 recent purchases (last 3 months) against OpenInsider: same ticker, insider title, share count and dollar value. Any mismatch gets explained before Phase 2 starts.
```

---

## Change 6: Add a line to Section 9 (Out of scope)

After the line about congressional trades / 13F filings / social media sentiment, add:

```
- Scraping OpenInsider or any other third-party site. The SEC is the only data source for filings.
```

---

## Change 7: Add references to Section 10

Append after the McLean & Pontiff reference:

```markdown
- Alldredge, D., & Blank, B. (2019). Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading. *Journal of Financial Research*, 42(2), 331–360. https://onlinelibrary.wiley.com/doi/abs/10.1111/jfir.12172. Source for H5a.
- Jeng, L. A., Metrick, A., & Zeckhauser, R. (2003). Estimating the Returns to Insider Trading: A Performance-Evaluation Perspective. *Review of Economics and Statistics*, 85(2). Purchases informative, sales not; timing of returns.
- Lakonishok, J., & Lee, I. (2001). Are Insider Trades Informative? *Review of Financial Studies*, 14(1). Stronger effect in small firms.
- Piotroski, J. D., & Roulstone, D. T. (2005). Do Insider Trades Reflect Both Contrarian Beliefs and Superior Knowledge About Future Cash Flow Realizations? *Journal of Accounting and Economics*, 39(1). Insiders buy after declines.
- IBKR Campus, *What Corporate Insider Buying Can Tell Investors: Evidence from Academic Research*. Secondhand summary used for the Section 2.1 figures: https://ibkrcampus.com/campus/traders-insight/securities/stocks/what-corporate-insider-buying-can-tell-investors-evidence-from-academic-research/
- OpenInsider: http://openinsider.com/
- mrshu/openinsider-notifier: https://github.com/mrshu/openinsider-notifier
- Setup4Alpha, *Market Edges in 2026, Part 2*: https://setup4alpha.substack.com/p/free-alternative-data-edges
```

---

## Change 8: Add Section 11 (Changelog) at the end of `project.md`

Insert before the final "*Research and educational use only…*" line:

```markdown
---

## 11. Changelog

- **v1 (26 Sep 2026):** initial plan.
- **v2 (26 Sep 2026), after the prior-evidence review.** All changes were made before any data was seen.
  - Added Section 2.1 (published magnitudes and why ours should be lower) and Section 2.2 (existing tools).
  - Split H5 into H5a (2-trading-day cluster, per Alldredge & Blank 2019) and H5b (10-calendar-day cluster). Secondary tests go from five to six.
  - Added the OpenInsider spot-check to the Phase 1 done criteria.
  - Added "no scraping third-party sites" to Section 9.
  - **Unchanged:** the H1 pass/fail bar, horizons, control design and Phase 3 gate.
```

---

## What did NOT change (do not touch)

- **H1 and its pass/fail bar:** at 20 or 60 days, an edge of at least +0.5pp, t ≥ 2.0, positive in both halves, n ≥ 300.
- **Horizons:** 5, 20, 60, 120 trading days.
- **Random-date control:** 200 draws, same tickers.
- **Event date:** filing date, with entry at the next trading day's close.
- **Data sources:** SEC Insider Transactions Data Sets and `yfinance`.
- **Phase order and gates:** Phase 3 is built only if H1 passes.
- **Working rules in Section 0.**

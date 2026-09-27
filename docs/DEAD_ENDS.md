# Dead Ends

Ideas tested and rejected, with the numbers. Each number cites the CSV it comes from, under `results/`.

## H8: insider purchases in established tech stocks (26 Sep 2026)

**Idea:** buy second-tier and large-cap tech/AI stocks after an insider's open-market purchase is filed.

**Test:**
- Universe: tech industry codes, 2013 onward, as-traded price ≥ $5, ≥ $10M a day traded, ≥ 3 years listed.
- 1,125 events at 221 companies.
- Compared with 200 random buy dates in the same stocks under the same rules.
- Rules fixed in `project.md` v3 before running; run once.

**Result: FAIL** (`phase2_h8_tech/h8_criteria.csv`)

| Horizon | Edge vs SPY | t |
|---|---|---|
| 20 days | +0.23pp | −0.41 |
| 60 days | −0.22pp | −0.24 |

- Against QQQ at 60 days: −0.24pp (`h8_edge_table.csv`).
- Median at 60 days: −0.53pp; 48.5% of events beat their random dates (`h8_robustness_checks.csv`).
- No industry group and no breakdown (CEO/CFO, clusters, large purchases, buying after a drop) reached the bar (`h8_edge_table.csv`, `h8_breakdown_tests.csv`).

**Why it probably fails:** heavily analysed, liquid companies leave little for insiders to know that the market has not already priced in. The one robust insider effect in this study is concentrated in the smallest companies (`phase2_event_study/secondary_tests.csv`, H7).

**Do not retry by** adding filters to this universe until something passes; that would be overfitting. A new idea needs its own pre-registration and a live paper-trading check.

## H1 in the post-publication era (2013 onward; exploratory)

H1 passes on the full 2006–2026 sample, but not from 2013 onward, the period after Cohen, Malloy & Pomorski was published (`phase2_event_study/edge_table.csv`):

| Horizon | Opportunistic edge | t | Second half |
|---|---|---|---|
| 60 days | +0.24pp | 0.35 | negative |
| 20 days | +0.05pp | 0.82 | |

This is consistent with McLean & Pontiff's finding that published anomalies decay after publication. H1's full-sample pass is recorded as-is in `docs/01_INSIDER_STUDY.md`.

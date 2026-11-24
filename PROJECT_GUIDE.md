# Ad Fatigue Analysis: Interview Prep Guide

Resume line: *Evaluated ad fatigue, ROAS & CRFC using campaign trend analysis… Applied A/B testing, dynamic ad allocation & frequency capping… targeting 15% ROI uplift.*

---

## 0. Read this first: how to describe the project honestly

This project runs on **simulated data** (real ad-account data is confidential, and I generated it to encode known mechanisms: CTR decays with frequency, each extra exposure is worth less). If an interviewer asks, say so plainly:

> "I built it as an end-to-end portfolio project on a simulated ad-platform dataset: 30 creatives across 6 campaigns over Feb–Apr 2026, plus a 400k-user frequency-cap experiment. Simulation let me validate each method against a known ground truth."

That is a strong answer. Interviewers care far more that you understand the methods than where the rows came from. Do **not** claim a real employer's data or that you *achieved* 15%. Your resume says "targeting", which is fine, and Section 5 shows how the numbers relate to that target.

**Suggested resume tweak** (more defensible and still strong):
- Evaluated ad fatigue, ROAS & reach-frequency curves using rolling CTR trend analysis on 30 creatives (2.4k creative-days); fatigue set in at a median of ~day 35, with ~54% of spend landing on fatigued creatives.
- Designed a frequency-cap A/B test (400k users) and a dynamic allocation back-test; a profit-optimal cap of ~12 raised ROAS ~25% with ~2% revenue loss.

**Assumption to confirm:** I read **CRFC as Cumulative Reach–Frequency Curve** (it fits "exposure gaps"). If you meant something else, tell me and I'll adapt the code and the answers.

---

## 1. 30-second pitch

"Ad performance decays as people see the same creative repeatedly. I measured *when* each creative fatigues using rolling CTR against its own peak, quantified how much budget was spent after fatigue, mapped how impressions are distributed across users with a reach-frequency curve, then tested interventions: a frequency cap through a randomized experiment, and dynamic budget reallocation through a no-look-ahead back-test. The main insight: capping raises ROAS a lot, but a naive cap loses profit; the right cap is where marginal ROAS hits break-even, not where ROAS peaks."

---

## 2. Glossary (know these cold)

| Term | Definition | Formula |
|---|---|---|
| Impression | One ad shown | |
| CTR | Click-through rate | clicks / impressions |
| CVR | Conversion rate | conversions / clicks |
| CPM | Cost per 1,000 impressions | spend / impressions × 1000 |
| CPA | Cost per acquisition | spend / conversions |
| ROAS | Return on ad spend | revenue / spend |
| ROI | Net return | (revenue − spend) / spend = ROAS − 1 |
| Reach | Unique users who saw the ad | |
| Frequency | Avg impressions per reached user | impressions / reach |
| Creative fatigue | Performance decay from over-exposure to the same creative | |
| CRFC (my reading) | Cumulative reach–frequency curve: share of users reached k+ times | |
| Frequency cap | Max impressions per user per period | |

**Rule to state out loud:** compute ratios from **sums** (SUM(clicks)/SUM(impressions)), never by averaging daily ratios. Averaging ratios over-weights small days.

---

## 3. What each file does

| File | Purpose |
|---|---|
| `01_generate_data.py` | Simulates `campaign_daily.csv` (2,408 creative-days) and `ab_test_users.csv` (400k users) |
| `02_queries.sql` + `run_sql.py` | 8 SQL analyses (scorecard, weekly trend, CTR decay, window-function fatigue flag, frequency buckets, A/B summary, reach-frequency curve) |
| `03_analysis.py` | Pandas fatigue detection, CRFC, A/B test with stats, cap sweep, allocation back-test, charts, Tableau exports |
| `tableau/` | 5 clean CSVs for the dashboard |
| `charts/` | 4 PNGs for quick reference |

**How the simulation works (be ready to explain):** each creative has its own appeal and decay rate. CTR is `base × quality × fatigue(freq)`, where fatigue falls from 1 toward 0.30 as cumulative frequency rises. In the experiment, each exposure converts with probability `p0 × 0.85^(j−1)`, so later exposures are worth less. Control = natural heavy-tailed exposure (mean ≈ 9). Variant = capped at 5 per 14 days.

---

## 4. Results (all verified by running the code)

**Fatigue (30 creatives)**
- All 30 hit fatigue (7-day CTR < 70% of own peak). Median onset: **day ~35**.
- **54% of spend** went to creative-days flagged fatigued.
- ROAS fresh **3.44** vs fatigued **1.78** (−48%). Portfolio ROAS 2.55.
- CTR fell 31–49% between a creative's first week and week 4+.
- ROAS by cumulative frequency: 3.99 (1–1.5) → 3.21 → 2.31 → 1.79 → 1.75 (4+).

**CRFC (control arm, 14 days)**
- ~5% of users saw the ad **zero** times; ~19% saw it fewer than 3 times (under-exposed).
- ~33% saw it more than 10 times (over-exposed).
- **55% of all impressions** were a user's 6th+ exposure.

**A/B test: cap of 5 vs no cap (≈200k users per arm)**
| Metric | Control | Variant | Change |
|---|---|---|---|
| Avg exposures | 9.0 | 4.1 | −55% |
| Conversion rate | 0.378% | 0.290% | −23% (p < 0.001) |
| ROAS | 3.71 | 6.42 | **+73%** (95% CI +55% to +95%) |
| Revenue / user | ₹6.02 | ₹4.69 | −22% |
| Profit / user | ₹4.40 | ₹3.96 | **−10%** |

- Sample ratio check passed (p = 0.74). Effect holds in both segments (new 2.58→4.41, returning 5.41→9.46), so no Simpson's paradox.
- **Key insight:** ROAS rose but absolute profit fell. A cap of 5 cuts too deep.

**Cap sweep (fitted diminishing-returns model)**
- Model fit on control only, validated out of sample: predicted variant conversion **0.294%** vs actual **0.290%**. Retention per extra exposure ≈ 0.82.
- ROAS keeps rising as the cap tightens (cap 1 is the "best ROAS"), but **profit peaks at cap ≈ 12**: ROAS 3.74 → 4.65 (**+25%**), revenue −2.3%, profit **+4.7%**, ROI (net) +34%.

**Dynamic allocation back-test** (re-split same spend using only yesterday's trailing-7d ROAS, 5% floor)
- Revenue elasticity to spend = 1.0: **+11.9%** ROAS. 0.7: **+2.4%**. 0.5: **−1.1%**.
- The gain depends on the diminishing-returns assumption, so I call it modest and assumption-sensitive.

### How this relates to the "15% ROI uplift"
A properly tuned cap (~12) gives about +25% ROAS and +34% net ROI on the experiment, exceeding the 15% target, while allocation adds a smaller, uncertain amount. **I would not multiply the two** (the levers overlap and the allocation test is a back-test), so quote them separately.

---

## 5. Interview Q&A

**Methodology**

1. **How did you define fatigue?** Rolling 7-day CTR (sum clicks / sum impressions over the window) falling below 70% of that creative's own running peak. Own-peak baseline controls for creative quality and channel differences; 7 days smooths day-of-week effects. The threshold is a judgment call, and I tested sensitivity: at 60% the median onset is day ~49 with 38% of spend fatigued; at 70%, day ~35 and 54%; at 80%, day ~24 and 69%. So the *level* depends on the cutoff, but the conclusion (every creative decays, and a large share of spend lands after decay) holds at all three. I'd set the real threshold with the business, based on the cost of a refresh.
2. **Why not just use a CTR threshold?** Display CTR is ~0.5% and search ~1.6%; a global threshold would flag the wrong channels. Relative decay is comparable across channels.
3. **Why rolling windows and not daily CTR?** Daily clicks are noisy (binomial noise) and weekends dip. Seven days covers one full weekly cycle.
4. **Why compute ratios from sums?** Averaging daily CTRs weights a 2k-impression day equal to a 50k day. Sums weight by volume.
5. **Fatigue vs seasonality vs auction effects: how do you separate them?** Compare across creatives launched on different dates in the same campaign (staggered launches); if CTR decay tracks creative age/frequency, not calendar date, it's fatigue. Also CPM drifting up with creative age is a platform-penalty signature.
6. **What is CRFC and why useful?** Share of users reached k+ times. It exposes both tails: under-exposed users (reach gap) and over-exposed users (waste). 55% of impressions were 6th+ exposures, so the cap has a real target.

**A/B test**

7. **How was it randomized?** At user level, so a user stays in one arm (avoids interference between exposures). I ran a sample-ratio-mismatch chi-square (p = 0.74), which was healthy.
8. **Which test for conversion?** Two-proportion z-test (large n, binary outcome). z = −4.8.
9. **How did you get a CI on ROAS?** ROAS is a ratio of sums, so no simple formula. I used a user-level bootstrap (1,000 resamples), giving +55% to +95%. The delta method is the analytical alternative.
10. **ROAS went up but conversions and profit went down. Which wins?** It depends on the objective. If budget is fixed and reallocatable elsewhere at ROAS > 1, efficiency matters. If the goal is total profit, tune to where marginal ROAS = 1. Marginal ROAS of the k-th exposure = incremental revenue / CPM cost. That led to the cap sweep.
11. **Why did you run a cap sweep and how do you trust it?** Raw conversion-by-exposure-count was too noisy (~0.4% conversion rate), so I fitted a diminishing-returns curve by maximum likelihood on control only and validated it by predicting the variant arm (0.294% vs 0.290%). First attempt with 60k users failed that validation, which is how I learned the experiment was underpowered, so I scaled to 400k.
12. **Power / sample size?** At a 0.4% base rate you need hundreds of thousands of users to detect a 10–20% relative change. Always compute power before launch.
13. **What can go wrong in a real cap test?** Novelty effects, cross-device users counted as different people, budget pacing shifting spend to other users, frequency measured per platform not cross-platform, and long-run brand effects not seen in 14 days.
14. **Why check segments?** To rule out Simpson's paradox and see whether the cap should differ for new vs returning users. Returning users have higher propensity, so their cap could be higher.

**Allocation**

15. **How does dynamic allocation work here?** Daily, within a campaign, redistribute the same total spend across active creatives with weight ∝ exp(yesterday's 7-day ROAS). Creatives lacking history get the average weight (exploration), 5% floor so nothing is starved. No look-ahead.
16. **Biggest weakness of that test?** It's a back-test: it assumes a creative's ROAS responds to spend with elasticity e. Results swing from +12% to −1% across e = 1.0 to 0.5. In production I'd run a live test, ideally with Thompson sampling (multi-armed bandit) for the explore/exploit trade-off.
17. **Why not just pause fatigued creatives?** Pausing ignores that fresh creative also needs supply. Allocation shifts budget gradually and keeps a floor, and refreshing creative is the real fix.

**SQL / Python / Tableau**

18. **SQL: how did you flag fatigue?** `SUM(...) OVER (PARTITION BY creative_id ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` for rolling clicks/impressions, `MAX(...) OVER (... UNBOUNDED PRECEDING)` for running peak, then a CASE flag. (Q4 in `02_queries.sql`.)
19. **SQL: compare first week vs week 4?** Conditional aggregation, `SUM(CASE WHEN days_since_launch <= 6 THEN clicks END)`. (Q3.)
20. **Pandas: rolling per creative?** `groupby('creative_id')[col].transform(lambda s: s.rolling(7).sum())`, then ratio of the sums, and `cummax()` for the peak.
21. **Tableau dashboard?** See Section 6.

**Judgment**

22. **What would you do differently with real data?** Pull log-level impressions, use platform holdout/lift studies for incrementality rather than last-click ROAS, model creative × audience, and test caps per segment.
23. **Is ROAS the right metric?** It's attributed revenue, so it can overstate impact (last-click). I'd cross-check with incrementality and margin-adjusted profit.
24. **How would you present to a marketing lead?** Lead with money: "54% of spend lands after fatigue; a cap near 12 lifts ROAS ~25% with ~2% revenue loss; a cap of 5 looks great on ROAS but loses profit." Then the creative-refresh cadence: refresh around day 30.

---

## 6. Tableau build (30–45 min)

Connect to the five CSVs in `tableau/`.

1. **Fatigue trend:** `creative_daily.csv` → Columns: Date; Rows: `ctr_7d`; Color: `creative_id` (filter by campaign). Add a reference line at 70% of peak, or color points by `fatigued`.
2. **Age curve:** Columns: `days_since_launch`; Rows: calculated field `SUM(clicks)/SUM(impressions)`. Always build ratios as calculated fields from sums.
3. **ROAS by frequency bucket:** create bins on `cum_frequency` (size 1) and plot `SUM(revenue)/SUM(spend)`.
4. **Reach-frequency curve:** `reach_frequency_curve.csv`, k on Columns, dual lines for the two percentages.
5. **Cap sweep:** `cap_sweep.csv`, dual axis ROAS vs profit; annotate the profit peak at 12.
6. **KPI strip:** ROAS, % spend on fatigued creative-days (`fatigued=1`), fatigue onset day (from `fatigue_summary.csv`).
7. Add a Campaign/Channel filter applied to all sheets. Calculated field to know: `IF [fatigued]=1 THEN [spend] END`.

---

## 7. Honest limitations (say these before they're asked)

- Simulated data: methods are validated, but magnitudes aren't real-world benchmarks.
- Back-test for allocation is assumption-driven (spend elasticity).
- A 14-day window can't capture long-run brand effects or novelty.
- ROAS is attributed revenue, not incremental revenue.
- The exposure counts in the experiment are assumed independent of user propensity within the control arm (true by construction here; in real data, use the randomized arms for causal claims).

---

## 8. Two-day study plan

**Day 1:** Re-run all scripts in order (`01` → `run_sql.py` → `03`), read each output, and explain it aloud. Rewrite Q3, Q4, Q7 from memory.
**Day 2:** Rebuild one Tableau dashboard, then practice Section 5 aloud, especially questions 10, 11, 16 and the honest framing in Section 0.

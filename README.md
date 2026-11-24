# Ad Fatigue Analysis

Analysis of ad fatigue, ROAS and reach-frequency across 30 creatives and a 400k-user frequency-cap experiment.
**Tools:** SQL (SQLite), Python, Pandas, SciPy, Matplotlib, Tableau-ready exports.

> **Note:** the data is **simulated** (real ad-account data is confidential). The simulation encodes known mechanisms (CTR decays as frequency builds; each extra exposure is worth less) so each method can be validated against a known ground truth. Magnitudes are not real-world benchmarks.

## What it answers
1. Do creatives fatigue, and when? (rolling 7-day CTR vs each creative's own peak)
2. How much spend lands after fatigue? (~54% of spend)
3. How are impressions spread across users? (cumulative reach-frequency curve; 55% of impressions are 6th+ exposures)
4. Does a frequency cap help? (randomised A/B test: ROAS +73%, but profit falls at cap 5)
5. What cap is best? (diminishing-returns model fit on control, validated on the variant arm; profit peaks near cap 12, ROAS +25%)
6. Can dynamic budget allocation help? (no-look-ahead back-test: -1% to +12% depending on assumed spend elasticity)

## Run order
```bash
pip install pandas numpy scipy matplotlib
python3 01_generate_data.py   # creates data/campaign_daily.csv and data/ab_test_users.csv
python3 run_sql.py            # runs all queries in 02_queries.sql (or: python3 run_sql.py Q3 Q4)
python3 03_analysis.py        # fatigue, A/B test, cap sweep, allocation, charts, tableau/*.csv, results.json
```

## Files
| File | Purpose |
|---|---|
| `01_generate_data.py` | Simulates the two datasets |
| `02_queries.sql`, `run_sql.py` | 8 SQL analyses and a runner that loads the CSVs into SQLite |
| `03_analysis.py` | Python analysis, charts and Tableau exports |
| `tableau/` | Clean CSVs for the dashboard |
| `charts/` | Output charts |
| `PROJECT_GUIDE.md` | Method notes and interview Q&A |

## Limitations
Simulated data; allocation result depends on an assumed spend elasticity; 14-day window cannot capture long-run effects; ROAS is attributed, not incremental, revenue.

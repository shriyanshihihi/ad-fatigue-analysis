"""
01_generate_data.py
-------------------
Simulates ad-platform data for the Ad Fatigue Analysis project (Feb 1 - Apr 30, 2026).

Produces (in ./data):
  campaign_daily.csv : creative-level daily performance (impressions, clicks, conv, spend, revenue, reach)
  ab_test_users.csv  : user-level randomised frequency-cap experiment (control vs variant)

Why simulated?  Real ad-account data is confidential.  The simulation encodes the
mechanisms the project is about (CTR decays as frequency builds; diminishing returns
per exposure) so every method can be validated against a known ground truth.
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

# ------------------------------------------------------------------ campaigns
campaigns = pd.DataFrame([
    # id, channel, audience pool, base CPM (INR), base CTR, base CVR, AOV (INR), daily budget per creative
    ("C1", "Meta",         400_000, 180, 0.018, 0.035, 1500, 4000),
    ("C2", "Meta",         300_000, 200, 0.020, 0.030, 1800, 4000),
    ("C3", "YouTube",      500_000, 120, 0.008, 0.020, 1400, 3000),
    ("C4", "Google Display", 600_000, 80, 0.006, 0.018, 1300, 2500),
    ("C5", "Programmatic", 350_000, 100, 0.007, 0.022, 1600, 2500),
    ("C6", "Google Search+", 250_000, 220, 0.030, 0.040, 1700, 4500),
], columns=["campaign_id", "channel", "pool", "cpm", "ctr", "cvr", "aov", "budget"])

formats = ["Video", "Static", "Carousel", "UGC", "Animated"]
start, end = pd.Timestamp("2026-02-01"), pd.Timestamp("2026-04-30")
dates = pd.date_range(start, end)
dow_mult = {0: 1.0, 1: 1.0, 2: 1.02, 3: 1.03, 4: 1.0, 5: 0.93, 6: 0.90}

rows = []
for _, c in campaigns.iterrows():
    for i in range(5):  # 5 creatives per campaign, staggered launches
        cid = f"{c.campaign_id}-CR{i+1}"
        launch = start + pd.Timedelta(days=int(rng.integers(0, 25) if i else 0))
        quality = rng.normal(1.0, 0.18)             # creative-specific appeal
        decay = rng.uniform(0.10, 0.22)             # how fast this creative saturates
        fmt = formats[i]
        cum_imps, cum_reach = 0.0, 0.0
        for d in dates[dates >= launch]:
            age = (d - launch).days
            # Spend is flat-ish (equal split), small noise; weekend dip in delivery
            spend_target = c.budget * dow_mult[d.dayofweek] * rng.normal(1, 0.05)
            cpm_today = c.cpm * (1 + 0.004 * age) * rng.normal(1, 0.04)   # CPM drifts up as creative tires
            imps = spend_target / cpm_today * 1000
            # unique reach follows saturating curve on the pool
            new_cum_imps = cum_imps + imps
            new_cum_reach = c.pool * (1 - np.exp(-new_cum_imps / c.pool))
            cum_freq = new_cum_imps / new_cum_reach
            # fatigue: CTR falls towards a floor as cumulative frequency rises
            fatigue = 0.30 + 0.70 * np.exp(-decay * (cum_freq - 1) * 3)
            ctr = c.ctr * quality * fatigue * dow_mult[d.dayofweek] * rng.normal(1, 0.05)
            cvr = c.cvr * (0.75 + 0.25 * fatigue) * rng.normal(1, 0.06)
            imps_i = int(imps)
            clicks = rng.binomial(imps_i, min(max(ctr, 0), 1))
            conv = rng.binomial(clicks, min(max(cvr, 0), 1))
            revenue = conv * c.aov * rng.normal(1, 0.08)
            rows.append(dict(
                date=d.date(), campaign_id=c.campaign_id, channel=c.channel, creative_id=cid,
                creative_format=fmt, launch_date=launch.date(), days_since_launch=age,
                impressions=imps_i, cum_impressions=int(new_cum_imps), cum_reach=int(new_cum_reach),
                cum_frequency=round(cum_freq, 3), clicks=int(clicks), conversions=int(conv),
                spend=round(spend_target, 2), revenue=round(revenue, 2),
            ))
            cum_imps, cum_reach = new_cum_imps, new_cum_reach

daily = pd.DataFrame(rows)
daily.to_csv(OUT / "campaign_daily.csv", index=False)

# ------------------------------------------------------------------ A/B test: frequency cap
# Randomised at user level. Control = uncapped delivery. Variant = cap of 5 impressions / 14 days.
N = 400_000
CPM = 180.0
CAP = 5
DECAY = 0.85          # each additional exposure is worth 85% of the previous one (diminishing returns)
users = pd.DataFrame({
    "user_id": np.arange(N),
    "arm": rng.choice(["control", "variant"], size=N),
    "segment": rng.choice(["new", "returning"], size=N, p=[0.6, 0.4]),
})
# Heavy-tailed natural exposure (some users get hammered): negative binomial, mean ~ 9
users["exposures_uncapped"] = rng.negative_binomial(n=1.6, p=1.6 / (1.6 + 9), size=N)
users["exposures"] = np.where(users.arm == "variant",
                              np.minimum(users.exposures_uncapped, CAP),
                              users.exposures_uncapped)
p0 = np.where(users.segment == "returning", 0.0014, 0.0006)
k = users.exposures.to_numpy()
# P(convert) = 1 - prod_{j=1..k}(1 - p0*DECAY^(j-1)) ; closed form via log-sum
def p_conv(p0_, k_):
    out = np.zeros_like(p0_, dtype=float)
    for kk in np.unique(k_):
        m = k_ == kk
        j = np.arange(kk)
        out[m] = 1 - np.prod(1 - p0_[m][:, None] * DECAY ** j, axis=1) if kk > 0 else 0
    return out
users["converted"] = (rng.random(N) < p_conv(p0, k)).astype(int)
users["revenue"] = np.where(users.converted == 1, rng.lognormal(np.log(1500), 0.35, N), 0).round(2)
users["cost"] = (users.exposures * CPM / 1000).round(4)
users.drop(columns="exposures_uncapped").to_csv(OUT / "ab_test_users.csv", index=False)

print(f"campaign_daily.csv: {len(daily):,} rows | ab_test_users.csv: {len(users):,} rows")

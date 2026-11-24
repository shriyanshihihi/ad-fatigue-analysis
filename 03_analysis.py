"""
03_analysis.py
--------------
1. Fatigue detection (rolling CTR vs. own peak) + wasted spend
2. CRFC: cumulative reach-frequency curve + marginal return per exposure
3. A/B test of a frequency cap (z-test, bootstrap CI for ROAS uplift, segment check)
4. Cap sweep: which cap maximises ROAS vs. profit?
5. Dynamic allocation back-test (no look-ahead)
Outputs: ./charts/*.png, ./tableau/*.csv, results.json
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

root = Path(__file__).parent
(root / "charts").mkdir(exist_ok=True)
(root / "tableau").mkdir(exist_ok=True)
rng = np.random.default_rng(7)
R = {}  # results collected for the prep guide

daily = pd.read_csv(root / "data/campaign_daily.csv", parse_dates=["date"])
users = pd.read_csv(root / "data/ab_test_users.csv")

# ============================================================ 1. FATIGUE DETECTION
daily = daily.sort_values(["creative_id", "date"]).reset_index(drop=True)
g = daily.groupby("creative_id")
for col in ["clicks", "impressions", "spend", "revenue"]:
    daily[f"{col}_7d"] = g[col].transform(lambda s: s.rolling(7, min_periods=7).sum())
daily["ctr"] = daily.clicks / daily.impressions
daily["roas"] = daily.revenue / daily.spend
daily["ctr_7d"] = daily.clicks_7d / daily.impressions_7d
daily["roas_7d"] = daily.revenue_7d / daily.spend_7d
daily["peak_ctr_7d"] = daily.groupby("creative_id")["ctr_7d"].cummax()
daily["fatigued"] = (daily.ctr_7d < 0.70 * daily.peak_ctr_7d).astype(int)

fat = daily.groupby("creative_id").agg(
    onset_day=("days_since_launch", lambda s: s[daily.loc[s.index, "fatigued"] == 1].min()),
    spend=("spend", "sum"),
    spend_fatigued=("spend", lambda s: s[daily.loc[s.index, "fatigued"] == 1].sum()),
    roas_all=("revenue", "sum"),
)
fat["pct_spend_fatigued"] = fat.spend_fatigued / fat.spend
# ROAS before vs after fatigue onset (portfolio level)
roas_fresh = daily.loc[daily.fatigued == 0, "revenue"].sum() / daily.loc[daily.fatigued == 0, "spend"].sum()
roas_tired = daily.loc[daily.fatigued == 1, "revenue"].sum() / daily.loc[daily.fatigued == 1, "spend"].sum()
R["fatigue"] = dict(
    creatives=int(daily.creative_id.nunique()),
    creatives_fatigued=int(fat.onset_day.notna().sum()),
    median_onset_day=float(fat.onset_day.median()),
    pct_spend_while_fatigued=float(daily.loc[daily.fatigued == 1, "spend"].sum() / daily.spend.sum()),
    roas_fresh=float(roas_fresh), roas_fatigued=float(roas_tired),
    overall_roas=float(daily.revenue.sum() / daily.spend.sum()),
)

# CTR decay curve (average across creatives by creative age)
age = daily.groupby("days_since_launch").agg(c=("clicks", "sum"), i=("impressions", "sum"), n=("creative_id", "nunique"))
age["ctr"] = age.c / age.i
age = age[age.n >= 8]
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(age.index, age.ctr * 100, color="#1f77b4")
ax.set(xlabel="Days since creative launch", ylabel="CTR (%)", title="CTR decays as creatives age")
ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(root / "charts/ctr_decay.png", dpi=150); plt.close(fig)

# ============================================================ 2. CRFC (reach-frequency curve)
ctrl = users[users.arm == "control"].copy()
rows = []
total_users, total_imps = len(ctrl), ctrl.exposures.sum()
conv_by_k = ctrl.groupby("exposures").agg(n=("converted", "size"), conv=("converted", "mean"), rev=("revenue", "sum"))
for k in range(1, 21):
    rows.append(dict(
        k=k,
        pct_users_reached_k_plus=(ctrl.exposures >= k).mean(),
        pct_impressions_beyond_k=np.maximum(ctrl.exposures - k + 1, 0).sum() / total_imps,
    ))
crfc = pd.DataFrame(rows)
R["crfc"] = dict(
    pct_users_unreached=float((ctrl.exposures == 0).mean()),
    pct_users_under3=float((ctrl.exposures < 3).mean()),
    pct_users_over10=float((ctrl.exposures > 10).mean()),
    pct_impr_after_5th=float(np.maximum(ctrl.exposures - 5, 0).sum() / total_imps),
)
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(crfc.k, crfc.pct_users_reached_k_plus * 100, marker="o", label="% users reached k+ times")
ax.plot(crfc.k, crfc.pct_impressions_beyond_k * 100, marker="s", label="% impressions delivered at exposure ≥ k")
ax.axvline(5, ls="--", color="grey"); ax.text(5.2, 80, "cap = 5", color="grey")
ax.set(xlabel="Exposure count k", ylabel="%", title="Reach–frequency curve (control arm, 14 days)")
ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(root / "charts/reach_frequency_curve.png", dpi=150); plt.close(fig)

# ============================================================ 3. A/B TEST
a = users[users.arm == "control"]; b = users[users.arm == "variant"]
# 3a. conversion rate: two-proportion z-test
x = np.array([b.converted.sum(), a.converted.sum()]); n = np.array([len(b), len(a)])
p_pool = x.sum() / n.sum()
z = (x[0] / n[0] - x[1] / n[1]) / np.sqrt(p_pool * (1 - p_pool) * (1 / n[0] + 1 / n[1]))
p_conv_test = 2 * (1 - stats.norm.cdf(abs(z)))
# 3b. ROAS uplift: ratio metric -> user-level bootstrap
def roas(df): return df.revenue.sum() / df.cost.sum()
boots = []
ra_, ca_ = a.revenue.to_numpy(), a.cost.to_numpy()
rb_, cb_ = b.revenue.to_numpy(), b.cost.to_numpy()
for _ in range(1000):
    ia = rng.integers(0, len(a), len(a)); ib = rng.integers(0, len(b), len(b))
    boots.append((rb_[ib].sum() / cb_[ib].sum()) / (ra_[ia].sum() / ca_[ia].sum()) - 1)
lo, hi = np.percentile(boots, [2.5, 97.5])
# 3c. cost per user & revenue per user
t_cost = stats.ttest_ind(b.cost, a.cost, equal_var=False)
t_rev = stats.ttest_ind(b.revenue, a.revenue, equal_var=False)
profit_a = a.revenue.sum() - a.cost.sum(); profit_b = b.revenue.sum() - b.cost.sum()
# sample ratio mismatch check
srm_p = stats.chisquare([len(a), len(b)]).pvalue
R["ab"] = dict(
    n_control=int(len(a)), n_variant=int(len(b)), srm_p=float(srm_p),
    conv_control=float(a.converted.mean()), conv_variant=float(b.converted.mean()),
    conv_rel_change=float(b.converted.mean() / a.converted.mean() - 1), conv_z=float(z), conv_p=float(p_conv_test),
    roas_control=float(roas(a)), roas_variant=float(roas(b)),
    roas_uplift=float(roas(b) / roas(a) - 1), roas_uplift_ci=[float(lo), float(hi)],
    cost_per_user_control=float(a.cost.mean()), cost_per_user_variant=float(b.cost.mean()),
    cost_change=float(b.cost.mean() / a.cost.mean() - 1), cost_p=float(t_cost.pvalue),
    rev_per_user_control=float(a.revenue.mean()), rev_per_user_variant=float(b.revenue.mean()),
    rev_change=float(b.revenue.mean() / a.revenue.mean() - 1), rev_p=float(t_rev.pvalue),
    profit_per_user_control=float(profit_a / len(a)), profit_per_user_variant=float(profit_b / len(b)),
    roi_control=float(profit_a / a.cost.sum()), roi_variant=float(profit_b / b.cost.sum()),
)
seg = users.groupby(["segment", "arm"]).apply(lambda d: pd.Series(dict(users=len(d), conv=d.converted.mean(), roas=roas(d))), include_groups=False).reset_index()
R["ab_segments"] = seg.to_dict("records")

# ============================================================ 4. CAP SWEEP (profit vs ROAS)
# Raw conversion-by-exposure-count is far too noisy (0.5% conv rate -> a handful of conversions per k), so we fit a
# diminishing-returns response curve by maximum likelihood on the CONTROL arm only:
#     P(convert | k exposures, segment) = 1 - exp(-a_seg * (1 - r^k) / (1 - r))      (r = per-exposure retention, 0<r<1)
# Then VALIDATE it out-of-sample: predict the variant arm (cap=5) conversion rate it never saw.
from scipy.optimize import minimize
CPM = 180.0
avg_rev_per_conv = users.loc[users.converted == 1, "revenue"].mean()

def p_model(params, seg_is_ret, k):
    a_new, a_ret, r = np.exp(params[0]), np.exp(params[1]), 1 / (1 + np.exp(-params[2]))
    a = np.where(seg_is_ret, a_ret, a_new)
    return 1 - np.exp(-a * (1 - r ** k) / (1 - r))

def nll(params, df):
    p = np.clip(p_model(params, (df.segment == "returning").to_numpy(), df.exposures.to_numpy()), 1e-9, 1 - 1e-9)
    y = df.converted.to_numpy()
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)).sum()

fit = minimize(nll, x0=[np.log(6e-4), np.log(1.4e-3), 1.5], args=(ctrl,), method="Nelder-Mead", options=dict(maxiter=4000, xatol=1e-6, fatol=1e-6))
a_new, a_ret, r_hat = np.exp(fit.x[0]), np.exp(fit.x[1]), 1 / (1 + np.exp(-fit.x[2]))
pred_variant_conv = p_model(fit.x, (b.segment == "returning").to_numpy(), b.exposures.to_numpy()).mean()
R["response_model"] = dict(a_new=float(a_new), a_returning=float(a_ret), retention_per_exposure=float(r_hat),
                           variant_conv_predicted=float(pred_variant_conv), variant_conv_actual=float(b.converted.mean()))

sweep = []
for cap in list(range(1, 16)) + [99]:
    exp_capped = np.minimum(ctrl.exposures.to_numpy(), cap)
    conv = p_model(fit.x, (ctrl.segment == "returning").to_numpy(), exp_capped)
    rev = (conv * avg_rev_per_conv).sum()
    cost = (exp_capped * CPM / 1000).sum()
    sweep.append(dict(cap=cap if cap != 99 else "no cap", revenue=rev, cost=cost, roas=rev / cost, profit=rev - cost))
sweep = pd.DataFrame(sweep)
best_roas = sweep.loc[sweep.roas.idxmax()]
best_profit = sweep.loc[sweep.profit.idxmax()]
nocap = sweep.iloc[-1]
sweep["roas_uplift_vs_nocap"] = sweep.roas / nocap.roas - 1
sweep["revenue_vs_nocap"] = sweep.revenue / nocap.revenue - 1
R["cap_sweep"] = dict(
    best_roas_cap=str(best_roas.cap), best_roas=float(best_roas.roas),
    best_profit_cap=str(best_profit.cap), best_profit_roas=float(best_profit.roas),
    best_profit_roas_uplift=float(best_profit.roas / nocap.roas - 1),
    best_profit_vs_nocap=float(best_profit.profit / nocap.profit - 1),
    best_profit_rev_vs_nocap=float(best_profit.revenue / nocap.revenue - 1),
    nocap_roas=float(nocap.roas),
)
d = sweep.iloc[:-1]
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(d.cap.astype(int), d.roas, marker="o", color="#1f77b4", label="ROAS")
ax.set(xlabel="Frequency cap (impressions / 14 days)", ylabel="ROAS", title="Cap sweep: ROAS vs profit")
ax2 = ax.twinx(); ax2.plot(d.cap.astype(int), d.profit, marker="s", color="#d62728", label="Profit (₹)")
ax2.set_ylabel("Profit (₹)")
if str(best_profit.cap).isdigit():
    ax.axvline(int(best_profit.cap), ls="--", color="grey")
ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(root / "charts/cap_sweep.png", dpi=150); plt.close(fig)

# ============================================================ 5. DYNAMIC ALLOCATION BACK-TEST
# Per campaign-day: re-split the SAME total spend across active creatives using only information up to yesterday.
# weight ∝ exp(trailing-7d ROAS / T); creatives with <7 days of history get the campaign-average weight (exploration);
# 5% floor per creative so nothing is starved. Revenue response uses spend elasticity e (<1 = diminishing returns).
def backtest(elasticity, temp=1.0, floor=0.05):
    out = []
    for (camp, day), df in daily.groupby(["campaign_id", "date"]):
        total = df.spend.sum()
        r7 = df.roas_7d.shift(0)  # roas_7d at row t uses days t-6..t (includes today) -> use yesterday's value instead
        prev = daily.loc[(daily.creative_id.isin(df.creative_id)) & (daily.date == day - pd.Timedelta(days=1)), ["creative_id", "roas_7d"]].set_index("creative_id").roas_7d
        sc = df.creative_id.map(prev)
        if sc.isna().all():
            w = np.ones(len(df))
        else:
            sc = sc.fillna(sc.mean())
            w = np.exp((sc.values - sc.values.mean()) / temp)
        w = w / w.sum()
        w = np.maximum(w, floor); w = w / w.sum()
        new_spend = w * total
        rev = df.revenue.values * (new_spend / df.spend.values) ** elasticity
        out.append((total, df.revenue.sum(), rev.sum()))
    o = np.array(out)
    return o[:, 0].sum(), o[:, 1].sum(), o[:, 2].sum()
alloc = {}
for e in [1.0, 0.7, 0.5]:
    s, r_base, r_dyn = backtest(e)
    alloc[str(e)] = dict(roas_static=r_base / s, roas_dynamic=r_dyn / s, uplift=r_dyn / r_base - 1)
R["allocation"] = alloc

# ============================================================ COMBINED VIEW
# Treat the two levers as independent, stacking on spend efficiency (state this assumption when presenting).
cap_uplift = R["ab"]["roas_uplift"]
alloc_uplift = alloc["0.7"]["uplift"]
R["combined_roas_uplift_naive"] = float((1 + cap_uplift) * (1 + alloc_uplift) - 1)

# ============================================================ TABLEAU EXPORTS
daily.drop(columns=[c for c in daily.columns if c.endswith("_7d") and c not in ("ctr_7d", "roas_7d")]).to_csv(root / "tableau/creative_daily.csv", index=False)
crfc.to_csv(root / "tableau/reach_frequency_curve.csv", index=False)
sweep.to_csv(root / "tableau/cap_sweep.csv", index=False)
fat.reset_index().to_csv(root / "tableau/fatigue_summary.csv", index=False)
ab_tbl = users.groupby("arm").apply(lambda d: pd.Series(dict(users=len(d), avg_exposures=d.exposures.mean(), conv_rate=d.converted.mean(), spend=d.cost.sum(), revenue=d.revenue.sum(), roas=roas(d))), include_groups=False).reset_index()
ab_tbl.to_csv(root / "tableau/ab_summary.csv", index=False)

# bucket chart
bk = pd.cut(daily.cum_frequency, [0, 1.5, 2, 3, 4, 99], labels=["1–1.5", "1.5–2", "2–3", "3–4", "4+"])
bt = daily.groupby(bk, observed=True).apply(lambda d: d.revenue.sum() / d.spend.sum(), include_groups=False)
fig, ax = plt.subplots(figsize=(7, 4)); ax.bar(bt.index.astype(str), bt.values, color="#1f77b4")
ax.set(xlabel="Cumulative frequency (avg impressions per reached user)", ylabel="ROAS", title="ROAS falls as frequency builds")
fig.tight_layout(); fig.savefig(root / "charts/roas_by_frequency.png", dpi=150); plt.close(fig)

json.dump(R, open(root / "results.json", "w"), indent=2, default=str)
print(json.dumps(R, indent=2, default=str))
print("\nCAP SWEEP\n", sweep.round(3).to_string(index=False))

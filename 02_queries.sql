-- 02_queries.sql  (SQLite dialect; window functions work the same in Postgres/BigQuery with tiny syntax changes)
-- Tables: campaign_daily, ab_test_users

-- Q1: Channel scorecard ---------------------------------------------------------
-- Core KPIs. Always compute ratios from SUMS, never average the daily ratios.
SELECT channel,
       SUM(impressions)                                   AS impressions,
       ROUND(100.0 * SUM(clicks) / SUM(impressions), 3)   AS ctr_pct,
       ROUND(100.0 * SUM(conversions) / SUM(clicks), 2)   AS cvr_pct,
       ROUND(SUM(spend) / SUM(conversions), 0)            AS cpa,
       ROUND(SUM(revenue) / SUM(spend), 2)                AS roas
FROM campaign_daily
GROUP BY channel
ORDER BY roas DESC;

-- Q2: Weekly ROAS trend per campaign --------------------------------------------
SELECT campaign_id,
       strftime('%Y-%W', date)                    AS yr_week,
       ROUND(SUM(revenue) / SUM(spend), 2)        AS roas,
       ROUND(100.0 * SUM(clicks) / SUM(impressions), 3) AS ctr_pct
FROM campaign_daily
GROUP BY campaign_id, yr_week
ORDER BY campaign_id, yr_week;

-- Q3: CTR decay per creative: first 7 days vs. days 22+ ----------------------------
-- Conditional aggregation = compare two life-stages of the same creative in one pass.
SELECT creative_id,
       ROUND(100.0 * SUM(CASE WHEN days_since_launch <= 6  THEN clicks END)
                   / SUM(CASE WHEN days_since_launch <= 6  THEN impressions END), 3) AS ctr_first7,
       ROUND(100.0 * SUM(CASE WHEN days_since_launch >= 21 THEN clicks END)
                   / SUM(CASE WHEN days_since_launch >= 21 THEN impressions END), 3) AS ctr_after21,
       ROUND(100.0 * (
             1.0 * SUM(CASE WHEN days_since_launch >= 21 THEN clicks END)
                 / SUM(CASE WHEN days_since_launch >= 21 THEN impressions END)
           / (1.0 * SUM(CASE WHEN days_since_launch <= 6  THEN clicks END)
                 / SUM(CASE WHEN days_since_launch <= 6  THEN impressions END)) - 1), 1) AS ctr_change_pct
FROM campaign_daily
GROUP BY creative_id
HAVING SUM(CASE WHEN days_since_launch >= 21 THEN impressions END) IS NOT NULL
ORDER BY ctr_change_pct;

-- Q4: Fatigue flag with window functions -------------------------------------------
-- Rolling 7-day CTR vs the creative's own best rolling CTR. Flag when it falls below 70% of peak.
WITH roll AS (
  SELECT creative_id, campaign_id, date, spend, revenue, days_since_launch,
         1.0 * SUM(clicks) OVER w / SUM(impressions) OVER w AS ctr7,
         COUNT(*) OVER w AS n_days
  FROM campaign_daily
  WINDOW w AS (PARTITION BY creative_id ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
), peak AS (
  SELECT *, MAX(ctr7) OVER (PARTITION BY creative_id ORDER BY date
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak_ctr7
  FROM roll WHERE n_days = 7
), flagged AS (
  SELECT *, CASE WHEN ctr7 < 0.70 * peak_ctr7 THEN 1 ELSE 0 END AS fatigued
  FROM peak
)
SELECT creative_id,
       MIN(CASE WHEN fatigued = 1 THEN date END)                 AS first_fatigue_date,
       MIN(CASE WHEN fatigued = 1 THEN days_since_launch END)    AS fatigue_onset_day,
       ROUND(SUM(CASE WHEN fatigued = 1 THEN spend END), 0)      AS spend_while_fatigued,
       ROUND(100.0 * SUM(CASE WHEN fatigued = 1 THEN spend END) / SUM(spend), 1) AS pct_spend_fatigued
FROM flagged
GROUP BY creative_id
ORDER BY spend_while_fatigued DESC;

-- Q5: Performance by cumulative-frequency bucket ------------------------------------
SELECT CASE WHEN cum_frequency < 1.5 THEN '1.0-1.5'
            WHEN cum_frequency < 2.0 THEN '1.5-2.0'
            WHEN cum_frequency < 3.0 THEN '2.0-3.0'
            WHEN cum_frequency < 4.0 THEN '3.0-4.0'
            ELSE '4.0+' END AS freq_bucket,
       COUNT(*)                                          AS creative_days,
       ROUND(100.0 * SUM(clicks) / SUM(impressions), 3)  AS ctr_pct,
       ROUND(100.0 * SUM(conversions) / SUM(clicks), 2)  AS cvr_pct,
       ROUND(SUM(revenue) / SUM(spend), 2)               AS roas
FROM campaign_daily
GROUP BY freq_bucket
ORDER BY MIN(cum_frequency);

-- Q6: A/B test summary --------------------------------------------------------------
SELECT arm,
       COUNT(*)                                          AS users,
       ROUND(AVG(exposures), 2)                          AS avg_exposures,
       ROUND(100.0 * AVG(converted), 3)                  AS conv_rate_pct,
       ROUND(SUM(cost), 0)                               AS spend,
       ROUND(SUM(revenue), 0)                            AS revenue,
       ROUND(SUM(revenue) / SUM(cost), 2)                AS roas
FROM ab_test_users
GROUP BY arm;

-- Q6b: by segment (check the effect is not driven by one cohort / Simpson's paradox) --
SELECT segment, arm,
       COUNT(*) AS users,
       ROUND(100.0 * AVG(converted), 3) AS conv_rate_pct,
       ROUND(SUM(revenue) / SUM(cost), 2) AS roas
FROM ab_test_users
GROUP BY segment, arm
ORDER BY segment, arm;

-- Q7: Reach-frequency curve (control arm) -------------------------------------------
-- "What share of users got at least k impressions?"  Reveals under-exposed and over-exposed tails.
WITH ctrl AS (SELECT exposures FROM ab_test_users WHERE arm = 'control'),
     n AS (SELECT COUNT(*) AS total FROM ctrl),
     ks AS (SELECT 1 AS k UNION ALL SELECT k + 1 FROM ks WHERE k < 20)
SELECT ks.k,
       ROUND(100.0 * (SELECT COUNT(*) FROM ctrl WHERE exposures >= ks.k) / n.total, 1) AS pct_users_reached_k_plus,
       ROUND(100.0 * (SELECT SUM(MAX(exposures - ks.k + 1, 0)) FROM ctrl)
             / (SELECT SUM(exposures) FROM ctrl), 1)                                    AS pct_impressions_beyond_k
FROM ks, n
WHERE ks.k IN (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20);

-- Q8: Share of impressions that were the 6th+ exposure to a user (candidate waste) -----
SELECT ROUND(100.0 * SUM(MAX(exposures - 5, 0)) / SUM(exposures), 1) AS pct_impressions_after_5th
FROM ab_test_users WHERE arm = 'control';

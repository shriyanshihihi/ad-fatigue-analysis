"""Loads the CSVs into SQLite and runs every query in 02_queries.sql, printing results."""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

root = Path(__file__).parent
con = sqlite3.connect(root / "ad_fatigue.db")
pd.read_csv(root / "data/campaign_daily.csv").to_sql("campaign_daily", con, if_exists="replace", index=False)
pd.read_csv(root / "data/ab_test_users.csv").to_sql("ab_test_users", con, if_exists="replace", index=False)

sql = (root / "02_queries.sql").read_text()
blocks = [b.strip() for b in re.split(r";\s*\n", sql) if "SELECT" in b.upper()]
only = sys.argv[1:]  # e.g. python run_sql.py Q3 Q4
pd.set_option("display.width", 200, "display.max_rows", 60)
for b in blocks:
    name = re.search(r"-- (Q\w+):", b)
    name = name.group(1) if name else "?"
    if only and name not in only:
        continue
    print(f"\n===== {name} =====")
    print(pd.read_sql(b, con).to_string(index=False))

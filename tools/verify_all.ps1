$ErrorActionPreference = "Stop"
Write-Host "[INFO] git commit"
git rev-parse --short HEAD

Write-Host "[INFO] pytest"
pytest -q

Write-Host "[INFO] verify search"
python tools/verify_search.py

Write-Host "[INFO] table counts"
python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("foods.db")
if not db.exists():
    print("foods.db not found, skip table count")
    raise SystemExit(0)

conn = sqlite3.connect(db)
cur = conn.cursor()
for tbl in ["foods", "food_nutrients", "nutrient_meta"]:
    try:
        count = cur.execute(f"select count(*) from {tbl}").fetchone()[0]
    except sqlite3.OperationalError:
        count = -1
    print(f"{tbl}={count}")
conn.close()
PY

Write-Host "PASS"

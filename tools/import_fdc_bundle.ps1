param(
  [string]$DbPath = "foods.db",
  [string]$InputDir = "data/fdc"
)

$ErrorActionPreference = "Stop"
Write-Host "[INFO] Importing FDC bundle from $InputDir to $DbPath"

python -m dog_nutrition.fdc_import --db $DbPath --input $InputDir

python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("foods.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

foods = cur.execute("select count(*) from foods").fetchone()[0]
print(f"foods_total={foods}")

for kw in ["lamb", "mutton", "shank", "leg"]:
    c = cur.execute("select count(*) from foods where lower(name) like ?", (f"%{kw}%",)).fetchone()[0]
    print(f"hit_{kw}={c}")

conn.close()
PY

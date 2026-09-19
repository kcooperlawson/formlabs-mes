"""Dump every resin spec on THIS machine's database to resin_export.json.

    venv\\Scripts\\python.exe export_resins.py

Run this here, copy resin_export.json to the work PC alongside the update,
then run import_resins.py there. Uses whatever DB_URL this machine's .env
(or bundled pgdata\\) points at - the same database the app itself reads.
"""
import json
from db_core import ScopedSession
from models import ResinSpec

FIELDS = ["cartridge_type", "sku", "resin_code", "resin_name", "actual_spec_g",
          "min_weight_g", "max_weight_g", "lifetime_months", "multiplier",
          "color_tag", "units_per_skid"]

session = ScopedSession()
rows = session.query(ResinSpec).order_by(ResinSpec.id).all()
data = [{f: getattr(r, f) for f in FIELDS} for r in rows]

with open("resin_export.json", "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)

print(f"Wrote resin_export.json - {len(data)} resin specs.")
print("Copy that file to the work PC and run import_resins.py there.")

"""Load resin_export.json (from export_resins.py) into THIS machine's database.

    venv\\Scripts\\python.exe import_resins.py

Safe to run more than once - skips any resin whose SKU already exists here
(e.g. a demo/default resin seeded on a fresh install) rather than duplicating
it. Uses whatever DB_URL this machine's .env (or bundled pgdata\\) points at.
"""
import json
import crud
from db_core import ScopedSession
from models import ResinSpec

with open("resin_export.json", encoding="utf-8") as fh:
    data = json.load(fh)

session = ScopedSession()
existing_skus = {sku for (sku,) in session.query(ResinSpec.sku).all() if sku}

added, skipped = 0, 0
for r in data:
    if r.get("sku") and r["sku"] in existing_skus:
        skipped += 1
        continue
    ok = crud.add_resin_spec(
        cartridge_type=r["cartridge_type"], sku=r["sku"] or "", resin_code=r["resin_code"] or "",
        resin_name=r["resin_name"], actual_spec_g=r["actual_spec_g"],
        min_weight_g=r["min_weight_g"], max_weight_g=r["max_weight_g"],
        lifetime_months=r.get("lifetime_months") or "24", multiplier=r.get("multiplier") or 1.0,
        color_tag=r.get("color_tag"), units_per_skid=r.get("units_per_skid") or 500,
        changed_by="resin import",
    )
    added += 1 if ok else 0

print(f"Added {added}, skipped {skipped} already-present SKU(s).")

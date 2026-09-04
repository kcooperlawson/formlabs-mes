"""Populate a throwaway database with a realistic fortnight of plant activity,
so the screenshots in the handbook show the app doing its actual job."""
import os, sys, pathlib, random, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pgserver
PGDATA = str(pathlib.Path.home() / "pgdata")
srv = pgserver.get_server(PGDATA, cleanup_mode=None)
try:
    srv.psql("DROP DATABASE IF EXISTS mes_demo WITH (FORCE);")
except Exception:
    srv.psql("DROP DATABASE IF EXISTS mes_demo;")
srv.psql("CREATE DATABASE mes_demo;")
URI = f"postgresql+psycopg2://postgres@/mes_demo?host={PGDATA}"
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), "w").write(f"DB_URL={URI}\n")
os.environ["DB_URL"] = URI

import crud
from crud import *
from db_core import ScopedSession
from models import (ProductionLog, DowntimeLog, AssignedRun, LotVerification,
                    DailyChecklist, PlantSettings, User)
from datetime import date, datetime, timedelta

random.seed(7)
S = ScopedSession()

for p in ("Pump 1", "Pump 2", "Pump 3", "Pack-Out Station"):
    add_pump_station(p)
for rname, cap in (("Reactor 1", 5000), ("Reactor 2", 5000), ("Reactor 3", 3000)):
    add_reactor(rname, cap)
for r in ("Nozzle Clog", "Carts/Bins", "Break/Shift Change", "Resin Changeover",
          "Scale Calibration", "Label Printer Jam"):
    add_downtime_reason(r)

RESINS = [
    ("V2", "RS-C2-GPCL-05", "FLGPCL05", "Clear V5",           1110.0, 1100.0, 1115.0, 500),
    ("V2", "RS-C2-GPGR-05", "FLGPGR05", "Grey V5",            1110.0, 1100.0, 1115.0, 500),
    ("V2", "RS-C2-GPWH-05", "FLGPWH05", "White V5",           1120.0, 1110.0, 1130.0, 500),
    ("V1", "RS-C1-DRV2-01", "FLDRV201", "Draft V2",           1120.0, 1110.0, 1130.0, 400),
    ("V1", "RS-C1-TO15-01", "FLTO1501", "Tough 1500 V1",      1070.0, 1060.0, 1080.0, 400),
    ("RPS","RS-R5-GPBK-05", "FLGPBK05", "Black V5",           5000.0, 4950.0, 5050.0, 100),
    ("V2", "RS-C2-HITE-02", "FLHITE02", "High Temp V2",       1140.0, 1130.0, 1150.0, 500),
    ("V2", "RS-C2-CAWX-01", "FLCAWX01", "Castable Wax V1",    1110.0, 1100.0, 1120.0, 500),
    ("V1", "RS-C1-FL80-01", "FLFL8001", "Flexible 80A V1",    1070.0, 1060.0, 1080.0, 400),
    ("V2", "RS-C2-ESD1-01", "FLESD101", "ESD V1",             1060.0, 1050.0, 1070.0, 500),
    ("V2", "RS-C2-CLCA-01", "FLCLCA01", "Clear Cast V1",      1090.0, 1080.0, 1100.0, 500),
    ("V2", "RS-C2-GYPR-01", "FLGYPR01", "Grey Pro V1",        1080.0, 1070.0, 1090.0, 500),
    # Deliberately not on the plant sheet: exercises the family rule (a
    # revision that does not exist yet) and the hashed-swatch fallback.
    ("V2", "RS-C2-BLK6-01", "FLBLK601", "Black V6",           1110.0, 1100.0, 1120.0, 500),
    ("V2", "RS-C2-BIOX-01", "FLBIOX01", "Bioresin XZ9",       1050.0, 1040.0, 1060.0, 500),
]
for c, sku, code, name, spec, lo, hi, ups in RESINS:
    add_resin_spec(c, sku, code, name, spec, lo, hi, units_per_skid=ups)

PEOPLE = [
    ("keagan", "Keagan Whitfield", "admin",    "Shift 1"),
    ("mvega",  "Maria Vega",       "manager",  "Shift 1"),
    ("aruiz",  "Ana Ruiz",         "operator", "Shift 1"),
    ("bchen",  "Bo Chen",          "operator", "Shift 1"),
    ("dokafor","Dee Okafor",       "operator", "Shift 2"),
    ("tlaurent","Theo Laurent",    "operator", "Shift 2"),
    ("smoreau","Sana Moreau",      "operator", "Shift 3"),
    ("cpatel", "Cy Patel",         "packer",   "Shift 1"),
    ("jhaddad","Jo Haddad",        "packer",   "Shift 2"),
]
for u, full, role, shift in PEOPLE:
    create_user(u, f"{u}@plant.local", "1234", full, role, shift=shift)

OPS = {"Shift 1": ["Ana Ruiz", "Bo Chen"], "Shift 2": ["Dee Okafor", "Theo Laurent"],
       "Shift 3": ["Sana Moreau"]}
PUMPS = ["Pump 1", "Pump 2", "Pump 3"]
LOTS = {"Clear V5": "2503C0088", "Grey V5": "2503G0141",
        "Draft V2": "2411A0742", "Tough 1500 V1": "2502T0310",
        "Black V5": "2505B0193", "High Temp V2": "2501H0067",
        "White V5": "2503W0219", "Castable Wax V1": "2412X0455",
        "Flexible 80A V1": "2501F0128", "ESD V1": "2502E0904",
        "Clear Cast V1": "2503K0077", "Grey Pro V1": "2502P0333",
        "Black V6": "2504B0011", "Bioresin XZ9": "2504Z0002"}

today = date.today()
prod, downs, checks = [], [], []
for back in range(13, -1, -1):
    d = today - timedelta(days=back)
    if d.weekday() >= 5:
        continue
    for shift, hour0 in (("Shift 1", 6), ("Shift 2", 14), ("Shift 3", 23)):
        for pump in PUMPS:
            cart, _, _, resin, *_ = random.choice(RESINS)
            lot = LOTS[resin]
            op = random.choice(OPS[shift])
            for h in range(6 if shift != "Shift 3" else 4):
                ts = datetime(d.year, d.month, d.day, (hour0 + h) % 24, random.randint(0, 55))
                units = random.randint(210, 330) if cart != "RPS" else random.randint(55, 85)
                se = random.choice([0, 0, 0, 0, 1, 2])
                sf = random.choice([0, 0, 0, 0, 0, 1, 3])
                prod.append(ProductionLog(
                    timestamp=ts, date=d, log_type="Hourly Bottle Count", operator_name=op,
                    pump_station=pump, shift=shift, cartridge_type=cart, resin_type=resin,
                    lot_number=lot, bottles_filled=units,
                    scrap_empty=se, scrap_filled=sf,
                    verify_status="verified",
                    notes=""))
            if random.random() < 0.45:
                downs.append(DowntimeLog(
                    timestamp=datetime(d.year, d.month, d.day, (hour0 + 2) % 24), date=d,
                    operator_name=op, pump_station=pump, shift=shift,
                    reason=random.choice(["Nozzle Clog", "Carts/Bins", "Resin Changeover",
                                          "Scale Calibration", "Label Printer Jam"]),
                    duration_min=random.choice([10, 15, 20, 25, 35, 45]), notes=""))
        packer = "Cy Patel" if shift == "Shift 1" else "Jo Haddad"
        if shift != "Shift 3":
            for _ in range(2):
                resin = random.choice([r[3] for r in RESINS if r[0] != "RPS"])
                prod.append(ProductionLog(
                    timestamp=datetime(d.year, d.month, d.day, (hour0 + 5) % 24), date=d,
                    log_type="Packing Count", operator_name=packer,
                    pump_station="Pack-Out Station", shift=shift, cartridge_type="V2",
                    resin_type=resin, lot_number=LOTS[resin], bottles_filled=random.randint(420, 520),
                    scrap_empty=0, scrap_filled=0, notes=""))
S.add_all(prod + downs)

for name, pump in (("Ana Ruiz", "Pump 1"), ("Bo Chen", "Pump 2"), ("Cy Patel", "Pack-Out Station")):
    S.add(DailyChecklist(date=today, operator_name=name, shift="Shift 1", pump_station=pump))
S.commit()

# --- lot verification history -------------------------------------------------
lv = []
for back in range(9, -1, -1):
    d = today - timedelta(days=back)
    if d.weekday() >= 5:
        continue
    for i in range(random.randint(5, 9)):
        resin = random.choice([r for r in RESINS if r[0] != "RPS"])
        lot = LOTS[resin[3]]
        op = random.choice(["Ana Ruiz", "Bo Chen", "Dee Okafor", "Theo Laurent"])
        pump = random.choice(PUMPS)
        roll = random.random()
        if roll < 0.055:
            res, lvl, reason, entered = ("mismatch", "full",
                "Wrong pallet staged at the station — lead approved finishing the tote",
                f"L:24{random.randint(10,99)}B0{random.randint(100,999)}")
        elif roll < 0.08:
            res, lvl, reason, entered = ("rejected", "full",
                "Cartridge pulled at the station before pouring",
                f"L:23{random.randint(10,99)}Z0{random.randint(100,999)}")
        elif roll < 0.45:
            res, lvl, reason, entered = ("verified", "fast", None, f"L:{lot}")
        else:
            res, lvl, reason, entered = ("verified", "full", None, f"L:{lot}")
        lv.append(LotVerification(
            timestamp=datetime(d.year, d.month, d.day, random.randint(6, 21), random.randint(0, 59)),
            date=d, operator_name=op, pump_station=pump, shift="Shift 1",
            cartridge_type=resin[0], resin_type=resin[3], expected_lot=lot,
            entered_lot=entered, result=res, check_level=lvl, reason=reason))
S.add_all(lv)
S.commit()

# --- work orders --------------------------------------------------------------
create_assigned_run("Reactor 1", 5000, "Draft V2", "V1", 4000, "Ana Ruiz", "Pump 1", "2411A0742", "Priority — customer backorder")
create_assigned_run("Reactor 2", 5000, "Clear V5", "V2", 4500, "Bo Chen", "Pump 2", "2503C0088", "")
create_assigned_run("Reactor 3", 3000, "Black V5", "RPS", 600, "Dee Okafor", "Pump 3", LOTS["Black V5"], "Bulk jugs — lot tag on before pouring")
create_assigned_run("Reactor 1", 5000, "Tough 1500 V1", "V1", 2500, "Theo Laurent", "Pump 1", "2502T0310", "Queued behind Draft V2")

ps = S.query(PlantSettings).first()
if not ps:
    ps = PlantSettings(); S.add(ps)
ps.target_lph, ps.packing_target_uph, ps.yield_target_pct = 400.0, 500.0, 99.0
S.commit()

pl = S.query(ProductionLog).count(); lvc = S.query(LotVerification).count()
print(f"seeded: {pl} production logs, {S.query(DowntimeLog).count()} downtime, "
      f"{lvc} lot checks, {S.query(AssignedRun).count()} work orders, "
      f"{S.query(User).count()} users")
print("DB_URL=" + URI)
S.close()

"""Everything behind a number.

Every total on every screen is a sum over production logs with some filter
applied - a lot, a pump, a resin, a day. This answers the question "what is
that made of" for any combination of those filters, in one place, so the
panel that opens when somebody clicks a lot and the one that opens when they
click "Pump 7 - 640 today" are the same panel reading the same rows, and can
never disagree with each other about what a lot is.

A run is the one filter that isn't a column: which logs count toward a run
is decided by crud.calculate_logged_units_for_resin (resin exact, pump exact,
cartridge by substring, a blank lot on either side matching anything). This
mirrors that rule rather than inventing a stricter one, so the total shown
here is the run's own progress figure and not a second opinion about it.
"""
from collections import defaultdict

from sqlalchemy import desc, func, or_

import crud
from db_core import ScopedSession
from models import (AssignedRun, CleanlinessAudit, DowntimeLog, LotVerification, ProductionLog,
                    Reactor, ReactorBatch)

LOG_LIMIT = 1000        # rows sent to the browser; the summary always covers all of them
RELATED_LIMIT = 200
POUR = "Hourly Bottle Count"
RUN_TYPES = (POUR, "System Calibration")   # what a run's progress counts


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _eq(column, value):
    """Case- and whitespace-insensitive match: lots and names are typed by
    people, and 'lot-9001 ' is the same lot as 'LOT-9001'."""
    return func.lower(func.trim(column)) == _norm(value)


def _blank_lot(value) -> bool:
    return _norm(value) in ("", "n/a", "none")


def _dated(query, model, f):
    if f.get("date_from"):
        query = query.filter(model.date >= f["date_from"])
    if f.get("date_to"):
        query = query.filter(model.date <= f["date_to"])
    if f.get("shift"):
        query = query.filter(model.shift == f["shift"])
    return query


def _run_matches(run, log) -> bool:
    """crud.calculate_logged_units_for_resin's rule, row by row."""
    if _norm(run.resin_type) and _norm(run.resin_type) != _norm(log.resin_type):
        return False
    if _norm(run.pump_station) and _norm(run.pump_station) != _norm(log.pump_station):
        return False
    cart, l_cart = _norm(run.cartridge_type), _norm(log.cartridge_type)
    if cart and cart not in l_cart and l_cart not in cart:
        return False
    if not _blank_lot(run.lot_number) and not _blank_lot(log.lot_number):
        if _norm(run.lot_number) != _norm(log.lot_number):
            return False
    return True


def resolve(filters: dict) -> dict:
    """Fill in what a run or a reactor implies, so the rest only ever deals
    in plain column filters. Returns the filters plus the run/reactor row."""
    f = {k: v for k, v in filters.items() if v not in (None, "")}
    session = ScopedSession()
    try:
        run = reactor = None
        if f.get("run_id"):
            run = session.query(AssignedRun).filter(AssignedRun.id == int(f["run_id"])).first()
        if f.get("reactor"):
            reactor = session.query(Reactor).filter(_eq(Reactor.reactor_name, f["reactor"])).first()
            # A tank's pours are the pours on the pump it feeds, of the resin in it.
            if reactor is not None:
                f.setdefault("pump", reactor.assigned_pump or "")
                f.setdefault("resin", reactor.current_resin or "")
                f = {k: v for k, v in f.items() if v not in (None, "")}
        session.expunge_all()
        return {"filters": f, "run": run, "reactor": reactor}
    finally:
        session.close()


def _logs(session, f, run):
    query = session.query(ProductionLog)
    if run is not None:
        query = query.filter(ProductionLog.log_type.in_(RUN_TYPES))
        if _norm(run.resin_type):
            query = query.filter(_eq(ProductionLog.resin_type, run.resin_type))
        if _norm(run.pump_station):
            query = query.filter(_eq(ProductionLog.pump_station, run.pump_station))
    else:
        query = query.filter(ProductionLog.log_type == POUR)
    if f.get("lot"):
        query = query.filter(_eq(ProductionLog.lot_number, f["lot"]))
    if f.get("pump"):
        query = query.filter(_eq(ProductionLog.pump_station, f["pump"]))
    if f.get("operator"):
        query = query.filter(_eq(ProductionLog.operator_name, f["operator"]))
    if f.get("resin"):
        query = query.filter(_eq(ProductionLog.resin_type, f["resin"]))
    query = _dated(query, ProductionLog, f)
    rows = query.order_by(desc(ProductionLog.timestamp)).all()
    if run is not None:
        rows = [r for r in rows if _run_matches(run, r)]
    return rows


def _summarise(rows) -> dict:
    by = {k: defaultdict(lambda: [0, 0]) for k in ("operator", "pump", "resin", "lot", "day", "shift")}
    units = litres = scrap_empty = scrap_filled = 0
    weight = defaultdict(int)
    verify = defaultdict(int)
    for r in rows:
        n = int(r.bottles_filled or 0)
        units += n
        litres += crud.log_litres(r.bottles_filled, r.cartridge_type, r.litres_poured)
        scrap_empty += int(r.scrap_empty or 0)
        scrap_filled += int(r.scrap_filled or 0)
        if r.weight_status:
            weight[r.weight_status] += 1
        if r.verify_status:
            verify[r.verify_status] += 1
        for key, value in (("operator", r.operator_name), ("pump", r.pump_station),
                           ("resin", r.resin_type), ("lot", r.lot_number if crud._is_real_lot(r.lot_number) else ""),
                           ("day", r.date.isoformat() if r.date else ""), ("shift", r.shift)):
            if value:
                by[key][value][0] += 1
                by[key][value][1] += n
    stamps = [r.timestamp for r in rows if r.timestamp]
    return {
        "logs": len(rows), "units": units, "litres": round(litres, 1),
        "scrap_empty": scrap_empty, "scrap_filled": scrap_filled,
        "first_at": min(stamps) if stamps else None, "last_at": max(stamps) if stamps else None,
        "weight": dict(weight), "verify": dict(verify),
        "breakdown": {k: sorted(({"key": name, "logs": c, "units": u} for name, (c, u) in v.items()),
                                key=lambda x: -x["units"])
                      for k, v in by.items()},
    }


def drill(filters: dict) -> dict:
    resolved = resolve(filters)
    f, run, reactor = resolved["filters"], resolved["run"], resolved["reactor"]
    session = ScopedSession()
    try:
        # A vessel with nothing to say which pours were its - retired, renamed,
        # a run's "Floor WIP", or a registered tank sitting idle with no pump
        # or resin - still has a batch history worth showing, but gets no
        # pours rather than every pour in the plant.
        orphan_vessel = bool(f.get("reactor")) and not (f.get("pump") or f.get("resin"))
        rows = [] if orphan_vessel else _logs(session, f, run)
        summary = _summarise(rows)

        # --- runs this could belong to --------------------------------------
        runs_q = session.query(AssignedRun)
        if orphan_vessel:
            runs_q = runs_q.filter(_eq(AssignedRun.reactor_id, f["reactor"]))
        elif run is not None:
            runs_q = runs_q.filter(AssignedRun.id == run.id)
        else:
            if f.get("lot"):
                runs_q = runs_q.filter(_eq(AssignedRun.lot_number, f["lot"]))
            if f.get("pump"):
                runs_q = runs_q.filter(_eq(AssignedRun.pump_station, f["pump"]))
            if f.get("resin"):
                runs_q = runs_q.filter(_eq(AssignedRun.resin_type, f["resin"]))
            if f.get("operator"):
                runs_q = runs_q.filter(_eq(AssignedRun.assigned_operator, f["operator"]))
            if not any(f.get(k) for k in ("lot", "pump", "resin", "operator")):
                runs_q = runs_q.filter(AssignedRun.id == -1)   # a bare date isn't "related to" every run
        runs = runs_q.order_by(desc(AssignedRun.created_at)).limit(RELATED_LIMIT).all()

        # --- reactor batches: where the resin came from -----------------------
        lot = f.get("lot") or (run.lot_number if run is not None and not _blank_lot(run.lot_number) else "")
        batch_q = session.query(ReactorBatch)
        if f.get("reactor"):
            batch_q = batch_q.filter(_eq(ReactorBatch.reactor_name, f["reactor"]))
        elif lot:
            batch_q = batch_q.filter(_eq(ReactorBatch.lot_number, lot))
        elif f.get("resin") or f.get("pump"):
            if f.get("resin"):
                batch_q = batch_q.filter(_eq(ReactorBatch.resin_type, f["resin"]))
            if f.get("pump"):
                batch_q = batch_q.filter(_eq(ReactorBatch.pump_station, f["pump"]))
        else:
            batch_q = batch_q.filter(ReactorBatch.id == -1)
        batches = batch_q.order_by(desc(ReactorBatch.filled_at)).limit(RELATED_LIMIT).all()

        # --- cartridge lot checks ---------------------------------------------
        ver_q = session.query(LotVerification)
        if lot:
            ver_q = ver_q.filter(or_(_eq(LotVerification.entered_lot, lot), _eq(LotVerification.expected_lot, lot)))
        if f.get("pump"):
            ver_q = ver_q.filter(_eq(LotVerification.pump_station, f["pump"]))
        if f.get("operator"):
            ver_q = ver_q.filter(_eq(LotVerification.operator_name, f["operator"]))
        if f.get("resin"):
            ver_q = ver_q.filter(_eq(LotVerification.resin_type, f["resin"]))
        ver_q = _dated(ver_q, LotVerification, f)
        verifications = ver_q.order_by(desc(LotVerification.timestamp)).limit(RELATED_LIMIT).all()

        # --- downtime and audits: about a pump/person/day, never about a lot ---
        downtime, audits = [], []
        if not lot and run is None and not orphan_vessel and (f.get("pump") or f.get("operator") or f.get("date_from")):
            dq = session.query(DowntimeLog)
            if f.get("pump"):
                dq = dq.filter(_eq(DowntimeLog.pump_station, f["pump"]))
            if f.get("operator"):
                dq = dq.filter(_eq(DowntimeLog.operator_name, f["operator"]))
            downtime = _dated(dq, DowntimeLog, f).order_by(desc(DowntimeLog.timestamp)).limit(RELATED_LIMIT).all()
            aq = session.query(CleanlinessAudit)
            if f.get("pump"):
                aq = aq.filter(_eq(CleanlinessAudit.pump_station, f["pump"]))
            if f.get("operator"):
                aq = aq.filter(_eq(CleanlinessAudit.operator_name, f["operator"]))
            audits = _dated(aq, CleanlinessAudit, f).order_by(desc(CleanlinessAudit.timestamp)).limit(RELATED_LIMIT).all()

        return {
            "filters": f, "run": run, "reactor": reactor, "summary": summary,
            "logs": rows[:LOG_LIMIT], "truncated": len(rows) > LOG_LIMIT,
            "runs": runs, "batches": batches, "verifications": verifications,
            "downtime": downtime, "audits": audits,
            "downtime_min": sum(int(d.duration_min or 0) for d in downtime),
        }
    finally:
        session.close()

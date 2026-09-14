"""Tab 1: Hourly Pouring Count.

Moved out of Operator_Form.py verbatim - this is the heaviest-traffic tab
on the page and the one with the most cross-widget behavior (tank
changeover detection, the lot verification gate, the bulk-pour amount
math), so the split here is a pure relocation with no logic changes.
Still reruns the whole page on every keystroke, same as before the split -
converting it to fragments is tracked separately, since that needs
someone testing right behind each change given how much of this tab reads
and writes the same session_state keys the checklist gate and "My
Station" picker also touch.
"""
from datetime import datetime, timedelta

import streamlit as st

import crud
import fill_weight
from bulk_pour import UNITS as BULK_UNITS, pour_litres, check_pour, describe_pour, resin_density
from components import lock_submit, save_state, submit_gate
from database import (
    add_hourly_log,
    add_lot_verification,
    can,
    container_words,
    esc,
    flash,
    format_choices,
    format_code,
    GATED_FORMATS,
    get_all_resin_specs_df,
    get_production_logs_df,
    is_placeholder_lot,
    lots_match,
    normalize_lot,
    save_lot_photo,
    undo_own_log,
    UNDO_WINDOW_SECONDS,
)
from resin_palette import resin_chip
from .shared import _vessel_label, bulk_vessel_state


def render(ctx):
    current_user = ctx.current_user
    current_shift = ctx.current_shift
    active_pumps = ctx.active_pumps
    bulk_pour_enabled = ctx.bulk_pour_enabled
    bulk_densities = ctx.bulk_densities
    resin_colour_map = ctx.resin_colour_map
    df_runs = ctx.df_runs
    simple_mode = ctx.simple_mode

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📍 1. Station & Material Setup")

    # Stacked inputs for maximum tap-target size on mobile.
    # No `index=` here on purpose: st.session_state["h_pump"] is
    # already seeded with the right default above, and this is the
    # single source of truth for "my station" — changing it here is
    # what updates Section 1's active-run list on the next rerun.
    # Open on what they picked last time. Same station, same format and
    # nearly always the same resin as the hour before, so asking for all
    # three twelve times a shift is asking somebody at a pump to re-answer
    # questions that have not changed since breakfast. Seeded once per
    # session and only where the widget has no value yet, so it never
    # fights an operator who has already changed something.
    if not st.session_state.get("_picks_seeded"):
        _last = crud.get_last_picks(current_user)
        if _last["cartridge"] and _last["cartridge"] in format_choices(bulk_pour_enabled):
            st.session_state.setdefault("h_cart", _last["cartridge"])
        if _last["resin"]:
            st.session_state["_last_resin_pick"] = _last["resin"]
        st.session_state["_picks_seeded"] = True

    station = st.selectbox("Pump Station", active_pumps, key="h_pump")

    # "Bulk / Drum" only appears when the plant has switched it on. A floor
    # that never decants should not have to scroll past an option it will
    # never pick, and until somebody turns it on this dropdown holds
    # exactly the four entries it has always held.
    # The label-to-code mapping is a table in crud, not a chain of
    # substring tests here. See crud.CONTAINER_FORMATS for why.
    cartridge = st.selectbox("Container Format",
                             format_choices(bulk_pour_enabled), key="h_cart")
    cart_code = format_code(cartridge)
    is_bulk = cart_code == "Bulk"

    # The Resin Formulation list must always show every resin on file,
    # never just the ones whose master spec happens to be registered
    # under this specific Container Format. A resin that's only ever
    # been registered as, say, V2 can still legitimately get run
    # through a V1 cartridge one day — and the operator has to be able
    # to log that regardless of what the spec table says. cart_code
    # is only used below to prefer a cartridge-matched spec for the
    # target-weight display; it never gates which resins are selectable.
    all_specs_df = get_all_resin_specs_df("ALL")
    resin_names = sorted(all_specs_df["resin_name"].unique().tolist()) if not all_specs_df.empty else []
    # The resin is seeded here rather than above, because the list it has
    # to be a member of is only built at this point.
    _seed_resin = st.session_state.pop("_last_resin_pick", "")
    if _seed_resin and _seed_resin in resin_names:
        st.session_state.setdefault("h_resin", _seed_resin)

    resin = st.selectbox("Resin Formulation", resin_names, key="h_resin")
    # The selected formulation, in its own colour, directly under the
    # dropdown. A dropdown shows the same grey text whatever is chosen,
    # so this is the one place on the screen where what the operator
    # picked can be compared at a glance against the cartridge in their
    # hand rather than by reading two lines of similar-looking text.
    if resin:
        st.markdown(resin_chip(resin, resin_colour_map.get(str(resin)), size="lg"),
                    unsafe_allow_html=True)

    # Which tank this hour will come off. Nobody picks it - it is worked
    # out from the station and the resin, the same way the level
    # arithmetic works it out. It is printed because a link nobody can see
    # is a link nobody can tell is wrong: reported from the floor as "there
    # is no reactor selector so it has no idea what I am pouring from",
    # and on that install it genuinely had no idea, because the vessel had
    # never been given a pump or a resin.
    #
    # None of it applies to a pour the operator has said came off a drum
    # rather than the tank. There is no vessel to name, no changeover to
    # confirm, and no missing link to warn about, so the whole block is
    # skipped rather than printing a tank this pour has nothing to do
    # with. The pick is read out of session state because the question
    # itself is asked further down the form, and a radio answers on the
    # rerun it causes.
    _said_off_tank = is_bulk and str(
        st.session_state.get("h_bulk_src", "")).startswith("A drum")
    if _said_off_tank:
        st.caption("🛢️ No tank on this one — you said it came out of a drum.")
    if station and resin and not _said_off_tank:
        _vessel = crud.reactor_for(station, resin)
        if _vessel is None:
            # A tank IS on this pump, it is just recorded as holding
            # something else. That is a changeover, and it is the one
            # moment a vessel's level accounting starts again - so the
            # operator confirms it rather than it happening silently
            # behind a mis-picked resin.
            _on_pump = crud.vessels_on_pump(station)
            if len(_on_pump) == 1:
                _v = _on_pump[0]
                _was = str(_v.get("current_resin") or "").strip()
                _tag = str(_v.get("asset_tag") or "").strip() or _v["reactor_name"]
                if not _was:
                    # Nothing recorded is a blank, not a changeover. There
                    # is no previous material to disagree with, so there is
                    # nothing to confirm. Submitting the log fills it in.
                    st.caption(f"🛢️ {_tag} has no resin recorded yet. Logging "
                               f"this will record it as holding {resin}.")
                else:
                    st.warning(
                        f"**{_tag} is recorded as holding "
                        f"{_was}, and you have picked {resin}.**")
                    if st.button(f"✅ Yes — {_tag} was changed over to {resin}",
                                 key="confirm_changeover", use_container_width=True):
                        crud.record_changeover(_v["reactor_name"], resin,
                                               operator=current_user,
                                               shift=current_shift,
                                               pump_station=station)
                        flash(f"{_tag} is now on {resin}.", "🛢️")
                        st.rerun()
                    st.caption("If that is not right, check the resin above. Your log "
                               "records either way — this only decides which tank the "
                               "litres come off.")
            else:
                # The checklist asks this once a day per station, so a tank
                # created after that morning's checklist could not be linked
                # until the next one, and the operator standing at the pump
                # was told to go and find a question that had already gone.
                # It is the same question, answerable here, any time this
                # station has no vessel on it.
                st.warning(
                    "**No vessel is linked to this station.** Your log still records "
                    "and still counts. It only means the tank level will not move "
                    "until this is answered.")
                _opts = crud.vessels_for_pump_picker(station)
                if _opts:
                    _map = {_vessel_label(v): v["reactor_name"] for v in _opts}
                    _pick = st.selectbox(
                        "🛢️ Which vessel does this pump draw from?",
                        ["— pick one —"] + list(_map.keys()),
                        key="form_vessel_pick")
                    if _pick and not _pick.startswith("—"):
                        _target = _map[_pick]
                        if st.button(f"🔗 Link {_target} to {station}",
                                     key="form_vessel_link",
                                     use_container_width=True):
                            if crud.link_vessel_to_pump(_target, station):
                                flash(f"{_target} is now on {station}.", "🛢️")
                                st.rerun()
                            else:
                                st.error("That vessel could not be linked. "
                                         "Tell your lead.")
                    st.caption("Read the tag off the side of the tank. A tank shown "
                               "as being on another pump can be moved here.")
                else:
                    st.caption("No vessels are registered yet. A manager adds them "
                               "in IT Admin.")
        elif _vessel.get("ambiguous"):
            st.warning("More than one vessel is set to this station and resin ("
                       + ", ".join(_vessel["ambiguous"]) + "), so the level cannot "
                       "tell which one this came out of. Your lead can fix that on "
                       "the reactor page.")
        else:
            _tag = str(_vessel.get("asset_tag") or "").strip()
            _bay = str(_vessel.get("bay_marker") or "").strip()
            _where = f" · bay {_bay}" if _bay else ""
            _name = f"{_tag} ({_vessel['reactor_name']})" if _tag else _vessel["reactor_name"]
            st.caption(f"🛢️ Drawing from **{_name}**{_where}")

            # Where that tank stands with QC. It is said and never
            # enforced: a missing QC entry is a gap in somebody's
            # paperwork, and stopping a pour over it would turn an office
            # job into a stopped line. The operator is told, their lead
            # gets told by the same screen, and the log records either way.
            _b = crud.current_batch(_vessel["reactor_name"])
            if _b:
                _r = _b.get("qc_result") or ""
                if _r == "fail":
                    st.warning("⚠️ **This tank's batch failed QC.** Your log "
                               "still records. Check with your lead before "
                               "you pour any more of it.")
                elif _r == "hold":
                    st.warning("⚠️ **This tank's batch is on hold at QC.** "
                               "Your log still records. Worth a word with "
                               "your lead.")
                elif _b.get("qc_open"):
                    st.caption("🧪 A sample from this tank is out at QC. "
                               "Nothing to do, it is just not back yet.")

                # How long this filling has actually been sitting here, and
                # the one action that keeps that number honest. Without this,
                # a filling's end is only ever inferred from the next
                # changeover - which is fine the moment a new resin goes in
                # right away, and wrong by however many hours the tank sat
                # dry first. Pressing this the moment the tank runs dry is
                # what makes that gap disappear.
                if can("mark_reactor_empty"):
                    _hrs = _b.get("hours_in_reactor")
                    _dwell_col, _empty_col = st.columns((3, 2))
                    with _dwell_col:
                        if _hrs is not None:
                            st.caption(f"⏱️ In the tank {_hrs:,.0f}h so far."
                                       if _hrs >= 1 else "⏱️ In the tank under an hour.")
                    with _empty_col:
                        if st.button("🛢️ Mark empty", key=f"pour_mark_empty_{_b['id']}",
                                     use_container_width=True,
                                     help=f"Press this the moment {_name} actually runs "
                                          "dry - don't wait for the next changeover. "
                                          "That is what keeps its dwell time on Batch "
                                          "History accurate."):
                            crud.close_batch(_vessel["reactor_name"], by=current_user)
                            flash(f"{_name} marked empty.", "🛢️")
                            st.rerun()

    cart_matched = get_all_resin_specs_df(cart_code)
    cart_matched = cart_matched[cart_matched["resin_name"] == resin] if not cart_matched.empty else cart_matched
    # weight_spec is whichever spec row we ended up showing, or None when
    # this resin has no numbers on file. The check-weight field further
    # down judges against exactly what the operator was shown here, so
    # the two can never disagree.
    weight_spec = None
    if not cart_matched.empty:
        spec_info = cart_matched.iloc[0]
        weight_spec = fill_weight.spec_from_row(spec_info)
        st.caption(f"⚖️ Target: **{spec_info['actual_spec_g']}g** | Range: **{spec_info['acceptable_range']}g**")
    else:
        matched = all_specs_df[all_specs_df["resin_name"] == resin]
        if not matched.empty:
            spec_info = matched.iloc[0]
            weight_spec = fill_weight.spec_from_row(spec_info)
            st.caption(f"⚖️ Target: **{spec_info['actual_spec_g']}g** | Range: **{spec_info['acceptable_range']}g** "
                       f"_(no spec on file for {cartridge} — showing this resin's spec from another Container Format)_")
        else:
            st.caption("⚖️ No weight spec on file for this resin yet — logging is still allowed.")

    # Case-/whitespace-insensitive match — pump/resin/cartridge all come
    # from the same dropdowns as the Manager Cockpit's, but incidental
    # differences (trailing space, casing) used to make this silently
    # miss and fall back to a generic lot number that wouldn't match
    # the real run, so bottle counts never reached its progress bar.
    _norm = lambda s: str(s).strip().lower()
    station_active_run = df_runs[
        (df_runs["pump_station"].apply(_norm) == _norm(station)) &
        (df_runs["resin_type"].apply(_norm) == _norm(resin)) &
        (df_runs["cartridge_type"].apply(_norm) == _norm(cart_code)) &
        (df_runs["status"].isin(["Active", "Pouring"]))
        ]
    auto_lot = str(station_active_run.iloc[0].get("lot_number",
                                                  f"LOT-{datetime.now().strftime('%Y%m%d')}-01")) if not station_active_run.empty else f"LOT-{datetime.now().strftime('%Y%m%d')}-01"

    # ==================================================================
    # 2. CARTRIDGE LOT VERIFICATION GATE
    # ------------------------------------------------------------------
    # The run's lot used to auto-fill an editable box right here, which
    # meant the form answered its own question: an operator could log a
    # full hour without ever turning a cartridge over. Now the expected
    # lot is masked and the operator types what is actually on the bottom
    # of the container in their hand, so nothing about this
    # gate can be satisfied from what is on screen.
    #
    # A mismatch never dead-ends anyone - it demands a reason, flags the
    # log, and alerts the manager.
    #
    # The gate now covers RPS as well. It used to skip that format on the
    # understanding that bulk jugs carried no lot label; they always have,
    # and the plant now requires the tag to be on the jug before pouring
    # starts, which is what made the check possible there. A 5-litre jug
    # is read exactly the way a cartridge is - turned over, the lot label
    # on its bottom - so only the noun differs on screen. See
    # crud.container_words.
    # ==================================================================
    gate_applies = cart_code in GATED_FORMATS
    words = container_words(cart_code)
    expected_lot = auto_lot
    expected_is_real = not is_placeholder_lot(expected_lot)

    st.markdown("---")
    st.markdown(f"#### 🔒 2. {words['noun'].capitalize()} Lot Verification")

    lot_num = expected_lot
    verification = None
    pending_photo = None
    gate_ok = False
    gate_blockers = []
    extra_note = ""

    if not gate_applies:
        # No format reaches this now. Kept rather than deleted because a
        # format added later with nothing to read on it should degrade to
        # a plain field, not to a gate that can never be satisfied.
        st.info(f"**No lot label on this format** — nothing to verify.")
        lot_num = st.text_input("Batch Lot Number", value=auto_lot,
                                help="Auto-fills from the active run.", key="h_lot")
        gate_ok = True

    else:
        gate_mem = st.session_state.setdefault("lot_gate_memory", {})
        mem = gate_mem.get(station)

        # The fast path exists so a per-log check doesn't decay into a
        # reflex tap. It only survives while nothing physical has changed,
        # and it re-arms into a full check every 10th log regardless.
        fast_ok = False
        if mem and expected_is_real and mem.get("entered"):
            same_material = (mem.get("expected") == expected_lot
                             and mem.get("resin") == resin
                             and mem.get("cart") == cart_code)
            fresh = (datetime.now() - mem.get("ts", datetime.min)) <= timedelta(hours=4)
            spot_check_due = mem.get("since_full", 0) >= 9
            fast_ok = bool(same_material and fresh and not spot_check_due)

        base_v = {
            "operator_name": current_user,
            "pump_station": station,
            "shift": current_shift,
            "cartridge_type": cart_code,
            "resin_type": resin,
            "expected_lot": expected_lot if expected_is_real else None,
        }

        if fast_ok:
            st.success(
                f"✅ Verified at **{mem['ts'].strftime('%I:%M %p').lstrip('0')}** "
                f"by {mem.get('by', 'this station')} — same run, same lot, same station.")
            still_reads = st.checkbox(
                f"{words['still_reads']} **L-{mem['entered']}**",
                key="h_lot_fast_confirm")
            st.caption("A full check comes back on any change of run, lot, resin or station, "
                       "after 4 hours, and on every 10th log.")
            if still_reads:
                gate_ok = True
                lot_num = expected_lot
                verification = dict(base_v, entered_lot=mem["entered"],
                                    result="verified", check_level="fast")
            else:
                gate_blockers.append("confirm the cartridge still reads the lot shown above")

        else:
            if expected_is_real:
                st.markdown(
                    "Expected lot for this run: &nbsp; `• • • • • • • • •` &nbsp; "
                    "<span style='color:inherit; opacity:0.72; font-size:0.85rem;'>"
                    f"hidden on purpose — read the {words['noun']}, not the screen</span>",
                    unsafe_allow_html=True)
            elif not simple_mode:
                # Only worth saying in a plant that dispatches runs, where
                # a missing match means a real mismatch somewhere. In a
                # plant that logs and nothing else there is no run to miss,
                # and a yellow box saying so is the app calling its own
                # normal state a problem - which is what made this screen
                # look half-configured. Recording the lot with no expected
                # value to compare it to is a complete answer to "which lot
                # went into this pour"; it is only the comparison that is
                # absent, and the caption below already says what to type.
                st.info(
                    f"No open run matches this station, resin and format, so the "
                    f"{words['noun']} lot is recorded rather than checked. Read it "
                    f"the same way.")
            st.caption(f"{words['where']} "
                       "Type it exactly as printed — spacing, case and the prefix don't matter.")

            entered_lot = st.text_input(words["field"],
                                        key="h_lot_entered", placeholder="2411A0742")

            typed = entered_lot.strip()
            result = None
            reason_kind, reason_detail = "", ""

            # The E- expiry line printed under the lot is deliberately NOT typed.
            # One field is all of the operator's time this check is worth, and a
            # second one every hour is how a gate turns into a reflex. The expiry
            # is already in the photo, so the offline OCR pass can fill
            # entered_expiry / expiry_status later without adding a keystroke at
            # the station - which is why those columns still exist on the table.
            if typed:
                if not expected_is_real:
                    result = "recorded"
                elif lots_match(expected_lot, typed):
                    result = "verified"
                else:
                    result = "mismatch"

            if result == "verified":
                st.success("✅ **Lot matches this run.**")
            elif result == "recorded":
                # normalize_lot, not the raw field: the caption above
                # promises the prefix does not matter, and an operator who
                # types the L- they can see on the label was being read
                # back "L-L-2411A0742" - which looks like the app
                # mistyped, on the one screen whose entire job is being
                # trusted about a code. "Stamp" is gone with it; the label
                # on the bottom of the container is a label, and calling
                # it two things is how an instruction stops being read.
                st.info(f"📝 Lot recorded: **L-{normalize_lot(typed) or typed}** — "
                        "saved against this log.")
            elif result == "mismatch":
                st.error(f"⛔ **STOP — DO NOT POUR.** This {words['noun']} is not from the lot "
                         "assigned to your run. Set it aside and get your lead.")

            if result == "mismatch":
                st.markdown(f"**Pulled the {words['noun']} instead? Log the catch — "
                            "it belongs in the record.**")
                if st.button(f"❌ Wrong {words['noun']} — pulled it, nothing poured",
                             use_container_width=True, key="h_lot_reject"):
                    add_lot_verification(dict(
                        base_v, entered_lot=typed, result="rejected", check_level="full",
                        reason=f"{words['noun'].capitalize()} pulled at the station "
                               "before pouring",
                        photo_filename=save_lot_photo(pending_photo)))
                    gate_mem.pop(station, None)
                    flash("Catch recorded. Nothing was logged as poured.", "🛑")
                    st.rerun()

                reason_kind = st.selectbox(
                    "Logging it anyway? Say what happened.",
                    ("", "Wrong pallet staged at the station", "Label misprint or unreadable",
                     "Cartridge was relabeled", "Run lot in the MES is wrong",
                     "Lead approved the pour", "Other"),
                    key="h_lot_reason_kind")
                reason_detail = st.text_input("Details (required)", key="h_lot_reason_detail",
                                              placeholder="What did you and your lead decide?")

                # Evidence is only worth the upload wait on this branch. A flagged
                # pour is the one someone reviews later and may have to defend, and
                # the operator is already stopped talking to their lead, so the
                # 20-30 seconds costs nothing the situation wasn't costing anyway.
                # Note it is NOT required to pull the cartridge above: the safe
                # action must never be slower than the risky one.
                st.markdown(f"**Photograph the {words['noun']} bottom** "
                            "— required to log a pour against a flag.")
                photo_mode = st.radio(f"Photo of the {words['noun']} bottom", ("Take photo", "Upload image"),
                                      horizontal=True, key="h_lot_photo_mode")
                if photo_mode == "Take photo":
                    pending_photo = st.camera_input(f"Photograph the {words['noun']} bottom",
                                                    key="h_lot_cam")
                else:
                    pending_photo = st.file_uploader(f"Upload a photo of the {words['noun']} bottom",
                                                     type=["png", "jpg", "jpeg", "webp", "heic", "heif"],
                                                     key="h_lot_upload")

            if not typed:
                gate_blockers.append("type the L- lot from the cartridge")
            if result == "mismatch" and not (reason_kind and reason_detail.strip()):
                gate_blockers.append("pick a reason and add details before logging a flagged pour")
            if result == "mismatch" and pending_photo is None:
                gate_blockers.append(f"photograph the {words['noun']} bottom")

            gate_ok = not gate_blockers
            if gate_ok:
                reason_text = " — ".join(p for p in (reason_kind, reason_detail.strip()) if p)
                # On a mismatch the log carries the lot that was physically in
                # the cartridge, not the one the run expected. The run's
                # progress bar not moving is the point: it surfaces the problem
                # instead of burying it under a correct-looking count.
                lot_num = typed if (result == "mismatch" or not expected_is_real) else expected_lot
                if result == "mismatch":
                    extra_note = (f"⚠️ LOT MISMATCH — {words['noun']} labelled L-{typed}, "
                                  f"run expects {expected_lot}. {reason_text}")
                verification = dict(base_v, entered_lot=typed, result=result,
                                    check_level="record" if result == "recorded" else "full",
                                    reason=reason_text or None)

    st.markdown("---")
    # A short window to take back the last entry. Deliberately here, next
    # to the form that created it, rather than on a manager's screen: the
    # person who typed 2500 instead of 250 is standing right here and
    # knows within seconds, and making them find a lead to fix it is how
    # a wrong number ends up living in the dashboards all shift.
    _undo = st.session_state.get("undo_log")
    if _undo:
        _age = (datetime.now() - _undo["at"]).total_seconds()
        if _age > UNDO_WINDOW_SECONDS:
            st.session_state.pop("undo_log", None)
        else:
            _u1, _u2 = st.columns([3, 1])
            _u1.caption(
                f"Last entry: **{_undo['units']:,} units** "
                f"({int(UNDO_WINDOW_SECONDS - _age)}s left to undo)")
            if _u2.button("↩️ Undo last", use_container_width=True, key="undo_last_log"):
                _ok, _msg = undo_own_log(_undo["id"], current_user)
                st.session_state.pop("undo_log", None)
                (st.toast if _ok else st.error)(_msg, **({"icon": "↩️"} if _ok else {}))
                if _ok:
                    st.rerun()

    st.markdown("#### 📊 3. Production Output")

    # A bulk pour is an amount, not a count, so the big field asks for the
    # amount instead. The container count stays - three identical drums off
    # the same tank is one thing that happened, and making somebody write
    # it three times is how the third one gets forgotten - but it is the
    # small field here, because it is almost always 1.
    bulk_litres = None
    bulk_note = ""
    bulk_off_tank = False
    bulk_verdict = {"blocked": False, "message": ""}

    if is_bulk:
        bk1, bk2, bk3 = st.columns([1.4, 1, 1])
        with bk1:
            bulk_each = st.number_input("Amount in each container", min_value=0.0,
                                        value=0.0, step=1.0, format="%.2f", key="h_bulk_each")
        with bk2:
            bulk_unit = st.radio("Unit", BULK_UNITS, horizontal=True, key="h_bulk_unit")
        with bk3:
            # Was 99. A drum decanted into 1 L bottles is a couple of
            # hundred of them, and a cap that stops at 99 turns one pour
            # into three log entries and an arithmetic problem at the end
            # of the shift.
            bottles_filled = st.number_input("Containers", min_value=1, max_value=999,
                                             value=1, step=1, key="h_bulk_count")

        bulk_note = st.text_input(
            "Poured into", placeholder="brown 1L bottles, 55 gal drum, blue tote, pail",
            max_chars=60, key="h_bulk_what",
            help="Whatever it was, in your own words. Nothing has to be registered "
                 "or match a list - this is for the person reading the log later.")

        # Where it came from. Every other log on this form comes off the
        # tank on this station, because that is what filling a cartridge
        # is. This one might not: resin decanted out of a drum left the
        # tank whenever that drum was filled, so charging it to the tank
        # again takes the same litres off twice and empties a vessel
        # nobody has touched. The operator is the only one who knows
        # which it was, so this asks, rather than a report being wrong
        # in a way that looks fine.
        _src = st.radio(
            "Where did it come from?",
            ("The tank on this station",
             "A drum or container already off the tank"),
            horizontal=False, key="h_bulk_src")
        bulk_off_tank = _src.startswith("A drum")

        _dens = resin_density(resin, bulk_densities)
        bulk_litres = pour_litres(bottles_filled, bulk_each, bulk_unit, _dens)

        # The tank this came out of, so an amount that cannot be true gets
        # caught here rather than showing up as an empty vessel on the wall
        # display an hour later. 1800 typed instead of 180 looks perfectly
        # ordinary in a number box. An off-tank pour has no vessel to
        # measure against, so it keeps the size check and drops the two
        # that are about this tank.
        if bulk_off_tank:
            bulk_verdict = check_pour(bulk_litres)
        else:
            _cap, _left = bulk_vessel_state(resin, station)
            bulk_verdict = check_pour(bulk_litres, capacity_l=_cap, remaining_l=_left)

        # The conversion stated out loud before the submit. The operator
        # knows they poured 200 kg; that it is 180 litres is the
        # application's claim, not theirs.
        if bulk_litres > 0:
            st.markdown(f"**{describe_pour(bottles_filled, bulk_each, bulk_unit, _dens, bulk_note, from_tank=not bulk_off_tank)}**")
        if bulk_off_tank:
            st.caption("This counts toward your shift and the plant's totals. "
                       "The tank level stays where it is, because that resin "
                       "came off it when the drum was filled.")
        if bulk_verdict["message"]:
            (st.error if bulk_verdict["blocked"] else st.warning)(bulk_verdict["message"])
    else:
        # Give the Good Units its own massive full-width input
        bottles_filled = st.number_input("✅ Good Units / Containers Filled", min_value=0, value=250, step=10,
                                         key="h_filled")

    # Scrap can share a row since they are smaller numbers
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        scrap_empty = st.number_input("🗑️ Scrap Empty", min_value=0, value=0, step=1, key="h_s_empty")
    with p_col2:
        scrap_filled = st.number_input("🗑️ Scrap Filled", min_value=0, value=0, step=1, key="h_s_filled")

    # ---------------------------------------------------------------
    # Check weight. Optional, never blocking, never pre-filled.
    #
    # Optional because a reading is a measurement, not a control: the lot
    # check stops the line because a wrong lot is a defect, but a heavy
    # cartridge is information. Make this mandatory and within a week it
    # is the target weight typed from memory on every log, and a column
    # full of 1110 is worse than an empty one because it looks like data.
    #
    # Never pre-filled for the same reason the run card had to stop
    # printing the lot it was hiding: a box that already contains the
    # right-looking answer gets accepted, not measured.
    #
    # One reading an hour is a sample of that hour, not an inspection of
    # one cartridge - which is why the analytics weight it by the units
    # logged alongside it.
    w_col1, w_col2 = st.columns([1, 2])
    with w_col1:
        check_weight = st.number_input(
            "⚖️ Check weight (g) — optional",
            min_value=0.0, max_value=99999.0, value=None, step=1.0,
            placeholder="leave blank if not weighed", key="h_weight",
            help="One cartridge off the scale. Skip it if you didn't weigh one — "
                 "the log submits either way.",
        )
    weight_reading = fill_weight.judge(check_weight, weight_spec)
    with w_col2:
        if check_weight is not None and weight_reading is None and weight_spec is None:
            st.caption("⚖️ Recorded, but there's no weight spec on file for this "
                       "resin yet, so there's nothing to compare it against.")
        elif weight_reading:
            _icon, _msg = fill_weight.describe(weight_reading)
            _tone = {"in": "#4ADE80", "over": "#FBBF24", "under": "#FBBF24"}.get(
                weight_reading["status"], "#94A3B8")
            st.markdown(
                f"<div style='margin-top:26px;color:{_tone};font-weight:600;'>"
                f"{_icon} {esc(_msg)}</div>", unsafe_allow_html=True)

    notes = st.text_area("Process Observations / Notes", placeholder="e.g. Target fill weight nominal...",
                         key="h_notes")

    st.markdown("<br>", unsafe_allow_html=True)
    # A bulk amount that cannot be true blocks the submit through the same
    # door the lot check uses, so there is one place on this screen that
    # says why the button is grey.
    if is_bulk and bulk_verdict["blocked"]:
        gate_blockers.append("enter an amount this vessel could actually have given out")
    _can_submit = gate_ok and not (is_bulk and bulk_verdict["blocked"])
    if gate_blockers:
        st.caption("Before you can submit: " + "; ".join(gate_blockers) + ".")
    # For the few seconds after a log lands, the button is not here at all
    # - a green block saying what was recorded stands in its place. See
    # components.submit_gate. This is the one screen where a second press
    # writes a second real pour, and on a shift where the confirmation was
    # not drawing, that is exactly what happened.
    _submit_free = submit_gate("pour")
    if _submit_free and st.button("🚀 SUBMIT POURING LOG", type="primary",
                                  use_container_width=True,
                                  disabled=not _can_submit):
        # Written to disk here rather than on every rerun while they type.
        if verification is not None and pending_photo is not None:
            verification["photo_filename"] = save_lot_photo(pending_photo)

        log_notes = (notes or "").strip()
        if extra_note:
            log_notes = f"{extra_note}\n{log_notes}".strip()

        # The write, with the outcome actually reported. On this plant's
        # network - which drops in parts of the building - "did that
        # submit?" is a real question, and a page that silently re-runs
        # answers it badly: an operator who is unsure submits again, and
        # a duplicated hourly count is worse than a missing one because
        # nothing about it looks wrong afterwards.
        _save_ok, _save_err = True, ""
        matched_run = False
        try:
            matched_run = add_hourly_log(
                operator_name=current_user,
                pump_station=station,
                shift=current_shift,
                cartridge_type=cart_code,
                resin_type=resin,
                lot_number=lot_num,
                bottles=int(bottles_filled),
                scrap_empty=int(scrap_empty),
                scrap_filled=int(scrap_filled),
                notes=log_notes,
                log_type="Hourly Bottle Count",
                verification=verification,
                weight=weight_reading,
                litres_poured=bulk_litres,
                pour_note=bulk_note,
                off_tank=bulk_off_tank,
            )
        except Exception as _e:
            _save_ok, _save_err = False, str(_e)[:160]

        if not _save_ok:
            save_state("failed", _save_err)
            st.stop()

        # A tank with nothing recorded on it is a blank, not a changeover,
        # so the log that was just written fills it in and the level starts
        # working without a manager opening a settings page. After the
        # write rather than before it: a resin picked and then corrected
        # would otherwise be adopted on the way past. Skipped on an
        # off-tank pour, which by definition did not come out of a vessel
        # on this station.
        if not bulk_off_tank:
            try:
                _adopted = crud.adopt_vessel_resin(
                    station, resin, operator=current_user, shift=current_shift)
                if _adopted:
                    flash(f"{_adopted} is now recorded as holding {resin}.", "🛢️")
            except Exception:
                pass

        # Arm the fast path only after a clean check. A mismatch or an
        # expired lot clears it, so the next log at this station starts
        # over with the full check.
        if gate_applies and verification is not None:
            _mem = st.session_state.setdefault("lot_gate_memory", {})
            if verification.get("result") == "verified":
                _prev = _mem.get(station) or {}
                _mem[station] = {
                    "expected": expected_lot,
                    "resin": resin,
                    "cart": cart_code,
                    "entered": verification.get("entered_lot", ""),
                    "ts": datetime.now(),
                    "by": current_user,
                    "since_full": (_prev.get("since_full", 0) + 1)
                                  if verification.get("check_level") == "fast" else 0,
                }
            else:
                _mem.pop(station, None)

        # Remember this submission so the operator can take it back if
        # they spot a typo in the next couple of minutes. Only the id and
        # the moment - everything else is re-read from the database, so a
        # stale session cannot delete the wrong row.
        try:
            _mine = get_production_logs_df()
            _mine = _mine[(_mine["operator_name"] == current_user)
                          & (_mine["pump_station"] == station)]
            if not _mine.empty:
                st.session_state["undo_log"] = {
                    "id": int(_mine.sort_values("id").iloc[-1]["id"]),
                    "at": datetime.now(),
                    "units": int(bottles_filled),
                }
        except Exception:
            st.session_state.pop("undo_log", None)

        if verification and verification.get("result") in ("mismatch", "expired"):
            flash("Logged and flagged for the manager — the lot did not check out.", "⚠️")
            crud.save_last_picks(current_user, station, cartridge, resin)
        if weight_reading and weight_reading.get("status") in ("over", "under"):
            flash(
                f"Weight {weight_reading['measured']:.0f} g is outside the band for "
                f"{resin} — recorded, and it shows on the manager's fill-weight view.",
                "⚖️")
        if matched_run:
            flash(f"Recorded {bottles_filled} units of {resin}. Credited to your active run.", "🧪")
            crud.save_last_picks(current_user, station, cartridge, resin)
        elif simple_mode:
            # The log is the product here, not a contribution to a run, so
            # a successful log is a success. It used to close with a
            # warning triangle and a note about a progress bar that this
            # plant does not have - every log, all shift.
            flash(f"Recorded {bottles_filled} units of {resin}.", "🧪")
            crud.save_last_picks(current_user, station, cartridge, resin)
        else:
            flash(
                f"Recorded {bottles_filled} units of {resin} to Analytics — "
                f"no active run matched this station/resin/lot, so it won't move a progress bar above.",
                "⚠️")

        # What the operator sees where the button was, for the next few
        # seconds. It names the pour rather than saying "saved", because
        # "saved" is what an operator doubts when they cannot see the log.
        if is_bulk and bulk_litres:
            _landed = (f"{bulk_litres:,.1f} L of {resin} into "
                       f"{bulk_note or 'containers'} at {station}")
        else:
            _landed = f"{bottles_filled} units of {resin} at {station}"
        lock_submit("pour", f"{_landed}, {datetime.now():%H:%M}")
        st.rerun()

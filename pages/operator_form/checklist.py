"""The hard gate: daily startup checklist.

Moved out of Operator_Form.py verbatim. This is the single riskiest block
on the page to get wrong - it is what stands between an operator and the
terminal each shift - so the split here is a pure relocation: the logic,
session_state keys, and control flow (including the st.stop() that halts
the rest of the page while the terminal is locked) are unchanged from the
original inline version.

render_checklist_gate(ctx) both renders the gate AND seeds
st.session_state["h_pump"] (the pump-station picker) before the pouring
tab ever runs - the checklist has to know which station it's certifying
before anything else on the page does. If the checklist is not yet
complete for this operator/shift/station, it calls st.stop() and this
function never returns.
"""
from datetime import date, datetime, timedelta

import streamlit as st

import crud
import external_links
from database import (
    add_cleanliness_audit,
    get_active_pumps,
    get_plant_settings,
    has_completed_daily_checklist,
    MAX_AUDIT_PHOTOS,
    set_cookie,
    submit_daily_checklist,
    flash,
)
from .shared import _vessel_label


def render_checklist_gate(ctx):
    """Only enforced for Operators and Packers, not Managers in Debug mode."""
    current_role = ctx.current_role
    current_user = ctx.current_user
    current_shift = ctx.current_shift
    cookie_manager = ctx.cookie_manager

    if current_role not in ("operator", "packer"):
        return

    # Which station the operator is standing at is part of the question. A
    # checklist certifies the condition of one pump - bins staged, station
    # clean - so someone moved to a different pump has certified nothing
    # about it and gets asked again. The selector below writes to the same
    # session_state key ("h_pump") the Hourly Pouring tab uses, so the pump
    # chosen here is the pump they end up logging against; there is only
    # ever one answer to "which station am I at".
    if current_role == "packer":
        _checklist_pumps = []
        checklist_station = "Pack-Out Station"
    else:
        _checklist_pumps = get_active_pumps() or ["New Pump #1"]
        if st.session_state.get("h_pump") not in _checklist_pumps:
            # The account knows where they were last, and it knows it before
            # any cookie comes back. This has to happen HERE rather than down
            # in the logging tab: the checklist decides which pump it is
            # certifying from this value, so seeding it later means an
            # operator returning gets asked to redo the checklist for a pump
            # they are not standing at.
            _remembered = crud.get_last_picks(current_user).get("station", "")
            _saved_station = cookie_manager.get(f"op_station_{current_user.replace(' ', '')}")
            st.session_state["h_pump"] = (
                _remembered if _remembered in _checklist_pumps
                else _saved_station if _saved_station in _checklist_pumps
                else _checklist_pumps[0])
        checklist_station = st.session_state["h_pump"]

    if not has_completed_daily_checklist(current_user, current_shift, checklist_station):
        st.error("🛑 **TERMINAL LOCKED: PRE-SHIFT VALIDATION REQUIRED**")
        st.info(
            f"Welcome, {current_user}. Complete the startup checklist for **{checklist_station}** "
            f"on **{current_shift}** before the production modules unlock.")

        if current_role != "packer":
            st.selectbox(
                "📍 Which pump station are you starting at?", _checklist_pumps, key="h_pump",
                help="Changing this switches which station's checklist you're completing — and "
                     "carries through to your logging tab, so you only answer it once.")

            # The one fact about this pump the app cannot work out for itself:
            # which physical tank it draws from. Asked here, once, where the
            # operator is standing at the pump and can read the tag off the
            # side of the vessel - and only when that pump has no tank on it
            # yet. Answered once, it never appears again, and no manager ever
            # has to open a settings page to link a reactor to a station.
            _chk_pump = st.session_state.get("h_pump", "")
            _vessels_here = crud.vessels_on_pump(_chk_pump)
            if not _vessels_here:
                _chk_opts = crud.vessels_for_pump_picker(_chk_pump)
                if _chk_opts:
                    _chk_map = {_vessel_label(v): v["reactor_name"] for v in _chk_opts}
                    st.session_state["_chk_vessel_map"] = _chk_map
                    st.selectbox(
                        "🛢️ Which vessel does this pump draw from?",
                        ["— I don't know —"] + list(_chk_map.keys()), key="chk_vessel",
                        help="Asked once per pump. It is how the tank level knows a pour "
                             "came out of this vessel and not the one beside it. If you are "
                             "not sure, leave it and tell your lead — your logs still record.")
                    st.caption("Read the tag off the side of the tank if there is one. "
                               "A tank shown as being on another pump can be moved here.")

        # --- Cookie check to survive page refreshes ---
        # Keyed by station as well as operator: moving to a new pump means a
        # new cleanliness photo of THAT pump, not a pass carried over from the
        # one they left.
        clean_cookie_name = f"clean_chk_{current_user.replace(' ', '')}_{checklist_station.replace(' ', '')}"
        clean_flag_key = f"pre_shift_clean_done_{checklist_station.replace(' ', '')}"

        # If the cookie has today's date, they already submitted the photo!
        if cookie_manager.get(clean_cookie_name) == str(date.today()):
            st.session_state[clean_flag_key] = True
        elif clean_flag_key not in st.session_state:
            st.session_state[clean_flag_key] = False

        st.markdown("### 📋 Daily Startup Checklist")

        # --- TEMPORARY: "already done" override for the old pumps ---
        # The checklist is scoped to a pump station name, on purpose - it
        # certifies the physical pump somebody is standing at, not the
        # operator in general. That falls apart on the twenty old pumps,
        # which don't have their own station names yet: two different
        # physical pumps can share one name in the system (so a checklist
        # nobody actually did at THIS pump reads as done), or the reverse.
        # Take this out once every old pump has its own row under IT Admin →
        # Pump Stations - at that point the per-station gate above is
        # correct on its own and this is just a way to skip it.
        with st.expander("🕒 Temporary: this pump was already checked today", expanded=False):
            st.caption(
                "Only for the old pumps, which don't have individual station "
                "names set up yet - so the system sometimes can't tell your "
                "pump apart from one a coworker already checked today. If "
                "that's what's happening, you can mark it done here instead "
                "of redoing the photo and boxes below.")
            already_who = st.text_input(
                "Who actually completed the checklist at this pump?",
                key=f"chk_already_who_{checklist_station.replace(' ', '')}",
                placeholder="e.g. Maria")
            if st.button("✅ Mark already done & unlock this terminal",
                         key=f"chk_already_btn_{checklist_station.replace(' ', '')}",
                         disabled=not already_who.strip()):
                add_cleanliness_audit(
                    audit_type="Startup Checklist — marked already done (pump not yet labeled)",
                    operator_name=current_user,
                    pump_station=checklist_station,
                    shift=current_shift,
                    resin_type="",
                    notes=(f"{current_user} unlocked {checklist_station} without "
                           f"redoing the checklist, saying it was already completed "
                           f"today by: {already_who.strip()}."),
                    is_spill=False,
                )
                submit_daily_checklist(current_user, current_shift, checklist_station)
                flash("Marked already done. Terminal unlocked.", "🔓")
                st.rerun()

        # --- STEP 1: THE AUTO-CHECK (CLEANLINESS AUDIT) ---
        if not st.session_state[clean_flag_key]:
            with st.expander("📸 Step 1: Perform & Submit Morning Cleanliness Check", expanded=True):
                st.caption("Submit your start-of-shift photo audit here to satisfy this requirement.")

                audit_station = checklist_station
                st.caption(f"Station: **{audit_station}** — set by the picker above.")
                audit_notes = st.text_area("Observations", placeholder="Station clean, ready for shift.",
                                           key="pre_notes")

                pre_types = ["png", "jpg", "jpeg", "webp"]
                pre_cam = st.camera_input("Capture live photo", key="pre_cam")
                pre_uploads = st.file_uploader("Or upload photos", type=pre_types,
                                               accept_multiple_files=True, key="pre_upload")
                pre_photos = ([pre_cam] if pre_cam is not None else []) + list(pre_uploads or [])
                if len(pre_photos) > MAX_AUDIT_PHOTOS:
                    st.caption(f"Up to {MAX_AUDIT_PHOTOS} photos per audit - keeping the first {MAX_AUDIT_PHOTOS}.")
                    pre_photos = pre_photos[:MAX_AUDIT_PHOTOS]

                # Prevent double-submission while the audit is being processed
                if "submitting_cleanliness" not in st.session_state:
                    st.session_state.submitting_cleanliness = False

                if st.session_state.submitting_cleanliness:
                    st.info("⏳ Submitting cleanliness audit... please wait.")
                elif st.button("💾 Submit Cleanliness Report", type="primary", width="stretch"):
                    if pre_photos:
                        st.session_state.submitting_cleanliness = True
                        try:
                            ok = add_cleanliness_audit(
                                audit_type="Start Of Shift (Cleanliness Check)",
                                operator_name=current_user,
                                pump_station=audit_station,
                                    shift=current_shift,
                                resin_type="",
                                notes=audit_notes,
                                is_spill=False,
                                uploaded_files=pre_photos
                            )
                            if ok:
                                # Flip the flag and save the cookie for today!
                                st.session_state[clean_flag_key] = True
                                set_cookie(cookie_manager, clean_cookie_name, str(date.today()),
                                                   expires_at=datetime.now() + timedelta(hours=12))

                                flash("Cleanliness audit recorded.", "📸")
                                st.session_state.submitting_cleanliness = False
                                st.rerun()
                            else:
                                st.error("❌ Failed to record cleanliness audit. Please try again.")
                                st.session_state.submitting_cleanliness = False
                        except Exception as e:
                            st.error(f"❌ Error submitting audit: {str(e)}")
                            st.session_state.submitting_cleanliness = False
                    else:
                        st.warning("⚠️ A photo is required for the pre-shift audit.")
        else:
            # The Auto-Check Success State!
            st.toast("✅ **Step 1: Morning Cleanliness Check — LOGGED & COMPLETED**")

        # --- STEP 2: MANUAL CHECKS & FINAL UNLOCK ---
        # The pump form button belongs HERE, not only above the logging tabs:
        # the first checkbox below asks the operator to have filled that form
        # in, and this screen is the locked one - nothing after the st.stop()
        # at the end of this block renders until it is cleared. The button was
        # originally placed above the tab strip, which is exactly the part of
        # the page an operator standing at the checklist could not see, so an
        # address entered in IT Admin appeared to do nothing.
        _lock_url, _lock_problem = external_links.normalise(
            get_plant_settings().get("pump_form_url", ""))
        if _lock_url:
            st.markdown("#### Step 2: Final Verification")
            st.link_button(
                "📱 " + external_links.label_or_default(
                    get_plant_settings().get("pump_form_label", "")),
                _lock_url, use_container_width=True,
                help="Opens the station checksheet in a new tab. Come back here "
                     "and tick the box once it is submitted.")
        with st.form("startup_checklist_form"):
            if not _lock_url:
                st.markdown("#### Step 2: Final Verification")

            # 1. Universal QR Check
            qr_check = st.checkbox("📱 I have scanned the daily station QR Code and submitted the external checksheet.")

            # 2. Dynamic Material Check based on Role
            if current_role == "packer":
                mat_text = "📦 I have verified all labels, boxes, and necessary materials are staged for my pack-out run."
            else:
                mat_text = "🛒 I have verified all bins of empty cartridges and receiving carts for filled bottles are staged for my run."

            mat_check = st.checkbox(mat_text)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("🔓 Submit Validation & Unlock Terminal", type="primary", use_container_width=True):
                # Verify ALL manual boxes are checked AND the auto-check is done
                if qr_check and mat_check:
                    if st.session_state.get(clean_flag_key):
                        submit_daily_checklist(current_user, current_shift, checklist_station)
                        # Link the vessel on the way through, if they answered.
                        _picked = st.session_state.get("chk_vessel", "")
                        if _picked and not _picked.startswith("—"):
                            _target = st.session_state.get(
                                "_chk_vessel_map", {}).get(_picked, _picked)
                            crud.link_vessel_to_pump(_target, checklist_station)
                        flash("Startup checklist recorded. Terminal unlocked.", "🔓")
                        # The station is certified and the screen opens up.
                        # That is a real event, once a shift, so the laser
                        # passes down the form as it happens. Set here and
                        # consumed on the next render, so it plays exactly
                        # once and never on an ordinary log.
                        st.session_state["_unlock_sweep"] = True

                        # Clean up the session state flag
                        del st.session_state[clean_flag_key]
                        st.rerun()
                    else:
                        st.error(
                            "⚠️ You must complete and submit the Morning Cleanliness Check (Step 1) above before unlocking.")
                else:
                    st.warning("⚠️ You must check ALL manual verification items in Step 2.")

        # This function strictly stops the rest of the page from rendering until the form is passed!
        st.stop()

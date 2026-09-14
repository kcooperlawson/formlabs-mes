"""Audit tab: cleanliness, changeover & spill photo audit.

Moved out of Operator_Form.py verbatim. Still free-running widgets (not a
form) — the live photo preview below the uploader needs to update as soon
as a photo is attached, which is exactly the kind of cross-widget
behavior called out as the reason this tab hasn't been converted yet in
the wider perf pass.
"""
import streamlit as st

from database import add_cleanliness_audit, flash, MAX_AUDIT_PHOTOS


def render(ctx):
    current_user = ctx.current_user
    current_shift = ctx.current_shift
    active_pumps = ctx.active_pumps
    my_station = ctx.my_station

    st.subheader("📸 Cleanliness, Changeover & Spill Photo Audit")
    st.caption("Document station readiness, pump changeovers, end-of-shift washdowns, or resin spills.")

    a_col1, a_col2 = st.columns(2)
    with a_col1:
        audit_type = st.selectbox(
            "Audit Checklist Event",
            ("Start Of Shift (Cleanliness Check)", "End Of Shift (Cleanliness Check)", "Station / Pump Transfer Check", "Resin Spill / Containment Issue")
        )
        _aud_pump_idx = active_pumps.index(my_station) if my_station in active_pumps else 0
        audit_station = st.selectbox("Pump / Workstation", active_pumps, index=_aud_pump_idx, key="aud_pump")
        is_spill_flag = st.checkbox("⚠️ Check if this is an active resin spill / leak incident", value=("Spill" in audit_type))

    with a_col2:
        audit_notes = st.text_area("Audit Observations / Cleanliness Verification", placeholder="e.g. Moving from Alpha Fast to White V5. Dispensing nozzles flushed and drip trays clear.", key="aud_notes")

    st.markdown("#### 📷 Attach Inspection Photos")
    st.caption("The first photo is the main one; add more if the situation deserves it.")

    aud_types = ["png", "jpg", "jpeg", "webp", "heic", "heif"]
    aud_cam = st.camera_input("Take a photo with this phone's camera")
    aud_uploads = st.file_uploader("Or upload photos", type=aud_types,
                                   accept_multiple_files=True, key="mobile_photo_upload")
    aud_photos = ([aud_cam] if aud_cam is not None else []) + list(aud_uploads or [])
    if len(aud_photos) > MAX_AUDIT_PHOTOS:
        st.caption(f"Up to {MAX_AUDIT_PHOTOS} photos per audit - keeping the first {MAX_AUDIT_PHOTOS}.")
        aud_photos = aud_photos[:MAX_AUDIT_PHOTOS]

    if aud_photos:
        st.image(aud_photos[0], caption="Main photo preview", width=300)
        if len(aud_photos) > 1:
            st.caption(f"{len(aud_photos) - 1} extra photo(s) will be attached.")

    # Prevent double-submission while the audit is being processed
    if "submitting_photo_audit" not in st.session_state:
        st.session_state.submitting_photo_audit = False

    if st.session_state.submitting_photo_audit:
        st.info("⏳ Submitting photo audit... please wait.")
    elif st.button("💾 Submit Cleanliness & Photo Audit", type="primary", width="stretch"):
        st.session_state.submitting_photo_audit = True
        try:
            ok = add_cleanliness_audit(
                audit_type=audit_type,
                operator_name=current_user,
                pump_station=audit_station,
                shift=current_shift,
                resin_type="",
                notes=audit_notes,
                is_spill=is_spill_flag,
                uploaded_files=aud_photos
            )
            if ok:
                flash("Photo audit recorded.", "📸")
                st.session_state.submitting_photo_audit = False
                st.rerun()
            else:
                st.error("❌ Failed to record photo audit. Please try again.")
                st.session_state.submitting_photo_audit = False
        except Exception as e:
            st.error(f"❌ Error submitting photo audit: {str(e)}")
            st.session_state.submitting_photo_audit = False

"""Packing tab (managers/admins in debug mode, and packers).

Moved out of Operator_Form.py verbatim.
"""
from datetime import datetime

import streamlit as st

from components import lock_submit, submit_gate
from database import add_hourly_log, flash, get_all_resin_specs_df
from resin_palette import resin_chip


def render(ctx):
    current_user = ctx.current_user
    current_shift = ctx.current_shift
    resin_colour_map = ctx.resin_colour_map

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📦 1. Packing Details")
    pack_station = "Pack-Out Station"
    st.info("Location: **End-of-Line / Pack-Out**")

    pack_cartridge = st.selectbox("Container Format",
                                  ("V2 (1L Cartridge)", "V1 (1L Cartridge)", "RPS (5L Bulk Jug)", "Pigment"),
                                  key="p_cart")
    p_cart_code = "RPS" if "RPS" in pack_cartridge else (
        "V1" if "V1" in pack_cartridge else ("Pigment" if "Pigment" in pack_cartridge else "V2"))

    # Same reasoning as the Hourly Pouring tab: never let the Container
    # Format filter hide a resin from the picker just because its
    # master spec isn't registered for this specific format.
    p_all_specs_df = get_all_resin_specs_df("ALL")
    p_resin_names = sorted(p_all_specs_df["resin_name"].unique().tolist()) if not p_all_specs_df.empty else []

    pack_resin = st.selectbox("Resin Formulation", p_resin_names, key="p_resin")
    if pack_resin:
        st.markdown(resin_chip(pack_resin, resin_colour_map.get(str(pack_resin)), size="lg"),
                    unsafe_allow_html=True)

    p_cart_matched = get_all_resin_specs_df(p_cart_code)
    p_cart_matched = p_cart_matched[p_cart_matched["resin_name"] == pack_resin] if not p_cart_matched.empty else p_cart_matched
    matched_pack = p_cart_matched if not p_cart_matched.empty else p_all_specs_df[p_all_specs_df["resin_name"] == pack_resin]
    units_per_skid = 500
    if not matched_pack.empty:
        units_per_skid = int(matched_pack.iloc[0].get("units_per_skid", 500))

    pack_lot = st.text_input("Batch Lot Number Being Packed", value=f"LOT-{datetime.now().strftime('%Y%m%d')}-01",
                             key="p_lot")

    st.markdown("---")
    st.markdown("#### 📊 2. Units Packed")

    units_packed = st.number_input("✅ Total Good Units Packed", min_value=1, value=units_per_skid, step=50,
                                   key="p_filled")
    skids_calculated = units_packed / units_per_skid if units_per_skid > 0 else 0
    st.caption(f"Equates to: **{skids_calculated:.2f} Skids** *(Based on {units_per_skid} units/skid)*")

    pack_notes = st.text_area("Packing Notes / Box Issues", placeholder="e.g. 2 partial boxes added to skid.",
                              key="p_notes")

    st.markdown("<br>", unsafe_allow_html=True)
    # Same lock as the pouring tab. A packing count is as easy to send
    # twice, and just as hard to spot afterwards.
    if submit_gate("pack") and st.button("📦 SUBMIT PACKING LOG", type="primary",
                                         use_container_width=True):
        add_hourly_log(
            operator_name=current_user,
            pump_station=pack_station,
            shift=current_shift,
            cartridge_type=p_cart_code,
            resin_type=pack_resin,
            lot_number=pack_lot,
            bottles=int(units_packed),
            scrap_empty=0,
            scrap_filled=0,
            notes=pack_notes,
            log_type="Packing Count"
        )
        flash(f"Packing saved. Recorded {units_packed} units.", "📦")
        lock_submit("pack", f"{units_packed} units of {pack_resin} packed, "
                            f"{datetime.now():%H:%M}")
        st.rerun()

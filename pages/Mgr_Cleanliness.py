
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from datetime import datetime, timedelta
from database import get_cleanliness_audits_df, delete_cleanliness_audit, UPLOAD_DIR, do_logout

st.set_page_config(page_title="Cleanliness Gallery | Formlabs MES", page_icon="📸", layout="wide")
from database import esc


try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Default Dark"), THEMES["Default Dark"]), unsafe_allow_html=True)

if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
from ui_shell import render_shell
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

st.subheader("📸 Cleanliness & Station Photo Gallery")

df_audits = get_cleanliness_audits_df()

k1, k2, k3, k4, k5 = st.columns(5)
total_audits = len(df_audits) if not df_audits.empty else 0
start_checks = len(df_audits[df_audits["audit_type"].str.contains("Start", na=False)]) if not df_audits.empty else 0
end_checks = len(df_audits[df_audits["audit_type"].str.contains("End", na=False)]) if not df_audits.empty else 0
transfers = len(df_audits[df_audits["audit_type"].str.contains("Transfer", na=False)]) if not df_audits.empty else 0
spills = len(df_audits[df_audits["is_spill"] == "Yes"]) if not df_audits.empty else 0
with k1: st.metric("All Photo Audits", f"{total_audits} records")
with k2: st.metric("Start Shift Checks", f"{start_checks} verified")
with k3: st.metric("End Shift Checks", f"{end_checks} shutdowns")
with k4: st.metric("Pump Transfers", f"{transfers} line changes")
with k5: st.metric("Spills / Issues", f"{spills} flags", delta="Attention Needed" if spills > 0 else "Clear", delta_color="inverse")
st.markdown("---")

if not df_audits.empty:
    ac1, ac2, ac3 = st.columns(3)
    for idx, row in df_audits.iterrows():
        target_col = ac1 if (idx % 3 == 0) else (ac2 if idx % 3 == 1 else ac3)
        with target_col:
            with st.container():
                badge_color = "#EF4444" if row["is_spill"] == "Yes" else "#38BDF8"
                st.markdown(
                    f"<div style='border:1px solid #334155; border-radius:8px; padding:12px; background-color:#0F172A; margin-bottom:8px;'>"
                    f"<b style='color:{badge_color}; font-size:0.85rem;'>● {esc(row['audit_type'])}</b>"
                    f"<span style='float:right; font-size:0.8rem; color:#94A3B8;'>{esc(row['pump_station'])}</span><br>",
                    unsafe_allow_html=True)
                if row["image_filename"]:
                    img_path = os.path.join(UPLOAD_DIR, str(row["image_filename"]))
                    if os.path.exists(img_path):
                        st.image(img_path, use_container_width=True)
                    else:
                        st.caption("🖼️ Image file not found on disk.")
                else:
                    st.caption("📝 Log entry without image attachment.")
                st.caption(f"📅 **Time:** `{row['timestamp']}` | 👤 **Operator:** {row['operator_name']}")
                st.markdown(f"*{row['notes'] if row['notes'] else 'No additional operator notes logged.'}*")
                st.markdown("</div>", unsafe_allow_html=True)
                if st.button(f"🗑️ Delete Photo Audit #{row['id']}", key=f"del_gal_aud_{row['id']}", use_container_width=True):
                    delete_cleanliness_audit(row["id"])
                    st.success(f"Deleted Audit #{row['id']}")
                    st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)

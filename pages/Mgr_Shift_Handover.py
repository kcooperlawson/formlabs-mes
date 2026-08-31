
import os
import sys
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
import extra_streamlit_components as stx

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_plant_settings, get_production_logs_df,do_logout

st.set_page_config(page_title="Shift Handover | Formlabs MES", page_icon="📤", layout="wide")


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

# ===================================================================

st.subheader("📤 Automated Shift Handover & PDF Generation")

current_settings = get_plant_settings()
default_list = current_settings.get("handover_emails", "")
df_logs = get_production_logs_df()

pdf_col1, pdf_col2 = st.columns(2)
with pdf_col1:
    recipient_emails = st.text_input("Recipient Email Addresses", value=default_list)
with pdf_col2:
    selected_pdf_theme = st.selectbox(
        "🎨 Select PDF Report Theme / Layout Style:",
        ["Formlabs Forge (Default Dark)", "Executive Clean (Print-Friendly)", "Cyberpunk SCADA (High-Tech)"]
    )

if st.button("📄 Generate & Dispatch Shift Report", type="primary", use_container_width=True):
    from fpdf import FPDF
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email import encoders

    today_str = date.today().strftime("%Y-%m-%d")
    df_today = df_logs[df_logs["date"].astype(str) == today_str] if not df_logs.empty else pd.DataFrame()
    pour_df = df_today[df_today["log_type"] == "Hourly Bottle Count"] if not df_today.empty else pd.DataFrame()
    pack_df = df_today[df_today["log_type"] == "Packing Count"] if not df_today.empty else pd.DataFrame()

    total_poured = int(pour_df["bottles_filled"].sum()) if not pour_df.empty else 0
    total_packed = int(pack_df["bottles_filled"].sum()) if not pack_df.empty else 0
    total_scrap = int(pour_df["scrap_empty"].sum() + pour_df["scrap_filled"].sum()) if not pour_df.empty else 0

    PDF_THEMES = {
        "Formlabs Forge (Default Dark)": {"bg_color": (15, 23, 42), "text_color": (248, 250, 252), "sub_color": (148, 163, 184), "accent_color": (234, 88, 12), "card_bg": (30, 41, 59), "font": "Arial"},
        "Executive Clean (Print-Friendly)": {"bg_color": (255, 255, 255), "text_color": (15, 23, 42), "sub_color": (71, 85, 105), "accent_color": (2, 132, 199), "card_bg": (241, 245, 249), "font": "Arial"},
        "Cyberpunk SCADA (High-Tech)": {"bg_color": (9, 1, 23), "text_color": (0, 255, 204), "sub_color": (168, 85, 247), "accent_color": (240, 0, 255), "card_bg": (24, 9, 48), "font": "Courier"}
    }
    theme = PDF_THEMES[selected_pdf_theme]

    class ThemedPDF(FPDF):
        def __init__(self, theme_cfg):
            super().__init__()
            self.theme = theme_cfg
        def header(self):
            self.set_fill_color(*self.theme["bg_color"])
            self.rect(0, 0, 210, 297, "F")
            self.set_fill_color(*self.theme["accent_color"])
            self.rect(0, 0, 210, 6, "F")

    pdf = ThemedPDF(theme)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font(theme["font"], 'B', 18)
    pdf.set_text_color(*theme["accent_color"])
    pdf.cell(0, 10, txt="FORMLABS PLANT SHIFT HANDOVER", ln=True, align='L')
    pdf.set_font(theme["font"], 'I', 10)
    pdf.set_text_color(*theme["sub_color"])
    pdf.cell(0, 6, txt=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Theme: {selected_pdf_theme}", ln=True, align='L')
    pdf.ln(10)

    metrics = [
        ("Total Poured", f"{total_poured:,} L"), ("Total Packed", f"{total_packed:,} Units"),
        ("Floor WIP", f"{total_poured - total_packed:,} Pending"), ("Total Scrap", f"{total_scrap:,} Units")
    ]

    pdf.set_font(theme["font"], 'B', 11)
    for i, (label, val) in enumerate(metrics):
        x = 10 if (i % 2 == 0) else 105
        y = pdf.get_y()
        pdf.set_fill_color(*theme["card_bg"])
        pdf.rect(x, y, 90, 22, "F")
        pdf.set_xy(x + 5, y + 3)
        pdf.set_text_color(*theme["sub_color"])
        pdf.cell(80, 5, txt=label.upper(), ln=False)
        pdf.set_xy(x + 5, y + 10)
        pdf.set_text_color(*theme["text_color"])
        pdf.cell(80, 8, txt=val, ln=False)
        if i % 2 == 1: pdf.ln(26)

    pdf_filename = f"Shift_Handover_{today_str}.pdf"
    pdf.output(pdf_filename)
    st.success("✅ Themed PDF Successfully Generated!")

    with open(pdf_filename, "rb") as pdf_file:
        st.download_button("⬇️ Download PDF Report Manually", data=pdf_file, file_name=pdf_filename, mime="application/pdf", use_container_width=True)

    if recipient_emails.strip():
        try:
            sender_email = os.getenv("SENDER_EMAIL") or os.getenv("EMAIL_USER", "")
            sender_password = os.environ.get("EMAIL_PASS")
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_emails
            msg['Subject'] = f"Formlabs Shift Handover - {today_str}"
            msg.attach(MIMEText(f"Attached is the automated shift handover report for {today_str}.", 'plain'))
            with open(pdf_filename, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {pdf_filename}")
            msg.attach(part)
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            st.success(f"📧 Shift Handover Report successfully emailed to: {recipient_emails}")
        except Exception as e:
            st.error(f"Failed to send email: {str(e)}")

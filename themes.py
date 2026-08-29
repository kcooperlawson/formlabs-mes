# themes.py - Central Style Library for Formlabs MES

# --- UNIVERSAL UI OVERRIDES (Applies to all themes automatically) ---
BASE_UI_CSS = """
<style>

        /* Force zero height and absolute invisibility on the multi-page container */
[data-testid="stSidebarNav"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    max-height: 0px !important;
    overflow: hidden !important;
}

        /* COMPLETELY DISABLE NATIVE SIDEBAR NAVIGATION */
[data-testid="stSidebarNav"] {
    display: none !important;
}

    /* HIDE TV DASHBOARD FROM NATIVE SIDEBAR MENU */
    [data-testid="stSidebarNav"] a[href*="Tv_Dashboard"],
    [data-testid="stSidebarNav"] li:has(a[href*="Tv_Dashboard"]) {
        display: none !important;
    }
    
    /* HIDE STREAMLIT DEPLOY BUTTON & 3-DOT MENU ONLY */
    [data-testid="stAppDeployButton"] { display: none !important; }

    /* Hide the 3-dot menu (MainMenu) */
    #MainMenu { visibility: hidden !important; }



    /* 1. UNIVERSAL PAGE LINKS (TOP NAV) */
    /* ANTI-SQUISH NAV BUTTONS (For 7-Column God Mode) */
    [data-testid="stPageLink-NavLink"] {
        padding-left: 0.2rem !important;
        padding-right: 0.2rem !important;
    }
    [data-testid="stPageLink-NavLink"] p {
        font-size: 0.82rem !important;
        white-space: nowrap !important;
        letter-spacing: -0.01em !important;
    }
    .stPageLink a {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        padding: 10px 15px !important;
        text-decoration: none !important;
        transition: all 0.2s ease !important;
    }
    .stPageLink a:hover {
        background-color: rgba(255, 255, 255, 0.15) !important;
        border-color: currentColor !important;
        transform: translateY(-2px);
    }
    .stPageLink p {
        font-size: 1.05rem !important;
        font-weight: 800 !important;
    }

    /* 2. UNIVERSAL SLIDABLE IN-PAGE TABS (MODERN PILL BUTTONS) */
    div[data-testid="stTabs"] > div > div > div[data-baseweb="tab-list"] {
        display: flex !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
        padding-bottom: 10px !important; 
        scroll-behavior: smooth !important;
        -webkit-overflow-scrolling: touch !important; 
    }
    div[data-testid="stTabs"] > div > div > div[data-baseweb="tab-list"]::-webkit-scrollbar {
        display: none !important; 
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        white-space: nowrap !important; 
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 30px !important; 
        padding: 10px 22px !important;
        margin-right: 4px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"]:hover {
        background-color: rgba(255, 255, 255, 0.12) !important;
        transform: translateY(-2px) !important;
        border-color: currentColor !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.15) !important;
        border: 1px solid currentColor !important;
        box-shadow: inset 0 0 10px currentColor, 0 4px 15px rgba(0,0,0,0.3) !important;
        transform: translateY(-2px) !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] p {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: #94A3B8 !important; 
        margin: 0 !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] p {
        color: #FFFFFF !important;
        font-weight: 900 !important;
        text-shadow: 0 0 8px currentColor !important;
    }
    div[data-testid="stTabs"] div[data-baseweb="tab-highlight"] {
        display: none !important; 
    }
</style>
"""

# --- THEME DICTIONARY ---
THEMES = {
    "Default Dark": """
    <style>
        .stApp { background-color: #02040A !important; color: #E2E8F0 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: linear-gradient(180deg, #0A1224 0%, #050914 100%); border: 1px solid #162643; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.7); }
        .system-badge { background: rgba(0, 210, 255, 0.08); color: #00D2FF; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(0, 210, 255, 0.25); text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: linear-gradient(180deg, #091224 0%, #050B17 100%); border: 1px solid #142542; border-radius: 8px; padding: 12px 16px; min-height: 96px; transition: all 0.3s ease; }
        .telemetry-grid-card:hover { transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0, 210, 255, 0.15), 0 4px 14px rgba(0, 0, 0, 0.6); border-color: #00D2FF; }
        .telemetry-label { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; color: #64748B; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; }
        .stTextInput > div > div > input { background-color: #0B1220 !important; color: #00D2FF !important; border: 1px solid #1E293B !important; border-radius: 6px !important; font-family: monospace !important; letter-spacing: 0.05em; }
        .stButton>button { background: linear-gradient(180deg, #0066FF 0%, #0044CC 100%) !important; color: #FFFFFF !important; font-weight: 800 !important; border: 1px solid #00D2FF !important; border-radius: 6px !important; box-shadow: 0 0 10px rgba(0, 102, 255, 0.4) !important; transition: all 0.2s ease !important; text-transform: uppercase; letter-spacing: 0.1em; }
        .stButton>button:hover { background: linear-gradient(180deg, #0080FF 0%, #0055FF 100%) !important; box-shadow: 0 0 20px rgba(0, 210, 255, 0.8) !important; text-shadow: 0 0 5px rgba(255,255,255,0.8); }
        .filter-section-card { background: #0B1220; border: 1px solid #1E293B; border-radius: 8px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #050B14 !important; border-right: 1px solid #162643 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #94A3B8 !important; font-weight: 600 !important; border-radius: 8px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #142542 !important; color: #00D2FF !important; transform: translateX(5px) !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: linear-gradient(90deg, #0066FF 0%, #00D2FF 100%) !important; color: #FFFFFF !important; font-weight: 900 !important; box-shadow: 0 4px 12px rgba(0, 210, 255, 0.3) !important; }
    </style>
    """ + BASE_UI_CSS,

    "Neon Cyberpunk": """
    <style>
        .stApp { background-color: #090117 !important; color: #E2E8F0 !important; font-family: "Courier New", Courier, monospace !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #000000; border: 1px solid #F000FF; border-radius: 0px; margin-bottom: 16px; box-shadow: 0 0 15px rgba(240, 0, 255, 0.5); }
        .system-badge { background: transparent; color: #00FFCC; font-size: 0.85rem; font-weight: 900; letter-spacing: 0.2em; padding: 4px 10px; border: 1px solid #00FFCC; text-transform: uppercase; margin-left: 14px; text-shadow: 0 0 5px #00FFCC; }
        .telemetry-grid-card { background: #000000; border: 1px solid #F000FF; border-radius: 0px; padding: 12px 16px; min-height: 96px; border-left: 4px solid #00FFCC; transition: all 0.3s ease; }
        .telemetry-grid-card:hover { transform: translateY(-5px); box-shadow: 0 0 20px rgba(0, 255, 204, 0.3); border-color: #00FFCC; }
        .telemetry-label { font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; color: #F000FF; text-transform: uppercase; text-shadow: 0 0 2px #F000FF; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #00FFCC; line-height: 1.2; text-shadow: 0 0 8px #00FFCC; }
        .stTextInput > div > div > input { background-color: #000000 !important; color: #00FFCC !important; border: 1px dashed #F000FF !important; border-radius: 0px !important; font-family: monospace !important; letter-spacing: 0.1em; }
        .stButton>button { background: transparent !important; color: #00FFCC !important; font-weight: 900 !important; border: 2px solid #00FFCC !important; border-radius: 0px !important; box-shadow: 0 0 10px rgba(0, 255, 204, 0.4), inset 0 0 10px rgba(0, 255, 204, 0.2) !important; text-transform: uppercase; letter-spacing: 0.15em; }
        .stButton>button:hover { background: #00FFCC !important; color: #000000 !important; box-shadow: 0 0 25px rgba(0, 255, 204, 1) !important; }
        .filter-section-card { background: #05000A; border: 1px dashed #F000FF; border-radius: 0px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px solid #F000FF !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #F000FF !important; font-weight: 600 !important; border-radius: 0px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #1A002A !important; color: #00FFCC !important; transform: translateX(5px) !important; border-left: 2px solid #00FFCC !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #F000FF !important; color: #000000 !important; font-weight: 900 !important; box-shadow: 0 0 15px rgba(240, 0, 255, 0.5) !important; }
    </style>
    """ + BASE_UI_CSS,

    "Formlabs Forge": """
    <style>
        .stApp { background-color: #0F172A !important; color: #F8FAFC !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #1E293B; border: 1px solid #334155; border-radius: 8px; margin-bottom: 16px; border-bottom: 3px solid #EA580C; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        .system-badge { background: rgba(234, 88, 12, 0.15); color: #F97316; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 4px; border: 1px solid #EA580C; text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px; min-height: 96px; transition: all 0.2s ease; border-left: 4px solid #94A3B8; }
        .telemetry-grid-card:hover { transform: translateX(5px); border-left: 4px solid #EA580C; background: #0F172A; box-shadow: -4px 4px 10px rgba(0,0,0,0.4); }
        .telemetry-label { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; color: #CBD5E1; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; }
        .stTextInput > div > div > input { background-color: #1E293B !important; color: #F97316 !important; border: 1px solid #475569 !important; border-radius: 4px !important; font-weight: 600; }
        .stTextInput > div > div > input:focus { border-color: #EA580C !important; box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.2) !important; }
        .stButton>button { background: #EA580C !important; color: #FFFFFF !important; font-weight: 800 !important; border: none !important; border-radius: 4px !important; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3) !important; transition: all 0.2s ease !important; text-transform: uppercase; letter-spacing: 0.1em; }
        .stButton>button:hover { background: #F97316 !important; box-shadow: 0 6px 12px rgba(234, 88, 12, 0.4) !important; }
        .filter-section-card { background: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #0F172A !important; border-right: 1px solid #334155 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #94A3B8 !important; font-weight: 600 !important; border-radius: 6px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #1E293B !important; color: #EA580C !important; transform: translateX(5px) !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #EA580C !important; color: #FFFFFF !important; font-weight: 900 !important; box-shadow: 0 4px 8px rgba(234, 88, 12, 0.3) !important; }
    </style>
    """ + BASE_UI_CSS,

    "The Matrix": """
    <style>
        .stApp { background-color: #000000 !important; color: #00FF41 !important; font-family: "Courier New", Courier, monospace !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #000000; border: 1px solid #00FF41; border-radius: 0px; margin-bottom: 16px; box-shadow: 0 0 10px rgba(0, 255, 65, 0.2); }
        .system-badge { background: #000000; color: #00FF41; font-size: 0.85rem; font-weight: bold; letter-spacing: 0.2em; padding: 4px 10px; border: 1px solid #00FF41; text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: #000000; border: 1px solid #005500; border-radius: 0px; padding: 12px 16px; min-height: 96px; transition: all 0.2s ease; }
        .telemetry-grid-card:hover { border: 1px solid #00FF41; box-shadow: 0 0 15px rgba(0, 255, 65, 0.3); transform: scale(1.02); }
        .telemetry-label { font-size: 0.75rem; font-weight: bold; letter-spacing: 0.15em; color: #008800; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: bold; color: #00FF41; line-height: 1.2; text-shadow: 0 0 5px #00FF41; }
        .stTextInput > div > div > input { background-color: #000000 !important; color: #00FF41 !important; border: 1px solid #00FF41 !important; border-radius: 0px !important; font-family: monospace !important; letter-spacing: 0.1em; }
        .stButton>button { background: #000000 !important; color: #00FF41 !important; font-weight: bold !important; border: 1px solid #00FF41 !important; border-radius: 0px !important; transition: all 0.2s ease !important; text-transform: uppercase; letter-spacing: 0.1em; }
        .stButton>button:hover { background: #00FF41 !important; color: #000000 !important; box-shadow: 0 0 15px #00FF41 !important; }
        .filter-section-card { background: #000000; border: 1px dotted #00FF41; border-radius: 0px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px dotted #00FF41 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #008800 !important; font-weight: 600 !important; border-radius: 0px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #002200 !important; color: #00FF41 !important; transform: translateX(5px) !important; border-left: 2px solid #00FF41 !important;}
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #00FF41 !important; color: #000000 !important; font-weight: 900 !important; box-shadow: 0 0 15px rgba(0, 255, 65, 0.4) !important; }
    </style>
    """ + BASE_UI_CSS,

    "Vaporwave 1984": """
    <style>
        .stApp { background-color: #1A0B2E !important; color: #E0B0FF !important; font-family: "Trebuchet MS", sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: linear-gradient(90deg, #4A00E0 0%, #8E2DE2 100%); border: 2px solid #00FFFF; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 4px 15px rgba(0, 255, 255, 0.4); }
        .system-badge { background: #FF007F; color: #FFFFFF; font-size: 0.85rem; font-weight: 900; letter-spacing: 0.2em; padding: 4px 10px; border-radius: 4px; text-transform: uppercase; margin-left: 14px; box-shadow: 0 0 10px #FF007F; }
        .telemetry-grid-card { background: #2B1055; border: 1px solid #FF007F; border-radius: 12px; padding: 12px 16px; min-height: 96px; transition: all 0.3s ease; box-shadow: inset 0 0 15px rgba(255, 0, 127, 0.2); }
        .telemetry-grid-card:hover { transform: translateY(-5px); border-color: #00FFFF; box-shadow: 0 8px 20px rgba(0, 255, 255, 0.4); }
        .telemetry-label { font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; color: #00FFFF; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FF007F; line-height: 1.2; text-shadow: 2px 2px #4A00E0; }
        .stTextInput > div > div > input { background-color: #2B1055 !important; color: #00FFFF !important; border: 2px solid #FF007F !important; border-radius: 8px !important; letter-spacing: 0.05em; font-weight: bold; }
        .stButton>button { background: linear-gradient(45deg, #FF007F, #4A00E0) !important; color: #FFFFFF !important; font-weight: 900 !important; border: 2px solid #00FFFF !important; border-radius: 8px !important; box-shadow: 0 4px 10px rgba(255, 0, 127, 0.5) !important; text-transform: uppercase; letter-spacing: 0.15em; }
        .stButton>button:hover { background: linear-gradient(45deg, #00FFFF, #4A00E0) !important; box-shadow: 0 0 20px #00FFFF !important; color: #000000 !important; }
        .filter-section-card { background: #2B1055; border: 2px solid #4A00E0; border-radius: 12px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #1A0B2E !important; border-right: 2px solid #4A00E0 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #E0B0FF !important; font-weight: 600 !important; border-radius: 8px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #2B1055 !important; color: #00FFFF !important; transform: translateX(5px) !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: linear-gradient(45deg, #FF007F, #4A00E0) !important; color: #FFFFFF !important; font-weight: 900 !important; box-shadow: 0 4px 15px rgba(255, 0, 127, 0.5) !important; border: 1px solid #00FFFF !important; }
    </style>
    """ + BASE_UI_CSS,

    "Crimson Alert": """
    <style>
        .stApp { background-color: #0A0000 !important; color: #FFB3B3 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #1A0000; border: 1px solid #660000; border-radius: 8px; margin-bottom: 16px; border-bottom: 3px solid #FF0000; box-shadow: 0 4px 20px rgba(255, 0, 0, 0.2); }
        .system-badge { background: rgba(255, 0, 0, 0.15); color: #FF3333; font-size: 0.75rem; font-weight: 900; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 4px; border: 1px solid #FF0000; text-transform: uppercase; margin-left: 14px; text-shadow: 0 0 5px #FF0000; }
        .telemetry-grid-card { background: #120000; border: 1px solid #330000; border-radius: 8px; padding: 12px 16px; min-height: 96px; transition: all 0.2s ease; border-left: 4px solid #660000; }
        .telemetry-grid-card:hover { transform: translateX(5px); border-left: 4px solid #FF0000; background: #1A0000; box-shadow: -4px 4px 15px rgba(255,0,0,0.3); }
        .telemetry-label { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; color: #CC6666; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; }
        .stTextInput > div > div > input { background-color: #120000 !important; color: #FF3333 !important; border: 1px solid #660000 !important; border-radius: 4px !important; font-weight: 600; }
        .stTextInput > div > div > input:focus { border-color: #FF0000 !important; box-shadow: 0 0 0 2px rgba(255, 0, 0, 0.2) !important; }
        .stButton>button { background: #660000 !important; color: #FFFFFF !important; font-weight: 800 !important; border: 1px solid #FF0000 !important; border-radius: 4px !important; box-shadow: 0 4px 6px rgba(255, 0, 0, 0.2) !important; transition: all 0.2s ease !important; text-transform: uppercase; letter-spacing: 0.1em; }
        .stButton>button:hover { background: #FF0000 !important; box-shadow: 0 0 15px rgba(255, 0, 0, 0.6) !important; }
        .filter-section-card { background: #1A0000; border: 1px solid #330000; border-radius: 8px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #0A0000 !important; border-right: 1px solid #330000 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #CC6666 !important; font-weight: 600 !important; border-radius: 4px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #1A0000 !important; color: #FF3333 !important; transform: translateX(5px) !important; border-left: 3px solid #FF0000 !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #660000 !important; color: #FFFFFF !important; font-weight: 900 !important; box-shadow: 0 4px 10px rgba(255, 0, 0, 0.3) !important; border: 1px solid #FF0000 !important; }
    </style>
    """ + BASE_UI_CSS,

    "Deep Space": """
    <style>
        .stApp { background-color: #020617 !important; color: #CBD5E1 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: linear-gradient(90deg, #0F172A 0%, #1E1B4B 100%); border: 1px solid #334155; border-radius: 16px; margin-bottom: 16px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8); }
        .system-badge { background: rgba(56, 189, 248, 0.1); color: #7DD3FC; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(56, 189, 248, 0.3); text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: rgba(15, 23, 42, 0.8); border: 1px solid #334155; border-radius: 16px; padding: 12px 16px; min-height: 96px; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); backdrop-filter: blur(10px); }
        .telemetry-grid-card:hover { transform: translateY(-8px); box-shadow: 0 15px 30px rgba(56, 189, 248, 0.1); border-color: #8B5CF6; }
        .telemetry-label { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; color: #94A3B8; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; }
        .stTextInput > div > div > input { background-color: rgba(15, 23, 42, 0.6) !important; color: #7DD3FC !important; border: 1px solid #334155 !important; border-radius: 8px !important; }
        .stTextInput > div > div > input:focus { border-color: #8B5CF6 !important; box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.3) !important; }
        .stButton>button { background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%) !important; color: #FFFFFF !important; font-weight: 800 !important; border: none !important; border-radius: 8px !important; box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4) !important; transition: all 0.3s ease !important; text-transform: uppercase; letter-spacing: 0.1em; }
        .stButton>button:hover { background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 100%) !important; box-shadow: 0 8px 25px rgba(139, 92, 246, 0.6) !important; transform: scale(1.02); }
        .filter-section-card { background: rgba(15, 23, 42, 0.6); border: 1px solid #334155; border-radius: 16px; padding: 14px 16px; margin: 16px 0; backdrop-filter: blur(10px); }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #020617 !important; border-right: 1px solid #1E293B !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #94A3B8 !important; font-weight: 600 !important; border-radius: 12px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #0F172A !important; color: #7DD3FC !important; transform: translateX(5px) !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%) !important; color: #FFFFFF !important; font-weight: 900 !important; box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3) !important; }
    </style>
    """ + BASE_UI_CSS,

    "Amber CRT": """
    <style>
        .stApp { background-color: #0D0800 !important; color: #FFB000 !important; font-family: "Courier New", Courier, monospace !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #0D0800; border: 1px solid #FFB000; border-radius: 4px; margin-bottom: 16px; box-shadow: 0 0 8px rgba(255, 176, 0, 0.3); }
        .system-badge { background: #0D0800; color: #FFB000; font-size: 0.85rem; font-weight: bold; letter-spacing: 0.2em; padding: 4px 10px; border: 1px solid #FFB000; text-transform: uppercase; margin-left: 14px; text-shadow: 0 0 4px #FFB000; }
        .telemetry-grid-card { background: #0D0800; border: 1px solid #8B6300; border-radius: 4px; padding: 12px 16px; min-height: 96px; transition: all 0.2s ease; }
        .telemetry-grid-card:hover { border: 1px solid #FFB000; box-shadow: 0 0 12px rgba(255, 176, 0, 0.4); transform: scale(1.01); background: #1A1000; }
        .telemetry-label { font-size: 0.75rem; font-weight: bold; letter-spacing: 0.15em; color: #CC8D00; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: bold; color: #FFB000; line-height: 1.2; text-shadow: 0 0 6px #FFB000; }
        .stTextInput > div > div > input { background-color: #0D0800 !important; color: #FFB000 !important; border: 1px solid #FFB000 !important; border-radius: 0px !important; font-family: monospace !important; }
        .stButton>button { background: #0D0800 !important; color: #FFB000 !important; font-weight: bold !important; border: 1px solid #FFB000 !important; border-radius: 4px !important; text-transform: uppercase; letter-spacing: 0.1em; transition: all 0.2s ease !important; }
        .stButton>button:hover { background: #FFB000 !important; color: #0D0800 !important; box-shadow: 0 0 15px #FFB000 !important; }
        .filter-section-card { background: #0D0800; border: 1px dashed #FFB000; border-radius: 4px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #0D0800 !important; border-right: 1px solid #8B6300 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #CC8D00 !important; font-weight: 600 !important; border-radius: 0px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #1A1000 !important; color: #FFB000 !important; transform: translateX(5px) !important; border-left: 2px solid #FFB000 !important;}
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #FFB000 !important; color: #0D0800 !important; font-weight: 900 !important; box-shadow: 0 0 10px rgba(255, 176, 0, 0.4) !important; }
    </style>
    """ + BASE_UI_CSS,

    "Toxic Sludge": """
    <style>
        .stApp { background-color: #0A0D0A !important; color: #D1E8D1 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #111A11; border: 1px solid #223322; border-radius: 8px; margin-bottom: 16px; border-bottom: 3px solid #39FF14; box-shadow: 0 4px 15px rgba(57, 255, 20, 0.15); }
        .system-badge { background: rgba(57, 255, 20, 0.1); color: #39FF14; font-size: 0.75rem; font-weight: 900; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 4px; border: 1px solid #39FF14; text-transform: uppercase; margin-left: 14px; text-shadow: 0 0 5px #39FF14; }
        .telemetry-grid-card { background: #0F140F; border: 1px solid #1A261A; border-radius: 8px; padding: 12px 16px; min-height: 96px; transition: all 0.2s ease; border-left: 4px solid #1A261A; }
        .telemetry-grid-card:hover { transform: translateX(5px); border-left: 4px solid #39FF14; background: #141C14; box-shadow: -4px 4px 15px rgba(57,255,20,0.2); }
        .telemetry-label { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; color: #7CA87C; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; text-shadow: 0 0 3px rgba(255,255,255,0.5); }
        .stTextInput > div > div > input { background-color: #0F140F !important; color: #39FF14 !important; border: 1px solid #223322 !important; border-radius: 4px !important; font-weight: 600; }
        .stTextInput > div > div > input:focus { border-color: #39FF14 !important; box-shadow: 0 0 0 2px rgba(57, 255, 20, 0.2) !important; }
        .stButton>button { background: #223322 !important; color: #39FF14 !important; font-weight: 900 !important; border: 1px solid #39FF14 !important; border-radius: 4px !important; box-shadow: 0 4px 6px rgba(57, 255, 20, 0.1) !important; text-transform: uppercase; letter-spacing: 0.1em; transition: all 0.2s ease !important; }
        .stButton>button:hover { background: #39FF14 !important; color: #000000 !important; box-shadow: 0 0 15px rgba(57, 255, 20, 0.6) !important; }
        .filter-section-card { background: #111A11; border: 1px solid #223322; border-radius: 8px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #0A0D0A !important; border-right: 1px solid #223322 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #7CA87C !important; font-weight: 600 !important; border-radius: 4px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #111A11 !important; color: #39FF14 !important; transform: translateX(5px) !important; border-left: 2px solid #39FF14 !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #223322 !important; color: #39FF14 !important; font-weight: 900 !important; border: 1px solid #39FF14 !important; box-shadow: 0 0 10px rgba(57, 255, 20, 0.2) !important; }
    </style>
    """ + BASE_UI_CSS,

    "Dracula": """
    <style>
        .stApp { background-color: #282A36 !important; color: #F8F8F2 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #44475A; border: 1px solid #6272A4; border-radius: 10px; margin-bottom: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .system-badge { background: rgba(189, 147, 249, 0.15); color: #BD93F9; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 6px; border: 1px solid #BD93F9; text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: #282A36; border: 1px solid #44475A; border-radius: 10px; padding: 12px 16px; min-height: 96px; transition: all 0.2s ease; box-shadow: 4px 4px 0px #44475A; }
        .telemetry-grid-card:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0px #FF79C6; border-color: #FF79C6; }
        .telemetry-label { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; color: #6272A4; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #50FA7B; line-height: 1.2; }
        .stTextInput > div > div > input { background-color: #44475A !important; color: #F8F8F2 !important; border: 1px solid #6272A4 !important; border-radius: 6px !important; }
        .stTextInput > div > div > input:focus { border-color: #8BE9FD !important; box-shadow: 0 0 0 2px rgba(139, 233, 253, 0.3) !important; }
        .stButton>button { background: #BD93F9 !important; color: #282A36 !important; font-weight: 800 !important; border: none !important; border-radius: 6px !important; box-shadow: 0 4px 10px rgba(189, 147, 249, 0.4) !important; text-transform: uppercase; letter-spacing: 0.1em; transition: all 0.2s ease !important; }
        .stButton>button:hover { background: #FF79C6 !important; box-shadow: 0 6px 15px rgba(255, 121, 198, 0.5) !important; transform: translateY(-2px); }
        .filter-section-card { background: #44475A; border: 1px solid #6272A4; border-radius: 10px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #282A36 !important; border-right: 1px solid #44475A !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #6272A4 !important; font-weight: 600 !important; border-radius: 8px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #44475A !important; color: #8BE9FD !important; transform: translateX(5px) !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #BD93F9 !important; color: #282A36 !important; font-weight: 900 !important; box-shadow: 0 4px 10px rgba(189, 147, 249, 0.4) !important; }
    </style>
    """ + BASE_UI_CSS,

    "Brutalist Monolith": """
    <style>
        .stApp { background-color: #1C1C1C !important; color: #E0E0E0 !important; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #2D2D2D; border: 2px solid #555555; border-radius: 0px; margin-bottom: 16px; box-shadow: 8px 8px 0px #000000; }
        .system-badge { background: #FFCC00; color: #000000; font-size: 0.85rem; font-weight: 900; letter-spacing: 0.1em; padding: 4px 10px; border-radius: 0px; border: 2px solid #000000; text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: #2D2D2D; border: 2px solid #555555; border-radius: 0px; padding: 12px 16px; min-height: 96px; transition: all 0.1s ease; box-shadow: 4px 4px 0px #000000; }
        .telemetry-grid-card:hover { transform: translate(2px, 2px); box-shadow: 2px 2px 0px #000000; border-color: #FFCC00; }
        .telemetry-label { font-size: 0.75rem; font-weight: 900; letter-spacing: 0.1em; color: #999999; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.8rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; }
        .stTextInput > div > div > input { background-color: #1C1C1C !important; color: #FFFFFF !important; border: 2px solid #555555 !important; border-radius: 0px !important; font-weight: bold; }
        .stTextInput > div > div > input:focus { border-color: #FFCC00 !important; }
        .stButton>button { background: #E0E0E0 !important; color: #000000 !important; font-weight: 900 !important; border: 2px solid #000000 !important; border-radius: 0px !important; box-shadow: 4px 4px 0px #000000 !important; text-transform: uppercase; letter-spacing: 0.1em; transition: all 0.1s ease !important; }
        .stButton>button:hover { background: #FFCC00 !important; transform: translate(2px, 2px); box-shadow: 2px 2px 0px #000000 !important; }
        .filter-section-card { background: #2D2D2D; border: 2px solid #555555; border-radius: 0px; padding: 14px 16px; margin: 16px 0; box-shadow: 4px 4px 0px #000000; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #1C1C1C !important; border-right: 2px solid #555555 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #999999 !important; font-weight: 900 !important; border-radius: 0px !important; margin: 4px 16px !important; transition: all 0.1s ease !important; border: 2px solid transparent !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #2D2D2D !important; color: #FFFFFF !important; transform: translate(2px, 2px) !important; border: 2px solid #555555 !important; box-shadow: 2px 2px 0px #000000 !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: #FFCC00 !important; color: #000000 !important; font-weight: 900 !important; border: 2px solid #000000 !important; box-shadow: 4px 4px 0px #000000 !important; }
    </style>
    """ + BASE_UI_CSS,

    "Ocean Depths": """
    <style>
        .stApp { background-color: #001220 !important; color: #B0D4E3 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: linear-gradient(180deg, #001D36 0%, #001220 100%); border: 1px solid #003B5C; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6); }
        .system-badge { background: rgba(0, 229, 255, 0.1); color: #00E5FF; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(0, 229, 255, 0.4); text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: #001D36; border: 1px solid #003B5C; border-radius: 12px; padding: 12px 16px; min-height: 96px; transition: all 0.3s ease; box-shadow: inset 0 2px 10px rgba(0,0,0,0.2); }
        .telemetry-grid-card:hover { transform: translateY(-4px); box-shadow: 0 10px 20px rgba(0, 229, 255, 0.15); border-color: #00E5FF; }
        .telemetry-label { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; color: #5B8C9E; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; }
        .stTextInput > div > div > input { background-color: #001220 !important; color: #00E5FF !important; border: 1px solid #003B5C !important; border-radius: 8px !important; }
        .stTextInput > div > div > input:focus { border-color: #00E5FF !important; box-shadow: 0 0 0 2px rgba(0, 229, 255, 0.2) !important; }
        .stButton>button { background: linear-gradient(180deg, #00B4D8 0%, #0369A1 100%) !important; color: #FFFFFF !important; font-weight: 800 !important; border: 1px solid #00E5FF !important; border-radius: 8px !important; box-shadow: 0 4px 12px rgba(0, 180, 216, 0.3) !important; text-transform: uppercase; letter-spacing: 0.1em; transition: all 0.2s ease !important; }
        .stButton>button:hover { background: linear-gradient(180deg, #00E5FF 0%, #0284C7 100%) !important; box-shadow: 0 6px 18px rgba(0, 229, 255, 0.5) !important; text-shadow: 0 0 5px rgba(255,255,255,0.8); }
        .filter-section-card { background: #001D36; border: 1px solid #003B5C; border-radius: 12px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #001220 !important; border-right: 1px solid #003B5C !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #5B8C9E !important; font-weight: 600 !important; border-radius: 8px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #001D36 !important; color: #00E5FF !important; transform: translateX(5px) !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: linear-gradient(180deg, #00B4D8 0%, #0369A1 100%) !important; color: #FFFFFF !important; font-weight: 900 !important; box-shadow: 0 4px 12px rgba(0, 180, 216, 0.3) !important; border: 1px solid #00E5FF !important; }
    </style>
    """ + BASE_UI_CSS,

    "Velvet Rose": """
    <style>
        .stApp { background-color: #1A0F14 !important; color: #E8D5DD !important; font-family: "Georgia", serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #2A1720; border: 1px solid #4A2535; border-radius: 16px; margin-bottom: 16px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4); }
        .system-badge { background: rgba(255, 141, 161, 0.1); color: #FF8DA1; font-size: 0.75rem; font-weight: bold; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(255, 141, 161, 0.4); text-transform: uppercase; margin-left: 14px; }
        .telemetry-grid-card { background: #2A1720; border: 1px solid #4A2535; border-radius: 16px; padding: 12px 16px; min-height: 96px; transition: all 0.3s ease; }
        .telemetry-grid-card:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(255, 141, 161, 0.15); border-color: #FF8DA1; }
        .telemetry-label { font-size: 0.7rem; font-weight: bold; letter-spacing: 0.1em; color: #A57C8A; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: bold; color: #FFFFFF; line-height: 1.2; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); }
        .stTextInput > div > div > input { background-color: #1A0F14 !important; color: #FF8DA1 !important; border: 1px solid #4A2535 !important; border-radius: 8px !important; }
        .stTextInput > div > div > input:focus { border-color: #FF8DA1 !important; box-shadow: 0 0 0 2px rgba(255, 141, 161, 0.2) !important; }
        .stButton>button { background: linear-gradient(135deg, #8B3A5A 0%, #4A2535 100%) !important; color: #FFFFFF !important; font-weight: bold !important; border: 1px solid #FF8DA1 !important; border-radius: 8px !important; box-shadow: 0 4px 12px rgba(139, 58, 90, 0.3) !important; text-transform: uppercase; letter-spacing: 0.1em; transition: all 0.3s ease !important; }
        .stButton>button:hover { background: linear-gradient(135deg, #A5486C 0%, #683049 100%) !important; box-shadow: 0 6px 18px rgba(255, 141, 161, 0.4) !important; transform: scale(1.02); }
        .filter-section-card { background: #2A1720; border: 1px solid #4A2535; border-radius: 16px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #1A0F14 !important; border-right: 1px solid #4A2535 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #A57C8A !important; font-weight: bold !important; border-radius: 16px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #2A1720 !important; color: #FF8DA1 !important; transform: translateX(5px) !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: linear-gradient(135deg, #8B3A5A 0%, #4A2535 100%) !important; color: #FFFFFF !important; font-weight: bold !important; box-shadow: 0 4px 12px rgba(139, 58, 90, 0.3) !important; border: 1px solid #FF8DA1 !important; }
    </style>
    """ + BASE_UI_CSS,

    "Synthwave Sunrise": """
    <style>
        .stApp { background-color: #0F0C29 !important; color: #E2E8F0 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; }
        header[data-testid="stHeader"] { background: transparent !important; }
        .brand-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: linear-gradient(90deg, #302B63 0%, #24243E 100%); border: 1px solid #FF416C; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 8px 20px rgba(255, 65, 108, 0.2); }
        .system-badge { background: linear-gradient(90deg, #FF4B2B 0%, #FF416C 100%); color: #FFFFFF; font-size: 0.75rem; font-weight: 900; letter-spacing: 0.15em; padding: 4px 10px; border-radius: 6px; text-transform: uppercase; margin-left: 14px; box-shadow: 0 2px 8px rgba(255, 65, 108, 0.5); border: none; }
        .telemetry-grid-card { background: #1B1833; border: 1px solid #302B63; border-radius: 12px; padding: 12px 16px; min-height: 96px; transition: all 0.3s ease; box-shadow: inset 0 -2px 10px rgba(255, 65, 108, 0.05); }
        .telemetry-grid-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(255, 75, 43, 0.2); border-color: #FF4B2B; }
        .telemetry-label { font-size: 0.7rem; font-weight: 800; letter-spacing: 0.12em; color: #A6A4C2; text-transform: uppercase; }
        .telemetry-val-large { font-size: 1.7rem; font-weight: 900; color: #FFFFFF; line-height: 1.2; text-shadow: 2px 2px 4px rgba(255, 65, 108, 0.6); }
        .stTextInput > div > div > input { background-color: #0F0C29 !important; color: #FF4B2B !important; border: 1px solid #302B63 !important; border-radius: 8px !important; font-weight: bold; }
        .stTextInput > div > div > input:focus { border-color: #FF416C !important; box-shadow: 0 0 0 2px rgba(255, 65, 108, 0.3) !important; }
        .stButton>button { background: linear-gradient(90deg, #FF4B2B 0%, #FF416C 100%) !important; color: #FFFFFF !important; font-weight: 900 !important; border: none !important; border-radius: 8px !important; box-shadow: 0 4px 15px rgba(255, 65, 108, 0.4) !important; text-transform: uppercase; letter-spacing: 0.1em; transition: all 0.3s ease !important; }
        .stButton>button:hover { background: linear-gradient(90deg, #FF416C 0%, #FF4B2B 100%) !important; box-shadow: 0 6px 20px rgba(255, 75, 43, 0.6) !important; transform: scale(1.03); }
        .filter-section-card { background: #1B1833; border: 1px solid #302B63; border-radius: 12px; padding: 14px 16px; margin: 16px 0; }

        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] { background-color: #0F0C29 !important; border-right: 1px solid #302B63 !important; }
        [data-testid="stSidebarNav"] { padding-top: 1.5rem; }
        [data-testid="stSidebarNav"] a { color: #A6A4C2 !important; font-weight: 600 !important; border-radius: 6px !important; margin: 4px 16px !important; transition: all 0.3s ease !important; }
        [data-testid="stSidebarNav"] a:hover { background-color: #1B1833 !important; color: #FF416C !important; transform: translateX(5px) !important; border-left: 2px solid #FF416C !important; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: linear-gradient(90deg, #FF4B2B 0%, #FF416C 100%) !important; color: #FFFFFF !important; font-weight: 900 !important; box-shadow: 0 4px 15px rgba(255, 65, 108, 0.4) !important; }
    </style>
    """ + BASE_UI_CSS
}
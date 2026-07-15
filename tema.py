"""
Tema ve CSS yönetim modülü.
Modern glassmorphism tasarım + Light/Dark tema.
"""
import streamlit as st

LIGHT_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

    /* ── Animated gradient background ── */
    .stApp {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 25%, #f0fdf4 50%, #ecfdf5 75%, #f0f9ff 100%) !important;
        background-size: 400% 400% !important;
        animation: gradientShift 15s ease infinite !important;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px !important;
    }

    /* ── Glassmorphism cards ── */
    div[data-testid="stMetric"], div.stAlert, .streamlit-expanderHeader,
    [data-testid="stFileUploader"], [data-testid="stDataFrame"],
    [data-testid="column"] > div > div,
    .st-emotion-cache-1r6slb0, .st-emotion-cache-11xgc7k,
    div:has(> .stButton) {
        background: rgba(255, 255, 255, 0.7) !important;
        backdrop-filter: blur(16px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(16px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.5) !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.05), 0 1px 4px rgba(0, 0, 0, 0.02) !important;
    }

    div[data-testid="stMetric"] {
        padding: 1rem 1.2rem !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 32px rgba(15, 118, 110, 0.12) !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.85) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border-right: 1px solid rgba(226, 232, 240, 0.8) !important;
        box-shadow: 2px 0 20px rgba(0, 0, 0, 0.03) !important;
    }
    [data-testid="stSidebar"] .st-emotion-cache-16txtl3 {
        padding: 1.5rem 1rem !important;
    }

    /* ── Headers ── */
    h1 {
        font-weight: 800 !important;
        font-size: 1.8rem !important;
        letter-spacing: -0.03em !important;
        background: linear-gradient(135deg, #0F766E 0%, #14B8A6 50%, #0D9488 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        margin-bottom: 0.5rem !important;
    }
    h2 {
        font-weight: 700 !important;
        font-size: 1.3rem !important;
        color: #134e4a !important;
        letter-spacing: -0.02em !important;
        border-bottom: 2px solid rgba(15, 118, 110, 0.15) !important;
        padding-bottom: 0.4rem !important;
        margin-top: 0.5rem !important;
    }
    h3 {
        font-weight: 600 !important;
        font-size: 1.05rem !important;
        color: #1e293b !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.5rem 1.2rem !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: 1px solid rgba(15, 118, 110, 0.2) !important;
        background: rgba(255, 255, 255, 0.8) !important;
        color: #0F766E !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(15, 118, 110, 0.15) !important;
        border-color: #14B8A6 !important;
        background: white !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(15, 118, 110, 0.25) !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 8px 30px rgba(15, 118, 110, 0.35) !important;
        transform: translateY(-2px) !important;
    }

    /* ── Inputs ── */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    .stSelectbox, div[data-baseweb="select"] > div {
        border-radius: 8px !important;
        border: 1px solid #e2e8f0 !important;
        background: rgba(255, 255, 255, 0.8) !important;
        transition: all 0.2s ease !important;
        backdrop-filter: blur(4px) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #0F766E !important;
        box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12) !important;
        background: white !important;
    }

    /* ── Metric values ── */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 800 !important;
        color: #0F766E !important;
        letter-spacing: -0.02em !important;
    }
    [data-testid="stMetricLabel"] {
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        color: #64748b !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }
    [data-testid="stMetricDelta"] svg { display: none !important; }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        border-radius: 10px !important;
        padding: 0.7rem 1rem !important;
        font-weight: 600 !important;
        color: #0F766E !important;
        transition: all 0.2s ease !important;
    }
    .streamlit-expanderHeader:hover {
        background: rgba(15, 118, 110, 0.08) !important;
    }

    /* ── DataFrame / Table ── */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    [data-testid="stDataFrame"] table {
        font-size: 0.85rem !important;
    }
    [data-testid="stDataFrame"] th {
        background: rgba(15, 118, 110, 0.06) !important;
        font-weight: 600 !important;
        color: #0F766E !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px !important;
        background: rgba(255, 255, 255, 0.5) !important;
        padding: 4px !important;
        border-radius: 12px !important;
        backdrop-filter: blur(8px) !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 6px 14px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [aria-selected="true"] {
        background: white !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
        color: #0F766E !important;
    }

    /* ── Alerts ── */
    .stAlert {
        border-radius: 10px !important;
        border-left: 4px solid #0F766E !important;
        padding: 0.8rem 1rem !important;
    }
    .stAlert > div { background: transparent !important; backdrop-filter: none !important; }

    /* ── Progress bar ── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #0F766E 0%, #14B8A6 50%, #2DD4BF 100%) !important;
        border-radius: 4px !important;
    }
    .stProgress > div > div {
        background: rgba(15, 118, 110, 0.12) !important;
        border-radius: 4px !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border: 2px dashed rgba(15, 118, 110, 0.3) !important;
        padding: 1.5rem !important;
        text-align: center !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #0F766E !important;
        background: rgba(15, 118, 110, 0.04) !important;
    }

    /* ── Divider ── */
    hr {
        background: linear-gradient(90deg, transparent, rgba(15, 118, 110, 0.2), transparent) !important;
        height: 2px !important;
        border: none !important;
        margin: 1.5rem 0 !important;
    }

    /* ── Sidebar radio ── */
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        padding: 0.4rem 1rem !important;
        border-radius: 8px !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
        background: rgba(15, 118, 110, 0.06) !important;
    }
    [data-testid="stSidebar"] div[data-testid="stMarkdown"] p {
        font-weight: 600 !important;
        color: #1e293b !important;
        font-size: 0.85rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        margin-top: 0.5rem !important;
    }

    /* ── Status widget ── */
    .stStatus {
        border-radius: 12px !important;
        border: 1px solid rgba(15, 118, 110, 0.15) !important;
    }

    /* ── Caption ── */
    .stCaption {
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
    }

    /* ── Data editor ── */
    div[data-testid="stDataEditor"] {
        border-radius: 12px !important;
        overflow: hidden !important;
    }

    /* ── Code ── */
    code {
        background: rgba(15, 118, 110, 0.08) !important;
        color: #0F766E !important;
        padding: 2px 8px !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-size: 0.85em !important;
    }

    /* ── Multi-select ── */
    div[data-baseweb="select"] > div {
        min-height: 38px !important;
    }

    /* ── Spinner ── */
    .stSpinner > div {
        border-color: #0F766E !important;
        border-right-color: transparent !important;
    }
</style>
"""

DARK_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

    /* ── Dark animated background ── */
    .stApp {
        background: linear-gradient(135deg, #0B1121 0%, #0F172A 25%, #1A1F35 50%, #0F172A 75%, #0B1121 100%) !important;
        background-size: 400% 400% !important;
        animation: gradientShift 15s ease infinite !important;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }

    /* ── Glassmorphism cards (dark) ── */
    div[data-testid="stMetric"], div.stAlert, .streamlit-expanderHeader,
    [data-testid="stFileUploader"], [data-testid="stDataFrame"],
    [data-testid="column"] > div > div,
    div:has(> .stButton) {
        background: rgba(30, 41, 59, 0.7) !important;
        backdrop-filter: blur(16px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(16px) saturate(180%) !important;
        border: 1px solid rgba(71, 85, 105, 0.4) !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2), 0 1px 4px rgba(0, 0, 0, 0.1) !important;
    }
    div[data-testid="stMetric"] {
        padding: 1rem 1.2rem !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 32px rgba(45, 212, 191, 0.1) !important;
    }

    /* ── Sidebar (dark) ── */
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.9) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border-right: 1px solid rgba(51, 65, 85, 0.6) !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        color: #e2e8f0 !important;
        padding: 0.4rem 1rem !important;
        border-radius: 8px !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
        background: rgba(45, 212, 191, 0.08) !important;
    }
    [data-testid="stSidebar"] div[data-testid="stMarkdown"] p {
        color: #94a3b8 !important;
    }

    /* ── Headers (dark) ── */
    h1 {
        font-weight: 800 !important;
        background: linear-gradient(135deg, #2DD4BF 0%, #5EEAD4 50%, #2DD4BF 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
    }
    h2 {
        color: #cbd5e1 !important;
        border-bottom-color: rgba(45, 212, 191, 0.15) !important;
    }
    h3 { color: #94a3b8 !important; }

    /* ── Buttons (dark) ── */
    .stButton > button {
        background: rgba(30, 41, 59, 0.8) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(71, 85, 105, 0.5) !important;
    }
    .stButton > button:hover {
        border-color: #2DD4BF !important;
        box-shadow: 0 8px 25px rgba(45, 212, 191, 0.12) !important;
        background: rgba(30, 41, 59, 0.95) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #14B8A6 0%, #2DD4BF 100%) !important;
        color: #0F172A !important;
        border: none !important;
    }

    /* ── Inputs (dark) ── */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    div[data-baseweb="select"] > div {
        background: rgba(30, 41, 59, 0.8) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(71, 85, 105, 0.5) !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #2DD4BF !important;
        box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.12) !important;
        background: rgba(30, 41, 59, 0.95) !important;
    }

    /* ── Metrics (dark) ── */
    [data-testid="stMetricValue"] {
        color: #2DD4BF !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }

    /* ── Expander (dark) ── */
    .streamlit-expanderHeader {
        color: #5EEAD4 !important;
    }
    .streamlit-expanderHeader:hover {
        background: rgba(45, 212, 191, 0.06) !important;
    }

    /* ── Tabs (dark) ── */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(30, 41, 59, 0.5) !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(30, 41, 59, 0.9) !important;
        color: #2DD4BF !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94a3b8 !important;
    }

    /* ── Alerts (dark) ── */
    .stAlert {
        border-left-color: #2DD4BF !important;
    }

    /* ── DataFrame (dark) ── */
    [data-testid="stDataFrame"] th {
        background: rgba(45, 212, 191, 0.08) !important;
        color: #2DD4BF !important;
    }

    /* ── Code (dark) ── */
    code {
        background: rgba(45, 212, 191, 0.1) !important;
        color: #5EEAD4 !important;
    }

    /* ── Divider (dark) ── */
    hr {
        background: linear-gradient(90deg, transparent, rgba(45, 212, 191, 0.15), transparent) !important;
    }

    /* ── General text (dark) ── */
    p, span, label, div, .stTextInput label, .stNumberInput label,
    .stSelectbox label, .stTextArea label {
        color: #cbd5e1 !important;
    }

    /* ── Status (dark) ── */
    .stStatus {
        border-color: rgba(45, 212, 191, 0.15) !important;
    }

    /* ── File uploader (dark) ── */
    [data-testid="stFileUploader"] {
        border-color: rgba(45, 212, 191, 0.25) !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #2DD4BF !important;
        background: rgba(45, 212, 191, 0.04) !important;
    }

    /* ── Success/Info/Warning (dark) ── */
    .stAlert > div { background: transparent !important; backdrop-filter: none !important; }
</style>
"""


def tema_uygula():
    tema = st.session_state.get("tema", "light")
    css = DARK_CSS if tema == "dark" else LIGHT_CSS
    st.markdown(css, unsafe_allow_html=True)
    st.markdown("""
    <div style="position:fixed;top:-50%;left:-50%;width:200%;height:200%;z-index:-1;pointer-events:none;overflow:hidden;opacity:0.15;">
        <div style="position:absolute;width:500px;height:500px;border-radius:50%;background:radial-gradient(circle,rgba(15,118,110,0.4),transparent 70%);top:10%;left:20%;animation:floatBlob 20s ease-in-out infinite;"></div>
        <div style="position:absolute;width:400px;height:400px;border-radius:50%;background:radial-gradient(circle,rgba(20,184,166,0.3),transparent 70%);bottom:10%;right:20%;animation:floatBlob 25s ease-in-out infinite 5s;"></div>
        <div style="position:absolute;width:300px;height:300px;border-radius:50%;background:radial-gradient(circle,rgba(45,212,191,0.25),transparent 70%);top:40%;left:60%;animation:floatBlob 18s ease-in-out infinite 10s;"></div>
    </div>
    <style>
        @keyframes floatBlob {
            0%,100% { transform: translate(0,0) scale(1); }
            33% { transform: translate(30px,-30px) scale(1.05); }
            66% { transform: translate(-20px,20px) scale(0.95); }
        }
    </style>
    """, unsafe_allow_html=True)


def tema_degistirici():
    mevcut = st.session_state.get("tema", "light")
    yeni = "dark" if mevcut == "light" else "light"
    ikon = "🌙" if mevcut == "light" else "☀️"
    etiket = f"{ikon} {yeni.capitalize()} Mod"
    if st.sidebar.button(etiket, key="tema_toggle", use_container_width=True):
        st.session_state.tema = yeni
        st.rerun()

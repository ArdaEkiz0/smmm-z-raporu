"""
Tema ve CSS yönetim modülü.
Modern glassmorphism tasarım - performans optimize edilmiş.
"""
import streamlit as st

LIGHT_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, .stApp, [data-testid="stAppViewContainer"],
    h1, h2, h3, h4, p, span, label, div, input, button, textarea, select, code {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* ── Static gradient background (no animation) ── */
    .stApp {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 50%, #f0fdf4 100%) !important;
    }

    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.92) !important;
        border-right: 1px solid #e2e8f0 !important;
    }

    /* ── Headers ── */
    h1 {
        font-weight: 800 !important;
        font-size: 1.8rem !important;
        letter-spacing: -0.03em !important;
        background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        margin-bottom: 0.3rem !important;
    }
    h2 {
        font-weight: 700 !important;
        font-size: 1.2rem !important;
        color: #134e4a !important;
        letter-spacing: -0.01em !important;
        border-bottom: 2px solid rgba(15, 118, 110, 0.15) !important;
        padding-bottom: 0.4rem !important;
        margin-top: 0.5rem !important;
    }
    h3 {
        font-weight: 600 !important;
        font-size: 1rem !important;
        color: #1e293b !important;
    }

    /* ── Metric cards (subtle, no heavy blur) ── */
    div[data-testid="stMetric"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 0.9rem 1.1rem !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #14B8A6 !important;
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.1) !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.5rem 1.1rem !important;
        border: 1px solid #e2e8f0 !important;
        background: #ffffff !important;
        color: #0F766E !important;
    }
    .stButton > button:hover {
        border-color: #14B8A6 !important;
        background: #f0fdfa !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
        color: white !important;
        border: none !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #0D9488 0%, #0F766E 100%) !important;
    }

    /* ── Inputs ── */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    div[data-baseweb="select"] > div {
        border-radius: 8px !important;
        border: 1px solid #e2e8f0 !important;
        background: #ffffff !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #0F766E !important;
        box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12) !important;
    }

    /* ── Metric values ── */
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 800 !important;
        color: #0F766E !important;
    }
    [data-testid="stMetricLabel"] {
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        color: #64748b !important;
        letter-spacing: 0.02em !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    [data-testid="stMetricValue"] {
        white-space: normal !important;
        overflow: visible !important;
    }
    div[data-testid="stMetric"] {
        overflow: visible !important;
    }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        border-radius: 8px !important;
        padding: 0.6rem 0.9rem !important;
        font-weight: 600 !important;
        color: #0F766E !important;
        background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
    }
    .streamlit-expanderHeader:hover {
        background: #f0fdfa !important;
        border-color: #14B8A6 !important;
    }

    /* ── DataFrame / Table ── */
    [data-testid="stDataFrame"] {
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
    }
    [data-testid="stDataFrame"] table {
        font-size: 0.85rem !important;
    }
    [data-testid="stDataFrame"] th {
        background: #f0fdfa !important;
        font-weight: 600 !important;
        color: #0F766E !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
        background: #f1f5f9 !important;
        padding: 4px !important;
        border-radius: 8px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px !important;
        padding: 6px 14px !important;
        font-weight: 500 !important;
    }
    .stTabs [aria-selected="true"] {
        background: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
        color: #0F766E !important;
    }

    /* ── Alerts ── */
    .stAlert {
        border-radius: 8px !important;
        border-left: 4px solid #0F766E !important;
        padding: 0.7rem 1rem !important;
    }

    /* ── Progress bar ── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #0F766E 0%, #14B8A6 100%) !important;
        border-radius: 4px !important;
    }
    .stProgress > div > div {
        background: rgba(15, 118, 110, 0.12) !important;
        border-radius: 4px !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border: 2px dashed #cbd5e1 !important;
        padding: 1.2rem !important;
        border-radius: 8px !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #0F766E !important;
        background: #f0fdfa !important;
    }

    /* ── Divider ── */
    hr {
        background: linear-gradient(90deg, transparent, rgba(15, 118, 110, 0.2), transparent) !important;
        height: 1px !important;
        border: none !important;
        margin: 1.2rem 0 !important;
    }

    /* ── Sidebar radio ── */
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        padding: 0.4rem 0.9rem !important;
        border-radius: 6px !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
        background: rgba(15, 118, 110, 0.06) !important;
    }
    [data-testid="stSidebar"] div[data-testid="stMarkdown"] p {
        font-weight: 600 !important;
        color: #1e293b !important;
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }

    /* ── Status widget ── */
    .stStatus {
        border-radius: 8px !important;
        border: 1px solid #e2e8f0 !important;
    }

    /* ── Caption ── */
    .stCaption { color: #94a3b8 !important; font-size: 0.75rem !important; }

    /* ── Data editor ── */
    div[data-testid="stDataEditor"] {
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
    }

    /* ── Code ── */
    code {
        background: #f1f5f9 !important;
        color: #0F766E !important;
        padding: 1px 6px !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
    }

    /* ── Multi-select ── */
    div[data-baseweb="select"] > div { min-height: 38px !important; }

    /* ── Spinner ── */
    .stSpinner > div {
        border-color: #0F766E !important;
        border-right-color: transparent !important;
    }

    /* ── Section headers (h2 with icon) ── */
    h2:not([style*="border"]) {
        display: flex !important;
        align-items: center !important;
        gap: 0.4rem !important;
    }

    /* ── Form containers ── */
    [data-testid="stForm"] {
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 1.2rem !important;
        background: rgba(255, 255, 255, 0.7) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
    }

    /* ── Selectbox / Dropdown ── */
    div[data-baseweb="select"] > div {
        border-radius: 8px !important;
        border: 1px solid #e2e8f0 !important;
        background: #ffffff !important;
    }
    div[data-baseweb="select"] > div:focus-within {
        border-color: #0F766E !important;
        box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12) !important;
    }

    /* ── Checkbox ── */
    .stCheckbox label span {
        font-size: 0.88rem !important;
    }

    /* ── Radio buttons ── */
    .stRadio label {
        padding: 0.3rem 0 !important;
        font-size: 0.88rem !important;
    }

    /* ── Toast / Success messages ── */
    .stToast {
        border-radius: 8px !important;
        font-size: 0.85rem !important;
    }

    /* ── Download button highlight ── */
    .stDownloadButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    .stDownloadButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
        color: white !important;
        border: none !important;
    }

    /* ── Date input ── */
    .stDateInput input {
        border-radius: 8px !important;
    }

    /* ── Better container borders ── */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        border-radius: 10px !important;
    }

    /* ── Column gap reduction for tighter layouts ── */
    [data-testid="stHorizontalBlock"] {
        gap: 0.8rem !important;
    }

    /* ── Expander content padding ── */
    .streamlit-expanderContent {
        padding: 0.5rem 0.8rem !important;
    }

    /* ── Scrollbar styling ── */
    ::-webkit-scrollbar {
        width: 6px !important;
        height: 6px !important;
    }
    ::-webkit-scrollbar-track {
        background: transparent !important;
    }
    ::-webkit-scrollbar-thumb {
        background: #cbd5e1 !important;
        border-radius: 3px !important;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8 !important;
    }

    /* ── Info/Warning/Error containers with left accent ── */
    [data-testid="stAlert"] > div {
        font-size: 0.85rem !important;
    }

    /* ── Sidebar section headers ── */
    [data-testid="stSidebar"] h3 {
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        color: #64748b !important;
        margin-top: 0.8rem !important;
        margin-bottom: 0.3rem !important;
    }

    /* ── Sidebar form spacing ── */
    [data-testid="stSidebar"] [data-testid="stForm"] {
        padding: 0.8rem !important;
    }

    /* ── Better tab content area ── */
    .stTabs [data-baseweb="tab-panel"] {
        padding: 1rem 0.2rem !important;
    }
</style>
"""

DARK_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, .stApp, [data-testid="stAppViewContainer"],
    h1, h2, h3, h4, p, span, label, div, input, button, textarea, select, code {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* ── Static dark background (no animation) ── */
    .stApp {
        background: #0B1121 !important;
    }

    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: #0F172A !important;
        border-right: 1px solid #1E293B !important;
    }

    /* ── Headers ── */
    h1 {
        font-weight: 800 !important;
        background: linear-gradient(135deg, #2DD4BF 0%, #5EEAD4 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
    }
    h2 {
        color: #cbd5e1 !important;
        border-bottom-color: rgba(45, 212, 191, 0.2) !important;
    }
    h3 { color: #94a3b8 !important; }

    /* ── Metric cards ── */
    div[data-testid="stMetric"] {
        background: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        padding: 0.9rem 1.1rem !important;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #2DD4BF !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: #1E293B !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    .stButton > button:hover {
        border-color: #2DD4BF !important;
        background: #0F172A !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #14B8A6 0%, #2DD4BF 100%) !important;
        color: #0F172A !important;
        border: none !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #0D9488 0%, #14B8A6 100%) !important;
    }

    /* ── Inputs ── */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    div[data-baseweb="select"] > div {
        background: #1E293B !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #2DD4BF !important;
        box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15) !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetricValue"] { color: #2DD4BF !important; }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        color: #5EEAD4 !important;
        background: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    .streamlit-expanderHeader:hover {
        background: #0F172A !important;
        border-color: #2DD4BF !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #1E293B !important;
    }
    .stTabs [aria-selected="true"] {
        background: #0F172A !important;
        color: #2DD4BF !important;
    }
    .stTabs [data-baseweb="tab"] { color: #94a3b8 !important; }

    /* ── Alerts ── */
    .stAlert {
        border-left-color: #2DD4BF !important;
    }

    /* ── DataFrame ── */
    [data-testid="stDataFrame"] {
        border: 1px solid #334155 !important;
    }
    [data-testid="stDataFrame"] th {
        background: #1E293B !important;
        color: #2DD4BF !important;
    }

    /* ── Code ── */
    code {
        background: #1E293B !important;
        color: #5EEAD4 !important;
    }

    /* ── Divider ── */
    hr {
        background: linear-gradient(90deg, transparent, rgba(45, 212, 191, 0.2), transparent) !important;
    }

    /* ── General text ── */
    p, span, label, div { color: #cbd5e1 !important; }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border-color: #334155 !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #2DD4BF !important;
        background: #1E293B !important;
    }

    /* ── Sidebar radio ── */
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
        background: rgba(45, 212, 191, 0.08) !important;
    }
    [data-testid="stSidebar"] div[data-testid="stMarkdown"] p {
        color: #94a3b8 !important;
    }

    /* ── Status ── */
    .stStatus { border-color: #334155 !important; }

    /* ── Form containers ── */
    [data-testid="stForm"] {
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        padding: 1.2rem !important;
        background: rgba(30, 41, 59, 0.5) !important;
    }

    /* ── Selectbox / Dropdown ── */
    div[data-baseweb="select"] > div {
        background: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] > div:focus-within {
        border-color: #2DD4BF !important;
        box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15) !important;
    }

    /* ── Checkbox / Radio ── */
    .stCheckbox label span, .stRadio label {
        color: #cbd5e1 !important;
        font-size: 0.88rem !important;
    }

    /* ── Toast ── */
    .stToast {
        border-radius: 8px !important;
        background: #1E293B !important;
        color: #e2e8f0 !important;
    }

    /* ── Download button ── */
    .stDownloadButton > button[kind="primary"] {
        background: linear-gradient(135deg, #14B8A6 0%, #2DD4BF 100%) !important;
        color: #0F172A !important;
        border: none !important;
    }

    /* ── Date input ── */
    .stDateInput input {
        border-radius: 8px !important;
    }

    /* ── Column gap ── */
    [data-testid="stHorizontalBlock"] {
        gap: 0.8rem !important;
    }

    /* ── Expander content ── */
    .streamlit-expanderContent {
        padding: 0.5rem 0.8rem !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {
        width: 6px !important;
        height: 6px !important;
    }
    ::-webkit-scrollbar-track {
        background: transparent !important;
    }
    ::-webkit-scrollbar-thumb {
        background: #475569 !important;
        border-radius: 3px !important;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #64748b !important;
    }

    /* ── Alert text size ── */
    [data-testid="stAlert"] > div {
        font-size: 0.85rem !important;
    }

    /* ── Sidebar section headers ── */
    [data-testid="stSidebar"] h3 {
        color: #64748b !important;
    }

    /* ── Tab content ── */
    .stTabs [data-baseweb="tab-panel"] {
        padding: 1rem 0.2rem !important;
    }

    /* ── Form label color fix ── */
    [data-testid="stForm"] label {
        color: #cbd5e1 !important;
    }
</style>
"""


def tema_uygula():
    """Mevcut tema tercihine göre CSS enjekte et.
    Her render'da değil, sadece tema değişince inject edilir (performans)."""
    tema = st.session_state.get("tema", "light")
    css = DARK_CSS if tema == "dark" else LIGHT_CSS
    if st.session_state.get("_tema_uygulandi") != tema:
        st.markdown(css, unsafe_allow_html=True)
        st.session_state["_tema_uygulandi"] = tema


def tema_degistirici():
    mevcut = st.session_state.get("tema", "light")
    yeni = "dark" if mevcut == "light" else "light"
    ikon = "🌙" if mevcut == "light" else "☀️"
    etiket = f"{ikon} {yeni.capitalize()} Mod"
    if st.sidebar.button(etiket, key="tema_toggle", use_container_width=True):
        st.session_state.tema = yeni
        st.rerun()

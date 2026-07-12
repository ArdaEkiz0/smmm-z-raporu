"""
Tema ve CSS yönetim modülü.
Light/Dark tema desteği, özel renkler ve stil iyileştirmeleri.
"""
import streamlit as st

LIGHT_CSS = """
<style>
    /* Modern font ve spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Başlık stili */
    h1 {
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    h2, h3 {
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
    }

    /* Sidebar güzelleştirme */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        border-right: 1px solid #e2e8f0;
    }

    /* Buton iyileştirmeleri */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.15) !important;
    }

    /* Primary buton */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
        color: white !important;
        border: none !important;
    }

    /* Input iyileştirmeleri */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        border-radius: 6px !important;
        border: 1px solid #cbd5e1 !important;
    }

    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #0F766E !important;
        box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.1) !important;
    }

    /* DataFrame / Tablo */
    .stDataFrame {
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        border-radius: 8px !important;
        background: #f8fafc !important;
        font-weight: 500 !important;
    }

    /* Metric kartları */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #0F766E !important;
    }

    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #0F766E 0%, #14B8A6 100%) !important;
    }

    /* Tab stili */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        padding: 8px 16px !important;
        font-weight: 500 !important;
    }

    /* Success/Info/Warning kutuları */
    .stAlert {
        border-radius: 8px !important;
        border-left-width: 4px !important;
    }

    /* Code blokları */
    code {
        background: #f1f5f9 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-size: 0.9em !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        border-radius: 8px !important;
        border: 2px dashed #cbd5e1 !important;
        padding: 1rem !important;
    }

    /* Spinner */
    .stSpinner > div {
        border-color: #0F766E !important;
    }
</style>
"""

DARK_CSS = """
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    h1 {
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: #F1F5F9 !important;
    }

    h2, h3 {
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        color: #E2E8F0 !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
        border-right: 1px solid #334155;
    }

    [data-testid="stSidebar"] * {
        color: #F1F5F9 !important;
    }

    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        background: #1E293B !important;
        color: #F1F5F9 !important;
        border: 1px solid #334155 !important;
    }

    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(45, 212, 191, 0.25) !important;
        border-color: #2DD4BF !important;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #14B8A6 0%, #2DD4BF 100%) !important;
        color: #0F172A !important;
        border: none !important;
        font-weight: 600 !important;
    }

    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        border-radius: 6px !important;
        background: #1E293B !important;
        color: #F1F5F9 !important;
        border: 1px solid #334155 !important;
    }

    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #2DD4BF !important;
        box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15) !important;
    }

    .stDataFrame {
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid #334155 !important;
    }

    .streamlit-expanderHeader {
        border-radius: 8px !important;
        background: #1E293B !important;
        color: #F1F5F9 !important;
        font-weight: 500 !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #2DD4BF !important;
    }

    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
    }

    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #14B8A6 0%, #2DD4BF 100%) !important;
    }

    .stTabs [data-baseweb="tab"] {
        background: #1E293B !important;
        color: #94A3B8 !important;
        border-radius: 8px 8px 0 0 !important;
    }

    .stTabs [aria-selected="true"] {
        background: #0F172A !important;
        color: #2DD4BF !important;
    }

    .stAlert {
        border-radius: 8px !important;
        background: #1E293B !important;
    }

    code {
        background: #1E293B !important;
        color: #2DD4BF !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
    }

    [data-testid="stFileUploader"] {
        border-radius: 8px !important;
        border: 2px dashed #334155 !important;
        background: #1E293B !important;
    }

    [data-testid="stFileUploader"] * {
        color: #F1F5F9 !important;
    }

    .stSpinner > div {
        border-color: #2DD4BF !important;
    }

    .stMarkdown, .stText, p, label, span {
        color: #F1F5F9 !important;
    }

    .stDataFrame [data-testid="stTable"] {
        background: #0F172A !important;
    }

    div[data-testid="stRadio"] label, div[data-testid="stCheckbox"] label {
        color: #F1F5F9 !important;
    }
</style>
"""


def tema_uygula():
    """Mevcut tema tercihine göre CSS enjekte et."""
    tema = st.session_state.get("tema", "light")
    css = DARK_CSS if tema == "dark" else LIGHT_CSS
    st.markdown(css, unsafe_allow_html=True)


def tema_degistirici():
    """Sidebar'a tema değiştirici butonu ekle."""
    mevcut = st.session_state.get("tema", "light")
    yeni = "dark" if mevcut == "light" else "light"
    ikon = "🌙" if mevcut == "light" else "☀️"
    etiket = "🌙 Karanlık" if mevcut == "light" else "☀️ Aydınlık"
    if st.sidebar.button(f"{etiket} Mod", key="tema_toggle", use_container_width=True):
        st.session_state.tema = yeni
        st.rerun()

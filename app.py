"""
Streamlit Web Interface — Agentic Risk Assessment Framework.

Professional risk analysis dashboard with:
  - Clean, minimal design
  - Real-time agent progress tracking
  - Interactive risk score visualisation
  - Sources panel showing data provenance
  - Report history management

Launch:  streamlit run app.py
"""

import asyncio
import glob
import html as html_mod
import json
import os
import re
import time
from datetime import datetime

import streamlit as st
import warnings

# Suppress annoying google.genai deprecation warning (AiohttpClientSession)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google.genai")

from src.main import run_analysis

# ── Page Config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Risk Assessment — Agentic Framework",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject Google Font + Professional CSS ─────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
    /* ═══════════════════════════════════════════════════
       shadcn-inspired Cream/Pastel Theme
       Warm sand + soft pastels + clean typography
       ═══════════════════════════════════════════════════ */

    /* ── Global Reset ────────────────────────────────── */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    /* Restore Material Symbols icons everywhere */
    .material-symbols-rounded,
    [data-testid="collapsedControl"] *,
    [data-testid="stSidebarCollapseButton"] *,
    button[kind="header"] *,
    [data-testid="stHeader"] span[class] {
        font-family: 'Material Symbols Rounded' !important;
    }

    /* ── App Background ─────────────────────────────── */
    .stApp {
        background: #FAF9F6 !important;
    }

    /* ── Sidebar Expand Button (collapsed state) ─────── */
    button[data-testid="collapsedControl"] {
        background: #2c2c3a !important;
        border: none !important;
        border-radius: 0 10px 10px 0 !important;
        color: white !important;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1) !important;
        transition: all 0.2s ease !important;
    }
    button[data-testid="collapsedControl"]:hover {
        background: #3d3d52 !important;
        box-shadow: 3px 3px 14px rgba(0,0,0,0.15) !important;
    }
    button[data-testid="collapsedControl"] * {
        color: white !important;
    }

    /* ── Sidebar Collapse Button (expanded state) ────── */
    [data-testid="stSidebarCollapseButton"] button {
        background: transparent !important;
        border: none !important;
        color: #6b7280 !important;
        transition: all 0.2s ease !important;
        opacity: 0.7;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        color: #2c2c3a !important;
        opacity: 1;
    }
    [data-testid="stSidebarCollapseButton"] button * {
        color: inherit !important;
    }

    /* ── Hide Streamlit Branding ─────────────────────── */
    #MainMenu, footer { visibility: hidden; }

    /* ── Typography ──────────────────────────────────── */
    h1, h2, h3 { color: #1c1c28 !important; font-weight: 700 !important; }

    /* ── Main Header ─────────────────────────────────── */
    .app-header {
        text-align: center;
        padding: 1.8rem 0 1rem;
    }
    .app-header h1 {
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        color: #1c1c28 !important;
        letter-spacing: -0.4px;
        margin-bottom: 0.3rem;
    }
    .app-header p {
        color: #a1a1aa;
        font-size: 0.75rem;
        font-weight: 400;
        letter-spacing: 0.5px;
    }

    /* ── Entity Badge ────────────────────────────────── */
    .entity-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.3rem 0.85rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.2px;
    }
    .entity-badge.public {
        background: #EFF6FF;
        color: #2563eb;
        border: 1px solid #BFDBFE;
    }
    .entity-badge.private {
        background: #FFFBEB;
        color: #b45309;
        border: 1px solid #FDE68A;
    }

    /* ── Metric Cards ────────────────────────────────── */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E8E5E0;
        border-radius: 14px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .metric-card:hover {
        border-color: #D4D0CA;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transform: translateY(-2px);
    }
    .metric-label {
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #a1a1aa;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #1c1c28;
    }
    .metric-value.score-critical { color: #e11d48; }
    .metric-value.score-high { color: #ea580c; }
    .metric-value.score-moderate { color: #ca8a04; }
    .metric-value.score-low { color: #16a34a; }

    /* ── Agent Pipeline Steps ────────────────────────── */
    .pipeline-container {
        display: flex;
        gap: 0.5rem;
        margin: 1rem 0;
    }
    .pipeline-step {
        flex: 1;
        background: #FFFFFF;
        border: 1px solid #E8E5E0;
        border-radius: 12px;
        padding: 1.1rem;
        text-align: center;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    .pipeline-step .step-icon { font-size: 1.3rem; margin-bottom: 0.3rem; }
    .pipeline-step .step-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #71717a;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .pipeline-step .step-status {
        font-size: 0.68rem;
        font-weight: 500;
        margin-top: 0.3rem;
    }

    .pipeline-step.waiting { border-color: #E8E5E0; }
    .pipeline-step.waiting .step-status { color: #a1a1aa; }

    .pipeline-step.active {
        border-color: #93c5fd;
        background: #F5F8FF;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.08);
    }
    .pipeline-step.active .step-status { color: #3b82f6; font-weight: 600; }
    .pipeline-step.active::after {
        content: '';
        position: absolute;
        bottom: 0; left: 0;
        width: 100%; height: 3px;
        background: linear-gradient(90deg, #60a5fa, #a78bfa);
        animation: progress-bar 2.5s ease-in-out infinite;
    }

    .pipeline-step.done {
        border-color: #86efac;
        background: #F0FDF4;
    }
    .pipeline-step.done .step-status { color: #16a34a; font-weight: 600; }

    @keyframes progress-bar {
        0% { transform: scaleX(0); transform-origin: left; }
        50% { transform: scaleX(1); transform-origin: left; }
        50.1% { transform: scaleX(1); transform-origin: right; }
        100% { transform: scaleX(0); transform-origin: right; }
    }

    /* ── Connector arrows between steps ──────────────── */
    .connector {
        display: flex;
        align-items: center;
        color: #D4D0CA;
        font-size: 1rem;
        padding: 0 0.15rem;
    }
    .connector.active { color: #60a5fa; }
    .connector.done { color: #86efac; }

    /* ── Report Block ────────────────────────────────── */
    .report-block {
        background: linear-gradient(145deg, #ffffff, #fdfcfa);
        border: 1px solid #e2dfd9;
        border-radius: 16px;
        padding: 3rem 4rem;
        margin: 1.5rem 0;
        font-size: 1rem;
        line-height: 1.85;
        color: #27272a;
        text-align: justify;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.02);
    }
    .report-block p, .report-block li {
        text-align: justify;
    }
    .report-block h2 {
        color: #18181b;
        font-weight: 700;
        font-size: 1.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid #f4f4f5;
        padding-bottom: 0.5rem;
    }
    .report-block h3 {
        font-weight: 600;
        font-size: 1.2rem;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        color: #3f3f46;
    }

    /* ── Sources Panel ───────────────────────────────── */
    .source-card {
        background: #FAFAF8;
        border: 1px solid #EFECE7;
        border-radius: 10px;
        padding: 0.85rem 1.1rem;
        margin: 0.4rem 0;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .source-card:hover {
        background: #F5F3EE;
        border-color: #E8E5E0;
        transform: translateX(2px);
    }
    .source-title {
        font-size: 0.82rem;
        font-weight: 600;
        color: #1c1c28;
        margin-bottom: 0.15rem;
    }
    .source-title a {
        color: #2563eb;
        text-decoration: none;
    }
    .source-title a:hover { text-decoration: underline; }
    .source-meta {
        font-size: 0.7rem;
        color: #a1a1aa;
    }
    .source-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.62rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-news { background: #EFF6FF; color: #2563eb; }
    .badge-market { background: #F0FDF4; color: #16a34a; }
    .badge-rag { background: #FFFBEB; color: #b45309; }
    .badge-live { background: #F0FDF4; color: #16a34a; }
    .badge-static { background: #FFF1F2; color: #be123c; }

    /* ── Welcome Card ────────────────────────────────── */
    .welcome-card {
        background: #FFFFFF;
        border: 1px solid #E8E5E0;
        border-radius: 18px;
        padding: 3rem 2.5rem;
        text-align: center;
        max-width: 720px;
        margin: 2.5rem auto;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }
    .welcome-card h2 {
        font-size: 1.25rem !important;
        margin-bottom: 0.5rem;
        color: #1c1c28 !important;
    }
    .welcome-card p {
        color: #71717a;
        font-size: 0.84rem;
        line-height: 1.7;
    }

    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
        margin-top: 1.5rem;
    }
    .feature-item {
        background: #FAFAF8;
        border: 1px solid #EFECE7;
        border-radius: 14px;
        padding: 1.3rem 1rem;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .feature-item:hover {
        border-color: #BFDBFE;
        background: #F5F8FF;
        transform: translateY(-3px);
        box-shadow: 0 6px 16px rgba(37,99,235,0.08);
    }
    .feature-item .icon { font-size: 1.4rem; margin-bottom: 0.5rem; }
    .feature-item .title {
        font-size: 0.78rem;
        font-weight: 700;
        color: #1c1c28;
    }
    .feature-item .desc {
        font-size: 0.68rem;
        color: #a1a1aa;
        margin-top: 0.2rem;
    }

    /* ── Section Titles ──────────────────────────────── */
    .section-title {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #a1a1aa;
        margin: 1.5rem 0 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #EFECE7;
    }

    /* ── Sidebar ─────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #FAFAF8 !important;
        border-right: 1px solid #E8E5E0 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #1c1c28 !important;
        font-size: 0.88rem !important;
    }
    section[data-testid="stSidebar"] label {
        color: #3f3f46 !important;
        font-weight: 500 !important;
        font-size: 0.76rem !important;
    }

    /* ── Selectbox & Inputs ──────────────────────────── */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: #FFFFFF !important;
        border-color: #E8E5E0 !important;
        border-radius: 10px !important;
        color: #1c1c28 !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] span,
    section[data-testid="stSidebar"] [data-baseweb="select"] div[class] {
        color: #1c1c28 !important;
    }
    section[data-testid="stSidebar"] textarea {
        background: #FFFFFF !important;
        border-color: #E8E5E0 !important;
        border-radius: 10px !important;
        font-size: 0.82rem !important;
        color: #1c1c28 !important;
    }
    section[data-testid="stSidebar"] textarea::placeholder {
        color: #a1a1aa !important;
    }
    section[data-testid="stSidebar"] textarea:focus {
        border-color: #93c5fd !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.08) !important;
    }
    section[data-testid="stSidebar"] input {
        color: #1c1c28 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * {
        color: #1c1c28 !important;
    }
    /* Dropdown menu items */
    [data-baseweb="menu"] li {
        color: #1c1c28 !important;
    }

    /* ── Primary Button ──────────────────────────────── */
    .stButton > button[kind="primary"] {
        background: #1c1c28 !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        padding: 0.65rem 1.5rem !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #2c2c3a !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
    }
    .stButton > button:not([kind="primary"]) {
        background: #FFFFFF !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        font-size: 0.78rem !important;
        border: 1px solid #E8E5E0 !important;
        color: #3f3f46 !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        border-color: #93c5fd !important;
        color: #2563eb !important;
        background: #F5F8FF !important;
    }

    /* ── Toggle ──────────────────────────────────────── */
    [data-testid="stToggle"] label span {
        font-size: 0.78rem !important;
        color: #3f3f46 !important;
    }

    /* ── Progress bar ────────────────────────────────── */
    .stProgress > div > div {
        background: linear-gradient(90deg, #86efac, #22c55e) !important;
        border-radius: 6px;
    }

    /* ── Tabs ─────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0 !important;
        background: transparent !important;
        border-bottom: 1px solid #EFECE7 !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        color: #71717a !important;
        padding: 0.6rem 1rem !important;
        border-radius: 8px 8px 0 0 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #2563eb !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #2563eb !important;
    }

    /* ── Download Button ─────────────────────────────── */
    .stDownloadButton > button {
        background: #FFFFFF !important;
        border: 1px solid #E8E5E0 !important;
        border-radius: 10px !important;
        color: #3f3f46 !important;
        font-weight: 500 !important;
        font-size: 0.78rem !important;
        transition: all 0.2s ease !important;
    }
    .stDownloadButton > button:hover {
        border-color: #93c5fd !important;
        color: #2563eb !important;
        background: #F5F8FF !important;
    }

    /* ── Hide default metrics styling ────────────────── */
    div[data-testid="stMetric"] {
        background: transparent;
        border: none;
        padding: 0;
    }

    /* ── Divider ─────────────────────────────────────── */
    hr { border-color: #EFECE7 !important; }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>Risk Assessment Framework</h1>
    <p>Multi-Agent LLM Pipeline &nbsp;·&nbsp; LangGraph &nbsp;·&nbsp; Gemini 2.5 Flash</p>
</div>
""", unsafe_allow_html=True)


# ── Example Queries ───────────────────────────────────────────────────
EXAMPLE_QUERIES = {
    "Apple (AAPL) — Supply Chain & Semiconductors": (
        "Perform a comprehensive credit and geopolitical risk assessment for "
        "Apple Inc. (AAPL), considering its supply chain exposure to China and "
        "Taiwan, the current US-China semiconductor tensions, and its financial "
        "health. Provide an integrated risk report with quantified risk scores."
    ),
    "NVIDIA (NVDA) — AI Chips & Export Controls": (
        "Perform a comprehensive risk assessment for NVIDIA Corp (NVDA), "
        "focusing on US-China export controls on AI chips, the CHIPS Act "
        "impact, and NVIDIA's revenue exposure to Chinese data centers. "
        "Include financial health analysis and quantified risk scores."
    ),
    "Volkswagen (VOW3.DE) — EV & BYD Competition": (
        "Assess the credit and geopolitical risk for Volkswagen AG (VOW3.DE), "
        "considering EU EV regulations, Chinese competition from BYD, and "
        "Volkswagen's exposure to the Russian market write-downs."
    ),
    "TotalEnergies (TTE.PA) — Middle East & Energy": (
        "Evaluate the integrated risk profile of TotalEnergies SE (TTE.PA), "
        "focusing on Middle East tensions, Strait of Hormuz transit risk, "
        "energy transition pressures, and diversification into renewables."
    ),
    "Deutsche Bank (DB) — Banking & Sovereign Risk": (
        "Perform a credit risk assessment for Deutsche Bank (DB), analyzing "
        "European banking sector stress, commercial real estate exposure, "
        "interest rate environment, and sovereign debt risks in the Eurozone."
    ),
    "Custom Query": "",
}

# ── Session State ─────────────────────────────────────────────────────
defaults = {"running": False, "report": None, "sources": None, "elapsed": 0}
for key, default in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")

    selected = st.selectbox("Query Template", list(EXAMPLE_QUERIES.keys()))
    query = st.text_area(
        "Analysis Query",
        value=EXAMPLE_QUERIES[selected],
        height=140,
        placeholder="Describe the risk analysis you need...",
    )

    use_redis = st.toggle("Redis (persistence)", value=False)

    run_btn = st.button(
        "Run Analysis",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.running or not query.strip(),
    )

    st.markdown("---")

    # History
    st.markdown("### History")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    reports = sorted(glob.glob(os.path.join(output_dir, "risk_report_*.md")), reverse=True)

    if reports:
        names = [os.path.basename(r) for r in reports]
        selected_report = st.selectbox("Report", names, label_visibility="collapsed")
        if st.button("View Report", use_container_width=True):
            with open(os.path.join(output_dir, selected_report)) as f:
                content = f.read()
            
            # Extract internal metadata if present
            sources = None
            meta_match = re.search(r"<!-- INTERNAL_METADATA_START\n(.*?)\nINTERNAL_METADATA_END -->", content, re.DOTALL)
            if meta_match:
                try:
                    meta_data = json.loads(meta_match.group(1))
                    sources = meta_data.get("sources")
                    # Clean the report content for display
                    content = content[:meta_match.start()].strip()
                except Exception:
                    pass

            idx = content.find("---\n\n")
            st.session_state.report = content[idx + 5:].strip() if idx >= 0 else content
            st.session_state.sources = sources
            st.session_state.elapsed = 0
    else:
        st.caption("No reports available.")


# ── Helpers ───────────────────────────────────────────────────────────
def _format_report_html(report_text: str) -> str:
    """Format the raw Markdown report for better visual layout."""
    # 1. Main Header
    report_text = re.sub(
        r'═{10,}\s*\n\s*(.+?)\n\s*═{10,}',
        r'\n\n<div style="text-align:center; margin: 2rem 0; padding: 1.5rem 0; border-top: 2px solid #e2dfd9; border-bottom: 2px solid #e2dfd9; font-weight: 800; font-size: 1.4rem; letter-spacing: 1.5px; color: #18181b; text-transform: uppercase; background: linear-gradient(90deg, transparent, rgba(244,244,245,0.4), transparent);">\1</div>\n\n',
        report_text
    )
    # 2. Section Headers
    report_text = re.sub(
        r'─{10,}\s*(.+?)\s*─{10,}',
        r'\n\n<div style="display:flex; justify-content:center; align-items:center; margin: 2.5rem 0 1.5rem 0;">'
        r'<span style="height:1px; background:linear-gradient(90deg, transparent, #d4d4d8); flex:1; margin-right:1.5rem;"></span>'
        r'<span style="color: #52525b; font-weight: 700; font-size: 0.85rem; letter-spacing: 3px; text-transform: uppercase;">\1</span>'
        r'<span style="height:1px; background:linear-gradient(90deg, #d4d4d8, transparent); flex:1; margin-left:1.5rem;"></span></div>\n\n',
        report_text
    )
    return report_text


def _parse_scores(report: str) -> dict:
    """Parse risk scores from report text."""
    scores = {}
    patterns = {
        "overall": r"OVERALL RISK SCORE:\s*(\d+)/100",
        "geopolitical": r"Geopolitical Risk:\s*(\d+)/100",
        "credit": r"Credit/Financial:\s*(\d+)/100",
        "market": r"Market/Liquidity:\s*(\d+)/100",
        "esg": r"ESG/Transition:\s*(\d+)/100",
    }
    for key, pat in patterns.items():
        m = re.search(pat, report)
        if m:
            scores[key] = int(m.group(1))

    m = re.search(r"INTERNAL CREDIT RATING:\s*(.+)", report)
    if m:
        scores["rating"] = m.group(1).strip()
    m = re.search(r"ENTITY:\s*(.+)", report)
    if m:
        scores["entity"] = m.group(1).strip()
    return scores


def _score_class(score: int) -> str:
    if score >= 75: return "score-critical"
    if score >= 50: return "score-high"
    if score >= 30: return "score-moderate"
    return "score-low"


def _score_label(score: int) -> str:
    if score >= 75: return "Critical"
    if score >= 50: return "High"
    if score >= 30: return "Moderate"
    return "Low"


@st.cache_data(ttl=300, show_spinner=False)
def _detect_entity_type(entity_name: str) -> dict:
    """Detect if an entity is publicly traded using yfinance.
    
    Uses progressive yf.Search with noise stripping to handle
    entity names like 'Thales Group (France)' → HO.PA.
    
    Returns dict with is_public, ticker, exchange, currency, market_cap, sector.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"is_public": False, "ticker": None, "exchange": None, "currency": None}
    
    default = {"is_public": False, "ticker": None, "exchange": None, "currency": None}
    entity_words = set(re.findall(r'[A-Za-z]{3,}', entity_name.lower()))
    
    candidates = []
    
    # 1. Tickers explicitly in parentheses if they look like tickers (max 5 chars)
    paren_match = re.findall(r'\(([A-Z0-9.\-]{1,5})\)', entity_name)
    candidates.extend([(t, True) for t in paren_match])
    
    # 2. Entire name if it looks like a pure ticker (max 5 chars)
    stripped = entity_name.strip()
    if re.match(r'^[A-Z0-9.\-]{1,5}$', stripped):
        candidates.append((stripped, True))
    
    # 3. Words that look like tickers (3-5 chars uppercase)
    parts = re.split(r'[\s\-]+', entity_name)
    for part in parts:
        clean = part.strip('().,;')
        if re.match(r'^[A-Z0-9.]{3,5}$', clean) and clean not in [c for c, _ in candidates]:
            candidates.append((clean, False))
    
    # 4. Progressive yf.Search — strip noise and try shorter variants
    # "Thales Group (France)" → ["THALES GROUP", "THALES"]
    clean_name = re.sub(r'\([^)]*\)', '', entity_name).strip()  # Remove parenthesized content
    clean_name = re.sub(r'\s+', ' ', clean_name)  # Normalize whitespace
    words = clean_name.split()
    
    search_variants = []
    # Try full cleaned name, then progressively drop last word
    for i in range(len(words), 0, -1):
        variant = " ".join(words[:i]).upper()
        if variant and variant not in search_variants:
            search_variants.append(variant)
    
    for variant in search_variants:
        try:
            search_obj = yf.Search(variant, max_results=5)
            for q in (search_obj.quotes or []):
                symbol = q.get("symbol", "")
                quote_type = q.get("quoteType", "")
                if symbol and quote_type == "EQUITY" and symbol not in [c for c, _ in candidates]:
                    candidates.append((symbol, True))
            if any(s not in [c for c, _ in candidates[:len(paren_match) + 2]] for s in [q.get("symbol") for q in (search_obj.quotes or []) if q.get("quoteType") == "EQUITY"]):
                break  # Found equity results, stop searching
        except Exception:
            continue
    
    # Try each candidate
    for ticker_str, is_explicit in candidates:
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            if not info or info.get('regularMarketPrice') is None:
                continue
            
            # Cross-validate non-explicit tickers
            if not is_explicit:
                yf_name = (info.get('shortName') or info.get('longName') or '').lower()
                yf_words = set(re.findall(r'[a-z]{3,}', yf_name))
                if not entity_words & yf_words:
                    continue
            
            return {
                "is_public": True,
                "ticker": ticker_str,
                "exchange": info.get('exchange', info.get('fullExchangeName', 'N/A')),
                "currency": info.get('currency', 'N/A'),
                "market_cap": info.get('marketCap'),
                "sector": info.get('sector', 'N/A'),
            }
        except Exception:
            continue
    
    return default


def _render_pipeline(geo="waiting", credit="waiting", synth="waiting"):
    """Render the 3-agent pipeline status bar."""
    icons = {"waiting": "⏳", "active": "🔄", "done": "✅"}
    statuses = {"waiting": "Waiting", "active": "Running...", "done": "Done"}

    def _conn_class(state):
        if state == "done": return "done"
        if state == "active": return "active"
        return ""

    st.markdown(f"""
    <div class="pipeline-container">
        <div class="pipeline-step {geo}">
            <div class="step-icon">🌍</div>
            <div class="step-label">Geopolitical</div>
            <div class="step-status">{icons[geo]} {statuses[geo]}</div>
        </div>
        <div class="connector {_conn_class(credit)}">→</div>
        <div class="pipeline-step {credit}">
            <div class="step-icon">💳</div>
            <div class="step-label">Credit</div>
            <div class="step-status">{icons[credit]} {statuses[credit]}</div>
        </div>
        <div class="connector {_conn_class(synth)}">→</div>
        <div class="pipeline-step {synth}">
            <div class="step-icon">📊</div>
            <div class="step-label">Synthesizer</div>
            <div class="step-status">{icons[synth]} {statuses[synth]}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_metrics(scores: dict):
    """Render the score metric cards with entity type detection."""
    overall = scores.get("overall")
    if overall is None:
        return

    entity = scores.get("entity", "N/A")
    rating = scores.get("rating", "N/A")

    # Detect if entity is publicly traded
    entity_info = _detect_entity_type(entity)

    # Entity type badge
    if entity_info["is_public"]:
        ticker = entity_info['ticker']
        exchange = entity_info.get('exchange', '')
        sector = entity_info.get('sector', '')
        badge_html = (
            f'<span class="entity-badge public">'
            f'📈 Publicly Traded — {ticker}'
            f'{" · " + exchange if exchange and exchange != "N/A" else ""}'
            f'</span>'
        )
    else:
        badge_html = '<span class="entity-badge private">🏢 Private Entity</span>'

    # Show entity badge above metrics
    st.markdown(f'<div style="text-align:center; margin-bottom:0.8rem;">{badge_html}</div>', unsafe_allow_html=True)

    cols = st.columns(6)
    items = [
        ("Entity", entity, ""),
        ("Overall Score", f"{overall}/100", _score_class(overall)),
        ("Rating", rating, ""),
        ("Geopolitical", f"{scores.get('geopolitical', '—')}/100", _score_class(scores.get('geopolitical', 0)) if 'geopolitical' in scores else ""),
        ("Credit", f"{scores.get('credit', '—')}/100", _score_class(scores.get('credit', 0)) if 'credit' in scores else ""),
        ("Market", f"{scores.get('market', '—')}/100", _score_class(scores.get('market', 0)) if 'market' in scores else ""),
    ]
    for col, (label, value, color_cls) in zip(cols, items):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value {color_cls}">{value}</div>
            </div>
            """, unsafe_allow_html=True)


def _render_radar(scores: dict):
    """Render plotly radar chart for risk sub-scores."""
    keys = ["geopolitical", "credit", "market", "esg"]
    if not all(k in scores for k in keys):
        return

    try:
        import plotly.graph_objects as go

        labels = ["Geopolitical", "Credit / Financial", "Market / Liquidity", "ESG / Transition"]
        values = [scores[k] for k in keys]
        values_closed = values + [values[0]]
        labels_closed = labels + [labels[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor="rgba(59,130,246,0.08)",
            line=dict(color="#3b82f6", width=2),
            marker=dict(size=6, color="#3b82f6"),
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickfont=dict(size=10, color="#9ca3af"),
                    gridcolor="#f3f4f6",
                    linecolor="#e5e7eb",
                ),
                angularaxis=dict(
                    tickfont=dict(size=11, color="#374151"),
                    gridcolor="#f3f4f6",
                    linecolor="#e5e7eb",
                ),
                bgcolor="white",
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            height=350,
            margin=dict(l=60, r=60, t=30, b=30),
            font=dict(family="Inter", color="#374151"),
        )
        st.plotly_chart(fig, width="stretch")
    except ImportError:
        pass


def _render_sources(sources: dict):
    """Render the sources panel showing data provenance."""
    if not sources:
        return

    has_any = any(sources.get(k) for k in ["news", "market", "rag"])
    if not has_any:
        return

    st.markdown('<div class="section-title">Sources Used</div>', unsafe_allow_html=True)

    tabs = []
    tab_keys = []
    if sources.get("news"):
        tabs.append(f"📰 News ({len(sources['news'])})")
        tab_keys.append("news")
    if sources.get("market"):
        tabs.append(f"📈 Market Data ({len(sources['market'])})")
        tab_keys.append("market")
    if sources.get("rag"):
        tabs.append(f"📄 RAG Documents ({len(sources['rag'])})")
        tab_keys.append("rag")

    if not tabs:
        return

    st_tabs = st.tabs(tabs)

    for tab, key in zip(st_tabs, tab_keys):
        with tab:
            if key == "news":
                for article in sources["news"]:
                    title = html_mod.escape(article.get("title", "Untitled"))
                    url = article.get("url", "")
                    source = html_mod.escape(article.get("source", ""))
                    date = article.get("date", "")
                    date_short = date[:10] if date else ""

                    link = f'<a href="{url}" target="_blank">{title}</a>' if url else title
                    st.markdown(f"""
                    <div class="source-card">
                        <div class="source-title">{link}</div>
                        <div class="source-meta">
                            <span class="source-badge badge-news">News</span>
                            <span class="source-badge badge-live">Live</span>
                            &nbsp; {source} {(' · ' + date_short) if date_short else ''}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            elif key == "market":
                for data in sources["market"]:
                    company = html_mod.escape(data.get("company", ""))
                    ticker = data.get("ticker", "")
                    price = data.get("price", "")
                    pe = data.get("pe_ratio", "")
                    st.markdown(f"""
                    <div class="source-card">
                        <div class="source-title">{company} ({ticker})</div>
                        <div class="source-meta">
                            <span class="source-badge badge-market">Market Data</span>
                            <span class="source-badge badge-live">Live</span>
                            &nbsp; Price: {price} &nbsp;|&nbsp; P/E: {pe}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            elif key == "rag":
                st.caption(
                    "⚠️ Static seed documents (2026). "
                    "To update, add your own files to the ChromaDB vector store."
                )
                for doc in sources["rag"]:
                    source_name = html_mod.escape(doc.get("source", ""))
                    company = html_mod.escape(doc.get("company", ""))
                    doc_type = doc.get("type", "")
                    score = doc.get("score", 0)
                    content_preview = html_mod.escape(doc.get("content", ""))[:400] + "..."
                    st.markdown(f"""
                    <div class="source-card">
                        <div class="source-title">{source_name}</div>
                        <div class="source-meta" style="margin-bottom:0.5rem;">
                            <span class="source-badge badge-rag">RAG</span>
                            <span class="source-badge badge-static">Static</span>
                            &nbsp; {company} · {doc_type} · Score: {score:.2f}
                        </div>
                        <div style="font-size:0.75rem; color:#4b5563; line-height:1.5; background:#fff; padding:0.5rem; border-radius:4px; border:1px solid #f3f4f6;">
                            {content_preview}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)


# ── Main — Run Analysis ──────────────────────────────────────────────
if run_btn and query.strip():
    st.session_state.running = True
    st.session_state.report = None
    st.session_state.sources = None
    st.session_state.token_usage = None

    st.markdown('<div class="section-title">Analysis Pipeline</div>', unsafe_allow_html=True)
    pipeline_placeholder = st.empty()
    progress_bar = st.progress(0)
    time_placeholder = st.empty()

    # Live log container
    st.markdown('<div class="section-title">Live Activity</div>', unsafe_allow_html=True)
    log_container = st.empty()

    with pipeline_placeholder.container():
        _render_pipeline("active", "waiting", "waiting")

    progress_bar.progress(10)

    start = time.time()

    # Set up shared log queue + run analysis in thread
    import queue
    import threading
    from src.agents.nodes import set_log_queue

    log_queue = queue.Queue(maxsize=200)
    set_log_queue(log_queue)
    log_lines = []

    result_holder = {"report": None, "sources": None, "token_usage": None, "error": None}

    def _run_in_thread():
        import asyncio as _asyncio
        try:
            loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(loop)
            r, s, t = loop.run_until_complete(run_analysis(query=query, use_redis=use_redis))
            result_holder["report"] = r
            result_holder["sources"] = s
            result_holder["token_usage"] = t
        except Exception as e:
            result_holder["error"] = str(e)
        finally:
            log_queue.put("__DONE__")

    analysis_thread = threading.Thread(target=_run_in_thread, daemon=True)
    analysis_thread.start()

    # Poll log queue and update UI in real-time
    geo_done = credit_done = synth_done = False
    while True:
        try:
            msg = log_queue.get(timeout=0.3)
        except queue.Empty:
            # Update elapsed time
            elapsed = time.time() - start
            time_placeholder.markdown(
                f"<p style='text-align:center; color:#a1a1aa; font-size:0.75rem;'>"
                f"⏱ {elapsed:.0f}s elapsed</p>",
                unsafe_allow_html=True,
            )
            continue

        if msg == "__DONE__":
            break

        log_lines.append(msg)

        # Update pipeline visualization based on log messages
        if "Geopolitical done" in msg:
            geo_done = True
        if "Credit Evaluator done" in msg:
            credit_done = True
        if "Synthesizer done" in msg:
            synth_done = True

        geo_status = "done" if geo_done else "active"
        credit_status = "done" if credit_done else ("active" if geo_done else "waiting")
        synth_status = "done" if synth_done else ("active" if credit_done else "waiting")

        with pipeline_placeholder.container():
            _render_pipeline(geo_status, credit_status, synth_status)

        # Progress estimation
        done_count = sum([geo_done, credit_done, synth_done])
        progress_bar.progress(10 + done_count * 28)

        # Render live log
        log_html = "\n".join(
            f"<div style='padding:0.2rem 0;font-size:0.72rem;color:#3f3f46;border-bottom:1px solid #EFECE7;'>"
            f"<span style='color:#a1a1aa;font-size:0.65rem;'>{i+1:02d}</span> {line}</div>"
            for i, line in enumerate(log_lines[-12:])  # Show last 12 lines
        )
        log_container.markdown(
            f'<div style="background:#FFFFFF;border:1px solid #E8E5E0;border-radius:12px;'
            f'padding:0.8rem 1rem;max-height:220px;overflow-y:auto;'
            f'box-shadow:0 1px 2px rgba(0,0,0,0.03);">{log_html}</div>',
            unsafe_allow_html=True,
        )

    # Clean up
    set_log_queue(None)
    analysis_thread.join(timeout=5)

    elapsed = time.time() - start

    if result_holder["error"]:
        with pipeline_placeholder.container():
            _render_pipeline("done", "done", "waiting")
        st.error(f"Error: {result_holder['error']}")
    else:
        st.session_state.report = result_holder["report"]
        st.session_state.sources = result_holder["sources"]
        st.session_state.token_usage = result_holder["token_usage"]
        st.session_state.elapsed = elapsed

        with pipeline_placeholder.container():
            _render_pipeline("done", "done", "done")
        progress_bar.progress(100)
        time_placeholder.markdown(
            f"<p style='text-align:center; color:#16a34a; font-weight:600; font-size:0.85rem;'>"
            f"✅ Analysis completed in {elapsed:.0f}s</p>",
            unsafe_allow_html=True,
        )

    st.session_state.running = False


# ── Main — Display Report ────────────────────────────────────────────
if st.session_state.report:
    report = st.session_state.report
    scores = _parse_scores(report)

    # Metrics
    st.markdown('<div class="section-title">Risk Scores</div>', unsafe_allow_html=True)
    _render_metrics(scores)

    # Token usage & cost
    token_usage = st.session_state.get("token_usage", [])
    if token_usage:
        total_in = sum(t.get("input", 0) for t in token_usage)
        total_out = sum(t.get("output", 0) for t in token_usage)
        total_cached = sum(t.get("cached", 0) for t in token_usage)
        cost_in = total_in * 0.30 / 1_000_000
        cost_out = total_out * 2.50 / 1_000_000
        total_cost = cost_in + cost_out
        saved = total_cached * 0.27 / 1_000_000

        saved_html = ""
        if saved > 0:
            saved_html = f' <span style="color:#16a34a;font-size:0.7rem;">(saved ${saved:.4f})</span>'

        rows_html = ""
        for t in token_usage:
            agent_name = t.get("agent", "").replace("_", " ").title()
            rows_html += (
                f'<tr>'
                f'<td style="font-weight:500;color:#1c1c28;padding:0.35rem 0.5rem;">{agent_name}</td>'
                f'<td style="text-align:right;padding:0.35rem 0.5rem;font-variant-numeric:tabular-nums;">{t.get("input", 0):,}</td>'
                f'<td style="text-align:right;padding:0.35rem 0.5rem;font-variant-numeric:tabular-nums;">{t.get("output", 0):,}</td>'
                f'<td style="text-align:right;padding:0.35rem 0.5rem;color:#2563eb;font-variant-numeric:tabular-nums;">{t.get("cached", 0):,}</td>'
                f'</tr>'
            )

        token_html = (
            '<div style="background:#FFFFFF;border:1px solid #E8E5E0;border-radius:14px;'
            'padding:1.2rem 1.5rem;margin:1rem 0;box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem;">'
            '<span style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
            'letter-spacing:1.2px;color:#a1a1aa;">Token Usage</span>'
            f'<span style="font-size:0.85rem;font-weight:700;color:#1c1c28;">'
            f'\U0001f4b0 ${total_cost:.4f}{saved_html}</span>'
            '</div>'
            '<table style="width:100%;font-size:0.75rem;color:#3f3f46;border-collapse:collapse;table-layout:fixed;">'
            '<colgroup><col style="width:46%;"><col style="width:18%;"><col style="width:18%;"><col style="width:18%;"></colgroup>'
            '<thead><tr style="border-bottom:1px solid #EFECE7;">'
            '<th style="text-align:left;padding:0.4rem 0.5rem;color:#a1a1aa;font-weight:600;">Agent</th>'
            '<th style="text-align:right;padding:0.4rem 0.5rem;color:#a1a1aa;font-weight:600;">Input</th>'
            '<th style="text-align:right;padding:0.4rem 0.5rem;color:#a1a1aa;font-weight:600;">Output</th>'
            '<th style="text-align:right;padding:0.4rem 0.5rem;color:#a1a1aa;font-weight:600;">Cached</th>'
            '</tr></thead>'
            f'<tbody>{rows_html}'
            '<tr style="border-top:1px solid #EFECE7;font-weight:700;">'
            f'<td style="padding-top:0.4rem;padding-left:0.5rem;color:#1c1c28;">Total</td>'
            f'<td style="text-align:right;padding-top:0.4rem;padding-right:0.5rem;font-variant-numeric:tabular-nums;">{total_in:,}</td>'
            f'<td style="text-align:right;padding-top:0.4rem;padding-right:0.5rem;font-variant-numeric:tabular-nums;">{total_out:,}</td>'
            f'<td style="text-align:right;padding-top:0.4rem;padding-right:0.5rem;color:#2563eb;font-variant-numeric:tabular-nums;">{total_cached:,}</td>'
            '</tr></tbody></table></div>'
        )
        st.markdown(token_html, unsafe_allow_html=True)

    # Radar chart + summary
    if all(k in scores for k in ["geopolitical", "credit", "market", "esg"]):
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown('<div class="section-title">Risk Radar</div>', unsafe_allow_html=True)
            _render_radar(scores)
        with col_right:
            st.markdown('<div class="section-title">Quick Summary</div>', unsafe_allow_html=True)
            overall = scores.get("overall", 0)
            label = _score_label(overall)
            st.markdown(f"""
            <div class="metric-card" style="text-align:left; padding:1.5rem;">
                <p style="color:#6b7280; font-size:0.8rem; margin-bottom:1rem;">
                    <strong>Risk Level:</strong>
                    <span style="font-size:1.1rem; font-weight:700;" class="{_score_class(overall)}">{label} ({overall}/100)</span>
                </p>
                <p style="color:#6b7280; font-size:0.8rem; margin-bottom:0.5rem;">
                    <strong>Internal Rating:</strong> {scores.get('rating', 'N/A')}
                </p>
                <p style="color:#6b7280; font-size:0.8rem; margin-bottom:0.5rem;">
                    <strong>Geopolitical:</strong> {scores.get('geopolitical', '—')}/100
                    &nbsp;|&nbsp; <strong>Credit:</strong> {scores.get('credit', '—')}/100
                </p>
                <p style="color:#6b7280; font-size:0.8rem;">
                    <strong>Market:</strong> {scores.get('market', '—')}/100
                    &nbsp;|&nbsp; <strong>ESG:</strong> {scores.get('esg', '—')}/100
                </p>
            </div>
            """, unsafe_allow_html=True)

    # Sources panel
    _render_sources(st.session_state.sources)

    # Full report
    formatted_report = _format_report_html(report)
    st.markdown('<div class="section-title">Full Report</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="report-block">\n\n{formatted_report}\n\n</div>', unsafe_allow_html=True)

    # Download
    st.download_button(
        "Download Report",
        data=report,
        file_name=f"risk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


# ── Welcome Screen ───────────────────────────────────────────────────
elif not st.session_state.running:
    st.markdown("""
    <div class="welcome-card">
        <h2>Welcome</h2>
        <p>
            This framework orchestrates <strong>3 specialized agents</strong> via LangGraph
            to produce CRO-level integrated risk assessment reports.
        </p>
        <div class="feature-grid">
            <div class="feature-item">
                <div class="icon">🌍</div>
                <div class="title">Geopolitical Analyst</div>
                <div class="desc">Sanctions, tensions, supply chain</div>
            </div>
            <div class="feature-item">
                <div class="icon">💳</div>
                <div class="title">Credit Evaluator</div>
                <div class="desc">Ratios, Altman Z-Score, debt</div>
            </div>
            <div class="feature-item">
                <div class="icon">📊</div>
                <div class="title">Market Synthesizer</div>
                <div class="desc">Integrated score, scenarios, reco.</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

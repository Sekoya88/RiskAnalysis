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
import uuid

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from src.main import run_analysis
import src.db as db

# ── Page Config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Risk Assessment — Agentic Framework",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject Google Font + Professional CSS ─────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
    /* ═══════════════════════════════════════════════════
       MONO THEME (21st.dev inspired)
       High contrast black & white + clean typography
       ═══════════════════════════════════════════════════ */

    /* ── Global Reset ────────────────────────────────── */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    code, .mono {
        font-family: 'JetBrains Mono', monospace !important;
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
        background: #ffffff !important;
        color: #000000 !important;
    }

    /* ── Sidebar Expand Button (collapsed state) ─────── */
    button[data-testid="collapsedControl"] {
        background: #000000 !important;
        border: none !important;
        border-radius: 0 4px 4px 0 !important;
        color: white !important;
        box-shadow: none !important;
        transition: all 0.2s ease !important;
    }
    button[data-testid="collapsedControl"]:hover {
        background: #333333 !important;
    }
    button[data-testid="collapsedControl"] * {
        color: white !important;
    }

    /* ── Sidebar Collapse Button (expanded state) ────── */
    [data-testid="stSidebarCollapseButton"] button {
        background: transparent !important;
        border: none !important;
        color: #666666 !important;
        transition: all 0.2s ease !important;
        opacity: 0.7;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        color: #000000 !important;
        opacity: 1;
    }
    [data-testid="stSidebarCollapseButton"] button * {
        color: inherit !important;
    }

    /* ── Hide Streamlit Branding ─────────────────────── */
    #MainMenu, footer { visibility: hidden; }

    /* ── Typography ──────────────────────────────────── */
    h1, h2, h3 { color: #000000 !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }

    /* ── Main Header ─────────────────────────────────── */
    .app-header {
        text-align: left;
        padding: 2rem 0 2rem;
        border-bottom: 1px solid #eaeaea;
        margin-bottom: 2rem;
    }
    .app-header h1 {
        font-size: 2rem !important;
        font-weight: 800 !important;
        color: #000000 !important;
        letter-spacing: -0.04em;
        margin-bottom: 0.5rem;
    }
    .app-header p {
        color: #666;
        font-size: 0.9rem;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 400;
        opacity: 0.8;
    }

    /* ── Entity Badge ────────────────────────────────── */
    .entity-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.75rem;
        border: 1px solid #000;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace !important;
    }
    .entity-badge.public {
        background: #ffffff;
        color: #000000;
        border-color: #000000;
    }
    .entity-badge.private {
        background: #000000;
        color: #ffffff;
        border-color: #000000;
    }

    /* ── Metric Cards (Mono) ─────────────────────────── */
    .metric-card {
        background: #ffffff;
        border: 1px solid #eaeaea;
        border-radius: 6px;
        padding: 1.5rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .metric-card:hover {
        border-color: #000000;
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.06);
    }
    .metric-label {
        font-size: 0.7rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
        margin-bottom: 0.75rem;
        font-family: 'JetBrains Mono', monospace !important;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 600;
        color: #000000;
        letter-spacing: -0.04em;
    }
    .metric-value.score-critical { color: #000000; text-decoration: underline; text-decoration-style: double; text-decoration-color: #000000; }
    .metric-value.score-high { color: #000000; text-decoration: underline; text-decoration-style: solid; text-decoration-color: #000000; }
    .metric-value.score-moderate { color: #000000; text-decoration: underline; text-decoration-style: dashed; text-decoration-color: #666666; }
    .metric-value.score-low { color: #000000; text-decoration: underline; text-decoration-style: dotted; text-decoration-color: #999999; }

    /* ── Agent Pipeline Steps (Mono) ─────────────────── */
    .pipeline-container {
        display: flex;
        gap: 1rem;
        margin: 2rem 0;
    }
    .pipeline-step {
        flex: 1;
        background: #ffffff;
        border: 1px solid #eaeaea;
        border-radius: 6px;
        padding: 1.25rem;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .pipeline-step .step-icon {
        font-size: 1.2rem;
        margin-bottom: 0.5rem;
        opacity: 0.4;
        filter: grayscale(100%);
    }
    .pipeline-step .step-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #000000;
        font-family: 'JetBrains Mono', monospace !important;
        text-transform: uppercase;
    }
    .pipeline-step .step-status {
        font-size: 0.7rem;
        color: #666;
        margin-top: 0.25rem;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .pipeline-step.active {
        border-color: #000000;
        background: #fafafa;
    }
    .pipeline-step.active .step-icon { opacity: 1; filter: none; }
    .pipeline-step.active .step-status { color: #000000; }

    .pipeline-step.done {
        background: #ffffff;
        border-color: #eaeaea;
    }
    .pipeline-step.done .step-icon { opacity: 1; color: #000000; }
    .pipeline-step.done .step-status { color: #000000; }

    .connector { display: none; }

    /* ── Micro-animations (21st.dev style) ─────────── */
    @keyframes pulse-soft {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.85; }
    }
    @keyframes slide-up {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes border-glow {
        0%, 100% { box-shadow: 0 0 0 0 rgba(0,0,0,0); }
        50% { box-shadow: 0 0 0 3px rgba(0,0,0,0.06); }
    }
    .pipeline-step.active {
        animation: pulse-soft 2s ease-in-out infinite, border-glow 2s ease-in-out infinite;
    }
    .feature-item {
        animation: slide-up 0.5s ease-out backwards;
    }
    .feature-item:nth-child(1) { animation-delay: 0.05s; }
    .feature-item:nth-child(2) { animation-delay: 0.1s; }
    .feature-item:nth-child(3) { animation-delay: 0.15s; }

    /* ── Report Block (Mono) ────────────────────────── */
    .report-block {
        background: #ffffff;
        border: 1px solid #eaeaea;
        border-radius: 6px;
        padding: 3rem;
        margin: 2rem 0;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem;
        line-height: 1.7;
        color: #111;
        box-shadow: none;
    }
    .report-block h2 {
        border-bottom: 1px solid #000;
        padding-bottom: 0.5rem;
        margin-top: 2rem;
    }

    /* ── Sources Panel (Mono) ───────────────────────── */
    .source-card {
        background: #ffffff;
        border: 1px solid #eaeaea;
        border-radius: 6px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .source-card:hover {
        border-color: #000000;
        background: #fafafa;
        transform: translateX(4px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .source-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #000000;
        margin-bottom: 0.25rem;
        font-family: 'Inter', sans-serif !important;
    }
    .source-title a { color: #000000; text-decoration: underline; text-underline-offset: 2px; }
    .source-meta {
        font-size: 0.7rem;
        color: #666;
        font-family: 'JetBrains Mono', monospace !important;
    }
    .source-badge {
        background: #f4f4f5;
        color: #000000;
        border: 1px solid #e4e4e7;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 500;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* ── Welcome Card (Mono) ────────────────────────── */
    .welcome-card {
        background: #ffffff;
        border: 1px solid #eaeaea;
        border-radius: 8px;
        padding: 4rem 2rem;
        text-align: center;
        max-width: 800px;
        margin: 2rem auto;
        box-shadow: none;
        animation: slide-up 0.6s ease-out;
    }
    .welcome-card h2 {
        font-size: 1.5rem !important;
        margin-bottom: 0.5rem;
        color: #000000 !important;
    }
    .welcome-card p {
        color: #666;
        font-size: 0.9rem;
        line-height: 1.6;
    }

    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin-top: 2rem;
    }
    .feature-item {
        background: #ffffff;
        border: 1px solid #eaeaea;
        border-radius: 6px;
        padding: 1.5rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        text-align: left;
        cursor: default;
    }
    .feature-item:hover {
        border-color: #000000;
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    }
    .feature-item .icon {
        font-size: 1.2rem;
        margin-bottom: 0.5rem;
        color: #000;
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .feature-item:hover .icon {
        transform: scale(1.1);
    }
    .feature-item .title {
        font-size: 0.8rem;
        font-weight: 700;
        color: #000000;
        margin-bottom: 0.25rem;
    }
    .feature-item .desc {
        font-size: 0.7rem;
        color: #666;
    }

    /* ── Section Titles ──────────────────────────────── */
    .section-title {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
        margin: 2rem 0 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #eaeaea;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* ── Sidebar ─────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #f9f9f9 !important;
        border-right: 1px solid #eaeaea !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #000000 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    section[data-testid="stSidebar"] label {
        color: #333 !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    /* Toggle text — ensure visibility */
    section[data-testid="stSidebar"] label span,
    section[data-testid="stSidebar"] label p,
    section[data-testid="stSidebar"] label div,
    section[data-testid="stSidebar"] .stCheckbox label span,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] span,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        opacity: 1 !important;
    }

    /* ── Inputs & Selects ────────────────────────────── */
    .stSelectbox div[data-baseweb="select"] > div {
        background: #ffffff !important;
        border-color: #eaeaea !important;
        border-radius: 4px !important;
        color: #000000 !important;
    }
    /* FIX: Textarea text must be explicitly black — le texte ne se voit plus */
    .stTextArea textarea,
    .stTextArea textarea::placeholder,
    section[data-testid="stSidebar"] textarea,
    section[data-testid="stSidebar"] textarea::placeholder,
    [data-baseweb="textarea"] textarea,
    textarea[data-baseweb="textarea"],
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextArea"] textarea::placeholder,
    textarea {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        caret-color: #000000 !important;
    }
    .stTextArea textarea::placeholder {
        color: #999999 !important;
        -webkit-text-fill-color: #999999 !important;
        opacity: 1;
    }
    .stTextArea textarea,
    section[data-testid="stSidebar"] textarea {
        background: #ffffff !important;
        border: 1px solid #eaeaea !important;
        border-radius: 6px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
        line-height: 1.5 !important;
        padding: 0.75rem 1rem !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stTextArea textarea:focus,
    section[data-testid="stSidebar"] textarea:focus {
        border-color: #000000 !important;
        box-shadow: 0 0 0 2px rgba(0,0,0,0.08) !important;
        outline: none !important;
    }

    /* ── Buttons (with micro-animations) ─────────────── */
    .stButton > button {
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .stButton > button[kind="primary"] {
        background: #000000 !important;
        color: #ffffff !important;
        border: 1px solid #000000 !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-family: 'JetBrains Mono', monospace !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.75rem !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #333333 !important;
        border-color: #333333 !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    }
    .stButton > button[kind="primary"]:active {
        transform: translateY(0);
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    .stButton > button:not([kind="primary"]) {
        background: #ffffff !important;
        border: 1px solid #eaeaea !important;
        border-radius: 6px !important;
        color: #000000 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
    }
    .stButton > button:not([kind="primary"]):hover {
        border-color: #000000 !important;
        color: #000000 !important;
        background: #fafafa !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
    }

    /* ── Feedback Buttons — Source Cards ────────── */
    .feedback-row {
        display: flex;
        gap: 0.5rem;
        margin: 0.4rem 0 0.8rem 0;
    }
    .feedback-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.3rem 1rem;
        border-radius: 40px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        cursor: pointer;
        transition: all 0.2s cubic-bezier(0.25, 1, 0.5, 1);
        border: 2px solid;
        min-width: 80px;
        text-align: center;
    }
    .feedback-btn-useful {
        background: #000000;
        border-color: #000000;
        color: #ffffff;
    }
    .feedback-btn-useful:hover {
        background: #333333;
        border-color: #333333;
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(0,0,0,0.15);
    }
    .feedback-btn-poor {
        background: #ffffff;
        border-color: #000000;
        color: #000000;
    }
    .feedback-btn-poor:hover {
        background: #f5f5f5;
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(0,0,0,0.08);
    }
    .feedback-btn-selected {
        background: #000000 !important;
        border-color: #000000 !important;
        color: #ffffff !important;
        pointer-events: none;
    }
    .feedback-btn-ghost {
        opacity: 0.35;
        pointer-events: none;
        border-color: #ccc;
        color: #999;
    }

    /* ── Redis status indicator ──────────────────── */
    .redis-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 0.5rem 0;
    }
    .redis-indicator.redis-off {
        background: #fff3cd;
        border: 1px solid #ffc107;
        color: #856404;
    }
    .redis-indicator.redis-on {
        background: #d4edda;
        border: 1px solid #28a745;
        color: #155724;
    }
    .redis-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }
    .redis-dot.off { background: #ffc107; }
    .redis-dot.on { background: #28a745; animation: pulse-soft 1.5s ease-in-out infinite; }

    /* ── Progress bar ────────────────────────────────── */
    .stProgress > div > div {
        background: #000000 !important;
        border-radius: 2px;
    }

    /* ── Tabs ────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem !important;
        background: transparent !important;
        border-bottom: 1px solid #eaeaea !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.75rem !important;
        font-family: 'JetBrains Mono', monospace !important;
        color: #666 !important;
        padding: 0.5rem 0 !important;
        border: none !important;
        background: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        color: #000000 !important;
        border-bottom: 2px solid #000000 !important;
    }

    /* ── Download button ────────────────────────────── */
    .stDownloadButton > button {
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .stDownloadButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
    }

    /* ── Divider ─────────────────────────────────────── */
    hr { border-color: #eaeaea !important; }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>Risk Assessment Framework</h1>
    <p>Multi-Agent LLM Pipeline &nbsp;·&nbsp; LangGraph &nbsp;·&nbsp; Ollama / Gemini</p>
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

    # Model selection
    OLLAMA_MODELS = {
        "qwen3.5 (9B — fast, good tool-use)": "qwen3.5",
        "lfm2 (24B — strong reasoning)": "lfm2",
        "gemini-2.5-flash (Google API)": "gemini-2.5-flash",
    }
    model_label = st.selectbox("LLM Model", list(OLLAMA_MODELS.keys()))
    selected_model = OLLAMA_MODELS[model_label]
    os.environ["OLLAMA_MODEL"] = selected_model
    
    if selected_model.startswith("gemini"):
        api_key = st.text_input("Google API Key", type="password", placeholder="Or set GOOGLE_API_KEY in .env")
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        else:
            api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            st.warning("API Key required for Gemini.")
    else:
        api_key = "ok"

    use_redis = st.toggle("Redis (persistence)", value=False)
    if use_redis:
        st.markdown(
            '<div class="redis-indicator redis-on"><span class="redis-dot on"></span> Redis Connected</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="redis-indicator redis-off"><span class="redis-dot off"></span> In-Memory Mode</div>',
            unsafe_allow_html=True,
        )

    run_btn = st.button(
        "Run Analysis",
        type="primary",
        disabled=st.session_state.running or not query.strip() or (selected_model.startswith("gemini") and not api_key),
    )

    st.markdown("---")

    # History
    st.markdown("### History")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    reports = sorted(glob.glob(os.path.join(output_dir, "risk_report_*.md")), reverse=True)

    if reports:
        names = [os.path.basename(r) for r in reports]
        selected_report = st.selectbox("Report", names, label_visibility="collapsed")
        if st.button("View Report"):
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
        r'\n\n<div style="text-align:left; margin: 2rem 0; padding: 1rem 0; border-bottom: 2px solid #000; font-weight: 800; font-size: 1.4rem; letter-spacing: -0.02em; color: #000; text-transform: uppercase;">\1</div>\n\n',
        report_text
    )
    # 2. Section Headers
    report_text = re.sub(
        r'─{10,}\s*(.+?)\s*─{10,}',
        r'\n\n<div style="margin: 2.5rem 0 1rem 0; border-bottom: 1px solid #eaeaea; padding-bottom: 0.5rem;">'
        r'<span style="color: #000; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.05em; text-transform: uppercase; font-family: \'JetBrains Mono\', monospace;">\1</span>'
        r'</div>\n\n',
        report_text
    )
    return report_text


def _get_scores() -> dict:
    """Get risk scores from structured report (preferred) or fallback to regex parsing."""
    sr = st.session_state.get("structured_report")
    if sr and isinstance(sr, dict):
        return {
            "entity": sr.get("entity", "Unknown"),
            "overall": sr.get("overall_score", 0),
            "geopolitical": sr.get("geopolitical_score", 0),
            "credit": sr.get("credit_score", 0),
            "market": sr.get("market_score", 0),
            "esg": sr.get("esg_score", 0),
            "rating": f"{sr.get('credit_rating', 'N/A')} / {sr.get('credit_outlook', 'Stable')}",
        }

    # Fallback: regex parsing for legacy/text-only reports
    report = st.session_state.get("report", "")
    from src.state.schema import parse_report_to_structured
    parsed = parse_report_to_structured(report)
    return parsed.to_scores_dict()


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
    """Detect if an entity is publicly traded using yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return {"is_public": False, "ticker": None, "exchange": None, "currency": None}
    
    default = {"is_public": False, "ticker": None, "exchange": None, "currency": None}
    entity_words = set(re.findall(r'[A-Za-z]{3,}', entity_name.lower()))
    
    candidates = []
    
    # 1. Tickers explicitly in parentheses
    paren_match = re.findall(r'\(([A-Z0-9.\-]{1,5})\)', entity_name)
    candidates.extend([(t, True) for t in paren_match])
    
    # 2. Entire name if it looks like a pure ticker
    stripped = entity_name.strip()
    if re.match(r'^[A-Z0-9.\-]{1,5}$', stripped):
        candidates.append((stripped, True))
    
    # 3. Words that look like tickers
    parts = re.split(r'[\s\-]+', entity_name)
    for part in parts:
        clean = part.strip('().,;')
        if re.match(r'^[A-Z0-9.]{3,5}$', clean) and clean not in [c for c, _ in candidates]:
            candidates.append((clean, False))
    
    # 4. Progressive yf.Search
    clean_name = re.sub(r'\([^)]*\)', '', entity_name).strip()
    clean_name = re.sub(r'\s+', ' ', clean_name)
    words = clean_name.split()
    
    search_variants = []
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
                break
        except Exception:
            continue
    
    for ticker_str, is_explicit in candidates:
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            if not info or info.get('regularMarketPrice') is None:
                continue
            
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
    statuses = {"waiting": "WAITING", "active": "RUNNING", "done": "DONE"}

    st.markdown(f"""
    <div class="pipeline-container">
        <div class="pipeline-step {geo}">
            <div class="step-icon">🌍</div>
            <div class="step-label">Geopolitical</div>
            <div class="step-status">{statuses[geo]}</div>
        </div>
        <div class="connector">→</div>
        <div class="pipeline-step {credit}">
            <div class="step-icon">💳</div>
            <div class="step-label">Credit</div>
            <div class="step-status">{statuses[credit]}</div>
        </div>
        <div class="connector">→</div>
        <div class="pipeline-step {synth}">
            <div class="step-icon">📊</div>
            <div class="step-label">Synthesizer</div>
            <div class="step-status">{statuses[synth]}</div>
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
        badge_html = (
            f'<span class="entity-badge public">'
            f'PUBLIC — {ticker}'
            f'</span>'
        )
    else:
        badge_html = '<span class="entity-badge private">PRIVATE</span>'

    # Show entity badge above metrics
    st.markdown(f'<div style="text-align:left; margin-bottom:1rem;">{badge_html}</div>', unsafe_allow_html=True)

    cols = st.columns(6)
    items = [
        ("Entity", entity, ""),
        ("Score", f"{overall}/100", _score_class(overall)),
        ("Rating", rating, ""),
        ("Geo", f"{scores.get('geopolitical', '—')}/100", _score_class(scores.get('geopolitical', 0)) if 'geopolitical' in scores else ""),
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

        labels = ["Geopolitical", "Credit", "Market", "ESG"]
        values = [scores[k] for k in keys]
        values_closed = values + [values[0]]
        labels_closed = labels + [labels[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor="rgba(0,0,0,0.1)",
            line=dict(color="#000000", width=2),
            marker=dict(size=6, color="#000000"),
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickfont=dict(size=10, color="#666", family="JetBrains Mono"),
                    gridcolor="#eaeaea",
                    linecolor="#eaeaea",
                ),
                angularaxis=dict(
                    tickfont=dict(size=11, color="#000", family="JetBrains Mono"),
                    gridcolor="#eaeaea",
                    linecolor="#eaeaea",
                ),
                bgcolor="white",
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            height=350,
            margin=dict(l=60, r=60, t=30, b=30),
            font=dict(family="Inter", color="#000"),
        )
        st.plotly_chart(fig, width="stretch")
    except ImportError:
        pass


def _render_sources(sources: dict, report_id: str = None):
    """Render the sources panel showing data provenance and RL feedback mechanism."""
    if not sources:
        return

    has_any = any(sources.get(k) for k in ["news", "market", "rag"])
    if not has_any:
        return

    st.markdown('<div class="section-title">Sources Used</div>', unsafe_allow_html=True)

    tabs = []
    tab_keys = []
    if sources.get("news"):
        sources["news"] = sources["news"][:10]  # Force cut off at 10 items
        tabs.append(f"NEWS ({len(sources['news'])})")
        tab_keys.append("news")
    if sources.get("market"):
        tabs.append(f"MARKET ({len(sources['market'])})")
        tab_keys.append("market")
    if sources.get("rag"):
        tabs.append(f"DOCS ({len(sources['rag'])})")
        tab_keys.append("rag")

    if not tabs:
        return

    st_tabs = st.tabs(tabs)

    # Track clicked states
    if "feedback_clicked" not in st.session_state:
        st.session_state.feedback_clicked = set()

    def _save_feedback(url: str, is_helpful: bool, btn_key: str):
        if report_id:
            db.save_feedback(report_id, url, is_helpful)
            st.session_state.feedback_clicked.add(btn_key)
            st.toast(f"✅ Feedback saved! This trains our RL loop.", icon="🧠")

    for tab, key in zip(st_tabs, tab_keys):
        with tab:
            if key == "news":
                # Limit to 10 news sources
                for i, article in enumerate(sources["news"]):
                    title = html_mod.escape(article.get("title", "Untitled"))
                    url = article.get("url", "")
                    source = html_mod.escape(article.get("source", ""))
                    date = article.get("date", "")
                    date_short = date[:10] if date else ""
                    
                    # ML RL Loop Feedback Weight
                    weight = db.get_source_feedback_score(url) if url else 0.5
                    
                    # Add time decay factor if it has a date
                    from datetime import datetime
                    time_bonus = ""
                    if date_short:
                        try:
                            article_date = datetime.strptime(date_short, "%Y-%m-%d")
                            today = datetime.now()
                            days_old = (today - article_date).days
                            if days_old <= 3:
                                time_bonus = ' <span style="color:#000000; font-weight:bold; background:#eaeaea; padding:1px 4px; border-radius:3px; font-size:0.6rem;">RECENT</span>'
                                weight += 0.1
                            elif days_old <= 1:
                                time_bonus = ' <span style="color:#ffffff; font-weight:bold; background:#000000; padding:1px 4px; border-radius:3px; font-size:0.6rem;">HOT</span>'
                                weight += 0.2
                        except ValueError:
                            pass

                    weight_badge = f'<span style="font-size:0.65rem; color:#888;" title="Reinforcement Learning Confidence Score based on user feedback">ML Confidence: {weight:.2f}</span>'

                    link = f'<a href="{url}" target="_blank">{title}</a>' if url else title
                    st.markdown(f"""
                    <div class="source-card">
                        <div class="source-title">{link}{time_bonus}</div>
                        <div class="source-meta">
                            <span class="source-badge badge-news">NEWS</span>
                            <span class="source-badge badge-live">LIVE</span>
                            &nbsp; {source} {(' · ' + date_short) if date_short else ''} &nbsp;|&nbsp; {weight_badge}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if url:
                        btn_up_key = f"up_{report_id}_{i}"
                        btn_down_key = f"down_{report_id}_{i}"
                        
                        # Determine button states
                        up_clicked = btn_up_key in st.session_state.feedback_clicked
                        down_clicked = btn_down_key in st.session_state.feedback_clicked
                        
                        if up_clicked:
                            useful_cls = "feedback-btn feedback-btn-selected"
                            poor_cls = "feedback-btn feedback-btn-ghost"
                        elif down_clicked:
                            useful_cls = "feedback-btn feedback-btn-ghost"
                            poor_cls = "feedback-btn feedback-btn-selected"
                        else:
                            useful_cls = "feedback-btn feedback-btn-useful"
                            poor_cls = "feedback-btn feedback-btn-poor"
                        
                        # Render styled HTML buttons with Streamlit fallback for interactivity
                        col1, col2, _ = st.columns([1, 1, 8])
                        with col1:
                            if up_clicked or down_clicked:
                                st.markdown(f'<div class="{useful_cls}">USEFUL</div>', unsafe_allow_html=True)
                            else:
                                if st.button("✓ USEFUL", key=f"up_{btn_up_key}", help="Train model to prefer this source"):
                                    _save_feedback(url, True, btn_up_key)
                                    st.rerun()
                        with col2:
                            if up_clicked or down_clicked:
                                st.markdown(f'<div class="{poor_cls}">POOR</div>', unsafe_allow_html=True)
                            else:
                                if st.button("✗ POOR", key=f"down_{btn_down_key}", help="Train model to avoid this source"):
                                    _save_feedback(url, False, btn_down_key)
                                    st.rerun()

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
                            <span class="source-badge badge-market">MARKET</span>
                            <span class="source-badge badge-live">LIVE</span>
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
                            <span class="source-badge badge-static">STATIC</span>
                            &nbsp; {company} · {doc_type} · Score: {score:.2f}
                        </div>
                        <div style="font-size:0.75rem; color:#666; line-height:1.5; background:#fafafa; padding:0.5rem; border-radius:4px; border:1px solid #eaeaea; font-family:'JetBrains Mono', monospace;">
                            {content_preview}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)


# ── Main — Run Analysis ──────────────────────────────────────────────
if run_btn and query.strip() and not st.session_state.running:
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

    result_holder = {"report": None, "sources": None, "token_usage": None, "structured_report": None, "error": None}

    def _run_in_thread():
        import asyncio as _asyncio
        try:
            loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(loop)
            r, s, t, sr = loop.run_until_complete(run_analysis(query=query, use_redis=use_redis))
            result_holder["report"] = r
            result_holder["sources"] = s
            result_holder["token_usage"] = t
            result_holder["structured_report"] = sr
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
                f"<p style='text-align:center; color:#a1a1aa; font-size:0.75rem; font-family:\"JetBrains Mono\"'>"
                f"⏱ {elapsed:.0f}s</p>",
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
            f"<div style='padding:0.2rem 0;font-size:0.72rem;color:#333;border-bottom:1px solid #eaeaea;font-family:\"JetBrains Mono\", monospace;'>"
            f"<span style='color:#999;font-size:0.65rem;margin-right:0.5rem;'>{i+1:02d}</span>{line}</div>"
            for i, line in enumerate(log_lines[-12:])  # Show last 12 lines
        )
        log_container.markdown(
            f'<div style="background:#FFFFFF;border:1px solid #eaeaea;border-radius:6px;'
            f'padding:0.8rem 1rem;max-height:220px;overflow-y:auto;">{log_html}</div>',
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
        st.session_state.structured_report = result_holder["structured_report"]
        st.session_state.elapsed = elapsed

        # Save report to history DB
        st.session_state.report_id = str(uuid.uuid4())
        scores = _get_scores()
        entity = scores.get("entity", "N/A").strip()
        if entity and entity != "N/A":
            db.save_report(st.session_state.report_id, entity, scores, st.session_state.report, st.session_state.sources)

        with pipeline_placeholder.container():
            _render_pipeline("done", "done", "done")
        progress_bar.progress(100)
        time_placeholder.markdown(
            f"<p style='text-align:center; color:#000; font-weight:600; font-size:0.85rem; font-family:\"JetBrains Mono\"'>"
            f"✅ DONE IN {elapsed:.0f}s</p>",
            unsafe_allow_html=True,
        )

    st.session_state.running = False


# ── Main — Display Report ────────────────────────────────────────────
if st.session_state.report:
    report = st.session_state.report
    scores = _get_scores()

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
            saved_html = f' <span style="color:#22c55e;font-size:0.7rem;">(SAVED ${saved:.4f})</span>'

        rows_html = ""
        for t in token_usage:
            agent_name = t.get("agent", "").replace("_", " ").upper()
            rows_html += (
                f'<tr>'
                f'<td style="font-weight:600;color:#000;padding:0.35rem 0.5rem;font-family:\"JetBrains Mono\"">{agent_name}</td>'
                f'<td style="text-align:right;padding:0.35rem 0.5rem;font-family:\"JetBrains Mono\"">{t.get("input", 0):,}</td>'
                f'<td style="text-align:right;padding:0.35rem 0.5rem;font-family:\"JetBrains Mono\"">{t.get("output", 0):,}</td>'
                f'<td style="text-align:right;padding:0.35rem 0.5rem;color:#666;font-family:\"JetBrains Mono\"">{t.get("cached", 0):,}</td>'
                f'</tr>'
            )

        token_html = (
            '<div style="background:#FFFFFF;border:1px solid #eaeaea;border-radius:6px;'
            'padding:1.2rem 1.5rem;margin:1rem 0;">'
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem;">'
            '<span style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.05em;color:#666;font-family:\"JetBrains Mono\"">TOKEN USAGE</span>'
            f'<span style="font-size:0.85rem;font-weight:700;color:#000;font-family:\"JetBrains Mono\"">'
            f'${total_cost:.4f}{saved_html}</span>'
            '</div>'
            '<table style="width:100%;font-size:0.7rem;color:#333;border-collapse:collapse;table-layout:fixed;">'
            '<colgroup><col style="width:46%;"><col style="width:18%;"><col style="width:18%;"><col style="width:18%;"></colgroup>'
            '<thead><tr style="border-bottom:1px solid #eaeaea;">'
            '<th style="text-align:left;padding:0.4rem 0.5rem;color:#999;font-weight:600;">AGENT</th>'
            '<th style="text-align:right;padding:0.4rem 0.5rem;color:#999;font-weight:600;">INPUT</th>'
            '<th style="text-align:right;padding:0.4rem 0.5rem;color:#999;font-weight:600;">OUTPUT</th>'
            '<th style="text-align:right;padding:0.4rem 0.5rem;color:#999;font-weight:600;">CACHED</th>'
            '</tr></thead>'
            f'<tbody>{rows_html}'
            '<tr style="border-top:1px solid #eaeaea;font-weight:700;">'
            f'<td style="padding-top:0.4rem;padding-left:0.5rem;color:#000;">TOTAL</td>'
            f'<td style="text-align:right;padding-top:0.4rem;padding-right:0.5rem;font-family:\"JetBrains Mono\"">{total_in:,}</td>'
            f'<td style="text-align:right;padding-top:0.4rem;padding-right:0.5rem;font-family:\"JetBrains Mono\"">{total_out:,}</td>'
            f'<td style="text-align:right;padding-top:0.4rem;padding-right:0.5rem;color:#666;font-family:\"JetBrains Mono\"">{total_cached:,}</td>'
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
                <p style="color:#666; font-size:0.8rem; margin-bottom:1rem; font-family:'JetBrains Mono'">
                    <strong>RISK LEVEL:</strong>
                    <span style="font-size:1.1rem; font-weight:700;" class="{_score_class(overall)}">{label} ({overall}/100)</span>
                </p>
                <p style="color:#666; font-size:0.8rem; margin-bottom:0.5rem; font-family:'JetBrains Mono'">
                    <strong>RATING:</strong> {scores.get('rating', 'N/A')}
                </p>
                <p style="color:#666; font-size:0.8rem; margin-bottom:0.5rem; font-family:'JetBrains Mono'">
                    <strong>GEO:</strong> {scores.get('geopolitical', '—')}/100
                    &nbsp;|&nbsp; <strong>CREDIT:</strong> {scores.get('credit', '—')}/100
                </p>
                <p style="color:#666; font-size:0.8rem; font-family:'JetBrains Mono'">
                    <strong>MARKET:</strong> {scores.get('market', '—')}/100
                    &nbsp;|&nbsp; <strong>ESG:</strong> {scores.get('esg', '—')}/100
                </p>
            </div>
            """, unsafe_allow_html=True)
            
    # Display Score Over Time Chart
    entity_name = scores.get("entity", "N/A").strip()
    if entity_name and entity_name != "N/A":
        history = db.get_history_for_entity(entity_name)
        if len(history) > 0:
            st.markdown('<div class="section-title">Score Over Time & Key News</div>', unsafe_allow_html=True)
            try:
                import plotly.graph_objects as go
                import sqlite3
                
                dates = [row['timestamp'] for row in history]
                overalls = [row['overall_score'] for row in history]
                report_ids = [row['id'] for row in history]
                
                # Fetch news titles for tooltips
                conn = sqlite3.connect(db.DB_PATH)
                c = conn.cursor()
                hover_texts = []
                for rid, score, date in zip(report_ids, overalls, dates):
                    c.execute("SELECT title, source FROM report_news WHERE report_id = ? LIMIT 3", (rid,))
                    news_items = c.fetchall()
                    if news_items:
                        news_str = "<br>".join([f"- {n[1]}: {n[0][:40]}..." for n in news_items])
                        hover_texts.append(f"<b>Score: {score}</b><br>Date: {date[:10]}<br><br><i>Key News:</i><br>{news_str}")
                    else:
                        hover_texts.append(f"<b>Score: {score}</b><br>Date: {date[:10]}")
                conn.close()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, y=overalls,
                    mode='lines+markers',
                    name='Overall Risk Score',
                    text=hover_texts,
                    hoverinfo='text',
                    line=dict(color='#000000', width=3),
                    marker=dict(size=8, color='#000000')
                ))
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Risk Score",
                    yaxis=dict(range=[0, 100]),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=300,
                    margin=dict(l=40, r=40, t=30, b=30),
                    font=dict(family="Inter", color="#000")
                )
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#eaeaea')
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#eaeaea')
                st.plotly_chart(fig, width="stretch")
            except ImportError:
                st.caption("Plotly not installed. Historical scores cannot be charted.")

    # Sources panel
    _render_sources(st.session_state.sources, st.session_state.get("report_id", "demo-report"))

    # Full report
    formatted_report = _format_report_html(report)
    st.markdown('<div class="section-title">Full Report</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="report-block">\n\n{formatted_report}\n\n</div>', unsafe_allow_html=True)

    # Download
    st.download_button(
        "DOWNLOAD REPORT",
        data=report,
        file_name=f"risk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",

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
                <div class="title">GEOPOLITICAL</div>
                <div class="desc">Sanctions, tensions, supply chain</div>
            </div>
            <div class="feature-item">
                <div class="icon">💳</div>
                <div class="title">CREDIT</div>
                <div class="desc">Ratios, Altman Z-Score, debt</div>
            </div>
            <div class="feature-item">
                <div class="icon">📊</div>
                <div class="title">MARKET</div>
                <div class="desc">Integrated score, scenarios</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

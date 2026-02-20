"""
Streamlit Web Interface — Agentic Risk Assessment Framework.

Provides a visual dashboard to:
  - Submit risk analysis queries
  - Monitor agent progress in real-time
  - View formatted final reports
  - Browse report history

Launch:
    streamlit run app.py
"""

import asyncio
import glob
import os
import re
import time
from datetime import datetime

import streamlit as st

from src.main import run_analysis

# ── Page Configuration ────────────────────────────────────────────────
st.set_page_config(
    page_title="🌐 Risk Assessment Framework",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark premium theme overrides */
    .stApp {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0d1b2a 100%);
    }

    /* Animated gradient header */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #6B8DD6 100%);
        background-size: 200% 200%;
        animation: gradient-shift 6s ease infinite;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0.5rem;
        font-family: 'Inter', sans-serif;
    }

    @keyframes gradient-shift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .sub-header {
        text-align: center;
        color: #8892b0;
        font-size: 1rem;
        margin-bottom: 2rem;
        letter-spacing: 0.5px;
    }

    /* Glassmorphism cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    /* Risk score badges */
    .risk-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
    }
    .risk-critical { background: #ff4757; color: white; }
    .risk-high { background: #ff6348; color: white; }
    .risk-moderate { background: #ffa502; color: #1a1a2e; }
    .risk-low { background: #2ed573; color: #1a1a2e; }

    /* Agent progress indicators */
    .agent-step {
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        border-left: 3px solid #667eea;
        background: rgba(102, 126, 234, 0.08);
        border-radius: 0 8px 8px 0;
    }

    .agent-step.completed {
        border-left-color: #2ed573;
        background: rgba(46, 213, 115, 0.08);
    }

    .agent-step.active {
        border-left-color: #ffa502;
        background: rgba(255, 165, 2, 0.08);
        animation: pulse-border 2s ease infinite;
    }

    @keyframes pulse-border {
        0%, 100% { border-left-color: #ffa502; }
        50% { border-left-color: #ff6348; }
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: rgba(15, 15, 35, 0.95);
        backdrop-filter: blur(10px);
    }

    /* Button styling */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        font-weight: 700;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }

    /* Report container */
    .report-container {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 2rem;
        font-family: 'Fira Code', 'Courier New', monospace;
        font-size: 0.9rem;
        line-height: 1.6;
    }

    /* Metrics cards */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🌐 Agentic Risk Assessment</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">'
    'Multi-Agent LLM System · LangGraph · Gemini 2.5 Flash · ChromaDB'
    '</div>',
    unsafe_allow_html=True,
)


# ── Predefined Query Examples ────────────────────────────────────────
EXAMPLE_QUERIES = {
    "🍎 Apple (AAPL) — Supply Chain China/Taiwan": (
        "Perform a comprehensive credit and geopolitical risk assessment for "
        "Apple Inc. (AAPL), considering its supply chain exposure to China and "
        "Taiwan, the current US-China semiconductor tensions, and its financial "
        "health. Provide an integrated risk report with quantified risk scores."
    ),
    "🟢 NVIDIA (NVDA) — AI Chips & Export Controls": (
        "Perform a comprehensive risk assessment for NVIDIA Corp (NVDA), "
        "focusing on US-China export controls on AI chips, the CHIPS Act "
        "impact, and NVIDIA's revenue exposure to Chinese data centers. "
        "Include financial health analysis and quantified risk scores."
    ),
    "🚗 Volkswagen (VOW3.DE) — EV & Chinese Competition": (
        "Assess the credit and geopolitical risk for Volkswagen AG (VOW3.DE), "
        "considering EU EV regulations, Chinese competition from BYD, and "
        "Volkswagen's exposure to the Russian market write-downs. Quantify risk."
    ),
    "🛢️ TotalEnergies (TTE.PA) — Middle East & Transition": (
        "Evaluate the integrated risk profile of TotalEnergies SE (TTE.PA), "
        "focusing on Middle East tensions, Strait of Hormuz transit risk, "
        "energy transition pressures, and its diversification into renewables."
    ),
    "🏦 Deutsche Bank (DB) — Banking & Sovereign Risk": (
        "Perform a credit risk assessment for Deutsche Bank (DB), analyzing "
        "European banking sector stress, commercial real estate exposure, "
        "interest rate environment, and sovereign debt risks in the Eurozone."
    ),
    "✏️ Requête personnalisée": "",
}

# ── Session State Initialization ─────────────────────────────────────
if "running" not in st.session_state:
    st.session_state.running = False
if "report" not in st.session_state:
    st.session_state.report = None
if "elapsed" not in st.session_state:
    st.session_state.elapsed = 0


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.divider()

    selected_example = st.selectbox(
        "📋 Exemples de requêtes",
        list(EXAMPLE_QUERIES.keys()),
        help="Choisissez une requête d'exemple ou écrivez la vôtre",
    )

    default_query = EXAMPLE_QUERIES[selected_example]
    query = st.text_area(
        "📝 Requête d'analyse",
        value=default_query,
        height=180,
        placeholder="Ex: Assess credit risk for Tesla Inc. considering...",
    )

    st.divider()
    use_redis = st.checkbox(
        "🔴 Utiliser Redis (persistance)",
        value=False,
        help="Nécessite un serveur Redis en cours d'exécution",
    )

    run_btn = st.button(
        "🚀 Lancer l'Analyse",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.running or not query,
    )

    st.divider()

    # ── Report History ────────────────────────────────────────────────
    st.markdown("### 📂 Historique des rapports")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    reports = sorted(glob.glob(os.path.join(output_dir, "risk_report_*.md")), reverse=True)

    if reports:
        report_names = [os.path.basename(r) for r in reports]
        selected_report = st.selectbox("Rapports sauvegardés", report_names)
        if st.button("📖 Voir ce rapport", use_container_width=True):
            report_path = os.path.join(output_dir, selected_report)
            with open(report_path) as f:
                st.session_state.report = f.read()
            st.session_state.elapsed = 0
    else:
        st.info("Aucun rapport généré pour l'instant.")


# ── Helper: Extract risk score from report ────────────────────────────
def _parse_risk_score(report: str) -> dict:
    """Extract risk scores from the report text."""
    scores = {}
    # Overall
    m = re.search(r"OVERALL RISK SCORE:\s*(\d+)/100", report)
    if m:
        scores["overall"] = int(m.group(1))
    # Sub-scores
    for label, key in [
        ("Geopolitical Risk:", "geopolitical"),
        ("Credit/Financial:", "credit"),
        ("Market/Liquidity:", "market"),
        ("ESG/Transition:", "esg"),
    ]:
        m = re.search(rf"{re.escape(label)}\s*(\d+)/100", report)
        if m:
            scores[key] = int(m.group(1))
    # Rating
    m = re.search(r"INTERNAL CREDIT RATING:\s*(.+)", report)
    if m:
        scores["rating"] = m.group(1).strip()
    # Entity
    m = re.search(r"ENTITY:\s*(.+)", report)
    if m:
        scores["entity"] = m.group(1).strip()
    return scores


def _score_color(score: int) -> str:
    if score >= 75:
        return "#ff4757"
    elif score >= 50:
        return "#ff6348"
    elif score >= 30:
        return "#ffa502"
    return "#2ed573"


# ── Main Area — Analysis Execution ────────────────────────────────────
if run_btn and query:
    st.session_state.running = True
    st.session_state.report = None

    # Pipeline progress display
    progress_container = st.container()

    with progress_container:
        st.markdown("### 🔄 Analyse en cours...")

        # Create progress placeholders
        col1, col2, col3 = st.columns(3)
        with col1:
            geo_status = st.empty()
            geo_status.markdown(
                '<div class="agent-step">⏳ 🌍 Geopolitical Analyst</div>',
                unsafe_allow_html=True,
            )
        with col2:
            credit_status = st.empty()
            credit_status.markdown(
                '<div class="agent-step">⏳ 💳 Credit Evaluator</div>',
                unsafe_allow_html=True,
            )
        with col3:
            synth_status = st.empty()
            synth_status.markdown(
                '<div class="agent-step">⏳ 📊 Market Synthesizer</div>',
                unsafe_allow_html=True,
            )

        progress_bar = st.progress(0, text="Initializing agents...")
        time_display = st.empty()

    # Run the analysis
    start_time = time.time()

    try:
        # Update progress as analysis runs
        progress_bar.progress(5, text="🧠 Supervisor routing to Geopolitical Analyst...")
        geo_status.markdown(
            '<div class="agent-step active">🔄 🌍 Geopolitical Analyst — analyzing...</div>',
            unsafe_allow_html=True,
        )

        report = asyncio.run(run_analysis(query=query, use_redis=use_redis))

        elapsed = time.time() - start_time
        st.session_state.report = report
        st.session_state.elapsed = elapsed

        # Mark all as completed
        geo_status.markdown(
            '<div class="agent-step completed">✅ 🌍 Geopolitical Analyst</div>',
            unsafe_allow_html=True,
        )
        credit_status.markdown(
            '<div class="agent-step completed">✅ 💳 Credit Evaluator</div>',
            unsafe_allow_html=True,
        )
        synth_status.markdown(
            '<div class="agent-step completed">✅ 📊 Market Synthesizer</div>',
            unsafe_allow_html=True,
        )
        progress_bar.progress(100, text="✅ Analysis completed!")
        time_display.metric("⏱️ Temps d'exécution", f"{elapsed:.1f}s")

    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse : {e}")
        progress_bar.progress(0, text="❌ Échec")

    st.session_state.running = False


# ── Main Area — Report Display ────────────────────────────────────────
if st.session_state.report:
    report = st.session_state.report

    st.divider()
    st.markdown("## 📊 Rapport d'Analyse Intégré")

    # Parse and display scores
    scores = _parse_risk_score(report)

    if scores.get("overall") is not None:
        # Score metrics row
        cols = st.columns(6)
        with cols[0]:
            entity = scores.get("entity", "N/A")
            st.metric("🏢 Entité", entity)
        with cols[1]:
            overall = scores["overall"]
            color = _score_color(overall)
            st.metric("🎯 Score Global", f"{overall}/100")
        with cols[2]:
            st.metric("📜 Rating", scores.get("rating", "N/A"))
        with cols[3]:
            geo = scores.get("geopolitical", "—")
            st.metric("🌍 Géopolitique", f"{geo}/100" if isinstance(geo, int) else geo)
        with cols[4]:
            credit = scores.get("credit", "—")
            st.metric("💳 Crédit", f"{credit}/100" if isinstance(credit, int) else credit)
        with cols[5]:
            market = scores.get("market", "—")
            st.metric("📈 Marché", f"{market}/100" if isinstance(market, int) else market)

        # Risk radar chart
        if all(k in scores for k in ["geopolitical", "credit", "market", "esg"]):
            try:
                import plotly.graph_objects as go

                fig = go.Figure()
                categories = ["Géopolitique", "Crédit", "Marché", "ESG"]
                values = [
                    scores["geopolitical"],
                    scores["credit"],
                    scores["market"],
                    scores["esg"],
                ]
                # Close the polygon
                categories_closed = categories + [categories[0]]
                values_closed = values + [values[0]]

                fig.add_trace(go.Scatterpolar(
                    r=values_closed,
                    theta=categories_closed,
                    fill="toself",
                    fillcolor="rgba(102, 126, 234, 0.2)",
                    line=dict(color="#667eea", width=2),
                    marker=dict(size=8, color="#667eea"),
                    name="Risk Score",
                ))

                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100],
                            tickfont=dict(color="#8892b0"),
                            gridcolor="rgba(255,255,255,0.1)",
                        ),
                        angularaxis=dict(
                            tickfont=dict(color="#ccd6f6", size=13),
                            gridcolor="rgba(255,255,255,0.1)",
                        ),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    height=400,
                    margin=dict(l=80, r=80, t=40, b=40),
                    font=dict(color="#ccd6f6"),
                )

                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                st.info("Installez plotly pour voir le graphique radar : `pip install plotly`")

    # Full report text
    st.divider()
    with st.expander("📄 Rapport complet (texte)", expanded=True):
        st.text(report)

    # Download button
    st.download_button(
        label="⬇️ Télécharger le rapport (.md)",
        data=report,
        file_name=f"risk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",
        use_container_width=True,
    )

elif not st.session_state.running:
    # Welcome message when no report is loaded
    st.markdown("""
    <div class="glass-card">
        <h3 style="color: #ccd6f6; margin-bottom: 1rem;">👋 Bienvenue !</h3>
        <p style="color: #8892b0; line-height: 1.8;">
            Ce framework utilise <strong>3 agents spécialisés</strong> orchestrés par
            <strong>LangGraph</strong> pour produire des rapports de risque de niveau CRO :
        </p>
        <ul style="color: #8892b0; line-height: 2;">
            <li>🌍 <strong>Geopolitical Analyst</strong> — Sanctions, tensions, supply chain</li>
            <li>💳 <strong>Credit Evaluator</strong> — Ratios financiers, Altman Z-Score, dette</li>
            <li>📊 <strong>Market Synthesizer</strong> — Score intégré, scénarios, recommandations</li>
        </ul>
        <p style="color: #667eea; font-weight: 600; margin-top: 1rem;">
            ← Choisissez une requête dans la sidebar et lancez l'analyse
        </p>
    </div>
    """, unsafe_allow_html=True)

"""
Streamlit Web Interface — Agentic Risk Assessment Framework.

Professional risk analysis dashboard with:
  - Clean, minimal design
  - Real-time agent progress tracking
  - Interactive risk score visualisation
  - Report history management

Launch:  streamlit run app.py
"""

import asyncio
import glob
import os
import re
import time
from datetime import datetime

import streamlit as st

from src.main import run_analysis

# ── Page Config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Risk Assessment — Agentic Framework",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject Google Font + Professional CSS ─────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
    /* ── Global Reset ────────────────────────────────── */
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

    .stApp {
        background-color: #fafbfc;
    }

    /* Hide Streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Typography ──────────────────────────────────── */
    h1, h2, h3 { color: #1a1a2e !important; font-weight: 700 !important; }

    /* ── Main Header ─────────────────────────────────── */
    .app-header {
        text-align: center;
        padding: 2rem 0 1rem;
    }
    .app-header h1 {
        font-size: 1.8rem !important;
        font-weight: 800 !important;
        color: #1a1a2e !important;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem;
    }
    .app-header p {
        color: #6b7280;
        font-size: 0.85rem;
        font-weight: 400;
        letter-spacing: 0.3px;
    }

    /* ── Metric Cards ────────────────────────────────── */
    .metric-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .metric-card:hover {
        border-color: #d1d5db;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        transform: translateY(-1px);
    }
    .metric-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #9ca3af;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a2e;
    }
    .metric-value.score-critical { color: #dc2626; }
    .metric-value.score-high { color: #ea580c; }
    .metric-value.score-moderate { color: #d97706; }
    .metric-value.score-low { color: #16a34a; }

    /* ── Agent Pipeline Steps ────────────────────────── */
    .pipeline-container {
        display: flex;
        gap: 0.5rem;
        margin: 1rem 0;
    }
    .pipeline-step {
        flex: 1;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    .pipeline-step .step-icon { font-size: 1.3rem; margin-bottom: 0.3rem; }
    .pipeline-step .step-label {
        font-size: 0.72rem;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .pipeline-step .step-status {
        font-size: 0.7rem;
        font-weight: 500;
        margin-top: 0.3rem;
    }

    .pipeline-step.waiting { border-color: #e5e7eb; }
    .pipeline-step.waiting .step-status { color: #9ca3af; }

    .pipeline-step.active {
        border-color: #3b82f6;
        background: #eff6ff;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
    }
    .pipeline-step.active .step-status { color: #3b82f6; font-weight: 600; }
    .pipeline-step.active::after {
        content: '';
        position: absolute;
        bottom: 0; left: 0;
        width: 100%; height: 3px;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        animation: progress-bar 3s ease-in-out infinite;
    }

    .pipeline-step.done {
        border-color: #22c55e;
        background: #f0fdf4;
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
        color: #d1d5db;
        font-size: 1rem;
        padding: 0 0.1rem;
    }
    .connector.active { color: #3b82f6; }
    .connector.done { color: #22c55e; }

    /* ── Report Block ────────────────────────────────── */
    .report-block {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 2rem;
        margin: 1rem 0;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.88rem;
        line-height: 1.8;
        color: #374151;
        white-space: pre-wrap;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── Welcome Card ────────────────────────────────── */
    .welcome-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 3rem 2rem;
        text-align: center;
        max-width: 680px;
        margin: 2rem auto;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .welcome-card h2 {
        font-size: 1.4rem !important;
        margin-bottom: 0.8rem;
    }
    .welcome-card p { color: #6b7280; font-size: 0.9rem; line-height: 1.7; }

    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin-top: 1.5rem;
    }
    .feature-item {
        background: #f9fafb;
        border: 1px solid #f3f4f6;
        border-radius: 10px;
        padding: 1.2rem 1rem;
        transition: all 0.2s ease;
    }
    .feature-item:hover {
        border-color: #e5e7eb;
        background: #f3f4f6;
    }
    .feature-item .icon { font-size: 1.5rem; margin-bottom: 0.4rem; }
    .feature-item .title {
        font-size: 0.78rem;
        font-weight: 600;
        color: #1a1a2e;
    }
    .feature-item .desc {
        font-size: 0.7rem;
        color: #9ca3af;
        margin-top: 0.2rem;
    }

    /* ── Section Titles ──────────────────────────────── */
    .section-title {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #9ca3af;
        margin: 1.5rem 0 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #f3f4f6;
    }

    /* ── Sidebar ─────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: white !important;
        border-right: 1px solid #e5e7eb !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #1a1a2e !important;
    }
    section[data-testid="stSidebar"] label {
        color: #374151 !important;
        font-weight: 500 !important;
        font-size: 0.8rem !important;
    }

    /* ── Buttons ──────────────────────────────────────── */
    .stButton > button[kind="primary"] {
        background-color: #1a1a2e !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #2d2d50 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(26,26,46,0.2) !important;
    }
    .stButton > button:not([kind="primary"]) {
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 0.8rem !important;
        border-color: #e5e7eb !important;
        color: #374151 !important;
    }

    /* ── Progress bar ────────────────────────────────── */
    .stProgress > div > div {
        background-color: #22c55e !important;
        border-radius: 4px;
    }

    /* ── Hide default metrics styling ────────────────── */
    div[data-testid="stMetric"] {
        background: transparent;
        border: none;
        padding: 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📊 Risk Assessment Framework</h1>
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
    "Requête personnalisée": "",
}

# ── Session State ─────────────────────────────────────────────────────
for key, default in [("running", False), ("report", None), ("elapsed", 0)]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    selected = st.selectbox("Requête type", list(EXAMPLE_QUERIES.keys()))
    query = st.text_area(
        "Requête d'analyse",
        value=EXAMPLE_QUERIES[selected],
        height=140,
        placeholder="Décrivez l'analyse de risque souhaitée...",
    )

    use_redis = st.toggle("Redis (persistance)", value=False)

    run_btn = st.button(
        "🚀  Lancer l'Analyse",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.running or not query.strip(),
    )

    st.markdown("---")

    # History
    st.markdown("### 📂 Historique")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    reports = sorted(glob.glob(os.path.join(output_dir, "risk_report_*.md")), reverse=True)

    if reports:
        names = [os.path.basename(r) for r in reports]
        selected_report = st.selectbox("Rapport", names, label_visibility="collapsed")
        if st.button("Voir ce rapport", use_container_width=True):
            with open(os.path.join(output_dir, selected_report)) as f:
                content = f.read()
            # Strip the markdown header to show only the report body
            idx = content.find("---\n\n")
            st.session_state.report = content[idx + 5:].strip() if idx >= 0 else content
            st.session_state.elapsed = 0
    else:
        st.caption("Aucun rapport disponible.")


# ── Helpers ───────────────────────────────────────────────────────────
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
    if score >= 75: return "Critique"
    if score >= 50: return "Élevé"
    if score >= 30: return "Modéré"
    return "Faible"


def _render_pipeline(geo="waiting", credit="waiting", synth="waiting"):
    """Render the 3-agent pipeline status bar."""
    icons = {"waiting": "⏳", "active": "🔄", "done": "✅"}
    statuses = {"waiting": "En attente", "active": "En cours...", "done": "Terminé"}

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
    """Render the score metric cards."""
    overall = scores.get("overall")
    if overall is None:
        return

    cls = _score_class(overall)
    entity = scores.get("entity", "N/A")
    rating = scores.get("rating", "N/A")

    cols = st.columns(6)
    items = [
        ("Entité", entity, ""),
        ("Score Global", f"{overall}/100", cls),
        ("Rating", rating, ""),
        ("Géopolitique", f"{scores.get('geopolitical', '—')}/100", _score_class(scores.get('geopolitical', 0)) if 'geopolitical' in scores else ""),
        ("Crédit", f"{scores.get('credit', '—')}/100", _score_class(scores.get('credit', 0)) if 'credit' in scores else ""),
        ("Marché", f"{scores.get('market', '—')}/100", _score_class(scores.get('market', 0)) if 'market' in scores else ""),
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

        labels = ["Géopolitique", "Crédit / Financier", "Marché / Liquidité", "ESG / Transition"]
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


# ── Main — Run Analysis ──────────────────────────────────────────────
if run_btn and query.strip():
    st.session_state.running = True
    st.session_state.report = None

    st.markdown('<div class="section-title">Pipeline d\'analyse</div>', unsafe_allow_html=True)
    pipeline_placeholder = st.empty()
    progress_bar = st.progress(0)
    time_placeholder = st.empty()

    with pipeline_placeholder.container():
        _render_pipeline("active", "waiting", "waiting")

    progress_bar.progress(10)

    start = time.time()

    try:
        report = asyncio.run(run_analysis(query=query, use_redis=use_redis))
        elapsed = time.time() - start
        st.session_state.report = report
        st.session_state.elapsed = elapsed

        with pipeline_placeholder.container():
            _render_pipeline("done", "done", "done")
        progress_bar.progress(100)
        time_placeholder.markdown(
            f"<p style='text-align:center; color:#16a34a; font-weight:600; font-size:0.85rem;'>"
            f"✅ Analyse terminée en {elapsed:.0f}s</p>",
            unsafe_allow_html=True,
        )
    except Exception as e:
        with pipeline_placeholder.container():
            _render_pipeline("done", "done", "waiting")
        st.error(f"Erreur : {e}")

    st.session_state.running = False


# ── Main — Display Report ────────────────────────────────────────────
if st.session_state.report:
    report = st.session_state.report
    scores = _parse_scores(report)

    # Metrics
    st.markdown('<div class="section-title">Scores de risque</div>', unsafe_allow_html=True)
    _render_metrics(scores)

    # Radar chart
    if all(k in scores for k in ["geopolitical", "credit", "market", "esg"]):
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown('<div class="section-title">Radar de risque</div>', unsafe_allow_html=True)
            _render_radar(scores)
        with col_right:
            # Quick summary
            st.markdown('<div class="section-title">Synthèse rapide</div>', unsafe_allow_html=True)
            overall = scores.get("overall", 0)
            label = _score_label(overall)
            st.markdown(f"""
            <div class="metric-card" style="text-align:left; padding:1.5rem;">
                <p style="color:#6b7280; font-size:0.8rem; margin-bottom:1rem;">
                    <strong>Niveau de risque :</strong>
                    <span style="font-size:1.1rem; font-weight:700;" class="{_score_class(overall)}">{label} ({overall}/100)</span>
                </p>
                <p style="color:#6b7280; font-size:0.8rem; margin-bottom:0.5rem;">
                    <strong>Rating interne :</strong> {scores.get('rating', 'N/A')}
                </p>
                <p style="color:#6b7280; font-size:0.8rem; margin-bottom:0.5rem;">
                    <strong>Géopolitique :</strong> {scores.get('geopolitical', '—')}/100
                    &nbsp;|&nbsp; <strong>Crédit :</strong> {scores.get('credit', '—')}/100
                </p>
                <p style="color:#6b7280; font-size:0.8rem;">
                    <strong>Marché :</strong> {scores.get('market', '—')}/100
                    &nbsp;|&nbsp; <strong>ESG :</strong> {scores.get('esg', '—')}/100
                </p>
            </div>
            """, unsafe_allow_html=True)

    # Full report
    st.markdown('<div class="section-title">Rapport complet</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="report-block">{report}</div>', unsafe_allow_html=True)

    # Download
    st.download_button(
        "⬇️  Télécharger le rapport",
        data=report,
        file_name=f"risk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


# ── Welcome Screen ───────────────────────────────────────────────────
elif not st.session_state.running:
    st.markdown("""
    <div class="welcome-card">
        <h2>Bienvenue</h2>
        <p>
            Ce framework orchestre <strong>3 agents spécialisés</strong> via LangGraph
            pour produire des rapports de risque intégrés de niveau CRO.
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
                <div class="desc">Ratios, Altman Z-Score, dette</div>
            </div>
            <div class="feature-item">
                <div class="icon">📊</div>
                <div class="title">Market Synthesizer</div>
                <div class="desc">Score intégré, scénarios, reco.</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

from __future__ import annotations

from typing import Any

from src.theme import THEME


def inject_global_css(st_api: Any, theme: dict[str, str] | None = None) -> None:
    if st_api is None:
        return
    theme = theme or THEME
    st_api.markdown(
        f"""
        <style>
        html, body {{
            color-scheme: dark;
            background: var(--background);
        }}
        :root {{
            --primary: {theme["primary"]};
            --secondary: {theme["secondary"]};
            --background: {theme["background"]};
            --surface: {theme["surface"]};
            --card: {theme["card"]};
            --sidebar: {theme["sidebar"]};
            --text: {theme["text"]};
            --muted-text: {theme["muted_text"]};
            --border: {theme["border"]};
            --accent: {theme["accent"]};
            --danger: {theme["danger"]};
            --warning: {theme["warning"]};
            --success: {theme["success"]};
            --table-header: {theme["table_header"]};
            --chart-grid: {theme["chart_grid"]};
            --shadow: {theme["shadow"]};
            --accent-soft: {theme["accent_soft"]};
            --success-soft: {theme["success_soft"]};
        }}
        .stApp {{
            background-color: var(--background);
            color: var(--text);
            font-size: 1rem;
        }}
        .block-container {{
            max-width: 1560px;
            padding: 2rem 2.75rem 3.5rem;
        }}
        [data-testid="stAppViewContainer"] {{
            background: var(--background);
        }}
        [data-testid="stHeader"] {{
            background: transparent;
        }}
        [data-testid="stSidebar"] > div:first-child {{
            padding: 1.5rem 1.1rem 2rem;
        }}
        [data-testid="stVerticalBlock"] {{
            gap: 0.75rem;
        }}
        [data-testid="stHorizontalBlock"] {{
            gap: 1rem;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: var(--text) !important;
            font-weight: 700 !important;
            letter-spacing: 0;
            text-wrap: balance;
        }}
        h1 {{ font-size: 2.25rem !important; line-height: 1.12 !important; }}
        h2 {{ font-size: 1.45rem !important; line-height: 1.25 !important; }}
        h3 {{ font-size: 1.08rem !important; line-height: 1.35 !important; }}
        p, li, label {{ line-height: 1.55; }}
        [data-testid="stMarkdownContainer"] p {{ margin-bottom: 0.55rem; }}
        a {{
            color: var(--primary) !important;
        }}
        [data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"],
        [data-testid="stCaptionContainer"] {{ color: var(--text); }}
        [data-testid="stCaptionContainer"] p {{ color: var(--muted-text) !important; }}
        section[data-testid="stSidebar"] {{
            background-color: var(--sidebar);
            border-right: 1px solid var(--border);
        }}
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
            gap: 0.55rem;
        }}
        section[data-testid="stSidebar"] h2 {{
            font-size: 0.82rem !important;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--muted-text) !important;
            margin-top: 1.15rem;
            margin-bottom: 0.15rem;
        }}
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div[data-testid="stMetricValue"],
        section[data-testid="stSidebar"] div[data-testid="stMetricLabel"] {{
            color: var(--text) !important;
        }}
        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] [data-baseweb="input"] > div {{
            background-color: var(--surface) !important;
            border-color: var(--border) !important;
            color: var(--text) !important;
            min-height: 44px;
            border-radius: 8px !important;
        }}
        section[data-testid="stSidebar"] input {{
            color: var(--text) !important;
        }}
        [data-baseweb="select"] > div,
        [data-baseweb="base-input"] > div,
        [data-baseweb="input"] > div {{
            background-color: var(--surface) !important;
            border-color: var(--border) !important;
            color: var(--text) !important;
            min-height: 44px;
            border-radius: 8px !important;
        }}
        [role="listbox"], [role="option"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
        }}
        [role="option"]:hover, [aria-selected="true"][role="option"] {{
            background-color: var(--card) !important;
        }}
        button[data-baseweb="tab"] {{ color: var(--muted-text) !important; }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: var(--text) !important;
            border-bottom-color: var(--accent) !important;
        }}
        [data-testid="stTabs"] [data-baseweb="tab-list"] {{
            display: flex;
            gap: 0.25rem;
            padding: 0.35rem;
            margin: 0.8rem 0 1.25rem;
            overflow-x: auto;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            scrollbar-width: none;
        }}
        [data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {{ display: none; }}
        [data-testid="stTabs"] button[data-baseweb="tab"] {{
            min-height: 44px;
            padding: 0.5rem 0.85rem;
            border: 1px solid transparent;
            border-radius: 6px;
            white-space: nowrap;
            touch-action: manipulation;
            transition: background-color 180ms ease, color 180ms ease, border-color 180ms ease;
        }}
        [data-testid="stTabs"] button[data-baseweb="tab"]:hover {{
            background: var(--card);
            color: var(--text) !important;
        }}
        [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {{
            background: var(--card);
            border-color: var(--border);
            box-shadow: inset 0 -2px 0 var(--accent);
        }}
        .st-key-dashboard_view {{
            width: 100%;
        }}
        [data-testid="stButtonGroup"] {{
            width: 100%;
            margin: 0.8rem 0 1.25rem;
        }}
        [data-testid="stButtonGroup"] [data-baseweb="button-group"] {{
            display: grid !important;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            width: 100% !important;
            max-width: none !important;
            gap: 0.25rem;
            padding: 0.35rem;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        [data-testid="stButtonGroup"] button {{
            width: 100%;
            min-width: 0;
            min-height: 44px;
            padding: 0.5rem 0.65rem;
            border: 1px solid transparent !important;
            border-radius: 6px !important;
            background: transparent !important;
            color: var(--muted-text) !important;
            font-weight: 700;
            white-space: normal;
            overflow-wrap: anywhere;
            line-height: 1.25;
        }}
        [data-testid="stButtonGroup"] button:hover {{
            background: var(--card) !important;
            color: var(--text) !important;
        }}
        [data-testid="stButtonGroup"] button[kind="segmented_controlActive"],
        [data-testid="stButtonGroup"] button[aria-pressed="true"],
        [data-testid="stButtonGroup"] button[aria-selected="true"] {{
            background: var(--card) !important;
            color: var(--text) !important;
            border-color: var(--border) !important;
            box-shadow: inset 0 -2px 0 var(--accent);
        }}        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
            color: var(--muted-text) !important;
        }}
        .hero-band {{
            background: transparent;
            color: var(--text);
            padding: 0.7rem 0 1rem;
            border: 0;
            border-bottom: 1px solid var(--border);
            border-radius: 0;
            margin-bottom: 1.3rem;
            box-shadow: none;
        }}
        .hero-kicker, .hero-meta {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.55rem;
        }}
        .hero-kicker {{
            color: var(--muted-text);
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .sidebar-brand {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            padding: 0.2rem 0 1rem;
            border-bottom: 1px solid var(--border);
        }}
        .sidebar-brand-mark {{
            display: grid;
            place-items: center;
            width: 2.25rem;
            height: 2.25rem;
            border-radius: 7px;
            background: var(--accent);
            color: var(--background);
            font-size: 0.78rem;
            font-weight: 900;
            letter-spacing: 0.02em;
        }}
        .sidebar-brand strong {{
            display: block;
            color: var(--text);
            font-size: 0.88rem;
        }}
        .sidebar-brand span {{
            display: block;
            margin-top: 0.1rem;
            color: var(--muted-text);
            font-size: 0.75rem;
        }}
        .hero-band h1 {{
            color: var(--text) !important;
            margin: 0.45rem 0 0.35rem;
            font-size: 1.9rem !important;
            line-height: 1.2 !important;
        }}
        .hero-band p {{
            max-width: 72ch;
            margin: 0.25rem 0;
            color: var(--muted-text) !important;
        }}
        .hero-meta {{
            margin-top: 0.8rem;
            padding-top: 0.7rem;
            border-top: 1px solid var(--border);
            color: var(--muted-text);
            font-size: 0.82rem;
            gap: 0;
        }}
        .hero-meta-item {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.15rem 0.85rem;
            background: transparent;
            border: 0;
            border-left: 1px solid var(--border);
            border-radius: 0;
        }}
        .hero-meta-item:first-child {{ padding-left: 0; border-left: 0; }}
        .hero-meta-item strong {{ color: var(--text); }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.3rem 0.5rem;
            border-radius: 4px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-left: 3px solid var(--success);
            color: var(--text);
            font-size: 0.78rem;
            letter-spacing: 0;
        }}
        .status-dot {{
            width: 7px;
            height: 7px;
            flex: 0 0 7px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: none;
        }}
        .metric-card,
        .kpi-card {{
            background: var(--card);
            color: var(--text);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 6px;
            padding: 1rem 1.05rem;
            min-height: 112px;
            height: calc(100% - 14px);
            box-shadow: none;
            margin-bottom: 14px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .metric-card .label {{
            color: var(--muted-text) !important;
            font-size: 0.82rem;
            margin-bottom: 0.55rem;
            font-weight: 700;
        }}
        .metric-card .value {{
            color: var(--text) !important;
            font-size: 1.65rem;
            line-height: 1.15;
            font-weight: 800;
            overflow-wrap: anywhere;
            font-variant-numeric: tabular-nums;
        }}
        .metric-card .note {{
            color: var(--muted-text) !important;
            font-size: 0.75rem;
            margin-top: 0.55rem;
            overflow-wrap: anywhere;
        }}
        .section-note,
        .section-card {{
            color: var(--text);
            background: var(--surface);
            border: 1px solid var(--border);
            border-left: 3px solid var(--secondary);
            border-radius: 8px;
            padding: 0.8rem 0.95rem;
            margin: 0 0 1.25rem;
            font-weight: 500;
            font-size: 0.88rem;
            line-height: 1.65;
        }}
        .risk-brief {{
            background: var(--surface);
            color: var(--text);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 1.05rem 1.1rem;
            margin: 0.15rem 0 1rem;
        }}
        .risk-brief-header {{
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 1rem;
        }}
        .risk-brief-kicker {{
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        .risk-brief h3 {{
            margin: 0.2rem 0 0;
            color: var(--text) !important;
            font-size: 1.22rem !important;
        }}
        .risk-brief p {{
            margin: 0.55rem 0 0;
            color: var(--text) !important;
            line-height: 1.6;
        }}
        .priority-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 32px;
            padding: 0.25rem 0.55rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
            font-size: 0.8rem;
            font-weight: 800;
            white-space: nowrap;
        }}
        .priority-badge.critical {{
            background: var(--accent-soft);
            border-color: var(--accent);
        }}
        .priority-badge.watch {{
            background: var(--success-soft);
            border-color: var(--secondary);
        }}
        .priority-badge.normal {{
            background: var(--card);
            border-color: var(--border);
        }}
        .risk-facts {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.6rem;
            margin-top: 0.9rem;
            padding-top: 0.85rem;
            border-top: 1px solid var(--border);
        }}
        .risk-fact {{
            min-width: 0;
            padding-right: 0.6rem;
            border-right: 1px solid var(--border);
        }}
        .risk-fact:last-child {{ border-right: 0; }}
        .risk-fact-label {{
            display: block;
            color: var(--muted-text);
            font-size: 0.74rem;
            font-weight: 700;
        }}
        .risk-fact-value {{
            display: block;
            margin-top: 0.2rem;
            color: var(--text);
            font-size: 1.08rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
            overflow-wrap: anywhere;
        }}
        .risk-disclaimer {{
            color: var(--muted-text) !important;
            font-size: 0.78rem;
        }}
        .section-header {{
            display: flex;
            align-items: end;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.25rem 0 0.15rem;
        }}
        .section-header h2 {{ margin: 0.15rem 0 0; }}
        .section-kicker {{
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }}
        .section-context {{
            color: var(--muted-text);
            font-size: 0.78rem;
            text-align: right;
        }}
        .metric-row-spacer {{
            height: 4px;
        }}
        .help-text {{
            color: var(--muted-text) !important;
            font-size: 0.95rem;
            line-height: 1.65;
        }}
        .warning-text {{
            color: var(--warning) !important;
            font-weight: 800;
        }}
        .danger-text {{
            color: var(--danger) !important;
            font-weight: 800;
        }}
        .success-text {{
            color: var(--success) !important;
            font-weight: 800;
        }}
        div[data-testid="stInfo"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border-left: 4px solid var(--secondary);
        }}
        div[data-testid="stWarning"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border-left: 4px solid var(--warning);
        }}
        .stAlert {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }}
        div[data-testid="stMetricValue"] {{
            color: var(--text) !important;
            font-weight: 800 !important;
        }}
        div[data-testid="stMetricLabel"] {{
            color: var(--muted-text) !important;
            font-weight: 700 !important;
        }}
        div[data-testid="stMetricDelta"] {{
            color: var(--accent) !important;
        }}
        [data-testid="stPlotlyChart"] {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.25rem;
            overflow: hidden;
        }}
        .watch-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.55rem 0 1rem;
        }}
        .watch-card {{
            min-width: 0;
            padding: 0.9rem 0.95rem;
            border: 1px solid var(--border);
            border-top: 2px solid var(--warning);
            border-radius: 8px;
            background: var(--card);
        }}
        .watch-card.critical {{ border-top-color: var(--danger); }}
        .watch-card-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
            color: var(--text);
            font-size: 0.9rem;
            font-weight: 800;
        }}
        .watch-level {{
            flex: 0 0 auto;
            padding: 0.2rem 0.42rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--accent);
            background: var(--surface);
            font-size: 0.74rem;
        }}
        .watch-card-main {{ display: flex; align-items: baseline; gap: 0.55rem; margin-top: 0.75rem; }}
        .watch-card-main strong {{ color: var(--text); font-size: 1.65rem; line-height: 1; }}
        .watch-card-main span, .watch-card p, .watch-bounds {{ color: var(--muted-text); }}
        .watch-card-main span {{ font-size: 0.76rem; }}
        .watch-card p {{ margin: 0.65rem 0; font-size: 0.82rem; line-height: 1.5; }}
        .watch-bounds {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; font-size: 0.76rem; }}
        .watch-bounds strong {{ color: var(--text); font-variant-numeric: tabular-nums; }}        .map-selection-note {{
            margin: 0.4rem 0 0.9rem;
            color: var(--muted-text) !important;
            font-size: 0.82rem;
            line-height: 1.55;
        }}
        button {{
            border-radius: 8px !important;
            touch-action: manipulation;
            transition: background-color 180ms ease, border-color 180ms ease, color 180ms ease;
        }}
        [data-testid="stBaseButton-headerNoPadding"],
        [data-testid="stExpandSidebarButton"] {{
            min-width: 44px !important;
            min-height: 44px !important;
        }}
        button:not(:disabled),
        [role="button"]:not([aria-disabled="true"]) {{
            cursor: pointer;
        }}
        button:focus-visible,
        [role="button"]:focus-visible,
        a:focus-visible,
        input:focus-visible,
        [data-baseweb="select"]:focus-within,
        [data-baseweb="base-input"]:focus-within {{
            outline: 3px solid var(--accent) !important;
            outline-offset: 2px !important;
        }}
        button:disabled,
        input:disabled,
        [aria-disabled="true"] {{
            cursor: not-allowed !important;
            opacity: 0.55;
        }}
        .table-shell {{
            overflow-x: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--card);
            margin: 8px 0 18px;
            scrollbar-color: var(--border) var(--surface);
        }}
        .table-shell:focus-visible {{
            outline: 3px solid var(--accent);
            outline-offset: 2px;
        }}
        .dashboard-table {{
            width: 100%;
            border-collapse: collapse;
            color: var(--text);
            font-size: 0.84rem;
            font-variant-numeric: tabular-nums;
        }}
        .dashboard-table th {{
            background: var(--table-header);
            color: var(--text);
            text-align: left;
            padding: 0.72rem 0.78rem;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
            font-weight: 800;
        }}
        .dashboard-table td {{
            background: var(--card);
            color: var(--text);
            padding: 0.68rem 0.78rem;
            border-bottom: 1px solid var(--border);
            white-space: normal;
            overflow-wrap: anywhere;
        }}
        .dashboard-table tr:last-child td {{ border-bottom: 0; }}
        .dashboard-table tbody tr td {{
            transition: background-color 160ms ease;
        }}
        .dashboard-table tbody tr:hover td {{ background: var(--surface); }}
        .anomaly-case-table th:nth-child(1), .anomaly-case-table td:nth-child(1) {{ min-width: 4.8rem; }}
        .anomaly-case-table th:nth-child(2), .anomaly-case-table td:nth-child(2) {{
            min-width: 2.8rem;
            white-space: nowrap;
        }}
        .confidence-watch-table th:nth-child(6), .confidence-watch-table td:nth-child(6) {{
            min-width: 6.5rem;
            white-space: nowrap;
            font-weight: 800;
            color: var(--accent);
        }}
        .anomaly-case-table th:nth-child(3), .anomaly-case-table td:nth-child(3),
        .anomaly-case-table th:nth-child(4), .anomaly-case-table td:nth-child(4) {{
            min-width: 3.4rem;
            white-space: nowrap;
        }}
        .sidebar-summary {{ margin: 0; }}
        .sidebar-summary div {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 7px 0;
            border-bottom: 1px solid var(--border);
        }}
        .sidebar-summary dt {{ color: var(--muted-text); }}
        .sidebar-summary dd {{ color: var(--text); margin: 0; font-weight: 700; text-align: right; }}
        .dashboard-footer {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-top: 2.5rem;
            padding-top: 0.9rem;
            border-top: 1px solid var(--border);
            color: var(--muted-text);
            font-size: 0.75rem;
        }}
        .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select {{
            font-family: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif;
        }}
        .block-container {{
            max-width: 1480px;
            padding-top: 1.6rem;
        }}
        [data-testid="stVerticalBlock"] {{ gap: 1rem; }}
        .hero-band {{
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            align-items: start;
            row-gap: 0.75rem;
            padding: 1rem 0 1.25rem;
            margin-bottom: 1.6rem;
        }}
        .hero-band h1 {{
            font-size: 2.15rem !important;
            letter-spacing: 0 !important;
        }}
        .hero-copy {{ min-width: 0; }}
        .hero-band p {{ max-width: 64ch; }}
        .hero-meta {{
            align-self: start;
            margin: 0;
            padding: 0;
            border-top: 0;
            justify-content: start;
            flex-wrap: wrap;
        }}
        .hero-meta-item {{
            min-height: 2.15rem;
            padding: 0.25rem 0.75rem;
        }}
        .dashboard-intro {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0 0 1.15rem;
            padding: 0.7rem 0.85rem;
            color: var(--muted-text);
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            font-size: 0.86rem;
            line-height: 1.55;
        }}
        .dashboard-intro strong {{ color: var(--text); }}
        .signal-deck {{
            display: grid;
            grid-template-columns: minmax(230px, 1.25fr) repeat(3, minmax(150px, 1fr));
            gap: 0.75rem;
            margin: 0.45rem 0 1.85rem;
        }}
        .signal-primary, .signal-card {{
            min-width: 0;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--card);
        }}
        .signal-primary {{
            grid-row: span 2;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 1.15rem 1.2rem 1.05rem;
            border-left: 4px solid var(--accent);
        }}
        .signal-label {{
            color: var(--muted-text);
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.05em;
        }}
        .signal-value {{
            display: block;
            margin-top: 0.55rem;
            color: var(--text);
            font-size: 2.8rem;
            font-weight: 800;
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }}
        .signal-context {{
            margin-top: 0.55rem;
            color: var(--muted-text);
            font-size: 0.84rem;
            line-height: 1.45;
        }}
        .signal-level {{
            display: inline-flex;
            width: fit-content;
            margin-top: 1.05rem;
            padding: 0.28rem 0.5rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            background: var(--surface);
            color: var(--text);
            font-size: 0.82rem;
            font-weight: 800;
        }}
        .signal-card {{
            display: flex;
            min-height: 106px;
            flex-direction: column;
            justify-content: space-between;
            padding: 0.9rem 0.95rem;
            transition: border-color 180ms ease, background-color 180ms ease;
        }}
        .signal-card:hover {{
            background: var(--surface);
            border-color: var(--secondary);
        }}
        .signal-card .signal-value {{
            margin: 0.35rem 0 0;
            font-size: 1.5rem;
            line-height: 1.15;
        }}
        .signal-card .signal-context {{
            margin-top: 0.4rem;
            font-size: 0.75rem;
        }}
        .signal-card.accent {{ border-top: 2px solid var(--accent); }}
        .signal-card.alert {{ border-top: 2px solid var(--danger); }}
        .signal-card.calm {{ border-top: 2px solid var(--secondary); }}
        .guidance-panel {{
            margin: 0 0 1.85rem;
            padding: 1.05rem 1.15rem;
            border: 1px solid var(--border);
            border-left: 4px solid var(--secondary);
            border-radius: 8px;
            background: var(--surface);
            color: var(--text);
        }}
        .guidance-heading {{
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 1rem;
        }}
        .guidance-kicker {{
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.06em;
        }}
        .guidance-heading h2 {{
            margin: 0.22rem 0 0;
            color: var(--text) !important;
            font-size: 1.2rem !important;
        }}
        .guidance-time {{
            display: grid;
            gap: 0.15rem;
            color: var(--muted-text);
            font-size: 0.74rem;
            text-align: right;
        }}
        .guidance-time strong {{ color: var(--text); font-size: 0.86rem; }}
        .guidance-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 0.9rem;
        }}
        .guidance-grid > div {{
            min-width: 0;
            padding: 0.8rem 0.85rem;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--card);
        }}
        .guidance-grid span {{ color: var(--accent); font-size: 0.76rem; font-weight: 800; }}
        .guidance-grid p {{ margin: 0.3rem 0 0; color: var(--text) !important; line-height: 1.55; }}
        .guidance-disclaimer {{
            margin: 0.75rem 0 0;
            color: var(--muted-text) !important;
            font-size: 0.76rem;
            line-height: 1.5;
        }}
        .guidance-disclaimer a {{ color: var(--accent) !important; font-weight: 800; }}
        .comparison-recommendation {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.25rem 0 1rem;
            padding: 0.95rem 1rem;
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            background: var(--surface);
            color: var(--text);
        }}
        .comparison-recommendation span {{ color: var(--muted-text); font-size: 0.78rem; font-weight: 700; }}
        .comparison-recommendation strong {{ display: block; margin-top: 0.18rem; color: var(--text); font-size: 1.12rem; }}
        .comparison-recommendation-value {{ color: var(--accent); font-size: 1rem; font-weight: 800; white-space: nowrap; }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.75rem 0 1.2rem;
        }}
        .comparison-card {{
            min-width: 0;
            padding: 0.95rem 1rem;
            border: 1px solid var(--border);
            border-top: 3px solid var(--secondary);
            border-radius: 8px;
            background: var(--card);
            color: var(--text);
        }}
        .comparison-card.stale {{ border-top-color: var(--warning); }}
        .comparison-card.anomaly {{ border-top-color: var(--danger); }}
        .comparison-card-head {{ display: flex; align-items: start; justify-content: space-between; gap: 0.6rem; }}
        .comparison-card-head strong {{ color: var(--text); font-size: 1rem; overflow-wrap: anywhere; }}
        .comparison-card-head span {{ color: var(--muted-text); font-size: 0.74rem; }}
        .comparison-state {{
            flex: 0 0 auto;
            padding: 0.2rem 0.4rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            background: var(--surface);
            color: var(--text) !important;
            font-weight: 800;
        }}
        .comparison-aqi {{ display: flex; align-items: end; gap: 0.55rem; margin-top: 0.85rem; }}
        .comparison-aqi strong {{ color: var(--text); font-size: 2rem; line-height: 1; font-variant-numeric: tabular-nums; }}
        .comparison-aqi span {{ color: var(--accent); font-size: 0.78rem; font-weight: 800; }}
        .comparison-facts {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.55rem; margin-top: 0.85rem; }}
        .comparison-fact {{ padding-top: 0.55rem; border-top: 1px solid var(--border); min-width: 0; }}
        .comparison-fact span {{ display: block; color: var(--muted-text); font-size: 0.7rem; }}
        .comparison-fact strong {{ display: block; margin-top: 0.16rem; color: var(--text); font-size: 0.88rem; overflow-wrap: anywhere; }}
        .comparison-time {{ margin: 0.75rem 0 0; color: var(--muted-text) !important; font-size: 0.72rem; }}
        .priority-queue {{
            display: grid;
            gap: 0.55rem;
            margin-top: 0.55rem;
        }}
        .priority-row {{
            display: grid;
            grid-template-columns: 1.85rem minmax(0, 1fr) auto;
            align-items: start;
            gap: 0.65rem;
            padding: 0.76rem 0;
            border-bottom: 1px solid var(--border);
        }}
        .priority-row:first-child {{ padding-top: 0.25rem; }}
        .priority-row:last-child {{ border-bottom: 0; }}
        .priority-rank {{
            display: grid;
            place-items: center;
            width: 1.85rem;
            height: 1.85rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--accent);
            background: var(--surface);
            font-size: 0.78rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
        }}
        .priority-place {{
            min-width: 0;
            color: var(--text);
            font-size: 0.95rem;
            font-weight: 800;
            line-height: 1.35;
        }}
        .priority-evidence {{
            display: block;
            margin-top: 0.22rem;
            color: var(--muted-text);
            font-size: 0.77rem;
            line-height: 1.45;
        }}
        .priority-aqi {{
            color: var(--text);
            font-size: 1rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
            text-align: right;
            white-space: nowrap;
        }}
        .priority-aqi span {{
            display: block;
            margin-top: 0.12rem;
            color: var(--muted-text);
            font-size: 0.68rem;
            font-weight: 700;
        }}
        .queue-empty {{
            margin: 0.75rem 0 0;
            color: var(--muted-text);
            font-size: 0.88rem;
        }}
        .watch-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.55rem 0 1rem;
        }}
        .watch-card {{
            min-width: 0;
            padding: 0.9rem 0.95rem;
            border: 1px solid var(--border);
            border-top: 2px solid var(--warning);
            border-radius: 8px;
            background: var(--card);
        }}
        .watch-card.critical {{ border-top-color: var(--danger); }}
        .watch-card-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
            color: var(--text);
            font-size: 0.9rem;
            font-weight: 800;
        }}
        .watch-level {{
            flex: 0 0 auto;
            padding: 0.2rem 0.42rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--accent);
            background: var(--surface);
            font-size: 0.74rem;
        }}
        .watch-card-main {{ display: flex; align-items: baseline; gap: 0.55rem; margin-top: 0.75rem; }}
        .watch-card-main strong {{ color: var(--text); font-size: 1.65rem; line-height: 1; }}
        .watch-card-main span, .watch-card p, .watch-bounds {{ color: var(--muted-text); }}
        .watch-card-main span {{ font-size: 0.76rem; }}
        .watch-card p {{ margin: 0.65rem 0; font-size: 0.82rem; line-height: 1.5; }}
        .watch-bounds {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; font-size: 0.76rem; }}
        .watch-bounds strong {{ color: var(--text); font-variant-numeric: tabular-nums; }}        .map-selection-note {{
            display: flex;
            align-items: center;
            min-height: 2rem;
            margin: 0.2rem 0 0;
            padding: 0.25rem 0;
            border-top: 1px solid var(--border);
        }}
        .section-divider {{
            height: 1px;
            margin: 1.8rem 0;
            background: var(--border);
        }}
        [data-testid="stPlotlyChart"] {{
            border-radius: 8px;
            padding: 0.45rem;
        }}
        .table-shell {{
            margin: 0.5rem 0 1.15rem;
            border-radius: 6px;
        }}
        .dashboard-table th {{
            position: sticky;
            top: 0;
            z-index: 1;
            padding: 0.68rem 0.72rem;
            font-size: 0.78rem;
        }}
        .dashboard-table td {{
            padding: 0.7rem 0.72rem;
            vertical-align: top;
        }}
        @media (max-width: 900px) {{
            .block-container {{ padding: 1.5rem 1.35rem 3rem; }}
            h1 {{ font-size: 2rem !important; }}
            .section-header {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
            .section-context {{ text-align: left; }}
            .hero-band {{ grid-template-columns: 1fr; gap: 0.9rem; }}
            .hero-meta {{ justify-content: start; }}
            .signal-deck {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .comparison-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .signal-primary {{ grid-row: auto; grid-column: span 2; }}
        }}
        @media (max-width: 640px) {{
            .block-container {{ padding: 3.75rem 0.9rem 2.5rem; }}
            h1 {{ font-size: 1.75rem !important; }}
            h2 {{ font-size: 1.25rem !important; }}
            .hero-band {{ padding: 0.55rem 0 0.9rem; margin-bottom: 1rem; }}
            .hero-band h1 {{ font-size: 1.65rem !important; }}
            .hero-band p {{ font-size: 1rem; }}
            .hero-kicker, .status-pill {{ font-size: 0.84rem; }}
            .hero-meta {{ align-items: stretch; flex-direction: column; }}
            .hero-meta-item, .status-pill {{
                width: 100%;
                box-sizing: border-box;
                font-size: 0.9rem;
            }}
            .hero-meta-item {{ border-left: 0; padding-left: 0; }}
            .hero-kicker .status-pill {{ width: fit-content; }}
            .metric-card {{ min-height: 98px; padding: 0.9rem; }}
            .metric-card .value {{ font-size: 1.5rem; }}
            .metric-card .label {{ font-size: 0.9rem; }}
            .metric-card .note {{ font-size: 0.82rem; }}
            .section-note, .section-card {{ font-size: 0.95rem; }}
            .risk-brief {{ padding: 0.95rem; }}
            .risk-brief-header {{ flex-direction: column; gap: 0.55rem; }}
            .risk-facts {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem 0.55rem; }}
            .risk-fact:nth-child(2) {{ border-right: 0; }}
            .risk-fact:nth-child(-n+2) {{ padding-bottom: 0.7rem; border-bottom: 1px solid var(--border); }}
            section[data-testid="stSidebar"] [data-baseweb="select"],
            section[data-testid="stSidebar"] input {{
                font-size: 1rem !important;
            }}
            .table-shell {{ margin-left: -0.1rem; margin-right: -0.1rem; }}
            .dashboard-table {{ font-size: 0.84rem; }}
            .dashboard-table th, .dashboard-table td {{ padding: 0.58rem 0.55rem; }}
            .dashboard-footer {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
            .dashboard-intro {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
            [data-testid="stButtonGroup"] [data-baseweb="button-group"] {{
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.25rem;
                padding: 0.25rem;
            }}
            [data-testid="stButtonGroup"] button {{
                min-height: 44px;
                padding: 0.4rem 0.25rem;
                font-size: 0.8rem;
            }}            [data-testid="stTabs"] [data-baseweb="tab-list"] {{
                flex-wrap: wrap;
                gap: 0.2rem;
                overflow-x: visible;
                padding: 0.25rem;
            }}
            [data-testid="stTabs"] button[data-baseweb="tab"] {{
                flex: 1 1 calc(33.333% - 0.2rem);
                min-width: 0;
                min-height: 44px;
                padding: 0.4rem 0.3rem;
                font-size: 0.75rem;
                justify-content: center;
            }}
            .signal-deck {{ grid-template-columns: 1fr; gap: 0.65rem; }}
            .signal-primary {{ grid-column: auto; padding: 1rem; }}
            .signal-value {{ font-size: 2.45rem; }}
            .signal-card {{ min-height: 94px; }}
            .guidance-heading {{ display: grid; }}
            .guidance-time {{ text-align: left; }}
            .guidance-grid {{ grid-template-columns: 1fr; }}
            .comparison-recommendation {{ align-items: start; flex-direction: column; }}
            .comparison-grid {{ grid-template-columns: 1fr; }}
            .priority-row {{ grid-template-columns: 1.75rem minmax(0, 1fr) auto; gap: 0.5rem; }}
            .priority-rank {{ width: 1.75rem; height: 1.75rem; }}
            .watch-grid {{ grid-template-columns: 1fr; }}
            .watch-card {{ padding: 0.85rem; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                scroll-behavior: auto !important;
                transition-duration: 0.01ms !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

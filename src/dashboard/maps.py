from __future__ import annotations

import pandas as pd

from src.app_helpers import get_station_coordinates

try:
    import plotly.graph_objects as go  # type: ignore
except Exception:  # pragma: no cover
    go = None

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None


def _station_map_data(brief: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in brief.iterrows():
        coordinates = get_station_coordinates(row.get("site_name_display"), row.get("county_display"))
        if coordinates is None:
            continue
        latitude, longitude = coordinates
        rows.append(
            {
                "site_name_display": str(row.get("site_name_display", "未知測站")),
                "county_display": str(row.get("county_display", "未知地區")),
                "latitude": latitude,
                "longitude": longitude,
                "latest_aqi": row.get("latest_aqi"),
                "latest_pm25": row.get("latest_pm25"),
                "attention_level": str(row.get("attention_level", "一般監測")),
                "evidence_summary": str(row.get("evidence_summary", "")),
            }
        )
    return pd.DataFrame(rows)


def _build_station_map(brief: pd.DataFrame, theme: dict[str, str]):
    if go is None:
        return None
    map_data = _station_map_data(brief)
    if map_data.empty:
        return None
    color_map = {
        "優先檢視": theme["danger"],
        "持續觀察": theme["accent"],
        "一般監測": theme["secondary"],
    }
    marker_sizes = [max(15, min(34, 13 + float(aqi) / 7)) for aqi in map_data["latest_aqi"]]
    # This simplified outline provides an offline spatial frame, not county boundaries.
    taiwan_outline = [
        (121.95, 25.30), (121.72, 25.25), (121.47, 25.17), (121.21, 24.98),
        (120.98, 24.73), (120.76, 24.38), (120.54, 23.95), (120.31, 23.50),
        (120.17, 23.08), (120.31, 22.70), (120.61, 22.26), (120.84, 21.90),
        (121.04, 22.06), (121.12, 22.43), (121.24, 22.83), (121.41, 23.22),
        (121.54, 23.62), (121.64, 24.00), (121.73, 24.36), (121.84, 24.71),
        (122.01, 25.02), (121.95, 25.30),
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[longitude for longitude, _ in taiwan_outline],
            y=[latitude for _, latitude in taiwan_outline],
            mode="lines",
            fill="toself",
            fillcolor=theme["background"],
            line={"color": theme["border"], "width": 1.5},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=map_data["longitude"],
            y=map_data["latitude"],
            customdata=map_data[["site_name_display", "county_display", "latest_aqi", "latest_pm25", "attention_level"]],
            mode="markers",
            marker={
                "size": marker_sizes,
                "color": [color_map.get(level, theme["secondary"]) for level in map_data["attention_level"]],
                "symbol": [
                    "diamond" if level == "優先檢視" else "square" if level == "持續觀察" else "circle"
                    for level in map_data["attention_level"]
                ],
                "line": {"color": theme["text"], "width": 1},
                "opacity": 0.94,
            },
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "目前 AQI: %{customdata[2]:.1f}<br>"
                "PM2.5: %{customdata[3]:.1f}<br>"
                "關注程度: %{customdata[4]}<br>"
                "點選此站即可套用篩選<extra></extra>"
            ),
            showlegend=False,
        )
    )
    figure.update_layout(
        paper_bgcolor=theme["card"],
        plot_bgcolor=theme["card"],
        font={"color": theme["text"]},
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        height=430,
        showlegend=False,
        clickmode="event+select",
        dragmode=False,
    )
    figure.update_xaxes(
        range=[119.75, 122.25],
        visible=False,
        fixedrange=True,
        showgrid=False,
        zeroline=False,
    )
    figure.update_yaxes(
        range=[21.65, 25.55],
        visible=False,
        fixedrange=True,
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    return figure


def _render_station_map(brief: pd.DataFrame, theme: dict[str, str], selected_site_display: str) -> None:
    figure = _build_station_map(brief, theme)
    if figure is None:
        st.info("目前資料沒有可對照座標的測站，因此無法顯示地圖。")
        return
    event = st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        key="station_map_selector",
        on_select="rerun",
        selection_mode="points",
        config={"displaylogo": False, "scrollZoom": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )
    selected_points = getattr(getattr(event, "selection", None), "points", []) if event is not None else []
    if not selected_points:
        return
    map_site = selected_points[0].get("customdata", [None])[0]
    if map_site and map_site != selected_site_display:
        st.session_state["pending_station_filter"] = str(map_site)
        st.rerun()

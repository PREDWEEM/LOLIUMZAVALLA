from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app_umbral_operativo as operational


LOW_EMERGENCE_MAX_PCT = 1.0
LOW_EMERGENCE_MAX = 0.01

_ORIGINAL_LOW_EMERGENCE_FIGURE = operational._low_emergence_figure
_ORIGINAL_PLOTLY_WITH_LOW_PANEL = operational._plotly_chart_with_low_panel
_ORIGINAL_TOGGLE = st.toggle


def _low_emergence_figure_1pct(
    data: Any,
    smooth: Any,
    x_range: Any,
    site_name: str,
    model_name: str,
    today: Any,
) -> go.Figure:
    """Limita el detalle a 0–1 % y destaca valores entre 0,001 y 0,01."""
    figure = _ORIGINAL_LOW_EMERGENCE_FIGURE(
        data,
        smooth,
        x_range,
        site_name,
        model_name,
        today,
    )

    daily = data.loc[:, ["Fecha", "EMERREL"]].copy()
    daily["Fecha"] = pd.to_datetime(daily["Fecha"], errors="coerce")
    daily["EMERREL"] = pd.to_numeric(daily["EMERREL"], errors="coerce")
    daily = daily.dropna(subset=["Fecha", "EMERREL"])
    highlighted = daily.loc[
        (daily["EMERREL"] >= operational.EMERGENCE_THRESHOLD)
        & (daily["EMERREL"] <= LOW_EMERGENCE_MAX)
    ].copy()
    highlighted["EMERREL_PCT"] = highlighted["EMERREL"] * 100.0

    if not highlighted.empty:
        # Se agrega al final para que los marcadores queden por encima de barras,
        # tendencias y áreas sombreadas del panel base.
        figure.add_trace(
            go.Scatter(
                x=highlighted["Fecha"],
                y=highlighted["EMERREL_PCT"],
                customdata=highlighted["EMERREL"],
                mode="markers",
                name="Valores EMERREL ≥ 0,001 y ≤ 0,01",
                marker={
                    "symbol": "circle",
                    "size": 11,
                    "color": "rgba(255,255,255,0.98)",
                    "line": {"color": "#dc2626", "width": 2.4},
                    "opacity": 1.0,
                },
                hovertemplate=(
                    "<b>Valor sobre el umbral operativo</b><br>"
                    "Fecha: %{x|%d-%m-%Y}<br>"
                    "Intensidad relativa: %{y:.3f}%<br>"
                    "EMERREL: %{customdata:.4f}<extra></extra>"
                ),
                showlegend=False,
                cliponaxis=False,
            )
        )

    title_text = str(figure.layout.title.text or "").replace(
        "EMERREL 0–0,02",
        "EMERREL 0–0,01",
    )
    figure.update_layout(title={"text": title_text})
    figure.update_yaxes(
        range=[0.0, LOW_EMERGENCE_MAX_PCT],
        tickmode="array",
        tickvals=[0.0, 0.1, 0.25, 0.5, 0.75, 1.0],
        ticktext=["0", "0,1", "0,25", "0,5", "0,75", "1"],
    )
    return figure


def _plotly_chart_with_1pct_caption(*args: Any, **kwargs: Any):
    """Actualiza el texto del panel 0–1 % durante su renderizado."""
    original_caption = st.caption

    def caption_1pct(body: Any, *caption_args: Any, **caption_kwargs: Any):
        if isinstance(body, str):
            body = body.replace(
                "Ampliación de EMERREL 0–0,02 (0–2 %).",
                (
                    "Ampliación de EMERREL 0–0,01 (0–1 %). "
                    "Los círculos con borde rojo identifican únicamente valores "
                    "con EMERREL ≥ 0,001 y ≤ 0,01 y se muestran por encima de "
                    "las áreas sombreadas."
                ),
            )
        return original_caption(body, *caption_args, **caption_kwargs)

    st.caption = caption_1pct
    try:
        return _ORIGINAL_PLOTLY_WITH_LOW_PANEL(*args, **kwargs)
    finally:
        st.caption = original_caption


def _toggle_1pct(*args: Any, **kwargs: Any):
    """Actualiza la ayuda del control del panel ampliado."""
    help_text = kwargs.get("help")
    if isinstance(help_text, str):
        help_text = help_text.replace("0 a 2 %", "0 a 1 %")
        help_text = help_text.replace("inferiores a 0,02", "hasta 0,01")
        kwargs["help"] = help_text
    return _ORIGINAL_TOGGLE(*args, **kwargs)


def run() -> None:
    """Ejecuta PREDWEEM con detalle 0–1 % y puntos sobre el umbral."""
    original_max_pct = operational.LOW_EMERGENCE_MAX_PCT
    original_low_figure = operational._low_emergence_figure
    original_plotly = operational._plotly_chart_with_low_panel
    original_toggle = st.toggle

    operational.LOW_EMERGENCE_MAX_PCT = LOW_EMERGENCE_MAX_PCT
    operational._low_emergence_figure = _low_emergence_figure_1pct
    operational._plotly_chart_with_low_panel = _plotly_chart_with_1pct_caption
    st.toggle = _toggle_1pct

    try:
        operational.run()
    finally:
        operational.LOW_EMERGENCE_MAX_PCT = original_max_pct
        operational._low_emergence_figure = original_low_figure
        operational._plotly_chart_with_low_panel = original_plotly
        st.toggle = original_toggle

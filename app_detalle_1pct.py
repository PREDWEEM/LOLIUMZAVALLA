from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app_umbral_operativo as operational


LOW_EMERGENCE_MAX_PCT = 5.0
LOW_EMERGENCE_MAX = 0.05
MAX_DIAS_SIN_FLUJO = 3
CAMPAIGN_EPSILON = 1e-12

_ORIGINAL_LOW_EMERGENCE_FIGURE = operational._low_emergence_figure
_ORIGINAL_PLOTLY_WITH_LOW_PANEL = operational._plotly_chart_with_low_panel
_ORIGINAL_TOGGLE = st.toggle


def _canonical_daily(data: Any) -> pd.DataFrame:
    """Normaliza la serie diaria y conserva el máximo EMERREL por fecha."""
    daily = data.loc[:, ["Fecha", "EMERREL"]].copy()
    daily["Fecha"] = pd.to_datetime(
        daily["Fecha"], errors="coerce"
    ).dt.normalize()
    daily["EMERREL"] = pd.to_numeric(
        daily["EMERREL"], errors="coerce"
    )
    daily = daily.dropna(subset=["Fecha", "EMERREL"])
    if daily.empty:
        return daily
    return (
        daily.groupby("Fecha", as_index=False, sort=True)["EMERREL"]
        .max()
        .reset_index(drop=True)
    )


def _isolated_operational_dates(daily: pd.DataFrame) -> set[pd.Timestamp]:
    """Devuelve fechas pertenecientes a grupos con un solo flujo operativo.

    Se replica el criterio temporal de agrupación de las campañas: dos flujos
    pertenecen al mismo grupo cuando entre ellos existen como máximo tres días
    sin una señal superior al umbral operativo.
    """
    active = daily.loc[
        daily["EMERREL"] > operational.EMERGENCE_THRESHOLD,
        ["Fecha"],
    ].copy()
    if active.empty:
        return set()

    active = active.sort_values("Fecha").reset_index(drop=True)
    maximum_date_gap = MAX_DIAS_SIN_FLUJO + 1
    starts_new_group = (
        active["Fecha"].diff().dt.days.fillna(maximum_date_gap + 1)
        > maximum_date_gap
    )
    active["Grupo"] = starts_new_group.cumsum()
    group_sizes = active.groupby("Grupo")["Fecha"].transform("size")

    return set(active.loc[group_sizes == 1, "Fecha"].tolist())


def _campaign_values_at_dates(
    smooth: Any,
    dates: pd.Series,
) -> np.ndarray:
    """Interpola la envolvente pintada en las fechas de los candidatos."""
    trend = smooth.loc[:, ["Fecha", "EMERREL_CAMPANA"]].copy()
    trend["Fecha"] = pd.to_datetime(
        trend["Fecha"], errors="coerce"
    )
    trend["EMERREL_CAMPANA"] = pd.to_numeric(
        trend["EMERREL_CAMPANA"], errors="coerce"
    )
    trend = (
        trend.dropna(subset=["Fecha", "EMERREL_CAMPANA"])
        .sort_values("Fecha")
        .drop_duplicates(subset=["Fecha"], keep="last")
    )
    if trend.empty or dates.empty:
        return np.zeros(len(dates), dtype=float)

    trend_x = trend["Fecha"].astype("int64").to_numpy(dtype=np.int64)
    trend_y = trend["EMERREL_CAMPANA"].to_numpy(dtype=float)
    candidate_x = pd.to_datetime(dates).astype("int64").to_numpy(dtype=np.int64)

    return np.interp(
        candidate_x.astype(float),
        trend_x.astype(float),
        trend_y,
        left=0.0,
        right=0.0,
    )


def _low_emergence_figure_5pct(
    data: Any,
    smooth: Any,
    x_range: Any,
    site_name: str,
    model_name: str,
    today: Any,
) -> go.Figure:
    """Amplía 0–5 % y destaca solo flujos aislados fuera de campañas."""
    figure = _ORIGINAL_LOW_EMERGENCE_FIGURE(
        data,
        smooth,
        x_range,
        site_name,
        model_name,
        today,
    )

    daily = _canonical_daily(data)
    isolated_dates = _isolated_operational_dates(daily)

    highlighted = daily.loc[
        (daily["EMERREL"] > operational.EMERGENCE_THRESHOLD)
        & (daily["EMERREL"] <= LOW_EMERGENCE_MAX)
        & (daily["Fecha"].isin(isolated_dates))
    ].copy()

    if not highlighted.empty:
        highlighted["EMERREL_CAMPANA"] = _campaign_values_at_dates(
            smooth,
            highlighted["Fecha"],
        )
        highlighted = highlighted.loc[
            highlighted["EMERREL_CAMPANA"] <= CAMPAIGN_EPSILON
        ].copy()

    highlighted["EMERREL_PCT"] = highlighted["EMERREL"] * 100.0

    if not highlighted.empty:
        # La traza se agrega al final para que los círculos queden por encima de
        # barras y líneas. No se agregan marcadores donde exista área pintada.
        figure.add_trace(
            go.Scatter(
                x=highlighted["Fecha"],
                y=highlighted["EMERREL_PCT"],
                customdata=highlighted["EMERREL"],
                mode="markers",
                name="Flujos aislados fuera de campañas",
                marker={
                    "symbol": "circle",
                    "size": 11,
                    "color": "rgba(255,255,255,0.98)",
                    "line": {"color": "#dc2626", "width": 2.4},
                    "opacity": 1.0,
                },
                hovertemplate=(
                    "<b>Flujo aislado fuera de campaña</b><br>"
                    "Fecha: %{x|%d-%m-%Y}<br>"
                    "Intensidad relativa: %{y:.3f}%<br>"
                    "EMERREL: %{customdata:.4f}<extra></extra>"
                ),
                showlegend=False,
                cliponaxis=False,
            )
        )

    title_text = str(figure.layout.title.text or "")
    for previous in ("EMERREL 0–0,01", "EMERREL 0–0,02"):
        title_text = title_text.replace(previous, "EMERREL 0–0,05")
    figure.update_layout(title={"text": title_text})
    figure.update_yaxes(
        range=[0.0, LOW_EMERGENCE_MAX_PCT],
        tickmode="array",
        tickvals=[0.0, 0.1, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0],
        ticktext=["0", "0,1", "0,5", "1", "2", "3", "4", "5"],
    )
    return figure


def _plotly_chart_with_5pct_caption(*args: Any, **kwargs: Any):
    """Actualiza el texto del panel 0–5 % durante su renderizado."""
    original_caption = st.caption

    def caption_5pct(body: Any, *caption_args: Any, **caption_kwargs: Any):
        if isinstance(body, str):
            for previous in (
                "Ampliación de EMERREL 0–0,02 (0–2 %).",
                "Ampliación de EMERREL 0–0,01 (0–1 %).",
            ):
                body = body.replace(
                    previous,
                    (
                        "Ampliación de EMERREL 0–0,05 (0–5 %). "
                        "Los círculos con borde rojo identifican solamente flujos "
                        "aislados con EMERREL > 0,001 y ≤ 0,05. No se marcan puntos "
                        "agrupados con otros flujos ni ubicados bajo las campañas "
                        "pintadas."
                    ),
                )
        return original_caption(body, *caption_args, **caption_kwargs)

    st.caption = caption_5pct
    try:
        return _ORIGINAL_PLOTLY_WITH_LOW_PANEL(*args, **kwargs)
    finally:
        st.caption = original_caption


def _toggle_5pct(*args: Any, **kwargs: Any):
    """Actualiza la ayuda del control del panel ampliado."""
    help_text = kwargs.get("help")
    if isinstance(help_text, str):
        help_text = help_text.replace("0 a 2 %", "0 a 5 %")
        help_text = help_text.replace("0 a 1 %", "0 a 5 %")
        help_text = help_text.replace("inferiores a 0,02", "hasta 0,05")
        help_text = help_text.replace("hasta 0,01", "hasta 0,05")
        kwargs["help"] = help_text
    return _ORIGINAL_TOGGLE(*args, **kwargs)


def run() -> None:
    """Ejecuta PREDWEEM con detalle 0–5 % y flujos aislados."""
    original_max_pct = operational.LOW_EMERGENCE_MAX_PCT
    original_low_figure = operational._low_emergence_figure
    original_plotly = operational._plotly_chart_with_low_panel
    original_toggle = st.toggle

    operational.LOW_EMERGENCE_MAX_PCT = LOW_EMERGENCE_MAX_PCT
    operational._low_emergence_figure = _low_emergence_figure_5pct
    operational._plotly_chart_with_low_panel = _plotly_chart_with_5pct_caption
    st.toggle = _toggle_5pct

    try:
        operational.run()
    finally:
        operational.LOW_EMERGENCE_MAX_PCT = original_max_pct
        operational._low_emergence_figure = original_low_figure
        operational._plotly_chart_with_low_panel = original_plotly
        st.toggle = original_toggle

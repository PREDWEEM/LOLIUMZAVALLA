from __future__ import annotations

import re
from typing import Any, Mapping

import pandas as pd
import streamlit as st

import app_zoom_operativo as base


EMERGENCE_THRESHOLD = 0.001
_ORIGINAL_RENDER_EMERGENCE_SEMAPHORE = base._render_emergence_semaphore


def _seven_day_emergence_forecast(data: Any, today: Any) -> dict[str, Any]:
    """Evalúa emergencia futura con el criterio EMERREL >= 0,001."""
    today_date = pd.Timestamp(today).normalize()
    start_date = today_date + pd.Timedelta(days=1)
    end_date = today_date + pd.Timedelta(days=base._FORECAST_DAYS)

    status: dict[str, Any] = {
        "start_label": start_date.strftime("%d/%m/%Y"),
        "end_label": end_date.strftime("%d/%m/%Y"),
        "available_days": 0,
        "has_emergence": False,
        "positive_days": 0,
        "max_intensity_pct": 0.0,
        "first_emergence_label": None,
    }

    if data is None or "Fecha" not in data or "EMERREL" not in data:
        return status

    forecast = data.loc[:, ["Fecha", "EMERREL"]].copy()
    forecast["Fecha"] = pd.to_datetime(
        forecast["Fecha"], errors="coerce"
    ).dt.normalize()
    forecast["EMERREL"] = pd.to_numeric(
        forecast["EMERREL"], errors="coerce"
    )
    forecast = forecast.dropna(subset=["Fecha", "EMERREL"])
    forecast = forecast.loc[
        (forecast["Fecha"] >= start_date)
        & (forecast["Fecha"] <= end_date)
    ].sort_values("Fecha")

    if forecast.empty:
        return status

    positive = forecast["EMERREL"] >= EMERGENCE_THRESHOLD
    status["available_days"] = int(forecast["Fecha"].nunique())
    status["has_emergence"] = bool(positive.any())
    status["positive_days"] = int(positive.sum())
    status["max_intensity_pct"] = float(
        forecast["EMERREL"].clip(lower=0.0).max() * 100.0
    )

    if bool(positive.any()):
        first_date = pd.Timestamp(forecast.loc[positive, "Fecha"].iloc[0])
        status["first_emergence_label"] = first_date.strftime("%d/%m/%Y")

    return status


def _render_emergence_semaphore(status: Mapping[str, Any]) -> None:
    """Conserva el diseño y muestra correctamente el nuevo criterio operativo."""
    original_markdown = st.markdown

    def markdown_with_threshold(body: Any, *args: Any, **kwargs: Any):
        if isinstance(body, str):
            body = re.sub(
                r"EMERREL &gt; [0-9.]+",
                "EMERREL &gt;= 0.001",
                body,
            )
        return original_markdown(body, *args, **kwargs)

    st.markdown = markdown_with_threshold
    try:
        _ORIGINAL_RENDER_EMERGENCE_SEMAPHORE(status)
    finally:
        st.markdown = original_markdown


def run() -> None:
    """Ejecuta la aplicación con umbral de emergencia EMERREL >= 0,001."""
    original_threshold = base._EMERGENCE_THRESHOLD
    original_forecast = base._seven_day_emergence_forecast
    original_renderer = base._render_emergence_semaphore

    base._EMERGENCE_THRESHOLD = EMERGENCE_THRESHOLD
    base._seven_day_emergence_forecast = _seven_day_emergence_forecast
    base._render_emergence_semaphore = _render_emergence_semaphore

    try:
        base.run()
    finally:
        base._EMERGENCE_THRESHOLD = original_threshold
        base._seven_day_emergence_forecast = original_forecast
        base._render_emergence_semaphore = original_renderer

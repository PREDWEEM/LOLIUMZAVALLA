from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st

from app_multisitio_principal import run as run_main


_ORIGINAL_PLOTLY_CHART = st.plotly_chart
_ZOOM_BUTTONS = (
    "zoom2d",
    "pan2d",
    "autoScale2d",
    "resetScale2d",
)


def _config_with_zoom(config: Mapping[str, Any]) -> dict[str, Any]:
    """Devuelve una copia de la configuración con controles de ampliación."""
    enhanced = dict(config)
    current_buttons = list(enhanced.get("modeBarButtonsToAdd", []))

    for button in _ZOOM_BUTTONS:
        if button not in current_buttons:
            current_buttons.append(button)

    enhanced["modeBarButtonsToAdd"] = current_buttons
    enhanced["displayModeBar"] = True
    enhanced["scrollZoom"] = True
    enhanced["doubleClick"] = "reset+autosize"
    return enhanced


def _plotly_chart_with_zoom(*args: Any, **kwargs: Any):
    """Añade la lupa solo a gráficos que ya admiten zoom con la rueda."""
    config = kwargs.get("config")
    if isinstance(config, Mapping) and config.get("scrollZoom"):
        kwargs["config"] = _config_with_zoom(config)
    return _ORIGINAL_PLOTLY_CHART(*args, **kwargs)


def run() -> None:
    """Ejecuta PREDWEEM con la barra de zoom visible en los gráficos."""
    st.plotly_chart = _plotly_chart_with_zoom
    try:
        run_main()
    finally:
        st.plotly_chart = _ORIGINAL_PLOTLY_CHART

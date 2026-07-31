from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st

from app_multisitio import get_site, ordered_sites
from app_multisitio_principal import run as run_main
from mapa_sitios import render_site_map


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


class _SidebarWithSiteMap:
    """Inserta el mapa en el cuerpo principal antes de abrir la barra lateral."""

    def __init__(self, sidebar: Any, runtime_state: dict[str, Any]) -> None:
        self._sidebar = sidebar
        self._runtime_state = runtime_state

    def _render_map_once(self) -> None:
        if self._runtime_state.get("map_rendered"):
            return

        slug = self._runtime_state.get("selected_site_slug")
        if not slug:
            return

        site = get_site(str(slug))
        st.subheader("🗺️ Red PREDWEEM y sitio seleccionado")
        st.caption(
            "Los marcadores azules representan la red de localidades. "
            "El sitio activo se destaca en rojo y se actualiza al cambiar el selector."
        )
        try:
            with st.container(border=True):
                render_site_map(site, ordered_sites(), height=455)
        except Exception as exc:
            st.warning(f"No se pudo representar el mapa de sitios: {exc}")

        self._runtime_state["map_rendered"] = True

    def __enter__(self):
        self._render_map_once()
        return self._sidebar.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        return self._sidebar.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sidebar, name)


def run() -> None:
    """Ejecuta PREDWEEM con zoom y mapa geográfico del sitio activo."""
    original_selectbox = st.selectbox
    original_sidebar = st.sidebar
    runtime_state: dict[str, Any] = {
        "selected_site_slug": None,
        "map_rendered": False,
    }

    def selectbox_with_site_capture(*args: Any, **kwargs: Any):
        value = original_selectbox(*args, **kwargs)
        if kwargs.get("key") == "selected_lolium_site":
            runtime_state["selected_site_slug"] = value
        return value

    st.plotly_chart = _plotly_chart_with_zoom
    st.selectbox = selectbox_with_site_capture
    st.sidebar = _SidebarWithSiteMap(original_sidebar, runtime_state)
    try:
        run_main()
    finally:
        st.plotly_chart = _ORIGINAL_PLOTLY_CHART
        st.selectbox = original_selectbox
        st.sidebar = original_sidebar

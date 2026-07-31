from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st

from app_multisitio import get_site, ordered_sites
import app_multisitio_principal as principal
from mapa_sitios import render_site_map


_ORIGINAL_PLOTLY_CHART = st.plotly_chart
_ORIGINAL_CAPTION = st.caption
_ORIGINAL_EMERGENCE_FIGURE = principal.emergence_figure
_ORIGINAL_THERMAL_FIGURE = principal.thermal_figure
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


def _date_from_annotation(text: str) -> str:
    """Recupera la fecha ya formateada desde una anotación de Plotly."""
    return text.split("<br>", 1)[1] if "<br>" in text else ""


def _emergence_figure_with_phenology(*args: Any, **kwargs: Any):
    """Añade los estados de macollaje a la ventana del gráfico principal."""
    figure, x_range = _ORIGINAL_EMERGENCE_FIGURE(*args, **kwargs)

    for annotation in figure.layout.annotations or ():
        text = str(annotation.text or "")

        if text == "<b>Ventana recomendada de intervención</b>":
            annotation.update(
                text=(
                    "<b>Ventana recomendada de intervención</b><br>"
                    "<span style='font-size:10px;'>"
                    "2–3 macollos (600 °Cd) → 6 macollos (800 °Cd)"
                    "</span>"
                ),
                y=0.965,
                borderpad=6,
            )
        elif "<b>600 °Cd</b>" in text:
            date_label = _date_from_annotation(text)
            annotation.update(
                text=(
                    "<b>2–3 macollos</b><br>"
                    f"600 °Cd · {date_label}"
                )
            )
        elif "<b>800 °Cd</b>" in text:
            date_label = _date_from_annotation(text)
            annotation.update(
                text=(
                    "<b>6 macollos</b><br>"
                    f"800 °Cd · {date_label}"
                )
            )

    return figure, x_range


def _thermal_figure_with_phenology(*args: Any, **kwargs: Any):
    """Relaciona los umbrales térmicos con los estados de macollaje."""
    figure = _ORIGINAL_THERMAL_FIGURE(*args, **kwargs)

    for annotation in figure.layout.annotations or ():
        text = str(annotation.text or "")
        if "600 °Cd · inicio de ventana" in text:
            annotation.update(text="2–3 macollos · 600 °Cd · inicio de ventana")
        elif "800 °Cd · fin de ventana" in text:
            annotation.update(text="6 macollos · 800 °Cd · fin de ventana")

    return figure


def _caption_with_phenology(body: Any, *args: Any, **kwargs: Any):
    """Aclara la interpretación fenológica debajo del gráfico principal."""
    if body == (
        "Barras azules: emergencia diaria. Línea gris: tendencia de pulsos. "
        "Banda ámbar: ventana recomendada. Línea negra: fecha actual."
    ):
        body = (
            "Barras azules: emergencia diaria. Línea gris: tendencia de pulsos. "
            "Banda ámbar: ventana recomendada entre 2–3 macollos (600 °Cd) "
            "y 6 macollos (800 °Cd). Línea negra: fecha actual."
        )
    return _ORIGINAL_CAPTION(body, *args, **kwargs)


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
    """Ejecuta PREDWEEM con mapa, zoom y ventana fenológica operativa."""
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
    st.caption = _caption_with_phenology
    st.selectbox = selectbox_with_site_capture
    st.sidebar = _SidebarWithSiteMap(original_sidebar, runtime_state)
    principal.emergence_figure = _emergence_figure_with_phenology
    principal.thermal_figure = _thermal_figure_with_phenology

    try:
        principal.run()
    finally:
        st.plotly_chart = _ORIGINAL_PLOTLY_CHART
        st.caption = _ORIGINAL_CAPTION
        st.selectbox = original_selectbox
        st.sidebar = original_sidebar
        principal.emergence_figure = _ORIGINAL_EMERGENCE_FIGURE
        principal.thermal_figure = _ORIGINAL_THERMAL_FIGURE

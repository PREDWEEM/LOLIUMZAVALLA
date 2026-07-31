from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config_zavalla import CONFIG
from predweem_core import load_ann, phenology_window_dates, simulate_dual
from sitios_lolium import DEFAULT_SITE_SLUG, SITES, get_site, ordered_sites
from visualizacion_pulsos import construir_campanas_agrupadas


BASE = Path(__file__).resolve().parent
LEGACY_METEO_PATH = BASE / "meteo_daily.csv"
LOG_OFFSET = 0.01
LOG_Y_RANGE = [-2.18, 0.12]
LOG_Y_TICKS = [-2.0, -1.5, -1.0, -0.5, 0.0]

st.set_page_config(
    page_title="PREDWEEM LOLIUM Multisitio",
    page_icon="🌾",
    layout="wide",
)


def read_table(source) -> pd.DataFrame:
    name = str(getattr(source, "name", source)).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(source)
    return pd.read_csv(source)


@st.cache_resource
def get_ann():
    return load_ann(BASE)


def resolve_site_weather(site, uploaded_weather):
    if uploaded_weather is not None:
        return (
            read_table(uploaded_weather),
            "Archivo meteorológico cargado por el usuario",
        )

    site_path = site.meteo_path(BASE)
    if site_path.is_file() and site_path.stat().st_size > 40:
        return (
            pd.read_csv(site_path),
            f"Copia exacta del repositorio: {site_path.relative_to(BASE)}",
        )

    if (
        site.slug == DEFAULT_SITE_SLUG
        and LEGACY_METEO_PATH.is_file()
        and LEGACY_METEO_PATH.stat().st_size > 40
    ):
        return (
            pd.read_csv(LEGACY_METEO_PATH),
            "Copia exacta heredada: meteo_daily.csv",
        )

    return None, "Sin serie meteorológica disponible"


def add_phenology_window(
    figure: go.Figure,
    *,
    control_date: pd.Timestamp | None,
    limit_date: pd.Timestamp | None,
    final_date: pd.Timestamp,
    label: str,
) -> None:
    if control_date is None:
        return

    end_date = limit_date if limit_date is not None else final_date
    annotation = label if limit_date is not None else f"{label} · 800 °Cd pendiente"
    figure.add_vrect(
        x0=control_date,
        x1=end_date,
        fillcolor="#16a34a",
        opacity=0.16,
        layer="below",
        line_width=0,
        annotation_text=annotation,
        annotation_position="top left",
    )
    figure.add_vline(
        x=control_date,
        line_width=1.7,
        line_dash="dash",
        line_color="#15803d",
    )
    if limit_date is not None:
        figure.add_vline(
            x=limit_date,
            line_width=1.7,
            line_dash="dash",
            line_color="#15803d",
        )


def format_window(
    control_date: pd.Timestamp | None,
    limit_date: pd.Timestamp | None,
) -> str:
    if control_date is None:
        return "600 °Cd todavía no alcanzados"
    control_text = control_date.strftime("%d/%m/%Y")
    limit_text = (
        limit_date.strftime("%d/%m/%Y") if limit_date is not None else "pendiente"
    )
    return f"600 °Cd = {control_text}; 800 °Cd = {limit_text}"


def build_operational_data(
    data: pd.DataFrame,
    *,
    model_mode: str,
    lag_days: int,
) -> tuple[pd.DataFrame, str, pd.Timestamp | None]:
    out = data.copy()

    if model_mode == "con_lag":
        model_name = f"Con lag fijo de {lag_days} días"
        value_column = "EMERREL_CON_LAG"
        cumulative_column = "EMERAC_CON_LAG"
        thermal_column = "TT_DESDE_PICO_CON_LAG"
        termoinhibition_column = "Termoinhibida_CON_LAG"
        threshold_column = "Umbral_Termoinhibicion_CON_LAG_C"
        decay_column = "FACTOR_DECAIMIENTO_CON_LAG"
        days_column = "DIAS_DESDE_PICO_CON_LAG"
    elif model_mode == "sin_lag":
        model_name = "Sin lag"
        value_column = "EMERREL_SIN_LAG"
        cumulative_column = "EMERAC_SIN_LAG"
        thermal_column = "TT_DESDE_PICO_SIN_LAG"
        termoinhibition_column = "Termoinhibida_SIN_LAG"
        threshold_column = "Umbral_Termoinhibicion_SIN_LAG_C"
        decay_column = "FACTOR_DECAIMIENTO_SIN_LAG"
        days_column = "DIAS_DESDE_PICO_SIN_LAG"
    else:
        raise ValueError(f"Modelo operativo desconocido: {model_mode}")

    out["EMERREL"] = out[value_column]
    out["EMERREL_LOG"] = np.log10(
        out["EMERREL"].clip(lower=0.0) + LOG_OFFSET
    )
    out["EMERAC"] = out[cumulative_column]
    out["TT_DESDE_PICO"] = out[thermal_column]
    out["Termoinhibida_Operativa"] = out[termoinhibition_column]
    out["Umbral_Termoinhibicion_Operativo_C"] = out[threshold_column]
    out["FACTOR_DECAIMIENTO_OPERATIVO"] = out[decay_column]
    out["DIAS_DESDE_PICO_OPERATIVO"] = out[days_column]
    out["Modelo_Operativo"] = model_name
    out["Lag_Operativo_Dias"] = int(lag_days if model_mode == "con_lag" else 0)
    out["Modelo_Referencia_Local"] = model_mode

    selected_candidates = out.index[
        out["EMERREL"] > float(CONFIG.umbral_primer_pico)
    ]
    peak = (
        pd.Timestamp(out.loc[selected_candidates[0], "Fecha"])
        if len(selected_candidates)
        else None
    )

    dual_columns = [
        column
        for column in out.columns
        if "SIN_LAG" in column or "CON_LAG" in column
    ]
    out = out.drop(columns=dual_columns, errors="ignore")
    return out, model_name, peak


def phenology_clock_state(
    data: pd.DataFrame,
    *,
    operational_peak: pd.Timestamp | None,
    today: pd.Timestamp,
    control_cd: float,
    limit_cd: float,
) -> dict[str, object]:
    """Replica el reloj térmico operativo de los repositorios LOLIUM."""

    ordered = data.sort_values("Fecha").reset_index(drop=True)
    dates = pd.to_datetime(ordered["Fecha"]).dt.normalize()

    current_candidates = ordered.index[dates <= today].tolist()
    current_index = current_candidates[-1] if current_candidates else 0
    current_date = pd.Timestamp(ordered.loc[current_index, "Fecha"]).normalize()

    forecast_target = today + pd.Timedelta(days=7)
    forecast_candidates = ordered.index[dates <= forecast_target].tolist()
    forecast_index = (
        forecast_candidates[-1] if forecast_candidates else current_index
    )
    forecast_index = max(forecast_index, current_index)
    forecast_date = pd.Timestamp(
        ordered.loc[forecast_index, "Fecha"]
    ).normalize()

    current_raw = ordered.loc[current_index, "TT_DESDE_PICO"]
    forecast_raw = ordered.loc[forecast_index, "TT_DESDE_PICO"]
    dga_today = float(current_raw) if pd.notna(current_raw) else 0.0
    dga_7days = float(forecast_raw) if pd.notna(forecast_raw) else dga_today
    dga_today = max(dga_today, 0.0)
    dga_7days = max(dga_7days, dga_today)

    if operational_peak is None:
        message = "Esperando pico de emergencia..."
        status = "Reloj térmico aún no iniciado"
    else:
        peak = pd.Timestamp(operational_peak).normalize()
        message = (
            f"Pico validado > {float(CONFIG.umbral_primer_pico):.2f} "
            f"el {peak.strftime('%d/%m')}"
        )
        if dga_today < float(control_cd):
            status = "Acumulación térmica previa al control"
        elif dga_today < float(limit_cd):
            status = "Ventana fenológica de máxima susceptibilidad"
        else:
            status = "Ventana fenológica de 600–800 °Cd superada"

    return {
        "fecha_hoy": current_date,
        "fecha_pronostico": forecast_date,
        "dga_hoy": dga_today,
        "dga_7dias": dga_7days,
        "mensaje": message,
        "estado": status,
    }


def build_lolium_clock_figure(
    dga_today: float,
    dga_7days: float,
    *,
    control_cd: float,
    limit_cd: float,
    message: str,
) -> go.Figure:
    """Mismo formato de reloj utilizado en los repositorios LOLIUM."""

    max_axis = float(limit_cd) * 1.2
    forecast_marker = min(max(float(dga_7days), 0.0), max_axis)

    figure = go.Figure().add_trace(
        go.Indicator(
            mode="gauge+number",
            value=float(dga_today),
            domain={"x": [0, 1], "y": [0, 1]},
            title={
                "text": "<b>TT POST-EMERGENCIA (°Cd)</b>",
                "font": {"size": 18},
            },
            gauge={
                "axis": {"range": [None, max_axis]},
                "bar": {"color": "#1e293b", "thickness": 0.3},
                "steps": [
                    {"range": [0, float(control_cd)], "color": "#4ade80"},
                    {
                        "range": [float(control_cd), float(limit_cd)],
                        "color": "#facc15",
                    },
                    {
                        "range": [float(limit_cd), max_axis],
                        "color": "#f87171",
                    },
                ],
                "threshold": {
                    "line": {"color": "#2563eb", "width": 6},
                    "thickness": 0.8,
                    "value": forecast_marker,
                },
            },
        )
    )
    figure.add_annotation(
        x=0.5,
        y=-0.1,
        text=(
            f"{message}<br>"
            f"Pronóstico +7d: <b>{float(dga_7days):.1f} °Cd</b>"
        ),
        showarrow=False,
        font={"size": 14, "color": "#1e3a8a"},
        align="center",
    )
    figure.update_layout(
        height=350,
        margin={"t": 80, "b": 50, "l": 30, "r": 30},
    )
    return figure


def add_grouped_pulses(
    figure: go.Figure,
    data: pd.DataFrame,
    *,
    model_name: str,
) -> pd.DataFrame:
    """Grafica el modelo operativo en la escala logarítmica LOLIUM."""

    smooth = construir_campanas_agrupadas(
        data["Fecha"],
        data["EMERREL"],
        umbral=0.01,
        max_dias_sin_flujo=3,
        puntos_por_dia=6,
        sigma_min_dias=2.0,
    )
    smooth["EMERREL_CAMPANA_LOG"] = np.log10(
        smooth["EMERREL_CAMPANA"].clip(lower=0.0) + LOG_OFFSET
    )

    figure.add_trace(
        go.Scatter(
            x=smooth["Fecha"],
            y=smooth["EMERREL_CAMPANA_LOG"],
            customdata=smooth["EMERREL_CAMPANA"],
            name=f"Pulsos agrupados · {model_name}",
            mode="lines",
            line={"color": "#111827", "width": 2.2, "shape": "spline"},
            opacity=0.82,
            hovertemplate=(
                f"{model_name}<br>Fecha=%{{x|%d/%m/%Y}}"
                "<br>Log10(EMERREL + 0,01)=%{y:.3f}"
                "<br>Campana agrupada=%{customdata:.3f}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data["Fecha"],
            y=data["EMERREL_LOG"],
            customdata=data["EMERREL"],
            name="Tasa diaria simulada (log)",
            mode="lines",
            line={"color": "#075FCF", "width": 2.4},
            opacity=0.98,
            hovertemplate=(
                "<b>%{x|%d-%m-%Y}</b><br>"
                "Log10(EMERREL + 0,01): %{y:.3f}<br>"
                "EMERREL: %{customdata:.3f}<extra></extra>"
            ),
        )
    )
    return smooth


site_list = ordered_sites()
site_slugs = [site.slug for site in site_list]
default_index = site_slugs.index(DEFAULT_SITE_SLUG)

with st.sidebar:
    st.header("Configuración geográfica")
    selected_slug = st.selectbox(
        "Sitio específico",
        options=site_slugs,
        index=default_index,
        format_func=lambda slug: SITES[slug].etiqueta,
        key="selected_lolium_site",
    )
    site = get_site(selected_slug)

    st.write(f"**{site.etiqueta}**")
    st.caption(f"Lat {site.latitud:.5f} · Lon {site.longitud:.5f}")
    st.markdown(
        f"Repositorio de referencia: [`{site.repositorio}`]"
        f"({site.repository_url})"
    )
    st.success(f"Modelo automático: **{site.modelo_operativo_etiqueta}**")

    uploaded_weather = st.file_uploader(
        f"Meteorología diaria de {site.nombre}",
        type=["csv", "xlsx", "xls"],
        key=f"weather_upload_{site.slug}",
    )
    coverage = st.slider(
        "Cobertura de rastrojo (%)",
        0,
        100,
        CONFIG.cobertura_predeterminada_pct,
        5,
        key=f"coverage_{site.slug}",
        help=(
            "Única variable de ajuste visible. Modifica el coeficiente de "
            "evaporación del suelo y el modulador térmico superficial."
        ),
    )
    st.caption(
        "La cobertura es la única variable de ajuste. Los demás parámetros "
        "permanecen fijados por la calibración específica de cada localidad."
    )

site_config = replace(
    CONFIG,
    nombre_sitio=site.etiqueta,
    latitud=site.latitud,
    longitud=site.longitud,
    timezone=site.timezone,
)
fixed_wmax = float(site_config.wmax_predeterminado_mm)
fixed_kr_exponent = float(site_config.exponente_kr_predeterminado)
meteo_path = site.meteo_path(BASE)

st.title(f"🌾 PREDWEEM {site.nombre} — {site.modelo_operativo_etiqueta}")
st.caption(
    "Predicción operativa de emergencia de Lolium con selección automática "
    "del modelo según la localidad."
)

weather, weather_source = resolve_site_weather(site, uploaded_weather)
st.caption(f"**Fuente meteorológica activa:** {weather_source}")

if weather is None or weather.empty:
    st.warning(
        f"No existe una serie meteorológica operativa para {site.etiqueta}. "
        "Ejecute el workflow diario o cargue un archivo con Fecha, TMAX, "
        "TMIN y Prec."
    )
    st.stop()

try:
    ann = get_ann()
    result = simulate_dual(
        weather,
        ann,
        coverage_percent=coverage,
        wmax=fixed_wmax,
        lag_days=int(site.lag_operativo_dias),
        kr_exponent=fixed_kr_exponent,
        config=site_config,
    )
    plot_data, model_name, operational_peak = build_operational_data(
        result.data,
        model_mode=site.modelo_operativo,
        lag_days=site.lag_operativo_dias,
    )
except Exception as exc:
    st.error(f"No se pudo ejecutar PREDWEEM para {site.nombre}: {exc}")
    st.stop()

plot_data["Fecha"] = pd.to_datetime(plot_data["Fecha"])
plot_data["Sitio"] = site.nombre
plot_data["Latitud"] = site.latitud
plot_data["Longitud"] = site.longitud

control_date, limit_date = phenology_window_dates(
    plot_data["Fecha"],
    plot_data["TT_DESDE_PICO"],
    site_config.tt_control_cd,
    site_config.tt_limite_cd,
)

today_local = (
    pd.Timestamp.now(tz=site.timezone)
    .tz_localize(None)
    .normalize()
)
clock_state = phenology_clock_state(
    plot_data,
    operational_peak=operational_peak,
    today=today_local,
    control_cd=site_config.tt_control_cd,
    limit_cd=site_config.tt_limite_cd,
)

st.markdown(
    "<div style='padding:16px;border-radius:12px;border:2px solid #15803d;"
    "background:#f0fdf4'>"
    f"<b>Sitio:</b> {site.etiqueta}<br>"
    f"<b>Modelo operativo automático:</b> {model_name}<br>"
    f"<b>Cobertura de rastrojo ajustada:</b> {coverage}%<br>"
    "<b>Selección:</b> regla fija por localidad; sin recuentos de campo."
    "</div>",
    unsafe_allow_html=True,
)

summary_metrics = st.columns(2)
summary_metrics[0].metric("Cobertura de rastrojo", f"{coverage}%")
summary_metrics[1].metric(
    "Primer pico",
    operational_peak.strftime("%d/%m/%Y")
    if operational_peak is not None
    else "—",
)

fig = go.Figure()
smooth_export = add_grouped_pulses(fig, plot_data, model_name=model_name)
smooth_export["Modelo"] = model_name
smooth_export["Sitio"] = site.nombre

final_date = pd.Timestamp(plot_data["Fecha"].max())
add_phenology_window(
    fig,
    control_date=control_date,
    limit_date=limit_date,
    final_date=final_date,
    label="Ventana fenológica 600–800 °Cd",
)

fig.update_layout(
    template="plotly_white",
    title={
        "text": f"{site.nombre} · Modelo operativo: {model_name}",
        "x": 0.0,
        "xanchor": "left",
    },
    xaxis={
        "title": "Fecha",
        "showgrid": False,
        "showline": True,
        "linecolor": "#6B7280",
        "ticks": "outside",
        "zeroline": False,
    },
    yaxis={
        "title": "Log10(EMERREL + 0,01)",
        "range": LOG_Y_RANGE,
        "tickmode": "array",
        "tickvals": LOG_Y_TICKS,
        "showgrid": True,
        "gridcolor": "rgba(148, 163, 184, 0.28)",
        "griddash": "dash",
        "showline": True,
        "linecolor": "#6B7280",
        "zeroline": False,
    },
    hovermode="x unified",
    height=580,
    margin={"l": 82, "r": 35, "t": 65, "b": 90},
    legend={
        "orientation": "h",
        "yanchor": "top",
        "y": -0.16,
        "xanchor": "left",
        "x": 0.0,
    },
)
fig.update_yaxes(fixedrange=False)
fig.update_xaxes(fixedrange=False)

col_main, col_gauge = st.columns([3.4, 1])

with col_main:
    st.plotly_chart(
        fig,
        width="stretch",
        config={
            "displaylogo": False,
            "responsive": True,
            "scrollZoom": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"PREDWEEM_{site.slug}_emergencia_log",
                "height": 1000,
                "width": 2000,
                "scale": 2,
            },
        },
    )
    st.caption(
        "El eje Y representa Log10(EMERREL + 0,01), igual que en los "
        "repositorios LOLIUM. Los valores originales de EMERREL se conservan "
        "en la tabla, la descarga y el cursor del gráfico."
    )
    st.caption(
        f"Ventana fenológica: {format_window(control_date, limit_date)}"
    )

with col_gauge:
    gauge_figure = build_lolium_clock_figure(
        float(clock_state["dga_hoy"]),
        float(clock_state["dga_7dias"]),
        control_cd=site_config.tt_control_cd,
        limit_cd=site_config.tt_limite_cd,
        message=str(clock_state["mensaje"]),
    )
    st.plotly_chart(gauge_figure, width="stretch")

with st.expander("Resultados diarios del modelo operativo"):
    st.dataframe(plot_data, width="stretch", hide_index=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Sitio": site.nombre,
                    "Provincia": site.provincia,
                    "Latitud": site.latitud,
                    "Longitud": site.longitud,
                    "Repositorio_origen": site.repositorio,
                    "Archivo_meteorologico": str(
                        meteo_path.relative_to(BASE)
                    ),
                    "Fuente_meteorologica_activa": weather_source,
                    "Modelo_operativo": model_name,
                    "Lag_operativo_dias": (
                        site.lag_operativo_dias
                        if site.modelo_operativo == "con_lag"
                        else 0
                    ),
                    "Cobertura_rastrojo_pct": coverage,
                    "Transformacion_grafica_Y": (
                        "log10(EMERREL + 0.01)"
                    ),
                    "Seleccion_automatica": True,
                    "Usa_recuento_campo": False,
                }
            ]
        ).to_excel(writer, sheet_name="Sitio", index=False)
        plot_data.to_excel(
            writer,
            sheet_name="Simulacion_Operativa",
            index=False,
        )
        pd.DataFrame(
            [
                {
                    "Modelo": model_name,
                    "Fecha_primer_pico": operational_peak,
                    "Fecha_reloj": clock_state["fecha_hoy"],
                    "TT_actual_desde_pico_Cd": clock_state["dga_hoy"],
                    "Fecha_pronostico_7d": clock_state["fecha_pronostico"],
                    "TT_pronostico_7d_Cd": clock_state["dga_7dias"],
                    "Estado_fenologico": clock_state["estado"],
                    "Fecha_600_Cd": control_date,
                    "Fecha_800_Cd": limit_date,
                    "Cobertura_rastrojo_pct": coverage,
                }
            ]
        ).to_excel(writer, sheet_name="Reloj_Fenologico", index=False)
        smooth_export.to_excel(
            writer,
            sheet_name="Pulsos_Agrupados",
            index=False,
        )

    st.download_button(
        "Descargar resultados completos",
        data=buffer.getvalue(),
        file_name=f"PREDWEEM_{site.slug}_Resultados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption(
    "Política automática: Pergamino y Zavalla usan solamente el modelo con "
    "lag fijo; las demás localidades usan solamente el modelo sin lag."
)

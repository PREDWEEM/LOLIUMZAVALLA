from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config_zavalla import CONFIG
from predweem_core import load_ann, phenology_window_dates, simulate_dual
from sitios_lolium import DEFAULT_SITE_SLUG, SITES, get_site, ordered_sites
from visualizacion_pulsos import construir_campanas_agrupadas


BASE = Path(__file__).resolve().parent
LEGACY_METEO_PATH = BASE / "meteo_daily.csv"

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
    out["EMERAC"] = out[cumulative_column]
    out["TT_DESDE_PICO"] = out[thermal_column]
    out["Termoinhibida_Operativa"] = out[termoinhibition_column]
    out["Umbral_Termoinhibicion_Operativo_C"] = out[threshold_column]
    out["FACTOR_DECAIMIENTO_OPERATIVO"] = out[decay_column]
    out["DIAS_DESDE_PICO_OPERATIVO"] = out[days_column]
    out["Modelo_Operativo"] = model_name
    out["Lag_Operativo_Dias"] = int(lag_days if model_mode == "con_lag" else 0)
    out["Modelo_Referencia_Local"] = model_mode

    selected_candidates = out.index[out["EMERREL"] > float(CONFIG.umbral_primer_pico)]
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


def add_grouped_pulses(
    figure: go.Figure,
    data: pd.DataFrame,
    *,
    model_name: str,
) -> pd.DataFrame:
    smooth = construir_campanas_agrupadas(
        data["Fecha"],
        data["EMERREL"],
        umbral=0.01,
        max_dias_sin_flujo=3,
        puntos_por_dia=6,
        sigma_min_dias=2.0,
    )

    figure.add_trace(
        go.Scatter(
            x=smooth["Fecha"],
            y=smooth["EMERREL_CAMPANA"],
            name=f"Pulsos agrupados · {model_name}",
            mode="lines",
            line={"color": "#111827", "width": 2.6, "shape": "spline"},
            fill="tozeroy",
            fillcolor="rgba(96, 165, 250, 0.22)",
            showlegend=False,
            hovertemplate=(
                f"{model_name}<br>Fecha=%{{x|%d/%m/%Y}}"
                "<br>Campana agrupada=%{y:.3f}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=data["Fecha"],
            y=data["EMERREL"],
            name=model_name,
            mode="lines",
            line={"color": "#1677d2", "width": 1.6},
            opacity=0.95,
            hovertemplate=(
                f"{model_name}<br>Fecha=%{{x|%d/%m/%Y}}"
                "<br>EMERREL diaria=%{y:.3f}<extra></extra>"
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
    )
    wmax = st.number_input(
        "Wmax superficial (mm)",
        5.0,
        60.0,
        CONFIG.wmax_predeterminado_mm,
        0.5,
        key=f"wmax_{site.slug}",
    )
    kr_exponent = st.slider(
        "Exponente Kr",
        0.0,
        2.0,
        CONFIG.exponente_kr_predeterminado,
        0.1,
        key=f"kr_{site.slug}",
    )
    st.caption(
        "La localidad determina automáticamente el modelo operativo. "
        "No se utilizan recuentos ni validaciones de campo para seleccionarlo."
    )

site_config = replace(
    CONFIG,
    nombre_sitio=site.etiqueta,
    latitud=site.latitud,
    longitud=site.longitud,
    timezone=site.timezone,
)
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
        wmax=float(wmax),
        lag_days=int(site.lag_operativo_dias),
        kr_exponent=float(kr_exponent),
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

st.markdown(
    "<div style='padding:16px;border-radius:12px;border:2px solid #15803d;"
    "background:#f0fdf4'>"
    f"<b>Sitio:</b> {site.etiqueta}<br>"
    f"<b>Modelo operativo automático:</b> {model_name}<br>"
    f"<b>Lag aplicado:</b> "
    f"{site.lag_operativo_dias if site.modelo_operativo == 'con_lag' else 0} días<br>"
    "<b>Selección:</b> regla fija por localidad; sin recuentos de campo."
    "</div>",
    unsafe_allow_html=True,
)

metrics = st.columns(5)
metrics[0].metric("Modelo operativo", model_name)
metrics[1].metric(
    "Primer pico",
    operational_peak.strftime("%d/%m/%Y") if operational_peak is not None else "—",
)
metrics[2].metric(
    "Lag operativo",
    f"{site.lag_operativo_dias} días"
    if site.modelo_operativo == "con_lag"
    else "0 días",
)
metrics[3].metric("Ke", f"{result.ke:.3f}")
metrics[4].metric("Wmax", f"{wmax:.1f} mm")

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
    xaxis={"title": "Fecha", "showgrid": False, "zeroline": False},
    yaxis={
        "title": "EMERREL",
        "range": [0.0, 1.05],
        "zeroline": False,
        "gridcolor": "rgba(148, 163, 184, 0.22)",
    },
    hovermode="x unified",
    height=580,
    margin={"l": 55, "r": 35, "t": 65, "b": 90},
    legend={
        "orientation": "h",
        "yanchor": "top",
        "y": -0.16,
        "xanchor": "left",
        "x": 0.0,
    },
)
st.plotly_chart(fig, width="stretch")
st.caption(
    "La línea fina representa EMERREL diaria. La envolvente agrupa "
    "activaciones cercanas como pulsos suaves."
)
st.caption(f"Ventana fenológica: {format_window(control_date, limit_date)}")

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
                    "Archivo_meteorologico": str(meteo_path.relative_to(BASE)),
                    "Fuente_meteorologica_activa": weather_source,
                    "Modelo_operativo": model_name,
                    "Lag_operativo_dias": (
                        site.lag_operativo_dias
                        if site.modelo_operativo == "con_lag"
                        else 0
                    ),
                    "Seleccion_automatica": True,
                    "Usa_recuento_campo": False,
                }
            ]
        ).to_excel(writer, sheet_name="Sitio", index=False)
        plot_data.to_excel(writer, sheet_name="Simulacion_Operativa", index=False)
        pd.DataFrame(
            [
                {
                    "Modelo": model_name,
                    "Fecha_600_Cd": control_date,
                    "Fecha_800_Cd": limit_date,
                }
            ]
        ).to_excel(writer, sheet_name="Ventana_Fenologica", index=False)
        smooth_export.to_excel(writer, sheet_name="Pulsos_Agrupados", index=False)

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

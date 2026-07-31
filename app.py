from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config_zavalla import CONFIG
from predweem_core import load_ann, phenology_window_dates, simulate_dual
from selector_adaptativo import (
    INSPECTION_COLUMNS,
    evaluate_selector,
    load_inspections,
    normalize_inspections,
    save_decision,
    save_inspections,
    visible_models,
)
from sitios_lolium import DEFAULT_SITE_SLUG, SITES, get_site, ordered_sites
from visualizacion_pulsos import construir_campanas_agrupadas

BASE = Path(__file__).resolve().parent
LEGACY_METEO_PATH = BASE / "meteo_daily.csv"
LEGACY_INSPECTIONS_PATH = BASE / "data" / "inspecciones_campo.csv"

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


def load_site_inspections(site) -> pd.DataFrame:
    path = site.inspections_path(BASE)
    if path.is_file() and path.stat().st_size:
        return load_inspections(path)
    if site.slug == DEFAULT_SITE_SLUG and LEGACY_INSPECTIONS_PATH.is_file():
        return load_inspections(LEGACY_INSPECTIONS_PATH)
    return normalize_inspections(None)


def resolve_site_weather(site, uploaded_weather):
    if uploaded_weather is not None:
        return read_table(uploaded_weather), "Archivo meteorológico cargado por el usuario"

    site_path = site.meteo_path(BASE)
    if site_path.is_file() and site_path.stat().st_size > 40:
        return pd.read_csv(site_path), f"Serie automática: {site_path.relative_to(BASE)}"

    if (
        site.slug == DEFAULT_SITE_SLUG
        and LEGACY_METEO_PATH.is_file()
        and LEGACY_METEO_PATH.stat().st_size > 40
    ):
        return pd.read_csv(LEGACY_METEO_PATH), "Serie automática heredada: meteo_daily.csv"

    return None, "Sin serie meteorológica disponible"


def add_phenology_window(
    figure: go.Figure,
    *,
    control_date: pd.Timestamp | None,
    limit_date: pd.Timestamp | None,
    final_date: pd.Timestamp,
    label: str,
    fillcolor: str,
) -> None:
    if control_date is None:
        return

    end_date = limit_date if limit_date is not None else final_date
    annotation = label if limit_date is not None else f"{label} · 800 °Cd pendiente"
    figure.add_vrect(
        x0=control_date,
        x1=end_date,
        fillcolor=fillcolor,
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
        line_color=fillcolor,
    )
    if limit_date is not None:
        figure.add_vline(
            x=limit_date,
            line_width=1.7,
            line_dash="dash",
            line_color=fillcolor,
        )


def format_window(
    name: str,
    control_date: pd.Timestamp | None,
    limit_date: pd.Timestamp | None,
) -> str:
    if control_date is None:
        return f"{name}: 600 °Cd todavía no alcanzados"
    control_text = control_date.strftime("%d/%m/%Y")
    limit_text = (
        limit_date.strftime("%d/%m/%Y") if limit_date is not None else "pendiente"
    )
    return f"{name}: 600 °Cd = {control_text}; 800 °Cd = {limit_text}"


def add_grouped_pulses(
    figure: go.Figure,
    data: pd.DataFrame,
    *,
    value_column: str,
    model_name: str,
    selected_model: bool,
    daily_color: str,
    outline_color: str,
    fill_color: str,
) -> pd.DataFrame:
    smooth = construir_campanas_agrupadas(
        data["Fecha"],
        data[value_column],
        umbral=0.01,
        max_dias_sin_flujo=3,
        puntos_por_dia=6,
        sigma_min_dias=2.0,
    )

    if selected_model:
        outline_color = "#111827"
        fill_color = "rgba(96, 165, 250, 0.22)"
        daily_color = "#1677d2"

    figure.add_trace(
        go.Scatter(
            x=smooth["Fecha"],
            y=smooth["EMERREL_CAMPANA"],
            name=f"Pulsos agrupados · {model_name}",
            mode="lines",
            line={"color": outline_color, "width": 2.6, "shape": "spline"},
            fill="tozeroy",
            fillcolor=fill_color,
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
            y=data[value_column],
            name=model_name,
            mode="lines",
            line={"color": daily_color, "width": 1.5},
            opacity=0.92,
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
    st.markdown(f"Repositorio de referencia: [`{site.repositorio}`]({site.repository_url})")

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
    lag_candidate = st.number_input(
        "Lag fijo del modelo con lag (días)",
        0,
        30,
        CONFIG.lag_candidato_dias,
        1,
        key=f"lag_{site.slug}",
    )
    st.caption(
        "El motor adaptativo es común; la selección del sitio ajusta identidad, "
        "meteorología y latitud empleada por ET0."
    )

site_config = replace(
    CONFIG,
    nombre_sitio=site.etiqueta,
    latitud=site.latitud,
    longitud=site.longitud,
    timezone=site.timezone,
)
meteo_path = site.meteo_path(BASE)
inspections_path = site.inspections_path(BASE)
state_path = site.selector_state_path(BASE)

st.title(f"🌾 PREDWEEM {site.nombre} — Selector sin lag / con lag")
st.caption(
    "Modelo dual para emergencia de Lolium con sitio geográfico seleccionable. "
    "Cada localidad conserva su propia meteorología, inspecciones y estado operativo."
)

weather, weather_source = resolve_site_weather(site, uploaded_weather)
st.caption(f"**Fuente meteorológica activa:** {weather_source}")

if weather is None or weather.empty:
    st.warning(
        f"No existe una serie meteorológica operativa para {site.etiqueta}. "
        "Ejecute el workflow multisitio o cargue un archivo con Fecha, TMAX, "
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
        lag_days=int(lag_candidate),
        kr_exponent=float(kr_exponent),
        config=site_config,
    )
except Exception as exc:
    st.error(f"No se pudo ejecutar PREDWEEM para {site.nombre}: {exc}")
    st.stop()

inspection_session_key = f"inspections::{site.slug}"
stored = load_site_inspections(site)
uploaded_inspections = st.sidebar.file_uploader(
    f"Restaurar inspecciones de {site.nombre}",
    type=["csv"],
    key=f"inspection_restore_{site.slug}",
)
if inspection_session_key not in st.session_state:
    st.session_state[inspection_session_key] = stored
if uploaded_inspections is not None:
    restored = normalize_inspections(pd.read_csv(uploaded_inspections))
    st.session_state[inspection_session_key] = restored
    save_inspections(restored, inspections_path)

inspections = normalize_inspections(st.session_state[inspection_session_key])
decision = evaluate_selector(
    result.first_peak_no_lag,
    result.first_peak_lag,
    inspections,
    lag_candidate_days=int(lag_candidate),
    config=site_config,
)
save_decision(decision, state_path)

state_color = {
    "SIN_LAG_CONFIRMADO": "green",
    "CON_LAG_CONFIRMADO": "green",
    "CON_LAG_PROVISIONAL": "orange",
    "NINGUNO_CONFIRMADO": "red",
}.get(decision.estado, "blue")
model_label = {
    "pendiente": "Pendiente de verificación",
    "sin_lag": "Sin lag",
    "con_lag": f"Con lag fijo de {lag_candidate} días",
    "ninguno": "Ninguno confirmado",
}.get(decision.modelo_activo, decision.modelo_activo)

st.markdown(
    f"<div style='padding:16px;border-radius:12px;border:2px solid {state_color};background:white'>"
    f"<b>Sitio:</b> {site.etiqueta}<br>"
    f"<b>Estado:</b> {decision.estado}<br>"
    f"<b>Modelo operativo:</b> {model_label}<br>"
    f"<b>Próxima acción:</b> {decision.proxima_accion}<br>"
    f"<b>Motivo:</b> {decision.motivo}</div>",
    unsafe_allow_html=True,
)

metrics = st.columns(6)
metrics[0].metric(
    "Pico sin lag",
    result.first_peak_no_lag.strftime("%d/%m/%Y")
    if result.first_peak_no_lag
    else "—",
)
metrics[1].metric(
    "Pico con lag",
    result.first_peak_lag.strftime("%d/%m/%Y") if result.first_peak_lag else "—",
)
metrics[2].metric(
    "Lag operativo",
    f"{decision.lag_operativo_dias} días"
    if decision.lag_operativo_dias is not None
    else "—",
)
metrics[3].metric("Ke", f"{result.ke:.3f}")
metrics[4].metric("Wmax", f"{wmax:.1f} mm")
metrics[5].metric("Próxima inspección", decision.proxima_inspeccion or "—")

plot_data = result.data.copy()
plot_data["Fecha"] = pd.to_datetime(plot_data["Fecha"])
plot_data["Sitio"] = site.nombre
plot_data["Latitud"] = site.latitud
plot_data["Longitud"] = site.longitud
show_no_lag, show_lag = visible_models(decision)
control_no_lag, limit_no_lag = phenology_window_dates(
    plot_data["Fecha"],
    plot_data["TT_DESDE_PICO_SIN_LAG"],
    site_config.tt_control_cd,
    site_config.tt_limite_cd,
)
control_lag, limit_lag = phenology_window_dates(
    plot_data["Fecha"],
    plot_data["TT_DESDE_PICO_CON_LAG"],
    site_config.tt_control_cd,
    site_config.tt_limite_cd,
)

fig = go.Figure()
selected_single_model = show_no_lag != show_lag
smooth_exports: list[pd.DataFrame] = []

if show_no_lag:
    smooth_no_lag = add_grouped_pulses(
        fig,
        plot_data,
        value_column="EMERREL_SIN_LAG",
        model_name="Sin lag",
        selected_model=selected_single_model,
        daily_color="#2563eb",
        outline_color="#1e3a8a",
        fill_color="rgba(37, 99, 235, 0.18)",
    )
    smooth_no_lag["Modelo"] = "Sin lag"
    smooth_no_lag["Sitio"] = site.nombre
    smooth_exports.append(smooth_no_lag)

if show_lag:
    smooth_lag = add_grouped_pulses(
        fig,
        plot_data,
        value_column="EMERREL_CON_LAG",
        model_name=f"Lag fijo {lag_candidate} días",
        selected_model=selected_single_model,
        daily_color="#f59e0b",
        outline_color="#92400e",
        fill_color="rgba(245, 158, 11, 0.20)",
    )
    smooth_lag["Modelo"] = f"Lag fijo {lag_candidate} días"
    smooth_lag["Sitio"] = site.nombre
    smooth_exports.append(smooth_lag)

final_date = pd.Timestamp(plot_data["Fecha"].max())
if show_no_lag and show_lag:
    add_phenology_window(
        fig,
        control_date=control_no_lag,
        limit_date=limit_no_lag,
        final_date=final_date,
        label="600–800 °Cd · sin lag",
        fillcolor="#2563eb",
    )
    add_phenology_window(
        fig,
        control_date=control_lag,
        limit_date=limit_lag,
        final_date=final_date,
        label=f"600–800 °Cd · lag {lag_candidate} d",
        fillcolor="#f59e0b",
    )
elif show_no_lag:
    add_phenology_window(
        fig,
        control_date=control_no_lag,
        limit_date=limit_no_lag,
        final_date=final_date,
        label="Ventana fenológica 600–800 °Cd",
        fillcolor="#16a34a",
    )
elif show_lag:
    add_phenology_window(
        fig,
        control_date=control_lag,
        limit_date=limit_lag,
        final_date=final_date,
        label="Ventana fenológica 600–800 °Cd",
        fillcolor="#16a34a",
    )

if not inspections.empty:
    fig.add_trace(
        go.Scatter(
            x=inspections["Fecha"],
            y=inspections["Plantas_m2"],
            name="Campo (plantas/m²)",
            mode="markers",
            marker={
                "size": 11,
                "symbol": "x",
                "color": "#60a5fa",
                "line": {"width": 2, "color": "#60a5fa"},
            },
            yaxis="y2",
            hovertemplate=(
                "Campo<br>Fecha=%{x|%d/%m/%Y}"
                "<br>Plantas/m²=%{y:.2f}<extra></extra>"
            ),
        )
    )

if show_no_lag and show_lag:
    model_graph_title = "Comparación de modelos antes de la selección"
elif show_no_lag:
    model_graph_title = "Modelo seleccionado: sin lag"
elif show_lag:
    model_graph_title = f"Modelo seleccionado: lag fijo de {lag_candidate} días"
else:
    model_graph_title = "Sin modelo visible"

graph_title = f"{site.nombre} · {model_graph_title}"
field_max = 1.0
if not inspections.empty:
    field_max = max(float(inspections["Plantas_m2"].max()), 1.0)

fig.update_layout(
    template="plotly_white",
    title={"text": graph_title, "x": 0.0, "xanchor": "left"},
    xaxis={"title": "Fecha", "showgrid": False, "zeroline": False},
    yaxis={
        "title": "EMERREL",
        "range": [0.0, 1.05],
        "zeroline": False,
        "gridcolor": "rgba(148, 163, 184, 0.22)",
    },
    yaxis2={
        "title": "Plantas/m²",
        "overlaying": "y",
        "side": "right",
        "showgrid": False,
        "zeroline": False,
        "range": [0.0, field_max * 1.15],
    },
    hovermode="x unified",
    height=580,
    margin={"l": 55, "r": 65, "t": 65, "b": 90},
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
    "La línea fina representa EMERREL diaria. La envolvente coloreada agrupa "
    "activaciones cercanas como pulsos suaves en forma de campana."
)

window_messages = []
if show_no_lag:
    window_messages.append(format_window("Sin lag", control_no_lag, limit_no_lag))
if show_lag:
    window_messages.append(
        format_window(
            f"Con lag fijo de {lag_candidate} días",
            control_lag,
            limit_lag,
        )
    )
st.caption(" · ".join(window_messages))

if decision.modelo_activo in {"sin_lag", "con_lag"}:
    st.info(
        "El modelo alternativo fue retirado de la gráfica porque la evidencia "
        "de campo ya produjo una selección operativa."
    )

st.subheader(f"Registrar inspección de campo · {site.nombre}")
with st.form(f"inspection_form_{site.slug}", clear_on_submit=True):
    columns = st.columns(4)
    inspection_date = columns[0].date_input("Fecha")
    operator = columns[1].text_input("Operario")
    plants_m2 = columns[2].number_input(
        "Plantas/m²", min_value=0.0, value=0.0, step=0.1
    )
    total_quadrats = columns[3].number_input(
        "Cuadros totales", min_value=1, value=10, step=1
    )
    positive_quadrats = st.number_input(
        "Cuadros positivos",
        min_value=0,
        max_value=int(total_quadrats),
        value=0,
        step=1,
    )
    explicit_confirmation = st.checkbox("Emergencia de Lolium confirmada")
    notes = st.text_area("Observaciones")
    submitted = st.form_submit_button("Guardar inspección", type="primary")

if submitted:
    row = pd.DataFrame(
        [
            [
                pd.Timestamp(inspection_date),
                operator,
                plants_m2,
                positive_quadrats,
                total_quadrats,
                explicit_confirmation,
                notes,
            ]
        ],
        columns=INSPECTION_COLUMNS,
    )
    updated = normalize_inspections(pd.concat([inspections, row], ignore_index=True))
    st.session_state[inspection_session_key] = updated
    save_inspections(updated, inspections_path)
    st.success(
        f"Inspección registrada para {site.nombre}. El selector se recalculará."
    )
    st.rerun()

st.subheader(f"Historial y auditoría · {site.nombre}")
if inspections.empty:
    st.info("Todavía no existen registros de campo para el sitio seleccionado.")
else:
    display_inspections = inspections.copy()
    display_inspections.insert(0, "Registro", range(1, len(display_inspections) + 1))
    st.dataframe(display_inspections, width="stretch", hide_index=True)

    option_labels = {
        index: (
            f"Registro {index + 1} · "
            f"{pd.Timestamp(row['Fecha']).strftime('%d/%m/%Y')} · "
            f"{str(row['Operario']).strip() or 'Sin operario'} · "
            f"{float(row['Plantas_m2']):.2f} plantas/m²"
        )
        for index, row in inspections.iterrows()
    }
    signature = int(
        pd.util.hash_pandas_object(inspections.astype(str), index=True).sum()
    )
    selected_indices = st.multiselect(
        "Seleccionar registros de campo para borrar",
        options=list(option_labels),
        format_func=lambda value: option_labels[value],
        key=f"delete_indices_{site.slug}_{signature}",
    )
    confirm_delete = st.checkbox(
        "Confirmo que deseo borrar los registros seleccionados",
        key=f"confirm_delete_{site.slug}_{signature}",
    )
    delete_clicked = st.button(
        "🗑️ Borrar registros seleccionados",
        disabled=not selected_indices or not confirm_delete,
        type="secondary",
        key=f"delete_button_{site.slug}_{signature}",
    )
    if delete_clicked:
        updated = inspections.drop(index=selected_indices, errors="ignore").reset_index(
            drop=True
        )
        updated = normalize_inspections(updated)
        st.session_state[inspection_session_key] = updated
        save_inspections(updated, inspections_path)
        st.success(
            f"Se borraron {len(selected_indices)} registro(s) de {site.nombre}."
        )
        st.rerun()

st.download_button(
    "Descargar inspecciones CSV",
    data=inspections.to_csv(index=False).encode("utf-8"),
    file_name=f"PREDWEEM_{site.slug}_inspecciones.csv",
    mime="text/csv",
)
st.download_button(
    "Descargar estado del selector",
    data=json.dumps(decision.to_dict(), indent=2, ensure_ascii=False).encode("utf-8"),
    file_name=f"PREDWEEM_{site.slug}_selector.json",
    mime="application/json",
)

with st.expander("Resultados diarios"):
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
                }
            ]
        ).to_excel(writer, sheet_name="Sitio", index=False)
        plot_data.to_excel(writer, sheet_name="Simulacion_Diaria", index=False)
        inspections.to_excel(writer, sheet_name="Inspecciones", index=False)
        pd.DataFrame([decision.to_dict()]).to_excel(
            writer, sheet_name="Selector", index=False
        )
        pd.DataFrame(
            [
                {
                    "Modelo": "Sin lag",
                    "Fecha_600_Cd": control_no_lag,
                    "Fecha_800_Cd": limit_no_lag,
                },
                {
                    "Modelo": f"Con lag fijo de {lag_candidate} días",
                    "Fecha_600_Cd": control_lag,
                    "Fecha_800_Cd": limit_lag,
                },
            ]
        ).to_excel(writer, sheet_name="Ventana_Fenologica", index=False)
        if smooth_exports:
            pd.concat(smooth_exports, ignore_index=True).to_excel(
                writer, sheet_name="Pulsos_Agrupados", index=False
            )
    st.download_button(
        "Descargar resultados completos",
        data=buffer.getvalue(),
        file_name=f"PREDWEEM_{site.slug}_Resultados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption(
    "Cada sitio mantiene archivos independientes. Si los dos conteos iniciales "
    "son negativos, el sistema selecciona automáticamente el modelo con lag fijo."
)

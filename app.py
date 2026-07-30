from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config_zavalla import CONFIG
from predweem_core import load_ann, simulate_dual
from selector_adaptativo import (
    INSPECTION_COLUMNS,
    evaluate_selector,
    load_inspections,
    normalize_inspections,
    save_decision,
    save_inspections,
    visible_models,
)

BASE = Path(__file__).resolve().parent
METEO_PATH = BASE / "meteo_daily.csv"
INSPECTIONS_PATH = BASE / "data" / "inspecciones_campo.csv"
STATE_PATH = BASE / "data" / "selector_estado.json"

st.set_page_config(
    page_title="PREDWEEM Zavalla Adaptativo",
    page_icon="🌾",
    layout="wide",
)
st.title("🌾 PREDWEEM Zavalla — Selector sin lag / con lag")
st.caption(
    "Modelo dual para emergencia de Lolium: el pico sin lag activa la inspección "
    "y la evidencia de campo selecciona exclusivamente una de las dos hipótesis."
)


def read_table(source) -> pd.DataFrame:
    name = str(getattr(source, "name", source)).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(source)
    return pd.read_csv(source)


@st.cache_resource
def get_ann():
    return load_ann(BASE)


with st.sidebar:
    st.header("Configuración del sitio")
    st.write(f"**{CONFIG.nombre_sitio}**")
    st.caption(f"Lat {CONFIG.latitud:.5f} · Lon {CONFIG.longitud:.5f}")
    uploaded_weather = st.file_uploader(
        "Meteorología diaria",
        type=["csv", "xlsx", "xls"],
    )
    coverage = st.slider(
        "Cobertura de rastrojo (%)",
        0,
        100,
        CONFIG.cobertura_predeterminada_pct,
        5,
    )
    wmax = st.number_input(
        "Wmax superficial (mm)",
        5.0,
        60.0,
        CONFIG.wmax_predeterminado_mm,
        0.5,
    )
    kr_exponent = st.slider(
        "Exponente Kr",
        0.0,
        2.0,
        CONFIG.exponente_kr_predeterminado,
        0.1,
    )
    lag_candidate = st.number_input(
        "Lag fijo del modelo con lag (días)",
        0,
        30,
        CONFIG.lag_candidato_dias,
        1,
    )
    st.caption(
        "El sistema no estima lags locales: selecciona entre lag 0 y este lag fijo."
    )

if uploaded_weather is not None:
    weather = read_table(uploaded_weather)
elif METEO_PATH.is_file() and METEO_PATH.stat().st_size > 40:
    weather = pd.read_csv(METEO_PATH)
else:
    weather = None

if weather is None or weather.empty:
    st.warning(
        "No existe una serie meteorológica operativa. Ejecute el workflow de "
        "actualización o cargue un archivo con Fecha, TMAX, TMIN y Prec."
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
    )
except Exception as exc:
    st.error(f"No se pudo ejecutar PREDWEEM: {exc}")
    st.stop()

stored = load_inspections(INSPECTIONS_PATH)
uploaded_inspections = st.sidebar.file_uploader(
    "Restaurar inspecciones",
    type=["csv"],
)
if uploaded_inspections is not None:
    stored = normalize_inspections(pd.read_csv(uploaded_inspections))
if "inspections" not in st.session_state:
    st.session_state.inspections = stored
if uploaded_inspections is not None:
    st.session_state.inspections = stored

inspections = normalize_inspections(st.session_state.inspections)
decision = evaluate_selector(
    result.first_peak_no_lag,
    result.first_peak_lag,
    inspections,
    lag_candidate_days=int(lag_candidate),
)
save_decision(decision, STATE_PATH)

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
    result.first_peak_lag.strftime("%d/%m/%Y")
    if result.first_peak_lag
    else "—",
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
show_no_lag, show_lag = visible_models(decision)
fig = go.Figure()
if show_no_lag:
    fig.add_trace(
        go.Scatter(
            x=plot_data["Fecha"],
            y=plot_data["EMERREL_SIN_LAG"],
            name="Sin lag",
            mode="lines",
        )
    )
if show_lag:
    fig.add_trace(
        go.Scatter(
            x=plot_data["Fecha"],
            y=plot_data["EMERREL_CON_LAG"],
            name=f"Lag fijo {lag_candidate} días",
            mode="lines",
        )
    )
if not inspections.empty:
    positive = (
        inspections["Emergencia_confirmada"]
        | (inspections["Plantas_m2"] >= CONFIG.densidad_confirmacion_pl_m2)
        | (inspections["Cuadros_positivos"] >= 2)
    )
    fig.add_trace(
        go.Scatter(
            x=inspections["Fecha"],
            y=inspections["Plantas_m2"],
            name="Campo (plantas/m²)",
            mode="markers",
            marker={
                "size": 11,
                "symbol": ["circle" if value else "x" for value in positive],
            },
            yaxis="y2",
        )
    )

if show_no_lag and show_lag:
    graph_title = "Comparación de modelos antes de la selección"
elif show_no_lag:
    graph_title = "Modelo seleccionado: sin lag"
elif show_lag:
    graph_title = f"Modelo seleccionado: lag fijo de {lag_candidate} días"
else:
    graph_title = "Sin modelo visible"

fig.update_layout(
    title=graph_title,
    xaxis_title="Fecha",
    yaxis={"title": "EMERREL"},
    yaxis2={
        "title": "Plantas/m²",
        "overlaying": "y",
        "side": "right",
        "showgrid": False,
    },
    hovermode="x unified",
    height=520,
    legend={"orientation": "h"},
)
st.plotly_chart(fig, width="stretch")

if decision.modelo_activo in {"sin_lag", "con_lag"}:
    st.info(
        "El modelo alternativo fue retirado de la gráfica porque la evidencia de "
        "campo ya produjo una selección operativa."
    )

st.subheader("Registrar inspección de campo")
with st.form("inspection_form", clear_on_submit=True):
    columns = st.columns(4)
    inspection_date = columns[0].date_input("Fecha")
    operator = columns[1].text_input("Operario")
    plants_m2 = columns[2].number_input(
        "Plantas/m²",
        min_value=0.0,
        value=0.0,
        step=0.1,
    )
    total_quadrats = columns[3].number_input(
        "Cuadros totales",
        min_value=1,
        value=10,
        step=1,
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
        [[
            pd.Timestamp(inspection_date),
            operator,
            plants_m2,
            positive_quadrats,
            total_quadrats,
            explicit_confirmation,
            notes,
        ]],
        columns=INSPECTION_COLUMNS,
    )
    st.session_state.inspections = normalize_inspections(
        pd.concat([inspections, row], ignore_index=True)
    )
    save_inspections(st.session_state.inspections, INSPECTIONS_PATH)
    st.success(
        "Inspección registrada. El selector se recalculará con la nueva evidencia."
    )
    st.rerun()

st.subheader("Historial y auditoría")
st.dataframe(inspections, width="stretch", hide_index=True)
st.download_button(
    "Descargar inspecciones CSV",
    data=inspections.to_csv(index=False).encode("utf-8"),
    file_name="PREDWEEM_Zavalla_inspecciones.csv",
    mime="text/csv",
)
st.download_button(
    "Descargar estado del selector",
    data=json.dumps(
        decision.to_dict(),
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8"),
    file_name="PREDWEEM_Zavalla_selector.json",
    mime="application/json",
)

with st.expander("Resultados diarios"):
    st.dataframe(plot_data, width="stretch", hide_index=True)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        plot_data.to_excel(writer, sheet_name="Simulacion_Diaria", index=False)
        inspections.to_excel(writer, sheet_name="Inspecciones", index=False)
        pd.DataFrame([decision.to_dict()]).to_excel(
            writer,
            sheet_name="Selector",
            index=False,
        )
    st.download_button(
        "Descargar resultados completos",
        data=buffer.getvalue(),
        file_name="PREDWEEM_Zavalla_Resultados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption(
    "El selector no estima un lag local. Si el pico sin lag no se confirma, "
    "opera con el lag fijo configurado; si tampoco se confirma esa ventana, "
    "pasa a NINGUNO_CONFIRMADO."
)

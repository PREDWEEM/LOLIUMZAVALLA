from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config_zavalla import CONFIG
from predweem_core import (
    load_ann,
    phenology_window_dates,
    simulate_dual,
)
from selector_adaptativo import (
    INSPECTION_COLUMNS,
    evaluate_selector,
    load_inspections,
    normalize_inspections,
    save_decision,
    save_inspections,
    visible_models,
)
from visualizacion_pulsos import construir_campanas_agrupadas

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


def add_phenology_window(
    figure: go.Figure,
    *,
    control_date: pd.Timestamp | None,
    limit_date: pd.Timestamp | None,
    final_date: pd.Timestamp,
    label: str,
    fillcolor: str,
) -> None:
    """Sombrea la ventana de 600–800 °Cd y marca sus límites."""
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
    limit_text = limit_date.strftime("%d/%m/%Y") if limit_date is not None else "pendiente"
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
    """Agrega la señal diaria y su envolvente de campanas agrupadas."""
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
    result.first_peak_no_lag.strftime("%d/%m/%Y") if result.first_peak_no_lag else "—",
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
show_no_lag, show_lag = visible_models(decision)
control_no_lag, limit_no_lag = phenology_window_dates(
    plot_data["Fecha"],
    plot_data["TT_DESDE_PICO_SIN_LAG"],
    CONFIG.tt_control_cd,
    CONFIG.tt_limite_cd,
)
control_lag, limit_lag = phenology_window_dates(
    plot_data["Fecha"],
    plot_data["TT_DESDE_PICO_CON_LAG"],
    CONFIG.tt_control_cd,
    CONFIG.tt_limite_cd,
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
    graph_title = "Comparación de modelos antes de la selección"
elif show_no_lag:
    graph_title = "Modelo seleccionado: sin lag"
elif show_lag:
    graph_title = f"Modelo seleccionado: lag fijo de {lag_candidate} días"
else:
    graph_title = "Sin modelo visible"

field_max = 1.0
if not inspections.empty:
    field_max = max(float(inspections["Plantas_m2"].max()), 1.0)

fig.update_layout(
    template="plotly_white",
    title={"text": graph_title, "x": 0.0, "xanchor": "left"},
    xaxis={
        "title": "Fecha",
        "showgrid": False,
        "zeroline": False,
    },
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
    "La línea fina representa EMERREL diaria. La envolvente con área coloreada "
    "agrupa activaciones cercanas y las representa como pulsos suaves en forma de campana."
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
        "El modelo alternativo fue retirado de la gráfica porque la evidencia de "
        "campo ya produjo una selección operativa. Las campanas y la banda "
        "fenológica corresponden únicamente al modelo visible."
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
    st.session_state.inspections = normalize_inspections(
        pd.concat([inspections, row], ignore_index=True)
    )
    save_inspections(st.session_state.inspections, INSPECTIONS_PATH)
    st.success(
        "Inspección registrada. El selector se recalculará con la nueva evidencia."
    )
    st.rerun()

st.subheader("Historial y auditoría")
if inspections.empty:
    st.info("Todavía no existen registros de campo.")
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
    inspection_signature = int(
        pd.util.hash_pandas_object(inspections.astype(str), index=True).sum()
    )
    selected_indices = st.multiselect(
        "Seleccionar registros de campo para borrar",
        options=list(option_labels),
        format_func=lambda value: option_labels[value],
        key=f"delete_inspection_indices_{inspection_signature}",
    )
    confirm_delete = st.checkbox(
        "Confirmo que deseo borrar los registros seleccionados",
        key=f"confirm_delete_inspections_{inspection_signature}",
    )
    delete_clicked = st.button(
        "🗑️ Borrar registros seleccionados",
        disabled=not selected_indices or not confirm_delete,
        type="secondary",
        key=f"delete_inspections_button_{inspection_signature}",
    )
    if delete_clicked:
        updated_inspections = inspections.drop(
            index=selected_indices,
            errors="ignore",
        ).reset_index(drop=True)
        st.session_state.inspections = normalize_inspections(updated_inspections)
        save_inspections(st.session_state.inspections, INSPECTIONS_PATH)
        st.success(
            f"Se borraron {len(selected_indices)} registro(s). "
            "El selector será recalculado."
        )
        st.rerun()

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
                writer,
                sheet_name="Pulsos_Agrupados",
                index=False,
            )
    st.download_button(
        "Descargar resultados completos",
        data=buffer.getvalue(),
        file_name="PREDWEEM_Zavalla_Resultados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption(
    "El selector no estima un lag local. Si los dos conteos iniciales son "
    "negativos, opera automáticamente con el lag fijo configurado; una "
    "verificación posterior permite confirmar o revisar esa hipótesis."
)

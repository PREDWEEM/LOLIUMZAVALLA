from __future__ import annotations

import io
from dataclasses import replace

import pandas as pd
import streamlit as st

from app_multisitio import (
    BASE,
    CHART_STYLES,
    CONFIG,
    DEFAULT_SITE_SLUG,
    SITES,
    build_operational_data,
    clock_figure,
    clock_state,
    emergence_figure,
    format_window,
    get_ann,
    get_site,
    ordered_sites,
    phenology_window_dates,
    resolve_weather,
    simulate_dual,
    smooth_pulses,
)


def run() -> None:
    st.set_page_config(
        page_title="PREDWEEM LOLIUM Multisitio",
        page_icon="🌾",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.25rem;
            max-width: 1520px;
        }
        [data-testid='stSidebar'] {
            background: linear-gradient(180deg,#f0fdf4 0%,#ecfdf5 52%,#f8fafc 100%);
            border-right: 1px solid #d1fae5;
        }
        [data-testid='stMetric'] {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: .75rem .9rem;
            box-shadow: 0 3px 12px rgba(15,23,42,.055);
        }
        div[data-testid='stPlotlyChart'] {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: .35rem;
            box-shadow: 0 5px 18px rgba(15,23,42,.065);
        }
        .coverage-panel {
            padding: 15px 18px;
            border-radius: 14px;
            border: 1px solid #bfdbfe;
            background: linear-gradient(90deg,#eff6ff,#ffffff);
            box-shadow: 0 4px 14px rgba(15,23,42,.05);
            min-height: 112px;
        }
        h1,h2,h3 {letter-spacing: -.02em;}
        #MainMenu,footer {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    sites = ordered_sites()
    slugs = [site.slug for site in sites]

    with st.sidebar:
        st.header("Configuración geográfica")
        slug = st.selectbox(
            "Sitio específico",
            slugs,
            index=slugs.index(DEFAULT_SITE_SLUG),
            format_func=lambda value: SITES[value].etiqueta,
            key="selected_lolium_site",
        )
        site = get_site(slug)
        st.write(f"**{site.etiqueta}**")
        st.caption(f"Lat {site.latitud:.5f} · Lon {site.longitud:.5f}")
        st.markdown(
            f"Repositorio de referencia: [`{site.repositorio}`]"
            f"({site.repository_url})"
        )
        st.success(f"Modelo automático: **{site.modelo_operativo_etiqueta}**")
        uploaded = st.file_uploader(
            f"Meteorología diaria de {site.nombre}",
            type=["csv", "xlsx", "xls"],
            key=f"weather_upload_{site.slug}",
        )
        style = st.selectbox(
            "Estilo de visualización",
            CHART_STYLES,
            index=0,
            key=f"chart_style_{site.slug}",
            help=(
                "Operativo: lectura rápida. Minimalista: máxima simplicidad. "
                "Académico: informes y publicaciones."
            ),
        )
        st.caption(
            "La cobertura de rastrojo se ajusta en la página principal. "
            "El estilo solo modifica la presentación."
        )

    config = replace(
        CONFIG,
        nombre_sitio=site.etiqueta,
        latitud=site.latitud,
        longitud=site.longitud,
        timezone=site.timezone,
    )

    st.title(f"🌾 PREDWEEM {site.nombre} — {site.modelo_operativo_etiqueta}")
    st.caption(
        "Predicción operativa de emergencia de Lolium con selección automática "
        "del modelo según la localidad."
    )

    st.subheader("🌱 Ajuste de cobertura superficial")
    coverage_column, explanation_column = st.columns([1.65, 2.35])
    with coverage_column:
        coverage = st.slider(
            "Cobertura de rastrojo (%)",
            0,
            100,
            CONFIG.cobertura_predeterminada_pct,
            5,
            key=f"coverage_{site.slug}",
            help=(
                "Única variable agronómica de ajuste visible. Modifica el "
                "coeficiente de evaporación y el microclima superficial."
            ),
        )
    with explanation_column:
        st.markdown(
            f"""
            <div class="coverage-panel">
                <b style="color:#1d4ed8;font-size:1.02rem;">
                    Cobertura seleccionada: {coverage}%
                </b><br>
                <span style="color:#475569;">
                    Este valor actualiza inmediatamente la simulación. Los demás
                    parámetros biofísicos permanecen fijos según la calibración
                    operativa de {site.nombre}.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    weather, source = resolve_weather(site, uploaded)
    st.caption(f"**Fuente meteorológica activa:** {source}")
    if weather is None or weather.empty:
        st.warning(
            f"No existe una serie meteorológica operativa para {site.etiqueta}. "
            "Ejecute el workflow diario o cargue un archivo con Fecha, TMAX, "
            "TMIN y Prec."
        )
        st.stop()

    try:
        result = simulate_dual(
            weather,
            get_ann(),
            coverage_percent=coverage,
            wmax=float(config.wmax_predeterminado_mm),
            lag_days=int(site.lag_operativo_dias),
            kr_exponent=float(config.exponente_kr_predeterminado),
            config=config,
        )
        data, model_name, peak = build_operational_data(
            result.data,
            site.modelo_operativo,
            site.lag_operativo_dias,
        )
    except Exception as exc:
        st.error(f"No se pudo ejecutar PREDWEEM para {site.nombre}: {exc}")
        st.stop()

    data["Fecha"] = pd.to_datetime(data["Fecha"])
    data["Sitio"] = site.nombre
    data["Latitud"] = site.latitud
    data["Longitud"] = site.longitud

    control, limit = phenology_window_dates(
        data["Fecha"],
        data["TT_DESDE_PICO"],
        config.tt_control_cd,
        config.tt_limite_cd,
    )
    state = clock_state(
        data,
        peak,
        pd.Timestamp.now(tz=site.timezone).tz_localize(None).normalize(),
    )

    st.markdown(
        f"""
        <div style="padding:16px 18px;border-radius:14px;border:1px solid #bbf7d0;
        background:linear-gradient(90deg,#f0fdf4,#fff);
        box-shadow:0 4px 14px rgba(15,23,42,.055)">
            <b style="color:#166534">Sitio:</b> {site.etiqueta}<br>
            <b style="color:#166534">Modelo operativo:</b> {model_name}<br>
            <b style="color:#166534">Cobertura:</b> {coverage}% ·
            <b style="color:#166534">Visualización:</b> {style}<br>
            <span style="color:#64748b">
                Selección fija por localidad; sin recuentos de campo.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    metrics = st.columns(3)
    metrics[0].metric("Cobertura de rastrojo", f"{coverage}%")
    metrics[1].metric(
        "Primer pico",
        peak.strftime("%d/%m/%Y") if peak is not None else "—",
    )
    metrics[2].metric(
        "Ventana fenológica",
        f"{control.strftime('%d/%m')}–{limit.strftime('%d/%m')}"
        if control is not None and limit is not None
        else "Pendiente",
    )

    smooth = smooth_pulses(data)
    smooth["Modelo"] = model_name
    smooth["Sitio"] = site.nombre
    figure = emergence_figure(
        data,
        smooth,
        site.nombre,
        model_name,
        style,
        peak,
        control,
        limit,
    )

    main_column, gauge_column = st.columns([3.4, 1])
    with main_column:
        st.plotly_chart(
            figure,
            width="stretch",
            config={
                "displaylogo": False,
                "responsive": True,
                "scrollZoom": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": (
                        f"PREDWEEM_{site.slug}_"
                        f"{style.lower().replace(' ', '_')}"
                    ),
                    "height": 1100,
                    "width": 2100,
                    "scale": 2,
                },
            },
        )
        st.caption(
            "La franja amarilla identifica la ventana fenológica de "
            "600–800 °Cd. El eje Y usa Log10(EMERREL + 0,01); el cursor "
            "conserva EMERREL original."
        )
        st.caption(f"Ventana fenológica: {format_window(control, limit)}")

    with gauge_column:
        st.plotly_chart(clock_figure(state), width="stretch")
        st.caption(str(state["estado"]))

    with st.expander("Resultados diarios del modelo operativo"):
        st.dataframe(data, width="stretch", hide_index=True)
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
                            site.meteo_path(BASE).relative_to(BASE)
                        ),
                        "Fuente_meteorologica_activa": source,
                        "Modelo_operativo": model_name,
                        "Lag_operativo_dias": (
                            site.lag_operativo_dias
                            if site.modelo_operativo == "con_lag"
                            else 0
                        ),
                        "Cobertura_rastrojo_pct": coverage,
                        "Estilo_grafico": style,
                        "Color_ventana_fenologica": "amarillo",
                        "Transformacion_grafica_Y": (
                            "log10(EMERREL + 0.01)"
                        ),
                        "Seleccion_automatica": True,
                        "Usa_recuento_campo": False,
                    }
                ]
            ).to_excel(writer, sheet_name="Sitio", index=False)
            data.to_excel(
                writer,
                sheet_name="Simulacion_Operativa",
                index=False,
            )
            pd.DataFrame(
                [
                    {
                        "Modelo": model_name,
                        "Fecha_primer_pico": peak,
                        "Fecha_reloj": state["fecha_hoy"],
                        "TT_actual_desde_pico_Cd": state["dga_hoy"],
                        "Fecha_pronostico_7d": state["fecha_pronostico"],
                        "TT_pronostico_7d_Cd": state["dga_7dias"],
                        "Estado_fenologico": state["estado"],
                        "Fecha_600_Cd": control,
                        "Fecha_800_Cd": limit,
                        "Cobertura_rastrojo_pct": coverage,
                    }
                ]
            ).to_excel(writer, sheet_name="Reloj_Fenologico", index=False)
            smooth.to_excel(
                writer,
                sheet_name="Pulsos_Agrupados",
                index=False,
            )

        st.download_button(
            "Descargar resultados completos",
            data=buffer.getvalue(),
            file_name=f"PREDWEEM_{site.slug}_Resultados.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    st.caption(
        "Política automática: Pergamino y Zavalla usan solamente el modelo "
        "con lag fijo; las demás localidades usan solamente el modelo sin lag."
    )

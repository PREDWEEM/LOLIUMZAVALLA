from __future__ import annotations

from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True)
class SiteCalibration:
    """Parámetros operativos reproducidos desde un repositorio geográfico."""

    slug: str
    cobertura_predeterminada_pct: int = 30
    wmax_predeterminado_mm: float = 20.0
    exponente_kr_predeterminado: float = 0.0
    latencia_jd: int = 25
    ventana_termica_dias: int = 5
    umbral_termoinhibicion_c: float = 24.0
    umbral_termoinhibicion_con_lag_c: float = 20.0
    ventana_lluvia_dias: int = 3
    umbral_choque_hidrico_mm: float = 45.0
    fin_choque_hidrico_jd: int = 110
    techo_choque_hidrico: float = 0.75
    umbral_primer_pico: float = 0.20
    lag_candidato_dias: int = 15
    repositorio_referencia: str = "PREDWEEM/LOLIUMZAVALLA"
    archivo_motor_referencia: str = "predweem_core.py"
    auditada: bool = False


# Los perfiles no auditados conservan temporalmente la calibración común del
# sistema multisitio. Bordenave y Lartigau reproducen los valores actualmente
# utilizados por sus motores geográficos originales.
_COMMON = SiteCalibration(slug="comun")
SITE_CALIBRATIONS: dict[str, SiteCalibration] = {
    "azul": SiteCalibration(slug="azul"),
    "balcarce": SiteCalibration(slug="balcarce"),
    "bordenave": SiteCalibration(
        slug="bordenave",
        cobertura_predeterminada_pct=75,
        wmax_predeterminado_mm=18.81,
        exponente_kr_predeterminado=0.0,
        latencia_jd=15,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=20.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=1.0,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/LOLIUM_BOR2026",
        archivo_motor_referencia="app_emergenciacombinado_core.py",
        auditada=True,
    ),
    "lartigau": SiteCalibration(
        slug="lartigau",
        cobertura_predeterminada_pct=75,
        wmax_predeterminado_mm=18.816,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=20.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=1.0,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/LOLIUM_LARTIGAU-2026",
        archivo_motor_referencia="app_emergencia_core.py",
        auditada=True,
    ),
    "olavarria": SiteCalibration(slug="olavarria"),
    "pergamino": SiteCalibration(slug="pergamino"),
    "san-pedro": SiteCalibration(slug="san-pedro"),
    "tres-arroyos": SiteCalibration(slug="tres-arroyos"),
    "zavalla": SiteCalibration(slug="zavalla"),
}

# Incrementar cuando cambien los valores predeterminados que deben reemplazar
# controles conservados en st.session_state de una versión anterior.
CALIBRATION_WIDGET_REVISION = 2


def get_site_calibration(slug: str | None) -> SiteCalibration:
    normalized = str(slug or "zavalla").strip().lower()
    return SITE_CALIBRATIONS.get(normalized, _COMMON)


def _active_site_slug() -> str:
    """Obtiene el sitio elegido sin acoplar el motor a Streamlit."""

    explicit = os.environ.get("PREDWEEM_ACTIVE_SITE", "").strip().lower()
    if explicit:
        return explicit

    streamlit_module = sys.modules.get("streamlit")
    if streamlit_module is not None:
        try:
            selected = streamlit_module.session_state.get(
                "selected_lolium_site",
                "zavalla",
            )
            return str(selected).strip().lower()
        except Exception:
            pass
    return "zavalla"


def _seed_streamlit_widget_defaults(
    slug: str,
    calibration: SiteCalibration,
) -> None:
    """Reemplaza una sola vez los antiguos valores genéricos de la interfaz."""

    streamlit_module = sys.modules.get("streamlit")
    if streamlit_module is None:
        return
    try:
        state = streamlit_module.session_state
        revision_key = f"calibration_widget_revision::{slug}"
        if state.get(revision_key) == CALIBRATION_WIDGET_REVISION:
            return
        state[f"coverage_{slug}"] = calibration.cobertura_predeterminada_pct
        state[f"wmax_{slug}"] = calibration.wmax_predeterminado_mm
        state[f"kr_{slug}"] = calibration.exponente_kr_predeterminado
        state[f"lag_{slug}"] = calibration.lag_candidato_dias
        state[revision_key] = CALIBRATION_WIDGET_REVISION
    except Exception:
        # Fuera de una ejecución de Streamlit no existe estado de widgets.
        return


_DYNAMIC_CALIBRATION_FIELDS = {
    "latencia_jd",
    "ventana_termica_dias",
    "umbral_termoinhibicion_c",
    "umbral_termoinhibicion_con_lag_c",
    "ventana_lluvia_dias",
    "umbral_choque_hidrico_mm",
    "fin_choque_hidrico_jd",
    "techo_choque_hidrico",
    "cobertura_predeterminada_pct",
    "wmax_predeterminado_mm",
    "exponente_kr_predeterminado",
    "umbral_primer_pico",
    "lag_candidato_dias",
}


@dataclass(frozen=True)
class ZavallaConfig:
    """Configuración común con resolución dinámica de la calibración local."""

    nombre_sitio: str = "Zavalla, Santa Fe"
    latitud: float = -33.02157
    longitud: float = -60.87930
    timezone: str = "America/Argentina/Cordoba"

    latencia_jd: int = 25
    ventana_termica_dias: int = 5
    umbral_termoinhibicion_c: float = 24.0
    umbral_termoinhibicion_con_lag_c: float = 20.0
    ventana_lluvia_dias: int = 3
    umbral_choque_hidrico_mm: float = 45.0
    fin_choque_hidrico_jd: int = 110
    techo_choque_hidrico: float = 0.75

    cobertura_predeterminada_pct: int = 30
    wmax_predeterminado_mm: float = 20.0
    exponente_kr_predeterminado: float = 0.0
    p50_hidrico: float = 0.30
    pendiente_hidrica: float = 10.0
    corte_hidrico: float = 0.20

    umbral_primer_pico: float = 0.20
    lag_candidato_dias: int = 15
    tolerancia_sin_lag_dias: int = 4
    tolerancia_lag_dias: int = 5
    densidad_confirmacion_pl_m2: float = 0.5

    t_base_c: float = 2.0
    t_optima_c: float = 20.0
    t_critica_c: float = 30.0
    tt_control_cd: float = 600.0
    tt_limite_cd: float = 800.0

    def __getattribute__(self, name: str):
        if name in _DYNAMIC_CALIBRATION_FIELDS:
            slug = _active_site_slug()
            calibration = get_site_calibration(slug)
            _seed_streamlit_widget_defaults(slug, calibration)
            return getattr(calibration, name)
        return object.__getattribute__(self, name)


CONFIG = ZavallaConfig()

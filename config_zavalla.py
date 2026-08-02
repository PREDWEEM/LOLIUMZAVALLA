from __future__ import annotations

from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True)
class SiteCalibration:
    """Perfil operativo auditado desde el motor del repositorio geográfico."""

    slug: str
    cobertura_predeterminada_pct: int
    wmax_predeterminado_mm: float
    exponente_kr_predeterminado: float
    latencia_jd: int
    ventana_termica_dias: int
    umbral_termoinhibicion_c: float
    umbral_termoinhibicion_con_lag_c: float
    ventana_lluvia_dias: int
    umbral_choque_hidrico_mm: float
    fin_choque_hidrico_jd: int
    techo_choque_hidrico: float
    umbral_primer_pico: float
    lag_candidato_dias: int
    decaimiento_activo: bool = False
    decaimiento_tau_dias: float = 1.0
    decaimiento_beta: float = 1.0
    decaimiento_intensidad: float = 0.0
    modelo_referencia_local: str = "sin_lag"
    repositorio_referencia: str = ""
    archivo_motor_referencia: str = ""


SITE_CALIBRATIONS: dict[str, SiteCalibration] = {
    "azul": SiteCalibration(
        slug="azul",
        cobertura_predeterminada_pct=10,
        wmax_predeterminado_mm=18.81,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=24.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=0.75,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/LOLIUM_AZUL2026",
        archivo_motor_referencia="app_emergenciacombinado_core.py",
    ),
    "balcarce": SiteCalibration(
        slug="balcarce",
        cobertura_predeterminada_pct=10,
        wmax_predeterminado_mm=10.0,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=24.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=1.0,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        decaimiento_activo=True,
        decaimiento_tau_dias=3.5656,
        decaimiento_beta=0.48684,
        decaimiento_intensidad=0.95,
        repositorio_referencia="PREDWEEM/LOLIUM_BAL2026",
        archivo_motor_referencia="app_emergenciacombinado_core.py",
    ),
    "bordenave": SiteCalibration(
        slug="bordenave",
        cobertura_predeterminada_pct=75,
        wmax_predeterminado_mm=18.81,
        exponente_kr_predeterminado=0.0,
        latencia_jd=15,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=24.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=1.0,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/LOLIUM_BOR2026",
        archivo_motor_referencia="app_emergenciacombinado_core.py",
    ),
    "lartigau": SiteCalibration(
        slug="lartigau",
        cobertura_predeterminada_pct=75,
        wmax_predeterminado_mm=18.816,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=24.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=1.0,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/LOLIUM_LARTIGAU-2026",
        archivo_motor_referencia="app_emergencia_core.py",
    ),
    "olavarria": SiteCalibration(
        slug="olavarria",
        cobertura_predeterminada_pct=10,
        wmax_predeterminado_mm=18.81,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=24.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=0.75,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/LOLIUM_OLAVA2026",
        archivo_motor_referencia="app_emergenciacombinado_core.py",
    ),
    "pergamino": SiteCalibration(
        slug="pergamino",
        cobertura_predeterminada_pct=80,
        wmax_predeterminado_mm=18.81,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=20.0,
        umbral_termoinhibicion_con_lag_c=20.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=0.75,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        modelo_referencia_local="con_lag",
        repositorio_referencia="PREDWEEM/LOLIUM-PERGA2026",
        archivo_motor_referencia="app_emergenciacombinado_core.py",
    ),
    "san-pedro": SiteCalibration(
        slug="san-pedro",
        cobertura_predeterminada_pct=90,
        wmax_predeterminado_mm=18.81,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=24.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=0.75,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/lolium_sanpedro2026",
        archivo_motor_referencia="app_emergencia_core.py",
    ),
    "tres-arroyos": SiteCalibration(
        slug="tres-arroyos",
        cobertura_predeterminada_pct=20,
        wmax_predeterminado_mm=18.81,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=24.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=0.75,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/loliumTA_2026",
        archivo_motor_referencia="app_emergencia_core.py",
    ),
    "zavalla": SiteCalibration(
        slug="zavalla",
        cobertura_predeterminada_pct=30,
        wmax_predeterminado_mm=20.0,
        exponente_kr_predeterminado=0.0,
        latencia_jd=25,
        ventana_termica_dias=5,
        umbral_termoinhibicion_c=24.0,
        umbral_termoinhibicion_con_lag_c=20.0,
        ventana_lluvia_dias=3,
        umbral_choque_hidrico_mm=45.0,
        fin_choque_hidrico_jd=110,
        techo_choque_hidrico=0.75,
        umbral_primer_pico=0.20,
        lag_candidato_dias=15,
        repositorio_referencia="PREDWEEM/LOLIUM_ZAVALLA2026",
        archivo_motor_referencia="predweem_core.py",
    ),
}

CALIBRATION_WIDGET_REVISION = 3


def get_site_calibration(slug: str | None) -> SiteCalibration:
    normalized = str(slug or "zavalla").strip().lower()
    try:
        return SITE_CALIBRATIONS[normalized]
    except KeyError as exc:
        raise KeyError(f"No existe calibración para el sitio: {normalized}") from exc


def _active_site_slug() -> str:
    explicit = os.environ.get("PREDWEEM_ACTIVE_SITE", "").strip().lower()
    if explicit:
        return explicit
    streamlit_module = sys.modules.get("streamlit")
    if streamlit_module is not None:
        try:
            return str(
                streamlit_module.session_state.get("selected_lolium_site", "zavalla")
            ).strip().lower()
        except Exception:
            pass
    return "zavalla"


def _seed_streamlit_widget_defaults(slug: str, profile: SiteCalibration) -> None:
    """Reemplaza una vez los valores genéricos conservados por Streamlit."""

    streamlit_module = sys.modules.get("streamlit")
    if streamlit_module is None:
        return
    try:
        state = streamlit_module.session_state
        revision_key = f"calibration_widget_revision::{slug}"
        if state.get(revision_key) == CALIBRATION_WIDGET_REVISION:
            return
        state[f"coverage_{slug}"] = profile.cobertura_predeterminada_pct
        state[f"wmax_{slug}"] = profile.wmax_predeterminado_mm
        state[f"kr_{slug}"] = profile.exponente_kr_predeterminado
        state[f"lag_{slug}"] = profile.lag_candidato_dias
        state[revision_key] = CALIBRATION_WIDGET_REVISION
    except Exception:
        return


_DYNAMIC_FIELDS = {
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
    "decaimiento_activo",
    "decaimiento_tau_dias",
    "decaimiento_beta",
    "decaimiento_intensidad",
    "modelo_referencia_local",
}


@dataclass(frozen=True)
class ZavallaConfig:
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

    decaimiento_activo: bool = False
    decaimiento_tau_dias: float = 1.0
    decaimiento_beta: float = 1.0
    decaimiento_intensidad: float = 0.0
    modelo_referencia_local: str = "sin_lag"

    t_base_c: float = 2.0
    t_optima_c: float = 20.0
    t_critica_c: float = 30.0
    tt_control_cd: float = 600.0
    tt_limite_cd: float = 800.0

    def __getattribute__(self, name: str):
        if name in _DYNAMIC_FIELDS:
            profile = get_site_calibration(_active_site_slug())
            _seed_streamlit_widget_defaults(profile.slug, profile)
            return getattr(profile, name)
        return object.__getattribute__(self, name)


CONFIG = ZavallaConfig()

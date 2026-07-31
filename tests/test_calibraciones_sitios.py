from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from config_zavalla import CONFIG, SITE_CALIBRATIONS, get_site_calibration
from predweem_core import apply_cohort_decay_weibull, simulate_dual
from sitios_lolium import SITES


class ConstantANN:
    def __init__(self, value: float = 0.8):
        self.value = float(value)

    def predict(self, values):
        return np.full(len(values), self.value, dtype=float)


EXPECTED_DEFAULTS = {
    "azul": (10, 18.81, 0.0, 25, 24.0, 0.75),
    "balcarce": (10, 10.0, 0.0, 25, 24.0, 1.0),
    "bordenave": (75, 18.81, 0.0, 15, 24.0, 1.0),
    "lartigau": (75, 18.816, 0.0, 25, 24.0, 1.0),
    "olavarria": (10, 18.81, 0.0, 25, 24.0, 0.75),
    "pergamino": (80, 18.81, 0.0, 25, 20.0, 0.75),
    "san-pedro": (90, 18.81, 0.0, 25, 24.0, 0.75),
    "tres-arroyos": (20, 18.81, 0.0, 25, 24.0, 0.75),
    "zavalla": (30, 20.0, 0.0, 25, 24.0, 0.75),
}


def test_all_geographic_sites_have_an_explicit_calibration():
    assert set(SITE_CALIBRATIONS) == set(SITES)
    for slug, expected in EXPECTED_DEFAULTS.items():
        profile = get_site_calibration(slug)
        observed = (
            profile.cobertura_predeterminada_pct,
            profile.wmax_predeterminado_mm,
            profile.exponente_kr_predeterminado,
            profile.latencia_jd,
            profile.umbral_termoinhibicion_c,
            profile.techo_choque_hidrico,
        )
        assert observed == expected
        assert profile.repositorio_referencia == SITES[slug].repositorio
        assert profile.archivo_motor_referencia.endswith(".py")


def test_balcarce_decay_parameters_match_the_validated_repository():
    profile = get_site_calibration("balcarce")
    assert profile.decaimiento_activo is True
    assert profile.decaimiento_tau_dias == pytest.approx(3.5656)
    assert profile.decaimiento_beta == pytest.approx(0.48684)
    assert profile.decaimiento_intensidad == pytest.approx(0.95)
    assert all(
        not candidate.decaimiento_activo
        for slug, candidate in SITE_CALIBRATIONS.items()
        if slug != "balcarce"
    )


def test_weibull_decay_preserves_peak_and_attenuates_later_days():
    signal = np.ones(8, dtype=float)
    decayed, factor, days = apply_cohort_decay_weibull(
        signal,
        peak_index=2,
        tau_days=3.5656,
        beta=0.48684,
        intensity=0.95,
    )

    assert factor[:3].tolist() == pytest.approx([1.0, 1.0, 1.0])
    assert decayed[2] == pytest.approx(1.0)
    assert np.all(np.diff(factor[2:]) < 0.0)
    assert decayed[-1] < decayed[3] < decayed[2]
    assert days.tolist() == pytest.approx([0, 0, 0, 1, 2, 3, 4, 5])


def _weather(periods: int = 75) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Fecha": pd.date_range("2026-01-01", periods=periods, freq="D"),
            "TMAX": np.full(periods, 18.0),
            "TMIN": np.full(periods, 8.0),
            "Prec": np.full(periods, 30.0),
        }
    )


def _site_config(monkeypatch, slug: str):
    monkeypatch.setenv("PREDWEEM_ACTIVE_SITE", slug)
    site = SITES[slug]
    return replace(
        CONFIG,
        nombre_sitio=site.etiqueta,
        latitud=site.latitud,
        longitud=site.longitud,
        timezone=site.timezone,
    )


@pytest.mark.parametrize(
    ("slug", "expected_peak"),
    [
        ("bordenave", pd.Timestamp("2026-01-16")),
        ("lartigau", pd.Timestamp("2026-01-26")),
    ],
)
def test_local_latency_controls_the_first_no_lag_peak(
    monkeypatch,
    slug,
    expected_peak,
):
    profile = get_site_calibration(slug)
    result = simulate_dual(
        _weather(),
        ConstantANN(),
        coverage_percent=profile.cobertura_predeterminada_pct,
        wmax=profile.wmax_predeterminado_mm,
        lag_days=profile.lag_candidato_dias,
        kr_exponent=profile.exponente_kr_predeterminado,
        config=_site_config(monkeypatch, slug),
    )

    assert result.first_peak_no_lag == expected_peak
    assert result.data["Umbral_Termoinhibicion_SIN_LAG_C"].iat[0] == 24.0
    assert result.data["Umbral_Termoinhibicion_CON_LAG_C"].iat[0] == 24.0


def test_balcarce_simulation_applies_decay_to_both_hypotheses(monkeypatch):
    slug = "balcarce"
    profile = get_site_calibration(slug)
    result = simulate_dual(
        _weather(),
        ConstantANN(),
        coverage_percent=profile.cobertura_predeterminada_pct,
        wmax=profile.wmax_predeterminado_mm,
        lag_days=profile.lag_candidato_dias,
        kr_exponent=profile.exponente_kr_predeterminado,
        config=_site_config(monkeypatch, slug),
    )
    data = result.data

    assert data["Decaimiento_Activo"].all()
    assert data["Decaimiento_Tau_Dias"].iat[0] == pytest.approx(3.5656)
    assert (
        data["EMERREL_SIN_LAG"]
        <= data["EMERREL_SIN_LAG_ANTES_DECAIMIENTO"] + 1e-12
    ).all()
    assert (
        data["EMERREL_CON_LAG"]
        <= data["EMERREL_CON_LAG_ANTES_DECAIMIENTO"] + 1e-12
    ).all()
    assert (data["FACTOR_DECAIMIENTO_SIN_LAG"] < 1.0).any()
    assert (data["FACTOR_DECAIMIENTO_CON_LAG"] < 1.0).any()


def test_pergamino_reference_curve_is_the_fixed_lag_hypothesis(monkeypatch):
    slug = "pergamino"
    profile = get_site_calibration(slug)
    result = simulate_dual(
        _weather(),
        ConstantANN(),
        coverage_percent=profile.cobertura_predeterminada_pct,
        wmax=profile.wmax_predeterminado_mm,
        lag_days=profile.lag_candidato_dias,
        kr_exponent=profile.exponente_kr_predeterminado,
        config=_site_config(monkeypatch, slug),
    )

    assert profile.modelo_referencia_local == "con_lag"
    assert profile.lag_candidato_dias == 15
    assert result.first_peak_lag == result.first_peak_no_lag + pd.Timedelta(days=15)
    assert result.data["Umbral_Termoinhibicion_SIN_LAG_C"].iat[0] == 20.0
    assert result.data["Umbral_Termoinhibicion_CON_LAG_C"].iat[0] == 20.0

import numpy as np
import pandas as pd

from config_zavalla import CONFIG
from predweem_core import (
    cumulative_thermal_time_from_peak,
    first_peak_index,
    phenology_window_dates,
    shift_signal,
    simulate_dual,
    surface_parameters,
)


class ConstantANN:
    def __init__(self, value: float = 0.8):
        self.value = value

    def predict(self, values):
        return np.full(len(values), self.value, dtype=float)


def test_shift_signal_delays_without_wraparound():
    values = np.array([0.0, 0.3, 0.2, 0.0])
    assert shift_signal(values, 2).tolist() == [0.0, 0.0, 0.0, 0.3]


def test_first_peak_uses_strict_threshold():
    assert first_peak_index(np.array([0.20, 0.21, 0.10]), 0.20) == 1


def test_surface_parameters_are_monotonic():
    ke0, _ = surface_parameters(0)
    ke100, _ = surface_parameters(100)
    assert ke0 > ke100


def test_phenology_window_accumulates_from_peak():
    dates = pd.date_range("2026-03-01", periods=10, freq="D")
    cumulative = cumulative_thermal_time_from_peak(
        np.full(10, 100.0),
        peak_index=2,
    )

    assert np.isnan(cumulative[0])
    assert np.isnan(cumulative[1])
    assert cumulative[2] == 100.0

    control_date, limit_date = phenology_window_dates(
        dates,
        cumulative,
        control_cd=600.0,
        limit_cd=800.0,
    )
    assert control_date == pd.Timestamp("2026-03-08")
    assert limit_date == pd.Timestamp("2026-03-10")


def test_lag_model_uses_20c_termoinhibition_independently():
    dates = pd.date_range("2026-01-01", periods=60, freq="D")
    weather = pd.DataFrame(
        {
            "Fecha": dates,
            "TMAX": 24.0,
            "TMIN": 20.0,
            "Prec": 20.0,
        }
    )

    result = simulate_dual(
        weather,
        ConstantANN(),
        coverage_percent=30,
        wmax=10.0,
        lag_days=15,
    )

    assert CONFIG.umbral_termoinhibicion_c == 24.0
    assert CONFIG.umbral_termoinhibicion_con_lag_c == 20.0
    assert not result.data["Termoinhibida_SIN_LAG"].any()
    assert result.data["Termoinhibida_CON_LAG"].all()
    assert result.first_peak_no_lag is not None
    assert result.first_peak_lag is None
    assert result.data["EMERREL_SIN_LAG"].max() > 0.20
    assert result.data["EMERREL_CON_LAG"].max() == 0.0

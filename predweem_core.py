from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from config_zavalla import CONFIG, ZavallaConfig


REQUIRED_MODEL_FILES = ("IW.npy", "bias_IW.npy", "LW.npy", "bias_out.npy")


class PracticalANNModel:
    def __init__(self, iw: np.ndarray, bias_iw: np.ndarray, lw: np.ndarray, bias_out: np.ndarray):
        self.iw = np.asarray(iw, dtype=float)
        self.bias_iw = np.asarray(bias_iw, dtype=float)
        self.lw = np.asarray(lw, dtype=float)
        self.bias_out = np.asarray(bias_out, dtype=float).reshape(-1)
        self.input_min = np.array([1.0, 0.0, -7.0, 0.0])
        self.input_max = np.array([300.0, 41.0, 25.5, 84.0])

    def predict(self, values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        normalized = 2.0 * (values - self.input_min) / (self.input_max - self.input_min) - 1.0
        hidden = np.tanh(normalized @ self.iw + self.bias_iw)
        linear = (hidden @ self.lw.T).reshape(-1)
        bias = float(self.bias_out[0]) if self.bias_out.size else 0.0
        return np.clip((np.tanh(linear + bias) + 1.0) / 2.0, 0.0, 1.0)


def load_ann(base: str | Path = ".") -> PracticalANNModel:
    base_path = Path(base)
    missing = [name for name in REQUIRED_MODEL_FILES if not (base_path / name).is_file()]
    if missing:
        raise FileNotFoundError("Faltan activos ANN: " + ", ".join(missing))
    return PracticalANNModel(
        np.load(base_path / "IW.npy"),
        np.load(base_path / "bias_IW.npy"),
        np.load(base_path / "LW.npy"),
        np.load(base_path / "bias_out.npy"),
    )


def canonicalize_weather(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()
    data.columns = [str(c).upper().strip() for c in data.columns]
    data = data.rename(columns={"FECHA": "Fecha", "DATE": "Fecha", "DATETIME": "Fecha", "PREC": "Prec", "PRECIPITACION": "Prec", "PRECIPITACIÓN": "Prec", "LLUVIA": "Prec"})
    required = ["Fecha", "TMAX", "TMIN", "Prec"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError("Faltan columnas meteorológicas: " + ", ".join(missing))
    data["Fecha"] = pd.to_datetime(data["Fecha"], errors="coerce").dt.normalize()
    for column in ("TMAX", "TMIN", "Prec"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=required).sort_values("Fecha").drop_duplicates("Fecha", keep="last").reset_index(drop=True)
    if data.empty:
        raise ValueError("No hay datos meteorológicos válidos.")
    if (data["TMAX"] < data["TMIN"]).any():
        raise ValueError("Se detectó TMAX menor que TMIN.")
    if (data["Prec"] < 0).any():
        raise ValueError("Se detectó precipitación negativa.")
    expected = pd.date_range(data["Fecha"].min(), data["Fecha"].max(), freq="D")
    missing_dates = expected.difference(pd.DatetimeIndex(data["Fecha"]))
    if len(missing_dates):
        preview = ", ".join(ts.strftime("%Y-%m-%d") for ts in missing_dates[:8])
        raise ValueError(f"La meteorología no es continua. Fechas faltantes: {preview}")
    return data


def surface_parameters(coverage_percent: float) -> tuple[float, float]:
    coverage = float(np.clip(coverage_percent, 0.0, 100.0))
    points = [0.0, 30.0, 70.0, 100.0]
    ke = float(np.interp(coverage, points, [0.85, 0.50, 0.25, 0.10]))
    thermal_modulator = float(np.interp(coverage, points, [0.95, 0.90, 0.85, 0.80]))
    return ke, thermal_modulator


def calculate_et0_hargreaves(julian_day: Iterable[float], tmax: Iterable[float], tmin: Iterable[float], latitude: float) -> np.ndarray:
    jd = np.asarray(julian_day, dtype=float)
    tx = np.asarray(tmax, dtype=float)
    tn = np.asarray(tmin, dtype=float)
    lat_rad = np.radians(float(latitude))
    dr = 1.0 + 0.033 * np.cos(2.0 * np.pi / 365.0 * jd)
    dec = 0.409 * np.sin(2.0 * np.pi / 365.0 * jd - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat_rad) * np.tan(dec), -1.0, 1.0))
    ra = (24.0 * 60.0 / np.pi) * 0.0820 * dr * (ws * np.sin(lat_rad) * np.sin(dec) + np.cos(lat_rad) * np.cos(dec) * np.sin(ws))
    ra_mm = ra / 2.45
    tmean = (tx + tn) / 2.0
    trange = np.maximum(tx - tn, 0.0)
    return np.maximum(0.0023 * ra_mm * (tmean + 17.8) * np.sqrt(trange), 0.0)


def surface_water_balance(precipitation: Iterable[float], et0: Iterable[float], wmax: float, ke: float, kr_exponent: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    prec = np.asarray(precipitation, dtype=float)
    et = np.asarray(et0, dtype=float)
    if float(wmax) <= 0:
        raise ValueError("Wmax debe ser mayor que cero.")
    water = np.zeros(len(prec), dtype=float)
    kr_daily = np.ones(len(prec), dtype=float)
    if len(water) == 0:
        return water, kr_daily
    water[0] = float(wmax) / 2.0
    exponent = max(float(kr_exponent), 0.0)
    for i in range(1, len(water)):
        relative = float(np.clip(water[i - 1] / float(wmax), 0.0, 1.0))
        kr = 1.0 if exponent == 0.0 else relative**exponent
        kr_daily[i] = kr
        evaporation = et[i] * float(ke) * kr
        water[i] = np.clip(water[i - 1] + prec[i] - evaporation, 0.0, float(wmax))
    return water, kr_daily


def thermal_time_scalar(t: float, base: float, optimum: float, critical: float) -> float:
    if t <= base:
        return 0.0
    if t <= optimum:
        return t - base
    if t < critical:
        return (t - base) * ((critical - t) / (critical - optimum))
    return 0.0


def shift_signal(values: np.ndarray, lag_days: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    shifted = np.zeros_like(values)
    if lag_days == 0:
        return values.copy()
    if lag_days > 0:
        shifted[lag_days:] = values[:-lag_days]
    else:
        k = abs(lag_days)
        shifted[:-k] = values[k:]
    return shifted


def first_peak_index(values: np.ndarray, threshold: float) -> int | None:
    candidates = np.flatnonzero(np.asarray(values, dtype=float) > float(threshold))
    return int(candidates[0]) if candidates.size else None


@dataclass
class SimulationResult:
    data: pd.DataFrame
    first_peak_no_lag: pd.Timestamp | None
    first_peak_lag: pd.Timestamp | None
    ke: float
    thermal_modulator: float


def simulate_dual(raw_weather: pd.DataFrame, ann: PracticalANNModel, *, coverage_percent: float, wmax: float, lag_days: int, kr_exponent: float = 0.0, config: ZavallaConfig = CONFIG) -> SimulationResult:
    data = canonicalize_weather(raw_weather)
    data["Julian_days"] = data["Fecha"].dt.dayofyear
    data["Tmedia_aire"] = (data["TMAX"] + data["TMIN"]) / 2.0
    ke, thermal_modulator = surface_parameters(coverage_percent)
    data["Cobertura_Rastrojo"] = float(coverage_percent)
    data["Ke_Suelo"] = ke
    data["Exponente_Kr"] = float(kr_exponent)
    inputs = data[["Julian_days", "TMAX", "TMIN", "Prec"]].to_numpy(float)
    raw_ann = ann.predict(inputs)
    data["EMERREL_RAW_ANN"] = raw_ann
    emer = raw_ann.copy()
    data["Prec_3d"] = data["Prec"].rolling(config.ventana_lluvia_dias, min_periods=1).sum()
    hydric_shock = (data["Julian_days"] > config.latencia_jd) & (data["Julian_days"] <= config.fin_choque_hidrico_jd) & (data["Prec_3d"] >= config.umbral_choque_hidrico_mm)
    emer[hydric_shock.to_numpy()] = np.maximum(emer[hydric_shock.to_numpy()], config.techo_choque_hidrico)
    data["Choque_Hidrico"] = hydric_shock
    data["ET0"] = calculate_et0_hargreaves(data["Julian_days"], data["TMAX"], data["TMIN"], config.latitud)
    water, kr_daily = surface_water_balance(data["Prec"], data["ET0"], wmax, ke, kr_exponent)
    data["W_superficial"] = water
    data["Kr_Diario"] = kr_daily
    relative_water = water / max(float(wmax), 1e-12)
    data["Humedad_Relativa"] = relative_water
    hydric_factor = 1.0 / (1.0 + np.exp(-config.pendiente_hidrica * (relative_water - config.p50_hidrico)))
    data["Hydric_Factor"] = hydric_factor
    emer *= hydric_factor
    emer[relative_water < config.corte_hidrico] = 0.0
    recharge = (data["Prec"] >= float(wmax)).cummax().to_numpy()
    data["Lluvia_Recarga"] = recharge
    emer[~recharge] = 0.0
    data["Tmedia_5d"] = data["Tmedia_aire"].rolling(config.ventana_termica_dias, min_periods=1).mean()
    thermoinhibited = data["Tmedia_5d"] >= config.umbral_termoinhibicion_c
    data["Termoinhibida"] = thermoinhibited
    emer[thermoinhibited.to_numpy()] = 0.0
    emer[(data["Julian_days"] <= config.latencia_jd).to_numpy()] = 0.0
    emer = np.clip(emer, 0.0, 1.0)
    idx0 = first_peak_index(emer, config.umbral_primer_pico)
    if idx0 is not None:
        emer[:idx0] = 0.0
    else:
        emer[:] = 0.0
    emer_lag = shift_signal(emer, int(lag_days))
    idx_lag = first_peak_index(emer_lag, config.umbral_primer_pico)
    if idx_lag is not None:
        emer_lag[:idx_lag] = 0.0
    data["EMERREL_SIN_LAG"] = emer
    data["EMERREL_CON_LAG"] = emer_lag
    data["EMERAC_SIN_LAG"] = np.cumsum(emer)
    data["EMERAC_CON_LAG"] = np.cumsum(emer_lag)
    data["GD_Tb2"] = [thermal_time_scalar(t, config.t_base_c, config.t_optima_c, config.t_critica_c) for t in data["Tmedia_aire"]]
    data["TT_ACUM"] = data["GD_Tb2"].cumsum()
    peak0 = pd.Timestamp(data.loc[idx0, "Fecha"]) if idx0 is not None else None
    peak_lag = pd.Timestamp(data.loc[idx_lag, "Fecha"]) if idx_lag is not None else None
    return SimulationResult(data, peak0, peak_lag, ke, thermal_modulator)

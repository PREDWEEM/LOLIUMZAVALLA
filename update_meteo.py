from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import tempfile

import pandas as pd
import requests

from config_zavalla import CONFIG

OUTPUT = Path("meteo_daily.csv")
STATE = Path("data/estado_actualizacion_meteo.json")
START_DATE = date(2026, 1, 1)
FORECAST_DAYS = 8
TIMEOUT = 90
COLUMNS = ["Fecha", "TMAX", "TMIN", "Prec", "Fuente", "TipoDato", "Emision"]


def get_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=TIMEOUT)
    print("URL:", response.url)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload.get("reason", str(payload)))
    return payload


def daily_frame(payload: dict, source: str, data_type: str, emission: str) -> pd.DataFrame:
    daily = payload.get("daily") or {}
    required = ["time", "temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
    missing = [key for key in required if key not in daily]
    if missing:
        raise RuntimeError("Respuesta incompleta: " + ", ".join(missing))
    frame = pd.DataFrame({"Fecha": pd.to_datetime(daily["time"], errors="coerce"), "TMAX": pd.to_numeric(daily["temperature_2m_max"], errors="coerce"), "TMIN": pd.to_numeric(daily["temperature_2m_min"], errors="coerce"), "Prec": pd.to_numeric(daily["precipitation_sum"], errors="coerce")})
    frame["Fuente"] = source
    frame["TipoDato"] = data_type
    frame["Emision"] = emission
    if frame[["Fecha", "TMAX", "TMIN", "Prec"]].isna().any().any():
        raise RuntimeError(f"{source} devolvió valores críticos nulos.")
    return frame[COLUMNS]


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().sort_values("Fecha").drop_duplicates("Fecha", keep="last").reset_index(drop=True)
    if data.empty:
        raise RuntimeError("La serie meteorológica quedó vacía.")
    if (data["TMAX"] < data["TMIN"]).any():
        raise RuntimeError("TMAX menor que TMIN.")
    if (data["Prec"] < 0).any():
        raise RuntimeError("Precipitación negativa.")
    expected = pd.date_range(data["Fecha"].min(), data["Fecha"].max(), freq="D")
    missing = expected.difference(pd.DatetimeIndex(data["Fecha"]))
    if len(missing):
        raise RuntimeError("Fechas faltantes: " + ", ".join(ts.strftime("%Y-%m-%d") for ts in missing[:10]))
    return data


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, dir=path.parent, encoding="utf-8", newline="") as handle:
        temporary = Path(handle.name)
        frame.to_csv(handle, index=False, date_format="%Y-%m-%d")
    os.replace(temporary, path)


def main() -> None:
    now = datetime.now(ZoneInfo(CONFIG.timezone))
    today = now.date()
    emission = now.isoformat(timespec="seconds")
    yesterday = today - timedelta(days=1)
    historical = pd.DataFrame(columns=COLUMNS)
    if yesterday >= START_DATE:
        payload = get_json("https://archive-api.open-meteo.com/v1/archive", {"latitude": CONFIG.latitud, "longitude": CONFIG.longitud, "start_date": START_DATE.isoformat(), "end_date": yesterday.isoformat(), "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum", "models": "ecmwf_ifs", "timezone": CONFIG.timezone, "temperature_unit": "celsius", "precipitation_unit": "mm", "cell_selection": "land"})
        historical = daily_frame(payload, "OPEN_METEO_ECMWF_IFS_ARCHIVE", "Historico_modelo", emission)
    forecast_payload = get_json("https://api.open-meteo.com/v1/forecast", {"latitude": CONFIG.latitud, "longitude": CONFIG.longitud, "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum", "models": "ecmwf_ifs", "forecast_days": FORECAST_DAYS, "timezone": CONFIG.timezone, "temperature_unit": "celsius", "precipitation_unit": "mm", "cell_selection": "land"})
    forecast = daily_frame(forecast_payload, "OPEN_METEO_ECMWF_IFS_FORECAST", "Pronostico", emission)
    forecast = forecast[forecast["Fecha"].dt.date >= today]
    combined = validate(pd.concat([historical, forecast], ignore_index=True))
    atomic_csv(combined, OUTPUT)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"actualizado": emission, "sitio": CONFIG.nombre_sitio, "latitud": CONFIG.latitud, "longitud": CONFIG.longitud, "inicio": combined["Fecha"].min().date().isoformat(), "fin": combined["Fecha"].max().date().isoformat(), "filas": int(len(combined)), "fuentes": combined.groupby(["Fuente", "TipoDato"]).size().astype(int).to_dict().__str__()}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(combined.tail(12).to_string(index=False))


if __name__ == "__main__":
    main()

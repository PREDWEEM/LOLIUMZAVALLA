from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import tempfile
import time

import pandas as pd
import requests

from sitios_lolium import DEFAULT_SITE_SLUG, LoliumSite, ordered_sites

LEGACY_OUTPUT = Path("meteo_daily.csv")
STATE = Path("data/estado_actualizacion_meteo.json")
START_DATE = date(2026, 1, 1)
FORECAST_DAYS = 8
FORECAST_PAST_DAYS = 2
TIMEOUT = 90
COLUMNS = ["Fecha", "TMAX", "TMIN", "Prec", "Fuente", "TipoDato", "Emision"]


def get_json(url: str, params: dict) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            print("URL:", response.url)
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(payload.get("reason", str(payload)))
            return payload
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(3 * attempt)
    raise RuntimeError(f"No fue posible consultar {url}") from last_error


def daily_frame(
    payload: dict,
    source: str,
    data_type: str,
    emission: str,
) -> pd.DataFrame:
    daily = payload.get("daily") or {}
    required = [
        "time",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    ]
    missing = [key for key in required if key not in daily]
    if missing:
        raise RuntimeError("Respuesta incompleta: " + ", ".join(missing))

    frame = pd.DataFrame(
        {
            "Fecha": pd.to_datetime(daily["time"], errors="coerce"),
            "TMAX": pd.to_numeric(
                daily["temperature_2m_max"], errors="coerce"
            ),
            "TMIN": pd.to_numeric(
                daily["temperature_2m_min"], errors="coerce"
            ),
            "Prec": pd.to_numeric(
                daily["precipitation_sum"], errors="coerce"
            ),
        }
    )
    frame["Fuente"] = source
    frame["TipoDato"] = data_type
    frame["Emision"] = emission
    if frame[["Fecha", "TMAX", "TMIN", "Prec"]].isna().any().any():
        raise RuntimeError(f"{source} devolvió valores críticos nulos.")
    return frame[COLUMNS]


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    data = (
        frame.copy()
        .sort_values("Fecha")
        .drop_duplicates("Fecha", keep="last")
        .reset_index(drop=True)
    )
    if data.empty:
        raise RuntimeError("La serie meteorológica quedó vacía.")
    if (data["TMAX"] < data["TMIN"]).any():
        raise RuntimeError("TMAX menor que TMIN.")
    if (data["Prec"] < 0).any():
        raise RuntimeError("Precipitación negativa.")
    expected = pd.date_range(data["Fecha"].min(), data["Fecha"].max(), freq="D")
    missing = expected.difference(pd.DatetimeIndex(data["Fecha"]))
    if len(missing):
        raise RuntimeError(
            "Fechas faltantes: "
            + ", ".join(ts.strftime("%Y-%m-%d") for ts in missing[:10])
        )
    return data


def combine_historical_and_forecast(
    historical: pd.DataFrame,
    forecast_with_recent_days: pd.DataFrame,
    today: date,
) -> pd.DataFrame:
    """Une bloques sin permitir un hueco entre ayer y el pronóstico.

    La Forecast API se consulta con ``past_days`` para que el día local actual
    quede incluido aun cuando la ventana predeterminada del modelo comience al
    día siguiente. El histórico se conserva solo hasta ayer y el bloque de
    pronóstico se utiliza desde hoy.
    """
    historical_block = historical.copy()
    forecast_block = forecast_with_recent_days.copy()

    if not historical_block.empty:
        historical_block = historical_block[
            historical_block["Fecha"].dt.date < today
        ]
    forecast_block = forecast_block[
        forecast_block["Fecha"].dt.date >= today
    ]

    available_dates = set(forecast_block["Fecha"].dt.date)
    if today not in available_dates:
        first_available = (
            forecast_block["Fecha"].min().date().isoformat()
            if not forecast_block.empty
            else "sin fechas"
        )
        raise RuntimeError(
            "Open-Meteo no devolvió el día actual "
            f"{today.isoformat()} ni siquiera usando past_days="
            f"{FORECAST_PAST_DAYS}. Primera fecha disponible: "
            f"{first_available}."
        )

    return validate(
        pd.concat([historical_block, forecast_block], ignore_index=True)
    )


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".csv",
        delete=False,
        dir=path.parent,
        encoding="utf-8",
        newline="",
    ) as handle:
        temporary = Path(handle.name)
        frame.to_csv(handle, index=False, date_format="%Y-%m-%d")
    os.replace(temporary, path)


def atomic_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        dir=path.parent,
        encoding="utf-8",
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(temporary, path)


def fetch_site_weather(site: LoliumSite) -> tuple[pd.DataFrame, str]:
    now = datetime.now(ZoneInfo(site.timezone))
    today = now.date()
    emission = now.isoformat(timespec="seconds")
    yesterday = today - timedelta(days=1)

    historical = pd.DataFrame(columns=COLUMNS)
    if yesterday >= START_DATE:
        payload = get_json(
            "https://archive-api.open-meteo.com/v1/archive",
            {
                "latitude": site.latitud,
                "longitude": site.longitud,
                "start_date": START_DATE.isoformat(),
                "end_date": yesterday.isoformat(),
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum"
                ),
                "models": "ecmwf_ifs",
                "timezone": site.timezone,
                "temperature_unit": "celsius",
                "precipitation_unit": "mm",
                "cell_selection": "land",
            },
        )
        historical = daily_frame(
            payload,
            "OPEN_METEO_ECMWF_IFS_ARCHIVE",
            "Historico_modelo",
            emission,
        )

    forecast_payload = get_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": site.latitud,
            "longitude": site.longitud,
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_sum"
            ),
            "models": "ecmwf_ifs",
            "forecast_days": FORECAST_DAYS,
            "past_days": FORECAST_PAST_DAYS,
            "timezone": site.timezone,
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
            "cell_selection": "land",
        },
    )
    forecast = daily_frame(
        forecast_payload,
        "OPEN_METEO_ECMWF_IFS_FORECAST",
        "Pronostico",
        emission,
    )
    combined = combine_historical_and_forecast(historical, forecast, today)
    return combined, emission


def source_summary(frame: pd.DataFrame) -> list[dict]:
    grouped = frame.groupby(["Fuente", "TipoDato"]).size()
    return [
        {
            "fuente": source,
            "tipo": data_type,
            "filas": int(count),
        }
        for (source, data_type), count in grouped.items()
    ]


def main() -> None:
    # Primero se descargan y validan todos los sitios. Solo después se escriben
    # archivos, evitando una actualización parcial cuando falla una localidad.
    downloaded: dict[str, tuple[LoliumSite, pd.DataFrame, str]] = {}
    for site in ordered_sites():
        print(f"\n=== {site.etiqueta} ===")
        frame, emission = fetch_site_weather(site)
        downloaded[site.slug] = (site, frame, emission)
        print(frame.tail(3).to_string(index=False))

    state_sites: dict[str, dict] = {}
    for slug, (site, frame, emission) in downloaded.items():
        output = site.meteo_path(Path("."))
        atomic_csv(frame, output)
        if slug == DEFAULT_SITE_SLUG:
            atomic_csv(frame, LEGACY_OUTPUT)
        state_sites[slug] = {
            "sitio": site.etiqueta,
            "repositorio": site.repositorio,
            "latitud": site.latitud,
            "longitud": site.longitud,
            "timezone": site.timezone,
            "archivo": output.as_posix(),
            "actualizado": emission,
            "inicio": frame["Fecha"].min().date().isoformat(),
            "fin": frame["Fecha"].max().date().isoformat(),
            "filas": int(len(frame)),
            "fuentes": source_summary(frame),
        }

    atomic_json(
        {
            "modo": "multisitio",
            "sitio_predeterminado": DEFAULT_SITE_SLUG,
            "cantidad_sitios": len(state_sites),
            "sitios": state_sites,
        },
        STATE,
    )
    print(f"\nActualización completa: {len(state_sites)} sitios.")


if __name__ == "__main__":
    main()

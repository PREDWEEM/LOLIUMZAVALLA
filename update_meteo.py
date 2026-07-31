from __future__ import annotations

from datetime import date, datetime, timedelta
from io import StringIO
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
COLUMNS = [
    "Fecha",
    "TMAX",
    "TMIN",
    "Prec",
    "Fuente",
    "TipoDato",
    "CalidadDato",
    "Emision",
]

FALLBACK_SOURCE = "OPEN_METEO_ECMWF_IFS_ARCHIVE_FALLBACK"


def request_headers() -> dict[str, str]:
    """Permite leer repositorios privados mediante un token opcional."""
    token = os.environ.get("PREDWEEM_REPOS_TOKEN", "").strip()
    if not token:
        return {}
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
    }


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


def get_text(url: str) -> str:
    """Descarga un meteo_daily.csv desde el repositorio geográfico."""
    last_error: Exception | None = None
    headers = request_headers()
    for attempt in range(1, 4):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=TIMEOUT,
            )
            print("URL meteo_daily del repositorio:", response.url)
            response.raise_for_status()
            if not response.text.strip():
                raise RuntimeError("La respuesta CSV está vacía.")
            return response.text
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(3 * attempt)
    raise RuntimeError(
        f"No fue posible descargar meteo_daily.csv desde {url}"
    ) from last_error


def daily_frame(
    payload: dict,
    source: str,
    data_type: str,
    quality: str,
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
    frame["CalidadDato"] = quality
    frame["Emision"] = emission
    if frame[["Fecha", "TMAX", "TMIN", "Prec"]].isna().any().any():
        raise RuntimeError(f"{source} devolvió valores críticos nulos.")
    return frame[COLUMNS]


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    for column in COLUMNS:
        if column not in data.columns:
            data[column] = ""
    data = (
        data[COLUMNS]
        .sort_values("Fecha")
        .drop_duplicates("Fecha", keep="last")
        .reset_index(drop=True)
    )
    if data.empty:
        raise RuntimeError("La serie meteorológica quedó vacía.")
    if data[["Fecha", "TMAX", "TMIN", "Prec"]].isna().any().any():
        raise RuntimeError("La serie contiene fechas o variables críticas nulas.")
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


def normalized_column_key(name: object) -> str:
    """Uniforma encabezados como TipoDato, TIPO o FECHA_EMISION."""
    return "".join(character for character in str(name).upper() if character.isalnum())


def canonicalize_repository_history(
    raw: pd.DataFrame,
    *,
    site: LoliumSite,
    emission: str,
    end_date: date,
) -> pd.DataFrame:
    """Normaliza meteo_daily.csv del repositorio y conserva su trazabilidad."""
    data = raw.copy()
    aliases = {
        "FECHA": "Fecha",
        "TMAX": "TMAX",
        "TMIN": "TMIN",
        "PREC": "Prec",
        "PRECIPITACION": "Prec",
        "FUENTE": "Fuente",
        "TIPODATO": "TipoDato",
        "TIPO": "TipoDato",
        "CALIDADDATO": "CalidadDato",
        "CALIDAD": "CalidadDato",
        "EMISION": "Emision",
        "EMISIONUTC": "Emision",
        "FECHAEMISION": "Emision",
    }
    rename = {}
    for column in data.columns:
        key = normalized_column_key(column)
        if key in aliases:
            rename[column] = aliases[key]
    data = data.rename(columns=rename)

    required = ["Fecha", "TMAX", "TMIN", "Prec"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise RuntimeError(
            f"{site.nombre}: {site.repositorio}/{site.archivo_meteo} no contiene "
            + ", ".join(missing)
        )

    if "Fuente" not in data.columns:
        data["Fuente"] = f"REPOSITORIO_{site.slug.upper().replace('-', '_')}"
    if "TipoDato" not in data.columns:
        data["TipoDato"] = "Historico_repositorio"
    if "CalidadDato" not in data.columns:
        data["CalidadDato"] = "Calidad_origen_no_declarada"
    if "Emision" not in data.columns:
        data["Emision"] = emission

    data["Fecha"] = pd.to_datetime(data["Fecha"], errors="coerce").dt.normalize()
    for column in ("TMAX", "TMIN", "Prec"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["Fuente"] = data["Fuente"].fillna(
        f"REPOSITORIO_{site.slug.upper().replace('-', '_')}"
    ).astype(str)
    data["TipoDato"] = data["TipoDato"].fillna(
        "Historico_repositorio"
    ).astype(str)
    data["CalidadDato"] = data["CalidadDato"].fillna(
        "Calidad_origen_no_declarada"
    ).astype(str)
    data["Emision"] = data["Emision"].fillna(emission).astype(str)

    start_timestamp = pd.Timestamp(START_DATE)
    end_timestamp = pd.Timestamp(end_date)
    data = data.loc[
        data["Fecha"].between(start_timestamp, end_timestamp, inclusive="both")
    ].copy()
    data = (
        data.sort_values("Fecha")
        .drop_duplicates("Fecha", keep="last")
        .reset_index(drop=True)
    )

    if data.empty:
        raise RuntimeError(
            f"{site.nombre}: {site.repositorio}/{site.archivo_meteo} "
            f"no aportó histórico hasta {end_date.isoformat()}."
        )
    if data[["Fecha", "TMAX", "TMIN", "Prec"]].isna().any().any():
        raise RuntimeError(
            f"{site.nombre}: meteo_daily.csv contiene valores críticos nulos."
        )
    if (data["TMAX"] < data["TMIN"]).any():
        raise RuntimeError(
            f"{site.nombre}: meteo_daily.csv contiene TMAX menor que TMIN."
        )
    if (data["Prec"] < 0).any():
        raise RuntimeError(
            f"{site.nombre}: meteo_daily.csv contiene precipitación negativa."
        )
    if site.usa_siga_historico and not data["Fuente"].str.contains(
        "SIGA", case=False
    ).any():
        raise RuntimeError(
            f"{site.nombre}: no se encontró ninguna observación SIGA en "
            f"{site.repositorio}/{site.archivo_meteo}."
        )
    return data[COLUMNS]


def merge_repository_priority_history(
    model_history: pd.DataFrame,
    repository_history: pd.DataFrame,
) -> pd.DataFrame:
    """Completa huecos con modelo y prioriza cada fecha del repositorio."""
    fallback = model_history.copy()
    fallback["Fuente"] = FALLBACK_SOURCE
    fallback["TipoDato"] = "Provisional"
    fallback["CalidadDato"] = "Provisional_hueco_repositorio"

    # Las filas del repositorio se agregan al final y ganan en fechas duplicadas.
    combined = pd.concat([fallback, repository_history], ignore_index=True)
    return validate(combined)


def merge_siga_priority_history(
    model_history: pd.DataFrame,
    repository_history: pd.DataFrame,
) -> pd.DataFrame:
    """Alias compatible con versiones anteriores."""
    return merge_repository_priority_history(model_history, repository_history)


def fetch_open_meteo_history(
    site: LoliumSite,
    *,
    emission: str,
    end_date: date,
) -> pd.DataFrame:
    if end_date < START_DATE:
        return pd.DataFrame(columns=COLUMNS)
    payload = get_json(
        "https://archive-api.open-meteo.com/v1/archive",
        {
            "latitude": site.latitud,
            "longitude": site.longitud,
            "start_date": START_DATE.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_sum"
            ),
            "models": "ecmwf_ifs",
            "timezone": site.timezone,
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
            "cell_selection": "land",
        },
    )
    return daily_frame(
        payload,
        "OPEN_METEO_ECMWF_IFS_ARCHIVE",
        "Historico_modelo",
        "Historico_modelo_grilla",
        emission,
    )


def fetch_repository_history(
    site: LoliumSite,
    *,
    emission: str,
    end_date: date,
) -> pd.DataFrame:
    text = get_text(site.raw_meteo_url)
    try:
        raw = pd.read_csv(StringIO(text))
    except Exception as exc:
        raise RuntimeError(
            f"{site.nombre}: no fue posible interpretar "
            f"{site.repositorio}/{site.archivo_meteo}."
        ) from exc
    return canonicalize_repository_history(
        raw,
        site=site,
        emission=emission,
        end_date=end_date,
    )


def fetch_repository_siga_history(
    site: LoliumSite,
    *,
    emission: str,
    end_date: date,
) -> pd.DataFrame:
    """Alias compatible con versiones anteriores."""
    return fetch_repository_history(
        site,
        emission=emission,
        end_date=end_date,
    )


def build_historical_block(
    site: LoliumSite,
    *,
    emission: str,
    end_date: date,
) -> pd.DataFrame:
    """Construye el histórico para cualquier sitio desde su repositorio."""
    model_history = fetch_open_meteo_history(
        site,
        emission=emission,
        end_date=end_date,
    )
    repository_history = fetch_repository_history(
        site,
        emission=emission,
        end_date=end_date,
    )
    merged = merge_repository_priority_history(
        model_history,
        repository_history,
    )

    repository_dates = set(repository_history["Fecha"])
    repository_rows = int(merged["Fecha"].isin(repository_dates).sum())
    fallback_rows = int((merged["Fuente"] == FALLBACK_SOURCE).sum())
    siga_rows = int(
        merged["Fuente"].astype(str).str.contains("SIGA", case=False).sum()
    )
    print(
        f"{site.nombre}: histórico desde {site.repositorio}/"
        f"{site.archivo_meteo} = {repository_rows} filas; "
        f"respaldo Open-Meteo = {fallback_rows} filas; "
        f"SIGA = {siga_rows} filas."
    )
    return merged


def combine_historical_and_forecast(
    historical: pd.DataFrame,
    forecast_with_recent_days: pd.DataFrame,
    today: date,
) -> pd.DataFrame:
    """Une bloques sin permitir un hueco entre ayer y el pronóstico."""
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
        historical = build_historical_block(
            site,
            emission=emission,
            end_date=yesterday,
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
        "Pronostico_operativo",
        emission,
    )
    combined = combine_historical_and_forecast(historical, forecast, today)
    return combined, emission


def source_summary(frame: pd.DataFrame) -> list[dict]:
    grouped = frame.groupby(["Fuente", "TipoDato", "CalidadDato"]).size()
    return [
        {
            "fuente": source,
            "tipo": data_type,
            "calidad": quality,
            "filas": int(count),
        }
        for (source, data_type, quality), count in grouped.items()
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

        today = datetime.now(ZoneInfo(site.timezone)).date()
        historical_mask = frame["Fecha"].dt.date < today
        fallback_mask = historical_mask & (frame["Fuente"] == FALLBACK_SOURCE)
        repository_mask = historical_mask & ~fallback_mask
        siga_mask = frame["Fuente"].astype(str).str.contains("SIGA", case=False)

        repository_rows = int(repository_mask.sum())
        if repository_rows == 0:
            raise RuntimeError(
                f"{site.nombre}: el archivo final no conserva ninguna fila "
                "histórica procedente de meteo_daily.csv."
            )

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
            "historico_prioritario": "meteo_daily.csv del repositorio geográfico",
            "repositorio_historico": site.repositorio,
            "url_historico": site.raw_meteo_url,
            "filas_historico_repositorio": repository_rows,
            "filas_respaldo_open_meteo": int(fallback_mask.sum()),
            "requiere_siga": site.usa_siga_historico,
            "filas_siga": int(siga_mask.sum()),
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

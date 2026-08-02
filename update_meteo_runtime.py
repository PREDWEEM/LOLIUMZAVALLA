from __future__ import annotations

from typing import Any

import pandas as pd

import update_meteo as base


_ORIGINAL_PRECIPITATION_MM = base._precipitation_mm
_ORIGINAL_FETCH_SMN = base.fetch_smn_rosario_daily
_ORIGINAL_MERGE = base.merge_observed_priority_history


def safe_precipitation_mm(value: float, units: str) -> float:
    """Convierte precipitación y descarta códigos negativos del origen."""
    converted = float(_ORIGINAL_PRECIPITATION_MM(value, units))
    if converted < 0:
        return float("nan")
    return converted


def sanitize_observed_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Convierte valores físicos inválidos en faltantes reemplazables.

    La selección de fuentes de ``update_meteo`` completa luego esos faltantes
    respetando la prioridad SMN → NOAA → Open-Meteo ECMWF IFS Archive.
    """
    if frame is None:
        return base._empty_weather()

    cleaned = frame.copy()
    if cleaned.empty:
        return cleaned

    if "Prec" in cleaned:
        precipitation = pd.to_numeric(cleaned["Prec"], errors="coerce")
        invalid_precipitation = precipitation < 0
        if bool(invalid_precipitation.any()):
            dates = pd.to_datetime(
                cleaned.loc[invalid_precipitation, "Fecha"],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d")
            print(
                "Precipitación observada negativa descartada en: "
                + ", ".join(dates.dropna().astype(str).tolist()[:20])
            )
            cleaned.loc[invalid_precipitation, "Prec"] = pd.NA
            if "Fuente_Prec" in cleaned:
                cleaned.loc[invalid_precipitation, "Fuente_Prec"] = pd.NA

    # Límites amplios destinados únicamente a detectar sentinelas o errores de
    # codificación. No sustituyen el control de calidad de la fuente.
    for variable, provenance in (
        ("TMAX", "Fuente_TMAX"),
        ("TMIN", "Fuente_TMIN"),
    ):
        if variable not in cleaned:
            continue
        temperature = pd.to_numeric(cleaned[variable], errors="coerce")
        invalid_temperature = (temperature < -60) | (temperature > 60)
        if bool(invalid_temperature.any()):
            cleaned.loc[invalid_temperature, variable] = pd.NA
            if provenance in cleaned:
                cleaned.loc[invalid_temperature, provenance] = pd.NA

    return cleaned


def fetch_smn_rosario_daily(*args: Any, **kwargs: Any) -> pd.DataFrame:
    """Obtiene SMN y elimina sentinelas antes de combinar fuentes."""
    return sanitize_observed_frame(_ORIGINAL_FETCH_SMN(*args, **kwargs))


def merge_observed_priority_history(
    smn: pd.DataFrame,
    noaa: pd.DataFrame,
    archive: pd.DataFrame,
    **kwargs: Any,
) -> pd.DataFrame:
    """Aplica un segundo control defensivo antes de elegir cada variable."""
    return _ORIGINAL_MERGE(
        sanitize_observed_frame(smn),
        sanitize_observed_frame(noaa),
        archive,
        **kwargs,
    )


def install_runtime_corrections() -> None:
    """Instala las correcciones en el módulo usado por el workflow."""
    base._precipitation_mm = safe_precipitation_mm
    base.fetch_smn_rosario_daily = fetch_smn_rosario_daily
    base.merge_observed_priority_history = merge_observed_priority_history


def main() -> None:
    install_runtime_corrections()
    base.main()


if __name__ == "__main__":
    main()

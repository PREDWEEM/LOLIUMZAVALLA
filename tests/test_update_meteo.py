from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from sitios_lolium import get_site
from update_meteo import (
    COLUMNS,
    FORECAST_PAST_DAYS,
    canonicalize_repository_history,
    combine_historical_and_forecast,
    merge_siga_priority_history,
)


def weather_frame(start: str, periods: int, source: str) -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq="D")
    frame = pd.DataFrame(
        {
            "Fecha": dates,
            "TMAX": [18.0] * periods,
            "TMIN": [8.0] * periods,
            "Prec": [0.0] * periods,
            "Fuente": [source] * periods,
            "TipoDato": [source] * periods,
            "CalidadDato": [source] * periods,
            "Emision": ["2026-07-30T23:57:00-03:00"] * periods,
        }
    )
    return frame[COLUMNS]


def test_past_days_is_enabled_for_the_forecast_bridge():
    assert FORECAST_PAST_DAYS >= 1


def test_recent_forecast_closes_gap_after_historical_block():
    historical = weather_frame("2026-07-27", 3, "archive")
    forecast = weather_frame("2026-07-29", 5, "forecast")

    combined = combine_historical_and_forecast(
        historical,
        forecast,
        date(2026, 7, 30),
    )

    assert combined["Fecha"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
        "2026-07-30",
        "2026-07-31",
        "2026-08-01",
        "2026-08-02",
    ]
    current_row = combined.loc[
        combined["Fecha"] == pd.Timestamp("2026-07-30")
    ].iloc[0]
    assert current_row["Fuente"] == "forecast"


def test_missing_current_day_has_explicit_diagnostic():
    historical = weather_frame("2026-07-27", 3, "archive")
    forecast = weather_frame("2026-07-31", 3, "forecast")

    with pytest.raises(RuntimeError, match="no devolvió el día actual 2026-07-30"):
        combine_historical_and_forecast(
            historical,
            forecast,
            date(2026, 7, 30),
        )


def test_repository_history_maps_siga_columns_and_emission():
    raw = pd.DataFrame(
        {
            "Fecha": ["2026-01-01", "2026-01-02"],
            "TMAX": [30.0, 29.0],
            "TMIN": [12.0, 11.0],
            "Prec": [0.0, 2.5],
            "Fuente": ["SIGA_INTA_PERGAMINO", "ECMWF_IFS_HISTORICO"],
            "TipoDato": ["Observado", "Provisional"],
            "CalidadDato": [
                "Observado_estacion",
                "Provisional_hasta_reemplazo_SIGA",
            ],
            "Emision_UTC": ["2026-07-30T20:00:00+00:00"] * 2,
        }
    )

    normalized = canonicalize_repository_history(
        raw,
        site=get_site("pergamino"),
        emission="2026-07-31T00:00:00-03:00",
        end_date=date(2026, 1, 2),
    )

    assert list(normalized.columns) == COLUMNS
    assert normalized.iloc[0]["Fuente"] == "SIGA_INTA_PERGAMINO"
    assert normalized.iloc[0]["Emision"] == "2026-07-30T20:00:00+00:00"


def test_siga_repository_rows_override_model_and_model_only_fills_gaps():
    model = weather_frame("2026-01-01", 3, "modelo")
    repository = weather_frame("2026-01-01", 1, "SIGA_INTA_BALCARCE")
    repository.loc[0, "TMAX"] = 31.5
    repository.loc[0, "TipoDato"] = "Observado"
    repository.loc[0, "CalidadDato"] = "Observado_estacion"

    combined = merge_siga_priority_history(model, repository)

    first = combined.loc[combined["Fecha"] == pd.Timestamp("2026-01-01")].iloc[0]
    second = combined.loc[combined["Fecha"] == pd.Timestamp("2026-01-02")].iloc[0]
    assert first["Fuente"] == "SIGA_INTA_BALCARCE"
    assert first["TMAX"] == 31.5
    assert second["Fuente"] == "OPEN_METEO_ECMWF_IFS_ARCHIVE_FALLBACK"
    assert second["CalidadDato"] == "Provisional_hueco_SIGA"


def test_repository_history_without_siga_is_rejected():
    raw = pd.DataFrame(
        {
            "Fecha": ["2026-01-01"],
            "TMAX": [30.0],
            "TMIN": [12.0],
            "Prec": [0.0],
            "Fuente": ["ECMWF_IFS_HISTORICO"],
        }
    )

    with pytest.raises(RuntimeError, match="ninguna observación SIGA"):
        canonicalize_repository_history(
            raw,
            site=get_site("balcarce"),
            emission="2026-07-31T00:00:00-03:00",
            end_date=date(2026, 1, 1),
        )

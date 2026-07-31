from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from update_meteo import (
    COLUMNS,
    FORECAST_PAST_DAYS,
    combine_historical_and_forecast,
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
            "Emision": ["2026-07-30T23:57:00-03:00"] * periods,
        }
    )
    return frame[COLUMNS]


def test_past_days_is_enabled_for_the_forecast_bridge():
    assert FORECAST_PAST_DAYS >= 1


def test_recent_forecast_closes_gap_after_historical_block():
    historical = weather_frame("2026-07-27", 3, "archive")
    # La respuesta con past_days incluye ayer, hoy y días futuros.
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

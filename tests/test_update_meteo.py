from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from sitios_lolium import SITES
from update_meteo import (
    ARCHIVE_SOURCE,
    COLUMNS,
    FORECAST_PAST_DAYS,
    FORECAST_SOURCE,
    NOAA_SOURCE,
    SMN_SOURCE,
    combine_historical_and_forecast,
    merge_observed_priority_history,
)


def weather_frame(
    start: str,
    periods: int,
    source: str,
    *,
    tmax: float | None = 18.0,
    tmin: float | None = 8.0,
    prec: float | None = 0.0,
    data_type: str = "Observado",
) -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq="D")
    frame = pd.DataFrame(
        {
            "Fecha": dates,
            "TMAX": [tmax] * periods,
            "TMIN": [tmin] * periods,
            "Prec": [prec] * periods,
            "Fuente": [source] * periods,
            "TipoDato": [data_type] * periods,
            "CalidadDato": [data_type] * periods,
            "Emision": ["2026-08-02T12:00:00-03:00"] * periods,
            "Fuente_TMAX": [source] * periods,
            "Fuente_TMIN": [source] * periods,
            "Fuente_Prec": [source] * periods,
        }
    )
    return frame[COLUMNS]


def test_past_days_is_enabled_for_the_forecast_bridge():
    assert FORECAST_PAST_DAYS >= 1


def test_all_sites_keep_meteo_daily_as_operational_filename():
    assert len(SITES) == 9
    assert all(site.archivo_meteo == "meteo_daily.csv" for site in SITES.values())


def test_smn_has_priority_when_all_variables_are_observed():
    smn = weather_frame("2026-01-01", 2, SMN_SOURCE)
    noaa = weather_frame("2026-01-01", 2, NOAA_SOURCE, tmax=25.0)
    archive = weather_frame("2026-01-01", 2, ARCHIVE_SOURCE, tmax=30.0)

    merged = merge_observed_priority_history(
        smn,
        noaa,
        archive,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        emission="2026-08-02T12:00:00-03:00",
    )

    assert (merged["Fuente"] == SMN_SOURCE).all()
    assert (merged["TMAX"] == 18.0).all()
    assert (merged["TipoDato"] == "Observado").all()


def test_noaa_completes_missing_smn_precipitation_per_variable():
    smn = weather_frame("2026-01-01", 1, SMN_SOURCE, prec=None)
    noaa = weather_frame("2026-01-01", 1, NOAA_SOURCE, prec=12.4)
    archive = weather_frame("2026-01-01", 1, ARCHIVE_SOURCE, prec=20.0)

    merged = merge_observed_priority_history(
        smn,
        noaa,
        archive,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
        emission="2026-08-02T12:00:00-03:00",
    )
    row = merged.iloc[0]

    assert row["TMAX"] == 18.0
    assert row["TMIN"] == 8.0
    assert row["Prec"] == 12.4
    assert row["Fuente_TMAX"] == SMN_SOURCE
    assert row["Fuente_Prec"] == NOAA_SOURCE
    assert row["TipoDato"] == "Observado_compuesto"
    assert row["CalidadDato"] == "Observado_SMN_con_respaldo_NOAA"


def test_open_meteo_archive_fills_days_absent_from_observed_sources():
    smn = weather_frame("2026-01-01", 1, SMN_SOURCE)
    noaa = weather_frame("2026-01-01", 1, NOAA_SOURCE)
    archive = weather_frame(
        "2026-01-01",
        3,
        ARCHIVE_SOURCE,
        tmax=27.0,
        data_type="Provisional",
    )

    merged = merge_observed_priority_history(
        smn,
        noaa,
        archive,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        emission="2026-08-02T12:00:00-03:00",
    )

    fallback = merged.loc[
        merged["Fecha"] == pd.Timestamp("2026-01-02")
    ].iloc[0]
    assert fallback["Fuente"] == ARCHIVE_SOURCE
    assert fallback["TMAX"] == 27.0
    assert fallback["TipoDato"] == "Provisional"
    assert fallback["CalidadDato"] == "Provisional_hueco_observaciones"


def test_merge_fails_when_all_three_sources_leave_a_critical_gap():
    smn = weather_frame("2026-01-01", 1, SMN_SOURCE, prec=None)
    noaa = weather_frame("2026-01-01", 1, NOAA_SOURCE, prec=None)
    archive = weather_frame("2026-01-01", 1, ARCHIVE_SOURCE, prec=None)

    with pytest.raises(RuntimeError, match="No fue posible completar"):
        merge_observed_priority_history(
            smn,
            noaa,
            archive,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1),
            emission="2026-08-02T12:00:00-03:00",
        )


def test_forecast_replaces_today_but_not_yesterday():
    historical = weather_frame(
        "2026-07-27",
        4,
        SMN_SOURCE,
    )
    forecast = weather_frame(
        "2026-07-29",
        5,
        FORECAST_SOURCE,
        data_type="Pronostico",
    )

    combined = combine_historical_and_forecast(
        historical,
        forecast,
        date(2026, 7, 30),
    )

    yesterday = combined.loc[
        combined["Fecha"] == pd.Timestamp("2026-07-29")
    ].iloc[0]
    today = combined.loc[
        combined["Fecha"] == pd.Timestamp("2026-07-30")
    ].iloc[0]
    assert yesterday["Fuente"] == SMN_SOURCE
    assert today["Fuente"] == FORECAST_SOURCE


def test_missing_current_day_has_explicit_diagnostic():
    historical = weather_frame("2026-07-27", 3, SMN_SOURCE)
    forecast = weather_frame("2026-07-31", 3, FORECAST_SOURCE)

    with pytest.raises(RuntimeError, match="no devolvió el día actual 2026-07-30"):
        combine_historical_and_forecast(
            historical,
            forecast,
            date(2026, 7, 30),
        )

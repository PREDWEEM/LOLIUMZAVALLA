from __future__ import annotations

from datetime import date
import math

import pandas as pd

import update_meteo as base
from update_meteo_runtime import (
    merge_observed_priority_history,
    safe_precipitation_mm,
    sanitize_observed_frame,
)


def weather_frame(
    source: str,
    *,
    precipitation: float | None,
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "Fecha": [pd.Timestamp("2026-04-04")],
            "TMAX": [24.0],
            "TMIN": [12.0],
            "Prec": [precipitation],
            "Fuente": [source],
            "TipoDato": ["Observado"],
            "CalidadDato": ["Prueba"],
            "Emision": ["2026-08-02T13:00:00-03:00"],
            "Fuente_TMAX": [source],
            "Fuente_TMIN": [source],
            "Fuente_Prec": [source],
        }
    )
    return frame[base.COLUMNS]


def test_negative_smn_precipitation_code_becomes_missing():
    assert math.isnan(safe_precipitation_mm(-1.0, "mm"))


def test_sanitizer_removes_value_and_precipitation_provenance():
    cleaned = sanitize_observed_frame(
        weather_frame(base.SMN_SOURCE, precipitation=-1.0)
    )

    assert pd.isna(cleaned.loc[0, "Prec"])
    assert pd.isna(cleaned.loc[0, "Fuente_Prec"])
    assert cleaned.loc[0, "TMAX"] == 24.0


def test_negative_smn_precipitation_is_replaced_by_archive():
    smn = weather_frame(base.SMN_SOURCE, precipitation=-1.0)
    noaa = weather_frame(base.NOAA_SOURCE, precipitation=None)
    archive = weather_frame(base.ARCHIVE_SOURCE, precipitation=7.6)
    archive["TipoDato"] = "Provisional"

    merged = merge_observed_priority_history(
        smn,
        noaa,
        archive,
        start_date=date(2026, 4, 4),
        end_date=date(2026, 4, 4),
        emission="2026-08-02T13:00:00-03:00",
    )
    row = merged.iloc[0]

    assert row["Prec"] == 7.6
    assert row["Fuente_Prec"] == base.ARCHIVE_SOURCE
    assert row["TMAX"] == 24.0
    assert row["Fuente_TMAX"] == base.SMN_SOURCE
    assert row["TipoDato"] == "Provisional"

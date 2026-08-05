from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

import app_fuente_hibrida as base


principal = base.principal
COHORT_EXHAUSTION_DAYS = 110
COHORT_REMAINING_THRESHOLD = 0.005

_ORIGINAL_SIMULATE_DUAL = principal.simulate_dual
_ORIGINAL_BUILD_OPERATIONAL_DATA = principal.build_operational_data


def _is_balcarce(config: Any) -> bool:
    """Identifica Balcarce por estado de Streamlit o por la configuración activa."""
    selected = str(
        st.session_state.get("selected_lolium_site", "")
    ).strip().lower()
    configured = str(getattr(config, "nombre_sitio", "")).strip().lower()
    return selected == "balcarce" or configured.startswith("balcarce")


def _simulate_dual_with_cohort_exhaustion(*args: Any, **kwargs: Any):
    """Aplica extinción fisiológica a la cohorte emergente de Balcarce."""
    result = _ORIGINAL_SIMULATE_DUAL(*args, **kwargs)
    config = kwargs.get("config")
    if config is None or not _is_balcarce(config):
        return result

    tau = max(float(config.decaimiento_tau_dias), 0.01)
    beta = max(float(config.decaimiento_beta), 0.01)
    data = result.data

    for suffix in ("SIN_LAG", "CON_LAG"):
        days_column = f"DIAS_DESDE_PICO_{suffix}"
        emergence_column = f"EMERREL_{suffix}"
        cumulative_column = f"EMERAC_{suffix}"
        mixed_factor_column = f"FACTOR_DECAIMIENTO_{suffix}"
        base_factor_column = f"FACTOR_DECAIMIENTO_BASE_{suffix}"
        exhausted_column = f"COHORTE_AGOTADA_{suffix}"

        if days_column not in data or emergence_column not in data:
            continue

        days = (
            pd.to_numeric(data[days_column], errors="coerce")
            .fillna(0.0)
            .to_numpy(float)
        )
        base_factor = np.exp(-np.power(days / tau, beta))
        exhausted = (
            (days >= COHORT_EXHAUSTION_DAYS)
            & (base_factor <= COHORT_REMAINING_THRESHOLD)
        )

        data[base_factor_column] = base_factor
        data[exhausted_column] = exhausted
        data.loc[exhausted, emergence_column] = 0.0
        if mixed_factor_column in data:
            data.loc[exhausted, mixed_factor_column] = 0.0
        data[cumulative_column] = data[emergence_column].cumsum()

    return result


def _build_operational_data_with_audit(
    data: pd.DataFrame,
    model_mode: str,
    lag_days: int,
):
    """Conserva la trazabilidad del agotamiento en la tabla operativa."""
    suffix = "CON_LAG" if model_mode == "con_lag" else "SIN_LAG"
    exhausted = data.get(f"COHORTE_AGOTADA_{suffix}")
    base_factor = data.get(f"FACTOR_DECAIMIENTO_BASE_{suffix}")

    output, model_name, peak = _ORIGINAL_BUILD_OPERATIONAL_DATA(
        data,
        model_mode,
        lag_days,
    )

    if exhausted is None:
        output["Cohorte_Agotada"] = False
        output["Factor_Decaimiento_Base"] = np.nan
        output["Criterio_Agotamiento_Dias"] = np.nan
        output["Criterio_Remanente_Maximo"] = np.nan
    else:
        output["Cohorte_Agotada"] = exhausted.to_numpy(bool)
        output["Factor_Decaimiento_Base"] = base_factor.to_numpy(float)
        output["Criterio_Agotamiento_Dias"] = COHORT_EXHAUSTION_DAYS
        output["Criterio_Remanente_Maximo"] = COHORT_REMAINING_THRESHOLD

    return output, model_name, peak


def run() -> None:
    """Ejecuta MULTISITIO con agotamiento fisiológico específico de Balcarce."""
    original_simulate_dual = principal.simulate_dual
    original_build_operational_data = principal.build_operational_data

    principal.simulate_dual = _simulate_dual_with_cohort_exhaustion
    principal.build_operational_data = _build_operational_data_with_audit
    try:
        base.run()
    finally:
        principal.simulate_dual = original_simulate_dual
        principal.build_operational_data = original_build_operational_data

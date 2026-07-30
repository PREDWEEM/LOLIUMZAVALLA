import pandas as pd

from selector_adaptativo import evaluate_selector, visible_models


def inspection(date, positive=False):
    return {
        "Fecha": date,
        "Operario": "test",
        "Plantas_m2": 1.0 if positive else 0.0,
        "Cuadros_positivos": 2 if positive else 0,
        "Cuadros_totales": 10,
        "Emergencia_confirmada": positive,
        "Observaciones": "",
    }


def test_positive_first_inspection_confirms_no_lag_and_hides_lag():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    decision = evaluate_selector(
        peak0,
        peak15,
        pd.DataFrame([inspection("2026-03-22", True)]),
        today=pd.Timestamp("2026-03-22"),
    )
    assert decision.estado == "SIN_LAG_CONFIRMADO"
    assert decision.modelo_activo == "sin_lag"
    assert visible_models(decision) == (True, False)


def test_first_negative_selects_fixed_lag_and_hides_no_lag():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    decision = evaluate_selector(
        peak0,
        peak15,
        pd.DataFrame([inspection("2026-03-20")]),
        today=pd.Timestamp("2026-03-20"),
    )
    assert decision.estado == "CON_LAG_PROVISIONAL"
    assert decision.modelo_activo == "con_lag"
    assert decision.lag_operativo_dias == 15
    assert visible_models(decision) == (False, True)


def test_positive_near_fixed_lag_confirms_lag():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    data = pd.DataFrame(
        [inspection("2026-03-20"), inspection("2026-04-03", True)]
    )
    decision = evaluate_selector(
        peak0,
        peak15,
        data,
        today=pd.Timestamp("2026-04-03"),
    )
    assert decision.estado == "CON_LAG_CONFIRMADO"
    assert decision.modelo_activo == "con_lag"
    assert visible_models(decision) == (False, True)


def test_intermediate_positive_does_not_estimate_local_lag():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    data = pd.DataFrame(
        [inspection("2026-03-20"), inspection("2026-03-28", True)]
    )
    decision = evaluate_selector(
        peak0,
        peak15,
        data,
        today=pd.Timestamp("2026-03-28"),
    )
    assert decision.estado == "CON_LAG_PROVISIONAL"
    assert decision.modelo_activo == "con_lag"
    assert decision.lag_operativo_dias == 15
    assert "local" in decision.motivo.lower()


def test_no_emergence_in_both_windows_rejects_both_and_shows_diagnostic_curves():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    data = pd.DataFrame([inspection("2026-03-20")])
    decision = evaluate_selector(
        peak0,
        peak15,
        data,
        today=pd.Timestamp("2026-04-12"),
    )
    assert decision.estado == "NINGUNO_CONFIRMADO"
    assert decision.modelo_activo == "ninguno"
    assert visible_models(decision) == (True, True)


def test_before_field_selection_both_models_remain_visible():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    decision = evaluate_selector(
        peak0,
        peak15,
        pd.DataFrame(),
        today=pd.Timestamp("2026-03-10"),
    )
    assert decision.modelo_activo == "pendiente"
    assert visible_models(decision) == (True, True)

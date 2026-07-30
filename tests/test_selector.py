import pandas as pd

from selector_adaptativo import evaluate_selector


def inspection(date, positive=False):
    return {"Fecha": date, "Operario": "test", "Plantas_m2": 1.0 if positive else 0.0, "Cuadros_positivos": 2 if positive else 0, "Cuadros_totales": 10, "Emergencia_confirmada": positive, "Observaciones": ""}


def test_positive_near_no_lag_confirms_no_lag():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    decision = evaluate_selector(peak0, peak15, pd.DataFrame([inspection("2026-03-22", True)]), today=pd.Timestamp("2026-03-22"))
    assert decision.estado == "SIN_LAG_CONFIRMADO"
    assert decision.modelo_activo == "sin_lag"


def test_two_negatives_activate_provisional_lag():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    data = pd.DataFrame([inspection("2026-03-20"), inspection("2026-03-24")])
    decision = evaluate_selector(peak0, peak15, data, today=pd.Timestamp("2026-03-25"))
    assert decision.estado == "CON_LAG_PROVISIONAL"
    assert decision.modelo_activo == "con_lag"


def test_positive_near_lag_confirms_lag():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    data = pd.DataFrame([inspection("2026-03-20"), inspection("2026-03-24"), inspection("2026-04-03", True)])
    decision = evaluate_selector(peak0, peak15, data, today=pd.Timestamp("2026-04-03"))
    assert decision.estado == "CON_LAG_CONFIRMADO"


def test_no_emergence_in_both_windows_rejects_both():
    peak0 = pd.Timestamp("2026-03-20")
    peak15 = pd.Timestamp("2026-04-04")
    data = pd.DataFrame([inspection("2026-03-20"), inspection("2026-03-24")])
    decision = evaluate_selector(peak0, peak15, data, today=pd.Timestamp("2026-04-12"))
    assert decision.estado == "NINGUNO_CONFIRMADO"

import numpy as np
import pandas as pd

from visualizacion_pulsos import agrupar_pulsos, construir_campanas_agrupadas


def test_pulsos_cercanos_se_agrupan_en_una_campana():
    fechas = pd.date_range("2026-03-01", periods=10, freq="D")
    valores = [0.0, 0.4, 1.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0]

    grupos = agrupar_pulsos(
        fechas,
        valores,
        umbral=0.01,
        max_dias_sin_flujo=3,
    )

    assert grupos == [(1, 5)]


def test_pulsos_lejanos_permanecen_separados():
    fechas = pd.date_range("2026-03-01", periods=14, freq="D")
    valores = np.zeros(14)
    valores[1] = 0.8
    valores[9] = 0.6

    grupos = agrupar_pulsos(
        fechas,
        valores,
        umbral=0.01,
        max_dias_sin_flujo=3,
    )

    assert grupos == [(1, 1), (9, 9)]


def test_campana_es_suave_y_respeta_la_escala_original():
    fechas = pd.date_range("2026-04-01", periods=12, freq="D")
    valores = [0.0, 0.2, 0.8, 1.0, 0.6, 0.0, 0.0, 0.0, 0.3, 0.5, 0.0, 0.0]

    curva = construir_campanas_agrupadas(fechas, valores)

    assert not curva.empty
    assert len(curva) > len(fechas)
    assert curva["EMERREL_CAMPANA"].min() >= 0.0
    assert curva["EMERREL_CAMPANA"].max() <= max(valores) + 1e-12
    assert curva["EMERREL_CAMPANA"].max() > 0.9


def test_serie_sin_emergencia_devuelve_area_cero():
    fechas = pd.date_range("2026-05-01", periods=8, freq="D")
    curva = construir_campanas_agrupadas(fechas, np.zeros(8))

    assert not curva.empty
    assert np.allclose(curva["EMERREL_CAMPANA"], 0.0)

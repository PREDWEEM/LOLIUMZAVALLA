from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import pandas as pd

from config_zavalla import CONFIG, ZavallaConfig


INSPECTION_COLUMNS = [
    "Fecha",
    "Operario",
    "Plantas_m2",
    "Cuadros_positivos",
    "Cuadros_totales",
    "Emergencia_confirmada",
    "Observaciones",
]


@dataclass
class SelectorDecision:
    estado: str
    modelo_activo: str
    lag_operativo_dias: int | None
    proxima_accion: str
    proxima_inspeccion: str | None
    fecha_pico_sin_lag: str | None
    fecha_pico_con_lag: str | None
    negativas_validas: int
    positivas_validas: int
    confianza: str
    motivo: str

    def to_dict(self) -> dict:
        return asdict(self)


def empty_inspections() -> pd.DataFrame:
    return pd.DataFrame(columns=INSPECTION_COLUMNS)


def normalize_inspections(raw: pd.DataFrame | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return empty_inspections()
    data = raw.copy()
    for column in INSPECTION_COLUMNS:
        if column not in data.columns:
            data[column] = None
    data = data[INSPECTION_COLUMNS]
    data["Fecha"] = pd.to_datetime(data["Fecha"], errors="coerce").dt.normalize()
    for column in ("Plantas_m2", "Cuadros_positivos", "Cuadros_totales"):
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)
    explicit = data["Emergencia_confirmada"].astype(str).str.lower().isin({"true", "1", "si", "sí", "yes"})
    data["Emergencia_confirmada"] = explicit
    return data.dropna(subset=["Fecha"]).sort_values("Fecha").reset_index(drop=True)


def classify_inspections(data: pd.DataFrame, config: ZavallaConfig = CONFIG) -> pd.DataFrame:
    out = normalize_inspections(data)
    if out.empty:
        out["Positiva"] = pd.Series(dtype=bool)
        return out
    out["Positiva"] = (
        out["Emergencia_confirmada"]
        | (out["Plantas_m2"] >= config.densidad_confirmacion_pl_m2)
        | (out["Cuadros_positivos"] >= 2)
    )
    return out


def evaluate_selector(
    peak_no_lag: pd.Timestamp | None,
    peak_lag: pd.Timestamp | None,
    inspections: pd.DataFrame | None,
    *,
    today: pd.Timestamp | None = None,
    lag_candidate_days: int = CONFIG.lag_candidato_dias,
    negative_required: int = CONFIG.negativas_para_lag,
    config: ZavallaConfig = CONFIG,
) -> SelectorDecision:
    now = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    if peak_no_lag is None:
        return SelectorDecision(
            "SIN_PICO_SIMULADO", "sin_lag", 0,
            "Continuar actualizando la meteorología; aún no existe un primer pico habilitado.",
            None, None, None, 0, 0, "baja", "La curva sin lag todavía no supera el umbral del primer pico."
        )

    peak0 = pd.Timestamp(peak_no_lag).normalize()
    peak15 = pd.Timestamp(peak_lag).normalize() if peak_lag is not None else peak0 + pd.Timedelta(days=int(lag_candidate_days))
    classified = classify_inspections(inspections, config)
    valid = classified[classified["Fecha"] >= peak0 - pd.Timedelta(days=2)].copy()
    positives = valid[valid["Positiva"]]
    negatives = valid[~valid["Positiva"]]

    if not positives.empty:
        first_positive = pd.Timestamp(positives.iloc[0]["Fecha"])
        observed_lag = int((first_positive - peak0).days)
        if observed_lag <= config.tolerancia_sin_lag_dias:
            return SelectorDecision(
                "SIN_LAG_CONFIRMADO", "sin_lag", 0,
                "Mantener el modelo sin lag y corroborar el segundo flujo o T50.",
                None, peak0.date().isoformat(), peak15.date().isoformat(), len(negatives), len(positives),
                "alta", f"La primera emergencia positiva ocurrió {observed_lag} días después del pico sin lag."
            )
        if abs((first_positive - peak15).days) <= config.tolerancia_lag_dias:
            return SelectorDecision(
                "CON_LAG_CONFIRMADO", "con_lag", int(lag_candidate_days),
                "Usar el modelo con lag y validar su desempeño Event-to-Event al final de la campaña.",
                None, peak0.date().isoformat(), peak15.date().isoformat(), len(negatives), len(positives),
                "alta", f"La emergencia apareció cerca de la ventana del lag candidato ({lag_candidate_days} días)."
            )
        return SelectorDecision(
            "LAG_LOCAL_ESTIMADO", "lag_local", max(0, observed_lag),
            "Usar provisionalmente el lag observado y mantener visibles las curvas lag 0 y lag candidato.",
            None, peak0.date().isoformat(), peak15.date().isoformat(), len(negatives), len(positives),
            "media", f"La emergencia apareció con un desfase local de {observed_lag} días."
        )

    if now < peak0 - pd.Timedelta(days=2):
        return SelectorDecision(
            "SIN_LAG_EN_EVALUACION", "sin_lag", 0,
            "Esperar la ventana del primer pico y organizar la inspección de campo.",
            peak0.date().isoformat(), peak0.date().isoformat(), peak15.date().isoformat(), 0, 0,
            "baja", "El primer pico sin lag todavía es futuro."
        )

    if len(negatives) == 0:
        return SelectorDecision(
            "VERIFICACION_1_PENDIENTE", "sin_lag", 0,
            "Realizar la primera inspección de campo y registrar densidad, cuadros y evidencia.",
            now.date().isoformat(), peak0.date().isoformat(), peak15.date().isoformat(), 0, 0,
            "baja", "El pico sin lag fue alcanzado, pero aún no hay una inspección válida."
        )

    last_negative = pd.Timestamp(negatives.iloc[-1]["Fecha"])
    if len(negatives) < int(negative_required):
        next_visit = last_negative + pd.Timedelta(days=config.dias_entre_inspecciones)
        return SelectorDecision(
            "LAG_CANDIDATO", "sin_lag", 0,
            "La primera visita fue negativa. Realizar una nueva inspección antes de activar definitivamente el lag.",
            next_visit.date().isoformat(), peak0.date().isoformat(), peak15.date().isoformat(), len(negatives), 0,
            "media", f"Se requieren {negative_required} inspecciones negativas y hay {len(negatives)}."
        )

    if now <= peak15 + pd.Timedelta(days=config.tolerancia_lag_dias):
        return SelectorDecision(
            "CON_LAG_PROVISIONAL", "con_lag", int(lag_candidate_days),
            "Operar provisionalmente con lag y realizar una inspección en la ventana del pico desplazado.",
            peak15.date().isoformat(), peak0.date().isoformat(), peak15.date().isoformat(), len(negatives), 0,
            "media", "El pico sin lag no fue confirmado en inspecciones consecutivas."
        )

    return SelectorDecision(
        "NINGUNO_CONFIRMADO", "ninguno", None,
        "Revisar meteorología, banco de semillas, dormición, Wmax, cobertura y termoinhibición.",
        None, peak0.date().isoformat(), peak15.date().isoformat(), len(negatives), 0,
        "baja", "No se observó emergencia ni en la ventana sin lag ni en la ventana con lag."
    )


def load_inspections(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.is_file() or file_path.stat().st_size == 0:
        return empty_inspections()
    return normalize_inspections(pd.read_csv(file_path))


def save_inspections(data: pd.DataFrame, path: str | Path) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    normalize_inspections(data).to_csv(file_path, index=False)


def save_decision(decision: SelectorDecision, path: str | Path) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(decision.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

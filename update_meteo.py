from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import tempfile
import time

import requests

from sitios_lolium import DEFAULT_SITE_SLUG, LoliumSite, ordered_sites


LEGACY_OUTPUT = Path("meteo_daily.csv")
STATE = Path("data/estado_actualizacion_meteo.json")
TIMEOUT = 90
MAX_ATTEMPTS = 3
PUBLIC_HEADERS = {
    "User-Agent": "PREDWEEM-LOLIUM-multisitio/1.0",
    "Accept": "text/csv,*/*",
}


def download_exact_repository_file(site: LoliumSite) -> tuple[bytes, str]:
    """
    Descarga los bytes originales del meteo_daily.csv público.

    No interpreta, completa, ordena, combina ni vuelve a serializar el CSV.
    """
    url = site.raw_meteo_url
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                headers=PUBLIC_HEADERS,
                timeout=TIMEOUT,
            )
            print(
                f"{site.nombre}: {site.repositorio}/"
                f"{site.archivo_meteo}@{site.rama_meteo} "
                f"HTTP {response.status_code}"
            )

            if response.status_code == 404:
                raise RuntimeError(
                    f"{site.nombre}: GitHub devolvió 404 para {url}. "
                    "Verifique el nombre del repositorio, la rama y la "
                    "ubicación de meteo_daily.csv."
                )

            response.raise_for_status()
            content = response.content

            if not content:
                raise RuntimeError(
                    f"{site.nombre}: el archivo descargado está vacío."
                )

            return content, response.url

        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(3 * attempt)

    raise RuntimeError(
        f"{site.nombre}: no fue posible copiar exactamente "
        f"{site.repositorio}/{site.archivo_meteo}."
    ) from last_error


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_exact_bytes(path: Path, content: bytes) -> None:
    """Escribe atómicamente y verifica que la copia conserve los mismos bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())

    try:
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    copied = path.read_bytes()
    if copied != content:
        raise RuntimeError(
            f"La verificación byte a byte falló para {path.as_posix()}."
        )


def main() -> None:
    updated_at = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).isoformat(timespec="seconds")

    state: dict[str, object] = {
        "actualizado_en": updated_at,
        "modo": "COPIA_EXACTA_METEO_DAILY_PUBLICO",
        "descripcion": (
            "Cada archivo de data/meteo_sitios es una copia byte por byte "
            "del meteo_daily.csv público de su repositorio geográfico."
        ),
        "sitios": {},
    }

    for site in ordered_sites():
        print(f"\n=== {site.etiqueta} ===")
        content, requested_url = download_exact_repository_file(site)
        destination = site.meteo_path(".")
        write_exact_bytes(destination, content)

        digest = sha256_bytes(content)
        site_state = {
            "repositorio": site.repositorio,
            "rama": site.rama_meteo,
            "archivo_origen": site.archivo_meteo,
            "url_origen": site.raw_meteo_url,
            "url_solicitada": requested_url,
            "archivo_destino": destination.as_posix(),
            "bytes": len(content),
            "sha256": digest,
            "copia_exacta": True,
            "repositorio_publico": True,
        }
        state["sitios"][site.slug] = site_state

        print(
            f"Copiado exactamente en {destination.as_posix()} | "
            f"{len(content)} bytes | sha256={digest}"
        )

        if site.slug == DEFAULT_SITE_SLUG:
            write_exact_bytes(LEGACY_OUTPUT, content)
            if sha256_bytes(LEGACY_OUTPUT.read_bytes()) != digest:
                raise RuntimeError(
                    "La copia raíz meteo_daily.csv no coincide con Zavalla."
                )

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "\nActualización terminada: todos los archivos públicos fueron "
        "copiados sin transformar sus datos ni su estructura."
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoliumSite:
    """Identidad geográfica y fuente histórica de una implementación LOLIUM."""

    slug: str
    nombre: str
    provincia: str
    latitud: float
    longitud: float
    repositorio: str
    timezone: str = "America/Argentina/Buenos_Aires"
    usa_siga_historico: bool = False

    @property
    def etiqueta(self) -> str:
        return f"{self.nombre} ({self.provincia})"

    @property
    def repository_url(self) -> str:
        return f"https://github.com/{self.repositorio}"

    @property
    def raw_meteo_url(self) -> str:
        return (
            f"https://raw.githubusercontent.com/{self.repositorio}/"
            "main/meteo_daily.csv"
        )

    def meteo_path(self, base: str | Path = ".") -> Path:
        return Path(base) / "data" / "meteo_sitios" / f"{self.slug}.csv"

    def inspections_path(self, base: str | Path = ".") -> Path:
        return Path(base) / "data" / "inspecciones" / f"{self.slug}.csv"

    def selector_state_path(self, base: str | Path = ".") -> Path:
        return Path(base) / "data" / "selector" / f"{self.slug}.json"

    def to_dict(self) -> dict:
        return asdict(self)


# Sitios inventariados a partir de los repositorios LOLIUM accesibles de PREDWEEM.
# En Balcarce, Bordenave, Pergamino, San Pedro y Tres Arroyos los repositorios
# geográficos ya construyen una serie consolidada con SIGA como observación
# prioritaria y ECMWF únicamente como reemplazo provisional de huecos.
SITES: dict[str, LoliumSite] = {
    "azul": LoliumSite(
        slug="azul",
        nombre="Azul",
        provincia="Buenos Aires",
        latitud=-36.8700,
        longitud=-59.8900,
        repositorio="PREDWEEM/LOLIUM_AZUL2026",
    ),
    "balcarce": LoliumSite(
        slug="balcarce",
        nombre="Balcarce",
        provincia="Buenos Aires",
        latitud=-37.7664,
        longitud=-58.2999,
        repositorio="PREDWEEM/LOLIUM_BAL2026",
        usa_siga_historico=True,
    ),
    "bordenave": LoliumSite(
        slug="bordenave",
        nombre="Bordenave",
        provincia="Buenos Aires",
        latitud=-37.761671,
        longitud=-63.0200,
        repositorio="PREDWEEM/LOLIUM_BOR2026",
        usa_siga_historico=True,
    ),
    "lartigau": LoliumSite(
        slug="lartigau",
        nombre="Lartigau",
        provincia="Buenos Aires",
        latitud=-38.6166,
        longitud=-61.7000,
        repositorio="PREDWEEM/LOLIUM_LARTIGAU-2026",
    ),
    "olavarria": LoliumSite(
        slug="olavarria",
        nombre="Olavarría",
        provincia="Buenos Aires",
        latitud=-36.8799,
        longitud=-60.2160,
        repositorio="PREDWEEM/LOLIUM_OLAVA2026",
    ),
    "pergamino": LoliumSite(
        slug="pergamino",
        nombre="Pergamino",
        provincia="Buenos Aires",
        latitud=-33.9443,
        longitud=-60.5745,
        repositorio="PREDWEEM/LOLIUM-PERGA2026",
        usa_siga_historico=True,
    ),
    "san-pedro": LoliumSite(
        slug="san-pedro",
        nombre="San Pedro",
        provincia="Buenos Aires",
        latitud=-33.7328,
        longitud=-59.7965,
        repositorio="PREDWEEM/lolium_sanpedro2026",
        usa_siga_historico=True,
    ),
    "tres-arroyos": LoliumSite(
        slug="tres-arroyos",
        nombre="Tres Arroyos",
        provincia="Buenos Aires",
        latitud=-38.4500,
        longitud=-60.2763,
        repositorio="PREDWEEM/loliumTA_2026",
        usa_siga_historico=True,
    ),
    "zavalla": LoliumSite(
        slug="zavalla",
        nombre="Zavalla",
        provincia="Santa Fe",
        latitud=-33.02157,
        longitud=-60.87930,
        repositorio="PREDWEEM/LOLIUMZAVALLA",
        timezone="America/Argentina/Cordoba",
    ),
}

DEFAULT_SITE_SLUG = "zavalla"


def get_site(slug: str) -> LoliumSite:
    try:
        return SITES[str(slug)]
    except KeyError as exc:
        raise KeyError(f"Sitio LOLIUM desconocido: {slug}") from exc


def ordered_sites() -> list[LoliumSite]:
    return sorted(SITES.values(), key=lambda site: site.nombre.casefold())


def validate_registry() -> None:
    if DEFAULT_SITE_SLUG not in SITES:
        raise ValueError("El sitio predeterminado no existe en el catálogo.")
    slugs = [site.slug for site in SITES.values()]
    if len(slugs) != len(set(slugs)):
        raise ValueError("Existen slugs geográficos duplicados.")
    for site in SITES.values():
        if not (-90.0 <= site.latitud <= 90.0):
            raise ValueError(f"Latitud inválida para {site.nombre}.")
        if not (-180.0 <= site.longitud <= 180.0):
            raise ValueError(f"Longitud inválida para {site.nombre}.")
        if not site.repositorio.startswith("PREDWEEM/"):
            raise ValueError(f"Repositorio inválido para {site.nombre}.")
        if site.usa_siga_historico and not site.raw_meteo_url.endswith(
            "/main/meteo_daily.csv"
        ):
            raise ValueError(f"Fuente SIGA inválida para {site.nombre}.")


validate_registry()

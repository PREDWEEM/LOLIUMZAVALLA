from pathlib import Path

from sitios_lolium import DEFAULT_SITE_SLUG, SITES, get_site, ordered_sites


EXPECTED_SITES = {
    "azul",
    "balcarce",
    "bordenave",
    "lartigau",
    "olavarria",
    "pergamino",
    "san-pedro",
    "tres-arroyos",
    "zavalla",
}
EXPECTED_SIGA_SITES = {
    "balcarce",
    "bordenave",
    "pergamino",
    "san-pedro",
    "tres-arroyos",
}


def test_registry_contains_all_lolium_geographic_repositories():
    assert set(SITES) == EXPECTED_SITES
    assert DEFAULT_SITE_SLUG == "zavalla"
    assert len(ordered_sites()) == 9


def test_coordinates_and_repositories_are_valid():
    for site in ordered_sites():
        assert -90.0 <= site.latitud <= 90.0
        assert -180.0 <= site.longitud <= 180.0
        assert site.repositorio.startswith("PREDWEEM/")
        assert site.repository_url.endswith(site.repositorio)


def test_site_storage_paths_are_isolated():
    base = Path("/tmp/predweem")
    meteo_paths = {site.meteo_path(base) for site in ordered_sites()}
    inspection_paths = {site.inspections_path(base) for site in ordered_sites()}
    state_paths = {site.selector_state_path(base) for site in ordered_sites()}

    assert len(meteo_paths) == len(SITES)
    assert len(inspection_paths) == len(SITES)
    assert len(state_paths) == len(SITES)
    assert all("meteo_sitios" in path.parts for path in meteo_paths)
    assert all("inspecciones" in path.parts for path in inspection_paths)
    assert all("selector" in path.parts for path in state_paths)


def test_zavalla_and_pergamino_metadata():
    zavalla = get_site("zavalla")
    pergamino = get_site("pergamino")

    assert zavalla.provincia == "Santa Fe"
    assert zavalla.latitud == -33.02157
    assert pergamino.repositorio == "PREDWEEM/LOLIUM-PERGA2026"
    assert pergamino.longitud == -60.5745


def test_exact_sites_with_siga_history_are_registered():
    siga_sites = {
        slug for slug, site in SITES.items() if site.usa_siga_historico
    }
    assert siga_sites == EXPECTED_SIGA_SITES
    for slug in EXPECTED_SIGA_SITES:
        assert SITES[slug].raw_meteo_url.endswith("/main/meteo_daily.csv")

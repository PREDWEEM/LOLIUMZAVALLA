from sitios_lolium import DEFAULT_SITE_SLUG, SITES, get_site, ordered_sites


EXPECTED_SITE_SLUGS = {
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


def test_repository_remains_multisite() -> None:
    assert set(SITES) == EXPECTED_SITE_SLUGS
    assert len(ordered_sites()) == len(EXPECTED_SITE_SLUGS)


def test_zavalla_remains_default_site_of_integrator() -> None:
    assert DEFAULT_SITE_SLUG == "zavalla"
    assert get_site(DEFAULT_SITE_SLUG).nombre == "Zavalla"


def test_operational_model_policy_is_preserved() -> None:
    assert get_site("pergamino").modelo_operativo == "con_lag"
    assert get_site("pergamino").lag_operativo_dias == 15
    assert get_site("zavalla").modelo_operativo == "con_lag"
    assert get_site("zavalla").lag_operativo_dias == 15

    without_lag = EXPECTED_SITE_SLUGS - {"pergamino", "zavalla"}
    for slug in without_lag:
        site = get_site(slug)
        assert site.modelo_operativo == "sin_lag"
        assert site.lag_operativo_dias == 0

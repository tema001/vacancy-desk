import pytest
from src.geo import canonicalize


def test_city_keeps_lowest_token_and_english_ancestors() -> None:
    geo = canonicalize(['Київ'])

    assert geo.location == ['kyiv']
    assert geo.location_str == 'Europe, Ukraine, Kyiv'


def test_country_only() -> None:
    geo = canonicalize(['Україна'])

    assert geo.location == ['UA']
    assert geo.location_str == 'Europe, Ukraine'


def test_city_wins_over_its_country() -> None:
    geo = canonicalize(['Україна', 'Київ'])

    assert geo.location == ['kyiv']
    assert geo.location_str == 'Europe, Ukraine, Kyiv'


def test_iso3_countries() -> None:
    geo = canonicalize(['POL', 'ESP', 'PRT'])

    assert geo.location == ['PL', 'ES', 'PT']
    assert geo.location_str == 'Europe, Poland, Spain, Portugal'


def test_continent() -> None:
    geo = canonicalize(['Europe'])

    assert geo.location == ['eu']
    assert geo.location_str == 'Europe'


def test_skipped_continent_cities_are_ignored() -> None:
    assert canonicalize(['Johannesburg']).location is None
    assert canonicalize(['Auckland']).location is None
    assert canonicalize(['Buenos Aires']).location is None


def test_asia_outside_allowlist_is_ignored() -> None:
    assert canonicalize(['CHN']).location is None
    assert canonicalize(['China']).location is None
    assert canonicalize(['Beijing']).location is None
    assert canonicalize(['Iran']).location is None
    assert canonicalize(['Japan']).location is None
    assert canonicalize(['NGA']).location is None
    assert canonicalize(['Nigeria']).location is None
    assert canonicalize(['Brazil']).location is None
    assert canonicalize(['Australia']).location is None


def test_empty_and_unknown_are_none() -> None:
    assert canonicalize([]) == canonicalize(['not-a-place'])
    geo = canonicalize([])

    assert geo.location is None
    assert geo.location_str is None


@pytest.mark.parametrize(
    ('tokens', 'location', 'location_str'),
    [
        (['Львів'], ['lviv'], 'Europe, Ukraine, Lviv'),
        (['Польща'], ['PL'], 'Europe, Poland'),
        (['Чехія'], ['CZ'], 'Europe, Czechia'),
        (['Латвія'], ['LV'], 'Europe, Latvia'),
        (['Ужгород'], ['uzhhorod'], 'Europe, Ukraine, Uzhhorod'),
        (['Рівне'], ['rivne'], 'Europe, Ukraine, Rivne'),
        (['Івано-Франківськ'], ['ivano-frankivsk'], 'Europe, Ukraine, Ivano-Frankivsk'),
        (['Луцьк'], ['lutsk'], 'Europe, Ukraine, Lutsk'),
        (['ISR'], ['IL'], 'Asia, Israel'),
        (['EST'], ['EE'], 'Europe, Estonia'),
        (['ROU'], ['RO'], 'Europe, Romania'),
        (['UKR'], ['UA'], 'Europe, Ukraine'),
        (['TUR'], ['TR'], 'Asia, Turkey'),
        (['CYP'], ['CY'], 'Europe, Cyprus'),
        (['GEO'], ['GE'], 'Asia, Georgia'),
    ],
)
def test_csv_tokens(tokens: list[str], location: list[str], location_str: str) -> None:
    geo = canonicalize(tokens)

    assert geo.location == location
    assert geo.location_str == location_str

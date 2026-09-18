import pickle
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, cast

type GeoKind = Literal['continent', 'country', 'city']

COUNTRY_ALIASES = {
    'україна': 'UA',
    'украина': 'UA',
    'польща': 'PL',
    'чехія': 'CZ',
    'латвія': 'LV',
}
SKIP_CONTINENTS = frozenset({'af', 'sa', 'oc'})
ASIA_ALLOWLIST = frozenset({'AM', 'AZ', 'CY', 'GE', 'IL', 'TR'})

INDEX_PATH = Path(__file__).resolve().parent / 'data' / 'geo_index.pkl'


@dataclass(frozen=True, slots=True)
class GeoLocation:
    location: list[str] | None
    location_str: str | None


@dataclass(frozen=True, slots=True)
class _Hit:
    kind: GeoKind
    geo_id: str
    name: str
    continent_id: str
    continent_name: str
    country_id: str | None = None
    country_name: str | None = None


@dataclass(frozen=True, slots=True)
class _Country:
    iso: str
    name: str
    continent_id: str


@dataclass(frozen=True, slots=True)
class _City:
    geo_id: str
    name: str
    country_iso: str
    population: int


@dataclass(frozen=True, slots=True)
class _Continent:
    code: str
    name: str


@dataclass(slots=True)
class _GeoIndex:
    tokens: dict[str, tuple[GeoKind, str]]
    continents: dict[str, _Continent]
    countries: dict[str, _Country]
    cities: dict[str, _City]


def canonicalize(tokens: Sequence[str]) -> GeoLocation:
    hits = [_resolve(token) for token in tokens]
    found = [hit for hit in hits if hit is not None]
    if not found:
        return GeoLocation(None, None)

    cities = [hit for hit in found if hit.kind == 'city']
    countries = [hit for hit in found if hit.kind == 'country']
    continents = [hit for hit in found if hit.kind == 'continent']
    lowest = cities or countries or continents

    return GeoLocation(
        location=[hit.geo_id for hit in lowest],
        location_str=', '.join(_display_names(found)),
    )


def build_index() -> _GeoIndex:
    from geonamescache import GeonamesCache, mappings

    gc = GeonamesCache()
    countries = gc.get_countries()
    continents = gc.get_continents()

    tokens: dict[str, tuple[GeoKind, str]] = {}
    kept_continents: dict[str, _Continent] = {}
    kept_countries: dict[str, _Country] = {}
    kept_cities: dict[str, _City] = {}

    for continent in continents.values():
        continent_row = _Continent(continent['continentCode'].lower(), continent['name'])
        kept_continents[continent_row.code] = continent_row
        _put(tokens, continent['name'], 'continent', continent_row.code)
        _put(tokens, continent['asciiName'], 'continent', continent_row.code)
        _put(tokens, continent_row.code, 'continent', continent_row.code)
        for alt in continent['alternateNames']:
            _put(tokens, alt['name'], 'continent', continent_row.code)

    for country in countries.values():
        if not _keep_country(country):
            continue
        continent_id = country['continentcode'].lower()
        country_row = _Country(country['iso'], country['name'], continent_id)
        kept_countries[country_row.iso] = country_row
        _put(tokens, country['iso'], 'country', country_row.iso)
        _put(tokens, country['iso3'], 'country', country_row.iso)
        _put(tokens, country['name'], 'country', country_row.iso)

    for alias, iso in COUNTRY_ALIASES.items():
        if iso in kept_countries:
            _put(tokens, alias, 'country', iso)
    by_name = {
        country.name.casefold(): country.iso for country in kept_countries.values()
    }
    for variant, name in mappings.country_names.items():
        mapped_iso = by_name.get(name.casefold())
        if mapped_iso is not None:
            _put(tokens, variant, 'country', mapped_iso)

    for city in gc.get_cities().values():
        country = countries.get(city['countrycode'])
        if country is None:
            continue
        if not _keep_country(country):
            continue

        city_row = _City(
            city['name'].casefold(),
            city['name'],
            city['countrycode'],
            city['population'],
        )
        current = kept_cities.get(city_row.geo_id)
        if current is None or city_row.population > current.population:
            kept_cities[city_row.geo_id] = city_row

        names = {city['name']}
        names.update(alias for alias in city['alternatenames'] if alias)
        for name in names:
            _put_city(tokens, kept_cities, name, city_row)

    return _GeoIndex(tokens, kept_continents, kept_countries, kept_cities)


def save_index(index: _GeoIndex) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_bytes(pickle.dumps(index, protocol=5))


def _keep_country(country: Mapping) -> bool:
    continent_id = country['continentcode'].lower()
    if continent_id in SKIP_CONTINENTS:
        return False
    if continent_id == 'as':
        return country['iso'] in ASIA_ALLOWLIST
    return True


@cache
def _index() -> _GeoIndex:
    if not INDEX_PATH.is_file():
        raise FileNotFoundError(
            f'Geo index not found at {INDEX_PATH}. Run: python -m src.geo'
        )
    return cast(_GeoIndex, pickle.loads(INDEX_PATH.read_bytes()))  # noqa: S301


def _put(
    tokens: dict[str, tuple[GeoKind, str]],
    raw: str,
    kind: GeoKind,
    geo_id: str,
) -> None:
    key = raw.casefold()
    if len(key) < 2:
        return
    current = tokens.get(key)
    if current is None or _kind_rank(kind) < _kind_rank(current[0]):
        tokens[key] = (kind, geo_id)


def _put_city(
    tokens: dict[str, tuple[GeoKind, str]],
    cities: dict[str, _City],
    raw: str,
    city: _City,
) -> None:
    key = raw.casefold()
    if len(key) < 2:
        return
    current = tokens.get(key)
    if current is None:
        tokens[key] = ('city', city.geo_id)
        return
    if current[0] != 'city':
        return
    if city.population > cities[current[1]].population:
        tokens[key] = ('city', city.geo_id)


def _kind_rank(kind: GeoKind) -> int:
    return {'country': 0, 'continent': 1, 'city': 2}[kind]


def _resolve(token: str) -> _Hit | None:
    raw = token.strip()
    if not raw:
        return None

    idx = _index()
    match = idx.tokens.get(raw.casefold())
    if match is None:
        return None

    kind, geo_id = match
    if kind == 'continent':
        continent = idx.continents[geo_id]
        return _Hit(
            kind='continent',
            geo_id=continent.code,
            name=continent.name,
            continent_id=continent.code,
            continent_name=continent.name,
        )

    if kind == 'country':
        country = idx.countries[geo_id]
        continent = idx.continents[country.continent_id]
        return _Hit(
            kind='country',
            geo_id=country.iso,
            name=country.name,
            continent_id=continent.code,
            continent_name=continent.name,
            country_id=country.iso,
            country_name=country.name,
        )

    city = idx.cities[geo_id]
    country = idx.countries[city.country_iso]
    continent = idx.continents[country.continent_id]
    return _Hit(
        kind='city',
        geo_id=city.geo_id,
        name=city.name,
        continent_id=continent.code,
        continent_name=continent.name,
        country_id=country.iso,
        country_name=country.name,
    )


def _display_names(hits: Sequence[_Hit]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    for hit in hits:
        add(hit.continent_name)
    for hit in hits:
        add(hit.country_name)
    for hit in hits:
        if hit.kind == 'city':
            add(hit.name)

    return names


if __name__ == '__main__':
    from src.geo import build_index, save_index

    built = build_index()
    save_index(built)

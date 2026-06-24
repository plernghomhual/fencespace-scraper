import argparse
import os
import re
import sys
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

import requests

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from scripts.rate_limiter import RateLimiter

SOURCE = "geocode_countries"
TARGET_TABLE = os.environ.get("COUNTRY_GEO_TABLE", "fs_country_geocodes")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = os.environ.get(
    "NOMINATIM_USER_AGENT",
    "FenceSpace-Scraper/1.0 (https://fencespace.app)",
)
REQUEST_DELAY = float(os.environ.get("NOMINATIM_REQUEST_DELAY", "1.0"))
PAGE_SIZE = 1000
FAILURE_CACHE_KEY = "nominatim_failure_cache"
MISSING_COUNTRIES_KEY = "missing_countries"


@dataclass(frozen=True)
class CountryGeo:
    alpha2: str | None
    alpha3: str
    olympic_code: str | None
    fie_code: str | None
    display_name: str
    continent: str | None
    region: str | None
    latitude: float
    longitude: float
    source: str
    source_metadata: dict[str, Any]
    aliases: tuple[str, ...] = ()

    def with_match(self, matched: str) -> "CountryGeo":
        metadata = dict(self.source_metadata)
        metadata["matched"] = clean_text(matched)
        return replace(self, source_metadata=metadata)

    def to_row(self, *, updated_at: str) -> dict[str, Any]:
        metadata = {
            "source": self.source,
            **dict(self.source_metadata),
        }
        return {
            "alpha2": self.alpha2,
            "alpha3": self.alpha3,
            "olympic_code": self.olympic_code,
            "fie_code": self.fie_code,
            "display_name": self.display_name,
            "name": self.display_name,
            "continent": self.continent,
            "region": self.region,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "source": self.source,
            "source_metadata": self.source_metadata,
            "metadata": metadata,
            "aliases": list(self.aliases),
            "updated_at": updated_at,
        }


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def fold_text(value: Any) -> str:
    text = clean_text(value).casefold()
    normalized = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", no_marks).strip()


def country_key(value: Any) -> str:
    return fold_text(value).replace(" ", "")


def _dedupe_aliases(values: Iterable[Any]) -> tuple[str, ...]:
    seen: set[str] = set()
    aliases: list[str] = []
    for value in values:
        alias = clean_text(value)
        if not alias:
            continue
        key = fold_text(alias)
        if key in seen:
            continue
        seen.add(key)
        aliases.append(alias)
    return tuple(aliases)


def _country(
    alpha2: str | None,
    alpha3: str,
    display_name: str,
    continent: str,
    region: str,
    latitude: float,
    longitude: float,
    *,
    olympic_code: str | None = None,
    fie_code: str | None = None,
    aliases: Iterable[Any] = (),
) -> CountryGeo:
    olympic = olympic_code or alpha3
    fie = fie_code or olympic
    all_aliases = _dedupe_aliases(
        (
            alpha2,
            alpha3,
            olympic,
            fie,
            display_name,
            *tuple(aliases),
        )
    )
    return CountryGeo(
        alpha2=alpha2,
        alpha3=alpha3,
        olympic_code=olympic,
        fie_code=fie,
        display_name=display_name,
        continent=continent,
        region=region,
        latitude=latitude,
        longitude=longitude,
        source="static",
        source_metadata={
            "dataset": "embedded_iso_noc_centroids",
            "centroid": "country",
        },
        aliases=all_aliases,
    )


STATIC_COUNTRIES: tuple[CountryGeo, ...] = (
    _country("US", "USA", "United States", "North America", "Americas", 39.8283, -98.5795, aliases=("United States of America", "USA", "U.S.A.")),
    _country("CA", "CAN", "Canada", "North America", "Americas", 56.1304, -106.3468),
    _country("MX", "MEX", "Mexico", "North America", "Americas", 23.6345, -102.5528),
    _country("PR", "PRI", "Puerto Rico", "North America", "Americas", 18.2208, -66.5901),
    _country("DO", "DOM", "Dominican Republic", "North America", "Americas", 18.7357, -70.1627),
    _country("JM", "JAM", "Jamaica", "North America", "Americas", 18.1096, -77.2975),
    _country("CU", "CUB", "Cuba", "North America", "Americas", 21.5218, -77.7812),
    _country("GT", "GTM", "Guatemala", "North America", "Americas", 15.7835, -90.2308, olympic_code="GUA", fie_code="GUA"),
    _country("CR", "CRI", "Costa Rica", "North America", "Americas", 9.7489, -83.7534, olympic_code="CRC", fie_code="CRC"),
    _country("PA", "PAN", "Panama", "North America", "Americas", 8.5380, -80.7821),
    _country("SV", "SLV", "El Salvador", "North America", "Americas", 13.7942, -88.8965, olympic_code="ESA", fie_code="ESA"),
    _country("HN", "HND", "Honduras", "North America", "Americas", 15.2000, -86.2419, olympic_code="HON", fie_code="HON"),
    _country("NI", "NIC", "Nicaragua", "North America", "Americas", 12.8654, -85.2072),
    _country("TT", "TTO", "Trinidad and Tobago", "North America", "Americas", 10.6918, -61.2225, olympic_code="TTO", fie_code="TTO", aliases=("Trinidad",)),
    _country("BB", "BRB", "Barbados", "North America", "Americas", 13.1939, -59.5432, olympic_code="BAR", fie_code="BAR"),
    _country("BS", "BHS", "Bahamas", "North America", "Americas", 25.0343, -77.3963, olympic_code="BAH", fie_code="BAH"),
    _country("AW", "ABW", "Aruba", "North America", "Americas", 12.5211, -69.9683, olympic_code="ARU", fie_code="ARU"),
    _country("AR", "ARG", "Argentina", "South America", "Americas", -38.4161, -63.6167),
    _country("BR", "BRA", "Brazil", "South America", "Americas", -14.2350, -51.9253),
    _country("CL", "CHL", "Chile", "South America", "Americas", -35.6751, -71.5430, olympic_code="CHI", fie_code="CHI"),
    _country("CO", "COL", "Colombia", "South America", "Americas", 4.5709, -74.2973),
    _country("VE", "VEN", "Venezuela", "South America", "Americas", 6.4238, -66.5897),
    _country("PE", "PER", "Peru", "South America", "Americas", -9.1900, -75.0152),
    _country("UY", "URY", "Uruguay", "South America", "Americas", -32.5228, -55.7658, olympic_code="URU", fie_code="URU"),
    _country("PY", "PRY", "Paraguay", "South America", "Americas", -23.4425, -58.4438, olympic_code="PAR", fie_code="PAR"),
    _country("BO", "BOL", "Bolivia", "South America", "Americas", -16.2902, -63.5887),
    _country("EC", "ECU", "Ecuador", "South America", "Americas", -1.8312, -78.1834),
    _country("GB", "GBR", "Great Britain", "Europe", "Europe", 55.3781, -3.4360, aliases=("United Kingdom", "UK", "England", "Scotland", "Wales", "Northern Ireland")),
    _country("FR", "FRA", "France", "Europe", "Europe", 46.2276, 2.2137),
    _country("IT", "ITA", "Italy", "Europe", "Europe", 41.8719, 12.5674),
    _country("DE", "DEU", "Germany", "Europe", "Europe", 51.1657, 10.4515, olympic_code="GER", fie_code="GER"),
    _country("ES", "ESP", "Spain", "Europe", "Europe", 40.4637, -3.7492),
    _country("PT", "PRT", "Portugal", "Europe", "Europe", 39.3999, -8.2245, olympic_code="POR", fie_code="POR"),
    _country("IE", "IRL", "Ireland", "Europe", "Europe", 53.1424, -7.6921),
    _country("NL", "NLD", "Netherlands", "Europe", "Europe", 52.1326, 5.2913, olympic_code="NED", fie_code="NED", aliases=("Holland",)),
    _country("BE", "BEL", "Belgium", "Europe", "Europe", 50.5039, 4.4699),
    _country("LU", "LUX", "Luxembourg", "Europe", "Europe", 49.8153, 6.1296),
    _country("CH", "CHE", "Switzerland", "Europe", "Europe", 46.8182, 8.2275, olympic_code="SUI", fie_code="SUI"),
    _country("AT", "AUT", "Austria", "Europe", "Europe", 47.5162, 14.5501),
    _country("HU", "HUN", "Hungary", "Europe", "Europe", 47.1625, 19.5033),
    _country("RO", "ROU", "Romania", "Europe", "Europe", 45.9432, 24.9668),
    _country("PL", "POL", "Poland", "Europe", "Europe", 51.9194, 19.1451),
    _country("CZ", "CZE", "Czechia", "Europe", "Europe", 49.8175, 15.4730, aliases=("Czech Republic",)),
    _country("SK", "SVK", "Slovakia", "Europe", "Europe", 48.6690, 19.6990),
    _country("SI", "SVN", "Slovenia", "Europe", "Europe", 46.1512, 14.9955, olympic_code="SLO", fie_code="SLO"),
    _country("HR", "HRV", "Croatia", "Europe", "Europe", 45.1000, 15.2000, olympic_code="CRO", fie_code="CRO"),
    _country("RS", "SRB", "Serbia", "Europe", "Europe", 44.0165, 21.0059),
    _country("BG", "BGR", "Bulgaria", "Europe", "Europe", 42.7339, 25.4858, olympic_code="BUL", fie_code="BUL"),
    _country("GR", "GRC", "Greece", "Europe", "Europe", 39.0742, 21.8243, olympic_code="GRE", fie_code="GRE"),
    _country("CY", "CYP", "Cyprus", "Europe", "Europe", 35.1264, 33.4299),
    _country("MT", "MLT", "Malta", "Europe", "Europe", 35.9375, 14.3754),
    _country("IS", "ISL", "Iceland", "Europe", "Europe", 64.9631, -19.0208, olympic_code="ISL", fie_code="ISL"),
    _country("NO", "NOR", "Norway", "Europe", "Europe", 60.4720, 8.4689),
    _country("SE", "SWE", "Sweden", "Europe", "Europe", 60.1282, 18.6435),
    _country("FI", "FIN", "Finland", "Europe", "Europe", 61.9241, 25.7482),
    _country("DK", "DNK", "Denmark", "Europe", "Europe", 56.2639, 9.5018, olympic_code="DEN", fie_code="DEN"),
    _country("EE", "EST", "Estonia", "Europe", "Europe", 58.5953, 25.0136),
    _country("LV", "LVA", "Latvia", "Europe", "Europe", 56.8796, 24.6032, olympic_code="LAT", fie_code="LAT"),
    _country("LT", "LTU", "Lithuania", "Europe", "Europe", 55.1694, 23.8813),
    _country("UA", "UKR", "Ukraine", "Europe", "Europe", 48.3794, 31.1656),
    _country("RU", "RUS", "Russia", "Europe", "Europe", 61.5240, 105.3188, aliases=("Russian Federation", "ROC")),
    _country("BY", "BLR", "Belarus", "Europe", "Europe", 53.7098, 27.9534),
    _country("TR", "TUR", "Turkey", "Asia", "Europe/Asia", 38.9637, 35.2433, aliases=("Turkiye", "Türkiye")),
    _country("AL", "ALB", "Albania", "Europe", "Europe", 41.1533, 20.1683),
    _country("BA", "BIH", "Bosnia and Herzegovina", "Europe", "Europe", 43.9159, 17.6791),
    _country("ME", "MNE", "Montenegro", "Europe", "Europe", 42.7087, 19.3744),
    _country("MK", "MKD", "North Macedonia", "Europe", "Europe", 41.6086, 21.7453, aliases=("Macedonia",)),
    _country("MD", "MDA", "Moldova", "Europe", "Europe", 47.4116, 28.3699),
    _country("MC", "MCO", "Monaco", "Europe", "Europe", 43.7384, 7.4246),
    _country("LI", "LIE", "Liechtenstein", "Europe", "Europe", 47.1660, 9.5554),
    _country("SM", "SMR", "San Marino", "Europe", "Europe", 43.9424, 12.4578),
    _country("AD", "AND", "Andorra", "Europe", "Europe", 42.5063, 1.5218),
    _country("CN", "CHN", "China", "Asia", "Asia", 35.8617, 104.1954),
    _country("HK", "HKG", "Hong Kong", "Asia", "Asia", 22.3193, 114.1694, aliases=("Hong Kong China", "Hong Kong, China")),
    _country("TW", "TWN", "Chinese Taipei", "Asia", "Asia", 23.6978, 120.9605, olympic_code="TPE", fie_code="TPE", aliases=("Taiwan", "Republic of China")),
    _country("JP", "JPN", "Japan", "Asia", "Asia", 36.2048, 138.2529),
    _country("KR", "KOR", "South Korea", "Asia", "Asia", 35.9078, 127.7669, aliases=("Korea", "Republic of Korea")),
    _country("SG", "SGP", "Singapore", "Asia", "Asia", 1.3521, 103.8198),
    _country("TH", "THA", "Thailand", "Asia", "Asia", 15.8700, 100.9925),
    _country("MY", "MYS", "Malaysia", "Asia", "Asia", 4.2105, 101.9758, olympic_code="MAS", fie_code="MAS"),
    _country("ID", "IDN", "Indonesia", "Asia", "Asia", -0.7893, 113.9213, olympic_code="INA", fie_code="INA"),
    _country("PH", "PHL", "Philippines", "Asia", "Asia", 12.8797, 121.7740, olympic_code="PHI", fie_code="PHI"),
    _country("VN", "VNM", "Vietnam", "Asia", "Asia", 14.0583, 108.2772, olympic_code="VIE", fie_code="VIE"),
    _country("IN", "IND", "India", "Asia", "Asia", 20.5937, 78.9629),
    _country("PK", "PAK", "Pakistan", "Asia", "Asia", 30.3753, 69.3451),
    _country("IR", "IRN", "Iran", "Asia", "Asia", 32.4279, 53.6880, aliases=("Islamic Republic of Iran",)),
    _country("IL", "ISR", "Israel", "Asia", "Asia", 31.0461, 34.8516),
    _country("KZ", "KAZ", "Kazakhstan", "Asia", "Asia", 48.0196, 66.9237),
    _country("UZ", "UZB", "Uzbekistan", "Asia", "Asia", 41.3775, 64.5853),
    _country("KG", "KGZ", "Kyrgyzstan", "Asia", "Asia", 41.2044, 74.7661),
    _country("AZ", "AZE", "Azerbaijan", "Asia", "Asia", 40.1431, 47.5769),
    _country("GE", "GEO", "Georgia", "Asia", "Europe/Asia", 42.3154, 43.3569),
    _country("AM", "ARM", "Armenia", "Asia", "Europe/Asia", 40.0691, 45.0382),
    _country("QA", "QAT", "Qatar", "Asia", "Asia", 25.3548, 51.1839),
    _country("AE", "ARE", "United Arab Emirates", "Asia", "Asia", 23.4241, 53.8478, olympic_code="UAE", fie_code="UAE"),
    _country("SA", "SAU", "Saudi Arabia", "Asia", "Asia", 23.8859, 45.0792, aliases=("KSA",)),
    _country("AU", "AUS", "Australia", "Oceania", "Oceania", -25.2744, 133.7751),
    _country("NZ", "NZL", "New Zealand", "Oceania", "Oceania", -40.9006, 174.8860),
    _country("EG", "EGY", "Egypt", "Africa", "Africa", 26.8206, 30.8025),
    _country("MA", "MAR", "Morocco", "Africa", "Africa", 31.7917, -7.0926),
    _country("TN", "TUN", "Tunisia", "Africa", "Africa", 33.8869, 9.5375),
    _country("ZA", "ZAF", "South Africa", "Africa", "Africa", -30.5595, 22.9375, olympic_code="RSA", fie_code="RSA"),
    _country("CI", "CIV", "Cote d'Ivoire", "Africa", "Africa", 7.5400, -5.5471, aliases=("Côte d'Ivoire", "Ivory Coast")),
    _country("DZ", "DZA", "Algeria", "Africa", "Africa", 28.0339, 1.6596, olympic_code="ALG", fie_code="ALG"),
    _country("SN", "SEN", "Senegal", "Africa", "Africa", 14.4974, -14.4524),
    _country("NG", "NGA", "Nigeria", "Africa", "Africa", 9.0820, 8.6753),
)


def _build_static_index() -> dict[str, CountryGeo]:
    index: dict[str, CountryGeo] = {}
    for country in STATIC_COUNTRIES:
        for alias in country.aliases:
            index.setdefault(fold_text(alias), country)
            index.setdefault(country_key(alias), country)
    return index


STATIC_INDEX = _build_static_index()


def lookup_static_country(value: Any) -> CountryGeo | None:
    text = clean_text(value)
    if not text:
        return None
    match = STATIC_INDEX.get(fold_text(text)) or STATIC_INDEX.get(country_key(text))
    return match.with_match(text) if match else None


def _state_dict(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        country_key(key): dict(entry)
        for key, entry in value.items()
        if country_key(key) and isinstance(entry, dict)
    }


def _new_failure_entry(country: str, reason: str, *, updated_at: str | None = None) -> dict[str, Any]:
    return {
        "country": clean_text(country),
        "reason": reason,
        "failed_at": updated_at or datetime.now(UTC).isoformat(),
    }


def parse_nominatim_country(raw_country: str, payload: Any) -> CountryGeo | None:
    if isinstance(payload, CountryGeo):
        return payload
    if isinstance(payload, list):
        row = payload[0] if payload else None
    else:
        row = payload
    if not isinstance(row, dict):
        return None

    try:
        latitude = float(row["lat"])
        longitude = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    _raw_address = row.get("address")
    address: dict[Any, Any] = _raw_address if isinstance(_raw_address, dict) else {}
    alpha2 = clean_text(address.get("country_code")).upper() or None
    display_name = (
        clean_text(address.get("country"))
        or clean_text(row.get("display_name")).split(",")[0]
        or clean_text(raw_country)
    )

    raw = clean_text(raw_country).upper()
    alpha3 = raw if re.fullmatch(r"[A-Z]{3}", raw) else ""
    if not alpha3:
        static_from_display = lookup_static_country(display_name)
        if static_from_display:
            return replace(
                static_from_display,
                latitude=latitude,
                longitude=longitude,
                source="nominatim",
                source_metadata=_nominatim_metadata(row, raw_country),
            )
        return None

    return CountryGeo(
        alpha2=alpha2,
        alpha3=alpha3,
        olympic_code=alpha3,
        fie_code=alpha3,
        display_name=display_name,
        continent=None,
        region=None,
        latitude=latitude,
        longitude=longitude,
        source="nominatim",
        source_metadata=_nominatim_metadata(row, raw_country),
        aliases=_dedupe_aliases((raw_country, alpha2, alpha3, display_name)),
    )


def _nominatim_metadata(row: dict[str, Any], query: str) -> dict[str, Any]:
    nominatim = {
        key: row[key]
        for key in ("display_name", "osm_type", "osm_id", "place_id")
        if key in row
    }
    return {
        "query": clean_text(query),
        "nominatim": nominatim,
    }


def _retry_after_seconds(value: str | None) -> float:
    try:
        return max(float(value or REQUEST_DELAY), REQUEST_DELAY)
    except (TypeError, ValueError):
        return REQUEST_DELAY


def nominatim_geocode_country(
    country: str,
    *,
    session: Any | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
    limiter: RateLimiter | None = None,
    user_agent: str = NOMINATIM_USER_AGENT,
    max_retries: int = 1,
) -> Any | None:
    http = session or requests.Session()
    rate_limiter = limiter or RateLimiter(default_rps=1.0, jitter=0.0, backoff=5.0)
    params = {
        "q": clean_text(country),
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    }
    headers = {"User-Agent": user_agent}

    for attempt in range(max_retries + 1):
        try:
            rate_limiter.wait("nominatim.openstreetmap.org", rps=1.0)
            response = http.get(
                NOMINATIM_URL,
                params=params,
                headers=headers,
                timeout=20,
            )
            if response.status_code == 429 and attempt < max_retries:
                rate_limiter.record_failure("nominatim.openstreetmap.org")
                sleep_func(_retry_after_seconds(response.headers.get("Retry-After")))
                continue
            response.raise_for_status()
            rate_limiter.record_success("nominatim.openstreetmap.org")
            return response.json()
        except Exception as exc:
            rate_limiter.record_failure("nominatim.openstreetmap.org")
            print(f"  Nominatim country geocode failed for {country}: {exc}")
            return None
    return None


def resolve_country_geo(
    country: Any,
    *,
    geocoder: Callable[[str], Any | None] | None = None,
    allow_network: bool = True,
) -> CountryGeo | None:
    text = clean_text(country)
    if not text:
        return None

    static = lookup_static_country(text)
    if static:
        return static

    if not allow_network:
        return None

    geocode = geocoder or nominatim_geocode_country
    payload = geocode(text)
    return parse_nominatim_country(text, payload)


def fetch_all(query: Any, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


COUNTRY_SOURCES = (
    ("fs_fencers", "country"),
    ("fs_tournaments", "country"),
    ("fs_medal_tables", "country"),
)


def collect_country_values(client: Any) -> list[str]:
    countries: set[str] = set()
    for table, column in COUNTRY_SOURCES:
        try:
            rows = fetch_all(client.table(table).select(column))
        except Exception as exc:
            print(f"  Could not fetch {table}.{column}: {exc}")
            continue
        for row in rows:
            country = clean_text(row.get(column))
            if country:
                countries.add(country)
    return sorted(countries, key=lambda value: fold_text(value))


def upsert_country_row(client: Any, row: dict[str, Any], *, target_table: str = TARGET_TABLE) -> None:
    client.table(target_table).upsert(row, on_conflict="alpha3").execute()


def backfill_country_geocodes(
    client: Any,
    *,
    target_table: str = TARGET_TABLE,
    geocoder: Callable[[str], Any | None] | None = None,
    allow_network: bool = True,
    dry_run: bool = False,
    sleep_func: Callable[[float], None] = time.sleep,
    request_delay: float = REQUEST_DELAY,
    updated_at: str | None = None,
    state_get: Callable[[str, str], Any] = get_state,
    state_set: Callable[[str, str, Any], None] = set_state,
) -> dict[str, int]:
    timestamp = updated_at or datetime.now(UTC).isoformat()
    countries = collect_country_values(client)
    failure_cache = _state_dict(state_get(SOURCE, FAILURE_CACHE_KEY))
    missing_countries: set[str] = set()
    rows_by_alpha3: dict[str, dict[str, Any]] = {}
    skipped = 0
    failed = 0
    network_requests = 0

    for country in countries:
        key = country_key(country)
        if key in failure_cache:
            missing_countries.add(country)
            skipped += 1
            continue

        resolved = lookup_static_country(country)
        if not resolved and allow_network and not dry_run:
            if network_requests > 0:
                sleep_func(request_delay)
            network_requests += 1
            resolved = resolve_country_geo(country, geocoder=geocoder, allow_network=True)

        if not resolved:
            missing_countries.add(country)
            skipped += 1
            if allow_network and not dry_run:
                failed += 1
                failure_cache[key] = _new_failure_entry(
                    country,
                    "no_result",
                    updated_at=timestamp,
                )
            continue

        failure_cache.pop(key, None)
        rows_by_alpha3.setdefault(resolved.alpha3, resolved.to_row(updated_at=timestamp))

    written = 0
    if not dry_run:
        for row in rows_by_alpha3.values():
            try:
                upsert_country_row(client, row, target_table=target_table)
                written += 1
            except Exception as exc:
                failed += 1
                print(f"  Country geo upsert failed for {row.get('alpha3')}: {exc}")

    summary = {
        "countries_seen": len(countries),
        "resolved": len(rows_by_alpha3),
        "written": written,
        "failed": failed,
        "skipped": skipped,
    }
    state_set(SOURCE, FAILURE_CACHE_KEY, failure_cache)
    state_set(SOURCE, MISSING_COUNTRIES_KEY, sorted(missing_countries, key=fold_text))
    state_set(SOURCE, "last_run", {"updated_at": timestamp, **summary})
    return summary


def get_supabase_client() -> Any:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(url, key)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill country geocodes for medal heatmaps.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve countries without writing rows.")
    parser.add_argument("--no-network", action="store_true", help="Skip Nominatim fallback for static misses.")
    parser.add_argument("--table", default=TARGET_TABLE, help=f"Target table, default {TARGET_TABLE}.")
    args = parser.parse_args()

    run_log = ScraperRunLogger(SOURCE).start()
    try:
        summary = backfill_country_geocodes(
            get_supabase_client(),
            target_table=args.table,
            allow_network=not args.no_network,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise

    run_log.complete(
        written=summary["written"],
        failed=summary["failed"],
        skipped=summary["skipped"],
        metadata=summary,
    )
    print(
        "Country geocode backfill complete - "
        f"seen={summary['countries_seen']}, resolved={summary['resolved']}, "
        f"written={summary['written']}, failed={summary['failed']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

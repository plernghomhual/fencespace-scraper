"""Country-code lookup helpers for FenceSpace scrapers and analytics.

Import this module instead of adding local one-off country maps:

    from scripts.country_codes import lookup_country, to_alpha3

The seed data lives in `supabase/migrations/20260602_country_codes.sql` inside
the `$country_codes$` JSON block. Keeping one parseable data block gives the
database migration and Python helpers the same source of truth.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260602_country_codes.sql"
)


@dataclass(frozen=True)
class CountryCode:
    alpha3: str
    alpha2: str | None
    name: str
    region: str | None
    continent: str | None
    flag_emoji: str | None
    olympic_code: str | None
    fie_code: str | None
    aliases: tuple[str, ...]
    latitude: float | None
    longitude: float | None

    def to_seed_row(self) -> dict[str, object]:
        return {
            "alpha3": self.alpha3,
            "alpha2": self.alpha2,
            "name": self.name,
            "region": self.region,
            "continent": self.continent,
            "flag_emoji": self.flag_emoji,
            "olympic_code": self.olympic_code,
            "fie_code": self.fie_code,
            "aliases": list(self.aliases),
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


def _flag_emoji(alpha2: str | None) -> str | None:
    if not alpha2 or len(alpha2) != 2 or not alpha2.isalpha():
        return None
    return "".join(chr(ord(letter.upper()) + 127397) for letter in alpha2)


def _load_seed_rows() -> list[dict[str, object]]:
    sql = MIGRATION_PATH.read_text()
    match = re.search(r"\$country_codes\$(?P<json>.*?)\$country_codes\$", sql, re.S)
    if not match:
        raise RuntimeError(f"country-code seed block not found in {MIGRATION_PATH}")
    rows = json.loads(match.group("json"))
    if not isinstance(rows, list):
        raise RuntimeError("country-code seed block must be a JSON array")
    return rows


def _country_from_row(row: dict[str, object]) -> CountryCode:
    alpha2 = row.get("alpha2")
    flag = row.get("flag_emoji") or _flag_emoji(alpha2 if isinstance(alpha2, str) else None)
    aliases = row.get("aliases") or ()
    if not isinstance(aliases, list | tuple):
        raise RuntimeError(f"aliases must be a list for {row.get('alpha3')}")
    return CountryCode(
        alpha3=str(row["alpha3"]).upper(),
        alpha2=str(alpha2).upper() if alpha2 else None,
        name=str(row["name"]),
        region=str(row["region"]) if row.get("region") else None,
        continent=str(row["continent"]) if row.get("continent") else None,
        flag_emoji=str(flag) if flag else None,
        olympic_code=str(row["olympic_code"]).upper() if row.get("olympic_code") else None,
        fie_code=str(row["fie_code"]).upper() if row.get("fie_code") else None,
        aliases=tuple(str(alias) for alias in aliases),
        latitude=float(row["latitude"]) if row.get("latitude") is not None else None,  # type: ignore[arg-type]
        longitude=float(row["longitude"]) if row.get("longitude") is not None else None,  # type: ignore[arg-type]
    )


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.replace("\u00a0", " ").strip()
    if not text:
        return None
    return re.sub(r"\s+", " ", text)


def _normalize_code(value: object) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    normalized = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    code = re.sub(r"[^A-Za-z0-9]", "", normalized).upper()
    return code or None


def _normalize_alias(value: object) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    text = re.sub(r"\([^)]*\)", "", text)
    normalized = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    key = re.sub(r"[^A-Za-z0-9]+", "", normalized).upper()
    return key or None


def _add_unique(index: dict[str, CountryCode], key: str | None, country: CountryCode, label: str) -> None:
    if not key:
        return
    existing = index.get(key)
    if existing and existing.alpha3 != country.alpha3:
        raise RuntimeError(
            f"conflicting {label} lookup {key}: {existing.alpha3} and {country.alpha3}"
        )
    index[key] = country


def _build_indexes(countries: tuple[CountryCode, ...]):
    by_alpha3: dict[str, CountryCode] = {}
    by_alpha2: dict[str, CountryCode] = {}
    by_olympic: dict[str, CountryCode] = {}
    by_fie: dict[str, CountryCode] = {}
    by_alias: dict[str, CountryCode] = {}

    for country in countries:
        _add_unique(by_alpha3, _normalize_code(country.alpha3), country, "alpha3")
        _add_unique(by_alpha2, _normalize_code(country.alpha2), country, "alpha2")
        _add_unique(by_olympic, _normalize_code(country.olympic_code), country, "olympic_code")
        _add_unique(by_fie, _normalize_code(country.fie_code), country, "fie_code")
        _add_unique(by_alias, _normalize_alias(country.name), country, "alias")
        for alias in country.aliases:
            _add_unique(by_alias, _normalize_alias(alias), country, "alias")

    return by_alpha3, by_alpha2, by_olympic, by_fie, by_alias


COUNTRY_CODES = tuple(_country_from_row(row) for row in _load_seed_rows())
_BY_ALPHA3, _BY_ALPHA2, _BY_OLYMPIC, _BY_FIE, _BY_ALIAS = _build_indexes(COUNTRY_CODES)


def country_seed_rows() -> list[dict[str, object]]:
    return [country.to_seed_row() for country in COUNTRY_CODES]


def lookup_by_alpha3(value: object) -> CountryCode | None:
    return _BY_ALPHA3.get(_normalize_code(value) or "")


def lookup_by_alpha2(value: object) -> CountryCode | None:
    return _BY_ALPHA2.get(_normalize_code(value) or "")


def lookup_by_olympic_code(value: object) -> CountryCode | None:
    return _BY_OLYMPIC.get(_normalize_code(value) or "")


def lookup_by_fie_code(value: object) -> CountryCode | None:
    return _BY_FIE.get(_normalize_code(value) or "")


def lookup_by_alias(value: object) -> CountryCode | None:
    return _BY_ALIAS.get(_normalize_alias(value) or "")


def lookup_country(value: object) -> CountryCode | None:
    code = _normalize_code(value)
    if code:
        for index in (_BY_ALPHA3, _BY_ALPHA2, _BY_OLYMPIC, _BY_FIE):
            country = index.get(code)
            if country:
                return country
    alias = _normalize_alias(value)
    return _BY_ALIAS.get(alias or "")


def to_alpha3(value: object, *, preserve_unknown_code: bool = True) -> str | None:
    country = lookup_country(value)
    if country:
        return country.alpha3
    code = _normalize_code(value)
    if preserve_unknown_code and code and re.fullmatch(r"[A-Z0-9]{3}", code):
        return code
    return None


def country_display_name(value: object) -> str | None:
    country = lookup_country(value)
    if country:
        return country.name
    text = _normalize_text(value)
    if not text:
        return None
    return to_alpha3(text) or text

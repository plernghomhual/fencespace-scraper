import os
import re
import time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

_supabase = None


def get_supabase():
    global _supabase
    if _supabase is None and SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


WEAPON_ALIASES = {
    "foil": "Foil", "fleuret": "Foil", "fioretto": "Foil", "florett": "Foil",
    "epee": "Epee", "degen": "Epee", "estoc": "Epee",
    "sabre": "Sabre", "saber": "Sabre", "sciabola": "Sabre", "sabel": "Sabre",
}
GENDER_ALIASES = {
    "men": "Men", "m": "Men", "male": "Men", "hommes": "Men", "herren": "Men",
    "manner": "Men", "uomini": "Men",
    "women": "Women", "w": "Women", "f": "Women", "female": "Women",
    "dames": "Women", "femmes": "Women", "damen": "Women", "frauen": "Women", "donne": "Women",
}
CATEGORY_ALIASES = {
    "senior": "Senior", "s": "Senior", "senioren": "Senior", "seniores": "Senior",
    "junior": "Junior", "j": "Junior", "u20": "Junior", "u21": "Junior",
    "cadet": "Cadet", "c": "Cadet", "u17": "Cadet", "u18": "Cadet",
    "veteran": "Veteran", "v": "Veteran", "masters": "Veteran",
}


def _strip_accents(s: str) -> str:
    replacements = {"é": "e", "è": "e", "ê": "e", "ë": "e",
                    "à": "a", "â": "a", "ä": "a",
                    "ö": "o", "ü": "u", "ï": "i", "ô": "o"}
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    return s


def normalize_weapon(raw: str) -> str | None:
    key = re.sub(r"[^a-z]", "", _strip_accents(raw.lower()))
    return WEAPON_ALIASES.get(key) or WEAPON_ALIASES.get(raw.lower())


def normalize_gender(raw: str) -> str | None:
    return GENDER_ALIASES.get(raw.lower().strip())


def normalize_category(raw: str) -> str | None:
    return CATEGORY_ALIASES.get(raw.lower().strip())


def build_ranking_row(
    *,
    source: str,
    season: str,
    weapon: str,
    gender: str,
    category: str,
    rank: int,
    name: str,
    country: str | None = None,
    club: str | None = None,
    points: float | None = None,
    fie_id: str | None = None,
    fencer_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "source": source,
        "season": season,
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "rank": rank,
        "name": name,
        "country": country,
        "club": club,
        "points": points,
        "fie_id": fie_id,
        "fencer_id": fencer_id,
        "metadata": metadata or {},
    }


def match_fencer(name: str, country: str | None, fie_id: str | None) -> str | None:
    client = get_supabase()
    if not client:
        return None
    try:
        if fie_id:
            rows = client.table("fs_fencers").select("id").eq("fie_id", fie_id).limit(1).execute().data
            if rows:
                return rows[0]["id"]
        if name and country:
            rows = client.table("fs_fencers").select("id").ilike("name", name).eq("country", country).limit(1).execute().data
            if rows:
                return rows[0]["id"]
    except Exception:
        pass
    return None


def write_rankings(rows: list[dict], source: str, season: str) -> int:
    client = get_supabase()
    if not client or not rows:
        return 0
    enriched = []
    for row in rows:
        if not row.get("fencer_id"):
            row = dict(row)
            row["fencer_id"] = match_fencer(row.get("name", ""), row.get("country"), row.get("fie_id"))
        enriched.append(row)

    seen_keys: set = set()
    deduped = []
    for row in enriched:
        key = (row.get("source"), row.get("season"), row.get("weapon"),
               row.get("gender"), row.get("category"), row.get("rank"))
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(row)

    written = 0
    for i in range(0, len(deduped), 100):
        batch = deduped[i:i + 100]
        try:
            client.table("fs_national_fed_rankings").upsert(
                batch, on_conflict="source,season,weapon,gender,category,rank"
            ).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Upsert batch failed: {exc}")
    return written

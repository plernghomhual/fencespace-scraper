import html
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import requests
from supabase import create_client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FIE_BASE_URL = "https://fie.org/athletes"
MAX_FENCERS = int(os.environ.get("FIE_PROFILE_LIMIT", "1000"))
REQUEST_DELAY_SECONDS = float(os.environ.get("FIE_PROFILE_DELAY", "1.5"))
BATCH_SIZE = int(os.environ.get("FIE_PROFILE_BATCH_SIZE", "50"))
FORCE_RESCRAPE = os.environ.get("FIE_PROFILE_FORCE_RESCRAPE", "").lower() in {"1", "true", "yes"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fie.org/athletes",
}

BASE_SELECT_COLUMNS = [
    "fie_id",
    "name",
    "world_rank",
    "club",
    "image_url",
    "metadata",
]
DATE_COLUMN_CANDIDATES = ["date_of_birth", "birth_date", "dob"]
HAND_COLUMN_CANDIDATES = ["hand", "handedness"]


@dataclass
class AthleteProfile:
    club: str | None = None
    image_url: str | None = None
    date_of_birth: str | None = None
    hand: str | None = None

    def fields_found(self) -> list[str]:
        return [field for field in ["club", "image_url", "date_of_birth", "hand"] if getattr(self, field)]


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "")).replace("\xa0", " ")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_label(value: str | None) -> str:
    text = clean_text(value) or ""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def normalize_hand(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower().strip()
    if key in {"r", "right", "right handed", "right-handed", "hand_r"}:
        return "right"
    if key in {"l", "left", "left handed", "left-handed", "hand_l"}:
        return "left"
    return None


def parse_date_value(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None

    text = re.sub(r"\s+00:00:00$", "", text)
    date_match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", text)
    if date_match:
        text = date_match.group(1)

    for fmt in [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]:
        try:
            parsed = datetime.strptime(text, fmt).date()
            if 1900 <= parsed.year <= date.today().year:
                return parsed.isoformat()
        except Exception:
            continue
    return None


def age_on_today(birthdate: date) -> int:
    today = date.today()
    age = today.year - birthdate.year
    if (today.month, today.day) < (birthdate.month, birthdate.day):
        age -= 1
    return age


def parse_birthdate_from_license(license_number: str | None, page_age: str | None) -> str | None:
    text = clean_text(license_number)
    if not text:
        return None

    digits = re.sub(r"\D", "", text)
    if len(digits) < 8:
        return None

    try:
        parsed = datetime.strptime(digits[:8], "%d%m%Y").date()
    except Exception:
        return None

    if not 1900 <= parsed.year <= date.today().year:
        return None

    age_text = clean_text(page_age)
    if age_text and age_text.isdigit():
        if abs(age_on_today(parsed) - int(age_text)) > 1:
            return None

    return parsed.isoformat()


def absolute_url(url: str | None) -> str | None:
    text = clean_text(url)
    if not text:
        return None
    text = text.strip("\"'")
    if text.startswith("//"):
        return f"https:{text}"
    if text.startswith("/"):
        return f"https://fie.org{text}"
    return text


def iter_window_json_blocks(page_html: str):
    decoder = json.JSONDecoder()
    skip_names = {"__translations__", "dataLayer", "_headToHead", "_tabRanking", "_tabResults", "_tabOpponents"}

    for match in re.finditer(r"window\.([A-Za-z0-9_$]+)\s*=", page_html):
        name = match.group(1)
        if name in skip_names:
            continue

        offset = match.end()
        while offset < len(page_html) and page_html[offset].isspace():
            offset += 1
        if offset >= len(page_html) or page_html[offset] not in "[{":
            continue

        try:
            block, _ = decoder.raw_decode(page_html[offset:])
            yield block
        except Exception:
            continue


def extract_from_json_blocks(page_html: str) -> AthleteProfile:
    profile = AthleteProfile()

    key_groups = {
        "club": {"club", "clubname", "clubteam", "team", "teamname", "federation", "federationname"},
        "image_url": {"image", "imageurl", "photourl", "photo", "picture", "profileimage", "avatar"},
        "date_of_birth": {"dateofbirth", "birthdate", "birth_date", "dob", "born"},
        "hand": {"hand", "handedness"},
    }

    def walk(value: Any):
        if isinstance(value, dict):
            for raw_key, raw_value in value.items():
                key = re.sub(r"[^a-z0-9]+", "", str(raw_key).lower())
                scalar = raw_value if isinstance(raw_value, (str, int, float)) else None

                if scalar is not None:
                    if not profile.club and key in key_groups["club"]:
                        profile.club = clean_text(scalar)
                    elif not profile.image_url and key in key_groups["image_url"]:
                        candidate = absolute_url(str(scalar))
                        if candidate and "/bg-default" not in candidate:
                            profile.image_url = candidate
                    elif not profile.date_of_birth and key in key_groups["date_of_birth"]:
                        profile.date_of_birth = parse_date_value(str(scalar))
                    elif not profile.hand and key in key_groups["hand"]:
                        profile.hand = normalize_hand(str(scalar))

                if isinstance(raw_value, (dict, list)):
                    walk(raw_value)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for block in iter_window_json_blocks(page_html):
        walk(block)

    return profile


def extract_profile_info(page_html: str) -> dict[str, str]:
    info = {}
    for item in re.findall(
        r'<div\b[^>]*class="[^"]*ProfileInfo-item[^"]*"[^>]*>(.*?)</div>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        spans = re.findall(r"<span\b[^>]*>(.*?)</span>", item, flags=re.IGNORECASE | re.DOTALL)
        if len(spans) < 2:
            continue
        label = clean_text(spans[0])
        value = clean_text(spans[1])
        if label and value:
            info[normalize_label(label)] = value
    return info


def extract_label_value_pairs(page_html: str) -> list[tuple[str, str]]:
    pairs = []
    for block in re.findall(
        r'<p\b[^>]*class="[^"]*AthleteBio-body[^"]*"[^>]*>(.*?)</p>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        label_match = re.search(
            r'<span\b[^>]*class="[^"]*AthleteBio-label[^"]*"[^>]*>(.*?)</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        value_match = re.search(
            r'<span\b[^>]*class="[^"]*Bio-stat[^"]*"[^>]*>(.*?)</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not label_match or not value_match:
            continue

        label = clean_text(label_match.group(1))
        value = clean_text(value_match.group(1))
        if label and value:
            pairs.append((label, value))
    return pairs


def find_pair_value(pairs: list[tuple[str, str]], wanted_labels: list[str]) -> str | None:
    wanted = [normalize_label(label) for label in wanted_labels]
    for target in wanted:
        for label, value in pairs:
            if normalize_label(label) == target and value:
                return value
    return None


def extract_hero_image(page_html: str) -> str | None:
    patterns = [
        r'<div\b[^>]*class="[^"]*AthleteHero-fencerImage[^"]*"[^>]*style="[^"]*background-image:\s*url\(([^)]+)\)',
        r'<div\b[^>]*class="[^"]*AthleteHero-bg[^"]*"[^>]*style="[^"]*background-image:\s*url\(([^)]+)\)',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        image_url = absolute_url(match.group(1))
        if image_url and "/bg-default" not in image_url:
            return image_url
    return None


def parse_athlete_profile(page_html: str) -> AthleteProfile:
    profile = extract_from_json_blocks(page_html)
    pairs = extract_label_value_pairs(page_html)
    summary = extract_profile_info(page_html)

    if not profile.club:
        profile.club = find_pair_value(pairs, ["Club / Team", "Club/Team", "Club Team", "Club"])

    if not profile.club:
        profile.club = find_pair_value(pairs, ["Federation", "National Federation", "Fencing Federation"])

    if not profile.image_url:
        profile.image_url = extract_hero_image(page_html)

    if not profile.date_of_birth:
        profile.date_of_birth = parse_date_value(
            find_pair_value(pairs, ["Date of birth", "Birthdate", "Birth date", "Born"])
        )

    if not profile.date_of_birth:
        profile.date_of_birth = parse_birthdate_from_license(
            find_pair_value(pairs, ["License number"]),
            summary.get("age"),
        )

    if not profile.hand:
        profile.hand = normalize_hand(find_pair_value(pairs, ["Handedness", "Hand"]))

    if not profile.hand:
        profile.hand = normalize_hand(summary.get("hand"))

    return profile


def first_available_column(candidates: list[str]) -> str | None:
    for column in candidates:
        try:
            supabase.table("fs_fencers").select(column).limit(1).execute()
            return column
        except Exception:
            continue
    return None


def select_columns(date_column: str | None, hand_column: str | None) -> str:
    columns = list(BASE_SELECT_COLUMNS)
    for column in [date_column, hand_column]:
        if column and column not in columns:
            columns.append(column)
    return ",".join(columns)


def query_missing_club_fencers(columns: str) -> list[dict[str, Any]]:
    def build_base_query():
        return (
            supabase.table("fs_fencers")
            .select(columns)
            .not_.is_("fie_id", "null")
            .not_.is_("world_rank", "null")
            .or_("club.is.null,club.eq.")
            .order("world_rank", desc=False)
            .limit(MAX_FENCERS)
        )

    if FORCE_RESCRAPE:
        return build_base_query().execute().data or []

    try:
        return (
            build_base_query()
            .filter("metadata->>fie_profile_attempted_at", "is", "null")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"Could not apply metadata attempt filter, falling back to local skip: {exc}")
        return build_base_query().execute().data or []


def ensure_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def was_already_attempted(fencer: dict[str, Any]) -> bool:
    if FORCE_RESCRAPE:
        return False
    metadata = ensure_metadata(fencer.get("metadata"))
    profile_scrape = metadata.get("fie_profile_scrape")
    return bool(
        metadata.get("fie_profile_attempted_at")
        or (isinstance(profile_scrape, dict) and profile_scrape.get("attempted_at"))
    )


def build_update_row(
    fencer: dict[str, Any],
    profile: AthleteProfile,
    status: str,
    http_status: int | None,
    error: str | None,
    date_column: str | None,
    hand_column: str | None,
) -> dict[str, Any]:
    attempted_at = datetime.now(timezone.utc).isoformat()
    metadata = ensure_metadata(fencer.get("metadata"))
    scrape_info = {
        "attempted_at": attempted_at,
        "status": status,
        "http_status": http_status,
        "profile_url": f"{FIE_BASE_URL}/{fencer.get('fie_id')}",
        "fields_found": profile.fields_found(),
    }
    if error:
        scrape_info["error"] = error[:500]

    metadata["fie_profile_attempted_at"] = attempted_at
    metadata["fie_profile_scrape"] = scrape_info

    if profile.club:
        metadata["fie_club"] = profile.club
    if profile.image_url:
        metadata["fie_profile_image_url"] = profile.image_url
    if profile.date_of_birth:
        metadata["fie_date_of_birth"] = profile.date_of_birth
    if profile.hand:
        metadata["fie_hand"] = profile.hand

    row = {
        "fie_id": str(fencer.get("fie_id")),
        "metadata": metadata,
        "updated_at": attempted_at,
    }

    if profile.club:
        row["club"] = profile.club

    if profile.image_url:
        row["image_url"] = profile.image_url

    if date_column and profile.date_of_birth and not clean_text(fencer.get(date_column)):
        row[date_column] = profile.date_of_birth

    if hand_column and profile.hand and not clean_text(fencer.get(hand_column)):
        row[hand_column] = profile.hand

    return row


def flush_updates(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    # fs_fencers has UNIQUE(fie_id, weapon, category) — not UNIQUE(fie_id) — so upsert
    # with on_conflict="fie_id" would fail. Use UPDATE ... WHERE fie_id = ? instead,
    # which applies profile data (club, image, metadata) to all weapon/category rows.
    flushed = 0
    remaining = list(rows)
    rows.clear()
    for row in remaining:
        fie_id = row.pop("fie_id", None)
        if not fie_id:
            continue
        try:
            supabase.table("fs_fencers").update(row).eq("fie_id", fie_id).execute()
            flushed += 1
        except Exception as exc:
            print(f"  Update failed for fie_id={fie_id}: {exc}")
    return flushed


def scrape_athlete_profiles():
    print(f"Athlete profile scraper starting - {datetime.now(timezone.utc).isoformat()}")
    print(f"Limit: {MAX_FENCERS}; delay: {REQUEST_DELAY_SECONDS}s; force rescrape: {FORCE_RESCRAPE}")

    date_column = first_available_column(DATE_COLUMN_CANDIDATES)
    hand_column = first_available_column(HAND_COLUMN_CANDIDATES)
    if date_column:
        print(f"Using DOB column: {date_column}")
    else:
        print("No DOB column found; storing DOB in metadata.fie_date_of_birth")
    if hand_column:
        print(f"Using hand column: {hand_column}")
    else:
        print("No hand column found; storing hand in metadata.fie_hand")

    fencers = query_missing_club_fencers(select_columns(date_column, hand_column))
    print(f"Found {len(fencers)} fencers with missing club data")

    session = requests.Session()
    session.headers.update(HEADERS)

    pending_updates = []
    processed = 0
    skipped_attempted = 0
    flushed_total = 0
    field_counts = {"club": 0, "image_url": 0, "date_of_birth": 0, "hand": 0}

    for fencer in fencers:
        if was_already_attempted(fencer):
            skipped_attempted += 1
            continue

        fie_id = str(fencer.get("fie_id") or "").strip()
        if not fie_id:
            continue

        profile = AthleteProfile()
        status = "no_profile_data"
        http_status = None
        error = None
        url = f"{FIE_BASE_URL}/{fie_id}"

        try:
            res = session.get(url, timeout=20)
            http_status = res.status_code

            if res.status_code == 404:
                status = "not_found"
                print(f"  {fie_id} - 404 not found")
            elif res.status_code != 200:
                status = f"http_{res.status_code}"
                print(f"  {fie_id} - HTTP {res.status_code}")
            else:
                profile = parse_athlete_profile(res.text)
                fields = profile.fields_found()
                status = "updated" if fields else "no_profile_data"
                for field in fields:
                    field_counts[field] += 1
        except Exception as exc:
            status = "error"
            error = str(exc)
            print(f"  {fie_id} - error: {exc}")

        pending_updates.append(
            build_update_row(fencer, profile, status, http_status, error, date_column, hand_column)
        )
        processed += 1

        if processed % 10 == 0:
            print(
                "Processed "
                f"{processed}/{len(fencers)}; pending={len(pending_updates)}; "
                f"club={field_counts['club']} image={field_counts['image_url']} "
                f"dob={field_counts['date_of_birth']} hand={field_counts['hand']}"
            )

        if processed % BATCH_SIZE == 0:
            flushed = flush_updates(pending_updates)
            flushed_total += flushed
            print(f"Flushed {flushed} updates (total flushed: {flushed_total})")

        time.sleep(REQUEST_DELAY_SECONDS)

    flushed = flush_updates(pending_updates)
    flushed_total += flushed

    print(
        "Athlete profile scraper complete - "
        f"processed={processed}, skipped_attempted={skipped_attempted}, "
        f"flushed={flushed_total}, field_counts={field_counts}"
    )


if __name__ == "__main__":
    scrape_athlete_profiles()

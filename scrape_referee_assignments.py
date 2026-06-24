import hashlib
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from supabase import create_client

try:
    from scripts.rate_limiter import RateLimiter as _RateLimiter

    _rate_limiter = _RateLimiter(default_rps=0.5, jitter=0.1, backoff=3.0)
except ImportError:
    _rate_limiter = None


SOURCE = "referee_assignments"
BATCH_SIZE = 100
REQUEST_DELAY_SECONDS = float(os.environ.get("REFEREE_ASSIGNMENTS_DELAY", "1.0"))
PAGE_SIZE = 1000

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml,application/json,application/pdf,*/*;q=0.8",
}


@dataclass
class ParseResult:
    rows: list[dict]
    blocked: bool = False
    reason: str | None = None
    metadata: dict = field(default_factory=dict)


def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def normalize_country(value) -> str | None:
    text = clean_text(value).upper()
    if not text:
        return None
    text = re.sub(r"[^A-Z]", "", text)
    return text if len(text) == 3 else None


def normalize_fie_id(value) -> str | None:
    if value is None:
        return None
    text = clean_text(value)
    if not text:
        return None
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        match = re.search(r"\d+", text)
        return match.group(0) if match else text


def normalize_role(value) -> str:
    text = clean_text(value).lower()
    if text in {"p", "president", "main"}:
        return "primary"
    if text in {"v"} or "video" in text or "vidéo" in text:
        return "video"
    if text in {"a"} or "assistant" in text or "assessor" in text or "adjoint" in text:
        return "assistant"
    if "arbitre" in text or "referee" in text or not text:
        return "primary"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "primary"


def _hash_source_key(parts: list[str | None]) -> str:
    payload = "|".join(clean_text(part) for part in parts)
    return "refassign:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_assignment_row(
    *,
    tournament_id: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
    bout_id: str | None = None,
    bout_source_id: str | None = None,
    referee_id: str | None = None,
    referee_fie_id: str | None = None,
    referee_fie_license_id: str | None = None,
    referee_name: str | None = None,
    country: str | None = None,
    role: str | None = None,
    piste: str | None = None,
    round_name: str | None = None,
    source_url: str | None = None,
    assignment_status: str = "assigned",
    metadata: dict | None = None,
) -> dict:
    normalized_role = normalize_role(role) if assignment_status == "assigned" else "unassigned"
    normalized_name = clean_text(referee_name) or None
    normalized_fie_id = normalize_fie_id(referee_fie_id)
    normalized_license = normalize_fie_id(referee_fie_license_id)
    identity = (
        normalized_fie_id
        or normalized_license
        or normalized_name
        or assignment_status
    )
    row = {
        "source_key": _hash_source_key(
            [
                source_url,
                tournament_id,
                event_id,
                bout_id,
                bout_source_id,
                normalized_role,
                identity,
                assignment_status,
            ]
        ),
        "tournament_id": tournament_id,
        "event_id": clean_text(event_id) or None,
        "event_name": clean_text(event_name) or None,
        "bout_id": clean_text(bout_id) or None,
        "bout_source_id": clean_text(bout_source_id) or None,
        "referee_id": referee_id,
        "referee_fie_id": normalized_fie_id,
        "referee_fie_license_id": normalized_license,
        "referee_name": normalized_name,
        "country": normalize_country(country),
        "role": normalized_role,
        "piste": clean_text(piste).upper() or None,
        "round": clean_text(round_name) or None,
        "source_url": source_url,
        "assignment_status": assignment_status,
        "metadata": metadata or {},
        "scraped_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    return row


def _attr(elem: ET.Element, *names: str) -> str | None:
    wanted = {name.lower() for name in names}
    for key, value in elem.attrib.items():
        if key.lower() in wanted:
            return value
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _referee_name_from_attrs(attrs: dict[str, str]) -> str | None:
    lowered = {key.lower(): value for key, value in attrs.items()}
    direct = lowered.get("name") or lowered.get("nomprenom") or lowered.get("fullname")
    if direct:
        return clean_text(direct) or None
    last = lowered.get("nom") or lowered.get("lastname") or lowered.get("last_name")
    first = lowered.get("prenom") or lowered.get("firstname") or lowered.get("first_name")
    return clean_text(f"{last or ''} {first or ''}") or None


def _referee_from_xml_elem(elem: ET.Element) -> dict:
    return {
        "referee_fie_id": normalize_fie_id(_attr(elem, "id", "refereeId", "fieId")),
        "referee_fie_license_id": normalize_fie_id(_attr(elem, "licence", "license", "licenseId")),
        "referee_name": _referee_name_from_attrs(dict(elem.attrib)),
        "country": normalize_country(_attr(elem, "nation", "country", "countryCode", "pays", "ioc")),
    }


def _round_for_xml_match(elem: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> str | None:
    direct = _attr(elem, "round", "tour", "phase", "libelle", "name", "nom")
    if direct:
        return clean_text(direct)
    parent = parent_map.get(elem)
    while parent is not None:
        value = _attr(parent, "libelle", "round", "tour", "name", "nom")
        if value:
            return clean_text(value)
        parent = parent_map.get(parent)
    return None


def parse_fie_xml_assignments(
    xml_text: str | bytes,
    *,
    source_url: str | None = None,
    tournament_id: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
    include_missing: bool = True,
) -> list[dict]:
    text = xml_text.decode("utf-8", errors="replace") if isinstance(xml_text, bytes) else xml_text
    root = ET.fromstring(text)
    parent_map = {child: parent for parent in root.iter() for child in list(parent)}
    registry: dict[str, dict] = {}
    for elem in root.iter():
        if _local_name(elem.tag) not in {"arbitre", "referee"}:
            continue
        if _attr(elem, "ref"):
            continue
        referee = _referee_from_xml_elem(elem)
        key = referee.get("referee_fie_id")
        if key:
            registry[key] = referee

    default_event_id = event_id or _attr(root, "eventId", "event_id", "id")
    default_event_name = event_name or _attr(root, "eventName", "nom", "name")
    rows: list[dict] = []
    for elem in root.iter():
        if _local_name(elem.tag) not in {"match", "bout", "assaut"}:
            continue
        bout_source_id = (
            _attr(elem, "id", "matchId", "boutId", "idmatch", "idbout")
            or _attr(elem, "no", "numero", "number")
        )
        piste = _attr(elem, "piste", "strip")
        round_name = _round_for_xml_match(elem, parent_map)
        ref_elems = [
            child
            for child in elem.iter()
            if child is not elem and _local_name(child.tag) in {"arbitre", "referee"}
        ]
        if not ref_elems and include_missing:
            rows.append(
                build_assignment_row(
                    tournament_id=tournament_id,
                    event_id=default_event_id,
                    event_name=default_event_name,
                    bout_source_id=bout_source_id,
                    role="unassigned",
                    piste=piste,
                    round_name=round_name,
                    source_url=source_url,
                    assignment_status="missing",
                    metadata={"source_type": "fie_xml"},
                )
            )
            continue
        for ref_elem in ref_elems:
            ref_key = normalize_fie_id(_attr(ref_elem, "ref", "id", "refereeId", "fieId"))
            referee = dict(registry.get(ref_key or "", {}))
            inline = _referee_from_xml_elem(ref_elem)
            for key, value in inline.items():
                if value is not None:
                    referee[key] = value
            if ref_key and not referee.get("referee_fie_id"):
                referee["referee_fie_id"] = ref_key
            rows.append(
                build_assignment_row(
                    tournament_id=tournament_id,
                    event_id=default_event_id,
                    event_name=default_event_name,
                    bout_source_id=bout_source_id,
                    referee_fie_id=referee.get("referee_fie_id"),
                    referee_fie_license_id=referee.get("referee_fie_license_id"),
                    referee_name=referee.get("referee_name"),
                    country=referee.get("country"),
                    role=_attr(ref_elem, "role", "type", "fonction"),
                    piste=piste,
                    round_name=round_name,
                    source_url=source_url,
                    metadata={"source_type": "fie_xml", "raw_ref": dict(ref_elem.attrib)},
                )
            )
    return rows


_ROLE_LABEL = r"(?:video\s+referee|assistant\s+referee|referee|arbitre\s+vid[eé]o|arbitre|video|assistant|assessor)"


def _parse_referee_value(value: str) -> tuple[str | None, str | None, str | None]:
    text = clean_text(value)
    id_match = re.search(r"\b(?:id|licen[cs]e|ref)\s*[:#]?\s*(\d+)\b", text, re.IGNORECASE)
    referee_id = normalize_fie_id(id_match.group(1)) if id_match else None
    if id_match:
        text = clean_text(text[: id_match.start()] + " " + text[id_match.end() :])
    country = None
    country_match = re.search(r"\b([A-Z]{3})\b\s*$", text)
    if country_match:
        country = country_match.group(1)
        text = clean_text(text[: country_match.start()])
    text = re.sub(r"\b\d{1,2}:\d{2}\b", "", text)
    return clean_text(text) or None, country, referee_id


def _piste_from_text(text: str) -> str | None:
    match = re.search(r"\bPiste\s+([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _assignment_rows_from_text_line(
    text: str,
    *,
    source_url: str | None,
    tournament_id: str | None,
    event_id: str | None,
    event_name: str | None,
    bout_source_id: str,
    round_name: str | None,
    include_missing: bool,
    source_type: str,
) -> list[dict]:
    rows: list[dict] = []
    piste = _piste_from_text(text)
    segment_pattern = re.compile(
        rf"(?P<label>{_ROLE_LABEL})\s*[:\-]\s*(?P<value>.*?)(?=(?:\s+{_ROLE_LABEL}\s*[:\-])|;|$)",
        re.IGNORECASE,
    )
    for match in segment_pattern.finditer(text):
        name, country, referee_fie_id = _parse_referee_value(match.group("value"))
        if not name:
            continue
        rows.append(
            build_assignment_row(
                tournament_id=tournament_id,
                event_id=event_id,
                event_name=event_name,
                bout_source_id=bout_source_id,
                referee_name=name,
                country=country,
                referee_fie_id=referee_fie_id,
                role=match.group("label"),
                piste=piste,
                round_name=round_name,
                source_url=source_url,
                metadata={"source_type": source_type, "raw_text": text[:500]},
            )
        )
    if not rows and include_missing and piste:
        rows.append(
            build_assignment_row(
                tournament_id=tournament_id,
                event_id=event_id,
                event_name=event_name,
                bout_source_id=bout_source_id,
                role="unassigned",
                piste=piste,
                round_name=round_name,
                source_url=source_url,
                assignment_status="missing",
                metadata={"source_type": source_type, "raw_text": text[:500]},
            )
        )
    return rows


def parse_engarde_html_assignments(
    html: str | bytes,
    *,
    source_url: str | None = None,
    tournament_id: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
    include_missing: bool = True,
) -> list[dict]:
    text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    soup = BeautifulSoup(text or "", "html.parser")
    heading = soup.find(["h1", "h2", "h3", "title"])
    round_name = clean_text(heading.get_text(" ", strip=True)) if heading else None
    rows: list[dict] = []
    table_rows = soup.find_all("tr")
    for index, tr in enumerate(table_rows, start=1):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        candidates = [cell for cell in cells if re.search(r"\b(Piste|Referee|Arbitre)\b", cell, re.IGNORECASE)]
        for offset, candidate in enumerate(candidates):
            rows.extend(
                _assignment_rows_from_text_line(
                    candidate,
                    source_url=source_url,
                    tournament_id=tournament_id,
                    event_id=event_id,
                    event_name=event_name,
                    bout_source_id=f"html-row-{index}-{offset}",
                    round_name=round_name,
                    include_missing=include_missing,
                    source_type="engarde_html",
                )
            )
    if not table_rows:
        for index, line in enumerate(soup.get_text("\n", strip=True).splitlines(), start=1):
            if not re.search(r"\b(Piste|Referee|Arbitre)\b", line, re.IGNORECASE):
                continue
            rows.extend(
                _assignment_rows_from_text_line(
                    line,
                    source_url=source_url,
                    tournament_id=tournament_id,
                    event_id=event_id,
                    event_name=event_name,
                    bout_source_id=f"html-line-{index}",
                    round_name=round_name,
                    include_missing=include_missing,
                    source_type="engarde_html",
                )
            )
    return rows


def parse_pdf_text_assignments(
    text: str,
    *,
    source_url: str | None = None,
    tournament_id: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
    include_missing: bool = True,
) -> list[dict]:
    rows: list[dict] = []
    current: dict | None = None
    current_has_refs = False

    def flush_missing():
        if current and include_missing and not current_has_refs:
            rows.append(
                build_assignment_row(
                    tournament_id=tournament_id,
                    event_id=event_id,
                    event_name=event_name,
                    bout_source_id=current.get("bout_source_id"),
                    role="unassigned",
                    piste=current.get("piste"),
                    round_name=current.get("round"),
                    source_url=source_url,
                    assignment_status="missing",
                    metadata={"source_type": "pdf_text"},
                )
            )

    for raw_line in (text or "").splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        bout_match = re.search(
            r"\b(?:Bout|Match)\s+(?P<bout>[A-Za-z0-9_.-]+)"
            r"(?:\s+Round\s+(?P<round>.*?))?"
            r"(?:\s+Piste\s+(?P<piste>[A-Za-z0-9_-]+))?$",
            line,
            re.IGNORECASE,
        )
        if bout_match:
            flush_missing()
            current = {
                "bout_source_id": bout_match.group("bout"),
                "round": clean_text(bout_match.group("round")) or None,
                "piste": bout_match.group("piste"),
            }
            current_has_refs = False
            continue
        if not current:
            continue
        match = re.search(rf"(?P<label>{_ROLE_LABEL})\s*[:\-]\s*(?P<value>.+)$", line, re.IGNORECASE)
        if not match:
            continue
        name, country, referee_fie_id = _parse_referee_value(match.group("value"))
        if not name:
            continue
        current_has_refs = True
        rows.append(
            build_assignment_row(
                tournament_id=tournament_id,
                event_id=event_id,
                event_name=event_name,
                bout_source_id=current.get("bout_source_id"),
                referee_name=name,
                country=country,
                referee_fie_id=referee_fie_id,
                role=match.group("label"),
                piste=current.get("piste"),
                round_name=current.get("round"),
                source_url=source_url,
                metadata={"source_type": "pdf_text", "raw_text": line[:500]},
            )
        )
    flush_missing()
    return rows


def parse_pdf_bytes_assignments(
    pdf_bytes: bytes,
    *,
    source_url: str | None = None,
    tournament_id: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
) -> list[dict]:
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return parse_pdf_text_assignments(
        "\n".join(chunks),
        source_url=source_url,
        tournament_id=tournament_id,
        event_id=event_id,
        event_name=event_name,
    )


def _loads_json(payload: str | bytes | dict | list):
    if isinstance(payload, dict | list):
        return payload
    text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    return json.loads(text)


def _iter_api_bouts(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_api_bouts(item)
        return
    if not isinstance(payload, dict):
        return
    if any(key in payload for key in ("referees", "arbitres", "officials")) and any(
        key in payload for key in ("id", "boutId", "bout_id", "matchId")
    ):
        yield payload
    for key in ("bouts", "matches", "assaults", "tableauBouts", "poolBouts"):
        value = payload.get(key)
        if isinstance(value, list | dict):
            yield from _iter_api_bouts(value)


def _api_value(data: dict, *keys: str):
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def parse_api_assignments(
    payload: str | bytes | dict | list,
    *,
    source_url: str | None = None,
    tournament_id: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
    include_missing: bool = True,
) -> list[dict]:
    data = _loads_json(payload)
    default_event_id = event_id if event_id is not None else _api_value(data, "eventId", "event_id") if isinstance(data, dict) else None
    rows: list[dict] = []
    for bout in _iter_api_bouts(data):
        bout_source_id = clean_text(_api_value(bout, "id", "boutId", "bout_id", "matchId")) or None
        round_name = _api_value(bout, "round", "roundName", "phase", "tableau")
        piste = _api_value(bout, "piste", "strip")
        refs = _api_value(bout, "referees", "arbitres", "officials", "judges") or []
        if isinstance(refs, dict):
            refs = [refs]
        if not refs and include_missing:
            rows.append(
                build_assignment_row(
                    tournament_id=tournament_id,
                    event_id=default_event_id,
                    event_name=event_name,
                    bout_source_id=bout_source_id,
                    role="unassigned",
                    piste=piste,
                    round_name=round_name,
                    source_url=source_url,
                    assignment_status="missing",
                    metadata={"source_type": "api", "raw_bout": bout},
                )
            )
            continue
        for ref in refs:
            if isinstance(ref, str):
                name, country, referee_fie_id = _parse_referee_value(ref)
                role = "referee"
                license_id = None
                referee_uuid = None
            elif isinstance(ref, dict):
                name = _api_value(ref, "name", "fullName", "displayName")
                country = _api_value(ref, "countryCode", "country", "nation")
                referee_fie_id = _api_value(ref, "fieId", "fie_id", "id", "refereeId")
                license_id = _api_value(ref, "licenseId", "licence", "license")
                role = _api_value(ref, "role", "type", "function")
                raw_referee_id = _api_value(ref, "referee_uuid", "referee_id")
                referee_uuid = clean_text(raw_referee_id) or None
            else:
                continue
            rows.append(
                build_assignment_row(
                    tournament_id=tournament_id,
                    event_id=default_event_id,
                    event_name=event_name,
                    bout_source_id=bout_source_id,
                    referee_id=referee_uuid,
                    referee_fie_id=referee_fie_id,
                    referee_fie_license_id=license_id,
                    referee_name=name,
                    country=country,
                    role=role,
                    piste=piste,
                    round_name=round_name,
                    source_url=source_url,
                    metadata={"source_type": "api", "raw_ref": ref},
                )
            )
    return rows


def blocked_source_reason(text: str | bytes, source_url: str | None = None) -> str | None:
    body = text.decode("utf-8", errors="replace") if isinstance(text, bytes) else (text or "")
    lower = body.lower()
    host = urlparse(source_url or "").netloc.lower()
    if "type=\"password\"" in lower or "type='password'" in lower:
        return "login_required"
    if "login required" in lower or "sign in to view" in lower or "authentication required" in lower:
        return "login_required"
    if "fencingtimelive.com" in host and ("login" in lower or "password" in lower):
        return "login_required"
    if "access denied" in lower or "forbidden" in lower:
        return "access_denied"
    return None


def parse_assignment_content(
    content: bytes,
    *,
    content_type: str = "",
    source_url: str | None = None,
    tournament_id: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
) -> ParseResult:
    reason = blocked_source_reason(content, source_url)
    if reason:
        return ParseResult(rows=[], blocked=True, reason=reason, metadata={"source_url": source_url})

    lower_type = (content_type or "").lower()
    text = content.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    try:
        if "pdf" in lower_type or (source_url or "").lower().endswith(".pdf"):
            return ParseResult(
                rows=parse_pdf_bytes_assignments(
                    content,
                    source_url=source_url,
                    tournament_id=tournament_id,
                    event_id=event_id,
                    event_name=event_name,
                )
            )
        if "json" in lower_type or stripped.startswith("{") or stripped.startswith("["):
            return ParseResult(
                rows=parse_api_assignments(
                    text,
                    source_url=source_url,
                    tournament_id=tournament_id,
                    event_id=event_id,
                    event_name=event_name,
                )
            )
        if "xml" in lower_type or (
            stripped.startswith("<") and re.search(r"<\s*(Competition|Match|Assaut|Bout|Arbitre)\b", stripped)
        ):
            try:
                return ParseResult(
                    rows=parse_fie_xml_assignments(
                        text,
                        source_url=source_url,
                        tournament_id=tournament_id,
                        event_id=event_id,
                        event_name=event_name,
                    )
                )
            except ET.ParseError:
                pass
        return ParseResult(
            rows=parse_engarde_html_assignments(
                text,
                source_url=source_url,
                tournament_id=tournament_id,
                event_id=event_id,
                event_name=event_name,
            )
        )
    except Exception as exc:
        return ParseResult(rows=[], blocked=False, reason=f"parse_error:{exc}", metadata={"source_url": source_url})


def dedupe_assignment_rows(rows: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for row in rows:
        key = row.get("source_key")
        if key:
            deduped[key] = row
    return list(deduped.values())


def upsert_assignments(client, rows: list[dict]) -> int:
    if not rows:
        return 0
    values = dedupe_assignment_rows(rows)
    written = 0
    for i in range(0, len(values), BATCH_SIZE):
        batch = values[i : i + BATCH_SIZE]
        client.table("fs_referee_assignments").upsert(batch, on_conflict="source_key").execute()
        written += len(batch)
    return written


def _source_from_tournament(tournament: dict) -> list[dict]:
    tournament_id = tournament.get("id")
    event_id = tournament.get("source_id") or tournament.get("competition_url_id")
    event_name = tournament.get("name")
    urls: list[str] = []
    competition_url_id = tournament.get("competition_url_id")
    season = tournament.get("season")
    if competition_url_id and season:
        urls.append(f"https://fie.org/competitions/{season}/{competition_url_id}")
    metadata = tournament.get("metadata") or {}
    for key in ("result_url", "live_results_url", "source_url", "assignment_url"):
        value = metadata.get(key)
        if isinstance(value, str):
            urls.append(value)
    for key in ("result_urls", "source_urls", "assignment_urls"):
        value = metadata.get(key)
        if isinstance(value, list):
            urls.extend(item for item in value if isinstance(item, str))

    seen: set[str] = set()
    sources: list[dict] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        sources.append(
            {
                "source_url": url,
                "tournament_id": tournament_id,
                "event_id": event_id,
                "event_name": event_name,
            }
        )
    return sources


def load_assignment_sources(client) -> list[dict]:
    rows = (
        client.table("fs_tournaments")
        .select("id,name,source_id,season,competition_url_id,metadata")
        .not_.is_("competition_url_id", "null")
        .eq("has_results", True)
        .order("end_date", desc=True)
        .limit(PAGE_SIZE)
        .execute()
        .data
        or []
    )
    sources: list[dict] = []
    for tournament in rows:
        sources.extend(_source_from_tournament(tournament))
    return sources


def fetch_source_assignments(session: requests.Session, source: dict) -> ParseResult:
    url = source["source_url"]
    host = urlparse(url).netloc or "unknown"
    if _rate_limiter:
        _rate_limiter.wait(host)
    else:
        time.sleep(REQUEST_DELAY_SECONDS)
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    result = parse_assignment_content(
        response.content,
        content_type=response.headers.get("content-type", ""),
        source_url=url,
        tournament_id=source.get("tournament_id"),
        event_id=source.get("event_id"),
        event_name=source.get("event_name"),
    )
    if _rate_limiter:
        _rate_limiter.record_success(host)
    return result


def scrape_referee_assignments(
    *,
    client=None,
    session: requests.Session | None = None,
    sources: list[dict] | None = None,
    delay: float | None = None,
    log_run: bool = True,
) -> dict:
    client = client or get_supabase()
    session = session or requests.Session()
    if hasattr(session, "headers"):
        session.headers.update(HEADERS)
    run_log = ScraperRunLogger("scrape_referee_assignments").start() if log_run else None
    prior_blocked = set(get_state(SOURCE, "blocked_source_urls") or []) if sources is None else set()
    sources = sources if sources is not None else load_assignment_sources(client)

    summary = {
        "sources": len(sources),
        "written": 0,
        "failed": 0,
        "skipped": 0,
        "blocked": 0,
        "rows_found": 0,
    }
    blocked_urls: list[str] = []
    try:
        for index, source in enumerate(sources):
            url = source.get("source_url")
            if not url:
                summary["skipped"] += 1
                continue
            if url in prior_blocked:
                summary["blocked"] += 1
                summary["skipped"] += 1
                blocked_urls.append(url)
                continue
            try:
                result = fetch_source_assignments(session, source)
            except Exception as exc:
                summary["failed"] += 1
                host = urlparse(url).netloc or "unknown"
                if _rate_limiter:
                    _rate_limiter.record_failure(host)
                print(f"  Failed to fetch {url}: {exc}")
                continue
            if result.blocked:
                summary["blocked"] += 1
                summary["skipped"] += 1
                blocked_urls.append(url)
                continue
            if result.reason:
                summary["failed"] += 1
                print(f"  Could not parse {url}: {result.reason}")
                continue
            summary["rows_found"] += len(result.rows)
            written = upsert_assignments(client, result.rows)
            summary["written"] += written
            if not result.rows:
                summary["skipped"] += 1
            if delay and index < len(sources) - 1:
                time.sleep(delay)
        if blocked_urls:
            set_state(SOURCE, "blocked_source_urls", sorted(set(blocked_urls)))
        state_value = {
            **summary,
            "scraped_at": datetime.now(UTC).isoformat(),
        }
        set_state(SOURCE, "last_run", state_value)
        if run_log:
            run_log.complete(
                written=summary["written"],
                failed=summary["failed"],
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = scrape_referee_assignments()
    print(
        "Done - "
        f"sources={summary['sources']}, rows_found={summary['rows_found']}, "
        f"written={summary['written']}, blocked={summary['blocked']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

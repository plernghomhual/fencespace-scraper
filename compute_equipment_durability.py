from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from statistics import median
from typing import Any, Iterable

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "compute_equipment_durability"
PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 200

DATE_KEYS = (
    "observed_date",
    "observed_at",
    "source_date",
    "published_at",
    "reviewed_at",
    "scraped_at",
    "created_at",
)

BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "Allstar": ("Allstar", "Allstar Uhlmann"),
    "Uhlmann": ("Uhlmann",),
    "Leon Paul": ("Leon Paul", "Leon Paul USA", "LP"),
    "Prieur": ("Prieur",),
    "Absolute Fencing": ("Absolute Fencing", "Absolute", "AF"),
    "Negrini": ("Negrini",),
    "FWF": ("FWF",),
    "Carmimari": ("Carmimari",),
    "Blaise Frères": ("Blaise Frères", "Blaise Freres"),
    "Triplette": ("Triplette",),
    "Versari": ("Versari",),
    "Favero": ("Favero",),
    "SG": ("SG",),
    "OK": ("OK",),
    "Dynamo": ("Dynamo",),
    "PBT": ("PBT",),
    "Blue Gauntlet": ("Blue Gauntlet", "BG"),
    "Victory": ("Victory",),
    "Wuxi": ("Wuxi",),
}

SHORT_BRAND_ALIASES = {"AF", "BG", "LP", "OK", "SG"}


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    brand: str
    equipment_type: str
    fencer_id: str | None
    observed_date: date
    source: str | None
    source_url: str | None
    confidence: str
    evidence_kind: str
    metadata: dict[str, Any]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )


def compare_text(value: str) -> str:
    text = strip_accents(unicodedata.normalize("NFKC", value)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def metadata_dict(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str) and metadata.strip():
        try:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def normalize_brand(value: Any) -> str | None:
    raw = clean_text(value)
    if not raw:
        return None

    normalized_raw = compare_text(raw)
    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            normalized_alias = compare_text(alias)
            if not normalized_alias:
                continue
            if alias in SHORT_BRAND_ALIASES:
                if normalized_raw == normalized_alias:
                    return canonical
                continue
            if re.search(rf"(^|\s){re.escape(normalized_alias)}($|\s)", normalized_raw):
                return canonical

    if raw.isupper() and len(raw) <= 4:
        return raw
    return " ".join(part.capitalize() for part in normalized_raw.split())


def normalize_equipment_type(value: Any, sponsor_name: Any = None) -> str | None:
    raw = clean_text(value)
    if not raw and clean_text(sponsor_name):
        return "sponsor"
    if not raw:
        return None

    text = compare_text(raw)
    if re.search(r"\b(mask|masks|visor|visors)\b", text):
        return "mask"
    if re.search(r"\b(lame|lames|jacket|jackets|uniform|uniforms|clothing|plastron|knickers)\b", text):
        return "jacket"
    if re.search(r"\b(weapon|weapons|blade|blades|foil|epee|eppee|sabre|saber|grip|grips)\b", text):
        return "weapon"
    if re.search(r"\b(sponsor|sponsorship|sponsored)\b", text):
        return "sponsor"
    if re.search(r"\b(scoring|machine|reel|body cord|body cords)\b", text):
        return "scoring_equipment"
    return text.replace(" ", "_")


def parse_public_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = clean_text(value)
    if not raw:
        return None

    match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
    if not match:
        return None
    date_text = match.group(0)
    try:
        return date.fromisoformat(date_text)
    except ValueError:
        return None


def evidence_date(row: dict[str, Any]) -> date | None:
    metadata = metadata_dict(row)
    for source in (metadata, row):
        for key in DATE_KEYS:
            parsed = parse_public_date(source.get(key))
            if parsed:
                return parsed
    return None


def row_source_url(row: dict[str, Any]) -> str | None:
    metadata = metadata_dict(row)
    for source in (row, metadata):
        for key in ("source_url", "url", "listing_url"):
            value = clean_text(source.get(key))
            if value:
                return value
    return None


def source_confidence(value: Any) -> str:
    confidence = clean_text(value)
    if confidence in {"high", "medium", "low"}:
        return confidence
    return "low"


def equipment_evidence_from_row(row: dict[str, Any]) -> tuple[Evidence | None, tuple[str, str] | None]:
    brand = normalize_brand(row.get("brand"))
    equipment_type = normalize_equipment_type(row.get("equipment_type"), row.get("sponsor_name"))
    if not brand or not equipment_type:
        return None, None

    observed = evidence_date(row)
    if not observed:
        return None, (brand, equipment_type)

    metadata = metadata_dict(row)
    evidence_id = clean_text(row.get("id")) or str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"equipment-evidence:{brand}:{equipment_type}:{row_source_url(row)}:{observed.isoformat()}")
    )
    return (
        Evidence(
            evidence_id=evidence_id,
            brand=brand,
            equipment_type=equipment_type,
            fencer_id=clean_text(row.get("fencer_id")),
            observed_date=observed,
            source=clean_text(row.get("source")),
            source_url=row_source_url(row),
            confidence=source_confidence(row.get("confidence")),
            evidence_kind="equipment_mention",
            metadata=metadata,
        ),
        None,
    )


def review_evidence_from_row(row: dict[str, Any]) -> tuple[Evidence | None, tuple[str, str] | None]:
    brand = normalize_brand(row.get("brand"))
    equipment_type = normalize_equipment_type(row.get("category")) or normalize_equipment_type(row.get("product_name"))
    if not brand or not equipment_type:
        return None, None

    observed = evidence_date(row)
    if not observed:
        return None, (brand, equipment_type)

    evidence_id = clean_text(row.get("id")) or str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"review-evidence:{brand}:{equipment_type}:{row_source_url(row)}:{observed.isoformat()}")
    )
    return (
        Evidence(
            evidence_id=evidence_id,
            brand=brand,
            equipment_type=equipment_type,
            fencer_id=None,
            observed_date=observed,
            source=clean_text(row.get("source")) or "equipment_review",
            source_url=row_source_url(row),
            confidence="low",
            evidence_kind="equipment_review",
            metadata=metadata_dict(row),
        ),
        None,
    )


def deterministic_row_id(brand: str, equipment_type: str, fencer_id: str | None) -> str:
    raw_key = "|".join([brand, equipment_type, fencer_id or "aggregate"])
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fencespace:equipment-durability:{raw_key}"))


def unique_values(values: Iterable[str | None], *, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def evidence_metadata(
    evidences: list[Evidence],
    *,
    estimate_basis: str,
    skipped_undated_evidence_count: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_counts = Counter(evidence.evidence_kind for evidence in evidences)
    confidence_counts = Counter(evidence.confidence for evidence in evidences)
    metadata: dict[str, Any] = {
        "estimate_basis": estimate_basis,
        "warning": "estimate_not_private_replacement_behavior",
        "estimate_label": "Estimate from public dated equipment evidence only.",
        "evidence_ids": unique_values((evidence.evidence_id for evidence in evidences)),
        "evidence_links": unique_values((evidence.source_url for evidence in evidences)),
        "sources": unique_values((evidence.source for evidence in evidences)),
        "evidence_kind_counts": dict(sorted(source_counts.items())),
        "source_confidence_counts": dict(sorted(confidence_counts.items())),
    }
    if skipped_undated_evidence_count:
        metadata["skipped_undated_evidence_count"] = skipped_undated_evidence_count
    if extra:
        metadata.update(extra)
    return metadata


def build_output_row(
    *,
    brand: str,
    equipment_type: str,
    fencer_id: str | None,
    evidences: list[Evidence],
    replacement_interval_estimate: int | None,
    confidence: str,
    computed_at: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    sorted_evidence = sorted(evidences, key=lambda item: (item.observed_date, item.evidence_id))
    first_date = sorted_evidence[0].observed_date.isoformat() if sorted_evidence else None
    last_date = sorted_evidence[-1].observed_date.isoformat() if sorted_evidence else None
    return {
        "id": deterministic_row_id(brand, equipment_type, fencer_id),
        "brand": brand,
        "equipment_type": equipment_type,
        "fencer_id": fencer_id,
        "observed_first_date": first_date,
        "observed_last_date": last_date,
        "replacement_interval_estimate": replacement_interval_estimate,
        "evidence_count": len(sorted_evidence),
        "confidence": confidence,
        "metadata": metadata,
        "computed_at": computed_at,
    }


def next_different_brand_evidence(target_brand: str, target_last_date: date, evidences: list[Evidence]) -> Evidence | None:
    candidates = [
        evidence
        for evidence in evidences
        if evidence.brand != target_brand and evidence.observed_date >= target_last_date
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.observed_date, item.brand, item.evidence_id))[0]


def fencer_confidence(evidences: list[Evidence], has_brand_change: bool) -> str:
    if has_brand_change and len(evidences) >= 2 and any(evidence.confidence == "high" for evidence in evidences):
        return "high"
    if has_brand_change or len(evidences) >= 2:
        return "medium"
    return "low"


def collect_evidence(
    equipment_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> tuple[list[Evidence], Counter[tuple[str, str]]]:
    evidences: list[Evidence] = []
    skipped_undated: Counter[tuple[str, str]] = Counter()

    for row in equipment_rows:
        evidence, undated_key = equipment_evidence_from_row(row)
        if evidence:
            evidences.append(evidence)
        elif undated_key:
            skipped_undated[undated_key] += 1

    for row in review_rows:
        evidence, undated_key = review_evidence_from_row(row)
        if evidence:
            evidences.append(evidence)
        elif undated_key:
            skipped_undated[undated_key] += 1

    return evidences, skipped_undated


def build_durability_rows(
    equipment_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    *,
    computed_at: str | None = None,
) -> list[dict[str, Any]]:
    computed_at = computed_at or datetime.now(timezone.utc).isoformat()
    evidences, skipped_undated = collect_evidence(equipment_rows, review_rows)
    if not evidences:
        return []

    rows: list[dict[str, Any]] = []
    emitted_brand_type: set[tuple[str, str]] = set()
    fencer_estimates_by_brand_type: dict[tuple[str, str], list[int]] = defaultdict(list)
    brand_type_has_change_context: set[tuple[str, str]] = set()

    fencer_type_groups: dict[tuple[str, str], list[Evidence]] = defaultdict(list)
    for evidence in evidences:
        if evidence.fencer_id:
            fencer_type_groups[(evidence.fencer_id, evidence.equipment_type)].append(evidence)

    for (fencer_id, equipment_type), group_evidences in sorted(fencer_type_groups.items()):
        sorted_group = sorted(group_evidences, key=lambda item: (item.observed_date, item.brand, item.evidence_id))
        brands = {evidence.brand for evidence in sorted_group}
        if len(brands) > 1:
            for brand in brands:
                brand_type_has_change_context.add((brand, equipment_type))

        by_brand: dict[str, list[Evidence]] = defaultdict(list)
        for evidence in sorted_group:
            by_brand[evidence.brand].append(evidence)

        for brand, brand_evidences in sorted(by_brand.items(), key=lambda item: (item[1][0].observed_date, item[0])):
            brand_evidences = sorted(brand_evidences, key=lambda item: (item.observed_date, item.evidence_id))
            first = brand_evidences[0].observed_date
            last = brand_evidences[-1].observed_date
            next_evidence = next_different_brand_evidence(brand, last, sorted_group)

            replacement_interval: int | None = None
            estimate_basis: str | None = None
            extra: dict[str, Any] = {}
            if next_evidence:
                replacement_interval = (next_evidence.observed_date - first).days
                estimate_basis = "public_brand_change"
                extra = {
                    "next_observed_brand": next_evidence.brand,
                    "next_observed_date": next_evidence.observed_date.isoformat(),
                    "replacement_gap_days": (next_evidence.observed_date - last).days,
                }
            elif len(brand_evidences) >= 2 and last > first:
                replacement_interval = (last - first).days
                estimate_basis = "minimum_public_observed_duration"

            if estimate_basis is None:
                continue

            key = (brand, equipment_type)
            emitted_brand_type.add(key)
            if replacement_interval is not None:
                fencer_estimates_by_brand_type[key].append(replacement_interval)
            rows.append(
                build_output_row(
                    brand=brand,
                    equipment_type=equipment_type,
                    fencer_id=fencer_id,
                    evidences=brand_evidences,
                    replacement_interval_estimate=replacement_interval,
                    confidence=fencer_confidence(brand_evidences, has_brand_change=next_evidence is not None),
                    computed_at=computed_at,
                    metadata=evidence_metadata(
                        brand_evidences,
                        estimate_basis=estimate_basis,
                        skipped_undated_evidence_count=skipped_undated.get(key, 0),
                        extra=extra,
                    ),
                )
            )

    aggregate_groups: dict[tuple[str, str], list[Evidence]] = defaultdict(list)
    for evidence in evidences:
        aggregate_groups[(evidence.brand, evidence.equipment_type)].append(evidence)

    for (brand, equipment_type), group_evidences in sorted(aggregate_groups.items()):
        if (brand, equipment_type) in emitted_brand_type:
            continue

        estimates = fencer_estimates_by_brand_type.get((brand, equipment_type), [])
        replacement_interval = round(median(estimates)) if estimates else None
        evidence_count = len(group_evidences)
        has_change_context = (brand, equipment_type) in brand_type_has_change_context
        if replacement_interval is not None and evidence_count >= 3:
            confidence = "medium"
            estimate_basis = "aggregate_public_fencer_estimates"
        elif evidence_count >= 2 or has_change_context:
            confidence = "low"
            estimate_basis = "aggregate_public_evidence_only"
        else:
            confidence = "insufficient"
            estimate_basis = "aggregate_public_evidence_only"

        rows.append(
            build_output_row(
                brand=brand,
                equipment_type=equipment_type,
                fencer_id=None,
                evidences=group_evidences,
                replacement_interval_estimate=replacement_interval,
                confidence=confidence,
                computed_at=computed_at,
                metadata=evidence_metadata(
                    sorted(group_evidences, key=lambda item: (item.observed_date, item.evidence_id)),
                    estimate_basis=estimate_basis,
                    skipped_undated_evidence_count=skipped_undated.get((brand, equipment_type), 0),
                    extra={"aggregate_scope": "brand_equipment_type"},
                ),
            )
        )

    return sorted(
        rows,
        key=lambda row: (
            row["brand"],
            row["equipment_type"],
            row["fencer_id"] or "",
            row["observed_first_date"] or "",
        ),
    )


def fetch_table_rows(client, table_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table_name)
            .select("*")
            .order("id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def upsert_durability_rows(client, rows: list[dict[str, Any]]) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[index : index + UPSERT_BATCH_SIZE]
        try:
            client.table("fs_equipment_durability").upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_equipment_durability upsert batch {index // UPSERT_BATCH_SIZE} failed: {exc}")
    return written, failed


def compute_equipment_durability(
    client=None,
    *,
    log_run: bool = True,
    computed_at: str | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    computed_at = computed_at or datetime.now(timezone.utc).isoformat()

    try:
        previous_state = get_state(SOURCE, "last_run")
        equipment_rows = fetch_table_rows(client, "fs_fencer_equipment")
        review_rows = fetch_table_rows(client, "fs_equipment_reviews")
        durability_rows = build_durability_rows(
            equipment_rows,
            review_rows,
            computed_at=computed_at,
        )
        written, failed = upsert_durability_rows(client, durability_rows) if durability_rows else (0, 0)
        skipped = sum(
            int(row.get("metadata", {}).get("skipped_undated_evidence_count", 0))
            for row in durability_rows
            if isinstance(row.get("metadata"), dict)
        )
        summary = {
            "equipment_rows_read": len(equipment_rows),
            "review_rows_read": len(review_rows),
            "durability_rows_found": len(durability_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "computed_at": computed_at,
        }
        if previous_state:
            summary["previous_run"] = previous_state
        set_state(SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def run(**kwargs) -> dict[str, Any]:
    return compute_equipment_durability(**kwargs)


def main() -> None:
    print(f"Equipment durability computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_equipment_durability()
    print(
        "Equipment durability computation complete - "
        f"equipment_rows={summary['equipment_rows_read']}, "
        f"review_rows={summary['review_rows_read']}, "
        f"found={summary['durability_rows_found']}, "
        f"written={summary['written']}, failed={summary['failed']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

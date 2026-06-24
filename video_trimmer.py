from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BOUT_WORDS = (
    "bout",
    "match",
    "table",
    "t64",
    "t32",
    "t16",
    "quarter",
    "quarterfinal",
    "semi",
    "semifinal",
    "final",
    "bronze",
    "gold",
)
TOURNAMENT_WORDS = (
    "fie",
    "world cup",
    "world championships",
    "grand prix",
    "olympic",
    "championship",
    "cairo",
    "milan",
    "paris",
    "foil",
    "epee",
    "sabre",
)


@dataclass(frozen=True)
class Chapter:
    start_seconds: int
    title: str
    end_seconds: int | None = None


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str
    description: str = ""
    duration_seconds: int | None = None
    chapters: Sequence[Chapter] = ()


@dataclass(frozen=True)
class FencerReference:
    id: str
    name: str
    aliases: Sequence[str] = ()


@dataclass(frozen=True)
class KnownBoutTimestamp:
    start_seconds: int
    end_seconds: int
    label: str = ""
    fencer_ids: Sequence[str] = ()
    tournament_name: str | None = None


@dataclass(frozen=True)
class TrimCandidate:
    id: str
    video_id: str
    title: str
    start_seconds: int
    end_seconds: int
    confidence: float
    related_fencer_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class TrimCommandPlan:
    candidate_id: str
    command: list[str]
    output_path: str
    will_execute: bool
    executed: bool
    reason: str


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_timecode(value: str) -> int | None:
    parts = value.strip().split(":")
    if len(parts) not in {2, 3}:
        return None
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None

    if len(numbers) == 2:
        minutes, seconds = numbers
        if seconds >= 60:
            return None
        return minutes * 60 + seconds

    hours, minutes, seconds = numbers
    if minutes >= 60 or seconds >= 60:
        return None
    return hours * 3600 + minutes * 60 + seconds


def format_timecode(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_chapters(description: str, duration_seconds: int | None = None) -> list[Chapter]:
    parsed: list[tuple[int, str]] = []
    seen_starts: set[int] = set()
    pattern = re.compile(
        r"^\s*(?P<time>(?:\d{1,2}:)?\d{1,3}:\d{2})\s*(?:[-|\u2013\u2014:]\s*)?(?P<title>.+?)\s*$"
    )

    for line in str(description or "").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        start = parse_timecode(match.group("time"))
        title = clean_text(match.group("title")).lstrip("-\u2013\u2014|: ")
        if start is None or not title or start in seen_starts:
            continue
        seen_starts.add(start)
        parsed.append((start, title))

    parsed.sort(key=lambda item: item[0])
    chapters: list[Chapter] = []
    for index, (start, title) in enumerate(parsed):
        next_start = parsed[index + 1][0] if index + 1 < len(parsed) else None
        end = next_start if next_start is not None else duration_seconds
        if end is not None and end <= start:
            end = None
        chapters.append(Chapter(start_seconds=start, end_seconds=end, title=title))
    return chapters


def _lower_words(value: str) -> str:
    return clean_text(value).casefold()


def _contains_any(text: str, words: Iterable[str]) -> bool:
    lowered = _lower_words(text)
    return any(word in lowered for word in words)


def _has_versus(text: str) -> bool:
    return bool(re.search(r"\b(vs?\.?|versus)\b", _lower_words(text)))


def _names_for_fencer(fencer: FencerReference) -> tuple[str, ...]:
    names = [fencer.name, *list(fencer.aliases or ())]
    cleaned = [clean_text(name) for name in names]
    return tuple(name for name in cleaned if name)


def _matched_fencer_ids(text: str, fencers: Sequence[FencerReference]) -> tuple[str, ...]:
    lowered = _lower_words(text)
    matched: list[str] = []
    for fencer in fencers:
        for name in _names_for_fencer(fencer):
            pattern = r"(?<![A-Za-z0-9])" + re.escape(name.casefold()) + r"(?![A-Za-z0-9])"
            if re.search(pattern, lowered):
                matched.append(fencer.id)
                break
    return tuple(dict.fromkeys(matched))


def _candidate_id(video_id: str, source: str, start: int, end: int, title: str) -> str:
    key = f"{video_id}|{source}|{start}|{end}|{title}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"{video_id}-{start}-{end}-{digest}"


def _score_candidate(
    *,
    source: str,
    text: str,
    title_text: str,
    metadata_text: str,
    related_fencer_ids: Sequence[str],
    explicit_fencer_ids: Sequence[str] = (),
) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []
    score = 0.18

    if source == "known_bout":
        score += 0.35
        reasons.append("known bout timestamp")
    elif source == "chapter":
        score += 0.18
        reasons.append("chapter timestamp")
    elif source == "full_video":
        score += 0.12
        reasons.append("title matched full video")

    if related_fencer_ids:
        score += 0.24
        reasons.append("matched fencer name")
    if explicit_fencer_ids:
        score += 0.12
        reasons.append("known fencer ids")
    if _has_versus(text):
        score += 0.09
        reasons.append("bout versus marker")
    if _contains_any(text, BOUT_WORDS):
        score += 0.08
        reasons.append("bout phase marker")
    if _contains_any(text, TOURNAMENT_WORDS) or _contains_any(title_text, TOURNAMENT_WORDS):
        score += 0.09
        reasons.append("tournament context")
    if related_fencer_ids and any(fencer_id in explicit_fencer_ids for fencer_id in related_fencer_ids):
        score += 0.05
        reasons.append("metadata agrees with known bout")
    if related_fencer_ids and any(name_part in _lower_words(title_text) for name_part in _lower_words(text).split()):
        score += 0.03
        reasons.append("video title context")
    if metadata_text and text and _lower_words(text) in _lower_words(metadata_text):
        score += 0.03
        reasons.append("description context")

    return min(round(score, 2), 0.98), tuple(dict.fromkeys(reasons))


def _bounded_window(start: int, end: int, padding_seconds: int, duration_seconds: int | None) -> tuple[int, int]:
    padded_start = max(0, int(start) - max(0, int(padding_seconds)))
    padded_end = int(end) + max(0, int(padding_seconds))
    if duration_seconds is not None:
        padded_end = min(int(duration_seconds), padded_end)
    if padded_end <= padded_start:
        padded_end = padded_start + 1
    return padded_start, padded_end


def _make_candidate(
    *,
    metadata: VideoMetadata,
    source: str,
    title: str,
    start: int,
    end: int,
    fencers: Sequence[FencerReference],
    padding_seconds: int,
    explicit_fencer_ids: Sequence[str] = (),
    tournament_name: str | None = None,
) -> TrimCandidate:
    text = clean_text(" ".join(part for part in (title, tournament_name or "") if part))
    named_fencer_ids = _matched_fencer_ids(text, fencers)
    related_ids = tuple(dict.fromkeys([*explicit_fencer_ids, *named_fencer_ids]))
    start_seconds, end_seconds = _bounded_window(
        start,
        end,
        padding_seconds=padding_seconds,
        duration_seconds=metadata.duration_seconds,
    )
    confidence, reasons = _score_candidate(
        source=source,
        text=text,
        title_text=metadata.title,
        metadata_text=metadata.description,
        related_fencer_ids=related_ids,
        explicit_fencer_ids=tuple(explicit_fencer_ids),
    )
    return TrimCandidate(
        id=_candidate_id(metadata.video_id, source, start_seconds, end_seconds, title),
        video_id=metadata.video_id,
        title=title,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        confidence=confidence,
        related_fencer_ids=related_ids,
        reasons=reasons,
        source=source,
    )


def _is_relevant_segment(text: str, fencers: Sequence[FencerReference]) -> bool:
    return bool(
        _matched_fencer_ids(text, fencers)
        or _has_versus(text)
        or _contains_any(text, BOUT_WORDS)
        or _contains_any(text, TOURNAMENT_WORDS)
    )


def _candidate_sort_key(candidate: TrimCandidate) -> tuple[float, int, str]:
    return (-candidate.confidence, candidate.start_seconds, candidate.id)


def plan_trim_candidates(
    metadata: VideoMetadata,
    *,
    fencers: Sequence[FencerReference] = (),
    known_bouts: Sequence[KnownBoutTimestamp] = (),
    padding_seconds: int = 8,
    min_confidence: float = 0.3,
) -> list[TrimCandidate]:
    candidates: list[TrimCandidate] = []

    for bout in known_bouts:
        if bout.end_seconds <= bout.start_seconds:
            continue
        label = clean_text(bout.label or bout.tournament_name or "Known bout")
        candidates.append(
            _make_candidate(
                metadata=metadata,
                source="known_bout",
                title=label,
                start=bout.start_seconds,
                end=bout.end_seconds,
                fencers=fencers,
                padding_seconds=padding_seconds,
                explicit_fencer_ids=tuple(bout.fencer_ids or ()),
                tournament_name=bout.tournament_name,
            )
        )

    chapters = list(metadata.chapters or parse_chapters(metadata.description, metadata.duration_seconds))
    for chapter in chapters:
        if chapter.end_seconds is None or chapter.end_seconds <= chapter.start_seconds:
            continue
        if not _is_relevant_segment(chapter.title, fencers):
            continue
        candidates.append(
            _make_candidate(
                metadata=metadata,
                source="chapter",
                title=chapter.title,
                start=chapter.start_seconds,
                end=chapter.end_seconds,
                fencers=fencers,
                padding_seconds=padding_seconds,
            )
        )

    if not candidates and metadata.duration_seconds and _is_relevant_segment(metadata.title, fencers):
        candidates.append(
            _make_candidate(
                metadata=metadata,
                source="full_video",
                title=metadata.title,
                start=0,
                end=metadata.duration_seconds,
                fencers=fencers,
                padding_seconds=0,
            )
        )

    filtered = [candidate for candidate in candidates if candidate.confidence >= min_confidence]
    return sorted(filtered, key=_candidate_sort_key)


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", clean_text(value)).strip("-._")
    return slug or "trim-candidate"


def build_ffmpeg_command(
    *,
    local_video_path: str | Path,
    candidate: TrimCandidate,
    output_dir: str | Path,
    ffmpeg_path: str = "ffmpeg",
) -> tuple[list[str], Path]:
    output = Path(output_dir) / f"{safe_slug(candidate.id)}.mp4"
    duration = max(1, candidate.end_seconds - candidate.start_seconds)
    command = [
        ffmpeg_path,
        "-y",
        "-ss",
        format_timecode(candidate.start_seconds),
        "-i",
        str(local_video_path),
        "-t",
        format_timecode(duration),
        "-map",
        "0",
        "-c",
        "copy",
        str(output),
    ]
    return command, output


def resolve_ffmpeg(ffmpeg_path: str | None = None) -> str | None:
    if ffmpeg_path:
        requested = str(ffmpeg_path)
        path = Path(requested)
        if path.is_absolute() or "/" in requested:
            return requested if path.is_file() and os.access(path, os.X_OK) else None
        return shutil.which(requested)
    return shutil.which("ffmpeg")


def plan_trim_commands(
    candidates: Sequence[TrimCandidate],
    *,
    local_video_path: str | Path | None = None,
    output_dir: str | Path = "trimmed-video",
    ffmpeg_path: str | None = None,
    execute: bool = False,
    runner: Callable[[list[str]], Any] | None = None,
) -> list[TrimCommandPlan]:
    resolved_ffmpeg = resolve_ffmpeg(ffmpeg_path)
    ffmpeg_bin = resolved_ffmpeg or ffmpeg_path or "ffmpeg"
    input_path: str | Path = local_video_path or "<LOCAL_VIDEO_PATH>"
    has_local_input = local_video_path is not None and Path(local_video_path).is_file()
    output_path = Path(output_dir)
    plans: list[TrimCommandPlan] = []

    for candidate in candidates:
        command, output = build_ffmpeg_command(
            local_video_path=input_path,
            candidate=candidate,
            output_dir=output_path,
            ffmpeg_path=ffmpeg_bin,
        )
        reason = "dry_run"
        will_execute = False
        executed = False

        if local_video_path is None:
            reason = "local_video_path_required"
        elif not has_local_input:
            reason = "local_video_not_found"
        elif resolved_ffmpeg is None:
            reason = "ffmpeg_not_found"
        elif execute:
            will_execute = True
            output.parent.mkdir(parents=True, exist_ok=True)
            run = runner or (lambda cmd: subprocess.run(cmd, check=True))
            run(command)
            executed = True
            reason = "executed"

        plans.append(
            TrimCommandPlan(
                candidate_id=candidate.id,
                command=command,
                output_path=str(output),
                will_execute=will_execute,
                executed=executed,
                reason=reason,
            )
        )

    return plans


def candidates_to_dicts(candidates: Sequence[TrimCandidate]) -> list[dict[str, Any]]:
    return [asdict(candidate) for candidate in candidates]


def command_plans_to_dicts(plans: Sequence[TrimCommandPlan]) -> list[dict[str, Any]]:
    return [asdict(plan) for plan in plans]


def _metadata_from_json(path: Path) -> tuple[VideoMetadata, list[FencerReference], list[KnownBoutTimestamp]]:
    data = json.loads(path.read_text())
    chapters = [
        Chapter(
            start_seconds=int(chapter["start_seconds"]),
            end_seconds=chapter.get("end_seconds"),
            title=chapter["title"],
        )
        for chapter in data.get("chapters", [])
    ]
    metadata = VideoMetadata(
        video_id=data["video_id"],
        title=data["title"],
        description=data.get("description", ""),
        duration_seconds=data.get("duration_seconds"),
        chapters=chapters,
    )
    fencers = [
        FencerReference(id=row["id"], name=row["name"], aliases=tuple(row.get("aliases", ())))
        for row in data.get("fencers", [])
    ]
    known_bouts = [
        KnownBoutTimestamp(
            start_seconds=int(row["start_seconds"]),
            end_seconds=int(row["end_seconds"]),
            label=row.get("label", ""),
            fencer_ids=tuple(row.get("fencer_ids", ())),
            tournament_name=row.get("tournament_name"),
        )
        for row in data.get("known_bouts", [])
    ]
    return metadata, fencers, known_bouts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan metadata-first fencing match trims without downloading videos."
    )
    parser.add_argument("metadata_json", type=Path, help="JSON file with video metadata and optional known bouts.")
    parser.add_argument("--local-video", type=Path, default=None, help="Optional local video path for ffmpeg trims.")
    parser.add_argument("--output-dir", type=Path, default=Path("trimmed-video"))
    parser.add_argument("--execute", action="store_true", help="Execute ffmpeg only when --local-video exists.")
    parser.add_argument("--padding-seconds", type=int, default=8)
    args = parser.parse_args()

    metadata, fencers, known_bouts = _metadata_from_json(args.metadata_json)
    candidates = plan_trim_candidates(
        metadata,
        fencers=fencers,
        known_bouts=known_bouts,
        padding_seconds=args.padding_seconds,
    )
    plans = plan_trim_commands(
        candidates,
        local_video_path=args.local_video,
        output_dir=args.output_dir,
        execute=args.execute,
    )
    print(json.dumps({"candidates": candidates_to_dicts(candidates), "trim_plans": command_plans_to_dicts(plans)}, indent=2))


if __name__ == "__main__":
    main()

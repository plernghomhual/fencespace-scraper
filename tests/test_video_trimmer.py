import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


VIDEO_DESCRIPTION = """
FIE Foil Grand Prix Cairo 2026 - Women's final table

00:00 Stream intro
00:45 Table of 64 - Lee Kiefer vs Ysaora Thibus
05:20 Break and replay
06:10 Semifinal - Alice Volpi v Lee Kiefer
14:30 Medal ceremony
"""


def test_parse_chapters_extracts_youtube_timecodes_with_inferred_ends():
    from video_trimmer import parse_chapters

    chapters = parse_chapters(VIDEO_DESCRIPTION, duration_seconds=930)

    assert [(chapter.start_seconds, chapter.end_seconds, chapter.title) for chapter in chapters] == [
        (0, 45, "Stream intro"),
        (45, 320, "Table of 64 - Lee Kiefer vs Ysaora Thibus"),
        (320, 370, "Break and replay"),
        (370, 870, "Semifinal - Alice Volpi v Lee Kiefer"),
        (870, 930, "Medal ceremony"),
    ]


def test_parse_chapters_handles_hour_timecodes_unicode_dashes_and_bad_lines():
    from video_trimmer import parse_chapters

    description = """
    1:02:03 \u2013 Gold medal bout - Lee Kiefer vs Alice Volpi
    99:99 Invalid timestamp
    1:03:10 | Medal presentation
    """

    chapters = parse_chapters(description, duration_seconds=3900)

    assert [(chapter.start_seconds, chapter.end_seconds, chapter.title) for chapter in chapters] == [
        (3723, 3790, "Gold medal bout - Lee Kiefer vs Alice Volpi"),
        (3790, 3900, "Medal presentation"),
    ]


def test_plan_trim_candidates_uses_chapters_and_known_bouts_with_fencer_ids_and_reasons():
    from video_trimmer import (
        FencerReference,
        KnownBoutTimestamp,
        VideoMetadata,
        parse_chapters,
        plan_trim_candidates,
    )

    metadata = VideoMetadata(
        video_id="yt-cairo-foil-final-table",
        title="Lee Kiefer at FIE Foil Grand Prix Cairo 2026",
        description=VIDEO_DESCRIPTION,
        duration_seconds=930,
        chapters=parse_chapters(VIDEO_DESCRIPTION, duration_seconds=930),
    )
    fencers = [
        FencerReference(id="fencer-lee-kiefer", name="Lee Kiefer", aliases=("Kiefer",)),
        FencerReference(id="fencer-ysaora-thibus", name="Ysaora Thibus", aliases=("Thibus",)),
        FencerReference(id="fencer-alice-volpi", name="Alice Volpi", aliases=("Volpi",)),
    ]
    known_bouts = [
        KnownBoutTimestamp(
            start_seconds=47,
            end_seconds=308,
            label="Lee Kiefer vs Ysaora Thibus - T64",
            fencer_ids=("fencer-lee-kiefer", "fencer-ysaora-thibus"),
            tournament_name="FIE Foil Grand Prix Cairo",
        )
    ]

    candidates = plan_trim_candidates(metadata, fencers=fencers, known_bouts=known_bouts, padding_seconds=5)

    assert len(candidates) >= 2
    top = candidates[0]
    assert top.start_seconds == 42
    assert top.end_seconds == 313
    assert top.confidence >= 0.85
    assert top.related_fencer_ids == ("fencer-lee-kiefer", "fencer-ysaora-thibus")
    assert any("known bout timestamp" in reason for reason in top.reasons)
    assert any("matched fencer" in reason for reason in top.reasons)

    semifinal = next(candidate for candidate in candidates if "Semifinal" in candidate.title)
    assert semifinal.related_fencer_ids == ("fencer-lee-kiefer", "fencer-alice-volpi")
    assert semifinal.confidence > 0.65


def test_candidate_confidence_is_lower_for_tournament_only_chapters():
    from video_trimmer import FencerReference, VideoMetadata, parse_chapters, plan_trim_candidates

    description = """
    00:00 FIE World Championships Milan 2023 opening
    02:00 Women's foil final piste
    08:00 Medal ceremony
    """
    metadata = VideoMetadata(
        video_id="yt-worlds-foil",
        title="FIE World Championships Milan 2023 foil finals",
        description=description,
        duration_seconds=600,
        chapters=parse_chapters(description, duration_seconds=600),
    )

    candidates = plan_trim_candidates(
        metadata,
        fencers=[FencerReference(id="fencer-lee-kiefer", name="Lee Kiefer")],
        known_bouts=[],
    )

    assert candidates
    assert candidates[0].related_fencer_ids == ()
    assert 0.35 <= candidates[0].confidence < 0.7
    assert any("tournament" in reason for reason in candidates[0].reasons)


def test_no_video_or_ffmpeg_does_not_execute_and_returns_auditable_dry_run(monkeypatch):
    from video_trimmer import TrimCandidate, plan_trim_commands

    calls = []
    monkeypatch.setattr("video_trimmer.shutil.which", lambda name: None)

    plans = plan_trim_commands(
        [
            TrimCandidate(
                id="yt123-10-50",
                video_id="yt123",
                title="Lee Kiefer vs Ysaora Thibus",
                start_seconds=10,
                end_seconds=50,
                confidence=0.9,
                related_fencer_ids=("fencer-lee-kiefer",),
                reasons=("known bout timestamp",),
                source="known_bout",
            )
        ],
        local_video_path=None,
        output_dir=Path("clips"),
        execute=True,
        runner=lambda command: calls.append(command),
    )

    assert calls == []
    assert plans[0].will_execute is False
    assert plans[0].executed is False
    assert plans[0].reason == "local_video_path_required"
    assert plans[0].command[0] == "ffmpeg"
    assert "<LOCAL_VIDEO_PATH>" in plans[0].command


def test_missing_explicit_ffmpeg_path_remains_dry_run_even_with_local_video(tmp_path):
    from video_trimmer import TrimCandidate, plan_trim_commands

    calls = []
    local_video = tmp_path / "match.mp4"
    local_video.write_bytes(b"placeholder")
    missing_ffmpeg = tmp_path / "missing-ffmpeg"

    plans = plan_trim_commands(
        [
            TrimCandidate(
                id="yt123-10-50",
                video_id="yt123",
                title="Lee Kiefer vs Ysaora Thibus",
                start_seconds=10,
                end_seconds=50,
                confidence=0.9,
                related_fencer_ids=("fencer-lee-kiefer",),
                reasons=("known bout timestamp",),
                source="known_bout",
            )
        ],
        local_video_path=local_video,
        output_dir=tmp_path / "clips",
        ffmpeg_path=str(missing_ffmpeg),
        execute=True,
        runner=lambda command: calls.append(command),
    )

    assert calls == []
    assert plans[0].will_execute is False
    assert plans[0].executed is False
    assert plans[0].reason == "ffmpeg_not_found"
    assert plans[0].command[0] == str(missing_ffmpeg)


def test_local_trim_command_construction_uses_copy_safe_ffmpeg_arguments(tmp_path):
    from video_trimmer import TrimCandidate, plan_trim_commands

    local_video = tmp_path / "match video.mp4"
    local_video.write_bytes(b"placeholder")
    ffmpeg_path = tmp_path / "ffmpeg"
    ffmpeg_path.write_text("#!/bin/sh\n")
    ffmpeg_path.chmod(0o755)

    plans = plan_trim_commands(
        [
            TrimCandidate(
                id="candidate one",
                video_id="yt123",
                title="Lee Kiefer vs Alice Volpi",
                start_seconds=12,
                end_seconds=72,
                confidence=0.88,
                related_fencer_ids=("fencer-lee-kiefer", "fencer-alice-volpi"),
                reasons=("chapter mentions matched fencer",),
                source="chapter",
            )
        ],
        local_video_path=local_video,
        output_dir=tmp_path / "clips",
        ffmpeg_path=str(ffmpeg_path),
        execute=False,
    )

    assert plans[0].will_execute is False
    assert plans[0].executed is False
    assert plans[0].reason == "dry_run"
    assert plans[0].output_path == str(tmp_path / "clips" / "candidate-one.mp4")
    assert plans[0].command == [
        str(ffmpeg_path),
        "-y",
        "-ss",
        "00:00:12",
        "-i",
        str(local_video),
        "-t",
        "00:01:00",
        "-map",
        "0",
        "-c",
        "copy",
        str(tmp_path / "clips" / "candidate-one.mp4"),
    ]

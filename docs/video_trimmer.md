# Video Trimmer

`video_trimmer.py` plans fencing match clips from YouTube metadata. It is metadata-first: it reads a title, description, parsed chapters, and optional known bout timestamps, then returns auditable trim candidates.

It does not download videos. Actual trimming requires an explicit local video path.

## Inputs

The planner accepts:

- `VideoMetadata`: `video_id`, `title`, optional `description`, optional `duration_seconds`, and optional `Chapter` entries.
- `FencerReference`: known fencer IDs, display names, and aliases.
- `KnownBoutTimestamp`: caller-provided bout start/end seconds, label, related fencer IDs, and optional tournament name.

If chapters are not supplied, `parse_chapters()` extracts YouTube-style description timestamps such as `00:45 Lee Kiefer vs Ysaora Thibus` or `1:02:03 - Gold medal bout`.

## Output

`plan_trim_candidates()` returns `TrimCandidate` records with:

- `start_seconds` and `end_seconds`, including configured padding.
- `confidence`, a bounded 0.0-1.0 score.
- `related_fencer_ids`, matched from explicit bout metadata or fencer names/aliases in metadata.
- `reasons`, including evidence such as known bout timestamp, chapter timestamp, matched fencer name, versus marker, bout phase marker, and tournament context.
- `source`, usually `known_bout`, `chapter`, or `full_video`.

Candidates are sorted by confidence and then start time.

## ffmpeg Behavior

`plan_trim_commands()` always returns planned ffmpeg commands for review. It only executes when all of these are true:

- `execute=True`
- `local_video_path` is supplied
- the local video path exists
- ffmpeg is available from `ffmpeg_path` or `PATH`

Without a local video path, the command includes `<LOCAL_VIDEO_PATH>` and the plan reason is `local_video_path_required`. If ffmpeg is missing, the reason is `ffmpeg_not_found`. This keeps planning useful on machines without local video tooling.

The command uses stream copy:

```bash
ffmpeg -y -ss 00:00:12 -i match.mp4 -t 00:01:00 -map 0 -c copy clips/candidate.mp4
```

Stream-copy trimming is fast but can be keyframe-aligned. For frame-exact clips, manually re-encode after review.

## CLI

Provide a JSON file with metadata, optional fencers, and optional known bouts:

```json
{
  "video_id": "yt-cairo-foil-final-table",
  "title": "Lee Kiefer at FIE Foil Grand Prix Cairo 2026",
  "description": "00:45 Lee Kiefer vs Ysaora Thibus",
  "duration_seconds": 930,
  "fencers": [
    {"id": "fencer-lee-kiefer", "name": "Lee Kiefer", "aliases": ["Kiefer"]}
  ],
  "known_bouts": [
    {
      "start_seconds": 47,
      "end_seconds": 308,
      "label": "Lee Kiefer vs Ysaora Thibus - T64",
      "fencer_ids": ["fencer-lee-kiefer"]
    }
  ]
}
```

Dry-run planning:

```bash
.venv/bin/python video_trimmer.py metadata.json
```

Plan commands against a local file without executing:

```bash
.venv/bin/python video_trimmer.py metadata.json --local-video ./match.mp4
```

Execute local trims:

```bash
.venv/bin/python video_trimmer.py metadata.json --local-video ./match.mp4 --execute
```

## Limitations

- Metadata matches are heuristic. Similar names, broadcast overlays, mislabeled chapters, and copied descriptions can produce false positives.
- The planner does not inspect video frames, audio, scoreboards, or uniforms.
- Chapter end times are inferred from the next chapter or video duration.
- Known bout timestamps are trusted as caller-provided evidence; bad input produces bad clip windows.
- Every candidate requires manual review before publication, athlete tagging, or downstream database writes.

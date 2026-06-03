# FenceSpace Calendar Feed

`calendar_feed.py` generates read-only iCalendar (`.ics`) feeds from `fs_tournaments` rows. It can be used as a pure generator, through the included CLI, or mounted by the public API later without changing the feed logic.

## Filters

Supported filters:

- `federation`: federation/source filter. In Supabase queries this maps to `fs_tournaments.type`; the pure generator also accepts row-level `federation` or `metadata.source`.
- `country`: country name or 2/3-letter code.
- `weapon`: `Foil`, `Epee`, or `Sabre`. `épée` is normalized to `Epee`.
- `category`: examples: `Senior`, `Junior`, `Cadet`, `Veteran`.
- `from-date`: inclusive lower bound, `YYYY-MM-DD`.
- `to-date`: inclusive upper bound, `YYYY-MM-DD`.
- `timezone`: IANA timezone used for naive datetime rows. Date-only tournament rows are emitted as all-day events.
- `limit`: capped at 500 events.

Invalid weapons, invalid dates, unrecognized timezones, control characters, and non-positive limits are rejected.

## API-Compatible URL Shape

No API route is added by this module. If the web API mounts `generate_ics_feed_from_client()`, use a URL shape like:

```text
/calendar.ics?federation=FIE&country=Egypt&weapon=Epee&category=Senior&from-date=2026-01-01&to-date=2026-12-31
```

More examples:

```text
/calendar.ics?country=USA&weapon=Foil&from-date=2026-03-01&to-date=2026-06-30
/calendar.ics?federation=AskFRED&category=Junior&limit=100
/calendar.ics?weapon=Sabre&timezone=America/New_York
```

The route should return `text/calendar; charset=utf-8` and use normal read-only API authentication/rate limiting.

## CLI

Generate from Supabase:

```bash
.venv/bin/python calendar_feed.py --federation FIE --weapon Epee --from-date 2026-01-01 --to-date 2026-12-31 --output fie-epee.ics
```

Generate from a captured JSON fixture:

```bash
.venv/bin/python calendar_feed.py --input tournaments.json --country USA --weapon Foil > usa-foil.ics
```

The input file can be either a JSON array of tournament rows or an object with a `data` array.

## Client Behavior

Calendar clients such as Google Calendar, Apple Calendar, Outlook, and Thunderbird subscribe by URL and periodically refresh the feed. Refresh intervals are controlled by the client and can range from minutes to many hours.

UIDs are stable across refreshes:

- `source_id` is preferred.
- `id` is used if `source_id` is missing.
- A deterministic fallback hash uses name, start date, country, weapon, and category.

Date-only tournament rows produce all-day events with inclusive tournament dates converted to iCalendar's exclusive `DTEND`. For example, a tournament from `2026-02-13` through `2026-02-15` is emitted as:

```text
DTSTART;VALUE=DATE:20260213
DTEND;VALUE=DATE:20260216
```

Rows without a valid `start_date` are skipped so clients do not receive undated events.

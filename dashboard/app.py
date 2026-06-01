from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st


REQUIRED_ENV_VARS = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")

PAGE_STATUS = "Status Dashboard"
PAGE_COUNTS = "Data Counts"
PAGE_COVERAGE = "Coverage Map"
PAGE_ERRORS = "Error Log"

PAGES = (PAGE_STATUS, PAGE_COUNTS, PAGE_COVERAGE, PAGE_ERRORS)

DEFAULT_SCRAPER_MODULES = (
    "scraper",
    "scrape_fie_events",
    "scrape_fie_history",
    "scrape_results",
    "scrape_bouts",
    "scrape_engarde",
    "scrape_olympics",
    "scrape_ncaa",
    "scrape_iwas",
    "scrape_wikidata",
    "scrape_athlete_profiles",
    "scrape_rankings_history",
    "scrape_clubs",
    "scrape_fed_british",
    "scrape_fed_canada",
    "scrape_fed_france",
    "scrape_fed_germany",
    "scrape_fed_italy",
    "scrape_fed_jpn",
    "watch_live_results",
    "data_quality_check",
    "match_orphan_results",
)

STATUS_HEALTH = {
    "completed": "success",
    "success": "success",
    "completed_with_errors": "completed_with_errors",
    "error": "error",
    "running": "running",
}

HEALTH_BACKGROUND = {
    "success": "#d1fae5",
    "completed_with_errors": "#fef3c7",
    "running": "#dbeafe",
    "error": "#fee2e2",
    "no recent run": "#e5e7eb",
    "no run": "#e5e7eb",
}


def _missing_env_vars() -> list[str]:
    return [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]


@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Any:
    missing = _missing_env_vars()
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    from supabase import create_client

    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def _fetch_all(
    client: Any,
    table_name: str,
    columns: str = "*",
    *,
    page_size: int = 1000,
    order_by: str | None = None,
    desc: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table_name).select(columns)
        if order_by:
            query = query.order(order_by, desc=desc)
        page = query.range(start, start + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _try_fetch_all(
    client: Any,
    table_name: str,
    columns: str = "*",
    *,
    warn: bool = True,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    try:
        return _fetch_all(client, table_name, columns, **kwargs)
    except Exception as exc:
        if warn:
            st.warning(f"Could not read {table_name}: {exc}")
        return []


def _count_rows(client: Any, table_name: str) -> int | None:
    try:
        result = client.table(table_name).select("id", count="exact").limit(0).execute()
        if getattr(result, "count", None) is not None:
            return int(result.count)
        return len(result.data or [])
    except Exception:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _display_datetime(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _metadata_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _latest_run_by_module(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        module = str(row.get("module") or "").strip()
        if not module:
            continue
        run_time = _parse_datetime(row.get("started_at")) or datetime.min.replace(tzinfo=timezone.utc)
        current = latest.get(module)
        current_time = _parse_datetime((current or {}).get("started_at")) if current else None
        if current is None or current_time is None or run_time > current_time:
            latest[module] = row
    return latest


def _health_for_run(row: dict[str, Any] | None) -> str:
    if not row:
        return "no run"
    status = str(row.get("status") or "").strip().lower()
    reference_time = _parse_datetime(row.get("completed_at")) or _parse_datetime(row.get("started_at"))
    if not reference_time:
        return "no recent run"
    if datetime.now(timezone.utc) - reference_time > timedelta(hours=48):
        return "no recent run"
    return STATUS_HEALTH.get(status, "completed_with_errors")


def _normalize_status_row(module: str, row: dict[str, Any] | None) -> dict[str, Any]:
    health = _health_for_run(row)
    return {
        "module": module,
        "last_run_time": _display_datetime((row or {}).get("started_at")),
        "completed_at": _display_datetime((row or {}).get("completed_at")),
        "status": (row or {}).get("status") or "no_run",
        "health": health,
        "written": _to_int((row or {}).get("written")),
        "failed": _to_int((row or {}).get("failed")),
        "skipped": _to_int((row or {}).get("skipped")),
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_status_rows(_client: Any) -> list[dict[str, Any]]:
    runs = _try_fetch_all(
        _client,
        "fs_scraper_runs",
        "module,started_at,completed_at,status,written,failed,skipped,metadata",
        order_by="started_at",
        desc=True,
    )
    latest = _latest_run_by_module(runs)
    modules = list(DEFAULT_SCRAPER_MODULES)
    for module in sorted(latest):
        if module not in modules:
            modules.append(module)
    return [_normalize_status_row(module, latest.get(module)) for module in modules]


def _season_key(value: Any) -> tuple[int, str]:
    text = str(value or "unknown")
    try:
        return (1, f"{int(text):06d}")
    except ValueError:
        return (0, text)


def _rows_from_counter(counter: Counter[str], key_name: str, value_name: str) -> list[dict[str, Any]]:
    return [
        {key_name: key, value_name: count}
        for key, count in sorted(counter.items(), key=lambda item: item[0])
    ]


def _fencer_source_counts(
    client: Any,
    result_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    view_rows = _try_fetch_all(
        client,
        "v_fencer_source_coverage",
        "source_name,fencer_count",
        warn=False,
    )
    if view_rows:
        return [
            {
                "source": str(row.get("source_name") or row.get("source") or "unknown"),
                "fencers": _to_int(row.get("fencer_count")),
            }
            for row in view_rows
        ]

    counts: list[dict[str, Any]] = []
    fencer_count = _count_rows(client, "fs_fencers")
    if fencer_count is not None:
        counts.append({"source": "fs_fencers", "fencers": fencer_count})

    ranking_count = _count_rows(client, "fs_national_fed_rankings")
    if ranking_count is not None:
        counts.append({"source": "fs_national_fed_rankings", "fencers": ranking_count})

    linked_fencers = {
        row.get("fencer_id")
        for row in result_rows
        if row.get("fencer_id") not in (None, "")
    }
    counts.append({"source": "fs_results_linked", "fencers": len(linked_fencers)})
    return counts


@st.cache_data(ttl=300, show_spinner=False)
def fetch_data_counts(_client: Any) -> dict[str, list[dict[str, Any]]]:
    tournaments = _try_fetch_all(_client, "fs_tournaments", "id,season,type,source_id")
    results = _try_fetch_all(_client, "fs_results", "id,tournament_id,fencer_id")

    tournament_by_id = {
        row.get("id"): row
        for row in tournaments
        if row.get("id") not in (None, "")
    }

    tournament_seasons: Counter[str] = Counter(str(row.get("season") or "unknown") for row in tournaments)
    result_types: Counter[str] = Counter()
    orphan_types: Counter[str] = Counter()

    for row in results:
        tournament = tournament_by_id.get(row.get("tournament_id")) or {}
        competition_type = str(tournament.get("type") or "unknown")
        result_types[competition_type] += 1
        if row.get("fencer_id") in (None, ""):
            orphan_types[competition_type] += 1

    view_orphans = _try_fetch_all(
        _client,
        "v_orphan_results",
        "tournament_type,orphan_count",
        warn=False,
    )
    if view_orphans:
        orphan_rows = [
            {
                "competition_type": str(row.get("tournament_type") or "unknown"),
                "orphans": _to_int(row.get("orphan_count")),
            }
            for row in view_orphans
        ]
    else:
        orphan_rows = _rows_from_counter(orphan_types, "competition_type", "orphans")

    season_rows = [
        {"season": season, "tournaments": count}
        for season, count in sorted(
            tournament_seasons.items(),
            key=lambda item: _season_key(item[0]),
            reverse=True,
        )
    ]

    return {
        "fencers_per_source": _fencer_source_counts(_client, results),
        "tournaments_per_season": season_rows,
        "results_per_competition_type": _rows_from_counter(
            result_types,
            "competition_type",
            "results",
        ),
        "orphan_counts": orphan_rows,
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_coverage_rows(_client: Any) -> list[dict[str, Any]]:
    fencers = _try_fetch_all(_client, "fs_fencers", "id,country")
    by_country: Counter[str] = Counter()
    for row in fencers:
        country = str(row.get("country") or "").strip()
        if country:
            by_country[country] += 1
    return _rows_from_counter(by_country, "country", "fencers")


def _error_message(row: dict[str, Any]) -> str:
    metadata = _metadata_dict(row.get("metadata"))
    message = metadata.get("error") or metadata.get("message")
    if message:
        return str(message)
    failed = _to_int(row.get("failed"))
    if failed:
        return f"{failed} failed rows"
    return ""


@st.cache_data(ttl=300, show_spinner=False)
def fetch_error_rows(_client: Any) -> list[dict[str, Any]]:
    runs = _try_fetch_all(
        _client,
        "fs_scraper_runs",
        "module,started_at,completed_at,status,failed,metadata",
        order_by="started_at",
        desc=True,
    )
    errors: list[dict[str, Any]] = []
    for row in runs:
        status = str(row.get("status") or "").lower()
        message = _error_message(row)
        failed = _to_int(row.get("failed"))
        if status == "error" or status == "completed_with_errors" or failed > 0 or message:
            errors.append(
                {
                    "module": row.get("module") or "",
                    "started_at": _display_datetime(row.get("started_at")),
                    "completed_at": _display_datetime(row.get("completed_at")),
                    "status": row.get("status") or "",
                    "failed": failed,
                    "error_message": message,
                }
            )
    return errors[:250]


def _plotly_express() -> Any:
    import plotly.express as px

    return px


def _dataframe(rows: list[dict[str, Any]], *, hide_index: bool = True) -> None:
    if not rows:
        st.info("No rows found.")
        return
    try:
        import pandas as pd
    except Exception:
        st.dataframe(rows, use_container_width=True)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=hide_index)


def _bar_chart(rows: list[dict[str, Any]], *, x: str, y: str, title: str) -> None:
    if not rows:
        st.info("No rows found.")
        return
    try:
        px = _plotly_express()
        fig = px.bar(rows, x=x, y=y, title=title)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not render chart: {exc}")
        _dataframe(rows)


def render_status_dashboard(client: Any) -> None:
    st.header(PAGE_STATUS)
    rows = fetch_status_rows(client)
    if not rows:
        st.info("No scraper runs found.")
        return

    try:
        import pandas as pd
    except Exception:
        _dataframe(rows)
        return

    df = pd.DataFrame(rows)

    def style_status(row: Any) -> list[str]:
        background = HEALTH_BACKGROUND.get(str(row.get("health")), "#ffffff")
        return [f"background-color: {background}" for _ in row]

    st.dataframe(
        df.style.apply(style_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )


def render_data_counts(client: Any) -> None:
    st.header(PAGE_COUNTS)
    data = fetch_data_counts(client)

    st.subheader("Fencers per source")
    _bar_chart(
        data["fencers_per_source"],
        x="source",
        y="fencers",
        title="Fencers per source",
    )

    st.subheader("Tournaments per season")
    _bar_chart(
        data["tournaments_per_season"],
        x="season",
        y="tournaments",
        title="Tournaments per season",
    )

    st.subheader("Results per competition type")
    _bar_chart(
        data["results_per_competition_type"],
        x="competition_type",
        y="results",
        title="Results per competition type",
    )

    st.subheader("Orphan counts")
    _dataframe(data["orphan_counts"])


def render_coverage_map(client: Any) -> None:
    st.header(PAGE_COVERAGE)
    rows = fetch_coverage_rows(client)
    if not rows:
        st.info("No fencer country data found.")
        return

    try:
        px = _plotly_express()
        fig = px.choropleth(
            rows,
            locations="country",
            locationmode="country names",
            color="fencers",
            hover_name="country",
            color_continuous_scale="Viridis",
        )
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not render map: {exc}")
        _dataframe(rows)


def render_error_log(client: Any) -> None:
    st.header(PAGE_ERRORS)
    rows = fetch_error_rows(client)
    modules = ["All"] + sorted({str(row.get("module") or "") for row in rows if row.get("module")})
    selected_module = st.selectbox("Module", modules)
    search = st.text_input("Search errors", "")
    search_text = search.strip().lower()

    filtered = rows
    if selected_module != "All":
        filtered = [row for row in filtered if row.get("module") == selected_module]
    if search_text:
        filtered = [
            row
            for row in filtered
            if search_text in " ".join(str(value) for value in row.values()).lower()
        ]

    _dataframe(filtered)


def main() -> None:
    st.set_page_config(page_title="Scraper Health", layout="wide")
    st.title("Scraper Health")

    missing = _missing_env_vars()
    if missing:
        st.error(f"Missing required environment variables: {', '.join(missing)}")
        st.stop()

    client = get_supabase_client()
    page = st.sidebar.radio("Page", PAGES)

    if page == PAGE_STATUS:
        render_status_dashboard(client)
    elif page == PAGE_COUNTS:
        render_data_counts(client)
    elif page == PAGE_COVERAGE:
        render_coverage_map(client)
    elif page == PAGE_ERRORS:
        render_error_log(client)
    else:
        st.error(f"Unknown page: {page}")


if __name__ == "__main__":
    main()

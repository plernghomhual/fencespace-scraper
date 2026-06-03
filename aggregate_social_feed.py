import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import unescape
from typing import Any

import requests

from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "aggregate_social_feed"
BATCH_SIZE = 100
MAX_EXCERPT_LENGTH = 500
DEFAULT_QUERIES = [
    "#fencing",
    "fencing epee foil sabre",
    "\"fencing world cup\"",
    "\"fencing grand prix\"",
]

FENCING_HASHTAGS = {
    "fencing",
    "fencer",
    "fencers",
    "epee",
    "épée",
    "foil",
    "sabre",
    "saber",
    "escrime",
    "esgrima",
}
FENCING_CONTEXT_TERMS = {
    "fencing",
    "fencer",
    "fencers",
    "epee",
    "épée",
    "foil",
    "sabre",
    "saber",
    "escrime",
    "esgrima",
    "fie",
    "piste",
    "bout",
    "world cup",
    "grand prix",
    "championship",
    "tournament",
}
FALSE_POSITIVE_PHRASES = {
    "privacy fence",
    "fence installation",
    "fencing contractor",
    "yard fence",
    "garden fence",
    "vinyl fence",
    "chain link",
    "cattle fence",
    "fence repair",
    "fence panels",
    "perimeter fence",
    "electric fence",
    "wood fence",
}
SPORT_DISAMBIGUATORS = {
    "epee",
    "épée",
    "foil",
    "sabre",
    "saber",
    "fencer",
    "fencers",
    "fie",
    "piste",
    "bout",
    "world cup",
    "grand prix",
    "championship",
    "tournament",
}
SPAM_TERMS = {
    "crypto",
    "casino",
    "betting",
    "onlyfans",
    "viagra",
    "loan offer",
    "promo code",
    "work from home",
}
PRIVATE_VISIBILITIES = {"private", "direct", "followers", "followers-only", "limited"}


@dataclass(frozen=True)
class RawSocialPost:
    platform: str
    post_id: str
    author: str | None
    url: str
    text: str
    hashtags: list[str]
    language: str | None
    posted_at: datetime
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    allows_text_excerpt: bool = False


@dataclass(frozen=True)
class FencerSocialLink:
    fencer_id: str
    platform: str
    handle: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class TournamentLink:
    id: str
    name: str


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_hashtag(tag: str | None) -> str:
    if not tag:
        return ""
    return tag.strip().lstrip("#").strip().lower()


def unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def extract_hashtags(text: str) -> list[str]:
    return [
        normalize_hashtag(match)
        for match in re.findall(r"#([\w\u00c0-\uffff-]+)", text or "")
    ]


def normalize_handle(handle: str | None) -> str:
    if not handle:
        return ""
    return handle.strip().lstrip("@").rstrip("/").lower()


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    return url.strip().rstrip("/").lower()


def normalize_platform(platform: str | None) -> str:
    platform = (platform or "").strip().lower()
    if platform in {"twitter", "x.com"}:
        return "x"
    return platform


def make_bluesky_url(uri: str, handle: str | None) -> str:
    rkey = uri.rstrip("/").split("/")[-1]
    if handle and rkey:
        return f"https://bsky.app/profile/{handle}/post/{rkey}"
    return uri


def parse_bluesky_search_response(payload: dict[str, Any], query: str) -> list[RawSocialPost]:
    posts: list[RawSocialPost] = []
    for item in payload.get("posts", []):
        record = item.get("record") or {}
        author = (item.get("author") or {}).get("handle")
        text = clean_text(record.get("text"))
        uri = item.get("uri") or item.get("cid")
        if not uri or not text:
            continue

        facet_tags: list[str] = []
        for facet in record.get("facets") or []:
            for feature in facet.get("features") or []:
                if str(feature.get("$type", "")).endswith("#tag"):
                    facet_tags.append(normalize_hashtag(feature.get("tag")))
        hashtags = unique_preserving_order(facet_tags + extract_hashtags(text))
        langs = record.get("langs") or []
        language = langs[0].lower() if langs else None
        labels = item.get("labels") or []
        posts.append(
            RawSocialPost(
                platform="bluesky",
                post_id=uri,
                author=author,
                url=make_bluesky_url(uri, author),
                text=text,
                hashtags=hashtags,
                language=language,
                posted_at=parse_datetime(record.get("createdAt") or item.get("indexedAt")),
                source="bluesky_public_search",
                metadata={
                    "query": query,
                    "cid": item.get("cid"),
                    "uri": uri,
                    "labels": labels,
                },
                allows_text_excerpt=True,
            )
        )
    return posts


def parse_mastodon_tag_response(
    payload: list[dict[str, Any]], instance: str, query: str
) -> list[RawSocialPost]:
    posts: list[RawSocialPost] = []
    for item in payload:
        account = item.get("account") or {}
        text = clean_text(item.get("content"))
        post_id = str(item.get("id") or "")
        url = item.get("url") or item.get("uri") or ""
        if not post_id or not url or not text:
            continue
        tags = [normalize_hashtag(tag.get("name")) for tag in item.get("tags") or []]
        hashtags = unique_preserving_order(tags + extract_hashtags(text))
        posts.append(
            RawSocialPost(
                platform="mastodon",
                post_id=post_id,
                author=account.get("acct") or account.get("username"),
                url=url,
                text=text,
                hashtags=hashtags,
                language=(item.get("language") or "").lower() or None,
                posted_at=parse_datetime(item.get("created_at")),
                source=f"mastodon:{instance}",
                metadata={
                    "query": query,
                    "instance": instance,
                    "visibility": item.get("visibility"),
                    "possibly_sensitive": bool(item.get("sensitive")),
                },
                allows_text_excerpt=True,
            )
        )
    return posts


def parse_x_recent_search_response(payload: dict[str, Any], query: str) -> list[RawSocialPost]:
    users = {
        user.get("id"): user.get("username")
        for user in (payload.get("includes") or {}).get("users", [])
    }
    posts: list[RawSocialPost] = []
    for item in payload.get("data") or []:
        text = clean_text(item.get("text"))
        post_id = str(item.get("id") or "")
        if not post_id or not text:
            continue
        username = users.get(item.get("author_id")) or item.get("author_id")
        entities = item.get("entities") or {}
        entity_tags = [
            normalize_hashtag(tag.get("tag")) for tag in entities.get("hashtags") or []
        ]
        hashtags = unique_preserving_order(entity_tags + extract_hashtags(text))
        posts.append(
            RawSocialPost(
                platform="x",
                post_id=post_id,
                author=username,
                url=f"https://x.com/{username}/status/{post_id}" if username else "",
                text=text,
                hashtags=hashtags,
                language=(item.get("lang") or "").lower() or None,
                posted_at=parse_datetime(item.get("created_at")),
                source="x_recent_search",
                metadata={
                    "query": query,
                    "possibly_sensitive": bool(item.get("possibly_sensitive")),
                },
                allows_text_excerpt=False,
            )
        )
    return posts


class XRecentSearchProvider:
    name = "x"
    platform = "x"
    required_env = ("X_BEARER_TOKEN",)
    rate_limit_seconds = 2.0
    allows_text_excerpt = False

    def __init__(
        self,
        env: dict[str, str] | None = None,
        http_get=None,
        sleep=time.sleep,
    ):
        self.env = env if env is not None else os.environ
        self.http_get = http_get or requests.get
        self.sleep = sleep

    def missing_configuration(self) -> list[str]:
        return [key for key in self.required_env if not self.env.get(key)]

    def fetch(self, queries: list[str]) -> list[RawSocialPost]:
        missing = self.missing_configuration()
        if missing:
            raise RuntimeError(f"missing provider keys: {', '.join(missing)}")
        token = self.env["X_BEARER_TOKEN"]
        posts: list[RawSocialPost] = []
        headers = {"Authorization": f"Bearer {token}"}
        for index, query in enumerate(queries):
            if index:
                self.sleep(self.rate_limit_seconds)
            response = self.http_get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": f"({query}) -is:retweet",
                    "max_results": 50,
                    "tweet.fields": "created_at,lang,possibly_sensitive,entities,author_id",
                    "expansions": "author_id",
                    "user.fields": "username,name",
                },
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            posts.extend(parse_x_recent_search_response(response.json(), query=query))
        return posts


class BlueskySearchProvider:
    name = "bluesky"
    platform = "bluesky"
    required_env: tuple[str, ...] = ()
    rate_limit_seconds = 1.0
    allows_text_excerpt = True

    def __init__(
        self,
        env: dict[str, str] | None = None,
        http_get=None,
        sleep=time.sleep,
    ):
        self.env = env if env is not None else os.environ
        self.http_get = http_get or requests.get
        self.sleep = sleep

    def missing_configuration(self) -> list[str]:
        if str(self.env.get("BLUESKY_SEARCH_ENABLED", "")).lower() not in {"1", "true", "yes"}:
            return ["BLUESKY_SEARCH_ENABLED"]
        return []

    def fetch(self, queries: list[str]) -> list[RawSocialPost]:
        posts: list[RawSocialPost] = []
        for index, query in enumerate(queries):
            if index:
                self.sleep(self.rate_limit_seconds)
            response = self.http_get(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
                params={"q": query, "limit": 50},
                headers={"User-Agent": "FenceSpaceScraper/1.0"},
                timeout=30,
            )
            response.raise_for_status()
            posts.extend(parse_bluesky_search_response(response.json(), query=query))
        return posts


def is_private_or_unsafe(post: RawSocialPost) -> bool:
    visibility = str(post.metadata.get("visibility", "")).lower()
    if visibility in PRIVATE_VISIBILITIES:
        return True
    if post.metadata.get("possibly_sensitive"):
        return True
    labels = post.metadata.get("labels")
    return bool(labels)


def is_spam(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in SPAM_TERMS)


def is_fencing_related(post: RawSocialPost) -> bool:
    if FENCING_HASHTAGS.intersection(set(post.hashtags)):
        return True
    lowered = post.text.lower()
    return any(term in lowered for term in FENCING_CONTEXT_TERMS)


def is_non_fencing_false_positive(post: RawSocialPost) -> bool:
    lowered = post.text.lower()
    if not any(phrase in lowered for phrase in FALSE_POSITIVE_PHRASES):
        return False
    return not any(term in lowered for term in SPORT_DISAMBIGUATORS)


def filter_and_dedupe_posts(
    posts: list[RawSocialPost],
) -> tuple[list[RawSocialPost], dict[str, int]]:
    stats = {
        "input": len(posts),
        "kept": 0,
        "duplicates": 0,
        "spam": 0,
        "false_positives": 0,
        "unsafe_or_private": 0,
    }
    seen: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()
    kept: list[RawSocialPost] = []

    for post in posts:
        if is_private_or_unsafe(post):
            stats["unsafe_or_private"] += 1
            continue
        if is_spam(post.text):
            stats["spam"] += 1
            continue
        if not is_fencing_related(post) or is_non_fencing_false_positive(post):
            stats["false_positives"] += 1
            continue

        key = (normalize_platform(post.platform), post.post_id)
        normalized_url = normalize_url(post.url)
        if key in seen or (normalized_url and normalized_url in seen_urls):
            stats["duplicates"] += 1
            continue
        seen.add(key)
        if normalized_url:
            seen_urls.add(normalized_url)
        kept.append(post)

    stats["kept"] = len(kept)
    return kept, stats


def load_fencer_links(client) -> list[FencerSocialLink]:
    result = (
        client.table("fs_fencer_social_media")
        .select("fencer_id,platform,handle,url")
        .execute()
    )
    links: list[FencerSocialLink] = []
    for row in result.data or []:
        fencer_id = row.get("fencer_id")
        if not fencer_id:
            continue
        links.append(
            FencerSocialLink(
                fencer_id=str(fencer_id),
                platform=normalize_platform(row.get("platform")),
                handle=row.get("handle"),
                url=row.get("url"),
            )
        )
    return links


def load_tournament_links(client) -> list[TournamentLink]:
    result = client.table("fs_tournaments").select("id,name").execute()
    tournaments: list[TournamentLink] = []
    for row in result.data or []:
        if row.get("id") and row.get("name"):
            tournaments.append(TournamentLink(id=str(row["id"]), name=str(row["name"])))
    return tournaments


def extract_handles(text: str) -> list[str]:
    return [
        normalize_handle(match)
        for match in re.findall(r"@([A-Za-z0-9][A-Za-z0-9._-]*(?:\.[A-Za-z0-9._-]+)*)", text or "")
    ]


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>\"]+", text or "")


def related_fencer_ids_for_post(
    post: RawSocialPost, fencer_links: list[FencerSocialLink]
) -> list[str]:
    handles = set(extract_handles(post.text))
    author_handle = normalize_handle(post.author)
    if author_handle:
        handles.add(author_handle)

    urls = {normalize_url(url) for url in extract_urls(post.text)}
    if post.url:
        urls.add(normalize_url(post.url))

    related: set[str] = set()
    post_platform = normalize_platform(post.platform)
    for link in fencer_links:
        link_platform = normalize_platform(link.platform)
        if link_platform != post_platform:
            continue
        link_handle = normalize_handle(link.handle)
        if link_handle and link_handle in handles:
            related.add(link.fencer_id)
            continue
        link_url = normalize_url(link.url)
        if link_url and any(url == link_url or url.startswith(f"{link_url}/") for url in urls):
            related.add(link.fencer_id)
    return sorted(related)


def normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def tournament_id_for_post(
    post: RawSocialPost, tournaments: list[TournamentLink]
) -> str | None:
    haystack = normalize_phrase(f"{post.text} {' '.join(post.hashtags)}")
    for tournament in sorted(tournaments, key=lambda item: len(item.name), reverse=True):
        name = normalize_phrase(tournament.name)
        if len(name) >= 6 and name in haystack:
            return tournament.id
    return None


def make_excerpt(post: RawSocialPost) -> str | None:
    if not post.allows_text_excerpt:
        return None
    text = clean_text(post.text)
    if len(text) <= MAX_EXCERPT_LENGTH:
        return text
    return text[: MAX_EXCERPT_LENGTH - 3].rstrip() + "..."


def build_feed_rows(
    posts: list[RawSocialPost],
    fencer_links: list[FencerSocialLink],
    tournaments: list[TournamentLink],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for post in posts:
        metadata = dict(post.metadata)
        metadata["excerpt_policy"] = (
            "stored" if post.allows_text_excerpt else "not_stored_provider_terms"
        )
        rows.append(
            {
                "platform": normalize_platform(post.platform),
                "post_id": post.post_id,
                "author": post.author,
                "url": post.url,
                "text_excerpt": make_excerpt(post),
                "hashtags": unique_preserving_order(
                    [normalize_hashtag(tag) for tag in post.hashtags]
                ),
                "language": (post.language or "").lower() or None,
                "related_fencer_ids": related_fencer_ids_for_post(post, fencer_links),
                "tournament_id": tournament_id_for_post(post, tournaments),
                "posted_at": post.posted_at.isoformat(),
                "source": post.source,
                "metadata": metadata,
            }
        )
    return rows


def upsert_social_feed_rows(client, rows: list[dict[str, Any]]) -> None:
    for index in range(0, len(rows), BATCH_SIZE):
        client.table("fs_social_feed").upsert(
            rows[index : index + BATCH_SIZE], on_conflict="platform,post_id"
        ).execute()


def build_default_providers(env: dict[str, str] | None = None):
    env = env if env is not None else os.environ
    providers = [XRecentSearchProvider(env=env)]
    if env.get("BLUESKY_SEARCH_ENABLED"):
        providers.append(BlueskySearchProvider(env=env))
    return providers


def _missing_provider_keys(providers) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for provider in providers:
        provider_missing = provider.missing_configuration()
        if provider_missing:
            missing[provider.name] = provider_missing
    return missing


def run(
    client,
    providers=None,
    env: dict[str, str] | None = None,
    sleep=time.sleep,
) -> dict[str, Any]:
    env = env if env is not None else os.environ
    providers = list(providers) if providers is not None else build_default_providers(env)
    missing_provider_keys = _missing_provider_keys(providers)
    configured = [
        provider for provider in providers if provider.name not in missing_provider_keys
    ]

    if not configured:
        print(
            "Social feed dry run: no configured public/API search providers. "
            f"Missing provider keys/settings: {missing_provider_keys}"
        )
        return {
            "dry_run": True,
            "providers": 0,
            "written": 0,
            "failed": 0,
            "skipped": len(providers),
            "missing_provider_keys": missing_provider_keys,
            "filter_stats": {},
        }

    all_posts: list[RawSocialPost] = []
    failed = 0
    for provider in configured:
        try:
            all_posts.extend(provider.fetch(DEFAULT_QUERIES))
            if provider.rate_limit_seconds:
                sleep(provider.rate_limit_seconds)
        except Exception as exc:
            failed += 1
            print(f"Social feed provider {provider.name} failed: {exc}")

    filtered_posts, filter_stats = filter_and_dedupe_posts(all_posts)
    rows: list[dict[str, Any]] = []
    if filtered_posts:
        fencer_links = load_fencer_links(client)
        tournaments = load_tournament_links(client)
        rows = build_feed_rows(filtered_posts, fencer_links, tournaments)
        if rows:
            upsert_social_feed_rows(client, rows)

    return {
        "dry_run": False,
        "providers": len(configured),
        "written": len(rows),
        "failed": failed,
        "skipped": len(providers) - len(configured) + filter_stats.get("input", 0) - filter_stats.get("kept", 0),
        "missing_provider_keys": missing_provider_keys,
        "filter_stats": filter_stats,
    }


def _get_client(env: dict[str, str] | None = None):
    env = env if env is not None else os.environ
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
    from supabase import create_client

    return create_client(url, key)


def main() -> int:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        env = os.environ
        providers = build_default_providers(env)
        missing_provider_keys = _missing_provider_keys(providers)
        client = None
        if len(missing_provider_keys) < len(providers):
            client = _get_client(env)
        stats = run(client=client, providers=providers, env=env)
        set_state(
            SOURCE,
            "last_run",
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "stats": stats,
            },
        )
        run_log.complete(
            written=stats.get("written", 0),
            failed=stats.get("failed", 0),
            skipped=stats.get("skipped", 0),
            metadata=stats,
        )
        return 0
    except Exception as exc:
        run_log.error(str(exc))
        print(f"Social feed aggregation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

import React, { useEffect, useMemo, useState } from "react";

export const NEWS_API_ENDPOINT = "/api/news";
export const DEFAULT_NEWS_PAGE_SIZE = 10;

export type RelatedFencer = {
  id?: string;
  name: string;
};

export type NewsArticle = {
  id?: string | number;
  title: string;
  url?: string | null;
  source?: string | null;
  sourceSite?: string | null;
  source_site?: string | null;
  publishedAt?: string | null;
  published_at?: string | null;
  category?: string | null;
  categories?: string[];
  summary?: string | null;
  relatedFencers?: Array<RelatedFencer | string>;
  related_fencers?: Array<RelatedFencer | string>;
  related_fencer_ids?: string[];
};

export type NewsFeedProps = {
  initialArticles?: NewsArticle[];
  articles?: NewsArticle[];
  loadArticles?: () => Promise<NewsArticle[]>;
  pageSize?: number;
};

type Filters = {
  category: string;
  fencer: string;
  source: string;
  from: string;
  to: string;
  search: string;
};

const EMPTY_FILTERS: Filters = {
  category: "",
  fencer: "",
  source: "",
  from: "",
  to: "",
  search: "",
};

const dateFormatter = new Intl.DateTimeFormat("en", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

function normalizeText(value: string | null | undefined): string {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function labelize(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getArticleId(article: NewsArticle, index: number): string {
  return String(article.id ?? article.url ?? `${article.title}-${index}`);
}

function getSourceSite(article: NewsArticle): string {
  return article.sourceSite || article.source_site || article.source || "Unknown source";
}

function getPublishedAt(article: NewsArticle): string | null {
  return article.publishedAt || article.published_at || null;
}

function getCategories(article: NewsArticle): string[] {
  const categories = article.categories?.filter(Boolean);
  if (categories?.length) {
    return categories;
  }
  return [article.category || "general"];
}

function getRelatedFencers(article: NewsArticle): RelatedFencer[] {
  const tagged = article.relatedFencers || article.related_fencers || [];
  const fencers = tagged.map((fencer) =>
    typeof fencer === "string" ? { id: fencer, name: fencer } : fencer,
  );

  if (fencers.length === 0 && article.related_fencer_ids?.length) {
    return article.related_fencer_ids.map((id) => ({ id, name: id }));
  }

  const seen = new Set<string>();
  return fencers.filter((fencer) => {
    const key = normalizeText(fencer.id || fencer.name);
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function safeExternalUrl(url: string | null | undefined): string | null {
  if (!url) {
    return null;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

function parseDateInput(value: string, endOfDay = false): number | null {
  if (!value) {
    return null;
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const [, year, month, day] = match.map(Number);
  return Date.UTC(year, month - 1, day, endOfDay ? 23 : 0, endOfDay ? 59 : 0, endOfDay ? 59 : 0, endOfDay ? 999 : 0);
}

function articleTime(article: NewsArticle): number | null {
  const publishedAt = getPublishedAt(article);
  if (!publishedAt) {
    return null;
  }
  const time = Date.parse(publishedAt);
  return Number.isNaN(time) ? null : time;
}

function formatArticleDate(article: NewsArticle): string {
  const time = articleTime(article);
  return time === null ? "Date unavailable" : dateFormatter.format(new Date(time));
}

function articleMatchesFilters(article: NewsArticle, filters: Filters): boolean {
  const categories = getCategories(article);
  const fencers = getRelatedFencers(article);
  const source = getSourceSite(article);

  if (filters.category && !categories.includes(filters.category)) {
    return false;
  }

  if (filters.source && source !== filters.source) {
    return false;
  }

  if (filters.fencer && !fencers.some((fencer) => fencer.name === filters.fencer || fencer.id === filters.fencer)) {
    return false;
  }

  const from = parseDateInput(filters.from);
  const to = parseDateInput(filters.to, true);
  if (from !== null || to !== null) {
    const time = articleTime(article);
    if (time === null) {
      return false;
    }
    if (from !== null && time < from) {
      return false;
    }
    if (to !== null && time > to) {
      return false;
    }
  }

  const query = normalizeText(filters.search);
  if (!query) {
    return true;
  }

  const haystack = normalizeText(
    [
      article.title,
      article.summary,
      source,
      categories.join(" "),
      fencers.map((fencer) => fencer.name).join(" "),
    ].join(" "),
  );
  return haystack.includes(query);
}

export default function NewsFeed({
  initialArticles = [],
  articles,
  loadArticles,
  pageSize = DEFAULT_NEWS_PAGE_SIZE,
}: NewsFeedProps) {
  const [loadedArticles, setLoadedArticles] = useState<NewsArticle[]>(articles ?? initialArticles);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(Boolean(loadArticles && !articles));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (articles) {
      setLoadedArticles(articles);
    }
  }, [articles]);

  useEffect(() => {
    if (!loadArticles || articles) {
      return;
    }

    let isCurrent = true;
    setIsLoading(true);
    setError(null);

    loadArticles()
      .then((nextArticles) => {
        if (isCurrent) {
          setLoadedArticles(nextArticles);
        }
      })
      .catch((err: unknown) => {
        if (isCurrent) {
          const message = err instanceof Error ? err.message : "Unknown error";
          setError(message);
          setLoadedArticles([]);
        }
      })
      .finally(() => {
        if (isCurrent) {
          setIsLoading(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [articles, loadArticles]);

  const currentArticles = articles ?? loadedArticles;

  const options = useMemo(() => {
    const categories = uniqueSorted(currentArticles.flatMap(getCategories));
    const fencers = uniqueSorted(currentArticles.flatMap((article) => getRelatedFencers(article).map((fencer) => fencer.name)));
    const sources = uniqueSorted(currentArticles.map(getSourceSite));
    return { categories, fencers, sources };
  }, [currentArticles]);

  const filteredArticles = useMemo(() => {
    return currentArticles
      .map((article, index) => ({ article, index, time: articleTime(article) ?? Number.NEGATIVE_INFINITY }))
      .filter(({ article }) => articleMatchesFilters(article, filters))
      .sort((a, b) => b.time - a.time || a.index - b.index)
      .map(({ article }) => article);
  }, [currentArticles, filters]);

  const totalPages = Math.max(1, Math.ceil(filteredArticles.length / Math.max(1, pageSize)));
  const currentPage = Math.min(page, totalPages);
  const startIndex = (currentPage - 1) * pageSize;
  const visibleArticles = filteredArticles.slice(startIndex, startIndex + pageSize);
  const hasActiveFilters = Object.values(filters).some(Boolean);

  function updateFilter(name: keyof Filters, value: string) {
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(1);
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  if (isLoading && currentArticles.length === 0) {
    return (
      <section aria-labelledby="news-feed-heading" className="news-feed">
        <h2 id="news-feed-heading">Fencing News</h2>
        <p role="status">Loading fencing news...</p>
      </section>
    );
  }

  if (error && currentArticles.length === 0) {
    return (
      <section aria-labelledby="news-feed-heading" className="news-feed">
        <h2 id="news-feed-heading">Fencing News</h2>
        <p role="alert">Could not load fencing news. {error}</p>
      </section>
    );
  }

  if (!isLoading && !error && currentArticles.length === 0) {
    return (
      <section aria-labelledby="news-feed-heading" className="news-feed">
        <h2 id="news-feed-heading">Fencing News</h2>
        <div role="status">
          <p>No fencing news is available yet.</p>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="news-feed-heading" className="news-feed">
      <div className="news-feed__header">
        <div>
          <h2 id="news-feed-heading">Fencing News</h2>
          <p>
            Showing {visibleArticles.length} of {filteredArticles.length} articles
          </p>
        </div>
        {error ? <p role="alert">Could not refresh fencing news. Showing cached articles. {error}</p> : null}
      </div>

      <form className="news-feed__filters" aria-label="News filters">
        <label>
          Search
          <input
            type="search"
            value={filters.search}
            onChange={(event) => updateFilter("search", event.currentTarget.value)}
            placeholder="Title, summary, source, fencer"
          />
        </label>

        <label>
          Category
          <select value={filters.category} onChange={(event) => updateFilter("category", event.currentTarget.value)}>
            <option value="">All categories</option>
            {options.categories.map((category) => (
              <option key={category} value={category}>
                {labelize(category)}
              </option>
            ))}
          </select>
        </label>

        <label>
          Fencer
          <select value={filters.fencer} onChange={(event) => updateFilter("fencer", event.currentTarget.value)}>
            <option value="">All fencers</option>
            {options.fencers.map((fencer) => (
              <option key={fencer} value={fencer}>
                {fencer}
              </option>
            ))}
          </select>
        </label>

        <label>
          Source
          <select value={filters.source} onChange={(event) => updateFilter("source", event.currentTarget.value)}>
            <option value="">All sources</option>
            {options.sources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </label>

        <label>
          From
          <input type="date" value={filters.from} onChange={(event) => updateFilter("from", event.currentTarget.value)} />
        </label>

        <label>
          To
          <input type="date" value={filters.to} onChange={(event) => updateFilter("to", event.currentTarget.value)} />
        </label>

        <button type="button" onClick={clearFilters} disabled={!hasActiveFilters}>
          Clear filters
        </button>
      </form>

      {visibleArticles.length === 0 ? (
        <div role="status" className="news-feed__empty">
          <p>No articles match these filters.</p>
        </div>
      ) : (
        <ol className="news-feed__list">
          {visibleArticles.map((article, index) => (
            <NewsArticleCard key={getArticleId(article, index)} article={article} index={index} />
          ))}
        </ol>
      )}

      <nav className="news-feed__pagination" aria-label="News pagination">
        <button
          type="button"
          aria-label="Previous page"
          disabled={currentPage <= 1}
          onClick={() => setPage((value) => Math.max(1, value - 1))}
        >
          Previous
        </button>
        <span>
          Page {currentPage} of {totalPages}
        </span>
        <button
          type="button"
          aria-label="Next page"
          disabled={currentPage >= totalPages}
          onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
        >
          Next
        </button>
      </nav>
    </section>
  );
}

function NewsArticleCard({ article, index }: { article: NewsArticle; index: number }) {
  const title = article.title || "Untitled article";
  const titleId = `news-article-${getArticleId(article, index)}-title`;
  const categories = getCategories(article);
  const fencers = getRelatedFencers(article);
  const url = safeExternalUrl(article.url);
  const publishedAt = getPublishedAt(article);

  return (
    <li className="news-feed__item">
      <article aria-labelledby={titleId}>
        <div className="news-feed__meta">
          <span>{getSourceSite(article)}</span>
          <span aria-hidden="true">·</span>
          {publishedAt ? <time dateTime={publishedAt}>{formatArticleDate(article)}</time> : <span>Date unavailable</span>}
        </div>

        <h3 id={titleId}>{title}</h3>

        <div className="news-feed__badges" aria-label="Categories">
          {categories.map((category) => (
            <span className="news-feed__badge" key={category}>
              {labelize(category)}
            </span>
          ))}
        </div>

        <p>{article.summary?.trim() ? article.summary : "No summary available."}</p>

        <div className="news-feed__fencers">
          <span>Related fencers:</span>{" "}
          {fencers.length ? (
            <ul aria-label={`Related fencers for ${title}`}>
              {fencers.map((fencer) => (
                <li key={fencer.id || fencer.name}>{fencer.name}</li>
              ))}
            </ul>
          ) : (
            <span>None tagged</span>
          )}
        </div>

        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer nofollow" aria-label={`Read article: ${title}`}>
            Read article
          </a>
        ) : (
          <span>Source link unavailable</span>
        )}
      </article>
    </li>
  );
}

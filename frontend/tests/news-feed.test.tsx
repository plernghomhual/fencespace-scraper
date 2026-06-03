import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import NewsFeed, { type NewsArticle } from "../components/NewsFeed";

const articles: NewsArticle[] = [
  {
    id: "1",
    title: "World Cup gold for Lee Kiefer",
    url: "https://fie.org/articles/1",
    source: "fie_news",
    sourceSite: "FIE",
    publishedAt: "2026-05-20T12:00:00Z",
    category: "competition_report",
    summary: "Lee Kiefer won foil gold after a strong final.",
    relatedFencers: [{ id: "lee-kiefer", name: "Lee Kiefer" }],
  },
  {
    id: "2",
    title: "Training update for Olga Kharlan",
    url: "https://www.britishfencing.com/news/2",
    source: "british_fencing",
    sourceSite: "British Fencing",
    publishedAt: "2026-05-18T09:30:00Z",
    category: "general",
    summary: null,
    relatedFencers: [{ id: "olga-kharlan", name: "Olga Kharlan" }],
  },
  {
    id: "3",
    title: "Federation switch approved",
    url: "notaurl",
    source: "fie_news",
    sourceSite: "FIE",
    publishedAt: "2026-04-12T10:00:00Z",
    category: "transfer",
    summary: "Transfer window update for youth and senior fencers.",
    relatedFencers: [],
  },
];

function filterControls(container: HTMLElement) {
  const form = container.querySelector('form[aria-label="News filters"]');
  if (!form) {
    throw new Error("News filters form was not rendered");
  }
  const [category, fencer, source] = Array.from(form.querySelectorAll("select"));
  const search = form.querySelector('input[type="search"]');
  const [from, to] = Array.from(form.querySelectorAll('input[type="date"]'));

  if (!search || !category || !fencer || !source || !from || !to) {
    throw new Error("Expected all news filter controls to render");
  }

  return {
    search,
    category,
    fencer,
    source,
    from,
    to,
  };
}

function renderNewsFeed(props: React.ComponentProps<typeof NewsFeed>) {
  return render(React.createElement(NewsFeed, props));
}

describe("NewsFeed", () => {
  it("renders hostile title and summary as escaped text, not HTML", () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => undefined);
    const hostileArticles: NewsArticle[] = [
      {
        id: "xss",
        title: "<img src=x onerror=alert('title')> medal report",
        url: "javascript:alert('bad')",
        source: "fie_news",
        sourceSite: "FIE",
        publishedAt: "2026-05-21T12:00:00Z",
        category: "competition_report",
        summary: "<script>alert('summary')</script><b>bold summary</b>",
        relatedFencers: [{ id: "lee-kiefer", name: "Lee Kiefer" }],
      },
    ];

    renderNewsFeed({ initialArticles: hostileArticles });

    expect(screen.getByText(/<img src=x onerror=alert\('title'\)> medal report/)).toBeTruthy();
    expect(screen.getByText(/<script>alert\('summary'\)<\/script><b>bold summary<\/b>/)).toBeTruthy();
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("img")).toBeNull();
    expect(screen.queryByRole("link", { name: /read article/i })).toBeNull();
    expect(alertSpy).not.toHaveBeenCalled();

    alertSpy.mockRestore();
  });

  it("filters by category, fencer, and source", () => {
    const { container } = renderNewsFeed({ initialArticles: articles, pageSize: 10 });
    const controls = filterControls(container);

    fireEvent.change(controls.category, {
      target: { value: "competition_report" },
    });
    fireEvent.change(controls.fencer, {
      target: { value: "Lee Kiefer" },
    });
    fireEvent.change(controls.source, {
      target: { value: "FIE" },
    });

    expect(container.textContent).toContain("World Cup gold for Lee Kiefer");
    expect(container.textContent).not.toContain("Training update");
    expect(container.textContent).not.toContain("Federation switch");

    const clearButton = Array.from(container.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("Clear filters"),
    );
    if (!clearButton) {
      throw new Error("Clear filters button was not rendered");
    }
    fireEvent.click(clearButton);

    expect(container.textContent).toContain("Training update");
    expect(container.textContent).toContain("No summary available");
    expect(container.textContent).toContain("Source link unavailable");
  });

  it("filters by date range and search text", () => {
    const { container } = renderNewsFeed({ initialArticles: articles, pageSize: 10 });
    const controls = filterControls(container);

    fireEvent.change(controls.from, {
      target: { value: "2026-04-01" },
    });
    fireEvent.change(controls.to, {
      target: { value: "2026-04-30" },
    });
    fireEvent.change(controls.search, {
      target: { value: "transfer" },
    });

    expect(container.textContent).toContain("Federation switch approved");
    expect(container.textContent).not.toContain("World Cup gold");
    expect(container.textContent).not.toContain("Training update");
  });

  it("paginates filtered articles and resets to the first page when filters change", () => {
    const { container } = renderNewsFeed({ initialArticles: articles, pageSize: 1 });

    expect(container.textContent).toContain("Page 1 of 3");
    expect(container.textContent).toContain("World Cup gold");

    const nextButton = container.querySelector('button[aria-label="Next page"]');
    if (!nextButton) {
      throw new Error("Next page button was not rendered");
    }
    fireEvent.click(nextButton);

    expect(container.textContent).toContain("Page 2 of 3");
    expect(container.textContent).toContain("Training update");

    fireEvent.change(filterControls(container).search, {
      target: { value: "transfer" },
    });

    expect(container.textContent).toContain("Page 1 of 1");
    expect(container.textContent).toContain("Federation switch approved");
  });

  it("shows empty state when no article matches filters", () => {
    const { container } = renderNewsFeed({ initialArticles: articles });

    fireEvent.change(filterControls(container).search, {
      target: { value: "nonexistent topic" },
    });

    expect(screen.getByText(/no articles match these filters/i)).toBeTruthy();
  });

  it("shows loading and error states for async article loading", async () => {
    const loadArticles = vi.fn<() => Promise<NewsArticle[]>>().mockRejectedValue(new Error("network down"));

    renderNewsFeed({ loadArticles });

    expect(screen.getByText(/loading fencing news/i)).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/could not load fencing news/i);
    });
  });

  it("shows a readable empty state when there are no articles", () => {
    renderNewsFeed({ initialArticles: [] });

    const status = screen.getByRole("status");
    expect(within(status).getByText(/no fencing news is available yet/i)).toBeTruthy();
  });
});

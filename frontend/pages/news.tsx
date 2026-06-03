import React from "react";

import NewsFeed, { NEWS_API_ENDPOINT, type NewsArticle } from "../components/NewsFeed";

export const NEWS_API_CONTRACT = {
  endpoint: NEWS_API_ENDPOINT,
  method: "GET",
  responseShape: "{ articles: NewsArticle[] }",
  backingTable: "fs_articles",
} as const;

const newsFixtures: NewsArticle[] = [
  {
    id: "fixture-fie-1649",
    title: "Alina Mikhailova Leads AIN to Women's Sabre Gold in Lima",
    url: "https://fie.org/articles/1649",
    source: "fie_news",
    sourceSite: "FIE",
    publishedAt: "2026-05-25T00:00:00+00:00",
    category: "competition_report",
    summary: "Alina Mikhailova won gold at the Women's Sabre World Cup in Lima after a comeback in the final.",
    relatedFencers: [{ id: "11111111-1111-1111-1111-111111111111", name: "Alina Mikhailova" }],
  },
  {
    id: "fixture-british-fencing-events",
    title: "Upcoming fencing events for May and June 2026",
    url: "https://www.britishfencing.com/upcoming-fencing-events-may-june-2026/",
    source: "british_fencing",
    sourceSite: "British Fencing",
    publishedAt: "2026-05-29T15:03:17+00:00",
    category: "general",
    summary: "A snapshot of upcoming fencing events across the United Kingdom.",
    relatedFencers: [],
  },
  {
    id: "fixture-rule-change",
    title: "FIE Congress approves competition format update",
    url: null,
    source: "fie_news",
    sourceSite: "FIE",
    publishedAt: "2026-04-18T10:00:00+00:00",
    category: "rule_change",
    summary: null,
    relatedFencers: [],
  },
];

export default function NewsPage() {
  return (
    <main>
      <h1>News</h1>
      <NewsFeed initialArticles={newsFixtures} />
    </main>
  );
}

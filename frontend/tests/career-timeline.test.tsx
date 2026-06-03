import "@testing-library/jest-dom/vitest";
import React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CareerTimeline } from "../components/CareerTimeline";
import {
  filterTimelineEvents,
  normalizeCareerTimeline,
  type CareerTimelineInput,
} from "../lib/careerTimeline";

const fullCareerFixture: CareerTimelineInput = {
  careerStats: [
    {
      season: "2019-2020",
      weapon: "Epee",
      category: "Senior",
      country: "United States",
      competitions: 8,
      bestRank: 8,
    },
    {
      season: "2023/24",
      weapon: "Foil",
      category: "Senior",
      country: "Canada",
      competitions: 11,
      rankingPeak: 2,
    },
  ],
  medals: [
    {
      date: "2021-07-24",
      competition: "Tokyo Olympic Games",
      medal: "Gold",
      weapon: "Foil",
      category: "Senior",
    },
    {
      year: 2020,
      competition: "Pan-American Championships",
      medal: "Bronze",
      weapon: "Epee",
      category: "Senior",
    },
  ],
  transfers: [
    {
      season: "2022-2023",
      fromCountry: "United States",
      toCountry: "Canada",
      weapon: "Foil",
      category: "Senior",
    },
  ],
  milestones: [
    {
      date: "2018-05-10",
      title: "Junior World Cup debut",
      description: "First recorded international final.",
      weapon: "Foil",
      category: "Junior",
    },
    {
      title: "First documented elite result",
      description: "Legacy source did not publish an exact date.",
    },
  ],
  longevity: [
    {
      firstSeason: "2018-2019",
      lastSeason: "2023/24",
      activeSeasons: 6,
      weapon: "Foil",
      category: "Senior",
    },
  ],
};

const emptyCareerFixture: CareerTimelineInput = {};

const sparseCareerFixture: CareerTimelineInput = {
  milestones: [
    {
      title: "First documented elite result",
      description: "Legacy source did not publish an exact date.",
    },
  ],
};

afterEach(() => {
  cleanup();
});

describe("normalizeCareerTimeline", () => {
  it("normalizes mixed career rows into sorted typed events with locale-safe labels", () => {
    const timeline = normalizeCareerTimeline(fullCareerFixture, { locale: "en-US" });

    expect(timeline.filterOptions.weapons).toEqual(["Epee", "Foil"]);
    expect(timeline.filterOptions.categories).toEqual(["Junior", "Senior"]);
    expect(timeline.events.map((event) => event.kind)).toEqual(
      expect.arrayContaining([
        "season",
        "medal",
        "ranking_peak",
        "country_change",
        "milestone",
        "longevity",
      ]),
    );

    const preservedSeason = timeline.events.find(
      (event) => event.kind === "season" && event.seasonLabel === "2023/24",
    );
    expect(preservedSeason?.title).toContain("2023/24");

    const unknown = timeline.events.at(-1);
    expect(unknown?.timeLabel).toBe("Date unknown");
    expect(unknown?.ariaLabel).toMatch(/Date unknown.*First documented elite result/i);
  });

  it("deduplicates season stats by season, weapon, and category while keeping the best rank", () => {
    const timeline = normalizeCareerTimeline({
      careerStats: [
        {
          season: "2021-2022",
          weapon: "Sabre",
          category: "Senior",
          competitions: 5,
          bestRank: 5,
        },
        {
          season: "2021-2022",
          weapon: "Sabre",
          category: "Senior",
          competitions: 3,
          bestRank: 2,
        },
      ],
    });

    const seasonEvents = timeline.events.filter((event) => event.kind === "season");
    const rankingEvents = timeline.events.filter((event) => event.kind === "ranking_peak");

    expect(seasonEvents).toHaveLength(1);
    expect(seasonEvents[0].details).toEqual(
      expect.arrayContaining(["8 competitions", "Best ranking #2"]),
    );
    expect(rankingEvents).toHaveLength(1);
    expect(rankingEvents[0].rank).toBe(2);
  });

  it("filters weapon-specific events without dropping global milestones", () => {
    const timeline = normalizeCareerTimeline(fullCareerFixture);

    const foilEvents = filterTimelineEvents(timeline.events, { weapon: "Foil" });

    expect(foilEvents.some((event) => event.title.includes("Tokyo Olympic Games"))).toBe(true);
    expect(foilEvents.some((event) => event.title.includes("Pan-American Championships"))).toBe(
      false,
    );
    expect(foilEvents.some((event) => event.title === "First documented elite result")).toBe(true);
  });
});

describe("CareerTimeline", () => {
  it("renders a safe empty state when career data is absent", () => {
    render(React.createElement(CareerTimeline, { data: emptyCareerFixture }));

    expect(screen.getByText("No career timeline data available.")).toBeInTheDocument();
    expect(
      screen.queryByRole("list", { name: /chronological career timeline/i }),
    ).not.toBeInTheDocument();
  });

  it("renders sparse unknown-date milestones with chronological accessibility labels", () => {
    render(React.createElement(CareerTimeline, { data: sparseCareerFixture }));

    const list = screen.getByRole("list", { name: /chronological career timeline/i });
    const item = within(list).getByRole("listitem", {
      name: /date unknown.*milestone.*first documented elite result/i,
    });

    expect(item).toHaveTextContent("Date unknown");
    expect(item).toHaveTextContent("Legacy source did not publish an exact date.");
  });

  it("renders full career data and filters multiple weapons without visual overlap controls", () => {
    render(React.createElement(CareerTimeline, { data: fullCareerFixture, locale: "en-US" }));

    expect(screen.getByRole("region", { name: /career timeline/i })).toBeInTheDocument();
    expect(screen.getByText(/Tokyo Olympic Games/)).toBeInTheDocument();
    expect(screen.getByText(/Ranking peak #2/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filter by weapon"), {
      target: { value: "Foil" },
    });

    expect(screen.getByText(/Tokyo Olympic Games/)).toBeInTheDocument();
    expect(screen.queryByText(/Pan-American Championships/)).not.toBeInTheDocument();
    expect(screen.getByText(/First documented elite result/)).toBeInTheDocument();
  });
});

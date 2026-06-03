import "@testing-library/jest-dom/vitest";
import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import FencerComparisonTool from "../components/FencerComparisonTool";
import {
  normalizeFencerComparison,
} from "../lib/fencerComparison";
import type { FencerComparisonStatObject } from "../lib/fencerComparison";

afterEach(() => {
  cleanup();
});

const alice: FencerComparisonStatObject = {
  id: "11111111-1111-1111-1111-111111111111",
  fieId: "12345",
  name: "Alice Volpi",
  country: "ITA",
  weapon: "Foil",
  careerStats: {
    total_competitions: 42,
    gold_medals: 8,
    silver_medals: 5,
    bronze_medals: 3,
    top8_count: 25,
    best_rank: 1,
    avg_rank: 4.2,
    worst_rank: 32,
    weapons_used: ["Foil"],
    categories_competed: ["Senior"],
    first_season: "2014",
    last_season: "2026",
    total_touches_scored: 918,
    total_touches_received: 800,
    touch_differential: 118,
  },
  medalTable: {
    gold: 9,
    silver: 4,
    bronze: 2,
    total: 15,
  },
  rankings: [
    {
      weapon: "Foil",
      category: "Senior",
      season: 2026,
      rank: 2,
      previous_rank: 4,
      rank_change: -2,
      points: 321.5,
      trend_direction: "up",
      projected_next_rank: 1,
    },
  ],
  elo: [
    {
      weapon: "Foil",
      category: "Senior",
      rating: 1840,
      peak_rating: 1902,
      games: 93,
      last_bout_at: "2026-05-12",
    },
  ],
  performanceAnalysis: [
    {
      weapon: "Foil",
      competitions_count: 14,
      avg_delta: 6.5,
      overperformance_rate: 72,
      clutch_score: 6.5,
    },
  ],
  recentForm: [
    {
      tournament: "Cairo World Cup",
      placement: 1,
      date: "2026-05-02",
    },
    {
      tournament: "Turin Grand Prix",
      placement: 5,
      date: "2026-04-19",
    },
  ],
};

const bob: FencerComparisonStatObject = {
  id: "22222222-2222-2222-2222-222222222222",
  fieId: "67890",
  name: "Bob Lee",
  nationality: "USA",
  weapon: "Foil",
  careerStats: {
    total_competitions: 18,
    gold_medals: 1,
    silver_medals: 3,
    bronze_medals: 4,
    top8_count: 11,
    best_rank: 3,
    avg_rank: 8.75,
    worst_rank: 40,
    weapons_used: ["Foil", "Epee"],
    categories_competed: ["Junior", "Senior"],
    first_season: "2021",
    last_season: "2026",
    total_touches_scored: 510,
    total_touches_received: 529,
    touch_differential: -19,
  },
  medals: {
    gold: 1,
    silver: 3,
    bronze: 4,
    total: 8,
  },
  rankingTrends: [
    {
      weapon: "Foil",
      category: "Senior",
      season: 2026,
      rank: 8,
      previous_rank: 7,
      rank_change: 1,
      points: 198,
      trend_direction: "down",
      projected_next_rank: 9,
    },
  ],
  eloRatings: {
    weapon: "Foil",
    category: "Senior",
    rating: 1695,
    peak_rating: 1710,
    games: 41,
    last_bout_at: "2026-04-29",
  },
  performance: {
    weapon: "Foil",
    competitions_count: 8,
    avg_delta: -1.5,
    overperformance_rate: 37.5,
    clutch_score: -1.5,
  },
  recentResults: [
    {
      tournament: "Cairo World Cup",
      rank: 12,
      date: "2026-05-02",
    },
  ],
};

const h2hRows = [
  {
    fencer_a_id: alice.id,
    fencer_b_id: bob.id,
    weapon: "Foil",
    a_wins: 3,
    b_wins: 1,
    a_touches: 58,
    b_touches: 43,
    bouts_total: 4,
    last_meeting_date: "2026-05-02",
    last_winner_id: alice.id,
  },
];

function rowValue(
  comparison: ReturnType<typeof normalizeFencerComparison>,
  sectionId: string,
  label: string,
  side: "left" | "right",
) {
  const section = comparison.sections.find((item) => item.id === sectionId);
  const row = section?.rows.find((item) => item.label === label);
  return row?.[side].display;
}

function renderTool(props: React.ComponentProps<typeof FencerComparisonTool> = {}) {
  return render(React.createElement(FencerComparisonTool, props));
}

describe("normalizeFencerComparison", () => {
  it("normalizes full backend analytics shapes into side-by-side sections", () => {
    const comparison = normalizeFencerComparison({
      left: alice,
      right: bob,
      h2hRows,
    });

    expect(comparison.left?.displayName).toBe("Alice Volpi");
    expect(comparison.right?.country).toBe("USA");
    expect(comparison.isSameFencer).toBe(false);
    expect(comparison.sections.map((section) => section.id)).toEqual([
      "career",
      "medals",
      "rankings",
      "elo",
      "h2h",
      "weapons",
      "recentForm",
    ]);
    expect(rowValue(comparison, "career", "Competitions", "left")).toBe("42");
    expect(rowValue(comparison, "career", "Best rank", "right")).toBe("#3");
    expect(rowValue(comparison, "medals", "Total medals", "left")).toBe("15");
    expect(rowValue(comparison, "rankings", "Current rank", "left")).toBe("#2");
    expect(rowValue(comparison, "elo", "Current Elo", "left")).toBe("1840");
    expect(rowValue(comparison, "h2h", "Foil wins", "left")).toBe("3");
    expect(rowValue(comparison, "h2h", "Foil wins", "right")).toBe("1");
    expect(rowValue(comparison, "weapons", "Weapons", "right")).toBe("Foil, Epee");
    expect(rowValue(comparison, "recentForm", "Recent form", "left")).toContain(
      "1st Cairo World Cup",
    );
  });

  it("keeps required sections and placeholder cells when analytics are missing", () => {
    const comparison = normalizeFencerComparison({
      left: { id: "left", name: "Left Fencer" },
      right: { id: "right", name: "Right Fencer" },
    });

    expect(comparison.sections).toHaveLength(7);
    expect(rowValue(comparison, "career", "Competitions", "left")).toBe("No data");
    expect(rowValue(comparison, "medals", "Total medals", "right")).toBe("No data");
    expect(rowValue(comparison, "rankings", "Current rank", "left")).toBe("No data");
    expect(rowValue(comparison, "h2h", "Wins", "right")).toBe("No bouts");
    expect(rowValue(comparison, "recentForm", "Recent form", "left")).toBe("No recent results");
  });
});

describe("FencerComparisonTool", () => {
  it("renders full side-by-side career, medals, ranking, Elo, H2H, weapons, and form", () => {
    renderTool({ left: alice, right: bob, h2hRows });

    expect(screen.getByText("Alice Volpi")).toBeInTheDocument();
    expect(screen.getByText("Bob Lee")).toBeInTheDocument();
    expect(screen.getByText("Career")).toBeInTheDocument();
    expect(screen.getByText("Medals")).toBeInTheDocument();
    expect(screen.getByText("Rankings")).toBeInTheDocument();
    expect(screen.getByText("Elo")).toBeInTheDocument();
    expect(screen.getByText("Head to head")).toBeInTheDocument();
    expect(screen.getByText("1840")).toBeInTheDocument();
    expect(screen.getByText("3-1")).toBeInTheDocument();
    expect(screen.getByText(/1st Cairo World Cup/)).toBeInTheDocument();
  });

  it("renders placeholders for typed fencers with missing analytics", () => {
    renderTool({
      left: { id: "left", name: "Left Fencer" },
      right: { id: "right", name: "Right Fencer" },
    });

    expect(screen.getAllByText("No data").length).toBeGreaterThan(4);
    expect(screen.getAllByText("No bouts")).toHaveLength(2);
    expect(screen.getAllByText("No recent results")).toHaveLength(2);
  });

  it("renders an empty state when no fencers are provided", () => {
    renderTool();

    expect(screen.getByText("Select two fencers to compare")).toBeInTheDocument();
    expect(screen.getAllByText("No fencer selected")).toHaveLength(2);
  });

  it("warns when the same fencer is selected on both sides", () => {
    renderTool({ left: alice, right: { ...alice } });

    expect(screen.getByText("Same fencer selected")).toBeInTheDocument();
    expect(screen.getByText("Choose two different fencers for a meaningful comparison.")).toBeInTheDocument();
  });

  it("loads ID inputs through the public loader and handles a missing fencer", async () => {
    const loadFencerStats = vi.fn(async (id: string) => {
      if (id === "alice") {
        return alice;
      }
      return null;
    });

    renderTool({
      leftId: "alice",
      rightId: "missing",
      loadFencerStats,
    });

    await waitFor(() => expect(loadFencerStats).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Alice Volpi")).toBeInTheDocument();
    expect(screen.getByText("Fencer not found")).toBeInTheDocument();
    expect(screen.getAllByText("No data").length).toBeGreaterThan(1);
  });
});

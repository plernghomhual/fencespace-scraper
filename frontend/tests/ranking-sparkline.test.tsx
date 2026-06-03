import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { RankingSparkline } from "../components/RankingSparkline";
import {
  buildSparklineLayout,
  normalizeRankingHistory,
  type RankingHistoryRow,
} from "../lib/rankingSparkline";

afterEach(cleanup);

const epeeHistory: RankingHistoryRow[] = [
  {
    season: "2021-2022",
    date: "2022-06-15",
    weapon: "Epee",
    category: "Senior",
    rank: 12,
    points: "51.5",
  },
  {
    season: "2023-2024",
    date: "2024-06-15",
    weapon: "Epee",
    category: "Senior",
    rank: 6,
    points: null,
  },
  {
    season: "2024-2025",
    date: "2025-06-15",
    weapon: "Epee",
    category: "Senior",
    rank: 6,
    points: 80,
  },
  {
    season: "2022-2023",
    date: "2023-06-15",
    weapon: "Foil",
    category: "Junior",
    rank: 3,
    points: 44,
  },
];

describe("ranking sparkline normalization", () => {
  it("orders one weapon/category series by season and fills missing seasons as gaps", () => {
    const [series] = normalizeRankingHistory(epeeHistory, {
      weapon: "Epee",
      category: "Senior",
      includeMissingSeasons: true,
    });

    expect(series.weapon).toBe("Epee");
    expect(series.category).toBe("Senior");
    expect(series.points.map((point) => point.season)).toEqual([
      "2021-2022",
      "2022-2023",
      "2023-2024",
      "2024-2025",
    ]);
    expect(series.points[0]).toMatchObject({ rank: 12, points: 51.5, missing: false });
    expect(series.points[1]).toMatchObject({
      season: "2022-2023",
      rank: null,
      points: null,
      weapon: "Epee",
      category: "Senior",
      missing: true,
    });
    expect(series.points[2]).toMatchObject({ rank: 6, points: null, missing: false });
  });

  it("maps better lower rank numbers upward and keeps tied ranks level", () => {
    const [series] = normalizeRankingHistory(epeeHistory, {
      weapon: "Epee",
      category: "Senior",
      includeMissingSeasons: true,
    });

    const layout = buildSparklineLayout(series.points, { width: 120, height: 48, padding: 6 });
    const rank12 = layout.points.find((point) => point.rank === 12);
    const tiedRank6 = layout.points.filter((point) => point.rank === 6);

    expect(rank12).toBeDefined();
    expect(tiedRank6).toHaveLength(2);
    expect(tiedRank6[0].y).toBeLessThan(rank12!.y);
    expect(tiedRank6[0].y).toBe(tiedRank6[1].y);
    expect(layout.segments).toHaveLength(2);
  });
});

describe("RankingSparkline", () => {
  it("renders a readable empty state", () => {
    render(createElement(RankingSparkline, { data: [] }));

    expect(screen.getByRole("img", { name: /no ranking history available/i })).toBeInTheDocument();
    expect(screen.getByText("No ranking history")).toBeInTheDocument();
  });

  it("renders a single-point series without a connecting path", () => {
    render(
      createElement(RankingSparkline, {
        data: [
          {
            season: "2024-2025",
            date: "2025-06-15",
            weapon: "Epee",
            category: "Senior",
            rank: 3,
            points: 118.5,
          },
        ],
        color: "#0057b8",
        height: 36,
        width: 144,
      }),
    );

    expect(screen.getByRole("img", { name: /ranking trend for senior epee/i })).toBeInTheDocument();
    expect(screen.queryByTestId("ranking-sparkline-path")).not.toBeInTheDocument();
    expect(screen.getByTestId("ranking-sparkline-svg")).toHaveAttribute("height", "36");
    expect(screen.getByTestId("ranking-sparkline-svg")).toHaveAttribute("width", "144");
    expect(screen.getByTestId("ranking-sparkline-point-0")).toHaveAttribute("fill", "#0057b8");
    expect(
      screen.getByLabelText("2024-2025 Senior Epee: rank 3, 118.5 points"),
    ).toBeInTheDocument();
  });

  it("renders full series segments and point tooltips including null points", () => {
    render(
      createElement(RankingSparkline, {
        data: epeeHistory,
        weapon: "Epee",
        category: "Senior",
        includeMissingSeasons: true,
        color: "#0b6bcb",
        width: 160,
        height: 42,
      }),
    );

    expect(screen.getByRole("img", { name: /latest rank 6/i })).toBeInTheDocument();
    expect(screen.getAllByTestId("ranking-sparkline-path")).toHaveLength(1);
    expect(screen.getAllByTestId(/ranking-sparkline-point-/)).toHaveLength(3);
    expect(
      screen.getByLabelText("2023-2024 Senior Epee: rank 6, points unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByText("2023-2024 Senior Epee: rank 6, points unavailable")).toBeInTheDocument();
  });
});

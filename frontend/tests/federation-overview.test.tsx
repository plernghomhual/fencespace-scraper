import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import FederationOverview, {
  getFederationCountry,
  sanitizeFederationPageData,
  type FederationOverviewData,
} from "../components/FederationOverview";

const completeData: FederationOverviewData = {
  federation: {
    code: "USA",
    name: "United States",
    flag: "🇺🇸",
  },
  topFencers: [
    {
      id: "fencer-1",
      name: "Lee Kiefer",
      country: "USA",
      weapon: "Foil",
      category: "Women",
      worldRank: 1,
      domesticRank: 1,
      club: "Bluegrass Fencers",
      fiePoints: 210,
    },
    {
      id: "fencer-2",
      name: "Nick Itkin",
      country: "USA",
      weapon: "Foil",
      category: "Men",
      worldRank: 4,
      domesticRank: 2,
      club: "Los Angeles International",
      fiePoints: 180,
    },
  ],
  depthRows: [
    {
      country: "USA",
      weapon: "Foil",
      category: "Women",
      fencersInTop16: 2,
      fencersInTop32: 4,
      fencersInTop64: 7,
      totalRanked: 18,
      avgWorldRank: 38.5,
    },
    {
      country: "USA",
      weapon: "Epee",
      category: "Men",
      fencersInTop16: 1,
      fencersInTop32: 3,
      fencersInTop64: 5,
      totalRanked: 14,
      avgWorldRank: 42.1,
    },
  ],
  medalRows: [
    {
      scope: "country",
      country: "USA",
      gold: 3,
      silver: 2,
      bronze: 4,
      total: 9,
    },
    {
      scope: "tier_country",
      country: "USA",
      tier: "World Cup",
      gold: 1,
      silver: 1,
      bronze: 2,
      total: 4,
    },
  ],
  clubRows: [
    {
      club: "bluegrass fencers",
      country: "USA",
      weapon: "Foil",
      totalFencers: 4,
      avgRank: 12.25,
      totalPoints: 510,
    },
  ],
  nationalRankingRows: [
    {
      country: "USA",
      weapon: "Foil",
      category: "Women",
      fencerCount: 42,
      top8Count: 3,
    },
  ],
  recentTournaments: [
    {
      id: "tournament-1",
      name: "USA Fencing National Championships",
      country: "USA",
      weapon: "Foil",
      category: "Senior",
      type: "National",
      startDate: "2026-04-10",
    },
  ],
};

afterEach(() => {
  cleanup();
});

describe("federation country-code mapping", () => {
  it("resolves route aliases through the shared federation country map", () => {
    expect(getFederationCountry("us")?.alpha3).toBe("USA");
    expect(getFederationCountry("deu")?.alpha3).toBe("DEU");
    expect(getFederationCountry("ger")?.alpha3).toBe("DEU");
    expect(getFederationCountry("gb")?.alpha3).toBe("GBR");
    expect(getFederationCountry("sgp")?.name).toBe("Singapore");
  });

  it("rejects unknown federation codes instead of guessing", () => {
    expect(getFederationCountry("not-a-country")).toBeNull();
  });
});

describe("FederationOverview", () => {
  it("renders complete federation analytics", () => {
    render(createElement(FederationOverview, { data: completeData }));

    expect(screen.getByRole("heading", { name: /United States Federation/i })).toBeInTheDocument();
    expect(screen.getByText("Lee Kiefer")).toBeInTheDocument();
    expect(screen.getAllByText("9 medals")).toHaveLength(2);
    expect(screen.getByText("bluegrass fencers")).toBeInTheDocument();
    expect(screen.getByText("USA Fencing National Championships")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /top-16 top-32 top-64 depth chart/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /weapon and gender split chart/i })).toBeInTheDocument();
    expect(screen.queryByText("NaN")).not.toBeInTheDocument();

    const rankingTable = screen.getByRole("table", { name: /national ranking coverage/i });
    expect(within(rankingTable).getByText("Foil")).toBeInTheDocument();
    expect(within(rankingTable).getByText("42")).toBeInTheDocument();
  });

  it("handles sparse national ranking data without hiding depth analytics", () => {
    render(
      createElement(FederationOverview, {
        data: {
          ...completeData,
          medalRows: [],
          clubRows: [],
          nationalRankingRows: [],
          recentTournaments: [],
        },
      }),
    );

    expect(screen.getByText(/No national ranking data is available/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /top-16 top-32 top-64 depth chart/i })).toBeInTheDocument();
    expect(screen.getByText("32 ranked fencers")).toBeInTheDocument();
  });

  it("renders an empty federation state safely", () => {
    render(
      createElement(FederationOverview, {
        data: {
          federation: {
            code: "AND",
            name: "Andorra",
            flag: "🇦🇩",
          },
          topFencers: [],
          depthRows: [],
          medalRows: [],
          clubRows: [],
          nationalRankingRows: [],
          recentTournaments: [],
        },
      }),
    );

    expect(screen.getByRole("heading", { name: /Andorra Federation/i })).toBeInTheDocument();
    expect(screen.getByText(/No federation analytics are available yet/i)).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
  });

  it("uses tabular chart fallbacks when visual charts are disabled", () => {
    render(createElement(FederationOverview, { data: completeData, preferTables: true }));

    expect(screen.queryByRole("img", { name: /depth chart/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /split chart/i })).not.toBeInTheDocument();

    const depthTable = screen.getByRole("table", { name: /top depth table/i });
    expect(within(depthTable).getByText("Top 16")).toBeInTheDocument();
    expect(within(depthTable).getByText("Top 64")).toBeInTheDocument();
  });

  it("does not render scraper metadata or service keys from raw input", () => {
    const sanitized = sanitizeFederationPageData({
      ...completeData,
      topFencers: [
        {
          ...completeData.topFencers[0],
          service_key: "service-role-secret",
          scraped_at: "2026-06-02T00:00:00Z",
          metadata: { source_url: "https://internal.example.test" },
        },
      ],
    });

    render(createElement(FederationOverview, { data: sanitized }));

    expect(screen.queryByText(/service-role-secret/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/scraped_at/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/internal.example/i)).not.toBeInTheDocument();
  });
});

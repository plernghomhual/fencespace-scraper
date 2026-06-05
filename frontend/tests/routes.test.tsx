import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiListResult, Fencer, HeadToHeadRecord, Ranking, Tournament } from "@/lib/types";

const fencers: Fencer[] = [
  { id: "f1", name: "Alex Lee", country: "KOR", weapon: "Epee", category: "Senior", world_rank: 1, fie_points: 210.5 }
];

const tournaments: Tournament[] = [
  { id: "t1", name: "Seoul Grand Prix", season: 2026, country: "KOR", type: "GP", start_date: "2026-05-02", end_date: "2026-05-04" }
];

const rankings: Ranking[] = [
  { season: 2026, weapon: "Epee", gender: "Men", category: "Senior", rank: 1, name: "Alex Lee", points: 210.5 }
];

const h2h: HeadToHeadRecord[] = [
  { fencer_a_id: "f1", fencer_b_id: "f2", weapon: "Epee", a_wins: 3, b_wins: 1, bouts_total: 4 }
];

function okList<T>(data: T[]): ApiListResult<T> {
  return { ok: true, source: "mock", data, pagination: { limit: 25, offset: 0, count: data.length } };
}

const api = vi.hoisted(() => ({
  getCountryDepth: vi.fn(),
  getFencerProfile: vi.fn(),
  getHeadToHead: vi.fn(),
  getTournamentResults: vi.fn(),
  listRankings: vi.fn(),
  listTournaments: vi.fn(),
  searchFencers: vi.fn()
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    ...api
  };
});

describe("route rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.searchFencers.mockResolvedValue(okList(fencers));
    api.listTournaments.mockResolvedValue(okList(tournaments));
    api.listRankings.mockResolvedValue(okList(rankings));
    api.getFencerProfile.mockResolvedValue({
      ok: true,
      source: "mock",
      data: { profile: fencers[0], career_stats: { total_competitions: 12 }, social: [], equipment: [] }
    });
    api.getTournamentResults.mockResolvedValue(okList([{ rank: 1, name: "Alex Lee", nationality: "KOR" }]));
    api.getCountryDepth.mockResolvedValue(okList([{ country: "KOR", weapon: "Epee", category: "Senior", fencers_in_top16: 3, fencers_in_top32: 7, fencers_in_top64: 12, total_ranked: 25, avg_world_rank: 22.4 }]));
    api.getHeadToHead.mockResolvedValue({ ok: true, source: "mock", data: { fencer_a: "f1", fencer_b: "f2", data: h2h } });
  });

  it("renders the home browse surface with live sections", async () => {
    const Page = (await import("@/app/page")).default;

    render(await Page());

    expect(screen.getByRole("heading", { name: "FenceSpace Explorer" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /browse fencers/i })).toBeInTheDocument();
    expect(screen.getAllByText("Alex Lee").length).toBeGreaterThan(0);
    expect(screen.getByText("Seoul Grand Prix")).toBeInTheDocument();
  });

  it("renders fencer search filters and forwards normalized params", async () => {
    const Page = (await import("@/app/fencers/page")).default;

    render(await Page({ searchParams: Promise.resolve({ name: "Alex", country: "kor", weapon: "Epee", limit: "25" }) }));

    expect(api.searchFencers).toHaveBeenCalledWith(expect.objectContaining({ name: "Alex", country: "KOR", weapon: "Epee" }));
    expect(screen.getByLabelText("Name")).toHaveValue("Alex");
    expect(screen.getByRole("table", { name: "Fencer results" })).toBeInTheDocument();
  });

  it("renders an empty state when a search has no rows", async () => {
    api.searchFencers.mockResolvedValue(okList([]));
    const Page = (await import("@/app/fencers/page")).default;

    render(await Page({ searchParams: Promise.resolve({ name: "No Match" }) }));

    expect(screen.getByText("No fencers match the current filters.")).toBeInTheDocument();
  });

  it("renders an error state returned by the data layer", async () => {
    api.listRankings.mockResolvedValue({ ok: false, source: "live", error: "API unavailable", status: 502 });
    const Page = (await import("@/app/rankings/page")).default;

    render(await Page({ searchParams: Promise.resolve({ weapon: "Epee" }) }));

    expect(screen.getByRole("alert")).toHaveTextContent("API unavailable");
  });

  it("renders detail, tournament, country, and head-to-head routes", async () => {
    const FencerPage = (await import("@/app/fencers/[id]/page")).default;
    const TournamentPage = (await import("@/app/tournaments/[id]/page")).default;
    const CountryPage = (await import("@/app/countries/[code]/page")).default;
    const HeadToHeadPage = (await import("../pages/head-to-head")).default;

    const { rerender } = render(await FencerPage({ params: Promise.resolve({ id: "f1" }) }));
    expect(screen.getByRole("heading", { name: "Alex Lee" })).toBeInTheDocument();

    rerender(await TournamentPage({ params: Promise.resolve({ id: "t1" }) }));
    expect(screen.getByRole("heading", { name: "Tournament t1" })).toBeInTheDocument();
    expect(screen.getByText("Tournament summary is not exposed by the current API contract.")).toBeInTheDocument();

    rerender(await CountryPage({ params: Promise.resolve({ code: "kor" }) }));
    expect(screen.getByRole("heading", { name: "KOR fencing depth" })).toBeInTheDocument();

    rerender(
      <HeadToHeadPage
        fencerA="f1"
        fencerB="f2"
        result={{ ok: true, source: "mock", data: { fencer_a: "f1", fencer_b: "f2", data: h2h } }}
      />
    );
    expect(screen.getByRole("heading", { name: "Head-to-head" })).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });
});

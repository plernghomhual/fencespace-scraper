import { describe, expect, it, vi } from "vitest";

import {
  buildApiUrl,
  getServerApiConfig,
  parseFencerSearchParams,
  parsePaginationParams,
  parseRankingSearchParams
} from "@/lib/api";

describe("frontend data client query handling", () => {
  it("validates pagination and fencer search filters", () => {
    const query = parseFencerSearchParams({
      name: "  Lee  ",
      country: "kor",
      weapon: "Epee",
      limit: "9999",
      offset: "-4"
    });

    expect(query).toEqual({
      name: "Lee",
      country: "KOR",
      weapon: "Epee",
      limit: 100,
      offset: 0
    });
  });

  it("drops invalid rankings filters instead of forwarding them", () => {
    expect(
      parseRankingSearchParams({
        season: "bad",
        weapon: "Longsword",
        gender: "Men",
        category: "Senior",
        limit: "25"
      })
    ).toEqual({
      gender: "Men",
      category: "Senior",
      limit: 25,
      offset: 0
    });
  });

  it("builds encoded API URLs with only defined query params", () => {
    const url = buildApiUrl("https://api.example.test/root/", "/fencer/search", {
      name: "Alex Lee",
      country: "KOR",
      weapon: undefined,
      limit: 20,
      offset: 0
    });

    expect(url).toBe("https://api.example.test/root/fencer/search?name=Alex+Lee&country=KOR&limit=20&offset=0");
  });

  it("does not use private Supabase service keys as frontend API credentials", () => {
    vi.stubEnv("SUPABASE_SERVICE_KEY", "private-service-key");
    vi.stubEnv("SUPABASE_KEY", "private-supabase-key");
    vi.stubEnv("FENCESPACE_API_BASE_URL", "https://api.example.test");
    vi.stubEnv("FENCESPACE_API_KEY", "");
    vi.stubEnv("FS_API_KEY", "");
    vi.stubEnv("API_KEY", "");

    expect(getServerApiConfig()).toEqual({ mode: "mock" });
    vi.unstubAllEnvs();
  });

  it("clamps pagination consistently", () => {
    expect(parsePaginationParams({ limit: "0", offset: "7" })).toEqual({ limit: 25, offset: 7 });
    expect(parsePaginationParams({ limit: "500", offset: "2" })).toEqual({ limit: 100, offset: 2 });
  });
});

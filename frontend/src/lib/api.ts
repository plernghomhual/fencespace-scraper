import {
  fixtureCountryDepth,
  fixtureFencers,
  fixtureHeadToHead,
  fixtureProfile,
  fixtureRankings,
  fixtureTournamentResults,
  fixtureTournaments,
} from "@/lib/fixtures";
import type {
  ApiItemResult,
  ApiListResult,
  CountryDepth,
  DataSource,
  Fencer,
  FencerProfile,
  HeadToHeadPayload,
  Pagination,
  Ranking,
  SearchParams,
  Tournament,
  TournamentResult,
} from "@/lib/types";

const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 100;
const WEAPONS = new Set(["Foil", "Epee", "Sabre"]);
const GENDERS = new Set(["Men", "Women"]);
const CATEGORIES = new Set(["Senior", "Junior", "Cadet", "Veteran"]);

export type PaginationQuery = {
  limit: number;
  offset: number;
};

export type FencerSearchQuery = PaginationQuery & {
  name?: string;
  country?: string;
  weapon?: string;
};

export type TournamentSearchQuery = PaginationQuery & {
  season?: number;
  type?: string;
  country?: string;
};

export type RankingSearchQuery = PaginationQuery & {
  season?: number;
  weapon?: string;
  gender?: string;
  category?: string;
};

export type ServerApiConfig =
  | { mode: "live"; baseUrl: string; apiKey: string }
  | { mode: "mock" };

function firstParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function cleanText(value: string | string[] | undefined): string | undefined {
  const text = firstParam(value)?.trim();
  return text || undefined;
}

function parseInteger(value: string | string[] | undefined): number | undefined {
  const text = cleanText(value);
  if (!text || !/^-?\d+$/.test(text)) {
    return undefined;
  }
  return Number.parseInt(text, 10);
}

function normalizeCountry(value: string | string[] | undefined): string | undefined {
  const text = cleanText(value)?.toUpperCase();
  if (!text || !/^[A-Z]{2,3}$/.test(text)) {
    return undefined;
  }
  return text;
}

function normalizeOption(value: string | string[] | undefined, allowed: Set<string>): string | undefined {
  const text = cleanText(value);
  if (!text) {
    return undefined;
  }
  const match = [...allowed].find((option) => option.toLowerCase() === text.toLowerCase());
  return match;
}

export function parsePaginationParams(params: SearchParams = {}): PaginationQuery {
  const rawLimit = parseInteger(params.limit);
  const rawOffset = parseInteger(params.offset);
  const limit = rawLimit && rawLimit > 0 ? Math.min(rawLimit, MAX_LIMIT) : DEFAULT_LIMIT;
  const offset = rawOffset && rawOffset > 0 ? rawOffset : 0;
  return { limit, offset };
}

export function parseFencerSearchParams(params: SearchParams = {}): FencerSearchQuery {
  return {
    name: cleanText(params.name),
    country: normalizeCountry(params.country),
    weapon: normalizeOption(params.weapon, WEAPONS),
    ...parsePaginationParams(params),
  };
}

export function parseTournamentSearchParams(params: SearchParams = {}): TournamentSearchQuery {
  return {
    season: parseInteger(params.season),
    type: cleanText(params.type),
    country: normalizeCountry(params.country),
    ...parsePaginationParams(params),
  };
}

export function parseRankingSearchParams(params: SearchParams = {}): RankingSearchQuery {
  return {
    season: parseInteger(params.season),
    weapon: normalizeOption(params.weapon, WEAPONS),
    gender: normalizeOption(params.gender, GENDERS),
    category: normalizeOption(params.category, CATEGORIES),
    ...parsePaginationParams(params),
  };
}

export function buildApiUrl(
  baseUrl: string,
  apiPath: string,
  params: Record<string, string | number | undefined | null> = {},
): string {
  const url = new URL(`${baseUrl.replace(/\/+$/, "")}/${apiPath.replace(/^\/+/, "")}`);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

export function getServerApiConfig(): ServerApiConfig {
  const baseUrl = process.env.FENCESPACE_API_BASE_URL?.trim();
  const apiKey =
    process.env.FENCESPACE_API_KEY?.trim() ||
    process.env.FS_API_KEY?.trim() ||
    process.env.API_KEY?.trim();

  if (!baseUrl || !apiKey) {
    return { mode: "mock" };
  }
  return { mode: "live", baseUrl, apiKey };
}

function pageSlice<T>(rows: T[], query: PaginationQuery): T[] {
  return rows.slice(query.offset, query.offset + query.limit);
}

function listOk<T>(data: T[], query: PaginationQuery, source: DataSource): ApiListResult<T> {
  return {
    ok: true,
    source,
    data: pageSlice(data, query),
    pagination: { limit: query.limit, offset: query.offset, count: pageSlice(data, query).length },
  };
}

function contains(value: string | null | undefined, needle: string | undefined): boolean {
  return !needle || String(value || "").toLowerCase().includes(needle.toLowerCase());
}

async function fetchJson<T>(
  apiPath: string,
  params: Record<string, string | number | undefined | null>,
): Promise<ApiItemResult<T>> {
  const config = getServerApiConfig();
  if (config.mode === "mock") {
    return { ok: false, source: "mock", error: "Mock mode does not fetch remote data." };
  }

  try {
    const response = await fetch(buildApiUrl(config.baseUrl, apiPath, params), {
      headers: { "X-API-Key": config.apiKey },
      cache: "no-store",
    });
    if (!response.ok) {
      return { ok: false, source: "live", status: response.status, error: `API request failed with ${response.status}` };
    }
    return { ok: true, source: "live", data: (await response.json()) as T };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown API error";
    return { ok: false, source: "live", error: message };
  }
}

async function fetchList<T>(
  apiPath: string,
  query: PaginationQuery,
  params: Record<string, string | number | undefined | null>,
  fallback: T[],
): Promise<ApiListResult<T>> {
  const config = getServerApiConfig();
  if (config.mode === "mock") {
    return listOk(fallback, query, "mock");
  }

  const result = await fetchJson<{ data: T[]; pagination: Pagination }>(apiPath, params);
  if (!result.ok) {
    return { ...result, data: [], pagination: { limit: query.limit, offset: query.offset, count: 0 } };
  }
  return { ok: true, source: "live", data: result.data.data, pagination: result.data.pagination };
}

export async function searchFencers(query: FencerSearchQuery): Promise<ApiListResult<Fencer>> {
  const rows = fixtureFencers.filter(
    (fencer) =>
      contains(fencer.name, query.name) &&
      (!query.country || fencer.country === query.country) &&
      (!query.weapon || fencer.weapon === query.weapon),
  );
  return fetchList("/fencer/search", query, query, rows);
}

export async function getFencerProfile(id: string): Promise<ApiItemResult<FencerProfile>> {
  const config = getServerApiConfig();
  if (config.mode === "mock") {
    const profile = fixtureProfile(id);
    return profile
      ? { ok: true, source: "mock", data: profile }
      : { ok: false, source: "mock", status: 404, error: "Fencer not found in fixture data." };
  }
  return fetchJson(`/fencer/${encodeURIComponent(id)}`, {});
}

export async function listTournaments(query: TournamentSearchQuery): Promise<ApiListResult<Tournament>> {
  const rows = fixtureTournaments.filter(
    (event) =>
      (!query.season || event.season === query.season) &&
      (!query.type || event.type?.toLowerCase() === query.type.toLowerCase()) &&
      (!query.country || event.country === query.country),
  );
  return fetchList("/tournaments", query, query, rows);
}

export async function getTournamentResults(id: string, query: PaginationQuery): Promise<ApiListResult<TournamentResult>> {
  const rows = fixtureTournamentResults.filter((result) => result.tournament_id === id);
  return fetchList(`/tournaments/${encodeURIComponent(id)}/results`, query, query, rows);
}

export async function listRankings(query: RankingSearchQuery): Promise<ApiListResult<Ranking>> {
  const rows = fixtureRankings.filter(
    (ranking) =>
      (!query.season || ranking.season === query.season) &&
      (!query.weapon || ranking.weapon === query.weapon) &&
      (!query.gender || ranking.gender === query.gender) &&
      (!query.category || ranking.category === query.category),
  );
  return fetchList("/rankings", query, query, rows);
}

export async function getCountryDepth(code: string, query: PaginationQuery): Promise<ApiListResult<CountryDepth>> {
  const country = normalizeCountry(code) || code.toUpperCase();
  const rows = fixtureCountryDepth.filter((depth) => depth.country === country);
  return fetchList(`/countries/${encodeURIComponent(country)}/depth`, query, query, rows);
}

export async function getHeadToHead(fencerA: string, fencerB: string): Promise<ApiItemResult<HeadToHeadPayload>> {
  const config = getServerApiConfig();
  if (config.mode === "mock") {
    if (!fencerA || !fencerB) {
      return { ok: true, source: "mock", data: { fencer_a: fencerA, fencer_b: fencerB, data: [] } };
    }
    return {
      ok: true,
      source: "mock",
      data: {
        ...fixtureHeadToHead,
        fencer_a: fencerA,
        fencer_b: fencerB,
      },
    };
  }
  return fetchJson(`/h2h/${encodeURIComponent(fencerA)}/${encodeURIComponent(fencerB)}`, {});
}

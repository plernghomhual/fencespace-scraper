export type RankingHistoryRow = {
  season?: string | number | null;
  date?: string | null;
  weapon?: string | null;
  category?: string | null;
  rank?: string | number | null;
  points?: string | number | null;
};

export type NormalizeRankingHistoryOptions = {
  weapon?: string | null;
  category?: string | null;
  includeMissingSeasons?: boolean;
};

export type RankingSparklinePoint = {
  id: string;
  season: string;
  date: string | null;
  weapon: string;
  category: string;
  rank: number | null;
  points: number | null;
  missing: boolean;
  seasonYear: number | null;
  seasonFormat: "range" | "year" | "label";
  dateSort: number | null;
  sourceIndex: number;
};

export type RankingSparklineSeries = {
  key: string;
  weapon: string;
  category: string;
  points: RankingSparklinePoint[];
};

export type SparklineLayoutOptions = {
  width?: number;
  height?: number;
  padding?: number;
};

export type RankingSparklineLayoutPoint = RankingSparklinePoint & {
  x: number;
  y: number;
  label: string;
};

export type RankingSparklineLayout = {
  width: number;
  height: number;
  padding: number;
  points: RankingSparklineLayoutPoint[];
  segments: RankingSparklineLayoutPoint[][];
};

const DEFAULT_DIMENSION = 96;
const DEFAULT_HEIGHT = 32;
const DEFAULT_PADDING = 4;
const UNKNOWN_WEAPON = "Unknown weapon";
const UNKNOWN_CATEGORY = "Unknown category";

function normalizeText(value: string | number | null | undefined, fallback = ""): string {
  if (value === null || value === undefined) {
    return fallback;
  }

  const text = String(value).trim();
  return text || fallback;
}

function sameFilterValue(candidate: string, filter: string | null | undefined): boolean {
  const normalizedFilter = normalizeText(filter);
  if (!normalizedFilter || normalizedFilter.toLowerCase() === "all") {
    return true;
  }

  return candidate.toLowerCase() === normalizedFilter.toLowerCase();
}

function parseNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  const match = value.replace(/,/g, "").trim().match(/-?\d+(?:\.\d+)?/);
  if (!match) {
    return null;
  }

  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseDateSort(value: string | null | undefined): number | null {
  const text = normalizeText(value);
  if (!text) {
    return null;
  }

  const time = Date.parse(text);
  return Number.isNaN(time) ? null : time;
}

function formatDateLabel(value: string): string {
  const time = Date.parse(value);
  if (Number.isNaN(time)) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(time));
}

function parseSeason(
  seasonInput: string | number | null | undefined,
  dateInput: string | null | undefined,
): Pick<RankingSparklinePoint, "season" | "seasonYear" | "seasonFormat"> {
  const season = normalizeText(seasonInput);
  const rangeMatch = season.match(/^(\d{4})\D+(\d{4})$/);
  if (rangeMatch) {
    const start = Number(rangeMatch[1]);
    const end = Number(rangeMatch[2]);
    return {
      season: `${start}-${end}`,
      seasonYear: end,
      seasonFormat: "range",
    };
  }

  const yearMatch = season.match(/^(\d{4})$/);
  if (yearMatch) {
    return {
      season,
      seasonYear: Number(yearMatch[1]),
      seasonFormat: "year",
    };
  }

  if (season) {
    return {
      season,
      seasonYear: null,
      seasonFormat: "label",
    };
  }

  const date = normalizeText(dateInput);
  if (date) {
    return {
      season: formatDateLabel(date),
      seasonYear: null,
      seasonFormat: "label",
    };
  }

  return {
    season: "Unknown season",
    seasonYear: null,
    seasonFormat: "label",
  };
}

function makeSeriesKey(weapon: string, category: string): string {
  return `${weapon.toLowerCase()}::${category.toLowerCase()}`;
}

function comparePoints(a: RankingSparklinePoint, b: RankingSparklinePoint): number {
  const seasonA = a.seasonYear ?? Number.MAX_SAFE_INTEGER;
  const seasonB = b.seasonYear ?? Number.MAX_SAFE_INTEGER;
  if (seasonA !== seasonB) {
    return seasonA - seasonB;
  }

  const dateA = a.dateSort ?? Number.MAX_SAFE_INTEGER;
  const dateB = b.dateSort ?? Number.MAX_SAFE_INTEGER;
  if (dateA !== dateB) {
    return dateA - dateB;
  }

  return a.sourceIndex - b.sourceIndex;
}

function compareSeries(a: RankingSparklineSeries, b: RankingSparklineSeries): number {
  const categoryCompare = a.category.localeCompare(b.category);
  if (categoryCompare !== 0) {
    return categoryCompare;
  }

  return a.weapon.localeCompare(b.weapon);
}

function seasonLabel(year: number, format: RankingSparklinePoint["seasonFormat"]): string {
  if (format === "range") {
    return `${year - 1}-${year}`;
  }

  return String(year);
}

function fillMissingSeasons(series: RankingSparklineSeries): RankingSparklineSeries {
  const years = series.points
    .map((point) => point.seasonYear)
    .filter((year): year is number => year !== null);

  if (years.length < 2) {
    return series;
  }

  const yearSet = new Set(years);
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const seasonFormat = series.points.find((point) => point.seasonFormat !== "label")?.seasonFormat ?? "year";
  const missing: RankingSparklinePoint[] = [];

  for (let year = minYear; year <= maxYear; year += 1) {
    if (!yearSet.has(year)) {
      missing.push({
        id: `${series.key}::missing-${year}`,
        season: seasonLabel(year, seasonFormat),
        date: null,
        weapon: series.weapon,
        category: series.category,
        rank: null,
        points: null,
        missing: true,
        seasonYear: year,
        seasonFormat,
        dateSort: null,
        sourceIndex: Number.MAX_SAFE_INTEGER - year,
      });
    }
  }

  if (missing.length === 0) {
    return series;
  }

  return {
    ...series,
    points: [...series.points, ...missing].sort(comparePoints),
  };
}

export function normalizeRankingHistory(
  rows: RankingHistoryRow[],
  options: NormalizeRankingHistoryOptions = {},
): RankingSparklineSeries[] {
  const seriesByKey = new Map<string, RankingSparklineSeries>();

  rows.forEach((row, sourceIndex) => {
    const weapon = normalizeText(row.weapon, UNKNOWN_WEAPON);
    const category = normalizeText(row.category, UNKNOWN_CATEGORY);

    if (!sameFilterValue(weapon, options.weapon) || !sameFilterValue(category, options.category)) {
      return;
    }

    const season = parseSeason(row.season, row.date);
    const date = normalizeText(row.date) || null;
    const key = makeSeriesKey(weapon, category);
    const point: RankingSparklinePoint = {
      id: `${key}::${season.season}::${date ?? "no-date"}::${sourceIndex}`,
      season: season.season,
      date,
      weapon,
      category,
      rank: parseNumber(row.rank),
      points: parseNumber(row.points),
      missing: false,
      seasonYear: season.seasonYear,
      seasonFormat: season.seasonFormat,
      dateSort: parseDateSort(row.date),
      sourceIndex,
    };

    const existing = seriesByKey.get(key);
    if (existing) {
      existing.points.push(point);
    } else {
      seriesByKey.set(key, {
        key,
        weapon,
        category,
        points: [point],
      });
    }
  });

  return Array.from(seriesByKey.values())
    .map((series) => ({
      ...series,
      points: series.points.sort(comparePoints),
    }))
    .map((series) => (options.includeMissingSeasons ? fillMissingSeasons(series) : series))
    .sort(compareSeries);
}

function roundCoordinate(value: number): number {
  return Math.round(value * 100) / 100;
}

function normalizeDimension(value: number | undefined, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback;
  }

  return Math.max(1, value);
}

export function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(value).replace(/0+$/, "").replace(/\.$/, "");
}

export function formatRankingPointLabel(point: Pick<RankingSparklinePoint, "season" | "weapon" | "category" | "rank" | "points">): string {
  const rankLabel = point.rank === null ? "rank unavailable" : `rank ${formatNumber(point.rank)}`;
  const pointsLabel = point.points === null ? "points unavailable" : `${formatNumber(point.points)} points`;

  return `${point.season} ${point.category} ${point.weapon}: ${rankLabel}, ${pointsLabel}`;
}

export function buildSparklineLayout(
  points: RankingSparklinePoint[],
  options: SparklineLayoutOptions = {},
): RankingSparklineLayout {
  const width = normalizeDimension(options.width, DEFAULT_DIMENSION);
  const height = normalizeDimension(options.height, DEFAULT_HEIGHT);
  const maxPadding = Math.max(0, Math.min(width, height) / 2 - 1);
  const padding = Math.min(Math.max(0, options.padding ?? DEFAULT_PADDING), maxPadding);
  const validPoints = points.filter((point) => point.rank !== null);
  const ranks = validPoints.map((point) => point.rank as number);
  const bestRank = ranks.length > 0 ? Math.min(...ranks) : 0;
  const worstRank = ranks.length > 0 ? Math.max(...ranks) : 0;
  const rankRange = worstRank - bestRank;
  const innerWidth = Math.max(0, width - padding * 2);
  const innerHeight = Math.max(0, height - padding * 2);
  const xStep = points.length > 1 ? innerWidth / (points.length - 1) : 0;
  const validById = new Map(
    validPoints.map((point) => {
      const sourceIndex = points.indexOf(point);
      const x = points.length > 1 ? padding + sourceIndex * xStep : width / 2;
      const y =
        rankRange === 0
          ? height / 2
          : padding + (((point.rank as number) - bestRank) / rankRange) * innerHeight;

      return [
        point.id,
        {
          ...point,
          x: roundCoordinate(x),
          y: roundCoordinate(y),
          label: formatRankingPointLabel(point),
        },
      ];
    }),
  );

  const layoutPoints = points
    .map((point) => validById.get(point.id))
    .filter((point): point is RankingSparklineLayoutPoint => Boolean(point));
  const segments: RankingSparklineLayoutPoint[][] = [];
  let currentSegment: RankingSparklineLayoutPoint[] = [];

  points.forEach((point) => {
    const layoutPoint = validById.get(point.id);
    if (!layoutPoint) {
      if (currentSegment.length > 0) {
        segments.push(currentSegment);
        currentSegment = [];
      }
      return;
    }

    currentSegment.push(layoutPoint);
  });

  if (currentSegment.length > 0) {
    segments.push(currentSegment);
  }

  return {
    width,
    height,
    padding,
    points: layoutPoints,
    segments,
  };
}

export function sparklinePath(points: Pick<RankingSparklineLayoutPoint, "x" | "y">[]): string {
  if (points.length === 0) {
    return "";
  }

  const [first, ...rest] = points;
  return [
    `M ${formatNumber(first.x)} ${formatNumber(first.y)}`,
    ...rest.map((point) => `L ${formatNumber(point.x)} ${formatNumber(point.y)}`),
  ].join(" ");
}

export function formatRankingSeriesLabel(series: RankingSparklineSeries | null): string {
  if (!series || series.points.length === 0) {
    return "No ranking history available";
  }

  const rankedPoints = series.points.filter((point) => point.rank !== null);
  if (rankedPoints.length === 0) {
    return `No ranking history available for ${series.category} ${series.weapon}`;
  }

  const ranks = rankedPoints.map((point) => point.rank as number);
  const latest = rankedPoints[rankedPoints.length - 1];

  return [
    `Ranking trend for ${series.category} ${series.weapon}`,
    `${series.points.length} ${series.points.length === 1 ? "season" : "seasons"}`,
    `latest rank ${formatNumber(latest.rank as number)}`,
    `best rank ${formatNumber(Math.min(...ranks))}`,
    `worst rank ${formatNumber(Math.max(...ranks))}`,
  ].join(", ");
}

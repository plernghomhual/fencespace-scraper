export type Primitive = string | number | boolean | null | undefined;

export type FencerComparisonInput =
  | string
  | FencerComparisonStatObject
  | null
  | undefined;

export type CareerStats = {
  total_competitions?: Primitive;
  gold_medals?: Primitive;
  silver_medals?: Primitive;
  bronze_medals?: Primitive;
  top8_count?: Primitive;
  best_rank?: Primitive;
  avg_rank?: Primitive;
  worst_rank?: Primitive;
  weapons_used?: unknown;
  categories_competed?: unknown;
  first_season?: Primitive;
  last_season?: Primitive;
  total_touches_scored?: Primitive;
  total_touches_received?: Primitive;
  touch_differential?: Primitive;
  clutch_score?: Primitive;
  [key: string]: unknown;
};

export type MedalStats = {
  gold?: Primitive;
  gold_medals?: Primitive;
  silver?: Primitive;
  silver_medals?: Primitive;
  bronze?: Primitive;
  bronze_medals?: Primitive;
  total?: Primitive;
  total_medals?: Primitive;
  [key: string]: unknown;
};

export type RankingStats = {
  weapon?: Primitive;
  category?: Primitive;
  season?: Primitive;
  rank?: Primitive;
  current_rank?: Primitive;
  previous_rank?: Primitive;
  rank_change?: Primitive;
  points?: Primitive;
  previous_points?: Primitive;
  points_change?: Primitive;
  trend_direction?: Primitive;
  projected_next_rank?: Primitive;
  projected_next_points?: Primitive;
  [key: string]: unknown;
};

export type EloStats = {
  weapon?: Primitive;
  category?: Primitive;
  rating?: Primitive;
  elo?: Primitive;
  current_rating?: Primitive;
  peak_rating?: Primitive;
  games?: Primitive;
  bouts?: Primitive;
  last_bout_at?: Primitive;
  updated_at?: Primitive;
  [key: string]: unknown;
};

export type PerformanceStats = {
  weapon?: Primitive;
  competitions_count?: Primitive;
  avg_delta?: Primitive;
  stddev_delta?: Primitive;
  overperformance_rate?: Primitive;
  clutch_score?: Primitive;
  [key: string]: unknown;
};

export type RecentResult = {
  tournament?: Primitive;
  tournament_name?: Primitive;
  event?: Primitive;
  rank?: Primitive;
  placement?: Primitive;
  result?: Primitive;
  opponent?: Primitive;
  score?: Primitive;
  date?: Primitive;
  bout_date?: Primitive;
  weapon?: Primitive;
  [key: string]: unknown;
};

export type HeadToHeadStats = {
  fencer_a_id?: Primitive;
  fencer_b_id?: Primitive;
  weapon?: Primitive;
  a_wins?: Primitive;
  b_wins?: Primitive;
  a_touches?: Primitive;
  b_touches?: Primitive;
  bouts_total?: Primitive;
  last_meeting_date?: Primitive;
  last_winner_id?: Primitive;
  [key: string]: unknown;
};

export type FencerComparisonStatObject = {
  id?: Primitive;
  fencer_id?: Primitive;
  fieId?: Primitive;
  fie_id?: Primitive;
  name?: Primitive;
  displayName?: Primitive;
  display_name?: Primitive;
  first_name?: Primitive;
  last_name?: Primitive;
  country?: Primitive;
  nationality?: Primitive;
  weapon?: Primitive;
  weapons?: unknown;
  career?: CareerStats;
  careerStats?: CareerStats;
  career_stats?: CareerStats;
  medalTable?: MedalStats;
  medal_table?: MedalStats;
  medals?: MedalStats;
  rankings?: RankingStats | RankingStats[];
  ranking?: RankingStats | RankingStats[];
  rankingTrends?: RankingStats | RankingStats[];
  ranking_trends?: RankingStats | RankingStats[];
  currentRanking?: RankingStats | RankingStats[];
  current_ranking?: RankingStats | RankingStats[];
  elo?: EloStats | EloStats[];
  eloRatings?: EloStats | EloStats[];
  elo_ratings?: EloStats | EloStats[];
  h2h?: HeadToHeadStats | HeadToHeadStats[];
  headToHead?: HeadToHeadStats | HeadToHeadStats[];
  head_to_head?: HeadToHeadStats | HeadToHeadStats[];
  performance?: PerformanceStats | PerformanceStats[];
  performanceAnalysis?: PerformanceStats | PerformanceStats[];
  performance_analysis?: PerformanceStats | PerformanceStats[];
  recentForm?: RecentResult[];
  recent_form?: RecentResult[];
  recentResults?: RecentResult[];
  recent_results?: RecentResult[];
  [key: string]: unknown;
};

export type ComparisonCellState = "available" | "missing" | "empty";

export type ComparisonCell = {
  display: string;
  raw?: unknown;
  state: ComparisonCellState;
};

export type ComparisonRow = {
  key: string;
  label: string;
  left: ComparisonCell;
  right: ComparisonCell;
  winner?: "left" | "right" | "tie";
  summary?: string;
};

export type ComparisonSection = {
  id:
    | "career"
    | "medals"
    | "rankings"
    | "elo"
    | "h2h"
    | "weapons"
    | "recentForm";
  title: string;
  rows: ComparisonRow[];
};

export type NormalizedFencerStats = {
  id: string | null;
  fieId: string | null;
  displayName: string;
  country: string | null;
  primaryWeapon: string | null;
  weapons: string[];
  categories: string[];
  career: CareerStats | null;
  medals: MedalStats | null;
  ranking: RankingStats | null;
  elo: EloStats | null;
  performance: PerformanceStats | null;
  h2h: HeadToHeadStats[];
  recentForm: RecentResult[];
  source: FencerComparisonStatObject;
};

export type NormalizeFencerComparisonOptions = {
  left?: FencerComparisonInput;
  right?: FencerComparisonInput;
  h2hRows?: HeadToHeadStats[];
};

export type NormalizedFencerComparison = {
  left: NormalizedFencerStats | null;
  right: NormalizedFencerStats | null;
  isSameFencer: boolean;
  sections: ComparisonSection[];
};

const NO_DATA = "No data";
const NO_BOUTS = "No bouts";
const NO_RECENT_RESULTS = "No recent results";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asObject(value: unknown): FencerComparisonStatObject | null {
  return isRecord(value) ? (value as FencerComparisonStatObject) : null;
}

function asString(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.replace(/,/g, "").trim();
    if (normalized.length === 0) {
      return null;
    }
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => asString(item))
      .filter((item): item is string => Boolean(item));
  }
  const text = asString(value);
  if (!text) {
    return [];
  }
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function firstObject<T extends Record<string, unknown>>(value: unknown): T | null {
  if (Array.isArray(value)) {
    return (value.find((item) => isRecord(item)) as T | undefined) ?? null;
  }
  return isRecord(value) ? (value as T) : null;
}

function objectList<T extends Record<string, unknown>>(value: unknown): T[] {
  if (Array.isArray(value)) {
    return value.filter(isRecord) as T[];
  }
  return isRecord(value) ? [value as T] : [];
}

function pickObject<T extends Record<string, unknown>>(
  source: FencerComparisonStatObject,
  keys: string[],
): T | null {
  for (const key of keys) {
    const value = firstObject<T>(source[key]);
    if (value) {
      return value;
    }
  }
  return null;
}

function pickObjectList<T extends Record<string, unknown>>(
  source: FencerComparisonStatObject,
  keys: string[],
): T[] {
  for (const key of keys) {
    const value = objectList<T>(source[key]);
    if (value.length > 0) {
      return value;
    }
  }
  return [];
}

function profileName(source: FencerComparisonStatObject): string {
  const direct =
    asString(source.displayName) ??
    asString(source.display_name) ??
    asString(source.name);
  if (direct) {
    return direct;
  }

  const joined = [asString(source.first_name), asString(source.last_name)]
    .filter(Boolean)
    .join(" ");
  return joined || "Unknown fencer";
}

function makeCell(display: string, raw?: unknown, state: ComparisonCellState = "available"): ComparisonCell {
  return { display, raw, state };
}

function missingCell(display = NO_DATA): ComparisonCell {
  return makeCell(display, undefined, "missing");
}

function numberCell(value: unknown, options: { prefix?: string; suffix?: string; decimals?: number } = {}): ComparisonCell {
  const numeric = asNumber(value);
  if (numeric === null) {
    return missingCell();
  }
  const displayNumber =
    typeof options.decimals === "number"
      ? numeric.toFixed(options.decimals)
      : Number.isInteger(numeric)
        ? String(numeric)
        : String(Number(numeric.toFixed(2)));
  return makeCell(`${options.prefix ?? ""}${displayNumber}${options.suffix ?? ""}`, numeric);
}

function textCell(value: unknown, fallback = NO_DATA): ComparisonCell {
  const text = asString(value);
  return text ? makeCell(text, value) : missingCell(fallback);
}

function listCell(values: unknown, fallback = NO_DATA): ComparisonCell {
  const list = asList(values);
  return list.length > 0 ? makeCell(list.join(", "), list) : missingCell(fallback);
}

function ordinal(value: unknown): string | null {
  const numeric = asNumber(value);
  if (numeric === null) {
    return null;
  }
  const whole = Math.trunc(numeric);
  const mod100 = whole % 100;
  const suffix =
    mod100 >= 11 && mod100 <= 13
      ? "th"
      : whole % 10 === 1
        ? "st"
        : whole % 10 === 2
          ? "nd"
          : whole % 10 === 3
            ? "rd"
            : "th";
  return `${whole}${suffix}`;
}

function rankCell(value: unknown): ComparisonCell {
  const numeric = asNumber(value);
  return numeric === null ? missingCell() : makeCell(`#${Math.trunc(numeric)}`, numeric);
}

function percentCell(value: unknown): ComparisonCell {
  const numeric = asNumber(value);
  if (numeric === null) {
    return missingCell();
  }
  return makeCell(`${Number(numeric.toFixed(1))}%`, numeric);
}

function totalMedals(medals: MedalStats | null): number | null {
  if (!medals) {
    return null;
  }
  const explicit = asNumber(medals.total) ?? asNumber(medals.total_medals);
  if (explicit !== null) {
    return explicit;
  }
  const gold = asNumber(medals.gold) ?? asNumber(medals.gold_medals) ?? 0;
  const silver = asNumber(medals.silver) ?? asNumber(medals.silver_medals) ?? 0;
  const bronze = asNumber(medals.bronze) ?? asNumber(medals.bronze_medals) ?? 0;
  const total = gold + silver + bronze;
  return total > 0 ? total : null;
}

function winner(left: ComparisonCell, right: ComparisonCell, higherIsBetter = true): "left" | "right" | "tie" | undefined {
  const leftValue = asNumber(left.raw);
  const rightValue = asNumber(right.raw);
  if (leftValue === null || rightValue === null) {
    return undefined;
  }
  if (leftValue === rightValue) {
    return "tie";
  }
  const leftWins = higherIsBetter ? leftValue > rightValue : leftValue < rightValue;
  return leftWins ? "left" : "right";
}

function row(
  key: string,
  label: string,
  left: ComparisonCell,
  right: ComparisonCell,
  options: { higherIsBetter?: boolean; summary?: string } = {},
): ComparisonRow {
  return {
    key,
    label,
    left,
    right,
    winner: winner(left, right, options.higherIsBetter ?? true),
    summary: options.summary,
  };
}

function normalizeId(input: FencerComparisonInput): string | null {
  if (typeof input === "string") {
    return asString(input);
  }
  const source = asObject(input);
  if (!source) {
    return null;
  }
  return (
    asString(source.id) ??
    asString(source.fencer_id) ??
    asString(source.fieId) ??
    asString(source.fie_id)
  );
}

export function normalizeFencerStats(input: FencerComparisonInput): NormalizedFencerStats | null {
  const source = asObject(input);
  if (!source) {
    return null;
  }

  const career = pickObject<CareerStats>(source, ["careerStats", "career_stats", "career"]);
  const medals =
    pickObject<MedalStats>(source, ["medalTable", "medal_table", "medals"]) ??
    (career
      ? {
          gold: career.gold_medals,
          silver: career.silver_medals,
          bronze: career.bronze_medals,
        }
      : null);
  const ranking = pickObject<RankingStats>(source, [
    "rankings",
    "ranking",
    "rankingTrends",
    "ranking_trends",
    "currentRanking",
    "current_ranking",
  ]);
  const elo = pickObject<EloStats>(source, ["elo", "eloRatings", "elo_ratings"]);
  const performance = pickObject<PerformanceStats>(source, [
    "performanceAnalysis",
    "performance_analysis",
    "performance",
  ]);
  const h2h = pickObjectList<HeadToHeadStats>(source, ["h2h", "headToHead", "head_to_head"]);
  const recentForm = pickObjectList<RecentResult>(source, [
    "recentForm",
    "recent_form",
    "recentResults",
    "recent_results",
  ]);
  const careerWeapons = career ? asList(career.weapons_used) : [];
  const directWeapons = asList(source.weapons);
  const primaryWeapon = asString(source.weapon) ?? careerWeapons[0] ?? directWeapons[0] ?? null;
  const weapons = Array.from(new Set([...directWeapons, ...careerWeapons, primaryWeapon].filter(Boolean) as string[]));

  return {
    id: normalizeId(source),
    fieId: asString(source.fieId) ?? asString(source.fie_id),
    displayName: profileName(source),
    country: asString(source.country) ?? asString(source.nationality),
    primaryWeapon,
    weapons,
    categories: career ? asList(career.categories_competed) : [],
    career,
    medals,
    ranking,
    elo,
    performance,
    h2h,
    recentForm,
    source,
  };
}

function combineH2hRows(
  left: NormalizedFencerStats | null,
  right: NormalizedFencerStats | null,
  externalRows: HeadToHeadStats[] = [],
): HeadToHeadStats[] {
  return [
    ...externalRows,
    ...(left?.h2h ?? []),
    ...(right?.h2h ?? []),
  ].filter((candidate) => {
    if (!left?.id || !right?.id) {
      return false;
    }
    const a = asString(candidate.fencer_a_id);
    const b = asString(candidate.fencer_b_id);
    return (
      (a === left.id && b === right.id) ||
      (a === right.id && b === left.id)
    );
  });
}

function h2hCells(
  h2hRows: HeadToHeadStats[],
  left: NormalizedFencerStats | null,
  right: NormalizedFencerStats | null,
): { label: string; leftWins: ComparisonCell; rightWins: ComparisonCell; summary: string } {
  if (!left?.id || !right?.id || h2hRows.length === 0) {
    return {
      label: "Wins",
      leftWins: missingCell(NO_BOUTS),
      rightWins: missingCell(NO_BOUTS),
      summary: NO_BOUTS,
    };
  }

  let leftWins = 0;
  let rightWins = 0;
  let bouts = 0;
  const weapons = new Set<string>();
  for (const item of h2hRows) {
    const a = asString(item.fencer_a_id);
    const b = asString(item.fencer_b_id);
    const aWins = asNumber(item.a_wins) ?? 0;
    const bWins = asNumber(item.b_wins) ?? 0;
    if (a === left.id && b === right.id) {
      leftWins += aWins;
      rightWins += bWins;
    } else if (a === right.id && b === left.id) {
      leftWins += bWins;
      rightWins += aWins;
    }
    bouts += asNumber(item.bouts_total) ?? aWins + bWins;
    const weapon = asString(item.weapon);
    if (weapon) {
      weapons.add(weapon);
    }
  }

  const weaponLabel = Array.from(weapons).join("/") || "H2H";
  return {
    label: weapons.size === 1 ? `${weaponLabel} wins` : "Wins",
    leftWins: makeCell(String(leftWins), leftWins),
    rightWins: makeCell(String(rightWins), rightWins),
    summary: bouts > 0 ? `${leftWins}-${rightWins}` : NO_BOUTS,
  };
}

function careerSection(left: NormalizedFencerStats | null, right: NormalizedFencerStats | null): ComparisonSection {
  const leftCareer = left?.career ?? null;
  const rightCareer = right?.career ?? null;
  return {
    id: "career",
    title: "Career",
    rows: [
      row(
        "competitions",
        "Competitions",
        numberCell(leftCareer?.total_competitions),
        numberCell(rightCareer?.total_competitions),
      ),
      row(
        "best_rank",
        "Best rank",
        rankCell(leftCareer?.best_rank),
        rankCell(rightCareer?.best_rank),
        { higherIsBetter: false },
      ),
      row(
        "avg_rank",
        "Average rank",
        numberCell(leftCareer?.avg_rank),
        numberCell(rightCareer?.avg_rank),
        { higherIsBetter: false },
      ),
      row(
        "top8",
        "Top 8s",
        numberCell(leftCareer?.top8_count),
        numberCell(rightCareer?.top8_count),
      ),
      row(
        "touch_differential",
        "Touch differential",
        numberCell(leftCareer?.touch_differential),
        numberCell(rightCareer?.touch_differential),
      ),
      row(
        "seasons",
        "Seasons",
        textCell(
          leftCareer?.first_season || leftCareer?.last_season
            ? `${leftCareer?.first_season ?? "?"} - ${leftCareer?.last_season ?? "?"}`
            : null,
        ),
        textCell(
          rightCareer?.first_season || rightCareer?.last_season
            ? `${rightCareer?.first_season ?? "?"} - ${rightCareer?.last_season ?? "?"}`
            : null,
        ),
      ),
    ],
  };
}

function medalsSection(left: NormalizedFencerStats | null, right: NormalizedFencerStats | null): ComparisonSection {
  const leftMedals = left?.medals ?? null;
  const rightMedals = right?.medals ?? null;
  return {
    id: "medals",
    title: "Medals",
    rows: [
      row("Gold", "Gold", numberCell(leftMedals?.gold ?? leftMedals?.gold_medals), numberCell(rightMedals?.gold ?? rightMedals?.gold_medals)),
      row("silver", "Silver", numberCell(leftMedals?.silver ?? leftMedals?.silver_medals), numberCell(rightMedals?.silver ?? rightMedals?.silver_medals)),
      row("bronze", "Bronze", numberCell(leftMedals?.bronze ?? leftMedals?.bronze_medals), numberCell(rightMedals?.bronze ?? rightMedals?.bronze_medals)),
      row("total", "Total medals", numberCell(totalMedals(leftMedals)), numberCell(totalMedals(rightMedals))),
    ],
  };
}

function rankingDescriptor(ranking: RankingStats | null): string | null {
  if (!ranking) {
    return null;
  }
  const bits = [asString(ranking.weapon), asString(ranking.category), asString(ranking.season)].filter(Boolean);
  return bits.length > 0 ? bits.join(" ") : null;
}

function rankingsSection(left: NormalizedFencerStats | null, right: NormalizedFencerStats | null): ComparisonSection {
  const leftRanking = left?.ranking ?? null;
  const rightRanking = right?.ranking ?? null;
  return {
    id: "rankings",
    title: "Rankings",
    rows: [
      row(
        "current_rank",
        "Current rank",
        rankCell(leftRanking?.rank ?? leftRanking?.current_rank),
        rankCell(rightRanking?.rank ?? rightRanking?.current_rank),
        { higherIsBetter: false },
      ),
      row("points", "Points", numberCell(leftRanking?.points), numberCell(rightRanking?.points)),
      row("trend", "Trend", textCell(leftRanking?.trend_direction), textCell(rightRanking?.trend_direction)),
      row(
        "projected_next_rank",
        "Projected next rank",
        rankCell(leftRanking?.projected_next_rank),
        rankCell(rightRanking?.projected_next_rank),
        { higherIsBetter: false },
      ),
      row("ranking_context", "Context", textCell(rankingDescriptor(leftRanking)), textCell(rankingDescriptor(rightRanking))),
    ],
  };
}

function eloRating(elo: EloStats | null): unknown {
  return elo?.rating ?? elo?.elo ?? elo?.current_rating;
}

function eloSection(left: NormalizedFencerStats | null, right: NormalizedFencerStats | null): ComparisonSection {
  const leftElo = left?.elo ?? null;
  const rightElo = right?.elo ?? null;
  const leftPerformance = left?.performance ?? null;
  const rightPerformance = right?.performance ?? null;
  return {
    id: "elo",
    title: "Elo",
    rows: [
      row("rating", "Current Elo", numberCell(eloRating(leftElo)), numberCell(eloRating(rightElo))),
      row("peak", "Peak Elo", numberCell(leftElo?.peak_rating), numberCell(rightElo?.peak_rating)),
      row("games", "Rated bouts", numberCell(leftElo?.games ?? leftElo?.bouts), numberCell(rightElo?.games ?? rightElo?.bouts)),
      row("clutch", "Clutch score", numberCell(leftPerformance?.clutch_score), numberCell(rightPerformance?.clutch_score)),
      row("overperformance", "Overperformance", percentCell(leftPerformance?.overperformance_rate), percentCell(rightPerformance?.overperformance_rate)),
    ],
  };
}

function h2hSection(
  left: NormalizedFencerStats | null,
  right: NormalizedFencerStats | null,
  h2hRows: HeadToHeadStats[],
): ComparisonSection {
  const cells = h2hCells(h2hRows, left, right);
  return {
    id: "h2h",
    title: "Head to head",
    rows: [
      row("wins", cells.label, cells.leftWins, cells.rightWins, { summary: cells.summary }),
    ],
  };
}

function weaponsSection(left: NormalizedFencerStats | null, right: NormalizedFencerStats | null): ComparisonSection {
  return {
    id: "weapons",
    title: "Weapons",
    rows: [
      row("weapons", "Weapons", listCell(left?.weapons), listCell(right?.weapons)),
      row("primary", "Primary weapon", textCell(left?.primaryWeapon), textCell(right?.primaryWeapon)),
      row("categories", "Categories", listCell(left?.categories), listCell(right?.categories)),
    ],
  };
}

function recentResultText(result: RecentResult): string | null {
  const placement = ordinal(result.placement ?? result.rank);
  const resultText = asString(result.result);
  const tournament = asString(result.tournament) ?? asString(result.tournament_name) ?? asString(result.event);
  const score = asString(result.score);
  const opponent = asString(result.opponent);
  if (placement && tournament) {
    return `${placement} ${tournament}`;
  }
  if (resultText && opponent && score) {
    return `${resultText} vs ${opponent} ${score}`;
  }
  if (resultText && tournament) {
    return `${resultText} ${tournament}`;
  }
  return tournament ?? resultText;
}

function recentFormCell(results: RecentResult[] | undefined): ComparisonCell {
  const formatted = (results ?? [])
    .map(recentResultText)
    .filter((item): item is string => Boolean(item))
    .slice(0, 3);
  return formatted.length > 0
    ? makeCell(formatted.join(" | "), formatted)
    : missingCell(NO_RECENT_RESULTS);
}

function recentFormSection(left: NormalizedFencerStats | null, right: NormalizedFencerStats | null): ComparisonSection {
  return {
    id: "recentForm",
    title: "Recent form",
    rows: [
      row("recent", "Recent form", recentFormCell(left?.recentForm), recentFormCell(right?.recentForm)),
    ],
  };
}

export function normalizeFencerComparison(
  options: NormalizeFencerComparisonOptions,
): NormalizedFencerComparison {
  const left = normalizeFencerStats(options.left);
  const right = normalizeFencerStats(options.right);
  const leftId = normalizeId(options.left);
  const rightId = normalizeId(options.right);
  const isSameFencer = Boolean(leftId && rightId && leftId === rightId);
  const h2h = combineH2hRows(left, right, options.h2hRows ?? []);

  return {
    left,
    right,
    isSameFencer,
    sections: [
      careerSection(left, right),
      medalsSection(left, right),
      rankingsSection(left, right),
      eloSection(left, right),
      h2hSection(left, right, h2h),
      weaponsSection(left, right),
      recentFormSection(left, right),
    ],
  };
}


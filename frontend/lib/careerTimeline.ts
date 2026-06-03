export type TimelineEventKind =
  | "season"
  | "medal"
  | "ranking_peak"
  | "country_change"
  | "milestone"
  | "longevity";

export type TimelineDatePrecision = "day" | "month" | "year" | "season" | "unknown";

export interface CareerBaseRow {
  weapon?: string | null;
  category?: string | null;
  country?: string | null;
  country_code?: string | null;
  nationality?: string | null;
  date?: string | null;
  year?: string | number | null;
  season?: string | number | null;
  seasonLabel?: string | number | null;
  season_label?: string | number | null;
  [key: string]: unknown;
}

export interface CareerStatsRow extends CareerBaseRow {
  competitions?: number | string | null;
  competition_count?: number | string | null;
  events?: number | string | null;
  event_count?: number | string | null;
  wins?: number | string | null;
  bouts?: number | string | null;
  points?: number | string | null;
  rank?: number | string | null;
  ranking?: number | string | null;
  bestRank?: number | string | null;
  best_rank?: number | string | null;
  rankingPeak?: number | string | null;
  ranking_peak?: number | string | null;
}

export interface CareerMilestoneRow extends CareerBaseRow {
  title?: string | null;
  label?: string | null;
  name?: string | null;
  milestone?: string | null;
  description?: string | null;
  type?: string | null;
}

export interface CareerMedalRow extends CareerBaseRow {
  competition?: string | null;
  competition_name?: string | null;
  event?: string | null;
  event_name?: string | null;
  medal?: string | null;
  medal_type?: string | null;
  place?: number | string | null;
}

export interface CareerTransferRow extends CareerBaseRow {
  fromCountry?: string | null;
  from_country?: string | null;
  toCountry?: string | null;
  to_country?: string | null;
}

export interface CareerLongevityRow extends CareerBaseRow {
  firstSeason?: string | number | null;
  first_season?: string | number | null;
  lastSeason?: string | number | null;
  last_season?: string | number | null;
  activeSeasons?: number | string | null;
  active_seasons?: number | string | null;
  spanYears?: number | string | null;
  span_years?: number | string | null;
}

export interface CareerTimelineInput {
  careerStats?: CareerStatsRow[] | null;
  career_stats?: CareerStatsRow[] | null;
  milestones?: CareerMilestoneRow[] | null;
  medals?: CareerMedalRow[] | null;
  transfers?: CareerTransferRow[] | null;
  longevity?: CareerLongevityRow[] | null;
}

export interface CareerTimelineFilter {
  weapon?: string;
  category?: string;
}

export interface CareerTimelineFilterOptions {
  weapons: string[];
  categories: string[];
}

export interface NormalizeCareerTimelineOptions {
  locale?: string;
}

export interface CareerTimelineEvent {
  id: string;
  kind: TimelineEventKind;
  title: string;
  description?: string;
  details: string[];
  weapon?: string;
  category?: string;
  country?: string;
  medal?: string;
  rank?: number;
  dateISO?: string;
  seasonLabel?: string;
  year?: number;
  timeLabel: string;
  ariaLabel: string;
  sortKey: number;
  datePrecision: TimelineDatePrecision;
}

export interface NormalizedCareerTimeline {
  events: CareerTimelineEvent[];
  filterOptions: CareerTimelineFilterOptions;
}

interface DateInfo {
  dateISO?: string;
  seasonLabel?: string;
  year?: number;
  datePrecision: TimelineDatePrecision;
  sortKey: number;
}

interface SeasonAggregate {
  idBase: string;
  sourceOrder: number;
  seasonLabel?: string;
  weapon?: string;
  category?: string;
  countryNames: Set<string>;
  competitions: number;
  wins?: number;
  bouts?: number;
  points?: number;
  bestRank?: number;
  dateInfo: DateInfo;
}

const UNKNOWN_SORT_KEY = Number.MAX_SAFE_INTEGER;

const KIND_LABELS: Record<TimelineEventKind, string> = {
  season: "Season",
  medal: "Medal",
  ranking_peak: "Ranking peak",
  country_change: "Country change",
  milestone: "Milestone",
  longevity: "Career span",
};

const KIND_PRIORITY: Record<TimelineEventKind, number> = {
  longevity: 0,
  season: 1,
  ranking_peak: 2,
  medal: 3,
  country_change: 4,
  milestone: 5,
};

export function normalizeCareerTimeline(
  input: CareerTimelineInput | null | undefined,
  options: NormalizeCareerTimelineOptions = {},
): NormalizedCareerTimeline {
  const locale = options.locale;
  const events: Array<CareerTimelineEvent & { sourceOrder: number }> = [];
  const statsRows = asArray(input?.careerStats ?? input?.career_stats);
  const sequence = createSequence();

  for (const seasonEvent of normalizeSeasonStats(statsRows, locale, sequence)) {
    events.push(seasonEvent);
  }

  for (const row of asArray(input?.medals)) {
    const common = readCommonFields(row);
    const dateInfo = readDateInfo(row, readSeasonLabel(row));
    const medal = readText(row, ["medal", "medal_type"]) ?? placeToMedal(row.place);
    const competition =
      readText(row, ["competition", "competition_name", "event", "event_name"]) ??
      "Competition unknown";
    const title = medal ? `${medal} medal - ${competition}` : `Medal - ${competition}`;
    events.push(
      makeEvent({
        kind: "medal",
        title,
        description: readText(row, ["description"]),
        details: compact([
          common.weapon && `Weapon: ${common.weapon}`,
          common.category && `Category: ${common.category}`,
          common.country && `Country: ${common.country}`,
        ]),
        medal,
        ...common,
        ...dateInfo,
        sourceOrder: sequence.next(),
      }, locale),
    );
  }

  for (const row of asArray(input?.transfers)) {
    const common = readCommonFields(row);
    const dateInfo = readDateInfo(row, readSeasonLabel(row));
    const fromCountry = readText(row, ["fromCountry", "from_country"]);
    const toCountry = readText(row, ["toCountry", "to_country"]);
    const title =
      fromCountry && toCountry
        ? `Country change: ${fromCountry} -> ${toCountry}`
        : toCountry
          ? `Country change to ${toCountry}`
          : "Country change";
    events.push(
      makeEvent({
        kind: "country_change",
        title,
        details: compact([
          fromCountry && `From: ${fromCountry}`,
          toCountry && `To: ${toCountry}`,
          common.weapon && `Weapon: ${common.weapon}`,
          common.category && `Category: ${common.category}`,
        ]),
        country: toCountry ?? common.country,
        weapon: common.weapon,
        category: common.category,
        ...dateInfo,
        sourceOrder: sequence.next(),
      }, locale),
    );
  }

  for (const row of asArray(input?.milestones)) {
    const common = readCommonFields(row);
    const dateInfo = readDateInfo(row, readSeasonLabel(row));
    const title =
      readText(row, ["title", "label", "name", "milestone"]) ?? "Career milestone";
    const type = readText(row, ["type"]);
    events.push(
      makeEvent({
        kind: "milestone",
        title,
        description: readText(row, ["description"]),
        details: compact([
          type && `Type: ${type}`,
          common.weapon && `Weapon: ${common.weapon}`,
          common.category && `Category: ${common.category}`,
          common.country && `Country: ${common.country}`,
        ]),
        ...common,
        ...dateInfo,
        sourceOrder: sequence.next(),
      }, locale),
    );
  }

  for (const row of asArray(input?.longevity)) {
    const common = readCommonFields(row);
    const firstSeason = normalizeText(row.firstSeason ?? row.first_season);
    const lastSeason = normalizeText(row.lastSeason ?? row.last_season);
    const activeSeasons = readNumber(row, ["activeSeasons", "active_seasons"]);
    const spanYears = readNumber(row, ["spanYears", "span_years"]);
    const dateInfo = readDateInfo(row, firstSeason);
    const spanLabel =
      firstSeason && lastSeason
        ? `${firstSeason} - ${lastSeason}`
        : firstSeason
          ? `${firstSeason} onward`
          : lastSeason
            ? `through ${lastSeason}`
            : "Career span";
    events.push(
      makeEvent({
        kind: "longevity",
        title: `Career span: ${spanLabel}`,
        details: compact([
          activeSeasons != null && `${formatNumber(activeSeasons, locale)} active seasons`,
          spanYears != null && `${formatNumber(spanYears, locale)} year span`,
          common.weapon && `Weapon: ${common.weapon}`,
          common.category && `Category: ${common.category}`,
        ]),
        ...common,
        ...dateInfo,
        seasonLabel: firstSeason ?? dateInfo.seasonLabel,
        sourceOrder: sequence.next(),
      }, locale),
    );
  }

  const sortedEvents = events
    .sort((a, b) => compareEvents(a, b))
    .map(({ sourceOrder: _sourceOrder, ...event }) => event);

  return {
    events: sortedEvents,
    filterOptions: collectFilterOptions(sortedEvents),
  };
}

export function filterTimelineEvents(
  events: CareerTimelineEvent[],
  filter: CareerTimelineFilter = {},
): CareerTimelineEvent[] {
  return events.filter((event) => {
    if (filter.weapon && event.weapon && event.weapon !== filter.weapon) {
      return false;
    }
    if (filter.category && event.category && event.category !== filter.category) {
      return false;
    }
    return true;
  });
}

function normalizeSeasonStats(
  rows: CareerStatsRow[],
  locale: string | undefined,
  sequence: { next: () => number },
): Array<CareerTimelineEvent & { sourceOrder: number }> {
  const aggregates = new Map<string, SeasonAggregate>();

  for (const row of rows) {
    const common = readCommonFields(row);
    const seasonLabel = readSeasonLabel(row);
    const dateInfo = readDateInfo(row, seasonLabel);
    const key = [
      seasonLabel ?? "unknown-season",
      common.weapon ?? "all-weapons",
      common.category ?? "all-categories",
    ].join("|");
    const competitions =
      readNumber(row, ["competitions", "competition_count", "events", "event_count"]) ?? 0;
    const wins = readNumber(row, ["wins"]);
    const bouts = readNumber(row, ["bouts"]);
    const points = readNumber(row, ["points"]);
    const rank = readNumber(row, [
      "rankingPeak",
      "ranking_peak",
      "bestRank",
      "best_rank",
      "ranking",
      "rank",
    ]);
    const existing = aggregates.get(key);

    if (!existing) {
      aggregates.set(key, {
        idBase: key,
        sourceOrder: sequence.next(),
        seasonLabel,
        weapon: common.weapon,
        category: common.category,
        countryNames: new Set(compact([common.country])),
        competitions,
        wins,
        bouts,
        points,
        bestRank: rank,
        dateInfo,
      });
      continue;
    }

    existing.competitions += competitions;
    existing.countryNames = new Set([...existing.countryNames, ...compact([common.country])]);
    existing.wins = sumOptional(existing.wins, wins);
    existing.bouts = sumOptional(existing.bouts, bouts);
    existing.points = sumOptional(existing.points, points);
    existing.bestRank = minOptional(existing.bestRank, rank);
    existing.dateInfo = earliestKnownDateInfo(existing.dateInfo, dateInfo);
  }

  const events: Array<CareerTimelineEvent & { sourceOrder: number }> = [];

  for (const aggregate of aggregates.values()) {
    const seasonTitle = `${aggregate.seasonLabel ?? "Unknown season"} season`;
    const countries = [...aggregate.countryNames];
    const details = compact([
      aggregate.weapon && `Weapon: ${aggregate.weapon}`,
      aggregate.category && `Category: ${aggregate.category}`,
      countries.length > 0 && `Country: ${countries.join(", ")}`,
      aggregate.competitions > 0 &&
        `${formatNumber(aggregate.competitions, locale)} ${plural(aggregate.competitions, "competition")}`,
      aggregate.wins != null && `${formatNumber(aggregate.wins, locale)} wins`,
      aggregate.bouts != null && `${formatNumber(aggregate.bouts, locale)} bouts`,
      aggregate.points != null && `${formatNumber(aggregate.points, locale)} points`,
      aggregate.bestRank != null && `Best ranking #${formatRank(aggregate.bestRank, locale)}`,
    ]);

    events.push(
      makeEvent({
        kind: "season",
        title: seasonTitle,
        details,
        weapon: aggregate.weapon,
        category: aggregate.category,
        country: countries[0],
        seasonLabel: aggregate.seasonLabel,
        ...aggregate.dateInfo,
        sourceOrder: aggregate.sourceOrder,
      }, locale),
    );

    if (aggregate.bestRank != null) {
      events.push(
        makeEvent({
          kind: "ranking_peak",
          title: `Ranking peak #${formatRank(aggregate.bestRank, locale)}`,
          details: compact([
            aggregate.seasonLabel && `Season: ${aggregate.seasonLabel}`,
            aggregate.weapon && `Weapon: ${aggregate.weapon}`,
            aggregate.category && `Category: ${aggregate.category}`,
          ]),
          rank: aggregate.bestRank,
          weapon: aggregate.weapon,
          category: aggregate.category,
          country: countries[0],
          seasonLabel: aggregate.seasonLabel,
          ...aggregate.dateInfo,
          sourceOrder: sequence.next(),
        }, locale),
      );
    }
  }

  return events;
}

function makeEvent(
  event: Omit<CareerTimelineEvent, "id" | "ariaLabel" | "timeLabel"> & {
    sourceOrder: number;
  },
  locale: string | undefined,
): CareerTimelineEvent & { sourceOrder: number } {
  const timeLabel = formatDateInfo(event, locale);
  const id = [
    event.kind,
    event.seasonLabel ?? event.dateISO ?? event.year ?? "unknown",
    event.weapon ?? "all",
    event.category ?? "all",
    event.sourceOrder,
  ]
    .join("-")
    .replace(/[^a-zA-Z0-9_-]+/g, "-");
  const ariaLabel = compact([
    timeLabel,
    KIND_LABELS[event.kind],
    event.title,
    event.description,
    ...event.details,
  ]).join(", ");

  return {
    ...event,
    id,
    timeLabel,
    ariaLabel,
  };
}

function compareEvents(
  a: CareerTimelineEvent & { sourceOrder: number },
  b: CareerTimelineEvent & { sourceOrder: number },
): number {
  if (a.sortKey !== b.sortKey) {
    return a.sortKey - b.sortKey;
  }
  const priority = KIND_PRIORITY[a.kind] - KIND_PRIORITY[b.kind];
  if (priority !== 0) {
    return priority;
  }
  return a.sourceOrder - b.sourceOrder;
}

function collectFilterOptions(events: CareerTimelineEvent[]): CareerTimelineFilterOptions {
  const weapons = new Set<string>();
  const categories = new Set<string>();

  for (const event of events) {
    if (event.weapon) {
      weapons.add(event.weapon);
    }
    if (event.category) {
      categories.add(event.category);
    }
  }

  return {
    weapons: [...weapons].sort((a, b) => a.localeCompare(b)),
    categories: [...categories].sort((a, b) => a.localeCompare(b)),
  };
}

function readCommonFields(row: CareerBaseRow): Pick<
  CareerTimelineEvent,
  "weapon" | "category" | "country"
> {
  return {
    weapon: readText(row, ["weapon"]),
    category: readText(row, ["category"]),
    country: readText(row, ["country", "country_code", "nationality"]),
  };
}

function readDateInfo(row: CareerBaseRow, seasonFallback?: string): DateInfo {
  const rawDate = readText(row, [
    "date",
    "eventDate",
    "event_date",
    "startDate",
    "start_date",
  ]);
  const parsedDate = parseISODate(rawDate);

  if (parsedDate) {
    const dateISO =
      parsedDate.precision === "day"
      ? `${parsedDate.year}-${pad2(parsedDate.month)}-${pad2(parsedDate.day)}`
      : `${parsedDate.year}-${pad2(parsedDate.month)}`;
    return {
      dateISO,
      year: parsedDate.year,
      datePrecision: parsedDate.precision,
      sortKey: Date.UTC(parsedDate.year, parsedDate.month - 1, parsedDate.day),
    };
  }

  const explicitYear = readNumber(row, ["year", "eventYear", "event_year"]);
  if (explicitYear != null) {
    const year = Math.trunc(explicitYear);
    return {
      year,
      datePrecision: "year",
      sortKey: Date.UTC(year, 0, 1),
    };
  }

  const seasonLabel = seasonFallback ?? readSeasonLabel(row);
  const seasonYear = extractYear(seasonLabel);
  if (seasonLabel && seasonYear != null) {
    return {
      seasonLabel,
      year: seasonYear,
      datePrecision: "season",
      sortKey: Date.UTC(seasonYear, 0, 1),
    };
  }

  return {
    seasonLabel,
    datePrecision: "unknown",
    sortKey: UNKNOWN_SORT_KEY,
  };
}

function readSeasonLabel(row: CareerBaseRow): string | undefined {
  return normalizeText(row.seasonLabel ?? row.season_label ?? row.season);
}

function formatDateInfo(info: DateInfo, locale: string | undefined): string {
  if (info.dateISO) {
    const parsedDate = parseISODate(info.dateISO);
    if (parsedDate?.precision === "day") {
      return new Intl.DateTimeFormat(locale, {
        day: "numeric",
        month: "short",
        timeZone: "UTC",
        year: "numeric",
      }).format(new Date(Date.UTC(parsedDate.year, parsedDate.month - 1, parsedDate.day)));
    }
    if (parsedDate?.precision === "month") {
      return new Intl.DateTimeFormat(locale, {
        month: "short",
        timeZone: "UTC",
        year: "numeric",
      }).format(new Date(Date.UTC(parsedDate.year, parsedDate.month - 1, 1)));
    }
  }

  if (info.datePrecision === "season" && info.seasonLabel) {
    return `Season ${info.seasonLabel}`;
  }

  if (info.year != null) {
    return new Intl.NumberFormat(locale, { maximumFractionDigits: 0, useGrouping: false }).format(
      info.year,
    );
  }

  return "Date unknown";
}

function readText(row: CareerBaseRow, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = normalizeText(row[key]);
    if (value) {
      return value;
    }
  }
  return undefined;
}

function readNumber(row: CareerBaseRow, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = toFiniteNumber(row[key]);
    if (value != null) {
      return value;
    }
  }
  return undefined;
}

function normalizeText(value: unknown): string | undefined {
  if (value == null) {
    return undefined;
  }
  const text = String(value).trim();
  return text.length > 0 ? text : undefined;
}

function toFiniteNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.trim().replace(/,/g, "");
    if (!normalized) {
      return undefined;
    }
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function parseISODate(value: string | undefined):
  | { year: number; month: number; day: number; precision: "day" | "month" }
  | undefined {
  if (!value) {
    return undefined;
  }

  const dayMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dayMatch) {
    const year = Number(dayMatch[1]);
    const month = Number(dayMatch[2]);
    const day = Number(dayMatch[3]);
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return { year, month, day, precision: "day" };
    }
  }

  const monthMatch = value.match(/^(\d{4})-(\d{2})$/);
  if (monthMatch) {
    const year = Number(monthMatch[1]);
    const month = Number(monthMatch[2]);
    if (month >= 1 && month <= 12) {
      return { year, month, day: 1, precision: "month" };
    }
  }

  return undefined;
}

function extractYear(value: string | number | undefined): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  const text = normalizeText(value);
  const match = text?.match(/\b(19|20)\d{2}\b/);
  return match ? Number(match[0]) : undefined;
}

function earliestKnownDateInfo(current: DateInfo, next: DateInfo): DateInfo {
  if (current.sortKey === UNKNOWN_SORT_KEY) {
    return next;
  }
  if (next.sortKey === UNKNOWN_SORT_KEY) {
    return current;
  }
  return next.sortKey < current.sortKey ? next : current;
}

function minOptional(current: number | undefined, next: number | undefined): number | undefined {
  if (current == null) {
    return next;
  }
  if (next == null) {
    return current;
  }
  return Math.min(current, next);
}

function sumOptional(current: number | undefined, next: number | undefined): number | undefined {
  if (current == null) {
    return next;
  }
  if (next == null) {
    return current;
  }
  return current + next;
}

function placeToMedal(value: unknown): string | undefined {
  const place = toFiniteNumber(value);
  if (place === 1) {
    return "Gold";
  }
  if (place === 2) {
    return "Silver";
  }
  if (place === 3) {
    return "Bronze";
  }
  return undefined;
}

function plural(value: number, word: string): string {
  return value === 1 ? word : `${word}s`;
}

function formatNumber(value: number, locale: string | undefined): string {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
  }).format(value);
}

function formatRank(value: number, locale: string | undefined): string {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 0,
    useGrouping: false,
  }).format(value);
}

function compact<T>(values: Array<T | false | null | undefined>): T[] {
  return values.filter(Boolean) as T[];
}

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function createSequence(): { next: () => number } {
  let value = 0;
  return {
    next: () => value++,
  };
}

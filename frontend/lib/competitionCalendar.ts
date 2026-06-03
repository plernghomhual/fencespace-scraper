export type CompetitionState = "upcoming" | "active" | "past";

export type CompetitionCalendarFilters = {
  weapon?: string | null;
  category?: string | null;
  country?: string | null;
};

export type CompetitionCalendarEvent = {
  id?: string | number | null;
  title?: string | null;
  name?: string | null;
  startDate: string;
  endDate?: string | null;
  country?: string | null;
  weapon?: string | null;
  category?: string | null;
  status?: string | null;
  url?: string | null;
  icsUrl?: string | null;
  ics_url?: string | null;
  calendarUrl?: string | null;
  calendar_url?: string | null;
};

export type CompetitionTiming = {
  startAt: Date;
  endAt: Date;
  startDateOnly: boolean;
  endDateOnly: boolean;
  dateLabel: string;
};

export type NormalizedCompetitionEvent = {
  id: string;
  title: string;
  country: string;
  weapon: string;
  category: string;
  sourceStatus: string;
  state: CompetitionState;
  countdownLabel: string;
  dateLabel: string;
  startAt: Date;
  endAt: Date;
  timing: CompetitionTiming;
  url?: string;
  icsUrl?: string;
};

const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_LABEL = "TBD";

function isAllValue(value: string | null | undefined): boolean {
  return !value || value.trim() === "" || value.trim().toLowerCase() === "all";
}

function sameFilterValue(candidate: string | null | undefined, filter: string | null | undefined): boolean {
  if (isAllValue(filter)) {
    return true;
  }

  const filterValue = filter?.trim().toLowerCase();
  return Boolean(filterValue) && (candidate ?? "").trim().toLowerCase() === filterValue;
}

function parseDateOnly(value: string, endOfDay: boolean): Date | null {
  const match = DATE_ONLY_RE.exec(value.trim());
  if (!match) {
    return null;
  }

  const year = Number(match[1]);
  const monthIndex = Number(match[2]) - 1;
  const day = Number(match[3]);

  const parsed = endOfDay
    ? new Date(year, monthIndex, day, 23, 59, 59, 999)
    : new Date(year, monthIndex, day, 0, 0, 0, 0);

  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== monthIndex ||
    parsed.getDate() !== day
  ) {
    throw new Error(`Invalid competition date: ${value}`);
  }

  return parsed;
}

function parseCalendarDate(value: string, endOfDay: boolean): { date: Date; dateOnly: boolean } {
  const dateOnly = parseDateOnly(value, endOfDay);
  if (dateOnly) {
    return { date: dateOnly, dateOnly: true };
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`Invalid competition date: ${value}`);
  }

  return { date: parsed, dateOnly: false };
}

function endOfStartDay(startAt: Date): Date {
  return new Date(
    startAt.getFullYear(),
    startAt.getMonth(),
    startAt.getDate(),
    23,
    59,
    59,
    999,
  );
}

function formatDate(date: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatDateRange(startAt: Date, endAt: Date): string {
  const sameDay =
    startAt.getFullYear() === endAt.getFullYear() &&
    startAt.getMonth() === endAt.getMonth() &&
    startAt.getDate() === endAt.getDate();

  if (sameDay) {
    return formatDate(startAt);
  }

  return `${formatDate(startAt)} - ${formatDate(endAt)}`;
}

function calendarDayIndex(date: Date): number {
  return Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY_MS);
}

function calendarDayDiff(from: Date, to: Date): number {
  return calendarDayIndex(to) - calendarDayIndex(from);
}

function normalizeText(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "";
  }

  return String(value).trim();
}

function makeEventId(event: CompetitionCalendarEvent): string {
  const explicitId = normalizeText(event.id);
  if (explicitId) {
    return explicitId;
  }

  return [event.title ?? event.name ?? "competition", event.startDate, event.country, event.weapon]
    .map((part) =>
      normalizeText(part)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, ""),
    )
    .filter(Boolean)
    .join("-");
}

function getEventTitle(event: CompetitionCalendarEvent): string {
  return normalizeText(event.title) || normalizeText(event.name) || "Untitled competition";
}

function getIcsUrl(event: CompetitionCalendarEvent): string | undefined {
  return (
    normalizeText(event.icsUrl) ||
    normalizeText(event.ics_url) ||
    normalizeText(event.calendarUrl) ||
    normalizeText(event.calendar_url) ||
    undefined
  );
}

export function getEventTiming(event: Pick<CompetitionCalendarEvent, "startDate" | "endDate">): CompetitionTiming {
  const start = parseCalendarDate(event.startDate, false);
  const end = event.endDate ? parseCalendarDate(event.endDate, true) : null;
  const endAt = end?.date ?? endOfStartDay(start.date);

  if (endAt.getTime() < start.date.getTime()) {
    throw new Error(`Competition end date is before start date: ${event.startDate} - ${event.endDate}`);
  }

  return {
    startAt: start.date,
    endAt,
    startDateOnly: start.dateOnly,
    endDateOnly: end?.dateOnly ?? false,
    dateLabel: formatDateRange(start.date, endAt),
  };
}

export function getCompetitionState(timing: CompetitionTiming, nowInput: Date | string = new Date()): CompetitionState {
  const now = typeof nowInput === "string" ? new Date(nowInput) : nowInput;

  if (Number.isNaN(now.getTime())) {
    throw new Error(`Invalid reference date: ${String(nowInput)}`);
  }

  if (now.getTime() < timing.startAt.getTime()) {
    return "upcoming";
  }

  if (now.getTime() <= timing.endAt.getTime()) {
    return "active";
  }

  return "past";
}

export function getCountdownLabel(timing: CompetitionTiming, nowInput: Date | string = new Date()): string {
  const now = typeof nowInput === "string" ? new Date(nowInput) : nowInput;
  const state = getCompetitionState(timing, now);

  if (state === "past") {
    return "Completed";
  }

  if (state === "active") {
    const daysUntilEnd = Math.max(0, calendarDayDiff(now, timing.endAt));
    if (daysUntilEnd === 0) {
      return "Ends today";
    }
    if (daysUntilEnd === 1) {
      return "Ends tomorrow";
    }
    return `Ends in ${daysUntilEnd} days`;
  }

  const daysUntilStart = Math.max(0, calendarDayDiff(now, timing.startAt));
  if (daysUntilStart === 0) {
    return "Starts today";
  }
  if (daysUntilStart === 1) {
    return "Starts tomorrow";
  }
  return `Starts in ${daysUntilStart} days`;
}

export function normalizeCompetitionEvent(
  event: CompetitionCalendarEvent,
  nowInput: Date | string = new Date(),
): NormalizedCompetitionEvent {
  const timing = getEventTiming(event);
  const state = getCompetitionState(timing, nowInput);

  return {
    id: makeEventId(event),
    title: getEventTitle(event),
    country: normalizeText(event.country) || DEFAULT_LABEL,
    weapon: normalizeText(event.weapon) || DEFAULT_LABEL,
    category: normalizeText(event.category) || DEFAULT_LABEL,
    sourceStatus: normalizeText(event.status) || DEFAULT_LABEL,
    state,
    countdownLabel: getCountdownLabel(timing, nowInput),
    dateLabel: timing.dateLabel,
    startAt: timing.startAt,
    endAt: timing.endAt,
    timing,
    url: normalizeText(event.url) || undefined,
    icsUrl: getIcsUrl(event),
  };
}

export function filterCompetitions(
  competitions: CompetitionCalendarEvent[],
  filters: CompetitionCalendarFilters,
): CompetitionCalendarEvent[] {
  return competitions.filter(
    (competition) =>
      sameFilterValue(competition.weapon, filters.weapon) &&
      sameFilterValue(competition.category, filters.category) &&
      sameFilterValue(competition.country, filters.country),
  );
}

export function getFilterOptions(competitions: CompetitionCalendarEvent[]): {
  weapons: string[];
  categories: string[];
  countries: string[];
} {
  const collect = (key: "weapon" | "category" | "country"): string[] => {
    const values = new Set<string>();
    for (const competition of competitions) {
      const value = normalizeText(competition[key]);
      if (value) {
        values.add(value);
      }
    }

    return Array.from(values).sort((a, b) => a.localeCompare(b));
  };

  return {
    weapons: collect("weapon"),
    categories: collect("category"),
    countries: collect("country"),
  };
}

export function buildCompetitionCalendar(
  competitions: CompetitionCalendarEvent[],
  options: {
    filters?: CompetitionCalendarFilters;
    now?: Date | string;
  } = {},
): NormalizedCompetitionEvent[] {
  const filtered = filterCompetitions(competitions, options.filters ?? {});

  return filtered
    .map((competition) => normalizeCompetitionEvent(competition, options.now))
    .sort((left, right) => {
      const stateRank: Record<CompetitionState, number> = {
        active: 0,
        upcoming: 1,
        past: 2,
      };
      const rankDiff = stateRank[left.state] - stateRank[right.state];
      if (rankDiff !== 0) {
        return rankDiff;
      }

      if (left.state === "past") {
        return right.startAt.getTime() - left.startAt.getTime();
      }

      return left.startAt.getTime() - right.startAt.getTime();
    });
}

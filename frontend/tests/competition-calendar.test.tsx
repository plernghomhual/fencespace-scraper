import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CompetitionCalendar } from "../components/CompetitionCalendar";
import {
  filterCompetitions,
  getCountdownLabel,
  getEventTiming,
  normalizeCompetitionEvent,
  type CompetitionCalendarEvent,
} from "../lib/competitionCalendar";

const now = new Date(2026, 5, 2, 12, 0, 0);

const events: CompetitionCalendarEvent[] = [
  {
    id: "active-worlds",
    title: "World Championships",
    startDate: "2026-06-01",
    endDate: "2026-06-04",
    country: "Italy",
    weapon: "Epee",
    category: "Senior",
    status: "published",
    icsUrl: "https://example.test/worlds.ics",
  },
  {
    id: "upcoming-juniors",
    title: "Junior Grand Prix",
    startDate: "2026-06-10",
    endDate: "2026-06-11",
    country: "France",
    weapon: "Foil",
    category: "Junior",
    status: "scheduled",
  },
  {
    id: "past-cadet",
    title: "Cadet Circuit",
    startDate: "2026-05-20",
    endDate: "2026-05-21",
    country: "Italy",
    weapon: "Sabre",
    category: "Cadet",
    status: "complete",
  },
];

describe("competition calendar date handling", () => {
  it("normalizes date-only events as local all-day ranges without UTC day shifting", () => {
    const timing = getEventTiming({
      startDate: "2026-03-10",
      endDate: "2026-03-10",
    });

    expect(timing.startAt.getFullYear()).toBe(2026);
    expect(timing.startAt.getMonth()).toBe(2);
    expect(timing.startAt.getDate()).toBe(10);
    expect(timing.startAt.getHours()).toBe(0);
    expect(timing.endAt.getFullYear()).toBe(2026);
    expect(timing.endAt.getMonth()).toBe(2);
    expect(timing.endAt.getDate()).toBe(10);
    expect(timing.endAt.getHours()).toBe(23);
    expect(timing.dateLabel).toBe("Mar 10, 2026");
  });

  it("classifies upcoming, active, and past events without negative countdown labels", () => {
    const active = normalizeCompetitionEvent(events[0], now);
    const upcoming = normalizeCompetitionEvent(events[1], now);
    const past = normalizeCompetitionEvent(events[2], now);

    expect(active.state).toBe("active");
    expect(active.countdownLabel).toBe("Ends in 2 days");
    expect(upcoming.state).toBe("upcoming");
    expect(upcoming.countdownLabel).toBe("Starts in 8 days");
    expect(past.state).toBe("past");
    expect(past.countdownLabel).toBe("Completed");
    expect(getCountdownLabel(past.timing, now)).not.toMatch(/-/);
  });
});

describe("competition filtering", () => {
  it("filters by weapon, category, and country together", () => {
    const filtered = filterCompetitions(events, {
      weapon: "Epee",
      category: "Senior",
      country: "Italy",
    });

    expect(filtered).toHaveLength(1);
    expect(filtered[0].title).toBe("World Championships");
  });

  it("treats empty filter values as all competitions", () => {
    expect(filterCompetitions(events, { weapon: "all", category: "", country: undefined })).toHaveLength(3);
  });
});

describe("CompetitionCalendar", () => {
  it("renders active, upcoming, and past competitions with countdowns and ICS links", () => {
    const html = renderToStaticMarkup(
      createElement(CompetitionCalendar, { competitions: events, now }),
    );

    expect(html).toContain("World Championships");
    expect(html).toContain("Active");
    expect(html).toContain("Ends in 2 days");
    expect(html).toContain('href="https://example.test/worlds.ics"');
    expect(html).toContain("Download calendar for World Championships");
    expect(html).toContain("Junior Grand Prix");
    expect(html).toContain("Upcoming");
    expect(html).toContain("Starts in 8 days");
    expect(html).toContain("Cadet Circuit");
    expect(html).toContain("Past");
    expect(html).toContain("Completed");
  });

  it("filters visible competitions from initial select state", () => {
    const html = renderToStaticMarkup(
      createElement(CompetitionCalendar, {
        competitions: events,
        initialFilters: { weapon: "Epee", category: "Senior", country: "Italy" },
        now,
      }),
    );

    expect(html).toContain("World Championships");
    expect(html).not.toContain("Junior Grand Prix");
    expect(html).not.toContain("Cadet Circuit");
  });

  it("renders empty and error states", () => {
    const emptyHtml = renderToStaticMarkup(
      createElement(CompetitionCalendar, { competitions: [], now }),
    );
    const errorHtml = renderToStaticMarkup(
      createElement(CompetitionCalendar, {
        competitions: [],
        error: "Unable to load competitions.",
        now,
      }),
    );

    expect(emptyHtml).toContain("No competitions match the current filters.");
    expect(errorHtml).toContain("Unable to load competitions.");
    expect(errorHtml).toContain('role="status"');
  });
});

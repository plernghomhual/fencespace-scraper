"use client";

import { useMemo, useState, type CSSProperties } from "react";

import {
  filterTimelineEvents,
  normalizeCareerTimeline,
  type CareerTimelineEvent,
  type CareerTimelineInput,
} from "../lib/careerTimeline";

export interface CareerTimelineProps {
  data: CareerTimelineInput | null | undefined;
  locale?: string;
  className?: string;
  initialWeapon?: string;
  initialCategory?: string;
  emptyMessage?: string;
}

const ALL_VALUE = "__all__";

export function CareerTimeline({
  data,
  locale,
  className,
  initialWeapon,
  initialCategory,
  emptyMessage = "No career timeline data available.",
}: CareerTimelineProps) {
  const [weaponFilter, setWeaponFilter] = useState(initialWeapon ?? ALL_VALUE);
  const [categoryFilter, setCategoryFilter] = useState(initialCategory ?? ALL_VALUE);
  const normalized = useMemo(() => normalizeCareerTimeline(data, { locale }), [data, locale]);

  const selectedWeapon =
    weaponFilter !== ALL_VALUE && normalized.filterOptions.weapons.includes(weaponFilter)
      ? weaponFilter
      : undefined;
  const selectedCategory =
    categoryFilter !== ALL_VALUE && normalized.filterOptions.categories.includes(categoryFilter)
      ? categoryFilter
      : undefined;

  const visibleEvents = useMemo(
    () =>
      filterTimelineEvents(normalized.events, {
        weapon: selectedWeapon,
        category: selectedCategory,
      }),
    [normalized.events, selectedCategory, selectedWeapon],
  );
  const showWeaponFilter = normalized.filterOptions.weapons.length > 1;
  const showCategoryFilter = normalized.filterOptions.categories.length > 1;

  if (normalized.events.length === 0) {
    return (
      <section aria-label="Career timeline" className={className} style={styles.root}>
        <p style={styles.emptyText}>{emptyMessage}</p>
      </section>
    );
  }

  return (
    <section aria-label="Career timeline" className={className} style={styles.root}>
      {(showWeaponFilter || showCategoryFilter) && (
        <div aria-label="Timeline filters" style={styles.filters}>
          {showWeaponFilter && (
            <label style={styles.filterField}>
              <span style={styles.filterLabel}>Weapon</span>
              <select
                aria-label="Filter by weapon"
                onChange={(event) => setWeaponFilter(event.target.value)}
                style={styles.select}
                value={weaponFilter}
              >
                <option value={ALL_VALUE}>All weapons</option>
                {normalized.filterOptions.weapons.map((weapon) => (
                  <option key={weapon} value={weapon}>
                    {weapon}
                  </option>
                ))}
              </select>
            </label>
          )}

          {showCategoryFilter && (
            <label style={styles.filterField}>
              <span style={styles.filterLabel}>Category</span>
              <select
                aria-label="Filter by category"
                onChange={(event) => setCategoryFilter(event.target.value)}
                style={styles.select}
                value={categoryFilter}
              >
                <option value={ALL_VALUE}>All categories</option>
                {normalized.filterOptions.categories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}

      {visibleEvents.length === 0 ? (
        <p style={styles.emptyText}>No career timeline events match the selected filters.</p>
      ) : (
        <ol aria-label="Chronological career timeline" style={styles.timelineList}>
          {visibleEvents.map((event) => (
            <TimelineItem event={event} key={event.id} />
          ))}
        </ol>
      )}
    </section>
  );
}

function TimelineItem({ event }: { event: CareerTimelineEvent }) {
  return (
    <li aria-label={event.ariaLabel} style={styles.timelineItem}>
      <time dateTime={event.dateISO} style={styles.timeLabel}>
        {event.timeLabel}
      </time>
      <article style={styles.eventCard}>
        <div style={styles.eventHeader}>
          <span style={styles.kindBadge}>{kindLabel(event.kind)}</span>
          <h3 style={styles.eventTitle}>{event.title}</h3>
        </div>
        {event.description && <p style={styles.description}>{event.description}</p>}
        {event.details.length > 0 && (
          <ul style={styles.detailList}>
            {event.details.map((detail) => (
              <li key={detail} style={styles.detailItem}>
                {detail}
              </li>
            ))}
          </ul>
        )}
      </article>
    </li>
  );
}

function kindLabel(kind: CareerTimelineEvent["kind"]): string {
  switch (kind) {
    case "country_change":
      return "Country";
    case "ranking_peak":
      return "Ranking";
    case "longevity":
      return "Span";
    case "medal":
      return "Medal";
    case "milestone":
      return "Milestone";
    case "season":
      return "Season";
  }
}

const styles: Record<string, CSSProperties> = {
  root: {
    color: "#172026",
    display: "grid",
    gap: "1rem",
    minWidth: 0,
  },
  filters: {
    alignItems: "end",
    display: "flex",
    flexWrap: "wrap",
    gap: "0.75rem",
  },
  filterField: {
    display: "grid",
    gap: "0.35rem",
    minWidth: "min(100%, 11rem)",
  },
  filterLabel: {
    color: "#5d6972",
    fontSize: "0.78rem",
    fontWeight: 600,
  },
  select: {
    background: "#ffffff",
    border: "1px solid #cfd8df",
    borderRadius: "0.5rem",
    color: "#172026",
    font: "inherit",
    minHeight: "2.35rem",
    padding: "0.4rem 0.65rem",
  },
  timelineList: {
    display: "grid",
    gap: "0.75rem",
    listStyle: "none",
    margin: 0,
    padding: 0,
  },
  timelineItem: {
    alignItems: "start",
    display: "grid",
    gap: "0.75rem",
    gridTemplateColumns: "minmax(6.5rem, 8rem) minmax(0, 1fr)",
    minWidth: 0,
  },
  timeLabel: {
    color: "#46525b",
    fontSize: "0.88rem",
    fontVariantNumeric: "tabular-nums",
    lineHeight: 1.35,
    paddingTop: "0.55rem",
    wordBreak: "break-word",
  },
  eventCard: {
    background: "#ffffff",
    border: "1px solid #d8e0e6",
    borderLeft: "0.28rem solid #3f7f93",
    borderRadius: "0.5rem",
    display: "grid",
    gap: "0.5rem",
    minWidth: 0,
    padding: "0.75rem 0.85rem",
  },
  eventHeader: {
    alignItems: "center",
    display: "flex",
    flexWrap: "wrap",
    gap: "0.5rem",
    minWidth: 0,
  },
  kindBadge: {
    background: "#e7f2ef",
    borderRadius: "999px",
    color: "#235668",
    fontSize: "0.72rem",
    fontWeight: 700,
    lineHeight: 1,
    padding: "0.32rem 0.48rem",
  },
  eventTitle: {
    fontSize: "1rem",
    fontWeight: 700,
    lineHeight: 1.25,
    margin: 0,
    minWidth: 0,
    overflowWrap: "anywhere",
  },
  description: {
    color: "#46525b",
    fontSize: "0.92rem",
    lineHeight: 1.45,
    margin: 0,
    overflowWrap: "anywhere",
  },
  detailList: {
    display: "flex",
    flexWrap: "wrap",
    gap: "0.35rem",
    listStyle: "none",
    margin: 0,
    padding: 0,
  },
  detailItem: {
    background: "#f4f7f9",
    border: "1px solid #dde5ea",
    borderRadius: "999px",
    color: "#35424a",
    fontSize: "0.78rem",
    lineHeight: 1.25,
    padding: "0.25rem 0.45rem",
  },
  emptyText: {
    color: "#5d6972",
    margin: 0,
  },
};

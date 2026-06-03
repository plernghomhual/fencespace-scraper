"use client";

import { useMemo, useState } from "react";

import {
  buildCompetitionCalendar,
  getFilterOptions,
  type CompetitionCalendarEvent,
  type CompetitionCalendarFilters,
  type CompetitionState,
} from "../lib/competitionCalendar";

type CompetitionCalendarProps = {
  competitions: CompetitionCalendarEvent[];
  now?: Date | string;
  error?: string | Error | null;
  isLoading?: boolean;
  initialFilters?: CompetitionCalendarFilters;
  title?: string;
};

const ALL_VALUE = "all";

function statusLabel(state: CompetitionState): string {
  if (state === "active") {
    return "Active";
  }
  if (state === "past") {
    return "Past";
  }
  return "Upcoming";
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="competition-calendar__filter">
      <span>{label}</span>
      <select aria-label={label} value={value || ALL_VALUE} onChange={(event) => onChange(event.target.value)}>
        <option value={ALL_VALUE}>All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

export function CompetitionCalendar({
  competitions,
  now,
  error,
  isLoading = false,
  initialFilters,
  title = "Competition calendar",
}: CompetitionCalendarProps) {
  const [filters, setFilters] = useState<CompetitionCalendarFilters>({
    weapon: initialFilters?.weapon ?? ALL_VALUE,
    category: initialFilters?.category ?? ALL_VALUE,
    country: initialFilters?.country ?? ALL_VALUE,
  });

  const filterOptions = useMemo(() => getFilterOptions(competitions), [competitions]);
  const normalizedCompetitions = useMemo(
    () => buildCompetitionCalendar(competitions, { filters, now }),
    [competitions, filters, now],
  );

  const updateFilter = (key: keyof CompetitionCalendarFilters, value: string) => {
    setFilters((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const errorMessage = typeof error === "string" ? error : error?.message;

  return (
    <section className="competition-calendar" aria-label={title}>
      <div className="competition-calendar__header">
        <div>
          <h2>{title}</h2>
          <p>{normalizedCompetitions.length} competitions</p>
        </div>
        <div className="competition-calendar__filters" aria-label="Competition filters">
          <FilterSelect
            label="Weapon"
            value={filters.weapon ?? ALL_VALUE}
            options={filterOptions.weapons}
            onChange={(value) => updateFilter("weapon", value)}
          />
          <FilterSelect
            label="Category"
            value={filters.category ?? ALL_VALUE}
            options={filterOptions.categories}
            onChange={(value) => updateFilter("category", value)}
          />
          <FilterSelect
            label="Country"
            value={filters.country ?? ALL_VALUE}
            options={filterOptions.countries}
            onChange={(value) => updateFilter("country", value)}
          />
        </div>
      </div>

      {errorMessage ? <div className="competition-calendar__state competition-calendar__state--error" role="status">{errorMessage}</div> : null}

      {isLoading ? <div className="competition-calendar__state" role="status">Loading competitions...</div> : null}

      {!isLoading && !errorMessage && normalizedCompetitions.length === 0 ? (
        <div className="competition-calendar__state">No competitions match the current filters.</div>
      ) : null}

      {!isLoading && !errorMessage && normalizedCompetitions.length > 0 ? (
        <div className="competition-calendar__list" role="list">
          {normalizedCompetitions.map((competition) => (
            <article
              key={competition.id}
              className={`competition-calendar__item competition-calendar__item--${competition.state}`}
              data-testid={`competition-${competition.id}`}
              role="listitem"
            >
              <div className="competition-calendar__primary">
                <span className={`competition-calendar__badge competition-calendar__badge--${competition.state}`}>
                  {statusLabel(competition.state)}
                </span>
                <div>
                  {competition.url ? (
                    <a className="competition-calendar__title" href={competition.url}>
                      {competition.title}
                    </a>
                  ) : (
                    <h3 className="competition-calendar__title">{competition.title}</h3>
                  )}
                  <p>{competition.dateLabel}</p>
                </div>
              </div>

              <dl className="competition-calendar__meta" aria-label={`${competition.title} details`}>
                <div>
                  <dt>Country</dt>
                  <dd>{competition.country}</dd>
                </div>
                <div>
                  <dt>Weapon</dt>
                  <dd>{competition.weapon}</dd>
                </div>
                <div>
                  <dt>Category</dt>
                  <dd>{competition.category}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{competition.sourceStatus}</dd>
                </div>
              </dl>

              <div className="competition-calendar__actions">
                <strong>{competition.countdownLabel}</strong>
                {competition.icsUrl ? (
                  <a href={competition.icsUrl} className="competition-calendar__ics" aria-label={`Download calendar for ${competition.title}`}>
                    ICS
                  </a>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : null}

      <style>{`
        .competition-calendar {
          color: #172033;
          display: grid;
          gap: 16px;
          width: 100%;
        }

        .competition-calendar__header {
          align-items: end;
          display: grid;
          gap: 14px;
          grid-template-columns: minmax(0, 1fr);
        }

        .competition-calendar h2,
        .competition-calendar h3,
        .competition-calendar p {
          margin: 0;
        }

        .competition-calendar h2 {
          font-size: 1.25rem;
          font-weight: 700;
          line-height: 1.25;
        }

        .competition-calendar__header p,
        .competition-calendar__primary p {
          color: #647084;
          font-size: 0.875rem;
          line-height: 1.35;
          margin-top: 4px;
        }

        .competition-calendar__filters {
          display: grid;
          gap: 8px;
          grid-template-columns: 1fr;
        }

        .competition-calendar__filter {
          display: grid;
          gap: 4px;
        }

        .competition-calendar__filter span,
        .competition-calendar__meta dt {
          color: #6d7688;
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0;
          text-transform: uppercase;
        }

        .competition-calendar__filter select {
          appearance: none;
          background: #ffffff;
          border: 1px solid #c9d1df;
          border-radius: 6px;
          color: #172033;
          font: inherit;
          min-height: 38px;
          padding: 7px 30px 7px 10px;
          width: 100%;
        }

        .competition-calendar__state {
          background: #f6f8fb;
          border: 1px solid #d9e0ea;
          border-radius: 8px;
          color: #475367;
          padding: 18px;
        }

        .competition-calendar__state--error {
          background: #fff4f2;
          border-color: #f0b8ad;
          color: #8f2f21;
        }

        .competition-calendar__list {
          border: 1px solid #d9e0ea;
          border-radius: 8px;
          overflow: hidden;
        }

        .competition-calendar__item {
          align-items: center;
          background: #ffffff;
          display: grid;
          gap: 12px;
          grid-template-columns: minmax(0, 1fr);
          padding: 14px;
        }

        .competition-calendar__item + .competition-calendar__item {
          border-top: 1px solid #e6ebf2;
        }

        .competition-calendar__item--active {
          background: #f4fbf8;
        }

        .competition-calendar__item--past {
          background: #fafbfc;
        }

        .competition-calendar__primary {
          align-items: start;
          display: grid;
          gap: 10px;
          grid-template-columns: auto minmax(0, 1fr);
          min-width: 0;
        }

        .competition-calendar__title {
          color: #172033;
          display: block;
          font-size: 0.98rem;
          font-weight: 700;
          line-height: 1.25;
          overflow-wrap: anywhere;
          text-decoration: none;
        }

        .competition-calendar__badge {
          border-radius: 6px;
          display: inline-flex;
          font-size: 0.75rem;
          font-weight: 700;
          line-height: 1;
          padding: 6px 8px;
          white-space: nowrap;
        }

        .competition-calendar__badge--active {
          background: #dff5e9;
          color: #17633a;
        }

        .competition-calendar__badge--upcoming {
          background: #e8f0ff;
          color: #2850a7;
        }

        .competition-calendar__badge--past {
          background: #eceff4;
          color: #556174;
        }

        .competition-calendar__meta {
          display: grid;
          gap: 8px;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          margin: 0;
        }

        .competition-calendar__meta div {
          min-width: 0;
        }

        .competition-calendar__meta dd {
          color: #253149;
          font-size: 0.88rem;
          font-weight: 600;
          margin: 2px 0 0;
          overflow-wrap: anywhere;
        }

        .competition-calendar__actions {
          align-items: center;
          display: flex;
          gap: 10px;
          justify-content: space-between;
        }

        .competition-calendar__actions strong {
          color: #172033;
          font-size: 0.92rem;
        }

        .competition-calendar__ics {
          border: 1px solid #b9c5d6;
          border-radius: 6px;
          color: #1f4f9d;
          font-size: 0.82rem;
          font-weight: 700;
          padding: 7px 9px;
          text-decoration: none;
        }

        @media (min-width: 700px) {
          .competition-calendar__header {
            grid-template-columns: minmax(180px, 1fr) minmax(420px, 1.6fr);
          }

          .competition-calendar__filters {
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }

          .competition-calendar__item {
            grid-template-columns: minmax(230px, 1.5fr) minmax(280px, 1.4fr) minmax(120px, 0.7fr);
            padding: 12px 14px;
          }

          .competition-calendar__meta {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }

          .competition-calendar__actions {
            justify-content: end;
          }
        }
      `}</style>
    </section>
  );
}

"use client";

import { createElement, useMemo, useState, type CSSProperties } from "react";

import {
  normalizeCountryMedalRows,
  projectCountryPoint,
  type CountryMedalDatum,
  type CountryMedalInputRow,
} from "../lib/countryMap";

export type CountryMedalHeatmapProps = {
  rows: readonly CountryMedalInputRow[];
  title?: string;
  description?: string;
  className?: string;
};

const DETAILS_ID = "country-medal-heatmap-details";
const h = createElement;

function medalLabel(count: number): string {
  return count === 1 ? "1 medal" : `${count} medals`;
}

function markerSize(total: number, maxTotal: number): number {
  if (maxTotal <= 0) {
    return 18;
  }
  return Math.round(18 + (total / maxTotal) * 22);
}

function MedalBreakdown({ country }: { country: CountryMedalDatum }) {
  return h(
    "dl",
    {
      "aria-label": `${country.name} medal breakdown`,
      className: "country-medal-heatmap__breakdown",
    },
    [
      ["Gold", country.gold],
      ["Silver", country.silver],
      ["Bronze", country.bronze],
      ["Total", country.total],
    ].map(([label, value]) =>
      h("div", { key: label }, h("dt", null, label), h("dd", null, value)),
    ),
  );
}

function CountryMedalHeatmapStyles() {
  return h("style", null, `
    .country-medal-heatmap {
      color: #162033;
      display: grid;
      gap: 18px;
      width: 100%;
    }

    .country-medal-heatmap h2,
    .country-medal-heatmap h3,
    .country-medal-heatmap p {
      margin: 0;
    }

    .country-medal-heatmap__header {
      align-items: end;
      display: flex;
      gap: 12px;
      justify-content: space-between;
    }

    .country-medal-heatmap__header h2 {
      font-size: 1.25rem;
      font-weight: 700;
      line-height: 1.25;
    }

    .country-medal-heatmap__header p,
    .country-medal-heatmap__details p {
      color: #627086;
      font-size: 0.9rem;
      line-height: 1.4;
      margin-top: 4px;
    }

    .country-medal-heatmap__header strong {
      background: #172033;
      border-radius: 6px;
      color: #ffffff;
      font-size: 0.82rem;
      padding: 7px 10px;
      white-space: nowrap;
    }

    .country-medal-heatmap__layout {
      display: grid;
      gap: 14px;
      grid-template-columns: minmax(0, 1fr);
    }

    .country-medal-heatmap__map {
      aspect-ratio: 16 / 9;
      background:
        linear-gradient(90deg, rgba(28, 55, 88, 0.07) 1px, transparent 1px),
        linear-gradient(0deg, rgba(28, 55, 88, 0.07) 1px, transparent 1px),
        #eef3f7;
      background-size: 12.5% 25%, 12.5% 25%, auto;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      min-height: 250px;
      overflow: hidden;
      position: relative;
    }

    .country-medal-heatmap__equator,
    .country-medal-heatmap__prime {
      background: rgba(77, 91, 111, 0.18);
      position: absolute;
    }

    .country-medal-heatmap__equator {
      height: 1px;
      left: 0;
      top: 50%;
      width: 100%;
    }

    .country-medal-heatmap__prime {
      height: 100%;
      left: 50%;
      top: 0;
      width: 1px;
    }

    .country-medal-heatmap__marker {
      align-items: center;
      background: #bd5d1f;
      border: 2px solid #ffffff;
      border-radius: 999px;
      box-shadow: 0 6px 14px rgba(111, 57, 23, 0.25);
      color: #ffffff;
      cursor: pointer;
      display: inline-flex;
      font-size: 0.58rem;
      font-weight: 800;
      justify-content: center;
      line-height: 1;
      min-height: 18px;
      min-width: 18px;
      padding: 0;
      position: absolute;
      transform: translate(-50%, -50%);
      transition: transform 150ms ease, box-shadow 150ms ease;
    }

    .country-medal-heatmap__marker:hover,
    .country-medal-heatmap__marker:focus-visible {
      box-shadow: 0 0 0 4px rgba(189, 93, 31, 0.2), 0 8px 18px rgba(111, 57, 23, 0.3);
      outline: none;
      transform: translate(-50%, -50%) scale(1.08);
      z-index: 2;
    }

    .country-medal-heatmap__marker span {
      max-width: 4ch;
      overflow: hidden;
      text-overflow: clip;
    }

    .country-medal-heatmap__details,
    .country-medal-heatmap__missing,
    .country-medal-heatmap__state {
      background: #ffffff;
      border: 1px solid #d6dde8;
      border-radius: 8px;
      padding: 16px;
    }

    .country-medal-heatmap__state {
      color: #596679;
    }

    .country-medal-heatmap__details-header {
      align-items: start;
      display: flex;
      gap: 12px;
      justify-content: space-between;
    }

    .country-medal-heatmap__details-header span {
      color: #7a4a21;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    .country-medal-heatmap__details-header h3,
    .country-medal-heatmap__missing h3 {
      font-size: 1rem;
      line-height: 1.3;
    }

    .country-medal-heatmap__details-header button {
      background: #f4f6f9;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      color: #253043;
      cursor: pointer;
      font: inherit;
      font-size: 0.8rem;
      padding: 6px 9px;
    }

    .country-medal-heatmap__breakdown {
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin: 14px 0 0;
    }

    .country-medal-heatmap__breakdown div {
      background: #f7f9fc;
      border-radius: 6px;
      padding: 10px;
    }

    .country-medal-heatmap__breakdown dt,
    .country-medal-heatmap__table th {
      color: #5e6b80;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    .country-medal-heatmap__breakdown dd {
      color: #172033;
      font-size: 1.15rem;
      font-weight: 800;
      margin: 4px 0 0;
    }

    .country-medal-heatmap__missing {
      display: grid;
      gap: 10px;
    }

    .country-medal-heatmap__missing ul {
      display: grid;
      gap: 8px;
      list-style: none;
      margin: 0;
      padding: 0;
    }

    .country-medal-heatmap__missing li {
      align-items: center;
      display: flex;
      gap: 10px;
      justify-content: space-between;
    }

    .country-medal-heatmap__missing strong {
      color: #596679;
      font-size: 0.86rem;
    }

    .country-medal-heatmap__table-wrap {
      border: 1px solid #d6dde8;
      border-radius: 8px;
      overflow-x: auto;
    }

    .country-medal-heatmap__table {
      border-collapse: collapse;
      min-width: 640px;
      width: 100%;
    }

    .country-medal-heatmap__table th,
    .country-medal-heatmap__table td {
      border-bottom: 1px solid #e2e7ef;
      padding: 10px 12px;
      text-align: left;
      white-space: nowrap;
    }

    .country-medal-heatmap__table tbody tr:last-child th,
    .country-medal-heatmap__table tbody tr:last-child td {
      border-bottom: 0;
    }

    @media (min-width: 840px) {
      .country-medal-heatmap__layout {
        grid-template-columns: minmax(0, 1.7fr) minmax(260px, 0.7fr);
      }
    }
  `);
}

export function CountryMedalHeatmap({
  rows,
  title = "Country medal heatmap",
  description = "Medal totals by country with gold, silver, and bronze breakdowns.",
  className,
}: CountryMedalHeatmapProps) {
  const countries = useMemo(() => normalizeCountryMedalRows(rows), [rows]);
  const points = useMemo(
    () => countries.map((country) => projectCountryPoint(country)).filter((point): point is NonNullable<typeof point> => Boolean(point)),
    [countries],
  );
  const missingCoordinates = useMemo(() => countries.filter((country) => !country.hasCoordinates), [countries]);
  const maxTotal = countries[0]?.total ?? 0;
  const [activeCode, setActiveCode] = useState<string | null>(null);
  const activeCountry = countries.find((country) => country.code === activeCode) ?? null;
  const sectionClass = ["country-medal-heatmap", className].filter(Boolean).join(" ");

  if (countries.length === 0) {
    return h(
      "section",
      { "aria-label": title, className: sectionClass },
      h(
        "div",
        { className: "country-medal-heatmap__header" },
        h("div", null, h("h2", null, title), h("p", null, description)),
      ),
      h("div", { className: "country-medal-heatmap__state", role: "status" }, "No country medal data available."),
      h(CountryMedalHeatmapStyles),
    );
  }

  return h(
    "section",
    { "aria-label": title, className: sectionClass },
    h(
      "div",
      { className: "country-medal-heatmap__header" },
      h("div", null, h("h2", null, title), h("p", null, description)),
      h("strong", null, medalLabel(countries.reduce((sum, country) => sum + country.total, 0))),
    ),
    h(
      "div",
      { className: "country-medal-heatmap__layout" },
      h(
        "div",
        {
          "aria-label": `Country medal map with ${points.length} coordinate-backed countries and ${missingCoordinates.length} countries without coordinates`,
          className: "country-medal-heatmap__map",
          role: "img",
        },
        h("div", { "aria-hidden": true, className: "country-medal-heatmap__equator" }),
        h("div", { "aria-hidden": true, className: "country-medal-heatmap__prime" }),
        points.map((country) => {
          const size = markerSize(country.total, maxTotal);
          const style: CSSProperties = {
            height: `${size}px`,
            left: `${country.x}%`,
            top: `${country.y}%`,
            width: `${size}px`,
          };

          return h(
            "button",
            {
              "aria-controls": DETAILS_ID,
              "aria-label": `${country.name}: ${medalLabel(country.total)} (${country.gold} gold, ${country.silver} silver, ${country.bronze} bronze)`,
              className: "country-medal-heatmap__marker",
              key: country.code,
              onClick: () => setActiveCode(country.code),
              onFocus: () => setActiveCode(country.code),
              onMouseEnter: () => setActiveCode(country.code),
              style,
              type: "button",
            },
            h("span", null, country.code),
          );
        }),
      ),
      h(
        "aside",
        {
          "aria-label": activeCountry ? `${activeCountry.name} medal details` : "Country medal details",
          className: "country-medal-heatmap__details",
          id: DETAILS_ID,
          role: activeCountry ? "dialog" : "status",
        },
        activeCountry
          ? [
              h(
                "div",
                { className: "country-medal-heatmap__details-header", key: "header" },
                h("div", null, h("span", null, activeCountry.code), h("h3", null, activeCountry.name)),
                h(
                  "button",
                  {
                    "aria-label": "Close medal details",
                    onClick: () => setActiveCode(null),
                    type: "button",
                  },
                  "Close",
                ),
              ),
              h(MedalBreakdown, { country: activeCountry, key: "breakdown" }),
            ]
          : h("p", null, "Select a country marker to inspect medal totals."),
      ),
    ),
    missingCoordinates.length > 0
      ? h(
          "section",
          {
            "aria-labelledby": "country-medal-heatmap-missing-title",
            className: "country-medal-heatmap__missing",
          },
          h("h3", { id: "country-medal-heatmap-missing-title" }, "Countries without map coordinates"),
          h(
            "ul",
            null,
            missingCoordinates.map((country) =>
              h(
                "li",
                { key: country.code },
                h("span", null, country.name),
                h("strong", null, `${country.code} - ${medalLabel(country.total)}`),
              ),
            ),
          ),
        )
      : null,
    h(
      "div",
      { className: "country-medal-heatmap__table-wrap" },
      h(
        "table",
        { "aria-label": "Country medal totals", className: "country-medal-heatmap__table" },
        h(
          "thead",
          null,
          h(
            "tr",
            null,
            ["Country", "Code", "Gold", "Silver", "Bronze", "Total", "Map status"].map((heading) =>
              h("th", { key: heading, scope: "col" }, heading),
            ),
          ),
        ),
        h(
          "tbody",
          null,
          countries.map((country) =>
            h(
              "tr",
              { key: country.code },
              h("th", { scope: "row" }, country.name),
              h("td", null, country.code),
              h("td", null, country.gold),
              h("td", null, country.silver),
              h("td", null, country.bronze),
              h("td", null, country.total),
              h("td", null, country.hasCoordinates ? "Mapped" : "No coordinates"),
            ),
          ),
        ),
      ),
    ),
    h(CountryMedalHeatmapStyles),
  );
}

export default CountryMedalHeatmap;

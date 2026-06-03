"use client";

import { createElement, useMemo } from "react";

import {
  buildSparklineLayout,
  formatRankingSeriesLabel,
  normalizeRankingHistory,
  sparklinePath,
  type RankingHistoryRow,
} from "../lib/rankingSparkline";

export type RankingSparklineProps = {
  data: RankingHistoryRow[];
  weapon?: string | null;
  category?: string | null;
  includeMissingSeasons?: boolean;
  width?: number;
  height?: number;
  padding?: number;
  color?: string;
  mutedColor?: string;
  strokeWidth?: number;
  pointRadius?: number;
  className?: string;
  ariaLabel?: string;
};

const DEFAULT_COLOR = "#2563eb";
const DEFAULT_MUTED_COLOR = "#d5dce8";
const DEFAULT_STROKE_WIDTH = 2;
const DEFAULT_POINT_RADIUS = 2.75;
const h = createElement;

export function RankingSparkline({
  data,
  weapon,
  category,
  includeMissingSeasons = false,
  width = 96,
  height = 32,
  padding = 4,
  color = DEFAULT_COLOR,
  mutedColor = DEFAULT_MUTED_COLOR,
  strokeWidth = DEFAULT_STROKE_WIDTH,
  pointRadius = DEFAULT_POINT_RADIUS,
  className,
  ariaLabel,
}: RankingSparklineProps) {
  const series = useMemo(
    () => normalizeRankingHistory(data, { weapon, category, includeMissingSeasons })[0] ?? null,
    [data, weapon, category, includeMissingSeasons],
  );
  const layout = useMemo(
    () => buildSparklineLayout(series?.points ?? [], { width, height, padding }),
    [series, width, height, padding],
  );
  const chartLabel = ariaLabel ?? formatRankingSeriesLabel(series);
  const classNames = ["ranking-sparkline", className].filter(Boolean).join(" ");
  const paths = layout.segments
    .filter((segment) => segment.length > 1)
    .map((segment) =>
      h("path", {
        "aria-hidden": "true",
        "data-testid": "ranking-sparkline-path",
        d: sparklinePath(segment),
        fill: "none",
        stroke: color,
        strokeLinecap: "round",
        strokeLinejoin: "round",
        strokeWidth,
      }),
    );
  const markers = layout.points.map((point, index) =>
    h(
      "circle",
      {
        "aria-label": point.label,
        "data-testid": `ranking-sparkline-point-${index}`,
        cx: point.x,
        cy: point.y,
        fill: color,
        r: pointRadius,
        tabIndex: 0,
      },
      h("title", null, point.label),
    ),
  );

  if (!series || layout.points.length === 0) {
    return h(
      "span",
      {
        "aria-label": chartLabel,
        className: `${classNames} ranking-sparkline--empty`,
        role: "img",
      },
      h("span", { "aria-hidden": "true" }, "No ranking history"),
      h(
        "style",
        null,
        `
          .ranking-sparkline {
            align-items: center;
            color: #6b7280;
            display: inline-flex;
            font-size: 0.75rem;
            line-height: 1;
            min-height: ${Math.max(1, height)}px;
            min-width: ${Math.max(1, width)}px;
          }
        `,
      ),
    );
  }

  return h(
    "span",
    { className: classNames },
    h(
      "svg",
      {
        "aria-label": chartLabel,
        "data-testid": "ranking-sparkline-svg",
        height: layout.height,
        role: "img",
        viewBox: `0 0 ${layout.width} ${layout.height}`,
        width: layout.width,
      },
      h("title", null, chartLabel),
      h("line", {
        "aria-hidden": "true",
        stroke: mutedColor,
        strokeLinecap: "round",
        strokeWidth: Math.max(1, strokeWidth / 2),
        x1: layout.padding,
        x2: layout.width - layout.padding,
        y1: layout.height / 2,
        y2: layout.height / 2,
      }),
      ...paths,
      ...markers,
    ),
    h(
      "style",
      null,
      `
        .ranking-sparkline {
          color: ${color};
          display: inline-flex;
          line-height: 0;
          max-width: 100%;
          vertical-align: middle;
        }

        .ranking-sparkline svg {
          display: block;
          flex: 0 0 auto;
          max-width: 100%;
          overflow: visible;
        }

        .ranking-sparkline circle:focus {
          outline: 2px solid ${color};
          outline-offset: 2px;
        }
      `,
    ),
  );
}

export default RankingSparkline;

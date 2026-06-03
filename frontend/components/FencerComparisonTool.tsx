import React, { useEffect, useMemo, useState } from "react";

import {
  normalizeFencerComparison,
} from "../lib/fencerComparison";
import type {
  FencerComparisonInput,
  FencerComparisonStatObject,
  HeadToHeadStats,
  NormalizedFencerStats,
} from "../lib/fencerComparison";

export type FencerStatsLoader = (
  fencerId: string,
) => Promise<FencerComparisonStatObject | null | undefined>;

export type FencerComparisonToolProps = {
  left?: FencerComparisonInput;
  right?: FencerComparisonInput;
  leftId?: string | null;
  rightId?: string | null;
  h2hRows?: HeadToHeadStats[];
  loadFencerStats?: FencerStatsLoader;
  publicApiBaseUrl?: string;
  className?: string;
};

type Side = "left" | "right";

type LoadedSide = {
  id: string | null;
  fencer: FencerComparisonStatObject | null;
  loading: boolean;
  missing: boolean;
  error: string | null;
};

const EMPTY_SIDE: LoadedSide = {
  id: null,
  fencer: null,
  loading: false,
  missing: false,
  error: null,
};

const h = React.createElement;

function fragment(...children: React.ReactNode[]): React.ReactElement {
  return h(React.Fragment, null, ...children);
}

function isIdInput(value: FencerComparisonInput): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function typedInput(value: FencerComparisonInput): FencerComparisonStatObject | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as FencerComparisonStatObject)
    : null;
}

function buildPublicComparisonUrl(id: string, publicApiBaseUrl = ""): string {
  const base = publicApiBaseUrl.replace(/\/$/, "");
  return `${base}/api/fencers/${encodeURIComponent(id)}/comparison`;
}

export async function fetchPublicFencerComparisonStats(
  fencerId: string,
  publicApiBaseUrl?: string,
): Promise<FencerComparisonStatObject | null> {
  if (typeof fetch !== "function") {
    return null;
  }

  const response = await fetch(buildPublicComparisonUrl(fencerId, publicApiBaseUrl), {
    credentials: "omit",
  });
  if (!response.ok) {
    return null;
  }

  const payload = await response.json();
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  return (
    (record.fencer as FencerComparisonStatObject | undefined) ??
    (record.data as FencerComparisonStatObject | undefined) ??
    (payload as FencerComparisonStatObject)
  );
}

function useLoadedFencer(
  side: Side,
  input: FencerComparisonInput,
  loader: FencerStatsLoader,
): LoadedSide {
  const requestedId = isIdInput(input) ? input.trim() : null;
  const [state, setState] = useState<LoadedSide>(EMPTY_SIDE);

  useEffect(() => {
    let active = true;
    if (!requestedId) {
      setState(EMPTY_SIDE);
      return () => {
        active = false;
      };
    }

    setState({
      id: requestedId,
      fencer: null,
      loading: true,
      missing: false,
      error: null,
    });

    loader(requestedId)
      .then((fencer) => {
        if (!active) {
          return;
        }
        setState({
          id: requestedId,
          fencer: fencer ?? null,
          loading: false,
          missing: !fencer,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setState({
          id: requestedId,
          fencer: null,
          loading: false,
          missing: true,
          error:
            error instanceof Error
              ? error.message
              : `${side} fencer could not be loaded`,
        });
      });

    return () => {
      active = false;
    };
  }, [loader, requestedId, side]);

  return state;
}

function sideInput(
  directInput: FencerComparisonInput,
  idInput: string | null | undefined,
): FencerComparisonInput {
  return directInput ?? idInput ?? null;
}

function displaySide(
  label: Side,
  fencer: NormalizedFencerStats | null,
  loadState: LoadedSide,
  hasInput: boolean,
): React.ReactNode {
  if (fencer) {
    return fragment(
      h("strong", { className: "fs-comparison__name" }, fencer.displayName),
      h(
        "span",
        { className: "fs-comparison__meta" },
        [fencer.country, fencer.primaryWeapon].filter(Boolean).join(" | ") ||
          "Profile loaded",
      ),
    );
  }

  if (loadState.loading) {
    return h("span", { className: "fs-comparison__placeholder" }, "Loading fencer...");
  }

  if (loadState.missing) {
    return fragment(
      h("strong", { className: "fs-comparison__name" }, "Fencer not found"),
      h(
        "span",
        { className: "fs-comparison__meta" },
        loadState.error ?? loadState.id ?? "Missing profile",
      ),
    );
  }

  return fragment(
    h("strong", { className: "fs-comparison__name" }, "No fencer selected"),
    h(
      "span",
      { className: "fs-comparison__meta" },
      hasInput ? `${label} profile unavailable` : "Select a fencer",
    ),
  );
}

function cellClassName(winner?: "left" | "right" | "tie", side?: Side): string {
  if (winner === "tie") {
    return "fs-comparison__cell fs-comparison__cell--tie";
  }
  if (winner && winner === side) {
    return "fs-comparison__cell fs-comparison__cell--leader";
  }
  return "fs-comparison__cell";
}

export default function FencerComparisonTool({
  left,
  right,
  leftId,
  rightId,
  h2hRows = [],
  loadFencerStats,
  publicApiBaseUrl,
  className,
}: FencerComparisonToolProps) {
  const leftInput = sideInput(left, leftId);
  const rightInput = sideInput(right, rightId);
  const loader = useMemo<FencerStatsLoader>(
    () =>
      loadFencerStats ??
      ((id: string) => fetchPublicFencerComparisonStats(id, publicApiBaseUrl)),
    [loadFencerStats, publicApiBaseUrl],
  );
  const loadedLeft = useLoadedFencer("left", leftInput, loader);
  const loadedRight = useLoadedFencer("right", rightInput, loader);
  const resolvedLeft = typedInput(leftInput) ?? loadedLeft.fencer;
  const resolvedRight = typedInput(rightInput) ?? loadedRight.fencer;
  const comparison = useMemo(
    () =>
      normalizeFencerComparison({
        left: resolvedLeft,
        right: resolvedRight,
        h2hRows,
      }),
    [h2hRows, resolvedLeft, resolvedRight],
  );
  const hasAnyInput = Boolean(leftInput || rightInput);
  const loading = loadedLeft.loading || loadedRight.loading;

  return h(
    "div",
    {
      className: ["fs-comparison", className].filter(Boolean).join(" "),
      "aria-busy": loading,
    },
    h(
      "header",
      { className: "fs-comparison__header" },
      h(
        "div",
        { className: "fs-comparison__side", "data-side": "left" },
        displaySide("left", comparison.left, loadedLeft, Boolean(leftInput)),
      ),
      h(
        "div",
        { className: "fs-comparison__title" },
        h("h2", null, "Fencer comparison"),
        !hasAnyInput ? h("p", null, "Select two fencers to compare") : null,
        comparison.isSameFencer
          ? h(
              "div",
              { className: "fs-comparison__warning", role: "status" },
              h("strong", null, "Same fencer selected"),
              h("span", null, "Choose two different fencers for a meaningful comparison."),
            )
          : null,
      ),
      h(
        "div",
        { className: "fs-comparison__side", "data-side": "right" },
        displaySide("right", comparison.right, loadedRight, Boolean(rightInput)),
      ),
    ),
    h(
      "div",
      { className: "fs-comparison__sections" },
      comparison.sections.map((section) =>
        h(
          "section",
          { className: "fs-comparison__section", key: section.id },
          h("h3", null, section.title),
          h(
            "table",
            { className: "fs-comparison__table" },
            h(
              "tbody",
              null,
              section.rows.map((comparisonRow) =>
                h(
                  "tr",
                  { key: comparisonRow.key },
                  h("th", { scope: "row" }, comparisonRow.label),
                  h(
                    "td",
                    { className: cellClassName(comparisonRow.winner, "left") },
                    comparisonRow.left.display,
                  ),
                  h(
                    "td",
                    { className: cellClassName(comparisonRow.winner, "right") },
                    comparisonRow.right.display,
                  ),
                ),
              ),
            ),
          ),
          section.id === "h2h" &&
            section.rows[0]?.summary &&
            section.rows[0].summary !== "No bouts"
            ? h("div", { className: "fs-comparison__summary" }, section.rows[0].summary)
            : null,
        ),
      ),
    ),
  );
}

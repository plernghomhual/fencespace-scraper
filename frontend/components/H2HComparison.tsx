import React, { useCallback, useEffect, useMemo, useState } from "react";

export type Fencer = {
  id: string;
  name?: string | null;
  country?: string | null;
  weapon?: string | null;
  category?: string | null;
  world_rank?: number | null;
  fie_id?: string | null;
};

export type HeadToHeadRow = {
  fencer_a_id: string;
  fencer_b_id: string;
  weapon: string;
  a_wins: number;
  b_wins: number;
  a_touches: number;
  b_touches: number;
  bouts_total: number;
  last_meeting_date?: string | null;
  last_winner_id?: string | null;
};

export type HeadToHeadApiResponse = {
  fencer_a: string;
  fencer_b: string;
  data: HeadToHeadRow[];
};

type JsonFetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

type H2HComparisonProps = {
  apiBase?: string;
  apiKey?: string;
  debounceMs?: number;
  initialFencerAId?: string | null;
  initialFencerBId?: string | null;
  fetcher?: JsonFetcher;
  onSelectionChange?: (fencerAId: string | null, fencerBId: string | null) => void;
};

type SearchPayload = {
  data?: unknown;
};

type FencerProfilePayload = {
  profile?: unknown;
};

type LoadStatus = "idle" | "loading" | "ready" | "same" | "empty" | "error";

type ComparisonStats = {
  leftWins: number;
  rightWins: number;
  leftTouches: number;
  rightTouches: number;
  boutsTotal: number;
  lastMeeting: string | null;
  weaponRows: WeaponStats[];
  recentBouts: RecentBout[];
};

type WeaponStats = {
  weapon: string;
  leftWins: number;
  rightWins: number;
  leftTouches: number;
  rightTouches: number;
  boutsTotal: number;
  lastMeeting: string | null;
  lastWinnerId: string | null;
};

type RecentBout = {
  weapon: string;
  date: string;
  winnerName: string;
  loserName: string;
};

class ApiRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNullableString(value: unknown): value is string | null | undefined {
  return value === null || value === undefined || typeof value === "string";
}

export function isFencer(value: unknown): value is Fencer {
  if (!isObject(value) || !isString(value.id)) {
    return false;
  }

  return (
    isNullableString(value.name) &&
    isNullableString(value.country) &&
    isNullableString(value.weapon) &&
    isNullableString(value.category)
  );
}

function isHeadToHeadRow(value: unknown): value is HeadToHeadRow {
  if (!isObject(value)) {
    return false;
  }

  return (
    isString(value.fencer_a_id) &&
    isString(value.fencer_b_id) &&
    isString(value.weapon) &&
    isNumber(value.a_wins) &&
    isNumber(value.b_wins) &&
    isNumber(value.a_touches) &&
    isNumber(value.b_touches) &&
    isNumber(value.bouts_total) &&
    isNullableString(value.last_meeting_date) &&
    isNullableString(value.last_winner_id)
  );
}

export function isHeadToHeadApiResponse(value: unknown): value is HeadToHeadApiResponse {
  if (!isObject(value) || !isString(value.fencer_a) || !isString(value.fencer_b) || !Array.isArray(value.data)) {
    return false;
  }

  return value.data.every(isHeadToHeadRow);
}

function apiUrl(apiBase: string | undefined, path: string, params?: URLSearchParams): string {
  const query = params?.toString();

  if (!apiBase) {
    return query ? `${path}?${query}` : path;
  }

  const url = new URL(path, apiBase.endsWith("/") ? apiBase : `${apiBase}/`);
  if (query) {
    url.search = query;
  }
  return url.toString();
}

function authHeaders(apiKey?: string): HeadersInit | undefined {
  return apiKey ? { "X-API-Key": apiKey } : undefined;
}

function isAbortError(error: unknown): boolean {
  return isObject(error) && error.name === "AbortError";
}

function fencerTitle(fencer: Fencer | null): string {
  return fencer?.name || fencer?.id || "Unknown fencer";
}

function fencerMeta(fencer: Fencer): string {
  return [fencer.country, fencer.weapon, fencer.category].filter(Boolean).join(" / ");
}

function aggregateRows(rows: HeadToHeadRow[], left: Fencer, right: Fencer): ComparisonStats {
  const weaponRows = rows
    .map((row) => {
      const leftIsCanonicalA = row.fencer_a_id === left.id;
      return {
        weapon: row.weapon,
        leftWins: leftIsCanonicalA ? row.a_wins : row.b_wins,
        rightWins: leftIsCanonicalA ? row.b_wins : row.a_wins,
        leftTouches: leftIsCanonicalA ? row.a_touches : row.b_touches,
        rightTouches: leftIsCanonicalA ? row.b_touches : row.a_touches,
        boutsTotal: row.bouts_total,
        lastMeeting: row.last_meeting_date || null,
        lastWinnerId: row.last_winner_id || null,
      };
    })
    .sort((a, b) => a.weapon.localeCompare(b.weapon));

  const totals = weaponRows.reduce(
    (acc, row) => {
      acc.leftWins += row.leftWins;
      acc.rightWins += row.rightWins;
      acc.leftTouches += row.leftTouches;
      acc.rightTouches += row.rightTouches;
      acc.boutsTotal += row.boutsTotal;
      if (row.lastMeeting && (!acc.lastMeeting || row.lastMeeting > acc.lastMeeting)) {
        acc.lastMeeting = row.lastMeeting;
      }
      return acc;
    },
    {
      leftWins: 0,
      rightWins: 0,
      leftTouches: 0,
      rightTouches: 0,
      boutsTotal: 0,
      lastMeeting: null as string | null,
    }
  );

  const recentBouts = weaponRows
    .filter((row) => row.lastMeeting)
    .sort((a, b) => String(b.lastMeeting).localeCompare(String(a.lastMeeting)))
    .slice(0, 5)
    .map((row) => {
      const leftWon = row.lastWinnerId === left.id;
      const rightWon = row.lastWinnerId === right.id;
      return {
        weapon: row.weapon,
        date: row.lastMeeting || "",
        winnerName: leftWon ? fencerTitle(left) : rightWon ? fencerTitle(right) : "Unknown winner",
        loserName: leftWon ? fencerTitle(right) : rightWon ? fencerTitle(left) : "opponent",
      };
    });

  return {
    ...totals,
    weaponRows,
    recentBouts,
  };
}

function SearchControl({
  label,
  selected,
  missingMessage,
  apiBase,
  apiKey,
  debounceMs,
  fetcher,
  onSelect,
}: {
  label: string;
  selected: Fencer | null;
  missingMessage: string | null;
  apiBase?: string;
  apiKey?: string;
  debounceMs: number;
  fetcher: JsonFetcher;
  onSelect: (fencer: Fencer | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Fencer[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [searchedQuery, setSearchedQuery] = useState("");
  const inputId = `${label.toLowerCase().replace(/\s+/g, "-")}-search`;

  useEffect(() => {
    if (selected) {
      setQuery(fencerTitle(selected));
      setResults([]);
    }
  }, [selected?.id]);

  useEffect(() => {
    const trimmed = query.trim();
    if (selected && trimmed === fencerTitle(selected)) {
      return;
    }
    if (trimmed.length < 2) {
      setResults([]);
      setSearchedQuery("");
      setStatus("idle");
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setStatus("loading");
      try {
        const params = new URLSearchParams({ name: trimmed, limit: "8" });
        const response = await fetcher(apiUrl(apiBase, "/fencer/search", params), {
          headers: authHeaders(apiKey),
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new ApiRequestError(response.status, "Fencer search failed");
        }

        const payload = (await response.json()) as SearchPayload;
        const nextResults = Array.isArray(payload.data) ? payload.data.filter(isFencer) : [];
        setResults(nextResults);
        setSearchedQuery(trimmed);
        setStatus("idle");
      } catch (error) {
        if (!isAbortError(error)) {
          setResults([]);
          setSearchedQuery(trimmed);
          setStatus("error");
        }
      }
    }, debounceMs);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [apiBase, apiKey, debounceMs, fetcher, query, selected]);

  const clear = () => {
    setQuery("");
    setResults([]);
    setSearchedQuery("");
    setStatus("idle");
    onSelect(null);
  };

  return (
    <div className="fencer-control">
      <div className="control-label-row">
        <label htmlFor={inputId}>{label}</label>
        {(query || selected) && (
          <button type="button" className="clear-button" onClick={clear}>
            Clear
          </button>
        )}
      </div>
      <input
        id={inputId}
        aria-label={label}
        value={query}
        placeholder="Search by fencer name"
        autoComplete="off"
        onChange={(event) => {
          setQuery(event.target.value);
          if (selected) {
            onSelect(null);
          }
        }}
      />
      {missingMessage && <p className="field-error">{missingMessage}</p>}
      {status === "loading" && <p className="field-hint">Searching...</p>}
      {status === "error" && <p className="field-error">Could not search fencers.</p>}
      {status === "idle" && searchedQuery && results.length === 0 && !selected && (
        <p className="field-hint">No matching fencers.</p>
      )}
      {results.length > 0 && (
        <div className="search-results" role="listbox" aria-label={`${label} search results`}>
          {results.map((fencer) => (
            <button
              type="button"
              key={fencer.id}
              role="option"
              className="result-option"
              onClick={() => onSelect(fencer)}
            >
              <span>Select {fencerTitle(fencer)}</span>
              <small>{fencerMeta(fencer) || fencer.id}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function FencerStatPanel({
  fencer,
  wins,
  losses,
  touches,
  testId,
}: {
  fencer: Fencer;
  wins: number;
  losses: number;
  touches: number;
  testId: string;
}) {
  return (
    <section className="fencer-card" data-testid={testId}>
      <div>
        <h3>{fencerTitle(fencer)}</h3>
        <p>{fencerMeta(fencer) || "Public fencer profile"}</p>
      </div>
      <dl>
        <div>
          <dt>Wins</dt>
          <dd>{wins}</dd>
        </div>
        <div>
          <dt>Losses</dt>
          <dd>{losses}</dd>
        </div>
        <div>
          <dt>Touches</dt>
          <dd>{touches}</dd>
        </div>
      </dl>
    </section>
  );
}

export default function H2HComparison({
  apiBase,
  apiKey,
  debounceMs = 300,
  initialFencerAId,
  initialFencerBId,
  fetcher = fetch,
  onSelectionChange,
}: H2HComparisonProps) {
  const [leftFencer, setLeftFencer] = useState<Fencer | null>(null);
  const [rightFencer, setRightFencer] = useState<Fencer | null>(null);
  const [leftMissing, setLeftMissing] = useState<string | null>(null);
  const [rightMissing, setRightMissing] = useState<string | null>(null);
  const [rows, setRows] = useState<HeadToHeadRow[]>([]);
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchJson = useCallback(
    async (path: string, signal?: AbortSignal) => {
      const response = await fetcher(apiUrl(apiBase, path), {
        headers: authHeaders(apiKey),
        signal,
      });
      if (!response.ok) {
        throw new ApiRequestError(response.status, "API request failed");
      }
      return response.json() as Promise<unknown>;
    },
    [apiBase, apiKey, fetcher]
  );

  const loadInitialFencer = useCallback(
    (
      id: string | null | undefined,
      setFencer: (fencer: Fencer | null) => void,
      setMissing: (message: string | null) => void
    ) => {
      if (!id) {
        setFencer(null);
        setMissing(null);
        return undefined;
      }

      const controller = new AbortController();
      setMissing(null);

      fetchJson(`/fencer/${encodeURIComponent(id)}`, controller.signal)
        .then((payload) => {
          const profile = isObject(payload) ? (payload as FencerProfilePayload).profile : undefined;
          if (isFencer(profile)) {
            setFencer(profile);
          } else {
            setFencer(null);
            setMissing("Selected fencer was not found.");
          }
        })
        .catch((error) => {
          if (isAbortError(error)) {
            return;
          }
          setFencer(null);
          setMissing(error instanceof ApiRequestError && error.status === 404 ? "Selected fencer was not found." : "Could not load selected fencer.");
        });

      return () => controller.abort();
    },
    [fetchJson]
  );

  useEffect(
    () => loadInitialFencer(initialFencerAId, setLeftFencer, setLeftMissing),
    [initialFencerAId, loadInitialFencer]
  );

  useEffect(
    () => loadInitialFencer(initialFencerBId, setRightFencer, setRightMissing),
    [initialFencerBId, loadInitialFencer]
  );

  const selectLeft = (fencer: Fencer | null) => {
    setLeftMissing(null);
    setLeftFencer(fencer);
    onSelectionChange?.(fencer?.id ?? null, rightFencer?.id ?? null);
  };

  const selectRight = (fencer: Fencer | null) => {
    setRightMissing(null);
    setRightFencer(fencer);
    onSelectionChange?.(leftFencer?.id ?? null, fencer?.id ?? null);
  };

  useEffect(() => {
    setRows([]);
    setErrorMessage(null);

    if (!leftFencer || !rightFencer) {
      setStatus("idle");
      return;
    }

    if (leftFencer.id === rightFencer.id) {
      setStatus("same");
      return;
    }

    const controller = new AbortController();
    setStatus("loading");

    fetchJson(`/h2h/${encodeURIComponent(leftFencer.id)}/${encodeURIComponent(rightFencer.id)}`, controller.signal)
      .then((payload) => {
        if (!isHeadToHeadApiResponse(payload)) {
          throw new Error("Unexpected H2H API response");
        }
        setRows(payload.data);
        setStatus(payload.data.length > 0 ? "ready" : "empty");
      })
      .catch((error) => {
        if (isAbortError(error)) {
          return;
        }
        setRows([]);
        setStatus("error");
        setErrorMessage(error instanceof ApiRequestError && error.status === 404 ? "No head-to-head record yet." : "Could not load head-to-head data. Try again.");
      });

    return () => controller.abort();
  }, [fetchJson, leftFencer, rightFencer]);

  const stats = useMemo(() => {
    if (!leftFencer || !rightFencer || rows.length === 0) {
      return null;
    }
    return aggregateRows(rows, leftFencer, rightFencer);
  }, [leftFencer, rightFencer, rows]);

  return (
    <div className="h2h-shell">
      <header className="h2h-header">
        <p>Head-to-head comparison</p>
        <h1>Compare fencers</h1>
      </header>

      <section className="selector-grid" aria-label="Select fencers">
        <SearchControl
          label="Fencer A"
          selected={leftFencer}
          missingMessage={leftMissing}
          apiBase={apiBase}
          apiKey={apiKey}
          debounceMs={debounceMs}
          fetcher={fetcher}
          onSelect={selectLeft}
        />
        <SearchControl
          label="Fencer B"
          selected={rightFencer}
          missingMessage={rightMissing}
          apiBase={apiBase}
          apiKey={apiKey}
          debounceMs={debounceMs}
          fetcher={fetcher}
          onSelect={selectRight}
        />
      </section>

      {leftFencer && rightFencer && (
        <section className="comparison-title" aria-live="polite">
          <h2>
            {fencerTitle(leftFencer)} vs {fencerTitle(rightFencer)}
          </h2>
        </section>
      )}

      {!leftFencer || !rightFencer ? (
        <section className="empty-state">
          <h2>Select two fencers to compare.</h2>
          <p>Search uses public fencer names. Deep links store only fencer IDs.</p>
        </section>
      ) : null}

      {status === "same" && (
        <section className="message-state error" role="alert">
          Choose two different fencers.
        </section>
      )}

      {status === "loading" && <section className="message-state">Loading head-to-head data...</section>}

      {status === "empty" && <section className="message-state">No head-to-head record yet.</section>}

      {status === "error" && (
        <section className="message-state error" role="alert">
          {errorMessage || "Could not load head-to-head data. Try again."}
        </section>
      )}

      {stats && leftFencer && rightFencer && status === "ready" && (
        <section className="stats-stack">
          <div className="summary-row">
            <FencerStatPanel
              fencer={leftFencer}
              wins={stats.leftWins}
              losses={stats.rightWins}
              touches={stats.leftTouches}
              testId="left-fencer-stats"
            />
            <div className="summary-center">
              <span>{stats.boutsTotal}</span>
              <p>Total bouts</p>
              <strong>Last meeting</strong>
              <p>{stats.lastMeeting || "Unknown"}</p>
            </div>
            <FencerStatPanel
              fencer={rightFencer}
              wins={stats.rightWins}
              losses={stats.leftWins}
              touches={stats.rightTouches}
              testId="right-fencer-stats"
            />
          </div>

          <section className="data-section">
            <h3>Weapon split</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Weapon</th>
                    <th scope="col">{fencerTitle(leftFencer)} wins</th>
                    <th scope="col">{fencerTitle(rightFencer)} wins</th>
                    <th scope="col">Touches</th>
                    <th scope="col">Bouts</th>
                    <th scope="col">Last meeting</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.weaponRows.map((row) => (
                    <tr key={row.weapon}>
                      <td>{row.weapon}</td>
                      <td>{row.leftWins}</td>
                      <td>{row.rightWins}</td>
                      <td>
                        {row.leftTouches}-{row.rightTouches}
                      </td>
                      <td>{row.boutsTotal}</td>
                      <td>{row.lastMeeting || "Unknown"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="data-section">
            <h3>Recent bouts</h3>
            {stats.recentBouts.length > 0 ? (
              <ol className="recent-list">
                {stats.recentBouts.map((bout) => (
                  <li key={`${bout.weapon}-${bout.date}`}>
                    <span>{bout.date}</span>
                    <strong>{bout.weapon}</strong>
                    <p>
                      {bout.winnerName} defeated {bout.loserName}
                    </p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="field-hint">No dated bouts are available for this matchup.</p>
            )}
          </section>
        </section>
      )}

      <style jsx>{`
        .h2h-shell {
          color: #17202a;
          margin: 0 auto;
          max-width: 1120px;
          padding: 32px 20px 48px;
        }

        .h2h-header {
          margin-bottom: 24px;
        }

        .h2h-header p {
          color: #556170;
          font-size: 0.9rem;
          margin: 0 0 6px;
          text-transform: uppercase;
        }

        .h2h-header h1 {
          font-size: clamp(2rem, 4vw, 3.2rem);
          line-height: 1;
          margin: 0;
        }

        .selector-grid {
          display: grid;
          gap: 16px;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          margin-bottom: 24px;
        }

        .fencer-control,
        .fencer-card,
        .message-state,
        .empty-state,
        .data-section,
        .summary-center {
          background: #ffffff;
          border: 1px solid #d7dde5;
          border-radius: 8px;
        }

        .fencer-control {
          min-height: 142px;
          padding: 16px;
          position: relative;
        }

        .control-label-row {
          align-items: center;
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
        }

        label {
          color: #263241;
          font-weight: 700;
        }

        input {
          border: 1px solid #bac4d1;
          border-radius: 6px;
          font-size: 1rem;
          padding: 10px 12px;
          width: 100%;
        }

        button {
          cursor: pointer;
          font: inherit;
        }

        .clear-button {
          background: transparent;
          border: 0;
          color: #2563a8;
          font-size: 0.9rem;
          padding: 4px;
        }

        .search-results {
          background: #ffffff;
          border: 1px solid #d7dde5;
          border-radius: 8px;
          box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
          left: 16px;
          max-height: 270px;
          overflow-y: auto;
          position: absolute;
          right: 16px;
          top: 88px;
          z-index: 5;
        }

        .result-option {
          align-items: flex-start;
          background: transparent;
          border: 0;
          border-bottom: 1px solid #edf1f5;
          display: flex;
          flex-direction: column;
          gap: 4px;
          padding: 11px 12px;
          text-align: left;
          width: 100%;
        }

        .result-option:hover,
        .result-option:focus {
          background: #f2f7fb;
        }

        .result-option span {
          font-weight: 700;
        }

        .result-option small,
        .field-hint,
        .field-error,
        .empty-state p,
        .fencer-card p,
        .summary-center p {
          color: #5c6877;
        }

        .field-error {
          color: #a32929;
          margin: 8px 0 0;
        }

        .field-hint {
          margin: 8px 0 0;
        }

        .comparison-title h2 {
          font-size: 1.5rem;
          line-height: 1.2;
          margin: 0 0 16px;
        }

        .empty-state,
        .message-state {
          padding: 20px;
        }

        .empty-state h2 {
          font-size: 1.1rem;
          margin: 0 0 6px;
        }

        .empty-state p {
          margin: 0;
        }

        .message-state {
          margin-top: 16px;
        }

        .message-state.error {
          border-color: #e0a4a4;
          color: #8d1f1f;
        }

        .stats-stack {
          display: grid;
          gap: 18px;
        }

        .summary-row {
          align-items: stretch;
          display: grid;
          gap: 14px;
          grid-template-columns: minmax(0, 1fr) 180px minmax(0, 1fr);
        }

        .fencer-card {
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          min-height: 184px;
          padding: 18px;
        }

        .fencer-card h3 {
          font-size: 1.25rem;
          margin: 0 0 4px;
        }

        .fencer-card p {
          margin: 0;
        }

        dl {
          display: grid;
          gap: 10px;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          margin: 18px 0 0;
        }

        dt {
          color: #647181;
          font-size: 0.78rem;
          text-transform: uppercase;
        }

        dd {
          font-size: 1.7rem;
          font-weight: 800;
          margin: 2px 0 0;
        }

        .summary-center {
          align-items: center;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding: 18px;
          text-align: center;
        }

        .summary-center span {
          font-size: 2.4rem;
          font-weight: 800;
        }

        .summary-center strong {
          margin-top: 14px;
        }

        .summary-center p {
          margin: 4px 0 0;
        }

        .data-section {
          padding: 18px;
        }

        .data-section h3 {
          margin: 0 0 12px;
        }

        .table-wrap {
          overflow-x: auto;
        }

        table {
          border-collapse: collapse;
          min-width: 760px;
          width: 100%;
        }

        th,
        td {
          border-bottom: 1px solid #e5e9ef;
          padding: 10px 8px;
          text-align: left;
        }

        th {
          color: #566273;
          font-size: 0.82rem;
          text-transform: uppercase;
        }

        .recent-list {
          display: grid;
          gap: 10px;
          list-style: none;
          margin: 0;
          padding: 0;
        }

        .recent-list li {
          border: 1px solid #e5e9ef;
          border-radius: 8px;
          padding: 12px;
        }

        .recent-list span {
          color: #5c6877;
          font-size: 0.9rem;
        }

        .recent-list strong {
          display: inline-block;
          margin-left: 8px;
        }

        .recent-list p {
          margin: 5px 0 0;
        }

        @media (max-width: 760px) {
          .selector-grid,
          .summary-row {
            grid-template-columns: 1fr;
          }

          .summary-center {
            min-height: 140px;
          }
        }
      `}</style>
    </div>
  );
}

import type { CSSProperties } from "react";

import {
  type BracketBout,
  type BracketSide,
  type RawBracketRow,
  normalizeBracket,
} from "../lib/brackets";

export type BracketVisualizerProps = {
  bouts?: RawBracketRow[] | null;
  title?: string;
  error?: string | Error | null;
  emptyMessage?: string;
  className?: string;
};

const rootStyle: CSSProperties = {
  color: "#172026",
  fontFamily:
    "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif",
};

const headingStyle: CSSProperties = {
  margin: "0 0 14px",
  fontSize: "1.125rem",
  fontWeight: 700,
  letterSpacing: 0,
};

const scrollStyle: CSSProperties = {
  overflowX: "auto",
  overflowY: "hidden",
  WebkitOverflowScrolling: "touch",
  paddingBottom: 8,
};

const columnsStyle: CSSProperties = {
  display: "grid",
  gap: 16,
  alignItems: "start",
  minWidth: 760,
};

const roundStyle: CSSProperties = {
  minWidth: 220,
};

const roundHeadingStyle: CSSProperties = {
  margin: "0 0 10px",
  fontSize: "0.8125rem",
  fontWeight: 700,
  letterSpacing: 0,
  textTransform: "uppercase",
  color: "#4b5b63",
};

const matchListStyle: CSSProperties = {
  display: "grid",
  gap: 12,
};

const cardStyle: CSSProperties = {
  border: "1px solid #d7dee2",
  borderRadius: 8,
  background: "#ffffff",
  boxShadow: "0 1px 2px rgba(23, 32, 38, 0.08)",
  outlineOffset: 3,
  overflow: "hidden",
};

const metaStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 8,
  padding: "8px 10px",
  borderBottom: "1px solid #e8edf0",
  color: "#5c6970",
  fontSize: "0.75rem",
  fontWeight: 600,
};

const sideStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "34px minmax(96px, 1fr) 34px",
  alignItems: "center",
  gap: 8,
  minHeight: 38,
  padding: "8px 10px",
};

const winnerSideStyle: CSSProperties = {
  ...sideStyle,
  background: "#edf8f2",
};

const seedStyle: CSSProperties = {
  color: "#6c7a82",
  fontSize: "0.75rem",
  fontVariantNumeric: "tabular-nums",
};

const nameStyle: CSSProperties = {
  minWidth: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  fontSize: "0.875rem",
  fontWeight: 650,
};

const byeNameStyle: CSSProperties = {
  ...nameStyle,
  color: "#7b878d",
  fontStyle: "italic",
};

const scoreStyle: CSSProperties = {
  justifySelf: "end",
  fontSize: "0.875rem",
  fontWeight: 750,
  fontVariantNumeric: "tabular-nums",
};

const statusStyle: CSSProperties = {
  borderRadius: 999,
  padding: "2px 8px",
  background: "#eff4f6",
  color: "#445159",
  fontSize: "0.6875rem",
  fontWeight: 700,
  textTransform: "uppercase",
  whiteSpace: "nowrap",
};

const winnerLabelStyle: CSSProperties = {
  display: "block",
  marginTop: 2,
  color: "#157347",
  fontSize: "0.6875rem",
  fontWeight: 700,
  textTransform: "uppercase",
};

const stateStyle: CSSProperties = {
  border: "1px solid #d7dee2",
  borderRadius: 8,
  padding: 16,
  background: "#f7f9fa",
  color: "#445159",
};

function scoreText(side: BracketSide): string {
  if (side.isBye) {
    return "";
  }
  return side.score === null ? "TBD" : String(side.score);
}

function statusLabel(status: BracketBout["status"]): string {
  if (status === "bye") {
    return "Advance";
  }
  if (status === "complete") {
    return "Complete";
  }
  return "Pending";
}

function boutLabel(bout: BracketBout): string {
  const [sideA, sideB] = bout.sides;
  const labelPrefix = `${bout.roundName} bout ${bout.boutOrder}`;

  if (bout.status === "bye") {
    const advancing = sideA.isBye ? sideB.name : sideA.name;
    return `${labelPrefix}: ${advancing} advances by bye`;
  }

  if (bout.status === "complete") {
    const winner = sideA.isWinner ? sideA : sideB.isWinner ? sideB : null;
    const loser = winner === sideA ? sideB : sideA;
    if (winner) {
      return `${labelPrefix}: ${winner.name} defeated ${loser.name}, ${sideA.score} to ${sideB.score}`;
    }
  }

  return `${labelPrefix}: ${sideA.name} versus ${sideB.name}, pending`;
}

function MatchSide({ side }: { side: BracketSide }) {
  return (
    <div style={side.isWinner ? winnerSideStyle : sideStyle}>
      <span style={seedStyle}>{side.seed === null ? "" : side.seed}</span>
      <span style={side.isBye ? byeNameStyle : nameStyle} title={side.name}>
        {side.name}
        {side.isWinner ? <span style={winnerLabelStyle}>Winner</span> : null}
      </span>
      <span style={scoreStyle}>{scoreText(side)}</span>
    </div>
  );
}

function MatchCard({ bout }: { bout: BracketBout }) {
  return (
    <article aria-label={boutLabel(bout)} role="group" tabIndex={0} style={cardStyle}>
      <div style={metaStyle}>
        <span>Bout {bout.boutOrder}</span>
        <span style={statusStyle}>{statusLabel(bout.status)}</span>
      </div>
      <MatchSide side={bout.sides[0]} />
      <MatchSide side={bout.sides[1]} />
    </article>
  );
}

export function BracketVisualizer({
  bouts,
  title = "Direct Elimination Bracket",
  error,
  emptyMessage = "No bracket data available.",
  className,
}: BracketVisualizerProps) {
  if (error) {
    return (
      <section className={className} style={rootStyle}>
        <div role="alert" style={stateStyle}>
          {typeof error === "string" ? error : error.message}
        </div>
      </section>
    );
  }

  const bracket = normalizeBracket(bouts);
  if (bracket.totalBouts === 0) {
    return (
      <section className={className} style={rootStyle} aria-label={title}>
        <p style={stateStyle}>{emptyMessage}</p>
      </section>
    );
  }

  const minWidth = Math.max(760, bracket.rounds.length * 252);

  return (
    <section className={className} style={rootStyle} aria-label={title}>
      <h2 style={headingStyle}>{title}</h2>
      <div
        aria-label="Direct elimination bracket"
        data-testid="bracket-scroll"
        style={scrollStyle}
      >
        <div
          data-testid="bracket-columns"
          style={{
            ...columnsStyle,
            gridTemplateColumns: `repeat(${bracket.rounds.length}, minmax(220px, 1fr))`,
            minWidth,
          }}
        >
          {bracket.rounds.map((round) => (
            <section key={round.id} style={roundStyle} aria-labelledby={`${round.id}-heading`}>
              <h3 id={`${round.id}-heading`} style={roundHeadingStyle}>
                {round.name}
              </h3>
              <div role="list" style={matchListStyle}>
                {round.bouts.map((bout) => (
                  <div role="listitem" key={bout.id}>
                    <MatchCard bout={bout} />
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </section>
  );
}

export default BracketVisualizer;

import "@testing-library/jest-dom/vitest";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BracketVisualizer } from "../components/BracketVisualizer";
import { normalizeBracket } from "../lib/brackets";

const fullDeRows = [
  {
    id: "t8-1",
    round_name: "Table of 8",
    round_order: 1,
    bout_order: 1,
    fencer_a_id: "fencer-ada",
    fencer_a_name: "Ada Lee",
    fencer_a_seed: 1,
    fencer_b_id: "fencer-nina",
    fencer_b_name: "Nina Park",
    fencer_b_seed: 8,
    score_a: 15,
    score_b: 6,
    winner_id: "fencer-ada",
  },
  {
    id: "t8-2",
    round_name: "Table of 8",
    round_order: 1,
    bout_order: 2,
    fencer_a_id: "fencer-maya",
    fencer_a_name: "Maya Chen",
    fencer_a_seed: 4,
    fencer_b_id: "fencer-zoe",
    fencer_b_name: "Zoe Ruiz",
    fencer_b_seed: 5,
    score_a: 12,
    score_b: 15,
    winner_id: "fencer-zoe",
  },
  {
    id: "t8-3",
    round_name: "Table of 8",
    round_order: 1,
    bout_order: 3,
    fencer_a_id: "fencer-bea",
    fencer_a_name: "Bea Smith",
    fencer_a_seed: 2,
    fencer_b_id: "fencer-ivy",
    fencer_b_name: "Ivy Stone",
    fencer_b_seed: 7,
    score_a: 15,
    score_b: 14,
    winner_id: "fencer-bea",
  },
  {
    id: "t8-4",
    round_name: "Table of 8",
    round_order: 1,
    bout_order: 4,
    fencer_a_id: "fencer-lena",
    fencer_a_name: "Lena Ortiz",
    fencer_a_seed: 3,
    fencer_b_id: "fencer-uma",
    fencer_b_name: "Uma Patel",
    fencer_b_seed: 6,
    score_a: 15,
    score_b: 11,
    winner_id: "fencer-lena",
  },
  {
    id: "sf-1",
    round_name: "Semi-Finals",
    round_order: 2,
    bout_order: 1,
    fencer_a_id: "fencer-ada",
    fencer_a_name: "Ada Lee",
    fencer_a_seed: 1,
    fencer_b_id: "fencer-zoe",
    fencer_b_name: "Zoe Ruiz",
    fencer_b_seed: 5,
    score_a: 15,
    score_b: 9,
    winner_id: "fencer-ada",
  },
  {
    id: "sf-2",
    round_name: "Semi-Finals",
    round_order: 2,
    bout_order: 2,
    fencer_a_id: "fencer-bea",
    fencer_a_name: "Bea Smith",
    fencer_a_seed: 2,
    fencer_b_id: "fencer-lena",
    fencer_b_name: "Lena Ortiz",
    fencer_b_seed: 3,
    score_a: 15,
    score_b: 13,
    winner_id: "fencer-bea",
  },
  {
    id: "final",
    round_name: "Final",
    round_order: 3,
    bout_order: 1,
    fencer_a_id: "fencer-ada",
    fencer_a_name: "Ada Lee",
    fencer_a_seed: 1,
    fencer_b_id: "fencer-bea",
    fencer_b_name: "Bea Smith",
    fencer_b_seed: 2,
    score_a: 15,
    score_b: 12,
    winner_id: "fencer-ada",
  },
];

const byeAndIncompleteRows = [
  {
    id: "bye-1",
    round_name: "Table of 16",
    round_order: 1,
    bout_order: 1,
    seed_a: 1,
    fencer_a: "fencer-ada",
    fencer_a_name: "Ada Lee",
    seed_b: 16,
    is_bye: true,
    winner: "fencer-ada",
  },
  {
    id: "pending-1",
    round_name: "Table of 16",
    round_order: 1,
    bout_order: 2,
    seed_a: 8,
    fencer_a: "fencer-ivy",
    fencer_a_name: "Ivy Stone",
    seed_b: 9,
    fencer_b: "fencer-zoe",
    fencer_b_name: "Zoe Ruiz",
    score_a: null,
    score_b: null,
    winner: null,
  },
];

describe("normalizeBracket", () => {
  it("groups and sorts full direct-elimination rows without leaking raw DB quirks", () => {
    const bracket = normalizeBracket([...fullDeRows].reverse());

    expect(bracket.rounds.map((round) => round.name)).toEqual([
      "Table of 8",
      "Semi-Finals",
      "Final",
    ]);
    expect(bracket.rounds[0].bouts.map((bout) => bout.id)).toEqual([
      "t8-1",
      "t8-2",
      "t8-3",
      "t8-4",
    ]);
    expect(bracket.rounds[2].bouts[0].sides[0]).toMatchObject({
      id: "fencer-ada",
      name: "Ada Lee",
      seed: 1,
      score: 15,
      isWinner: true,
    });
  });
});

describe("BracketVisualizer", () => {
  it("renders a full direct-elimination bracket", () => {
    render(<BracketVisualizer bouts={fullDeRows} title="Senior Women's Foil DE" />);

    expect(screen.getByText("Senior Women's Foil DE")).toBeInTheDocument();
    expect(screen.getByText("Table of 8")).toBeInTheDocument();
    expect(screen.getByText("Semi-Finals")).toBeInTheDocument();
    expect(screen.getByText("Final")).toBeInTheDocument();

    const final = screen.getByLabelText(/Final bout 1: Ada Lee defeated Bea Smith, 15 to 12/i);
    expect(within(final).getByText("Ada Lee")).toBeInTheDocument();
    expect(within(final).getByText("Bea Smith")).toBeInTheDocument();
    expect(within(final).getByText("15")).toBeInTheDocument();
    expect(within(final).getByText("12")).toBeInTheDocument();
    expect(within(final).getByText("Winner")).toBeInTheDocument();
  });

  it("renders byes and incomplete bouts without missing-score crashes", () => {
    render(<BracketVisualizer bouts={byeAndIncompleteRows} />);

    const bye = screen.getByLabelText(/Table of 16 bout 1: Ada Lee advances by bye/i);
    expect(within(bye).getByText("BYE")).toBeInTheDocument();
    expect(within(bye).getByText("Advance")).toBeInTheDocument();

    const pending = screen.getByLabelText(
      /Table of 16 bout 2: Ivy Stone versus Zoe Ruiz, pending/i,
    );
    expect(within(pending).getAllByText("Pending").length).toBeGreaterThan(0);
    expect(within(pending).getAllByText("TBD").length).toBeGreaterThan(0);
  });

  it("uses keyboard-focusable, labelled match cards", () => {
    render(<BracketVisualizer bouts={fullDeRows} />);

    const cards = screen.getAllByLabelText(/bout/i);
    expect(cards).toHaveLength(7);
    expect(cards[0]).toHaveAttribute("role", "group");
    expect(cards[0]).toHaveAccessibleName(/Table of 8 bout 1/i);
    expect(cards[0]).toHaveAttribute("tabindex", "0");

    cards[0].focus();
    expect(cards[0]).toHaveFocus();
  });

  it("keeps mobile layouts in a horizontal overflow region", () => {
    render(<BracketVisualizer bouts={fullDeRows} />);

    const scroller = screen.getByTestId("bracket-scroll");
    const columns = screen.getByTestId("bracket-columns");

    expect(scroller).toHaveStyle({ overflowX: "auto" });
    expect(scroller).toHaveAttribute("aria-label", "Direct elimination bracket");
    expect(columns).toHaveStyle({ minWidth: "760px" });
  });

  it("renders empty and error states", () => {
    const { rerender } = render(<BracketVisualizer bouts={[]} />);

    expect(screen.getByText("No bracket data available.")).toBeInTheDocument();

    rerender(<BracketVisualizer bouts={fullDeRows} error="Unable to load bracket." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load bracket.");
  });
});

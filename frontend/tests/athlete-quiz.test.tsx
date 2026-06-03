import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AthleteQuiz, type AthleteQuizQuestion } from "../components/AthleteQuiz";

const questions: AthleteQuizQuestion[] = [
  {
    id: "q1",
    question: "Which weapon appears in Alice Example's verified career data?",
    answer: "Epee",
    options: ["Epee", "Foil", "Sabre"],
    sourceMetadata: {
      sources: [
        {
          table: "fs_fencer_career_stats",
          row_id: "fencer-alice",
          columns: ["fencer_id", "weapons_used"],
        },
      ],
    },
  },
  {
    id: "q2",
    question: "Which country is Bob Example listed as representing?",
    answer: "USA",
    options: ["FRA", "ITA", "JPN", "USA"],
    sourceMetadata: {
      sources: [
        {
          table: "fs_fencers",
          row_id: "fencer-bob",
          columns: ["id", "name", "country"],
        },
      ],
    },
  },
];
const emptyQuestions: AthleteQuizQuestion[] = [];

describe("AthleteQuiz", () => {
  it("renders an empty state without quiz controls", () => {
    render(<AthleteQuiz questions={emptyQuestions} />);

    expect(screen.getByRole("region", { name: /athlete quiz/i })).toHaveTextContent(
      "No trivia questions available.",
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("reveals answers, tracks score, advances, and restarts deterministically", async () => {
    render(<AthleteQuiz questions={questions} />);

    expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
    expect(screen.getByText("Score 0 / 2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Foil" }));

    expect(screen.getByText("Not this time.")).toBeInTheDocument();
    expect(screen.getByText("Correct answer: Epee")).toBeInTheDocument();
    expect(screen.getByText("Source: fs_fencer_career_stats")).toBeInTheDocument();
    expect(screen.getByText("Score 0 / 2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next question/i }));

    expect(screen.getByText("Question 2 of 2")).toBeInTheDocument();
    expect(screen.getByText(/Which country is Bob Example/)).toBeInTheDocument();

    const options = screen.getByRole("group", { name: /answer options/i });
    fireEvent.click(within(options).getByRole("button", { name: "USA" }));

    expect(screen.getByText("Correct.")).toBeInTheDocument();
    expect(screen.getByText("Score 1 / 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /restart quiz/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /restart quiz/i }));

    expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
    expect(screen.getByText("Score 0 / 2")).toBeInTheDocument();
  });
});

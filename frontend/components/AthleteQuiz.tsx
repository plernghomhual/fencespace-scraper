"use client";

import { CheckCircle, ChevronRight, RotateCcw, XCircle, type LucideIcon } from "lucide-react";
import { useMemo, useState, type CSSProperties } from "react";

export interface AthleteQuizSource {
  table?: string;
  row_id?: string;
  columns?: string[];
}

export interface AthleteQuizSourceMetadata {
  sources?: AthleteQuizSource[];
}

export interface AthleteQuizQuestion {
  id: string;
  question: string;
  answer: string;
  options: string[];
  questionType?: string;
  sourceMetadata?: AthleteQuizSourceMetadata;
}

export interface AthleteQuizProps {
  questions: AthleteQuizQuestion[] | null | undefined;
  className?: string;
  emptyMessage?: string;
}

export function AthleteQuiz({
  questions,
  className,
  emptyMessage = "No trivia questions available.",
}: AthleteQuizProps) {
  const safeQuestions = useMemo(() => normalizeQuestions(questions), [questions]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [score, setScore] = useState(0);

  if (safeQuestions.length === 0) {
    return (
      <section aria-label="Athlete quiz" className={className} style={styles.root}>
        <p style={styles.emptyText}>{emptyMessage}</p>
      </section>
    );
  }

  const currentIndex = Math.min(questionIndex, safeQuestions.length - 1);
  const current = safeQuestions[currentIndex];
  const hasAnswered = selectedAnswer !== null;
  const isCorrect = selectedAnswer === current.answer;
  const isLastQuestion = currentIndex === safeQuestions.length - 1;

  function chooseAnswer(option: string) {
    if (selectedAnswer !== null) {
      return;
    }
    setSelectedAnswer(option);
    if (option === current.answer) {
      setScore((value) => value + 1);
    }
  }

  function nextQuestion() {
    setQuestionIndex((value) => Math.min(value + 1, safeQuestions.length - 1));
    setSelectedAnswer(null);
  }

  function restartQuiz() {
    setQuestionIndex(0);
    setSelectedAnswer(null);
    setScore(0);
  }

  return (
    <section aria-label="Athlete quiz" className={className} style={styles.root}>
      <header style={styles.header}>
        <span style={styles.progressText}>
          Question {currentIndex + 1} of {safeQuestions.length}
        </span>
        <span aria-live="polite" style={styles.scoreText}>
          Score {score} / {safeQuestions.length}
        </span>
      </header>

      <h2 style={styles.questionText}>{current.question}</h2>

      <div aria-label="Answer options" role="group" style={styles.optionGrid}>
        {current.options.map((option) => {
          const selected = option === selectedAnswer;
          const correctOption = hasAnswered && option === current.answer;
          return (
            <button
              aria-pressed={selected}
              disabled={hasAnswered}
              key={option}
              onClick={() => chooseAnswer(option)}
              style={{
                ...styles.optionButton,
                ...(selected ? styles.selectedOption : null),
                ...(correctOption ? styles.correctOption : null),
              }}
              type="button"
            >
              {option}
            </button>
          );
        })}
      </div>

      {hasAnswered && (
        <AnswerReveal
          answer={current.answer}
          isCorrect={isCorrect}
          sourceMetadata={current.sourceMetadata}
        />
      )}

      {hasAnswered && (
        <div style={styles.actions}>
          {isLastQuestion ? (
            <ActionButton icon={RotateCcw} label="Restart quiz" onClick={restartQuiz} />
          ) : (
            <ActionButton icon={ChevronRight} label="Next question" onClick={nextQuestion} />
          )}
        </div>
      )}
    </section>
  );
}

function normalizeQuestions(questions: AthleteQuizQuestion[] | null | undefined): AthleteQuizQuestion[] {
  return (questions ?? [])
    .filter((question) => {
      if (!question.id || !question.question || !question.answer) {
        return false;
      }
      return Array.isArray(question.options) && question.options.includes(question.answer);
    })
    .map((question) => ({
      ...question,
      options: [...new Set(question.options)],
    }));
}

function AnswerReveal({
  answer,
  isCorrect,
  sourceMetadata,
}: {
  answer: string;
  isCorrect: boolean;
  sourceMetadata?: AthleteQuizSourceMetadata;
}) {
  const Icon = isCorrect ? CheckCircle : XCircle;
  const sourceLabel = sourceMetadata?.sources
    ?.map((source) => source.table)
    .filter(Boolean)
    .filter((table, index, tables) => tables.indexOf(table) === index)
    .join(", ");

  return (
    <aside aria-live="polite" style={styles.reveal}>
      <p style={styles.resultLine}>
        <Icon aria-hidden="true" size={18} strokeWidth={2.2} />
        <span>{isCorrect ? "Correct." : "Not this time."}</span>
      </p>
      <p style={styles.answerLine}>Correct answer: {answer}</p>
      {sourceLabel && <p style={styles.sourceText}>Source: {sourceLabel}</p>}
    </aside>
  );
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
}) {
  return (
    <button onClick={onClick} style={styles.actionButton} type="button">
      <Icon aria-hidden="true" size={17} strokeWidth={2.2} />
      <span>{label}</span>
    </button>
  );
}

const styles: Record<string, CSSProperties> = {
  root: {
    color: "#172026",
    display: "grid",
    gap: "0.9rem",
    maxWidth: "42rem",
    minWidth: 0,
  },
  header: {
    alignItems: "center",
    display: "flex",
    flexWrap: "wrap",
    gap: "0.65rem",
    justifyContent: "space-between",
  },
  progressText: {
    color: "#5d6972",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  scoreText: {
    color: "#172026",
    fontSize: "0.9rem",
    fontVariantNumeric: "tabular-nums",
    fontWeight: 700,
  },
  questionText: {
    fontSize: "1.1rem",
    lineHeight: 1.35,
    margin: 0,
  },
  optionGrid: {
    display: "grid",
    gap: "0.55rem",
    gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 9rem), 1fr))",
  },
  optionButton: {
    background: "#ffffff",
    border: "1px solid #cfd8df",
    borderRadius: "0.5rem",
    color: "#172026",
    cursor: "pointer",
    font: "inherit",
    fontWeight: 650,
    minHeight: "2.7rem",
    padding: "0.55rem 0.75rem",
    textAlign: "left",
  },
  selectedOption: {
    borderColor: "#2f6d7e",
    boxShadow: "inset 0 0 0 1px #2f6d7e",
  },
  correctOption: {
    background: "#eef8f2",
    borderColor: "#397854",
  },
  reveal: {
    background: "#f6f8f9",
    border: "1px solid #d8e0e6",
    borderRadius: "0.5rem",
    display: "grid",
    gap: "0.35rem",
    padding: "0.75rem",
  },
  resultLine: {
    alignItems: "center",
    display: "flex",
    gap: "0.4rem",
    fontWeight: 750,
    margin: 0,
  },
  answerLine: {
    margin: 0,
  },
  sourceText: {
    color: "#5d6972",
    fontSize: "0.85rem",
    margin: 0,
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
  },
  actionButton: {
    alignItems: "center",
    background: "#172026",
    border: "1px solid #172026",
    borderRadius: "0.5rem",
    color: "#ffffff",
    cursor: "pointer",
    display: "inline-flex",
    font: "inherit",
    fontWeight: 700,
    gap: "0.4rem",
    minHeight: "2.45rem",
    padding: "0.5rem 0.75rem",
  },
  emptyText: {
    color: "#5d6972",
    margin: 0,
  },
};

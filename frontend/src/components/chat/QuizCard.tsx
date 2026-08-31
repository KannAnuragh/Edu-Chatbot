"use client";

import { cn } from "@/lib/utils";
import { GraduationCap, Check, X, Sparkles, ChevronRight, Trophy } from "lucide-react";
import {
  type QuizQuestion,
  type QuizResult,
  type QuizTopicsPayload,
} from "@/types";

interface QuizCardProps {
  variant: "topics" | "question" | "result" | "complete";
  data: QuizTopicsPayload | QuizQuestion | QuizResult | null;
  onTopicPick?: (topic: string) => void;
  onAnswer?: (key: "A" | "B" | "C" | "D") => void;
  // When true, the question has already been answered and the option
  // buttons are disabled (the result card will appear next to it).
  locked?: boolean;
  disabled?: boolean;
}

/**
 * Structured quiz UI. Three variants:
 *  - "topics":    Renders the topic picker buttons.
 *  - "question":  Renders a multiple-choice question with clickable option chips.
 *  - "result":    Shows feedback for the just-graded answer.
 *  - "complete":  Shows the final score.
 */
export default function QuizCard({
  variant,
  data,
  onTopicPick,
  onAnswer,
  locked,
  disabled,
}: QuizCardProps) {
  if (variant === "topics") {
    return (
      <TopicsCard
        data={data as QuizTopicsPayload}
        onTopicPick={onTopicPick!}
        disabled={disabled}
      />
    );
  }
  if (variant === "question") {
    return (
      <QuestionCard
        question={data as QuizQuestion}
        onAnswer={onAnswer!}
        locked={!!locked}
        disabled={disabled}
      />
    );
  }
  if (variant === "result") {
    return <ResultCard result={data as QuizResult} />;
  }
  if (variant === "complete") {
    return <CompleteCard result={data as QuizResult} />;
  }
  return null;
}

function TopicsCard({
  data,
  onTopicPick,
  disabled,
}: {
  data: QuizTopicsPayload;
  onTopicPick: (topic: string) => void;
  disabled?: boolean;
}) {
  const topics = data?.topics || [];
  return (
    <div className="mt-3 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-[12px] font-semibold text-[#1C4D8C]">
        <Sparkles size={14} />
        Choose a topic
      </div>
      {topics.map((topic, i) => (
        <button
          key={i}
          onClick={() => onTopicPick(topic)}
          disabled={disabled}
          className={cn(
            "w-full text-left px-4 py-3 rounded-2xl border bg-white/95 border-gray-200/80 shadow-[0_2px_10px_rgba(0,0,0,0.04)]",
            "hover:border-[#1C4D8C] hover:bg-blue-50/40 transition-[border-color,background-color,transform] duration-150",
            "active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed group flex items-center justify-between gap-2"
          )}
        >
          <span className="text-[14px] font-medium text-gray-900 leading-snug">
            {topic}
          </span>
          <ChevronRight
            size={16}
            className="text-gray-400 group-hover:text-[#1C4D8C] group-hover:translate-x-0.5 transition-all flex-shrink-0"
          />
        </button>
      ))}
      <button
        onClick={() => onTopicPick("All Topics (Mixed)")}
        disabled={disabled}
        className={cn(
          "w-full text-left px-4 py-3 rounded-2xl border bg-gradient-to-br from-[#1C4D8C]/10 to-[#3B82F6]/10 border-[#1C4D8C]/30",
          "hover:from-[#1C4D8C]/15 hover:to-[#3B82F6]/15 transition-[background-color,transform] duration-150",
          "active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed group flex items-center justify-between gap-2"
        )}
      >
        <span className="text-[14px] font-semibold text-[#1C4D8C] leading-snug flex items-center gap-2">
          <GraduationCap size={16} />
          All Topics (Mixed)
        </span>
        <ChevronRight
          size={16}
          className="text-[#1C4D8C] group-hover:translate-x-0.5 transition-all flex-shrink-0"
        />
      </button>
    </div>
  );
}

function QuestionCard({
  question,
  onAnswer,
  locked,
  disabled,
}: {
  question: QuizQuestion;
  onAnswer: (key: "A" | "B" | "C" | "D") => void;
  locked: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="mt-3 flex flex-col gap-2.5">
      <div className="flex items-center gap-2 text-[12px] font-semibold text-[#1C4D8C]">
        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#1C4D8C] text-white text-[11px] font-bold">
          {question.index + 1}
        </span>
        Question {question.index + 1} of {question.total}
        {question.topic && (
          <span className="ml-1 text-[11px] text-gray-500 font-normal truncate">
            · {question.topic}
          </span>
        )}
      </div>
      <div className="text-[15px] font-semibold text-gray-900 leading-snug">
        {question.stem}
      </div>
      <div className="flex flex-col gap-2 mt-1">
        {question.options.map((opt) => (
          <button
            key={opt.key}
            onClick={() => onAnswer(opt.key)}
            disabled={disabled || locked}
            className={cn(
              "w-full text-left px-4 py-3 rounded-2xl border bg-white/95 border-gray-200/80 shadow-[0_2px_10px_rgba(0,0,0,0.04)]",
              "hover:border-[#1C4D8C] hover:bg-blue-50/40 transition-[border-color,background-color,transform] duration-150",
              "active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed group flex items-center gap-3"
            )}
          >
            <span
              className={cn(
                "flex-shrink-0 w-7 h-7 rounded-full border-2 border-gray-300 group-hover:border-[#1C4D8C] group-hover:bg-[#1C4D8C] group-hover:text-white",
                "flex items-center justify-center text-[12px] font-bold text-gray-600 transition-colors"
              )}
            >
              {opt.key}
            </span>
            <span className="text-[14px] text-gray-900 leading-snug font-medium">
              {opt.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ResultCard({ result }: { result: QuizResult }) {
  const ok = result.is_correct;
  return (
    <div
      className={cn(
        "mt-2 flex items-start gap-2.5 rounded-2xl px-4 py-3 border text-[14px] leading-snug font-medium",
        ok
          ? "bg-emerald-50 border-emerald-200 text-emerald-900"
          : "bg-rose-50 border-rose-200 text-rose-900"
      )}
    >
      <div
        className={cn(
          "flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-white",
          ok ? "bg-emerald-500" : "bg-rose-500"
        )}
      >
        {ok ? <Check size={16} /> : <X size={16} />}
      </div>
      <div className="flex-1 min-w-0">
        {ok ? (
          <span className="font-semibold">Correct!</span>
        ) : (
          <span className="font-semibold">
            Not quite. The correct answer is {result.correct_key}.
          </span>
        )}
        {result.explanation && (
          <p className="mt-1 text-[13px] font-normal text-gray-700">
            {result.explanation}
          </p>
        )}
      </div>
    </div>
  );
}

function CompleteCard({ result }: { result: QuizResult }) {
  const pct = result.total > 0 ? Math.round((result.score / result.total) * 100) : 0;
  return (
    <div className="mt-3 rounded-2xl bg-gradient-to-br from-[#1C4D8C] to-[#3B82F6] text-white px-5 py-4 shadow-[0_8px_24px_rgba(28,77,140,0.3)] flex items-center gap-3">
      <div className="flex-shrink-0 w-12 h-12 rounded-full bg-white/15 flex items-center justify-center">
        <Trophy size={22} className="text-amber-300" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[16px] font-bold">Quiz Complete!</div>
        <div className="text-[13px] text-blue-100 mt-0.5">
          Your Score: {result.score}/{result.total} ({pct}%)
        </div>
      </div>
    </div>
  );
}

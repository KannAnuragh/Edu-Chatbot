"use client";

import { FormEvent, useState } from "react";
import { Brain, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { type ExplainMode, type ExplainPromptPayload } from "@/types";

interface ExplainCardProps {
  data: ExplainPromptPayload;
  disabled?: boolean;
  onSubmit: (concept: string, mode: ExplainMode) => void;
}

const MODES: { value: ExplainMode; label: string; description: string }[] = [
  { value: "ELI5", label: "Simple Explanation", description: "Simple and memorable" },
  { value: "DEEP_DIVE", label: "Deep Dive", description: "Technical detail" },
  { value: "EXAM_FOCUSED", label: "Exam-Focused", description: "Built for recall" },
];

export default function ExplainCard({ data, disabled, onSubmit }: ExplainCardProps) {
  const [concept, setConcept] = useState("");
  const [mode, setMode] = useState<ExplainMode>(data.modes[0] || "ELI5");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = concept.trim();
    if (value && !disabled) onSubmit(value, mode);
  };

  return (
    <div className="mt-3 rounded-2xl border border-indigo-100 bg-white/95 p-4 shadow-[0_4px_18px_rgba(15,23,42,0.06)]">
      <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-indigo-700">
        <Brain size={17} />
        <div>
          <div>Concept Explainer</div>
          <div className="text-[11px] font-normal text-slate-500">Clear breakdowns with analogies and key insights</div>
        </div>
      </div>
      <form onSubmit={submit}>
        <input
          value={concept}
          onChange={(event) => setConcept(event.target.value)}
          placeholder="What concept should we explain?"
          disabled={disabled}
          className="mb-3 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-[13px] text-slate-900 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
        />
        <div className="mb-3 grid grid-cols-3 gap-2">
          {MODES.filter((item) => data.modes.includes(item.value)).map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setMode(item.value)}
              disabled={disabled}
              className={cn(
                "rounded-xl border px-2 py-2 text-left transition-colors disabled:opacity-50",
                mode === item.value ? "border-indigo-400 bg-indigo-50 text-indigo-800" : "border-slate-200 bg-white text-slate-700 hover:border-indigo-200"
              )}
            >
              <span className="block text-[12px] font-semibold">{item.label}</span>
              <span className="block text-[10px] leading-tight text-slate-500">{item.description}</span>
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={disabled || !concept.trim()}
          className="flex w-full items-center justify-center gap-1 rounded-xl bg-indigo-600 px-3 py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Explain concept <ChevronRight size={15} />
        </button>
      </form>
    </div>
  );
}
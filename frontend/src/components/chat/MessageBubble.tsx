"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Bot, User, Copy, Check, ThumbsUp, ThumbsDown, RotateCw, Lightbulb, Pencil, ClipboardList, Zap } from "lucide-react";
import { type Message, type SourceReference } from "@/types";
import { cn } from "@/lib/utils";
import SourceBadge from "./SourceBadge";

interface MessageBubbleProps {
  message: Message;
  onSourceClick?: (source: SourceReference) => void;
  onViewNote?: (content: string, sources?: SourceReference[]) => void;
  onRegenerate?: () => void;
  isStreaming?: boolean;
  isLatest?: boolean;
  onSendFollowUp?: (text: string) => void;
}

export default function MessageBubble({ message, onSourceClick, onViewNote, onRegenerate, isStreaming, isLatest, onSendFollowUp }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const normalizeFollowUpQuestion = (value: string) => {
    const trimmed = (value ?? "").trim();
    if (!trimmed) return "";

    const withoutLabel = trimmed.replace(
      /^(?:\*{0,2})?(?:Follow(?:\s|-)?Up|Suggested\s+(?:Follow(?:\s|-)?Up\s+)?(?:Questions?|Qs?)|Related\s+Questions?)\s*[:\-]?\s*/i,
      ""
    ).trim();

    if (!withoutLabel) return "";
    return withoutLabel.replace(/^[-*•\d.\s]+/, "").trim();
  };

  const extractFollowUps = (text: string) => {
    const rawText = text ?? "";
    const marker = "===FOLLOWUP_QUESTIONS===";
    const delimiterIndex = rawText.indexOf(marker);

    let cleanText = rawText;
    let followUps: string[] = [];

    const parseInlineFollowUpBlock = (source: string) => {
      const inlineMatch = source.match(/(?:^|\n)\s*(?:Follow(?:\s|-)?Up|FOLLOWUP)\s*[:\-]?\s*([\s\S]*?)(?=\n\s*(?:Follow(?:\s|-)?Up|FOLLOWUP|Suggested\s+(?:Follow(?:\s|-)?Up\s+)?(?:Questions?|Qs?)|Related\s+Questions?)\s*[:\-]?|$)/i);
      if (!inlineMatch) return [];

      const tail = (inlineMatch[1] || "").trim();
      if (!tail) return [];

      return tail
        .split(/\r?\n|\s*\|\s*/)
        .map((line) => normalizeFollowUpQuestion(line).replace(/^\[|\]$/g, "").trim())
        .filter((item) => item && item.length > 3 && /[?]/.test(item));
    };

    if (delimiterIndex !== -1) {
      cleanText = rawText.slice(0, delimiterIndex).trim();
      const followUpPayload = rawText.slice(delimiterIndex + marker.length).trim();
      if (followUpPayload) {
        try {
          const parsed = JSON.parse(followUpPayload);
          if (Array.isArray(parsed)) {
            followUps = parsed
              .filter((item): item is string => typeof item === "string")
              .map((item) => normalizeFollowUpQuestion(item))
              .filter((item) => item && item.length > 3 && /[?]/.test(item));
          }
        } catch {
          followUps = followUpPayload
            .split(/\r?\n|\s*\|\s*/)
            .map((item) => normalizeFollowUpQuestion(item))
            .filter((item) => item && item.length > 3 && /[?]/.test(item));
        }
      }
      return { cleanText, followUps: Array.from(new Set(followUps)).slice(0, 3) };
    }

    const inlineFollowUps = parseInlineFollowUpBlock(rawText);
    if (inlineFollowUps.length > 0) {
      followUps = Array.from(new Set(inlineFollowUps)).slice(0, 3);
      cleanText = rawText.replace(/(?:^|\n)\s*(?:Follow(?:\s|-)?Up|FOLLOWUP)\s*[:\-]?\s*[\s\S]*?(?=\n\s*(?:Follow(?:\s|-)?Up|FOLLOWUP|Suggested\s+(?:Follow(?:\s|-)?Up\s+)?(?:Questions?|Qs?)|Related\s+Questions?)\s*[:\-]?|$)/i, "").trim();
      return { cleanText, followUps };
    }

    const headerRegex = /(?:\n+|^)\s*(?:\*{0,2})?(?:Follow-?up Questions?:?|Suggested (?:Follow-?ups?|Questions?):?|Related Questions?:?)(?:\*{0,2})?\s*(?:\n+|$)([\s\S]*)$/i;
    const headerMatch = rawText.match(headerRegex);

    if (headerMatch) {
      const trailing = (headerMatch[1] || "").trim();
      const parsedQuestions = trailing
        .split(/\r?\n/)
        .map((line) => normalizeFollowUpQuestion(line).replace(/^\[|\]$/g, "").trim())
        .filter((item) => item && item.length > 3 && /[?]/.test(item));
      followUps = Array.from(new Set(parsedQuestions)).slice(0, 3);
      cleanText = rawText.slice(0, headerMatch.index ?? 0).trim();
    }

    const legacyQuestions = cleanText.match(/\[(?:FOLL?OW-?UP|QUESTION\s*\d*):\s*([\s\S]*?)\]/gi) || [];
    if (legacyQuestions.length > 0) {
      legacyQuestions.forEach((item) => {
        const match = item.match(/\[(?:FOLL?OW-?UP|QUESTION\s*\d*):\s*([\s\S]*?)\]/i);
        const q = normalizeFollowUpQuestion(match?.[1] ?? "");
        if (q && !followUps.includes(q)) followUps.push(q);
      });
      cleanText = cleanText.replace(/\[(?:FOLL?OW-?UP|QUESTION\s*\d*):\s*([\s\S]*?)\]/gi, "").trim();
    }

    cleanText = cleanText
      .replace(/(?:\n+|^)\s*(?:\*{0,2})?(?:Follow-?up Questions?:?|Suggested (?:Follow-?ups?|Questions?):?|Related Questions?:?)(?:\*{0,2})?\s*$/i, "")
      .trim();

    return { cleanText, followUps: Array.from(new Set(followUps)).slice(0, 3) };
  };

  const { cleanText, followUps } = extractFollowUps(message.content);
  const effectiveFollowUps = (message.follow_up_questions ?? followUps)
    .map((question) => normalizeFollowUpQuestion(question))
    .filter((question) => question && /[?]/.test(question));

  const handleCopy = () => {
    navigator.clipboard.writeText(cleanText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderContent = (content: string) => {
    let processedContent = content.replace(
      /^(?:Based on the provided (?:documents?|course materials?|reference materials?|context|text),?\s*|Based on the (?:provided |)(?:documents?|course materials?|reference materials?|context|text),?\s*|According to the (?:provided )?(?:documents?|course materials?|reference materials?|context|text),?\s*|From the (?:provided )?(?:course materials?|reference materials?|text),?\s*|The (?:text|document|course material|reference material) (?:mentions|states|says|explains|describes|indicates),?\s*|As per the (?:provided )?(?:course materials?|reference materials?|documents?|text),?\s*|In the provided (?:course materials?|context|reference materials?|text),?\s*|Here is the information from the text:?\s*)/i,
      ""
    );

    processedContent = processedContent.replace(
      /(\*{0,2})\[([^\]]+?)\s*(?:—|–|-)\s*[Pp]age\s*(\d+)(?:,\s*\d+)*\](\*{0,2})/g,
      ""
    );
    processedContent = processedContent.replace(/\[CITE:[^\]]+\]/g, "");

    return (
      <ReactMarkdown
        className={cn(
          "prose prose-sm max-w-none prose-p:leading-relaxed prose-p:mb-2.5 prose-p:last:mb-0 prose-pre:my-3 prose-li:my-1 prose-headings:font-heading",
          isUser
            ? "text-white prose-p:text-white prose-strong:text-white prose-headings:text-white prose-li:text-white prose-code:text-blue-100 prose-code:bg-black/20 prose-a:text-blue-200 font-medium"
            : "text-gray-900 prose-p:text-gray-900 prose-strong:text-gray-900 prose-headings:text-gray-900 prose-li:text-gray-900 prose-code:text-nimbus prose-code:bg-gray-100 prose-a:text-nimbus font-medium"
        )}
      >
        {processedContent.trim()}
      </ReactMarkdown>
    );
  };

  // ─── USER MESSAGE ───
  if (isUser) {
    return (
      <div className="flex justify-end my-2.5 animate-fade-in-up group">
        <div
          className="relative text-white font-medium px-[18px] py-[12px] rounded-[18px] rounded-br-[4px] text-[15px] max-w-[80%] border border-white/15 shadow-[0_4px_14px_rgba(22,51,89,0.35)] transition-all"
          style={{
            background: 'linear-gradient(135deg, #1C4D8C 0%, #1C4D8C 25%, #163359 100%)',
          }}
        >
          <div className="relative">
            {renderContent(cleanText)}
          </div>

          {/* Hover Edit Pencil */}
          <button className="absolute -left-8 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-[#3B82F6] opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 backdrop-blur-sm rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.1)] border border-gray-200">
            <Pencil size={14} />
          </button>
        </div>
      </div>
    );
  }

  // ─── BOT (ASSISTANT) MESSAGE: White Background Bubble, Left-Aligned with Bot Avatar ───
  return (
    <div className="flex items-start gap-3 my-3.5 animate-fade-in-up">
      {/* Bot Avatar Icon */}
      <div className="relative w-8 h-8 flex items-center justify-center flex-shrink-0 mt-0.5">
        {/* Static Background Blob */}
        <div
          className="absolute inset-[-6px] rounded-full blur-[5px] opacity-100"
          style={{
            background: 'radial-gradient(circle at 35% 35%, #9cbbe0 0%, #1C4D8C 55%, #163359 100%)',
            boxShadow: '0 4px 12px rgba(28, 77, 140, 0.4)'
          }}
        />

        {/* Static Face */}
        <svg viewBox="0 0 100 100" className="relative z-10 w-[32px] h-[32px] text-white drop-shadow-md">
          {/* Eyebrows */}
          <path d="M 32 38 Q 38 30 44 38" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" />
          <path d="M 56 38 Q 62 30 68 38" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" />

          {/* Eyes */}
          <ellipse cx="38" cy="48" rx="4.5" ry="4.5" fill="currentColor" />
          <ellipse cx="62" cy="48" rx="4.5" ry="4.5" fill="currentColor" />

          {/* Nose */}
          <path d="M 50 49 L 50 63 L 56 63" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>

      {/* White Message Bubble */}
      <div className={cn("flex flex-col gap-1.5 max-w-[85%] min-w-0", isStreaming && "is-streaming")}>
        <div className="relative isolate overflow-hidden bg-white/60 backdrop-blur-2xl text-slate-950 rounded-[14px] rounded-tl-xl p-5 shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.85),inset_0_-1px_1px_rgba(0,0,0,0.04),0_8px_30px_rgba(0,0,0,0.05)] border border-white/70">
          {/* Glass sheen to match the user bubble's material */}
          <div className="pointer-events-none absolute inset-x-0 top-0 h-8 rounded-t-[14px] bg-gradient-to-b from-white/50 to-transparent" />

          {/* Message Content */}
          <div className="relative text-[15px] leading-relaxed">
            {cleanText.trim().length > 0 ? (
              renderContent(cleanText)
            ) : (
              <div className="flex items-center gap-1.5 py-1 px-1">
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            )}
          </div>
        </div>

        {/* Action Row Below Chat Box: Like & Dislike on Left, Copy Button on Right */}
        <div className="flex items-center justify-between px-1 text-xs">
          {/* Left: Like and Dislike */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFeedback(feedback === "up" ? null : "up")}
              className={cn(
                "p-1 rounded transition-colors",
                feedback === "up" ? "text-[#1C4D8C] bg-blue-50" : "text-gray-700 hover:text-black"
              )}
              title="Helpful"
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => setFeedback(feedback === "down" ? null : "down")}
              className={cn(
                "p-1 rounded transition-colors",
                feedback === "down" ? "text-[#1C4D8C] bg-blue-50" : "text-gray-700 hover:text-black"
              )}
              title="Not helpful"
            >
              <ThumbsDown size={14} />
            </button>
          </div>

          {/* Right: Sources & Copy Button */}
          <div className="flex items-center gap-2">
            {message.sources && message.sources.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {message.sources.map((src, i) => (
                  <SourceBadge
                    key={i}
                    source={src}
                    onClick={onSourceClick ? () => onSourceClick(src) : undefined}
                  />
                ))}
              </div>
            )}

            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="p-1 text-gray-700 hover:text-black rounded transition-colors flex items-center gap-1 text-xs"
                title="Regenerate response"
              >
                <RotateCw size={14} />
              </button>
            )}

            {cleanText.trim().length > 0 && (
              <button
                onClick={handleCopy}
                className="p-1 text-gray-700 hover:text-black rounded transition-colors flex items-center gap-1 text-xs"
                title="Copy message"
              >
                {copied ? (
                  <>
                    <Check size={14} className="text-emerald-600" />
                    <span className="text-emerald-600 text-[11px] font-medium">Copied</span>
                  </>
                ) : (
                  <Copy size={14} />
                )}
              </button>
            )}
          </div>
        </div>
        
        {/* Smart Follow-Up Chips */}
        {isLatest && !isStreaming && onSendFollowUp && effectiveFollowUps.length > 0 && (
          <div className="flex flex-row overflow-x-auto no-scrollbar gap-2 mt-2 px-1 pb-1">
            {effectiveFollowUps.map((text, i) => {
              return (
                <button
                  key={i}
                  onClick={() => onSendFollowUp(text)}
                  className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/60 border border-[#E2E8F0] text-gray-700 text-[13px] font-medium hover:border-[#1C4D8C] hover:text-[#1C4D8C] transition-colors shadow-sm active:scale-95 whitespace-nowrap"
                >
                  <Lightbulb size={12} className="text-amber-500" />
                  {text}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

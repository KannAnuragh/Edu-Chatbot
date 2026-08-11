"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Bot, User, Copy, Check, ThumbsUp, ThumbsDown, RotateCw } from "lucide-react";
import { type Message, type SourceReference } from "@/types";
import { cn } from "@/lib/utils";
import SourceBadge from "./SourceBadge";

interface MessageBubbleProps {
  message: Message;
  onSourceClick?: (source: SourceReference) => void;
  onViewNote?: (content: string, sources?: SourceReference[]) => void;
  onRegenerate?: () => void;
}

export default function MessageBubble({ message, onSourceClick, onViewNote, onRegenerate }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
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
          "prose prose-sm max-w-none prose-p:leading-relaxed prose-p:mb-2.5 prose-pre:my-3 prose-li:my-1 prose-headings:font-heading",
          isUser
            ? "text-gray-900 prose-p:text-gray-900 prose-strong:text-gray-900 prose-headings:text-gray-900 prose-li:text-gray-900 font-medium"
            : "text-white/95 prose-p:text-white/95 prose-strong:text-white prose-headings:text-white prose-li:text-white/95 prose-code:text-amber-200 prose-code:bg-white/10 prose-a:text-amber-300"
        )}
      >
        {processedContent.trim()}
      </ReactMarkdown>
    );
  };

  // ─── USER MESSAGE: No Box / No Background, Right-Aligned with Profile Avatar ───
  if (isUser) {
    return (
      <div className="flex items-center justify-end gap-3 w-full my-3 animate-fade-in-up">
        {/* Action Button (Refresh / Re-run) */}
        {onRegenerate && (
          <button
            onClick={onRegenerate}
            className="w-7 h-7 rounded-full bg-transparent border border-gray-300/60 text-gray-400 hover:text-nimbus hover:border-nimbus flex items-center justify-center flex-shrink-0 transition-all active:scale-95"
            title="Retry prompt"
          >
            <RotateCw size={13} />
          </button>
        )}

        {/* Plain Text User Message (No Box, No Background) */}
        <div className="text-gray-900 text-[16px] font-medium max-w-[85%] text-right leading-relaxed">
          {renderContent(message.content)}
        </div>

        {/* User Avatar on the RIGHT Side */}
        <div className="w-9 h-9 rounded-full bg-[#1C4D8C] text-white flex items-center justify-center flex-shrink-0 shadow-sm text-xs font-semibold overflow-hidden">
          <User size={18} />
        </div>
      </div>
    );
  }

  // ─── ASSISTANT MESSAGE: Blue Card with Feedback & Sources BELOW the Blue Box ───
  return (
    <div className="w-full my-3.5 animate-fade-in-up">
      {/* Blue Background Container */}
      <div className="relative bg-[#1C4D8C] text-white rounded-[26px] p-5 shadow-md border border-blue-900/30">
        
        {/* Header row: Bot Avatar on top-left, Copy Icon on top-right */}
        <div className="flex items-center justify-between mb-3">
          <div className="w-8 h-8 rounded-full bg-slate-900/80 border border-white/20 flex items-center justify-center text-emerald-400 shadow-sm">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>

          {/* Copy Button */}
          <button
            onClick={handleCopy}
            className="p-1.5 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors flex items-center gap-1 text-xs"
            title="Copy message"
          >
            {copied ? (
              <>
                <Check size={15} className="text-emerald-300" />
                <span className="text-emerald-300 text-[11px]">Copied</span>
              </>
            ) : (
              <Copy size={15} />
            )}
          </button>
        </div>

        {/* Message Content */}
        <div className="text-[15px] leading-relaxed">
          {renderContent(message.content)}
        </div>
      </div>

      {/* BELOW the Blue Box: Thumbs Up / Down Feedback Icons & Sources */}
      <div className="flex items-center justify-between mt-2.5 px-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setFeedback(feedback === "up" ? null : "up")}
            className={cn(
              "p-1.5 rounded-lg transition-colors",
              feedback === "up" ? "text-nimbus bg-nimbus-tint" : "text-gray-400 hover:text-gray-700 hover:bg-gray-200/50"
            )}
            title="Helpful"
          >
            <ThumbsUp size={16} />
          </button>
          <button
            onClick={() => setFeedback(feedback === "down" ? null : "down")}
            className={cn(
              "p-1.5 rounded-lg transition-colors",
              feedback === "down" ? "text-nimbus bg-nimbus-tint" : "text-gray-400 hover:text-gray-700 hover:bg-gray-200/50"
            )}
            title="Not helpful"
          >
            <ThumbsDown size={16} />
          </button>
        </div>

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
      </div>
    </div>
  );
}

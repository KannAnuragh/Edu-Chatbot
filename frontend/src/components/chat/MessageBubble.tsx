"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import { Bot, User, FileText } from "lucide-react";
import { type Message, type SourceReference } from "@/types";
import { cn } from "@/lib/utils";
import SourceBadge from "./SourceBadge";

interface MessageBubbleProps {
  message: Message;
  onSourceClick?: (source: SourceReference) => void;
  onViewNote?: (content: string, sources?: SourceReference[]) => void;
}

export default function MessageBubble({ message, onSourceClick, onViewNote }: MessageBubbleProps) {
  const isUser = message.role === "user";

  const contentToRender = message.content;

  // Clean up and render content
  const renderContent = (content: string) => {
    // 1. Remove introductory filler phrases if the LLM still generates them
    let processedContent = content.replace(
      /^(?:Based on the provided (?:documents?|course materials?|reference materials?|context|text),?\s*|Based on the (?:provided |)(?:documents?|course materials?|reference materials?|context|text),?\s*|According to the (?:provided )?(?:documents?|course materials?|reference materials?|context|text),?\s*|From the (?:provided )?(?:course materials?|reference materials?|text),?\s*|The (?:text|document|course material|reference material) (?:mentions|states|says|explains|describes|indicates),?\s*|As per the (?:provided )?(?:course materials?|reference materials?|documents?|text),?\s*|In the provided (?:course materials?|context|reference materials?|text),?\s*|Here is the information from the text:?\s*)/i,
      ""
    );

    // 2. Aggressively strip out any citation tags like [filename - Page X] or [CITE:...]
    processedContent = processedContent.replace(
      /(\*{0,2})\[([^\]]+?)\s*(?:—|–|-)\s*[Pp]age\s*(\d+)(?:,\s*\d+)*\](\*{0,2})/g,
      ""
    );
    processedContent = processedContent.replace(/\[CITE:[^\]]+\]/g, "");

    return (
      <ReactMarkdown
        className={cn(
          "prose prose-sm max-w-none prose-p:leading-relaxed prose-p:mb-3 prose-pre:my-3 prose-li:my-1 prose-headings:font-heading",
          isUser
            ? "prose-p:text-white prose-strong:text-white prose-headings:text-white prose-li:text-white text-white prose-a:text-blue-200"
            : "nimbus-prose prose-a:text-nimbus"
        )}
      >
        {processedContent.trim()}
      </ReactMarkdown>
    );
  };

  if (isUser) {
    // ─── User message: blue gradient bubble, right-aligned ───
    return (
      <div className="flex justify-end animate-fade-in-up">
        <div className="max-w-[82%]">
          <div className="px-4 py-3 rounded-2xl rounded-br-md bg-gradient-to-br from-nimbus to-nimbus-deep text-white shadow-sm">
            {renderContent(contentToRender)}
          </div>
        </div>
      </div>
    );
  }

  // ─── Assistant message: white card, left-aligned with avatar ───
  return (
    <div className="flex items-start gap-3 animate-fade-in-up">
      {/* Bot avatar */}
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-nimbus-light to-nimbus flex items-center justify-center flex-shrink-0 shadow-sm mt-0.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      </div>

      {/* Message content */}
      <div className="flex flex-col gap-2 max-w-[85%] min-w-0">
        <div className="px-4 py-3 rounded-2xl rounded-tl-md bg-white border border-gray-100 text-gray-800 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          {renderContent(contentToRender)}
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-1">
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

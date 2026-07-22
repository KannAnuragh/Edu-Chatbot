"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import { Bot, User, FileText, ChevronRight } from "lucide-react";
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
      /^(?:Based on the provided documents,?|Based on the provided document chunks,?|Based on the text,?|According to the provided context,?|Here is the information from the text:?)\s*/i,
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
        className="prose prose-sm max-w-none prose-p:leading-relaxed prose-p:mb-3 prose-pre:my-3 prose-li:my-1 prose-headings:font-heading prose-a:text-emerald"
      >
        {processedContent.trim()}
      </ReactMarkdown>
    );
  };

  return (
    <div className={cn("flex gap-4", isUser ? "flex-row-reverse" : "")}>
      {/* Avatar */}
      <div className={cn(
        "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm border",
        isUser
          ? "bg-white text-emerald border-border"
          : "bg-emerald text-white border-emerald-deep"
      )}>
        {isUser ? <User size={16} /> : <Bot size={18} />}
      </div>

      {/* Bubble Container */}
      <div className={cn(
        "flex flex-col gap-2 max-w-[85%]",
        isUser ? "items-end" : "items-start"
      )}>
        <div className={cn(
          "px-4 py-3 rounded-2xl shadow-sm relative overflow-hidden",
          isUser
            ? "bg-emerald text-white rounded-tr-sm"
            : "bg-white border border-border text-ink rounded-tl-sm"
        )}>
          {renderContent(contentToRender)}
        </div>


      </div>
    </div>
  );
}

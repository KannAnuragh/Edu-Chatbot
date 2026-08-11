"use client";

import { FileText } from "lucide-react";
import { type SourceReference } from "@/types";

interface SourceBadgeProps {
  source: SourceReference;
  onClick?: () => void;
}

export default function SourceBadge({ source, onClick }: SourceBadgeProps) {
  const displayFilename = source.filename.replace('.pdf', '');
  
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 mx-0.5 px-2.5 py-1 rounded-lg text-[11px] font-medium bg-nimbus-tint text-nimbus hover:bg-nimbus/10 transition-all border border-nimbus-border cursor-pointer whitespace-nowrap align-middle active:scale-[0.96]"
      title="View source"
    >
      <FileText size={11} className="opacity-60" />
      <span className="max-w-[120px] truncate">{displayFilename}</span>
      <span className="opacity-60 font-mono text-[9px] ml-0.5 border-l border-nimbus/20 pl-1.5">p.{source.page_number}</span>
    </button>
  );
}

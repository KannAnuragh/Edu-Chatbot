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
      className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-tint text-emerald hover:bg-emerald/20 transition-all border border-emerald-border cursor-pointer whitespace-nowrap align-middle"
      title="View in PDF"
    >
      <FileText size={10} className="opacity-70" />
      <span className="max-w-[120px] truncate">{displayFilename}</span>
      <span className="opacity-70 font-mono text-[9px] ml-0.5 border-l border-emerald/30 pl-1">p.{source.page_number}</span>
    </button>
  );
}

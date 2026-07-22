"use client";

import { useState, useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import { FileText, ChevronLeft, ChevronRight, ExternalLink, Download, Loader2, Sparkles } from "lucide-react";
import { type Document as DocType } from "@/types";
import { cn } from "@/lib/utils";

interface PDFViewerProps {
  documents: DocType[];
  activeDocumentId: string | null;
  onDocumentSelect: (id: string) => void;
  highlightInfo?: { pageNumber: number; text: string } | null;
}

export interface PDFViewerHandle {
  goToPage: (page: number) => void;
}

const PDFViewer = forwardRef<PDFViewerHandle, PDFViewerProps>(
  ({ documents, activeDocumentId, onDocumentSelect, highlightInfo }, ref) => {
    const [pageNumber, setPageNumber] = useState<number>(1);
    const iframeRef = useRef<HTMLIFrameElement>(null);

    // Filter ready documents
    const readyDocuments = documents.filter((d) => d.status?.toLowerCase() === "ready");
    const activeDoc = readyDocuments.find((d) => d.id === activeDocumentId) || readyDocuments[0];

    // Auto-select first ready doc if none selected
    useEffect(() => {
      if (!activeDocumentId && readyDocuments.length > 0) {
        onDocumentSelect(readyDocuments[0].id);
      }
    }, [activeDocumentId, readyDocuments, onDocumentSelect]);

    // Handle highlight navigation from chat citations
    useEffect(() => {
      if (highlightInfo) {
        setPageNumber(highlightInfo.pageNumber);
      }
    }, [highlightInfo]);

    // Reset page number when switching document
    useEffect(() => {
      if (!highlightInfo) {
        setPageNumber(1);
      }
    }, [activeDocumentId]);

    useImperativeHandle(ref, () => ({
      goToPage: (page: number) => {
        if (page >= 1) {
          setPageNumber(page);
        }
      },
    }));

    const getPdfUrl = (doc: DocType) => {
      if (!doc || !doc.file_path) return "";
      let baseUrl = "";
      if (process.env.NEXT_PUBLIC_API_URL) {
        baseUrl = process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/v1\/?$/, "");
      } else if (typeof window !== "undefined") {
        const hostname = window.location.hostname;
        if (hostname === "localhost" || hostname === "127.0.0.1") {
          baseUrl = `http://${hostname}:8001`;
        } else {
          baseUrl = ""; // Relative url for production proxying
        }
      } else {
        baseUrl = "http://localhost:8001";
      }
      const cleanPath = doc.file_path.replace(/\\/g, "/").replace(/^\.?\//, "");
      return `${baseUrl}/${cleanPath}`;
    };

    if (readyDocuments.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted bg-preview p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-white border border-border flex items-center justify-center mb-4 shadow-sm">
            <FileText className="w-8 h-8 text-muted opacity-40" />
          </div>
          <h3 className="font-heading font-medium text-ink text-base mb-1">No PDFs Available</h3>
          <p className="text-xs text-muted max-w-sm">
            Upload a PDF document to view and interact with it here.
          </p>
        </div>
      );
    }

    const pdfUrl = activeDoc ? getPdfUrl(activeDoc) : "";
    const pdfEmbedUrl = pdfUrl ? `${pdfUrl}#page=${pageNumber}` : "";

    return (
      <div className="flex flex-col h-full bg-preview overflow-hidden">
        {/* Action Toolbar with Dropdown */}
        <div className="h-12 border-b border-border bg-white flex items-center justify-between px-4 flex-shrink-0 z-10 shadow-sm">
          {/* Document Dropdown Selector */}
          <div className="flex items-center gap-2 min-w-0 max-w-[50%]">
            <div className="w-6 h-6 rounded-md bg-emerald-tint flex items-center justify-center flex-shrink-0">
              <FileText size={14} className="text-emerald" />
            </div>
            {readyDocuments.length > 1 ? (
              <select
                value={activeDoc?.id || ""}
                onChange={(e) => onDocumentSelect(e.target.value)}
                className="font-heading font-medium text-xs text-ink bg-transparent border border-border rounded-lg py-1.5 px-2 focus:ring-1 focus:ring-emerald outline-none cursor-pointer hover:border-emerald/50 transition-colors truncate w-full"
                title={activeDoc?.filename}
              >
                {readyDocuments.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename}
                  </option>
                ))}
              </select>
            ) : (
              <span className="font-heading font-medium text-xs text-ink truncate block" title={activeDoc?.filename}>
                {activeDoc?.filename}
              </span>
            )}
            {activeDoc?.page_count ? (
              <span className="text-[10px] font-mono text-muted bg-rail px-1.5 py-0.5 rounded border border-border flex-shrink-0">
                {activeDoc.page_count} pages
              </span>
            ) : null}
          </div>

          {/* Quick Page Jump Control */}
          <div className="flex items-center gap-1 bg-rail px-2 py-1 rounded-lg border border-border">
            <button
              onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
              disabled={pageNumber <= 1}
              className="p-1 rounded text-muted hover:text-ink disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Previous Page"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-[11px] font-mono font-medium text-ink px-1 min-w-[50px] text-center">
              Page {pageNumber}
            </span>
            <button
              onClick={() => setPageNumber((p) => p + 1)}
              className="p-1 rounded text-muted hover:text-ink transition-colors"
              title="Next Page"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          {/* External Action Buttons */}
          <div className="flex items-center gap-1">
            {pdfUrl && (
              <>
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 text-muted hover:text-emerald hover:bg-rail rounded-lg transition-colors flex items-center gap-1 text-xs"
                  title="Open in New Tab"
                >
                  <ExternalLink size={14} />
                  <span className="hidden sm:inline text-[11px]">Open</span>
                </a>
                <a
                  href={pdfUrl}
                  download={activeDoc?.filename || "document.pdf"}
                  className="p-1.5 text-muted hover:text-emerald hover:bg-rail rounded-lg transition-colors flex items-center gap-1 text-xs"
                  title="Download PDF"
                >
                  <Download size={14} />
                  <span className="hidden sm:inline text-[11px]">Download</span>
                </a>
              </>
            )}
          </div>
        </div>

        {/* Highlight Citation Toast */}
        {highlightInfo && (
          <div className="bg-emerald-tint border-b border-emerald-border px-4 py-1.5 flex items-center justify-between z-10 animate-fade-in">
            <div className="flex items-center gap-2 text-emerald text-xs font-medium truncate">
              <Sparkles size={14} className="flex-shrink-0" />
              <span>Jumped to page {highlightInfo.pageNumber} from chat reference</span>
            </div>
            <span className="text-[10px] text-emerald/80 truncate max-w-[200px] italic">"{highlightInfo.text.slice(0, 40)}..."</span>
          </div>
        )}

        {/* Embedded Interactive PDF Viewer Canvas */}
        <div className="flex-1 w-full h-full relative bg-canvas p-2 overflow-hidden">
          {pdfEmbedUrl ? (
            <iframe
              ref={iframeRef}
              src={pdfEmbedUrl}
              key={`${activeDoc?.id}-${pageNumber}`}
              className="w-full h-full rounded-xl border border-border shadow-xs bg-white"
              title={activeDoc?.filename || "PDF Viewer"}
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-muted bg-white rounded-xl border border-border">
              <Loader2 className="w-6 h-6 animate-spin text-emerald mb-2" />
              <p className="text-xs">Loading PDF document...</p>
            </div>
          )}
        </div>
      </div>
    );
  }
);

PDFViewer.displayName = "PDFViewer";

export default PDFViewer;

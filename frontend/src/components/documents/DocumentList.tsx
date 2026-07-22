"use client";

import { useEffect, useState, useRef } from "react";
import { FileText, Loader2, CheckCircle2, AlertCircle, Trash2, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { type Document } from "@/types";
import { useAuth } from "@/providers/AuthProvider";
import { formatBytes } from "@/lib/utils";

interface DocumentListProps {
  projectId: string;
  documents: Document[];
  onDocumentsChange: (docs: Document[]) => void;
  onViewDocument?: (docId: string) => void;
}

export default function DocumentList({ projectId, documents, onDocumentsChange, onViewDocument }: DocumentListProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [polling, setPolling] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Poll for status updates if any document is pending or processing
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === "pending" || d.status === "processing"
    );

    if (hasProcessing && !polling) {
      setPolling(true);
      pollingRef.current = setInterval(async () => {
        try {
          const data = await api.getDocuments(projectId);
          onDocumentsChange(data.documents);
          
          // Stop polling if no more processing documents
          const stillProcessing = data.documents.some(
            (d: Document) => d.status === "pending" || d.status === "processing"
          );
          if (!stillProcessing) {
            clearInterval(pollingRef.current!);
            setPolling(false);
          }
        } catch (error) {
          console.error("Polling failed", error);
        }
      }, 3000);
    } else if (!hasProcessing && polling) {
      if (pollingRef.current) clearInterval(pollingRef.current);
      setPolling(false);
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [documents, projectId, onDocumentsChange, polling]);

  const handleDelete = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this document? This will remove all associated vectors.")) return;
    
    try {
      await api.deleteDocument(projectId, docId);
      onDocumentsChange(documents.filter((d) => d.id !== docId));
    } catch (error) {
      alert("Failed to delete document");
    }
  };

  const handleReprocess = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.reprocessDocument(projectId, docId);
      // Optimistically update
      onDocumentsChange(
        documents.map((d) => (d.id === docId ? { ...d, status: "pending", error_message: null } : d))
      );
    } catch (error) {
      alert("Failed to queue reprocessing");
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ready":
        return <CheckCircle2 className="w-4 h-4 text-emerald" />;
      case "failed":
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Loader2 className="w-4 h-4 text-emerald animate-spin" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "ready": return "Ready";
      case "failed": return "Failed";
      case "processing": return "Extracting & Embedding...";
      default: return "Queued";
    }
  };

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div 
          key={doc.id} 
          onClick={() => doc.status === "ready" && onViewDocument?.(doc.id)}
          className={`flex items-start gap-3 p-3 bg-white border rounded-xl transition-all shadow-sm
            ${doc.status === 'ready' ? 'cursor-pointer hover:border-emerald/50 hover:shadow-md' : 'opacity-80 border-border'}
            ${doc.status === 'failed' ? 'border-red-100 bg-red-50/30' : ''}
          `}
        >
          <div className={`mt-0.5 p-2 rounded-lg flex-shrink-0 ${doc.status === 'failed' ? 'bg-red-100 text-red-500' : 'bg-emerald-tint text-emerald'}`}>
            <FileText size={16} />
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-[13px] font-medium text-ink truncate" title={doc.filename}>
                {doc.filename}
              </h4>
              <div className="flex items-center gap-1.5 flex-shrink-0 bg-rail px-2 py-0.5 rounded-full border border-border">
                {getStatusIcon(doc.status)}
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted">
                  {getStatusText(doc.status)}
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-3 mt-1.5 text-[11px] text-muted font-mono">
              <span>{formatBytes(doc.file_size)}</span>
              {doc.page_count > 0 && (
                <>
                  <span className="w-1 h-1 rounded-full bg-border" />
                  <span>{doc.page_count} pages</span>
                </>
              )}
            </div>

            {doc.status === "failed" && doc.error_message && (
              <div className="mt-2 text-[11px] text-red-600 bg-white p-2 rounded border border-red-100 font-mono break-words">
                {doc.error_message}
              </div>
            )}
          </div>
          
          {isAdmin && (
             <div className="flex flex-col gap-1 flex-shrink-0 ml-1">
                {doc.status === "failed" && (
                  <button
                    onClick={(e) => handleReprocess(doc.id, e)}
                    className="p-1.5 text-muted hover:text-emerald rounded-md hover:bg-emerald-tint transition-colors border border-transparent hover:border-emerald-border"
                    title="Retry processing"
                  >
                    <RefreshCw size={14} />
                  </button>
                )}
                <button
                  onClick={(e) => handleDelete(doc.id, e)}
                  className="p-1.5 text-muted hover:text-red-500 rounded-md hover:bg-red-50 transition-colors border border-transparent hover:border-red-100"
                  title="Delete document"
                >
                  <Trash2 size={14} />
                </button>
             </div>
          )}
        </div>
      ))}
    </div>
  );
}

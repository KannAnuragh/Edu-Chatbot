"use client";

import ReactMarkdown from "react-markdown";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { api } from "@/lib/api";
import Sidebar from "@/components/sidebar/Sidebar";
import ChatPanel from "@/components/chat/ChatPanel";
import PDFViewerWrapper from "@/components/pdf-viewer/PDFViewerWrapper";
import { type PDFViewerHandle } from "@/components/pdf-viewer/PDFViewer";
import UploadZone from "@/components/upload/UploadZone";
import DocumentList from "@/components/documents/DocumentList";
import { Pencil } from "lucide-react";
import type { Project, Document as DocType, SourceReference } from "@/types";

const preprocessNotes = (content: string) => {
  if (!content) return "";
  const regex = /(\*{0,2})\[([^\]]+?)\s*(?:—|-)\s*[Pp]age\s*(\d+)\](\*{0,2})/g;
  return content.replace(regex, (match, bold1, filename, pageNum, bold2) => {
    const encodedFilename = encodeURIComponent(filename.trim());
    return `${bold1}[${filename.trim()} (p.${pageNum})](#locate:${encodedFilename}?page=${pageNum})${bold2}`;
  });
};

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const isAdmin = user?.role === "admin";

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<DocType[]>([]);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [loading, setLoading] = useState(true);
  const [highlightInfo, setHighlightInfo] = useState<{ pageNumber: number; text: string } | null>(null);
  const pdfViewerRef = useRef<PDFViewerHandle>(null);

  // Mobile state
  const [mobileTab, setMobileTab] = useState<"chat" | "pdf">("chat");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setHighlightInfo(null);
  }, [activeDocId]);

  useEffect(() => {
    const handleGlobalDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer?.types?.includes("Files")) {
        setShowUpload(true);
      }
    };

    document.addEventListener("dragover", handleGlobalDragOver);
    return () => document.removeEventListener("dragover", handleGlobalDragOver);
  }, []);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, authLoading, router]);

  // Redirect admins to the admin dashboard (they can still reach chat via the "Open Chatbot" button)
  useEffect(() => {
    if (!authLoading && user?.role === "admin" && projectId) {
      // Only redirect if they navigated here directly (not via the "Open Chatbot" button)
      // We check for a query param to allow admins to explicitly open chat
      const url = new URL(window.location.href);
      if (!url.searchParams.has("chat")) {
        router.replace(`/dashboard/project/${projectId}/admin`);
      }
    }
  }, [user, authLoading, projectId, router]);

  useEffect(() => {
    if (projectId && isAuthenticated) {
      setActiveDocId(null); // Reset active doc when switching courses
      loadProject();
      loadDocuments();
      if (!isAdmin) {
        api.enrollCourse(projectId).catch(() => {});
      }
    }
  }, [projectId, isAuthenticated, isAdmin]);

  const loadProject = async () => {
    try {
      const p = await api.getProject(projectId);
      setProject(p);
    } catch {
      router.push("/dashboard");
    }
  };

  const handleRenameCourse = async () => {
    if (!project || !isAdmin) return;
    const newTitle = prompt("Enter new course name:", project.title);
    if (!newTitle || newTitle.trim() === "" || newTitle.trim() === project.title) return;
    try {
      const updated = await api.updateCourse(project.id, newTitle.trim());
      setProject((prev) => prev ? { ...prev, title: updated.title } : null);
    } catch (error) {
      console.error("Failed to rename course", error);
      alert("Failed to rename course");
    }
  };

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const data = await api.getDocuments(projectId);
      setDocuments(data.documents);
      const readyDoc = data.documents.find((d: DocType) => d.status?.toLowerCase() === "ready");
      if (readyDoc && !activeDocId) setActiveDocId(readyDoc.id);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const handleUploadComplete = useCallback(
    (doc: DocType) => {
      setDocuments((prev) => [doc, ...prev]);
      setShowUpload(false);
    },
    []
  );

  const handleDocumentsChange = useCallback(
    (updatedDocs: DocType[]) => {
      setDocuments(updatedDocs);
      const readyDoc = updatedDocs.find((d) => d.status === "ready");
      if (readyDoc && !activeDocId) setActiveDocId(readyDoc.id);
    },
    [activeDocId]
  );

  const handleSourceClick = useCallback(
    (source: SourceReference) => {
      const doc = documents.find((d) => d.id === source.document_id || d.filename === source.filename);
      if (doc) {
        setActiveDocId(doc.id);
        setHighlightInfo({ pageNumber: source.page_number, text: source.chunk_text });
        setMobileTab("pdf");
      }
    },
    [documents]
  );

  const handleSelectProject = (p: Project) => {
    router.push(`/dashboard/project/${p.id}`);
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-canvas">
        <div className="flex items-center gap-3">
          <div className="typing-dot" />
          <div className="typing-dot" />
          <div className="typing-dot" />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <>
      {/* ======== DESKTOP LAYOUT (≥768px) ======== */}
      <div className="hidden md:flex h-screen w-full bg-canvas overflow-hidden">
        {/* Zone 1: Icon Rail */}
        <Sidebar activeProjectId={projectId} />

        {/* Zone 2: Chat Column */}
        <div className="w-[452px] flex-shrink-0 flex flex-col border-r border-border bg-canvas relative">
          {/* Chat Header */}
          <div className="py-2 border-b border-border bg-canvas/90 backdrop-blur-md flex items-center justify-between px-4 z-20 flex-shrink-0 min-h-[48px]">
            <div className="flex flex-col min-w-0 justify-center mr-2">
              <div className="flex items-center gap-1.5 min-w-0">
                <h2 className="font-heading font-semibold text-[14px] truncate text-ink">{project?.title || "Course"}</h2>
              </div>
              {project?.description && (
                <p className="text-[11px] text-muted truncate max-w-[280px]" title={project.description}>
                  {project.description}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-tint border border-emerald-border">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald animate-pulse" />
              </div>
              <span className="font-mono text-[10px] text-muted whitespace-nowrap">
                {documents.length} pdfs
              </span>
            </div>
          </div>

          {/* Chat Thread */}
          <div className="flex-1 overflow-hidden relative">
            <Suspense fallback={<div className="flex items-center justify-center h-full"><div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" /></div>}>
              <ChatPanel
                projectId={projectId}
                onSourceClick={handleSourceClick}
                onAttachClick={isAdmin ? () => setShowUpload((prev) => !prev) : undefined}
              />
            </Suspense>
          </div>
        </div>

        {/* Zone 3: Live Preview Panel */}
        <div className="flex-1 bg-preview overflow-hidden flex flex-col relative">
          {/* Tab Content */}
          <div className="flex-1 overflow-hidden relative">
            <PDFViewerWrapper
              ref={pdfViewerRef}
              documents={documents}
              activeDocumentId={activeDocId}
              onDocumentSelect={(id) => {
                setActiveDocId(id);
                setHighlightInfo(null);
              }}
              highlightInfo={highlightInfo}
            />
          </div>
        </div>
      </div>

      {/* ======== MOBILE LAYOUT (<768px) ======== */}
      <div className="flex md:hidden flex-col h-screen w-full bg-canvas overflow-hidden">
        {/* Mobile Sidebar Drawer */}
        <Sidebar
          activeProjectId={projectId}
          isMobileOpen={mobileMenuOpen}
          onMobileClose={() => setMobileMenuOpen(false)}
        />

        {/* Mobile Header (h-12 aligned) */}
        <div className="h-12 flex-shrink-0 px-3 border-b border-border bg-canvas/95 backdrop-blur-md flex items-center justify-between pt-safe z-30">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="p-1.5 rounded-lg text-muted hover:bg-rail hover:text-ink transition-colors flex-shrink-0"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
            </button>
            <h2 className="font-heading font-medium text-[14px] text-ink truncate min-w-0">{project?.title || "Course"}</h2>
            {isAdmin && project && (
              <button
                onClick={handleRenameCourse}
                className="p-1 text-muted hover:text-emerald rounded hover:bg-rail transition-colors flex-shrink-0"
                title="Rename Course"
              >
                <Pencil size={13} />
              </button>
            )}
          </div>
          <div className="flex items-center flex-shrink-0">
            <button
              onClick={() => setMobileTab("pdf")}
              className="px-2.5 py-1.5 text-[11px] font-medium text-emerald bg-emerald-tint border border-emerald-border rounded shadow-sm flex items-center gap-1 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
              View PDF
            </button>
          </div>
        </div>


        {/* Mobile Tab Content (full screen) */}
        <div className="flex-1 overflow-hidden relative">
          {/* Chat Tab */}
          <div className={`absolute inset-0 ${mobileTab === "chat" ? "flex flex-col" : "hidden"}`}>
            <Suspense fallback={<div className="flex items-center justify-center h-full"><div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" /></div>}>
              <ChatPanel
                projectId={projectId}
                onSourceClick={handleSourceClick}
                onAttachClick={isAdmin ? () => setShowUpload((prev) => !prev) : undefined}
              />
            </Suspense>
          </div>

          {/* PDF Tab */}
          <div className={`absolute inset-0 bg-canvas z-40 ${mobileTab === "pdf" ? "flex flex-col" : "hidden"}`}>
            <div className="md:hidden h-12 flex-shrink-0 flex items-center px-3 border-b border-border bg-canvas/95 backdrop-blur-md">
               <button onClick={() => setMobileTab("chat")} className="flex items-center gap-1 text-emerald font-medium text-[13px] hover:opacity-80 transition-opacity">
                 <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7"/></svg>
                 Back to Chat
               </button>
            </div>
            <div className="flex-1 relative">
              <PDFViewerWrapper
                ref={pdfViewerRef}
                documents={documents}
                activeDocumentId={activeDocId}
                onDocumentSelect={(id) => {
                  setActiveDocId(id);
                  setHighlightInfo(null);
                }}
                highlightInfo={highlightInfo}
              />
            </div>
          </div>


        </div>
      </div>

      {/* ======== SOURCE LIST & UPLOAD BOTTOM SHEET DRAWER ======== */}
      {showUpload && (
        <div className="fixed inset-0 z-50 flex flex-col justify-end">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
            onClick={() => setShowUpload(false)}
          />

          {/* Drawer Container */}
          <div className="relative w-full max-w-lg mx-auto bg-canvas border-t border-x border-border rounded-t-3xl shadow-2xl overflow-hidden flex flex-col max-h-[60vh] animate-slide-in-up">
            {/* Drawer Header */}
            <div className="px-5 py-3 border-b border-border flex items-center justify-between bg-rail/60">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald" />
                <h3 className="font-heading font-medium text-ink text-sm">Course PDFs & Upload</h3>
              </div>
              <button
                onClick={() => setShowUpload(false)}
                className="p-1.5 text-muted hover:text-ink rounded-lg hover:bg-rail transition-colors"
                title="Close"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-4 overflow-y-auto custom-scrollbar space-y-4">
              {/* Document List */}
              {documents.length > 0 ? (
                <div>
                  <h4 className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">Attached PDFs ({documents.length})</h4>
                  <DocumentList
                    projectId={projectId}
                    documents={documents}
                    onDocumentsChange={handleDocumentsChange}
                    onViewDocument={(docId) => {
                      setActiveDocId(docId);
                      setMobileTab("pdf");
                      setShowUpload(false);
                    }}
                  />
                </div>
              ) : (
                <div className="text-center py-4 text-xs text-muted">No PDFs attached yet.</div>
              )}

              {/* Upload PDF in one line at the bottom */}
              {isAdmin && (
                <div className="pt-2 border-t border-border">
                  <UploadZone projectId={projectId} onUploadComplete={handleUploadComplete} />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

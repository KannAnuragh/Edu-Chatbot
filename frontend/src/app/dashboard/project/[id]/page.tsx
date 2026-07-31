"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { api } from "@/lib/api";
import Sidebar from "@/components/sidebar/Sidebar";
import ChatPanel from "@/components/chat/ChatPanel";
import UploadZone from "@/components/upload/UploadZone";
import DocumentList from "@/components/documents/DocumentList";
import { Pencil, FileText, Settings as SettingsIcon } from "lucide-react";
import type { Project, Document as DocType, SourceReference } from "@/types";

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const isAdmin = user?.role === "admin";

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<DocType[]>([]);
  const [showUpload, setShowUpload] = useState(false);
  const [loading, setLoading] = useState(true);

  // Mobile state
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleGlobalDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer?.types?.includes("Files") && isAdmin) {
        setShowUpload(true);
      }
    };

    document.addEventListener("dragover", handleGlobalDragOver);
    return () => document.removeEventListener("dragover", handleGlobalDragOver);
  }, [isAdmin]);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, authLoading, router]);

  // Redirect admins to the admin dashboard if navigated without explicit chat flag
  useEffect(() => {
    if (!authLoading && user?.role === "admin" && projectId) {
      const url = new URL(window.location.href);
      if (!url.searchParams.has("chat")) {
        router.replace(`/dashboard/project/${projectId}/admin`);
      }
    }
  }, [user, authLoading, projectId, router]);

  useEffect(() => {
    if (projectId && isAuthenticated) {
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
      setProject((prev) => (prev ? { ...prev, title: updated.title } : null));
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
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const handleUploadComplete = useCallback(
    (doc: DocType) => {
      setDocuments((prev) => [doc, ...prev]);
    },
    []
  );

  const handleDocumentsChange = useCallback(
    (updatedDocs: DocType[]) => {
      setDocuments(updatedDocs);
    },
    []
  );

  const handleSourceClick = useCallback(
    (source: SourceReference) => {
      // Open documents sheet if clicked
      setShowUpload(true);
    },
    []
  );

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

        {/* Zone 2: Main Full-Width Chat Column */}
        <div className="flex-1 flex flex-col h-full bg-canvas relative overflow-hidden">
          {/* Top Header */}
          <div className="py-2.5 border-b border-border bg-canvas/90 backdrop-blur-md flex items-center justify-between px-6 z-20 flex-shrink-0 min-h-[52px]">
            <div className="flex flex-col min-w-0 justify-center mr-4">
              <div className="flex items-center gap-2 min-w-0">
                <h2 className="font-heading font-semibold text-[15px] truncate text-ink">
                  {project?.title || "Course"}
                </h2>
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
              {project?.description && (
                <p className="text-[12px] text-muted truncate max-w-[500px]" title={project.description}>
                  {project.description}
                </p>
              )}
            </div>

            <div className="flex items-center gap-3 flex-shrink-0">
              {/* Document Count Badge */}
              <button
                onClick={() => setShowUpload(true)}
                className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-tint border border-emerald-border hover:bg-emerald-tint/80 transition-colors"
                title="View attached PDFs"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-emerald animate-pulse" />
                <span className="font-mono text-[11px] text-emerald-deep font-medium">
                  {documents.length} PDF{documents.length !== 1 ? "s" : ""}
                </span>
              </button>

              {isAdmin && (
                <button
                  onClick={() => router.push(`/dashboard/project/${projectId}/admin`)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-muted hover:text-ink hover:bg-rail border border-border transition-colors"
                  title="Course Settings"
                >
                  <SettingsIcon size={14} />
                  Course Settings
                </button>
              )}
            </div>
          </div>

          {/* Main Chat Thread */}
          <div className="flex-1 overflow-hidden relative">
            <Suspense
              fallback={
                <div className="flex items-center justify-center h-full">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              }
            >
              <ChatPanel
                projectId={projectId}
                onSourceClick={handleSourceClick}
                onAttachClick={isAdmin ? () => setShowUpload((prev) => !prev) : undefined}
              />
            </Suspense>
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

        {/* Mobile Header */}
        <div className="h-12 flex-shrink-0 px-3 border-b border-border bg-canvas/95 backdrop-blur-md flex items-center justify-between pt-safe z-30">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="p-1.5 rounded-lg text-muted hover:bg-rail hover:text-ink transition-colors flex-shrink-0"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h2 className="font-heading font-medium text-[14px] text-ink truncate min-w-0">
              {project?.title || "Course"}
            </h2>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => setShowUpload(true)}
              className="px-2.5 py-1.5 text-[11px] font-medium text-emerald bg-emerald-tint border border-emerald-border rounded shadow-sm flex items-center gap-1 transition-colors"
            >
              <FileText size={13} />
              {documents.length} PDF{documents.length !== 1 ? "s" : ""}
            </button>
          </div>
        </div>

        {/* Mobile Chat Thread */}
        <div className="flex-1 overflow-hidden relative">
          <Suspense
            fallback={
              <div className="flex items-center justify-center h-full">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            }
          >
            <ChatPanel
              projectId={projectId}
              onSourceClick={handleSourceClick}
              onAttachClick={isAdmin ? () => setShowUpload((prev) => !prev) : undefined}
            />
          </Suspense>
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
                <h3 className="font-heading font-medium text-ink text-sm">Course PDFs & Documents</h3>
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
                  <h4 className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
                    Attached PDFs ({documents.length})
                  </h4>
                  <DocumentList
                    projectId={projectId}
                    documents={documents}
                    onDocumentsChange={handleDocumentsChange}
                    onViewDocument={() => setShowUpload(false)}
                  />
                </div>
              ) : (
                <div className="text-center py-4 text-xs text-muted">No PDFs attached yet.</div>
              )}

              {/* Upload PDF section at the bottom for admin */}
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

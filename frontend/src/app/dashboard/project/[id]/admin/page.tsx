"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { api } from "@/lib/api";
import UploadZone from "@/components/upload/UploadZone";
import DocumentList from "@/components/documents/DocumentList";
import {
  Pencil,
  FileText,
  Users,
  MessageSquare,
  ArrowRight,
  Save,
  X,
  Upload,
  Bot,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Layers,
  Trash2,
} from "lucide-react";
import type { Project, Document as DocType } from "@/types";
import { getBadgeGradient } from "../../../page";

interface CourseStats {
  document_count: number;
  total_pages: number;
  enrolled_students: number;
  conversation_count: number;
}

export default function AdminCoursePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { user, isAuthenticated, loading: authLoading } = useAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<DocType[]>([]);
  const [stats, setStats] = useState<CourseStats | null>(null);
  const [loading, setLoading] = useState(true);

  // Sidebar state
  const [sidebarMinimized, setSidebarMinimized] = useState(true);

  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth >= 768) {
      setSidebarMinimized(false);
    }
  }, []);

  // Editing states
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState("");
  const [savingDesc, setSavingDesc] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!authLoading && user && user.role !== "admin") {
      router.push(`/dashboard/project/${projectId}`);
    }
  }, [user, authLoading, projectId, router]);

  useEffect(() => {
    if (projectId && isAuthenticated) {
      loadAll();
    }
  }, [projectId, isAuthenticated]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [p, docData, statsData] = await Promise.all([
        api.getProject(projectId),
        api.getDocuments(projectId),
        api.getCourseStats(projectId),
      ]);
      setProject(p);
      setDocuments(docData.documents);
      setStats(statsData);
    } catch {
      router.push("/dashboard");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTitle = async () => {
    if (!project || !titleDraft.trim() || titleDraft.trim() === project.title) {
      setEditingTitle(false);
      return;
    }
    try {
      const updated = await api.updateCourse(project.id, titleDraft.trim());
      setProject((prev) => (prev ? { ...prev, title: updated.title } : null));
      setEditingTitle(false);
    } catch {
      alert("Failed to rename course");
    }
  };

  const handleSaveDescription = async () => {
    if (!project) return;
    setSavingDesc(true);
    try {
      await api.updateCourse(project.id, undefined, descDraft);
      setProject((prev) => (prev ? { ...prev, description: descDraft } : null));
      setEditingDesc(false);
    } catch {
      alert("Failed to save description");
    } finally {
      setSavingDesc(false);
    }
  };

  const handleUpdateBadgeColor = async (color: string) => {
    if (!project) return;
    try {
      await api.updateCourse(project.id, undefined, undefined, color);
      setProject((prev) => (prev ? { ...prev, badge_color: color } : null));
    } catch {
      alert("Failed to update badge color");
    }
  };

  const handleDeleteCourse = async () => {
    if (!project) return;
    if (
      !confirm(
        `Are you sure you want to delete "${project.title}"? All uploaded documents and chat history for this course will be permanently removed.`
      )
    ) {
      return;
    }
    try {
      await api.deleteCourse(project.id);
      router.push("/dashboard");
    } catch {
      alert("Failed to delete course");
    }
  };

  const handleUploadComplete = useCallback((doc: DocType) => {
    setDocuments((prev) => [doc, ...prev]);
    setStats((prev) =>
      prev ? { ...prev, document_count: prev.document_count + 1 } : prev
    );
  }, []);

  const handleDocumentsChange = useCallback((updatedDocs: DocType[]) => {
    setDocuments(updatedDocs);
  }, []);

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

  if (!isAuthenticated || !project) return null;

  const statCards = [
    {
      label: "Documents",
      value: stats?.document_count ?? 0,
      icon: FileText,
      color: "text-emerald",
      bg: "bg-emerald-tint",
      borderColor: "border-emerald-border",
    },
    {
      label: "Students Enrolled",
      value: stats?.enrolled_students ?? 0,
      icon: Users,
      color: "text-violet-600",
      bg: "bg-violet-50",
      borderColor: "border-violet-200",
    },
    {
      label: "Conversations",
      value: stats?.conversation_count ?? 0,
      icon: MessageSquare,
      color: "text-amber-600",
      bg: "bg-amber-50",
      borderColor: "border-amber-200",
    },
  ];

  return (
    <div className="flex flex-col md:flex-row h-[100dvh] bg-preview md:overflow-hidden">

      {/* Custom Left Sidebar Panel */}
      <div
        className={`flex flex-col bg-white border-b md:border-b-0 md:border-r border-border transition-all duration-300 relative z-30 flex-shrink-0 ${
          sidebarMinimized ? "hidden md:flex md:w-20" : "w-full md:w-80 h-[50vh] md:h-auto"
        }`}
      >
        {/* Sidebar Header: Back & Minimize */}
        <div className={`border-b border-border flex items-center px-4 flex-shrink-0 ${sidebarMinimized ? "flex-col justify-center gap-3 py-4" : "h-14 justify-between"}`}>
          <button
            onClick={() => router.push("/dashboard")}
            className="flex items-center gap-2 text-sm text-muted hover:text-ink font-medium transition-colors"
            title="Back to Dashboard"
          >
            <ArrowLeft size={16} />
            {!sidebarMinimized && "Dashboard"}
          </button>
          <button
            onClick={() => setSidebarMinimized(!sidebarMinimized)}
            className={`p-1.5 rounded-lg text-muted hover:bg-rail hover:text-ink transition-colors`}
            title={sidebarMinimized ? "Expand Sidebar" : "Minimize Sidebar"}
          >
            {sidebarMinimized ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        {/* Sidebar Body: Badge, Title, Description */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className={`flex flex-col p-6 ${sidebarMinimized ? "items-center px-2" : ""}`}>

            {/* Colored Badge */}
            <div
              className={`rounded-2xl bg-gradient-to-br ${getBadgeGradient(project.badge_color)} shadow-md flex items-center justify-center text-white mb-6 flex-shrink-0 transition-all ${sidebarMinimized ? "w-12 h-12" : "w-20 h-20"
                }`}
              title="Course Badge"
            >
              <span className={`font-heading font-bold ${sidebarMinimized ? "text-xl" : "text-3xl"}`}>
                {project.title.charAt(0).toUpperCase()}
              </span>
            </div>

            {!sidebarMinimized && (
              <div className="space-y-6 w-full animate-fade-in">
                {/* Editable Title */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-muted">Course Title</h3>
                    {!editingTitle && (
                      <button
                        onClick={() => {
                          setTitleDraft(project.title);
                          setEditingTitle(true);
                        }}
                        className="text-muted hover:text-emerald p-1 rounded hover:bg-emerald-tint transition-colors"
                      >
                        <Pencil size={12} />
                      </button>
                    )}
                  </div>

                  {editingTitle ? (
                    <div className="flex items-start gap-2">
                      <input
                        type="text"
                        value={titleDraft}
                        onChange={(e) => setTitleDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveTitle();
                          if (e.key === "Escape") setEditingTitle(false);
                        }}
                        className="w-full font-heading font-semibold text-lg text-ink bg-transparent border-b-2 border-emerald focus:outline-none py-0.5"
                        autoFocus
                      />
                      <button onClick={handleSaveTitle} className="p-1.5 text-emerald hover:bg-emerald-tint rounded">
                        <Save size={14} />
                      </button>
                      <button onClick={() => setEditingTitle(false)} className="p-1.5 text-muted hover:bg-rail rounded">
                        <X size={14} />
                      </button>
                    </div>
                  ) : (
                    <h1 className="font-heading font-semibold text-2xl text-ink leading-tight break-words">
                      {project.title}
                    </h1>
                  )}
                </div>

                <hr className="border-border" />

                {/* Editable Description */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-muted">Description</h3>
                    {!editingDesc && (
                      <button
                        onClick={() => {
                          setDescDraft(project.description || "");
                          setEditingDesc(true);
                        }}
                        className="text-muted hover:text-emerald p-1 rounded hover:bg-emerald-tint transition-colors"
                      >
                        <Pencil size={12} />
                      </button>
                    )}
                  </div>

                  {editingDesc ? (
                    <div className="space-y-3">
                      <textarea
                        value={descDraft}
                        onChange={(e) => setDescDraft(e.target.value)}
                        rows={6}
                        className="w-full rounded-lg border border-border bg-canvas px-3 py-2 text-sm text-ink focus:border-emerald focus:ring-1 focus:ring-emerald outline-none transition-all resize-none"
                        placeholder="Enter course description..."
                        autoFocus
                      />
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => setEditingDesc(false)} className="px-3 py-1.5 rounded-lg text-xs font-medium text-muted hover:bg-rail">
                          Cancel
                        </button>
                        <button
                          onClick={handleSaveDescription}
                          disabled={savingDesc}
                          className="bg-emerald text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-emerald-deep flex items-center gap-1.5"
                        >
                          {savingDesc ? "Saving..." : <><Save size={12} /> Save</>}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap break-words">
                      {project.description || <span className="italic opacity-60">No description provided.</span>}
                    </p>
                  )}
                </div>

                <hr className="border-border" />

                {/* Badge Color Picker */}
                <div>
                  <h3 className="text-xs font-mono uppercase tracking-wider text-muted mb-3">Badge Color</h3>
                  <div className="flex flex-wrap gap-2">
                    {['emerald', 'blue', 'purple', 'rose', 'amber', 'indigo'].map((color) => (
                      <button
                        key={color}
                        onClick={() => handleUpdateBadgeColor(color)}
                        className={`w-8 h-8 rounded-full shadow-sm hover:scale-110 transition-transform ${project.badge_color === color ? 'ring-2 ring-ink ring-offset-2 ring-offset-white' : ''} bg-gradient-to-br ${getBadgeGradient(color)}`}
                        title={color.charAt(0).toUpperCase() + color.slice(1)}
                      />
                    ))}
                  </div>
                </div>

                <hr className="border-border" />

                {/* Delete Course */}
                <div>
                  <button
                    onClick={handleDeleteCourse}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 transition-colors shadow-sm"
                  >
                    <Trash2 size={14} />
                    Delete Course
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content (Right Panel) */}
      <div className="flex-1 flex flex-col overflow-hidden bg-preview relative">
        {/* Top Header Bar for Main Content */}
        <div className="h-14 bg-white/80 backdrop-blur-md flex items-center justify-between px-4 md:px-6 flex-shrink-0 z-20 shadow-sm border-b border-border/50">
          <div className="flex items-center gap-2 md:hidden">
            <button
              onClick={() => setSidebarMinimized(!sidebarMinimized)}
              className="p-1.5 rounded-lg text-muted hover:bg-rail hover:text-ink transition-colors flex-shrink-0"
            >
              <Layers size={20} />
            </button>
            <h2 className="font-heading font-medium text-[14px] text-ink truncate min-w-0">Settings</h2>
          </div>
          <div className="flex items-center gap-3 ml-auto">
            <button
              onClick={handleDeleteCourse}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 transition-colors"
              title="Delete Course"
            >
              <Trash2 size={14} />
              Delete Course
            </button>
            <button
              onClick={() => router.push(`/dashboard/project/${projectId}?chat=1`)}
              className="emerald-btn flex items-center gap-2 px-4 py-2 rounded-lg text-sm shadow-emerald-500/20 shadow-lg hover:shadow-emerald-500/40"
            >
              <Bot size={16} />
              Open Chatbot
            </button>
          </div>
        </div>

        {/* Scrollable Main Area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="max-w-5xl mx-auto px-6 lg:px-10 py-8 space-y-8">

            {/* Stats Row */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-in-up">
              {statCards.map((stat) => (
                <div
                  key={stat.label}
                  className={`bg-white rounded-2xl border ${stat.borderColor} p-6 flex items-start gap-4 shadow-sm hover:shadow-md transition-shadow group`}
                >
                  <div className={`w-12 h-12 rounded-xl ${stat.bg} flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform`}>
                    <stat.icon size={24} className={stat.color} />
                  </div>
                  <div>
                    <p className="text-3xl font-heading font-bold text-ink">
                      {stat.value}
                    </p>
                    <p className="text-sm text-muted font-medium mt-1">
                      {stat.label}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Documents Section */}
            <div
              className="bg-white rounded-2xl border border-border shadow-sm animate-fade-in-up"
              style={{ animationDelay: "0.1s" }}
            >
              <div className="p-6 border-b border-border bg-rail/30 rounded-t-2xl">
                <h2 className="font-heading font-semibold text-ink text-lg flex items-center gap-2">
                  <FileText size={20} className="text-emerald" />
                  Course Documents
                  <span className="ml-2 text-xs font-mono font-medium text-emerald bg-emerald-tint px-2.5 py-0.5 rounded-full border border-emerald-border">
                    {documents.length} PDF{documents.length !== 1 ? 's' : ''}
                  </span>
                </h2>
                <p className="text-sm text-muted mt-1">
                  Upload PDFs to train the AI chatbot. Students can query these documents instantly.
                </p>
              </div>

              <div className="p-6 space-y-6">
                <UploadZone
                  projectId={projectId}
                  onUploadComplete={handleUploadComplete}
                />

                {documents.length > 0 ? (
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-muted mb-4 px-1">
                      Uploaded Files
                    </h3>
                    <DocumentList
                      projectId={projectId}
                      documents={documents}
                      onDocumentsChange={handleDocumentsChange}
                      onViewDocument={(docId) => {
                        router.push(`/dashboard/project/${projectId}?chat=1`);
                      }}
                    />
                  </div>
                ) : (
                  <div className="text-center py-12 px-4 rounded-xl border border-dashed border-border bg-canvas/50">
                    <div className="w-16 h-16 rounded-2xl bg-white border border-border flex items-center justify-center mx-auto mb-4 shadow-sm">
                      <Upload size={24} className="text-muted" />
                    </div>
                    <p className="font-heading font-medium text-ink mb-1">
                      No documents yet
                    </p>
                    <p className="text-sm text-muted">
                      Upload your first PDF to generate answers.
                    </p>
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}

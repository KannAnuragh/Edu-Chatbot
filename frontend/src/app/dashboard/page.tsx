"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  BookOpen,
  FileText,
  Users,
  Plus,
  ArrowRight,
  LogOut,
  Activity,
  Trash2,
} from "lucide-react";
import type { Project } from "@/types";

interface GlobalStats {
  total_pdfs: number;
  total_students: number;
  active_students: number;
}

// Helper to get the correct Tailwind gradient classes from a color name
export const getBadgeGradient = (color?: string) => {
  const map: Record<string, string> = {
    emerald: "from-emerald-500 to-blue-400", // Default
    blue: "from-blue-500 to-cyan-400",
    purple: "from-purple-500 to-pink-400",
    rose: "from-rose-500 to-orange-400",
    amber: "from-amber-500 to-yellow-400",
    indigo: "from-indigo-500 to-purple-400",
  };
  return map[color || "emerald"] || map["emerald"];
};

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  const [courses, setCourses] = useState<Project[]>([]);
  const [globalStats, setGlobalStats] = useState<GlobalStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [isAdmin]);

  const loadData = async () => {
    try {
      const [coursesData, statsData] = await Promise.all([
        api.getCourses(),
        isAdmin ? api.getGlobalStats() : Promise.resolve(null),
      ]);
      setCourses(coursesData.courses || []);
      if (statsData) setGlobalStats(statsData);
    } catch (error) {
      console.error("Failed to load dashboard data", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCourse = (course: any) => {
    if (isAdmin) {
      router.push(`/dashboard/project/${course.id}/admin`);
    } else {
      router.push(`/dashboard/project/${course.id}`);
    }
  };

  const handleCreateCourse = async () => {
    try {
      const title = `Course ${courses.length + 1}`;
      const project = await api.createCourse(title, "A new learning course");
      router.push(`/dashboard/project/${project.id}/admin`);
    } catch (error) {
      console.error("Failed to create course", error);
    }
  };

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const handleDeleteCourse = async (e: React.MouseEvent, courseId: string) => {
    e.stopPropagation();
    if (
      !confirm(
        "Are you sure you want to delete this course? All uploaded PDFs and chat data will be deleted."
      )
    ) {
      return;
    }
    try {
      await api.deleteCourse(courseId);
      setCourses((prev) => prev.filter((c) => c.id !== courseId));
    } catch (error) {
      console.error("Failed to delete course", error);
      alert("Failed to delete course");
    }
  };

  return (
    <div className="flex flex-col h-screen bg-canvas overflow-hidden">
      {/* Top Header */}
      <div className="h-14 border-b border-border bg-white/80 backdrop-blur-md flex items-center justify-between px-6 flex-shrink-0 z-20 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-tint border border-emerald-border flex items-center justify-center">
            <BookOpen size={16} className="text-emerald" />
          </div>
          <h1 className="font-heading font-semibold text-lg text-ink">
            {isAdmin ? "Admin Dashboard" : "My Courses"}
          </h1>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center gap-2 text-sm text-muted mr-4">
            <span className="w-2 h-2 rounded-full bg-emerald"></span>
            {user?.name}
          </div>
          {isAdmin && (
            <button
              onClick={handleCreateCourse}
              className="emerald-btn flex items-center gap-2 px-4 py-2 rounded-lg text-sm shadow-emerald-500/20 shadow-sm"
            >
              <Plus size={16} />
              New Course
            </button>
          )}
          <button
            onClick={handleLogout}
            className="p-2 text-muted hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors border border-transparent hover:border-red-200"
            title="Logout"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-6xl mx-auto px-6 py-8">
          
          {/* Admin Global Stats */}
          {isAdmin && globalStats && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-10 animate-fade-in-up">
              <div className="bg-white rounded-2xl border border-border p-6 shadow-sm flex items-start gap-4 hover:shadow-md transition-shadow">
                <div className="w-12 h-12 rounded-xl bg-emerald-tint flex items-center justify-center flex-shrink-0">
                  <FileText size={24} className="text-emerald" />
                </div>
                <div>
                  <p className="text-3xl font-heading font-bold text-ink">
                    {globalStats.total_pdfs}
                  </p>
                  <p className="text-sm text-muted font-medium mt-1">
                    Total PDFs Added
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-border p-6 shadow-sm flex items-start gap-4 hover:shadow-md transition-shadow">
                <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
                  <Users size={24} className="text-blue-600" />
                </div>
                <div>
                  <p className="text-3xl font-heading font-bold text-ink">
                    {globalStats.total_students}
                  </p>
                  <p className="text-sm text-muted font-medium mt-1">
                    Total Students
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-border p-6 shadow-sm flex items-start gap-4 hover:shadow-md transition-shadow">
                <div className="w-12 h-12 rounded-xl bg-violet-50 flex items-center justify-center flex-shrink-0">
                  <Activity size={24} className="text-violet-600" />
                </div>
                <div>
                  <p className="text-3xl font-heading font-bold text-ink">
                    {globalStats.active_students}
                  </p>
                  <p className="text-sm text-muted font-medium mt-1">
                    Active Students Right Now
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Courses Grid */}
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="flex items-center gap-3">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            </div>
          ) : courses.length === 0 ? (
            <div className="text-center py-20 animate-fade-in-up">
              <div className="w-20 h-20 bg-rail rounded-2xl flex items-center justify-center mx-auto mb-6">
                <BookOpen size={32} className="text-muted" />
              </div>
              <h3 className="font-heading font-semibold text-ink text-lg mb-2">
                No courses yet
              </h3>
              <p className="text-sm text-muted mb-6">
                {isAdmin
                  ? "Create your first course to get started."
                  : "No courses are available yet. Check back later."}
              </p>
              {isAdmin && (
                <button
                  onClick={handleCreateCourse}
                  className="emerald-btn px-6 py-2.5 rounded-lg text-sm inline-flex items-center gap-2"
                >
                  <Plus size={16} />
                  Create Your First Course
                </button>
              )}
            </div>
          ) : (
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-muted mb-4 font-medium px-1">
                {isAdmin ? "Your Courses" : "Available Courses"} ({courses.length})
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {courses.map((course, idx) => (
                  <button
                    key={course.id}
                    onClick={() => handleSelectCourse(course)}
                    className="bg-white rounded-2xl border border-border p-6 text-left hover:shadow-lg hover:border-emerald/30 transition-all group animate-fade-in-up flex flex-col h-full"
                    style={{ animationDelay: `${idx * 0.05}s` }}
                  >
                    <div className="flex items-start justify-between mb-4">
                      {/* Gradient Badge for Course */}
                      <div className={`w-12 h-12 rounded-xl bg-gradient-to-tl ${getBadgeGradient(course.badge_color)} shadow-sm flex items-center justify-center text-white group-hover:scale-110 transition-transform`}>
                        <span className="font-heading font-bold text-xl">
                          {course.title.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {isAdmin && (
                          <div
                            onClick={(e) => handleDeleteCourse(e, course.id)}
                            className="w-8 h-8 rounded-full bg-canvas flex items-center justify-center hover:bg-red-50 text-muted hover:text-red-600 transition-colors z-10"
                            title="Delete Course"
                          >
                            <Trash2 size={15} />
                          </div>
                        )}
                        <div className="w-8 h-8 rounded-full bg-canvas flex items-center justify-center group-hover:bg-emerald-tint transition-colors">
                          <ArrowRight
                            size={16}
                            className="text-muted group-hover:text-emerald group-hover:translate-x-0.5 transition-all"
                          />
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex-1">
                      <h4 className="font-heading font-bold text-ink text-lg mb-2 line-clamp-1">
                        {course.title}
                      </h4>
                      <p className="text-sm text-muted line-clamp-2 mb-4 leading-relaxed">
                        {course.description || <span className="italic opacity-60">No description provided.</span>}
                      </p>
                    </div>

                    <div className="flex items-center gap-3 text-[11px] font-medium text-muted bg-rail/50 px-3 py-2 rounded-lg mt-auto">
                      <span className="flex items-center gap-1.5">
                        <FileText size={14} className="text-emerald" />
                        {course.document_count ?? 0} docs
                      </span>
                      <span className="text-border">•</span>
                      <span>
                        {new Date(course.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                ))}

                {/* Add Course Card (admin only) */}
                {isAdmin && (
                  <button
                    onClick={handleCreateCourse}
                    className="rounded-2xl border-2 border-dashed border-border p-6 text-center hover:border-emerald/40 hover:bg-emerald-tint/30 transition-all flex flex-col items-center justify-center min-h-[220px] group animate-fade-in-up"
                    style={{
                      animationDelay: `${courses.length * 0.05}s`,
                    }}
                  >
                    <div className="w-14 h-14 rounded-full bg-white border border-border flex items-center justify-center mb-4 shadow-sm group-hover:border-emerald/40 group-hover:bg-emerald-tint group-hover:scale-110 transition-all">
                      <Plus
                        size={24}
                        className="text-muted group-hover:text-emerald transition-colors"
                      />
                    </div>
                    <span className="text-base font-heading font-semibold text-ink group-hover:text-emerald transition-colors">
                      Create New Course
                    </span>
                    <span className="text-sm text-muted mt-1">
                      Upload PDFs and train the AI
                    </span>
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

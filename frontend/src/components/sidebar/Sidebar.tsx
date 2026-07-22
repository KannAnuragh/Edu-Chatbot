"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { api } from "@/lib/api";
import { type Project, type Conversation } from "@/types";
import { cn } from "@/lib/utils";
import { Plus, LayoutDashboard, User, LogOut, MessageSquare, ChevronLeft, ChevronRight, ArrowLeft } from "lucide-react";

interface SidebarProps {
  activeProjectId?: string;
  isMobileOpen?: boolean;
  onMobileClose?: () => void;
}

export default function Sidebar({ activeProjectId, isMobileOpen, onMobileClose }: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [minimized, setMinimized] = useState(false);
  
  const { user, logout } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeConvId = searchParams.get("conv");

  useEffect(() => {
    if (activeProjectId) {
      loadConversations(activeProjectId);
    }
  }, [activeProjectId]);

  const loadConversations = async (projectId: string) => {
    try {
      setLoading(true);
      const data = await api.getConversations(projectId);
      setConversations(data.conversations);
    } catch (error) {
      console.error("Failed to load conversations", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectConversation = (conv: Conversation) => {
    router.push(`/dashboard/project/${activeProjectId}?conv=${conv.id}`);
    if (isMobileOpen && onMobileClose) onMobileClose();
  };

  const handleNewChat = () => {
    router.push(`/dashboard/project/${activeProjectId}`);
    if (isMobileOpen && onMobileClose) onMobileClose();
  };

  const groupedConversations = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    const groups: Record<string, Conversation[]> = {
      "Today": [],
      "Yesterday": [],
      "Previous 7 Days": [],
      "Older": []
    };

    conversations.forEach(conv => {
      const d = new Date(conv.created_at);
      d.setHours(0, 0, 0, 0);
      
      if (d.getTime() === today.getTime()) {
        groups["Today"].push(conv);
      } else if (d.getTime() === yesterday.getTime()) {
        groups["Yesterday"].push(conv);
      } else if (today.getTime() - d.getTime() <= 7 * 24 * 60 * 60 * 1000) {
        groups["Previous 7 Days"].push(conv);
      } else {
        groups["Older"].push(conv);
      }
    });

    return groups;
  }, [conversations]);

  const sidebarContent = (
    <div className={cn(
      "flex flex-col h-full bg-rail border-r border-border text-sm overflow-hidden pt-safe pb-safe transition-all duration-300",
      minimized ? "w-[80px]" : "w-[260px]"
    )}>
      {/* Header */}
      <div className={cn(
        "border-b border-border flex items-center px-4 flex-shrink-0",
        minimized ? "flex-col justify-center gap-3 py-4 h-auto" : "h-14 justify-between"
      )}>
        <button
          onClick={() => router.push("/dashboard")}
          className="flex items-center gap-2 text-sm text-muted hover:text-ink font-medium transition-colors"
          title="Back to Dashboard"
        >
          <ArrowLeft size={16} />
          {!minimized && <span>Dashboard</span>}
        </button>
        <button
          onClick={() => setMinimized(!minimized)}
          className="p-1.5 rounded-lg text-muted hover:bg-white hover:shadow-sm hover:text-ink transition-colors"
          title={minimized ? "Expand Sidebar" : "Minimize Sidebar"}
        >
          {minimized ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-6">
        
        {/* Conversations Section */}
        {activeProjectId && (
          <div>
            <div className={cn(
              "font-mono text-muted uppercase tracking-wider mb-4 flex items-center",
              minimized ? "text-[10px] justify-center text-center mt-2" : "text-[11px] justify-between px-2"
            )}>
              {!minimized && <span>Chats</span>}
              <button 
                onClick={handleNewChat}
                className={cn(
                  "hover:text-emerald transition-colors bg-white rounded-md border border-border shadow-sm flex items-center justify-center",
                  minimized ? "w-8 h-8 mx-auto" : "w-6 h-6"
                )}
                title="New Chat"
              >
                <Plus size={14} />
              </button>
            </div>
            
            <div className="space-y-4">
              {loading ? (
                <div className="px-2 text-muted text-xs text-center py-4">Loading...</div>
              ) : conversations.length === 0 ? (
                 <div className="px-2 text-muted text-xs italic text-center">No chats yet</div>
              ) : (
                Object.entries(groupedConversations).map(([groupName, convs]) => {
                  if (convs.length === 0) return null;
                  return (
                    <div key={groupName} className="space-y-1">
                      {!minimized && (
                        <h4 className="text-[10px] font-medium text-muted/70 px-3 py-1 mt-2 uppercase tracking-wide">
                          {groupName}
                        </h4>
                      )}
                      {convs.map(conv => {
                        const isActive = activeConvId === conv.id;
                        return (
                          <button
                            key={conv.id}
                            onClick={() => handleSelectConversation(conv)}
                            title={conv.title}
                            className={cn(
                              "w-full text-left rounded-lg flex items-center group transition-colors",
                              minimized ? "justify-center p-2" : "px-3 py-2 gap-2",
                              isActive 
                                ? "bg-white text-emerald shadow-sm border border-emerald/10" 
                                : "text-muted hover:bg-white hover:text-ink border border-transparent"
                            )}
                          >
                            <MessageSquare size={14} className={cn("flex-shrink-0", isActive ? "text-emerald" : "opacity-50")} />
                            {!minimized && (
                              <span className="truncate pr-2 text-xs font-medium">{conv.title}</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer User Profile */}
      <div className={cn(
        "p-3 border-t border-border mt-auto flex-shrink-0 flex items-center",
        minimized ? "justify-center flex-col gap-2" : ""
      )}>
        <div className={cn(
          "flex items-center rounded-xl bg-white border border-border shadow-sm w-full",
          minimized ? "p-1 flex-col gap-2" : "gap-3 p-2"
        )}>
          <div className={cn(
            "rounded-full bg-emerald-tint text-emerald flex items-center justify-center flex-shrink-0",
            minimized ? "w-10 h-10" : "w-8 h-8"
          )}>
            <User size={16} />
          </div>
          {!minimized && (
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-ink truncate">{user?.name}</div>
              <div className="text-[10px] text-muted capitalize">{user?.role}</div>
            </div>
          )}
          <button 
            onClick={logout}
            className="p-1.5 text-muted hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
            title="Log out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  );

  if (isMobileOpen !== undefined) {
    return (
      <>
        {/* Mobile Backdrop */}
        {isMobileOpen && (
          <div 
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity md:hidden"
            onClick={onMobileClose}
          />
        )}
        
        {/* Mobile Drawer */}
        <div className={cn(
          "fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out md:hidden shadow-2xl",
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}>
          {sidebarContent}
        </div>

        {/* Desktop Sidebar (hidden on mobile when not rendering as drawer) */}
        <div className="hidden md:block h-full">
          {sidebarContent}
        </div>
      </>
    );
  }

  // Standard desktop render
  return (
    <div className="hidden md:block h-full z-30">
      {sidebarContent}
    </div>
  );
}

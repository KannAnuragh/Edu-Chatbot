"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Send, Paperclip, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { type Message, type SourceReference, type SSEEvent, type Conversation } from "@/types";
import MessageBubble from "./MessageBubble";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/AuthProvider";

interface ChatPanelProps {
  projectId: string;
  onSourceClick?: (source: SourceReference) => void;
  onAttachClick?: () => void;
  onViewNote?: (content: string, sources?: SourceReference[]) => void;
  onHasMessagesChange?: (hasMessages: boolean) => void;
}

const SUGGESTIONS = [
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-nimbus">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <path d="M12 17h.01" />
      </svg>
    ),
    title: "Explain a concept",
    subtitle: "Break down complex ideas simply",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-nimbus">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
    title: "Summarize a chapter",
    subtitle: "Get key points from any topic",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-nimbus">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
    title: "Help me study",
    subtitle: "Quiz me or review important topics",
  },
];

export default function ChatPanel({ projectId, onSourceClick, onAttachClick, onViewNote, onHasMessagesChange }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const searchParams = useSearchParams();
  const convIdParam = searchParams.get('conv');
  const { user } = useAuth();

  // Notify parent of message presence for top bar logo transition
  useEffect(() => {
    onHasMessagesChange?.(messages.length > 0);
  }, [messages.length, onHasMessagesChange]);

  // Load conversation if provided in URL
  useEffect(() => {
    if (convIdParam) {
      setConversationId(convIdParam);
      loadConversation(convIdParam);
    } else {
      setConversationId(null);
      setMessages([]);
    }
  }, [convIdParam, projectId]);

  const loadConversation = async (id: string) => {
    try {
      const conv = await api.getConversation(projectId, id);
      setMessages(conv.messages || []);
      scrollToBottom();
    } catch (error) {
      console.error("Failed to load conversation", error);
      setConversationId(null);
    }
  };

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    // Auto-resize
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = async (overrideMessage?: string) => {
    const messageToSend = overrideMessage || inputValue.trim();
    if (!messageToSend || isTyping) return;

    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const optimisticUserMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: messageToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMsg]);
    setIsTyping(true);

    let assistantMsgContent = "";
    let assistantSources: SourceReference[] = [];
    let assistantMsgId = (Date.now() + 1).toString();

    // Create an empty placeholder message for the assistant
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      await api.chatStream(
        projectId,
        messageToSend,
        conversationId,
        (event: SSEEvent) => {
          if (event.type === "meta") {
            setConversationId(event.data.conversation_id);
          } else if (event.type === "sources") {
            assistantSources = event.data;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, sources: assistantSources } : msg
              )
            );
          } else if (event.type === "token") {
            if (event.data.text) {
              assistantMsgContent += event.data.text;
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMsgId ? { ...msg, content: assistantMsgContent } : msg
                )
              );
            }
          } else if (event.type === "error") {
            assistantMsgContent += `\n\n[Error: ${event.data.error || 'Unknown error'}]`;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, content: assistantMsgContent } : msg
              )
            );
          }
        }
      );
    } catch (error: any) {
      console.error("Chat error:", error);
      const isAuthErr = error.message?.includes("token") || error.message?.includes("authenticated") || error.message?.includes("401") || error.message?.includes("403");
      const errDisplay = isAuthErr
        ? "Session expired or invalid login. Please log out and log in again."
        : error.message || "Network error while connecting to backend.";
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, content: assistantMsgContent + `\n\n[System Error: ${errDisplay}]` }
            : msg
        )
      );
    } finally {
      setIsTyping(false);
    }
  };

  const handleDeleteCurrentChat = async () => {
    if (!window.confirm("Are you sure you want to delete this chat history?")) return;
    try {
      if (conversationId) {
        await api.deleteConversation(projectId, conversationId);
      }
      setMessages([]);
      setConversationId(null);
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        url.searchParams.delete("conv");
        window.history.replaceState({}, "", url.toString());
      }
    } catch (error) {
      console.error("Failed to delete chat history", error);
    }
  };

  const handleSuggestionClick = (title: string) => {
    handleSend(title);
  };

  const firstName = user?.name?.split(" ")[0] || "there";

  return (
    <div className="flex flex-col h-full relative" style={{ background: "var(--nimbus-bg)" }}>
      {/* Top action bar when conversation has messages */}
      {messages.length > 0 && (
        <div className="px-4 py-2 border-b border-gray-100 bg-white/60 backdrop-blur-sm flex justify-between items-center z-10 flex-shrink-0">
          <span className="text-xs text-gray-400 font-medium">Active Chat</span>
          <button
            onClick={handleDeleteCurrentChat}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
            title="Delete Chat History"
          >
            <Trash2 size={13} />
            <span>Clear</span>
          </button>
        </div>
      )}

      {/* Messages Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto no-scrollbar px-4 pb-24"
      >
        <div className="max-w-lg mx-auto space-y-4 pb-2">
          {messages.length === 0 ? (
            /* ─── Welcome Screen ─── */
            <div className="flex flex-col items-center justify-center pt-8 pb-4 animate-fade-in">
              {/* Animated Orb — smaller and tighter */}
              <div className="nimbus-orb mb-5" style={{ width: "56px", height: "56px" }} />

              {/* Greeting */}
              <h2 className="font-heading font-bold text-lg text-gray-900 mb-1.5 text-center">
                Hi {firstName}, how can I help?
              </h2>
              <p className="text-sm text-gray-400 mb-5 text-center max-w-[260px]">
                Ask me anything about your subject.
              </p>

              {/* Suggestion Cards */}
              <div className="w-full space-y-2.5 px-1">
                {SUGGESTIONS.map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(suggestion.title)}
                    className="nimbus-suggestion-card w-full flex items-center gap-4 bg-white rounded-2xl border border-gray-100 px-5 py-3.5 text-left shadow-[0_1px_3px_rgba(0,0,0,0.04)] hover:shadow-md hover:border-nimbus/20 group"
                    style={{ animationDelay: `${idx * 0.08}s` }}
                  >
                    <div className="w-10 h-10 rounded-xl bg-nimbus-tint flex items-center justify-center flex-shrink-0 group-hover:bg-nimbus/10 transition-colors">
                      {suggestion.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-[14px] text-gray-800 mb-0.5">
                        {suggestion.title}
                      </div>
                      <div className="text-[12px] text-gray-400 leading-snug">
                        {suggestion.subtitle}
                      </div>
                    </div>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gray-300 group-hover:text-nimbus transition-colors flex-shrink-0">
                      <path d="M9 18l6-6-6-6" />
                    </svg>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* ─── Message Thread ─── */
            <div className="pt-4 space-y-5">
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onSourceClick={onSourceClick}
                  onViewNote={onViewNote}
                />
              ))}

              {/* Typing indicator */}
              {isTyping && messages.length > 0 && messages[messages.length - 1].role === "user" && (
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-nimbus-light to-nimbus flex items-center justify-center flex-shrink-0 shadow-sm">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2L2 7l10 5 10-5-10-5z" />
                      <path d="M2 17l10 5 10-5" />
                      <path d="M2 12l10 5 10-5" />
                    </svg>
                  </div>
                  <div className="flex items-center gap-1.5 h-10 bg-white border border-gray-100 rounded-2xl rounded-tl-md px-5 shadow-sm">
                    <div className="nimbus-typing-dot" />
                    <div className="nimbus-typing-dot" />
                    <div className="nimbus-typing-dot" />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ─── Composer Area — Fixed at bottom ─── */}
      <div className="absolute bottom-0 left-0 right-0 p-2.5 pt-2 bg-gradient-to-t from-[var(--nimbus-bg)] via-[var(--nimbus-bg)]/95 to-transparent pb-safe z-10">
        <div className="max-w-lg mx-auto relative flex items-end gap-2 bg-white rounded-2xl shadow-[0_2px_14px_rgba(0,0,0,0.06)] border border-gray-100 p-1.5 px-2 focus-within:border-nimbus/30 focus-within:shadow-[0_2px_18px_rgba(59,107,245,0.08)] transition-all">

          {/* Attach button */}
          {onAttachClick && (
            <button
              onClick={onAttachClick}
              className="p-2 text-gray-400 hover:text-nimbus hover:bg-nimbus-tint rounded-xl transition-colors mb-0.5"
              title="Attach file"
            >
              <Paperclip size={19} />
            </button>
          )}

          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything..."
            className="flex-1 max-h-[120px] bg-transparent resize-none outline-none py-2 px-2 text-[15px] leading-relaxed no-scrollbar placeholder:text-gray-400 text-gray-800"
            rows={1}
            disabled={isTyping}
          />

          {/* Send button */}
          <button
            onClick={() => handleSend()}
            disabled={!inputValue.trim() || isTyping}
            className={cn(
              "p-2.5 rounded-xl transition-all mb-0.5",
              inputValue.trim() && !isTyping
                ? "bg-nimbus text-white shadow-sm hover:bg-nimbus-deep active:scale-95"
                : "bg-gray-100 text-gray-300 cursor-not-allowed"
            )}
          >
            <Send size={18} />
          </button>
        </div>

        <div className="text-center mt-1.5">
          <span className="text-[10px] text-gray-400 font-medium tracking-wide opacity-60">
            Responses may contain inaccuracies. Always verify important information.
          </span>
        </div>
      </div>
    </div>
  );
}

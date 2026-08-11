"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Send, Paperclip, Trash2, HelpCircle, BookOpen, GraduationCap } from "lucide-react";
import { api } from "@/lib/api";
import { type Message, type SourceReference, type SSEEvent, type Conversation } from "@/types";
import MessageBubble from "./MessageBubble";
import EtherealAvatar from "./EtherealAvatar";
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
    icon: <HelpCircle size={20} className="text-indigo-600" />,
    iconBg: "bg-indigo-50 border border-indigo-100/80 group-hover:bg-indigo-100/80",
    title: "Explain a concept",
    subtitle: "Break down complex ideas simply",
  },
  {
    icon: <BookOpen size={20} className="text-teal-600" />,
    iconBg: "bg-teal-50 border border-teal-100/80 group-hover:bg-teal-100/80",
    title: "Summarize a chapter",
    subtitle: "Get key points from any topic",
  },
  {
    icon: <GraduationCap size={20} className="text-amber-600" />,
    iconBg: "bg-amber-50 border border-amber-100/80 group-hover:bg-amber-100/80",
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
  
  const firstName = user?.name?.split(" ")[0] || "there";
  const [greeting, setGreeting] = useState<React.ReactNode>(<>Welcome<br />aboard, {firstName}!</>);

  useEffect(() => {
    const greetings = [
      <>Welcome<br />aboard, {firstName}!</>,
      <>Ready to<br />learn, {firstName}?</>,
      <>What's on your<br />mind, {firstName}?</>,
      <>Let's study,<br />{firstName}!</>,
      <>Hi {firstName},<br />how can I help?</>
    ];
    setGreeting(greetings[Math.floor(Math.random() * greetings.length)]);
  }, [firstName]);

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

  return (
    <div className="flex flex-col h-full relative" style={{ background: "var(--nimbus-bg)" }}>

      {/* Messages Area */}
      <div
        ref={scrollRef}
        className={cn("flex-1 overflow-y-auto no-scrollbar px-4", messages.length === 0 ? "flex flex-col h-full" : "pb-24")}
      >
        <div className={cn("max-w-lg mx-auto w-full", messages.length === 0 ? "flex-1 flex flex-col h-full" : "space-y-4 pb-2")}>
          {messages.length === 0 ? (
            /* ─── Mindmate-Inspired Welcome Screen (50/50 split) ─── */
            <div className="flex-1 flex flex-col items-center justify-between animate-fade-in relative z-10 w-full h-full min-h-[calc(100vh-140px)]">
              
              {/* Top Section - Hero Section */}
              <div className="flex-[1.35] flex flex-col items-center justify-end text-center w-full pb-4">
                <EtherealAvatar />
                <h2 className="font-display font-medium text-[44px] text-gray-900 leading-[1.05] tracking-[-0.03em] mb-3">
                  {greeting}
                </h2>
                <p className="text-[14px] text-slate-600 font-medium max-w-[270px] leading-relaxed">
                  Your personal AI study companion for instant answers & summaries.
                </p>
              </div>

              {/* Bottom Section - Actionable Suggestion Cards Grid */}
              <div className="flex-1 flex flex-col justify-end w-full pb-[110px] gap-3">
                {SUGGESTIONS.map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(suggestion.title)}
                    className="w-full flex items-center gap-4 bg-white/90 backdrop-blur-md rounded-2xl border border-gray-200/90 px-5 py-4 text-left shadow-[0_4px_18px_rgba(0,0,0,0.03)] hover:shadow-[0_8px_24px_rgba(28,77,140,0.12)] hover:border-nimbus/40 hover:bg-white hover:-translate-y-0.5 active:scale-[0.99] transition-all duration-200 group"
                  >
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors ${suggestion.iconBg}`}>
                      {suggestion.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-[15px] text-gray-900 mb-0.5 group-hover:text-nimbus transition-colors">
                        {suggestion.title}
                      </div>
                      <div className="text-[13px] text-slate-600 font-normal truncate">
                        {suggestion.subtitle}
                      </div>
                    </div>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-gray-400 group-hover:text-nimbus group-hover:translate-x-0.5 transition-all flex-shrink-0">
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

      {/* ─── Composer Area — Fixed at bottom with Floating Send Button (Reference UI) ─── */}
      <div className="absolute bottom-0 left-0 right-0 p-3 pt-2 bg-gradient-to-t from-[var(--nimbus-bg)] via-[var(--nimbus-bg)]/95 to-transparent pb-safe z-10">
        <div className="max-w-lg mx-auto flex items-center gap-2">
          
          {/* Main Input Box (Rounded Pill) */}
          <div className="flex-1 flex items-center gap-2 bg-white rounded-full shadow-[0_4px_20px_rgba(0,0,0,0.05)] border border-gray-200/90 px-4 py-1.5 focus-within:border-nimbus/40 transition-all">
            {onAttachClick && (
              <button
                onClick={onAttachClick}
                className="p-1.5 text-gray-400 hover:text-nimbus hover:bg-nimbus-tint rounded-full transition-colors"
                title="Attach file"
              >
                <Paperclip size={18} />
              </button>
            )}

            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              className="flex-1 max-h-[100px] bg-transparent resize-none outline-none py-2 px-1 text-[15px] leading-relaxed no-scrollbar placeholder:text-gray-400 text-gray-800"
              rows={1}
              disabled={isTyping}
            />
          </div>

          {/* Floating Circular Send Button (Reference UI) */}
          <button
            onClick={() => handleSend()}
            disabled={!inputValue.trim() || isTyping}
            className={cn(
              "w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0 transition-all shadow-md",
              inputValue.trim() && !isTyping
                ? "bg-nimbus text-white hover:bg-nimbus-deep hover:scale-105 active:scale-95 shadow-nimbus/20"
                : "bg-gray-200 text-gray-400 cursor-not-allowed"
            )}
          >
            <Send size={18} className="translate-x-0.5" />
          </button>
        </div>

        <div className="text-center mt-1.5">
          <span className="text-[11px] text-slate-500 font-medium tracking-wide">
            Responses may contain inaccuracies. Always verify important information.
          </span>
        </div>
      </div>
    </div>
  );
}

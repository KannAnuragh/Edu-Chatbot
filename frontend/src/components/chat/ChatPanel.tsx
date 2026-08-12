"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
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
  const [isInitializing, setIsInitializing] = useState(true);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const suppressAutoScrollRef = useRef(false);
  const searchParams = useSearchParams();
  const router = useRouter();
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
      setIsInitializing(false);
    } else {
      setConversationId(null);
      setMessages([]);
      setIsInitializing(true);
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

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  const handleScrollToMessage = useCallback((id: string) => {
    // Suppress auto-scroll so the useEffect scrollToBottom doesn't undo this jump
    suppressAutoScrollRef.current = true;
    
    const el = document.getElementById(`message-${id}`);
    if (el && scrollRef.current) {
      const container = scrollRef.current;
      
      // Walk up offsetTop chain to compute the element's absolute position
      // relative to the scroll container. This is the only method that gives
      // the true scroll offset regardless of current scroll position.
      let top = 0;
      let node: HTMLElement | null = el;
      while (node && node !== container) {
        top += node.offsetTop;
        node = node.offsetParent as HTMLElement | null;
      }
      
      container.scrollTop = Math.max(0, top - 16);
    }
    
    // Re-enable auto-scroll after a short delay
    setTimeout(() => {
      suppressAutoScrollRef.current = false;
    }, 500);
  }, []);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const containerRect = scrollRef.current.getBoundingClientRect();
    const wrappers = Array.from(document.querySelectorAll('.user-message-wrapper'));
    
    let foundId: string | null = null;

    // Find the last user message whose top is within the upper 60% of the container
    for (const w of wrappers) {
      const rect = w.getBoundingClientRect();
      const relativeTop = rect.top - containerRect.top;
      
      if (relativeTop < containerRect.height * 0.6) {
        foundId = w.getAttribute('data-message-id');
      }
    }

    if (foundId) {
      setActiveMessageId(foundId);
    }
  }, []);

  // Auto-scroll to bottom on new messages, but NOT when a manual jump is in progress
  useEffect(() => {
    if (!suppressAutoScrollRef.current) {
      scrollToBottom();
    }
  }, [messages, isTyping, scrollToBottom]);

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
            const newConvId = event.data.conversation_id;
            setConversationId(newConvId);
            if (newConvId && !convIdParam) {
              router.replace(`/dashboard/project/${projectId}?conv=${newConvId}`);
            }
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

  const handleRegenerate = async (targetId: string) => {
    const targetIndex = messages.findIndex(m => m.id === targetId);
    if (targetIndex <= 0) return;
    
    const userMsg = messages[targetIndex - 1];
    if (userMsg.role !== "user") return;
    
    setMessages(prev => prev.slice(0, targetIndex - 1));
    handleSend(userMsg.content);
  };

  const handleSuggestionClick = (title: string) => {
    handleSend(title);
  };

  return (
    <div className="flex flex-col h-full relative overflow-hidden" style={{ background: "var(--nimbus-bg)" }}>
      
      {/* Aurora Background */}
      <div 
        className={cn(
          "aurora-bg transition-[height,opacity] duration-1000 ease-in-out z-0", 
          (messages.length === 0 && isInitializing) ? "opacity-0" : 
          (messages.length === 0 && !isInitializing) ? "h-full opacity-100 delay-500" : 
          "h-[85%] opacity-100"
        )}
      >
        <div className="aurora-blob aurora-blob-1"></div>
        <div className="aurora-blob aurora-blob-2"></div>
        <div className="aurora-blob aurora-blob-3"></div>
      </div>

      {/* Messages Area */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={cn("flex-1 overflow-y-auto no-scrollbar px-4 relative z-20", messages.length === 0 ? "flex flex-col h-full" : "pb-20")}
      >
        <div className={cn("max-w-lg mx-auto w-full relative z-20", messages.length === 0 ? "flex-1 flex flex-col h-full" : "space-y-4 pb-2")}>
          {messages.length === 0 ? (
            /* ─── Mindmate-Inspired Welcome Screen (50/50 split) ─── */
            <div className="flex-1 flex flex-col items-center justify-between animate-fade-in relative z-20 w-full h-full min-h-[calc(100vh-140px)]">
              
              {/* Top Section - Hero Section */}
              <div className="flex-[1.35] flex flex-col items-center justify-end text-center w-full pb-4">
                <div className={cn(
                  "transition-all duration-1000 ease-[cubic-bezier(0.16,1,0.3,1)]",
                  isInitializing ? "translate-y-[20vh] scale-125" : "translate-y-0 scale-100"
                )}>
                  <EtherealAvatar 
                    playStartupAnimation={isInitializing}
                    onAnimationComplete={() => setIsInitializing(false)}
                  />
                </div>
                <h2 className={cn("font-display font-medium text-[44px] text-gray-900 leading-[1.05] tracking-[-0.03em] mb-3 transition-all duration-700 delay-[600ms]", isInitializing ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0")}>
                  {greeting}
                </h2>
                <p className={cn("text-[14px] text-slate-600 font-medium max-w-[270px] leading-relaxed transition-all duration-700 delay-[700ms]", isInitializing ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0")}>
                  Your personal AI study companion for instant answers & summaries.
                </p>
              </div>

              {/* Bottom Section - Actionable Suggestion Cards Grid */}
              <div className={cn("flex-1 flex flex-col justify-end w-full pb-[80px] gap-3 transition-all duration-700 delay-[800ms]", isInitializing ? "opacity-0 translate-y-4 pointer-events-none" : "opacity-100 translate-y-0 pointer-events-auto")}>
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
            <div className="pt-3 space-y-4">
              {messages.map((msg, index) => (
                <div 
                  key={msg.id} 
                  id={`message-${msg.id}`} 
                  data-message-id={msg.id}
                  className={msg.role === 'user' ? 'user-message-wrapper' : ''}
                >
                  <MessageBubble
                    message={msg}
                    onSourceClick={onSourceClick}
                    onViewNote={onViewNote}
                    onRegenerate={msg.role === 'assistant' ? () => handleRegenerate(msg.id) : undefined}
                    isStreaming={isTyping && index === messages.length - 1}
                    isLatest={index === messages.length - 1}
                    onSendFollowUp={(text) => handleSend(text)}
                  />
                </div>
              ))}

              {/* Typing indicator */}
              {isTyping && messages.length > 0 && messages[messages.length - 1].role === "user" && (
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-[#1C4D8C] text-white flex items-center justify-center flex-shrink-0 shadow-sm">
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



      {/* ─── Composer Area — Floating Unified Input Pill (Perfect Alignment) ─── */}
      <div className={cn(
        "absolute bottom-0 left-0 right-0 px-4 pt-12 pb-5 bg-gradient-to-t from-[var(--nimbus-bg)]/60 via-[var(--nimbus-bg)]/20 to-transparent pointer-events-none z-30 transition-all duration-700 delay-[900ms]",
        (messages.length === 0 && isInitializing) ? "opacity-0 translate-y-8" : "opacity-100 translate-y-0"
      )}>
        <div className="max-w-lg mx-auto pointer-events-auto">
          {/* Single Unified Floating Pill Box */}
          <div 
            className="flex items-center gap-2 bg-white/60 backdrop-blur-2xl rounded-full border border-white/80 px-4 py-2 focus-within:border-blue-500/60 focus-within:bg-white/90 focus-within:ring-4 focus-within:ring-blue-500/10 transition-all shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.9),inset_0_-1px_1px_rgba(0,0,0,0.03),0_10px_30px_rgba(0,0,0,0.06)]"
          >
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              className="flex-1 max-h-[100px] bg-transparent resize-none outline-none py-1.5 px-1 text-[15px] leading-relaxed no-scrollbar placeholder:text-slate-600 text-slate-950 font-semibold"
              rows={1}
              disabled={isTyping}
            />

            {/* Integrated Circular Send Button */}
            <button
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || isTyping}
              className={cn(
                "w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 transition-all shadow-sm",
                inputValue.trim() && !isTyping
                  ? "bg-[#1C4D8C] text-white hover:bg-[#163359] hover:scale-105 active:scale-95 shadow-[0_4px_12px_rgba(28,77,140,0.3)]"
                  : "bg-slate-200/80 text-slate-400 border border-slate-300/40 cursor-not-allowed"
              )}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

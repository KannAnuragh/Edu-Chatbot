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
  const conversationIdRef = useRef<string | null>(null);
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  const [isInitializing, setIsInitializing] = useState(true);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [isInputFocused, setIsInputFocused] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const suppressAutoScrollRef = useRef(false);

  // Smooth ChatGPT-style typewriter streaming refs
  const streamTargetRef = useRef("");
  const streamDisplayedRef = useRef("");
  const streamActiveRef = useRef(false);
  const animationFrameIdRef = useRef<number | null>(null);

  const searchParams = useSearchParams();
  const router = useRouter();
  const convIdParam = searchParams.get('conv');
  const { user } = useAuth();

  const firstName = user?.name?.split(" ")[0] || "there";
  const [greeting, setGreeting] = useState<React.ReactNode>(<>Welcome<br />aboard, {firstName}!</>);

  // Smooth Gemini & ChatGPT-style typewriter ticker loop
  // Smooth Gemini & ChatGPT-style word-rate typewriter loop
  const startTypewriter = useCallback((assistantMsgId: string) => {
    if (animationFrameIdRef.current) {
      cancelAnimationFrame(animationFrameIdRef.current);
      animationFrameIdRef.current = null;
    }

    let lastTickTime = performance.now();

    const step = (now: number) => {
      const elapsed = now - lastTickTime;

      // Smooth word-rate ticker running every ~24ms
      if (elapsed >= 24) {
        lastTickTime = now;

        const target = streamTargetRef.current;
        const displayed = streamDisplayedRef.current;
        const remainingText = target.slice(displayed.length);

        if (remainingText.length > 0) {
          const remainingWords = remainingText.trim().split(/\s+/).filter(Boolean);
          const backlogCount = remainingWords.length;

          // Determine words to append per tick:
          // 1-2 words per tick for smooth ChatGPT/Gemini cadence
          let wordsToAppend = 1;
          if (backlogCount > 40) {
            wordsToAppend = Math.min(5, Math.ceil(backlogCount / 8));
          } else if (backlogCount > 15) {
            wordsToAppend = 2;
          }

          // Slice target text at the Nth word boundary to prevent word slicing
          let sliceEnd = 0;
          let wordMatches = 0;
          const wordRegex = /\S+(?:\s+|$)/g;
          let match: RegExpExecArray | null;

          while ((match = wordRegex.exec(remainingText)) !== null) {
            wordMatches++;
            sliceEnd = match.index + match[0].length;
            if (wordMatches >= wordsToAppend) break;
          }

          if (sliceEnd === 0) sliceEnd = remainingText.length;

          const nextContent = target.slice(0, displayed.length + sliceEnd);
          streamDisplayedRef.current = nextContent;

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId ? { ...msg, content: nextContent } : msg
            )
          );
        }
      }

      const currentBacklog = streamTargetRef.current.length - streamDisplayedRef.current.length;
      if (currentBacklog > 0 || streamActiveRef.current) {
        animationFrameIdRef.current = requestAnimationFrame(step);
      } else {
        animationFrameIdRef.current = null;
        setIsTyping(false);
      }
    };

    animationFrameIdRef.current = requestAnimationFrame(step);
  }, []);

  useEffect(() => {
    return () => {
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current);
      }
    };
  }, []);

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

  // Load conversation if provided in URL (only if changing to a different conversation)
  useEffect(() => {
    if (convIdParam) {
      if (convIdParam !== conversationIdRef.current) {
        conversationIdRef.current = convIdParam;
        setConversationId(convIdParam);
        loadConversation(convIdParam);
        setIsInitializing(false);
      }
    } else {
      if (conversationIdRef.current && !streamActiveRef.current) {
        conversationIdRef.current = null;
        setConversationId(null);
        setMessages([]);
        setIsInitializing(true);
      }
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
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: isTyping ? 'smooth' : 'auto'
      });
    }
  }, [isTyping]);

  const handleScrollToMessage = useCallback((id: string) => {
    // Suppress auto-scroll so the useEffect scrollToBottom doesn't undo this jump
    suppressAutoScrollRef.current = true;

    const el = document.getElementById(`message-${id}`);
    if (el && scrollRef.current) {
      const container = scrollRef.current;

      let top = 0;
      let node: HTMLElement | null = el;
      while (node && node !== container) {
        top += node.offsetTop;
        node = node.offsetParent as HTMLElement | null;
      }

      container.scrollTop = Math.max(0, top - 16);
    }

    setTimeout(() => {
      suppressAutoScrollRef.current = false;
    }, 500);
  }, []);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const containerRect = scrollRef.current.getBoundingClientRect();
    const wrappers = Array.from(document.querySelectorAll('.user-message-wrapper'));

    let foundId: string | null = null;

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
      textareaRef.current.blur();
    }
    setIsInputFocused(false);

    const optimisticUserMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: messageToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticUserMsg]);
    setIsTyping(true);

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

    // Reset streaming typewriter refs
    streamTargetRef.current = "";
    streamDisplayedRef.current = "";
    streamActiveRef.current = true;

    // Start smooth ChatGPT-style typewriter ticker
    startTypewriter(assistantMsgId);

    try {
      await api.chatStream(
        projectId,
        messageToSend,
        conversationId,
        (event: SSEEvent) => {
          if (event.type === "meta") {
            const newConvId = event.data.conversation_id;
            conversationIdRef.current = newConvId;
            setConversationId(newConvId);
            if (newConvId && typeof window !== "undefined") {
              window.history.replaceState({}, "", `/dashboard/project/${projectId}?conv=${newConvId}`);
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
              streamTargetRef.current += event.data.text;
            }
          } else if (event.type === "error") {
            streamTargetRef.current += `\n\n[Error: ${event.data.error || 'Unknown error'}]`;
          }
        }
      );
    } catch (error: any) {
      console.error("Chat error:", error);
      const isAuthErr = error.message?.includes("token") || error.message?.includes("authenticated") || error.message?.includes("401") || error.message?.includes("403");
      const errDisplay = isAuthErr
        ? "Session expired or invalid login. Please log out and log in again."
        : error.message || "Network error while connecting to backend.";
      streamTargetRef.current += `\n\n[System Error: ${errDisplay}]`;
    } finally {
      streamActiveRef.current = false;
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
          "aurora-bg transition-all duration-[1500ms] ease-in-out z-0 pointer-events-none",
          isInputFocused
            ? "h-[50%] opacity-100"
            : (messages.length === 0 && isInitializing) ? "opacity-0" :
              "h-[35%] opacity-90"
        )}
      >
        <div className={cn("aurora-blob aurora-blob-1 transition-all duration-[1500ms] ease-in-out", isInputFocused ? "opacity-100 scale-125 -translate-y-6" : "opacity-75 scale-100 translate-y-0")} />
        <div className={cn("aurora-blob aurora-blob-2 transition-all duration-[1500ms] ease-in-out", isInputFocused ? "!bg-[#3B82F6] opacity-95 scale-125 -translate-y-4" : "opacity-65 scale-100 translate-y-0")} />
        <div className={cn("aurora-blob aurora-blob-3 transition-all duration-[1500ms] ease-in-out", isInputFocused ? "opacity-100 scale-120 -translate-y-8" : "opacity-70 scale-100 translate-y-0")} />
      </div>

      {/* Side Border Aurora (Generating State) */}
      <div 
        className={cn(
          "absolute inset-0 pointer-events-none overflow-hidden transition-opacity duration-[1500ms] ease-in-out z-10",
          isTyping ? "opacity-100" : "opacity-0"
        )}
      >
        {/* Left Edge Aurora */}
        <div className="absolute top-[20%] -left-[80px] w-[140px] h-[50%] bg-[#3B82F6]/30 blur-[65px] rounded-full mix-blend-screen animate-pulse" style={{ animationDuration: '3s' }} />
        {/* Right Edge Aurora */}
        <div className="absolute top-[35%] -right-[80px] w-[140px] h-[45%] bg-[#1C4D8C]/40 blur-[65px] rounded-full mix-blend-screen animate-pulse" style={{ animationDuration: '4s' }} />
      </div>

      {/* Messages Area */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        onPointerDown={() => {
          // Dismiss keyboard when tapping the background on mobile
          if (isInputFocused && textareaRef.current) {
            textareaRef.current.blur();
          }
        }}
        className={cn("flex-1 overflow-y-auto no-scrollbar px-4 relative z-20", messages.length === 0 ? "flex flex-col h-full" : "pb-24")}
      >
        <div className={cn("max-w-lg mx-auto w-full relative z-20", messages.length === 0 ? "flex-1 flex flex-col h-full" : "space-y-4 pb-2")}>
          {messages.length === 0 ? (
            /* ─── Welcome Screen ─── */
            <div className="flex-1 flex flex-col items-center animate-fade-in relative z-20 w-full h-full">

              {/* Hero Section — centered vertically in available space */}
              <div className="flex-1 flex flex-col items-center justify-center text-center w-full pb-4 md:pb-8">
                <div className={cn(
                  "transition-all duration-1000 ease-[cubic-bezier(0.16,1,0.3,1)]",
                  isInitializing ? "translate-y-[20vh] scale-125" : "translate-y-0 scale-100"
                )}>
                  <EtherealAvatar
                    playStartupAnimation={isInitializing}
                    onAnimationComplete={() => setIsInitializing(false)}
                  />
                </div>
                <h2 className={cn("font-display font-medium text-[28px] sm:text-[36px] md:text-[44px] text-gray-900 leading-[1.05] tracking-[-0.03em] mb-2 md:mb-3 transition-all duration-700 delay-[600ms]", isInitializing ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0")}>
                  {greeting}
                </h2>
                <p className={cn("text-[13px] sm:text-[14px] text-slate-600 font-medium max-w-[270px] leading-relaxed transition-all duration-700 delay-[700ms]", isInitializing ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0")}>
                  Your personal AI study companion for instant answers & summaries.
                </p>
              </div>

              {/* Suggestion Cards */}
              <div className={cn(
                "flex-shrink-0 flex flex-col w-full gap-2 md:gap-3 transition-all duration-500 ease-in-out overflow-hidden",
                isInitializing ? "opacity-0 translate-y-4 pointer-events-none" : "translate-y-0 pointer-events-auto",
                isInputFocused ? "max-h-0 md:max-h-[500px] opacity-0 md:opacity-100 pb-0 md:pb-[80px] m-0" : "max-h-[500px] opacity-100 pb-[72px] md:pb-[80px]"
              )}>
                {SUGGESTIONS.map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(suggestion.title)}
                    className="w-full flex items-center gap-3 md:gap-4 bg-white/90 backdrop-blur-md rounded-2xl border border-gray-200/90 px-4 py-3 md:px-5 md:py-4 text-left shadow-[0_4px_18px_rgba(0,0,0,0.03)] hover:shadow-[0_8px_24px_rgba(28,77,140,0.12)] hover:border-nimbus/40 hover:bg-white hover:-translate-y-0.5 active:scale-[0.99] transition-all duration-200 group"
                  >
                    <div className={`w-9 h-9 md:w-11 md:h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors ${suggestion.iconBg}`}>
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
        "absolute bottom-0 left-0 right-0 px-4 pt-12 pb-4 md:pb-5 bg-gradient-to-t from-[var(--nimbus-bg)]/60 via-[var(--nimbus-bg)]/20 to-transparent pointer-events-none z-30 transition-all duration-700 delay-[900ms]",
        (messages.length === 0 && isInitializing) ? "opacity-0 translate-y-8" : "opacity-100 translate-y-0"
      )} style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
        <div className="max-w-lg mx-auto pointer-events-auto">
          {/* Single Unified Floating Pill Box */}
          <div
            className="group relative isolate overflow-hidden flex items-center gap-2 rounded-full backdrop-blur-2xl px-4 py-2 transition-all shadow-[inset_0_1.5px_1px_rgba(255,255,255,0.9),inset_0_-1px_1px_rgba(0,0,0,0.04),0_10px_30px_rgba(28,77,140,0.16)]"
            style={{
              background:
                'linear-gradient(160deg, rgba(255,255,255,0.82) 0%, rgba(232,240,251,0.7) 100%)',
            }}
          >
            {/* Adaptive glass border - blends with whatever is behind the pill */}
            <div className="pointer-events-none absolute inset-0 rounded-full border border-white/40 mix-blend-soft-light" />
            {/* Quiet static ring */}
            <div className="pointer-events-none absolute inset-0 rounded-full border border-white/25" />
            {/* Glass sheen across the top, same treatment as the message bubbles */}
            <div className="pointer-events-none absolute inset-x-0 top-0 h-1/2 rounded-t-full bg-gradient-to-b from-white/40 to-transparent" />

            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsInputFocused(true)}
              onBlur={() => setIsInputFocused(false)}
              placeholder="Ask me anything..."
              className="relative flex-1 max-h-[100px] bg-transparent resize-none outline-none py-1.5 px-1 text-[15px] leading-relaxed no-scrollbar placeholder:text-slate-600 text-slate-950 font-semibold focus:outline-none focus:ring-0"
              rows={1}
              disabled={isTyping}
            />

            {/* Integrated Circular Send Button - Dark Blue Theme */}
            <button
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || isTyping}
              className={cn(
                "group/btn relative isolate z-10 overflow-hidden w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 transition-all",
                inputValue.trim() && !isTyping
                  ? "text-white hover:scale-105 active:scale-95 border border-white/15 shadow-[0_4px_14px_rgba(22,51,89,0.35)]"
                  : "bg-slate-200/80 text-slate-400 border border-slate-300/40 cursor-not-allowed"
              )}
              style={
                inputValue.trim() && !isTyping
                  ? { background: 'linear-gradient(135deg, #1C4D8C 0%, #1C4D8C 25%, #163359 100%)' }
                  : undefined
              }
            >
              <Send
                size={16}
                className={cn(
                  "relative z-10 transition-colors",
                  inputValue.trim() && !isTyping ? "text-white" : "text-slate-400"
                )}
              />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
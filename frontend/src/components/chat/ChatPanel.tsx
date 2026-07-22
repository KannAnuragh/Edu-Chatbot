"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Send, FileText, Bot, User, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { type Message, type SourceReference, type SSEEvent, type Conversation } from "@/types";
import MessageBubble from "./MessageBubble";
import { cn } from "@/lib/utils";

interface ChatPanelProps {
  projectId: string;
  onSourceClick?: (source: SourceReference) => void;
  onAttachClick?: () => void;
  onViewNote?: (content: string, sources?: SourceReference[]) => void;
}

export default function ChatPanel({ projectId, onSourceClick, onAttachClick, onViewNote }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const searchParams = useSearchParams();
  const convIdParam = searchParams.get('conv');

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

  const handleSend = async () => {
    if (!inputValue.trim() || isTyping) return;

    const userMessage = inputValue.trim();
    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const optimisticUserMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: userMessage,
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
        userMessage,
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

  return (
    <div className="flex flex-col h-full bg-canvas relative">
      {/* Messages Area */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-6 pb-32"
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted mt-10">
            <div className="w-16 h-16 bg-white rounded-2xl shadow-sm border border-border flex items-center justify-center mb-6">
              <Bot className="w-8 h-8 text-emerald" />
            </div>
            <h3 className="font-heading font-medium text-ink mb-2">How can I help you learn?</h3>
            <p className="text-sm text-center max-w-xs text-muted leading-relaxed">
              Ask questions about the course documents, and I'll find the answers with exact citations.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble 
              key={msg.id} 
              message={msg} 
              onSourceClick={onSourceClick}
              onViewNote={onViewNote} 
            />
          ))
        )}
        
        {isTyping && messages.length > 0 && messages[messages.length - 1].role === "user" && (
          <div className="flex items-start gap-4">
             <div className="w-8 h-8 rounded-full bg-emerald flex items-center justify-center flex-shrink-0 text-white shadow-sm">
              <Bot size={18} />
            </div>
            <div className="flex items-center gap-1.5 h-8 bg-white border border-border rounded-2xl rounded-tl-sm px-4 shadow-sm">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        )}
      </div>

      {/* Composer Area - Floating at bottom */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-canvas via-canvas/95 to-transparent pb-safe z-10">
        <div className="max-w-3xl mx-auto relative flex items-end gap-2 bg-white rounded-2xl shadow-[0_2px_12px_rgb(0,0,0,0.06)] border border-border p-2 pr-3 focus-within:border-emerald/50 focus-within:shadow-[0_2px_16px_rgba(16,185,129,0.1)] transition-all">
          
          {onAttachClick && (
            <button 
              onClick={onAttachClick}
              className="p-2.5 text-muted hover:text-emerald hover:bg-emerald-tint rounded-xl transition-colors mb-0.5"
              title="Upload PDF"
            >
              <FileText size={20} />
            </button>
          )}

          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about the course..."
            className="flex-1 max-h-[120px] bg-transparent resize-none outline-none py-2.5 px-1 text-[15px] leading-relaxed custom-scrollbar placeholder:text-muted/70 text-ink"
            rows={1}
            disabled={isTyping}
          />

          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isTyping}
            className={cn(
              "p-2.5 rounded-xl transition-all mb-0.5",
              inputValue.trim() && !isTyping 
                ? "bg-emerald text-white shadow-sm hover:bg-emerald-deep active:scale-95" 
                : "bg-rail text-muted cursor-not-allowed"
            )}
          >
            <Send size={18} />
          </button>
        </div>
        <div className="text-center mt-2">
           <span className="text-[10px] text-muted font-medium tracking-wide opacity-70">
             AI responses are generated based on course materials and may contain inaccuracies.
           </span>
        </div>
      </div>
    </div>
  );
}

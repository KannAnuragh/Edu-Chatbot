import React, { useState, useRef, useEffect, useCallback } from 'react';
import { type Message } from '@/types';
import { cn } from '@/lib/utils';

interface ChatTimelineProps {
  messages: Message[];
  activeId: string | null;
  onScrollTo: (id: string) => void;
}

export default function ChatTimeline({ messages, activeId, onScrollTo }: ChatTimelineProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const hoveredIdRef = useRef<string | null>(null);
  const isDraggingRef = useRef(false);
  const touchStartYRef = useRef(0);

  const userMessages = messages.filter((m) => m.role === 'user');

  const updateHoverScrub = useCallback((clientY: number) => {
    const items = Array.from(document.querySelectorAll('.timeline-item'));
    if (items.length === 0) return;

    let closestId = null;
    let minDistance = Infinity;

    for (const item of items) {
      const rect = item.getBoundingClientRect();
      const itemCenterY = rect.top + rect.height / 2;
      const distance = Math.abs(clientY - itemCenterY);
      
      if (distance < minDistance) {
        minDistance = distance;
        closestId = item.getAttribute('data-id');
      }
    }

    if (closestId && closestId !== hoveredIdRef.current && minDistance < 150) {
      hoveredIdRef.current = closestId;
      setHoveredId(closestId);
    }
  }, []);

  const handleTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    isDraggingRef.current = false;
    touchStartYRef.current = e.touches[0].clientY;
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLDivElement>) => {
    const dy = Math.abs(e.touches[0].clientY - touchStartYRef.current);
    if (dy > 10) {
      isDraggingRef.current = true;
      updateHoverScrub(e.touches[0].clientY);
    }
  };

  const handleTouchEnd = () => {
    if (isDraggingRef.current && hoveredIdRef.current) {
      onScrollTo(hoveredIdRef.current);
    }
    isDraggingRef.current = false;
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    isDraggingRef.current = false;
    touchStartYRef.current = e.clientY;
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.buttons > 0) {
      const dy = Math.abs(e.clientY - touchStartYRef.current);
      if (dy > 5) {
        isDraggingRef.current = true;
        updateHoverScrub(e.clientY);
      }
    } else {
      const element = document.elementFromPoint(e.clientX, e.clientY);
      const item = element?.closest('.timeline-item');
      if (item) {
        const id = item.getAttribute('data-id');
        if (id && id !== hoveredIdRef.current) {
          hoveredIdRef.current = id;
          setHoveredId(id);
        }
      } else {
        hoveredIdRef.current = null;
        setHoveredId(null);
      }
    }
  };

  const handleMouseUp = () => {
    if (isDraggingRef.current && hoveredIdRef.current) {
      onScrollTo(hoveredIdRef.current);
    }
    isDraggingRef.current = false;
  };

  const handleMouseLeave = () => {
    if (!isDraggingRef.current) {
      hoveredIdRef.current = null;
      setHoveredId(null);
    }
  };

  if (userMessages.length === 0) return null;

  return (
    <div 
      className="absolute right-1 top-1/2 -translate-y-1/2 flex flex-col items-end gap-1.5 z-[60] pointer-events-auto select-none py-4 px-2"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      {userMessages.map((msg) => {
        const isActive = msg.id === activeId;
        const isHovered = msg.id === hoveredId;

        return (
          <div 
            key={msg.id}
            data-id={msg.id}
            onClick={() => onScrollTo(msg.id)}
            className="timeline-item relative flex items-center justify-end cursor-pointer w-10 h-4"
          >
            {/* Tooltip (Blue tinted glass) */}
            <div
              className={cn(
                "absolute right-8 max-w-[200px] bg-[#1C4D8C]/90 backdrop-blur-xl text-white border border-white/20 rounded-xl px-3 py-1.5 text-xs font-medium shadow-lg pointer-events-none transition-all duration-150 origin-right whitespace-nowrap overflow-hidden text-ellipsis drop-shadow-md",
                isHovered ? "opacity-100 scale-100 translate-x-0" : "opacity-0 scale-95 translate-x-2"
              )}
            >
              {msg.content}
            </div>

            {/* Dash (Blue themed) */}
            <div
              className={cn(
                "h-[2px] rounded-full transition-all duration-150 pointer-events-none",
                isActive 
                  ? "w-5 bg-[#1C4D8C] shadow-[0_0_6px_rgba(28,77,140,0.6)]" 
                  : isHovered 
                    ? "w-7 bg-[#1C4D8C]" 
                    : "w-2.5 bg-[#1C4D8C]/35"
              )}
            />
          </div>
        );
      })}
    </div>
  );
}

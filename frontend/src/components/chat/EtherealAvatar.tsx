import React, { useEffect, useState, useRef } from 'react';
import { cn } from '@/lib/utils';

interface EtherealAvatarProps {
  playStartupAnimation?: boolean;
  onAnimationComplete?: () => void;
}

export default function EtherealAvatar({ playStartupAnimation = false, onAnimationComplete }: EtherealAvatarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [transitionSpeed, setTransitionSpeed] = useState('0.1s ease-out');
  const [isBlinking, setIsBlinking] = useState(false);
  const [startupPhase, setStartupPhase] = useState(playStartupAnimation ? 0 : 5);

  // Startup Animation Sequence
  useEffect(() => {
    if (!playStartupAnimation) return;

    const sequence = [
      // 0.3s: Face pops (straight)
      { phase: 1, delay: 300, target: { x: 0, y: 0 }, speed: '0.4s cubic-bezier(0.34, 1.56, 0.64, 1)' },

      // 0.7s: Look gently down-left (more extreme left)
      { phase: 2, delay: 700, target: { x: -10 - Math.random() * 4, y: 3 + Math.random() * 3 }, speed: '0.6s ease-in-out' },

      // 1.2s: Slow, curious pan across to the far right side
      { phase: 3, delay: 1200, target: { x: 10 + Math.random() * 4, y: 1 + Math.random() * 3 }, speed: '0.8s ease-in-out' },

      // 1.7s: Lock onto the user (straight ahead) smoothly
      { phase: 4, delay: 1700, target: { x: 0, y: 0 }, speed: '0.4s ease-out' },

      // 2.0s: Done, resume normal tracking
      { phase: 5, delay: 2000, target: null, speed: '0.1s ease-out' },
    ];

    const timeouts = sequence.map((step) =>
      setTimeout(() => {
        setStartupPhase(step.phase);
        if (step.target) {
          setOffset(step.target);
        }
        setTransitionSpeed(step.speed);

        if (step.phase === 5 && onAnimationComplete) {
          onAnimationComplete();
        }
      }, step.delay)
    );

    return () => timeouts.forEach(clearTimeout);
  }, [playStartupAnimation, onAnimationComplete]);

  // Mouse/Touch tracking for parallax (only when startup is complete)
  useEffect(() => {
    if (startupPhase < 5) return; // Disable tracking during startup

    let idleTimeout: NodeJS.Timeout;

    const handleMove = (clientX: number, clientY: number) => {
      setTransitionSpeed('0.1s ease-out'); // Responsive tracking

      let moveX = 0;
      let moveY = 0;

      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const avatarCenterX = rect.left + rect.width / 2;
        const avatarCenterY = rect.top + rect.height / 2;

        const dx = clientX - avatarCenterX;
        const dy = clientY - avatarCenterY;

        // Gaze reaches max displacement at 300px away from the avatar center
        const referenceDistance = 300;
        moveX = Math.max(-1, Math.min(1, dx / referenceDistance));
        moveY = Math.max(-1, Math.min(1, dy / referenceDistance));
      }

      const maxDisplacement = 15;

      setOffset({
        x: moveX * maxDisplacement,
        y: moveY * maxDisplacement
      });

      // Reset idle timer
      clearTimeout(idleTimeout);
      idleTimeout = setTimeout(() => {
        setTransitionSpeed('1.5s ease-in-out'); // Smooth slow return
        setOffset({ x: 0, y: 0 }); // Look straight
      }, 6000); // Wait 6 seconds of no movement
    };

    const onMouseMove = (e: MouseEvent) => handleMove(e.clientX, e.clientY);
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        handleMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('touchmove', onTouchMove);

    // Initial idle timer setup
    idleTimeout = setTimeout(() => {
      setTransitionSpeed('1.5s ease-in-out');
      setOffset({ x: 0, y: 0 });
    }, 6000);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('touchmove', onTouchMove);
      clearTimeout(idleTimeout);
    };
  }, [startupPhase]);

  // Blinking logic (random intervals)
  useEffect(() => {
    const blink = () => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 150); // Blink duration

      // Schedule next blink randomly between 2s and 6s
      const nextBlink = Math.random() * 4000 + 2000;
      setTimeout(blink, nextBlink);
    };

    const initialTimer = setTimeout(blink, 2000);
    return () => clearTimeout(initialTimer);
  }, []);

  const showFace = startupPhase >= 1;

  return (
    <div ref={containerRef} className="relative w-28 h-28 sm:w-28 sm:h-28 md:w-32 md:h-32 mb-4 md:mb-8 mx-auto flex items-center justify-center animate-[float_4s_ease-in-out_infinite]">

      {/* Diffused Aurora Sphere - slowly spinning to create shifting color effect */}
      <div
        className="absolute inset-0 rounded-full blur-xl opacity-100 animate-[spin_15s_linear_infinite]"
        style={{
          background: 'radial-gradient(circle at 35% 35%, #F2F2F2 0%, #1C4D8C 55%, #163359 100%)',
          transform: 'scale(1.15)',
          boxShadow: '0 10px 40px rgba(28, 77, 140, 0.4)'
        }}
      />
      <div
        className="absolute inset-2 rounded-full blur-lg opacity-90 animate-[spin_10s_linear_infinite_reverse]"
        style={{
          background: 'radial-gradient(circle at 65% 65%, #1C4D8C 0%, #163359 50%, #F2F2F2 100%)',
          transform: 'scale(1.05)'
        }}
      />

      {/* 3D Parallax Face */}
      <svg
        viewBox="0 0 100 100"
        className={cn(
          "relative z-10 w-full h-full text-white drop-shadow-lg overflow-visible transition-all duration-500 ease-out",
          showFace ? "opacity-100 scale-100" : "opacity-0 scale-50"
        )}
      >

        {/* Eyebrows (move slowest) */}
        <g style={{ transform: `translate(${offset.x * 0.3}px, ${offset.y * 0.3}px)`, transition: `transform ${transitionSpeed}` }}>
          <path d="M 32 38 Q 38 30 44 38" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
          <path d="M 56 38 Q 62 30 68 38" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
        </g>

        {/* Eyes (move medium speed) - open/close based on isBlinking */}
        <g style={{ transform: `translate(${offset.x * 0.7}px, ${offset.y * 0.7}px)`, transition: `transform ${transitionSpeed}` }}>
          <ellipse cx="38" cy="48" rx="3.5" ry={isBlinking ? 0.5 : 3.5} fill="currentColor" className="transition-all duration-75" />
          <ellipse cx="62" cy="48" rx="3.5" ry={isBlinking ? 0.5 : 3.5} fill="currentColor" className="transition-all duration-75" />
        </g>

        {/* Nose (moves fastest to simulate sticking out) */}
        <g style={{ transform: `translate(${offset.x * 1.2}px, ${offset.y * 1.2}px)`, transition: `transform ${transitionSpeed}` }}>
          <path d="M 50 49 L 50 63 L 56 63" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
        </g>

      </svg>
    </div>
  );
}

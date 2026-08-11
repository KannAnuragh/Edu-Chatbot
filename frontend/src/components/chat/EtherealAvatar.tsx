import React, { useEffect, useState } from 'react';

export default function EtherealAvatar() {
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isBlinking, setIsBlinking] = useState(false);

  // Mouse/Touch tracking for parallax
  useEffect(() => {
    const handleMove = (clientX: number, clientY: number) => {
      const centerX = window.innerWidth / 2;
      const centerY = window.innerHeight / 2;
      
      const moveX = (clientX - centerX) / centerX;
      const moveY = (clientY - centerY) / centerY;
      
      const maxDisplacement = 15; 
      
      setOffset({
        x: moveX * maxDisplacement,
        y: moveY * maxDisplacement
      });
    };

    const onMouseMove = (e: MouseEvent) => handleMove(e.clientX, e.clientY);
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        handleMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('touchmove', onTouchMove);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('touchmove', onTouchMove);
    };
  }, []);

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

  return (
    <div className="relative w-32 h-32 mb-8 flex items-center justify-center animate-[float_4s_ease-in-out_infinite]">
      
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
      <svg viewBox="0 0 100 100" className="relative z-10 w-20 h-20 text-white drop-shadow-lg overflow-visible">
        
        {/* Eyebrows (move slowest) */}
        <g style={{ transform: `translate(${offset.x * 0.3}px, ${offset.y * 0.3}px)`, transition: 'transform 0.1s ease-out' }}>
          <path d="M 32 38 Q 38 30 44 38" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
          <path d="M 56 38 Q 62 30 68 38" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
        </g>
        
        {/* Eyes (move medium speed) - open/close based on isBlinking */}
        <g style={{ transform: `translate(${offset.x * 0.7}px, ${offset.y * 0.7}px)`, transition: 'transform 0.1s ease-out' }}>
          <ellipse cx="38" cy="48" rx="3.5" ry={isBlinking ? 0.5 : 3.5} fill="currentColor" className="transition-all duration-75" />
          <ellipse cx="62" cy="48" rx="3.5" ry={isBlinking ? 0.5 : 3.5} fill="currentColor" className="transition-all duration-75" />
        </g>
        
        {/* Nose (moves fastest to simulate sticking out) */}
        <g style={{ transform: `translate(${offset.x * 1.2}px, ${offset.y * 1.2}px)`, transition: 'transform 0.1s ease-out' }}>
          <path d="M 50 49 L 50 63 L 56 63" fill="none" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        
      </svg>
    </div>
  );
}

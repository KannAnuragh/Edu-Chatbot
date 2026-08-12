const NUM_TICKS = 24;
const MAX_SCALE = 3.5;
const SIGMA = 2.5; // Controls the spread of the Gaussian curve

const container = document.getElementById('scrub-container');
const rail = document.getElementById('scrub-rail');

// Generate ticks
const ticks = [];
for (let i = 0; i < NUM_TICKS; i++) {
  const tick = document.createElement('div');
  tick.classList.add('tick');
  rail.appendChild(tick);
  ticks.push({ el: tick, scale: 1, transX: 0, transY: 0 });
}

let prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', e => {
  prefersReducedMotion = e.matches;
  if (prefersReducedMotion) resetTicks();
});

function handleMove(e) {
  if (prefersReducedMotion) return;
  
  const clientX = e.touches ? e.touches[0].clientX : e.clientX;
  const clientY = e.touches ? e.touches[0].clientY : e.clientY;
  
  updateTicks(clientX, clientY);
}

function handleLeave() {
  if (prefersReducedMotion) return;
  resetTicks();
}

function resetTicks() {
  ticks.forEach(t => {
    t.scale = 1;
    t.transX = 0;
    t.transY = 0;
    applyStyles(t);
  });
}

function updateTicks(pointerX, pointerY) {
  const isVertical = window.innerWidth >= 680;
  const baseSize = 16; 
  const gap = 6;       
  const itemSpacing = baseSize + gap;
  
  // Use actual bounding box to support any CSS placement
  const rect = rail.getBoundingClientRect();
  const railCenter = isVertical ? rect.top + rect.height / 2 : rect.left + rect.width / 2;
  const pointerPos = isVertical ? pointerY : pointerX;
  
  const pointerOffset = pointerPos - railCenter;
  let hoverIndex = (pointerOffset / itemSpacing) + (NUM_TICKS - 1) / 2;
  
  // Clamp hoverIndex for smooth boundaries
  hoverIndex = Math.max(-2, Math.min(NUM_TICKS + 1, hoverIndex));
  
  const sizes = [];
  
  for (let i = 0; i < NUM_TICKS; i++) {
    const distance = Math.abs(i - hoverIndex);
    // Gaussian magnification
    const scale = 1 + (MAX_SCALE - 1) * Math.exp(-(distance * distance) / (2 * SIGMA * SIGMA));
    
    ticks[i].scale = scale;
    sizes.push(baseSize * scale);
  }
  
  // Calculate translations so items remain contiguous
  const totalLength = NUM_TICKS * baseSize + (NUM_TICKS - 1) * gap;
  const newTotalLength = sizes.reduce((a, b) => a + b, 0) + (NUM_TICKS - 1) * gap;
  
  const trans_centered = [];
  let currentOffset = -newTotalLength / 2;
  
  for (let i = 0; i < NUM_TICKS; i++) {
    const size = sizes[i];
    const newCenter = currentOffset + size / 2;
    const originalCenter = i * itemSpacing + baseSize / 2 - totalLength / 2;
    trans_centered.push(newCenter - originalCenter);
    currentOffset += size + gap;
  }
  
  // Anchor the dock at the cursor to prevent items slipping away
  let anchorShift = 0;
  if (hoverIndex <= 0) {
    anchorShift = trans_centered[0] || 0;
  } else if (hoverIndex >= NUM_TICKS - 1) {
    anchorShift = trans_centered[NUM_TICKS - 1] || 0;
  } else {
    const indexFloor = Math.floor(hoverIndex);
    const fraction = hoverIndex - indexFloor;
    anchorShift = trans_centered[indexFloor] * (1 - fraction) + trans_centered[indexFloor + 1] * fraction;
  }
  
  for (let i = 0; i < NUM_TICKS; i++) {
    const trans = trans_centered[i] - anchorShift;
    
    if (isVertical) {
      ticks[i].transY = trans;
      ticks[i].transX = 0;
    } else {
      ticks[i].transX = trans;
      ticks[i].transY = 0;
    }
    
    applyStyles(ticks[i]);
  }
}

function applyStyles(t) {
  t.el.style.setProperty('--scale', t.scale);
  t.el.style.setProperty('--translate-y', `${t.transY}px`);
  t.el.style.setProperty('--translate-x', `${t.transX}px`);
}

container.addEventListener('mousemove', handleMove);
container.addEventListener('mouseleave', handleLeave);
container.addEventListener('touchmove', handleMove, { passive: false });
container.addEventListener('touchend', handleLeave);
container.addEventListener('touchcancel', handleLeave);

container.addEventListener('touchstart', (e) => {
  e.preventDefault(); 
  handleMove(e);
}, { passive: false });

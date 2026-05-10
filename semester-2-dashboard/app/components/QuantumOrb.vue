<template>
  <div class="flex flex-col items-center gap-3 py-4 px-3 select-none">

    <!-- ── Bloch Sphere SVG ──────────────────────────────────────────── -->
    <svg viewBox="0 0 100 100" class="w-28 h-28" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="qcore" cx="50%" cy="50%" r="50%">
          <stop offset="0%"   stop-color="#ffffff" stop-opacity="1"/>
          <stop offset="30%"  stop-color="#b4694f" stop-opacity="1"/>
          <stop offset="100%" stop-color="#7a2d16" stop-opacity="0.15"/>
        </radialGradient>

        <radialGradient id="qhalo" cx="50%" cy="50%" r="50%">
          <stop offset="0%"   stop-color="#b4694f" stop-opacity="0.14"/>
          <stop offset="65%"  stop-color="#f4b88a" stop-opacity="0.04"/>
          <stop offset="100%" stop-color="#b4694f" stop-opacity="0"/>
        </radialGradient>

        <filter id="glow-s" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="1.4" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>

        <filter id="glow-l" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="3" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <!-- Breathing halo -->
      <circle cx="50" cy="50" r="46" fill="url(#qhalo)">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="4s" repeatCount="indefinite"/>
      </circle>

      <!-- Sphere outline -->
      <circle cx="50" cy="50" r="36" fill="none" stroke="rgba(154,158,165,0.1)" stroke-width="0.8"/>

      <!-- Pole labels: |0⟩ north, |1⟩ south -->
      <text x="50" y="9"  text-anchor="middle" font-family="monospace" font-size="5.5" fill="rgba(180,105,79,0.55)">|0⟩</text>
      <text x="50" y="98" text-anchor="middle" font-family="monospace" font-size="5.5" fill="rgba(244,184,138,0.55)">|1⟩</text>

      <!-- Axis dashes -->
      <line x1="50" y1="13" x2="50" y2="87" stroke="rgba(180,105,79,0.09)" stroke-width="0.5" stroke-dasharray="2 3"/>
      <line x1="14" y1="50" x2="86" y2="50" stroke="rgba(180,105,79,0.09)" stroke-width="0.5" stroke-dasharray="2 3"/>

      <!-- Equatorial ring — rotates CW -->
      <g>
        <animateTransform attributeName="transform" type="rotate"
          from="0 50 50" to="360 50 50" dur="9s" repeatCount="indefinite"/>
        <ellipse cx="50" cy="50" rx="36" ry="9"
          fill="none" stroke="rgba(180,105,79,0.5)" stroke-width="0.8"/>
        <circle cx="86" cy="50" r="2.5" fill="#b4694f" filter="url(#glow-s)">
          <animate attributeName="opacity" values="0.6;1;0.6" dur="2.2s" repeatCount="indefinite"/>
        </circle>
      </g>

      <!-- Vertical ring — rotates CCW, offset 90° -->
      <g>
        <animateTransform attributeName="transform" type="rotate"
          from="90 50 50" to="-270 50 50" dur="7s" repeatCount="indefinite"/>
        <ellipse cx="50" cy="50" rx="9" ry="36"
          fill="none" stroke="rgba(244,184,138,0.45)" stroke-width="0.8"/>
        <circle cx="50" cy="14" r="2" fill="#f4b88a" filter="url(#glow-s)">
          <animate attributeName="opacity" values="0.5;1;0.5" dur="1.8s" repeatCount="indefinite"/>
        </circle>
      </g>

      <!-- Diagonal ring — slow, steel/silver accent -->
      <g>
        <animateTransform attributeName="transform" type="rotate"
          from="45 50 50" to="405 50 50" dur="14s" repeatCount="indefinite"/>
        <ellipse cx="50" cy="50" rx="36" ry="9"
          fill="none" stroke="rgba(154,158,165,0.25)" stroke-width="0.7"/>
        <circle cx="86" cy="50" r="1.4" fill="rgba(154,158,165,0.6)" filter="url(#glow-s)"/>
      </g>

      <!-- State vector |ψ⟩ — rotates smoothly -->
      <g>
        <animateTransform attributeName="transform" type="rotate"
          from="0 50 50" to="360 50 50" dur="5s" repeatCount="indefinite"/>
        <line x1="50" y1="50" x2="50" y2="17"
          stroke="#b4694f" stroke-width="1.3" stroke-opacity="0.9" stroke-linecap="round"/>
        <circle cx="50" cy="17" r="2.5" fill="#b4694f" filter="url(#glow-l)">
          <animate attributeName="r" values="2;3;2" dur="1.6s" repeatCount="indefinite"/>
        </circle>
      </g>

      <!-- Core (pulsing) -->
      <circle cx="50" cy="50" r="7" fill="url(#qcore)" filter="url(#glow-l)">
        <animate attributeName="r" values="6;8;6" dur="2.8s" repeatCount="indefinite"/>
      </circle>
    </svg>

    <!-- ── Bra-ket label ─────────────────────────────────────────────── -->
    <div class="text-center space-y-0.5">
      <p class="text-[9px] font-mono tracking-[0.2em] uppercase text-[#b4694f]/50">Qubit State</p>
      <p class="text-[11px] font-mono text-[#b4694f]/60">|ψ⟩ = α|0⟩ + β|1⟩</p>
    </div>

    <!-- ── Probability amplitude wave ───────────────────────────────── -->
    <svg viewBox="0 0 120 24" class="w-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="wg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stop-color="#b4694f" stop-opacity="0"/>
          <stop offset="25%"  stop-color="#b4694f" stop-opacity="0.6"/>
          <stop offset="50%"  stop-color="#f4b88a" stop-opacity="0.7"/>
          <stop offset="75%"  stop-color="#b4694f" stop-opacity="0.6"/>
          <stop offset="100%" stop-color="#b4694f" stop-opacity="0"/>
        </linearGradient>
        <linearGradient id="wg2" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stop-color="#f4b88a" stop-opacity="0"/>
          <stop offset="30%"  stop-color="#f4b88a" stop-opacity="0.35"/>
          <stop offset="70%"  stop-color="#b4694f" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#f4b88a" stop-opacity="0"/>
        </linearGradient>
      </defs>

      <!-- Wave 1 — amplitude wave -->
      <path
        d="M0,12 C10,4 20,20 30,12 C40,4 50,20 60,12 C70,4 80,20 90,12 C100,4 110,20 120,12"
        stroke="url(#wg)" stroke-width="1.2" fill="none"
        stroke-dasharray="6 3"
      >
        <animate attributeName="stroke-dashoffset" from="0" to="-27" dur="1.8s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.5;1;0.5" dur="3.5s" repeatCount="indefinite"/>
      </path>

      <!-- Wave 2 — phase-shifted interference -->
      <path
        d="M0,12 C10,20 20,4 30,12 C40,20 50,4 60,12 C70,20 80,4 90,12 C100,20 110,4 120,12"
        stroke="url(#wg2)" stroke-width="0.8" fill="none"
        stroke-dasharray="4 5"
      >
        <animate attributeName="stroke-dashoffset" from="0" to="27" dur="2.4s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.3;0.7;0.3" dur="4s" repeatCount="indefinite"/>
      </path>
    </svg>

  </div>
</template>

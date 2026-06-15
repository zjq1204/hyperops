<template>
  <section data-testid="auth-showcase" class="auth-showcase">
    <span class="page-eyebrow auth-showcase__eyebrow">{{ t('auth.heroEyebrow') }}</span>

    <div class="auth-showcase__copy">
      <h1 class="auth-showcase__title">{{ t('auth.heroTitle') }}</h1>
      <p class="auth-showcase__description">{{ t('auth.heroDescription') }}</p>
    </div>

    <div class="auth-showcase__stage">
      <div class="auth-showcase__stage-orb auth-showcase__stage-orb--sky"></div>
      <div class="auth-showcase__stage-orb auth-showcase__stage-orb--violet"></div>
      <div class="auth-showcase__stage-orb auth-showcase__stage-orb--orange"></div>

      <div class="auth-figure auth-figure--left" :class="{ 'auth-figure--celebrate': active }" :style="butlerBoxStyle">
        <svg class="auth-figure__svg" viewBox="0 0 200 200" aria-hidden="true">
          <defs>
            <linearGradient id="butler-body-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#64748b" />
              <stop offset="100%" stop-color="#334155" />
            </linearGradient>
          </defs>

          <ellipse cx="100" cy="146" :rx="38 + butler.squishY * 0.3" ry="5" class="auth-shadow auth-shadow--slate" />

          <g :transform="`translate(${butler.swayX}, 0)`">
            <path d="M 64 94 Q 56 82 66 74 Q 72 84 64 94" fill="#e2e8f0" stroke="#475569" stroke-width="1.5" />
            <path d="M 136 94 Q 144 82 134 74 Q 128 84 136 94" fill="#e2e8f0" stroke="#475569" stroke-width="1.5" />
          </g>

          <path
            d="M 65 142 L 65 105 L 135 105 L 135 142 Z"
            fill="url(#butler-body-grad)"
            stroke="#1e293b"
            stroke-width="2"
            stroke-linejoin="round"
          />

          <polygon points="90,105 110,105 100,118" fill="#ffffff" stroke="#1e293b" stroke-width="1.5" />
          <g transform="translate(100, 114)">
            <polygon points="0,0 -8,-5 -8,5" fill="#ef4444" stroke="#991b1b" stroke-width="1" />
            <polygon points="0,0 8,-5 8,5" fill="#ef4444" stroke="#991b1b" stroke-width="1" />
            <circle cx="0" cy="0" r="2.5" fill="#b91c1c" />
          </g>
          <circle cx="100" cy="125" r="2" fill="#ffffff" />
          <circle cx="100" cy="133" r="2" fill="#ffffff" />

          <circle :cx="100 + butler.swayX" cy="94" r="26" fill="#f8fafc" stroke="#334155" stroke-width="2" />

          <g :transform="`translate(${butler.lookX}, ${butler.lookY})`">
            <circle cx="83" cy="97" r="4" fill="#fda4af" :opacity="0.3 + (active ? 0.15 : 0)" />
            <circle cx="117" cy="97" r="4" fill="#fda4af" :opacity="0.3 + (active ? 0.15 : 0)" />

            <g v-if="active" class="auth-celebrate-pulse">
              <path d="M 87 91 C 85 88, 81 89, 81 92 C 81 95, 87 98, 87 98 C 87 98, 93 95, 93 92 C 93 89, 89 88, 87 91 Z" fill="#fb7185" stroke="#e11d48" stroke-width="0.8" />
              <path d="M 113 91 C 111 88, 107 89, 107 92 C 107 95, 113 98, 113 98 C 113 98, 119 95, 119 92 C 119 89, 115 88, 113 91 Z" fill="#fb7185" stroke="#e11d48" stroke-width="0.8" />
            </g>
            <template v-else-if="butler.shyness < 0.5">
              <circle :cx="87 + butler.lookX * 0.4" :cy="91 + butler.lookY * 0.4" r="2.5" fill="#334155" />
              <circle :cx="113 + butler.lookX * 0.4" :cy="91 + butler.lookY * 0.4" r="2.5" fill="#334155" />
              <circle :cx="113 + butler.lookX * 0.3" :cy="91 + butler.lookY * 0.3" r="6.5" fill="none" stroke="#eab308" stroke-width="1.8" />
              <line x1="119.5" y1="91" x2="128" y2="100" stroke="#eab308" stroke-width="1" />
            </template>
            <template v-else>
              <path d="M 83 93 Q 87 89 91 93" fill="none" stroke="#334155" stroke-width="2.5" stroke-linecap="round" />
              <path d="M 109 93 Q 113 89 117 93" fill="none" stroke="#334155" stroke-width="2.5" stroke-linecap="round" />
            </template>

            <path d="M 96 100 Q 100 102 104 100" fill="none" stroke="#334155" stroke-width="2" stroke-linecap="round" />
          </g>

          <circle :cx="butler.pawLX" :cy="butler.pawLY" r="7.5" fill="#ffffff" stroke="#475569" stroke-width="1.5" />
          <circle :cx="butler.pawRX" :cy="butler.pawRY" r="7.5" fill="#ffffff" stroke="#475569" stroke-width="1.5" />
        </svg>
      </div>

      <div class="auth-figure auth-figure--center" :class="{ 'auth-figure--celebrate': active }" :style="heroBoxStyle">
        <svg class="auth-figure__svg auth-figure__svg--hero" viewBox="0 0 200 200" aria-hidden="true">
          <defs>
            <linearGradient id="hero-shell-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#f8fafc" />
              <stop offset="100%" stop-color="#cbd5e1" />
            </linearGradient>
            <linearGradient id="hero-visor-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#0f172a" />
              <stop offset="100%" stop-color="#1e293b" />
            </linearGradient>
            <linearGradient id="hero-glow-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#38bdf8" />
              <stop offset="100%" stop-color="#0284c7" />
            </linearGradient>
            <filter id="hero-visor-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <ellipse :cx="100" :cy="168" :rx="34 - hero.hoverY * 0.4" ry="6" class="auth-shadow auth-shadow--sky" />
          <circle cx="100" :cy="hero.bodyY" r="72" fill="none" stroke="#dbeafe" stroke-width="1" stroke-dasharray="4 7" opacity="0.38" />

          <path :d="`M 100 ${hero.bodyY - 45} L 100 ${hero.bodyY - 60}`" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" />
          <circle
            cx="100"
            :cy="hero.bodyY - 61"
            r="4"
            fill="#22d3ee"
            stroke="#0891b2"
            stroke-width="1"
            :class="{ 'auth-celebrate-pulse': active }"
          />

          <rect
            x="63"
            :y="hero.bodyY - 47"
            width="74"
            height="94"
            rx="37"
            fill="url(#hero-shell-grad)"
            stroke="#94a3b8"
            stroke-width="2.2"
          />

          <path
            :d="`M 84 ${hero.bodyY - 32} Q 100 ${hero.bodyY - 44} 116 ${hero.bodyY - 32}`"
            fill="none"
            stroke="rgba(255,255,255,0.6)"
            stroke-width="2"
            stroke-linecap="round"
          />

          <circle cx="100" :cy="hero.bodyY + 28" r="6" fill="#38bdf8" stroke="#67e8f9" stroke-width="1.5" :class="{ 'auth-celebrate-pulse': active }" />

          <g :transform="`translate(${hero.lookX}, ${hero.lookY})`">
            <rect
              x="73"
              :y="hero.bodyY - 19"
              width="54"
              height="34"
              rx="17"
              fill="url(#hero-visor-grad)"
              stroke="#475569"
              stroke-width="1.7"
            />

            <g v-if="active" filter="url(#hero-visor-glow)" class="auth-celebrate-pulse">
              <path :d="`M 86 ${hero.bodyY - 12} L 89 ${hero.bodyY - 12} L 90 ${hero.bodyY - 11} L 91 ${hero.bodyY - 12} L 94 ${hero.bodyY - 12} L 95 ${hero.bodyY - 11} L 95 ${hero.bodyY - 8} L 90 ${hero.bodyY - 3} L 85 ${hero.bodyY - 8} Z`" fill="#22d3ee" />
              <path :d="`M 106 ${hero.bodyY - 12} L 109 ${hero.bodyY - 12} L 110 ${hero.bodyY - 11} L 111 ${hero.bodyY - 12} L 114 ${hero.bodyY - 12} L 115 ${hero.bodyY - 11} L 115 ${hero.bodyY - 8} L 110 ${hero.bodyY - 3} L 105 ${hero.bodyY - 8} Z`" fill="#22d3ee" />
            </g>
            <g v-else-if="hero.shyness < 0.5" fill="#22d3ee" filter="url(#hero-visor-glow)">
              <rect :x="87 + hero.lookX * 0.3" :y="hero.bodyY - 11" width="6" height="12" rx="3" />
              <rect :x="107 + hero.lookX * 0.3" :y="hero.bodyY - 11" width="6" height="12" rx="3" />
            </g>
            <g v-else fill="none" stroke="#22d3ee" stroke-width="2.5" stroke-linecap="round" filter="url(#hero-visor-glow)">
              <path :d="`M 86 ${hero.bodyY - 5} Q 91 ${hero.bodyY - 10} 95 ${hero.bodyY - 5}`" />
              <path :d="`M 105 ${hero.bodyY - 5} Q 110 ${hero.bodyY - 10} 114 ${hero.bodyY - 5}`" />
            </g>
          </g>

          <g :style="{ opacity: hero.handOpacity }">
            <circle :cx="hero.handLX" :cy="hero.handLY" r="11" fill="url(#hero-shell-grad)" stroke="#94a3b8" stroke-width="1.5" />
            <circle v-if="active" :cx="hero.handLX" :cy="hero.handLY" r="5" fill="url(#hero-glow-grad)" class="auth-celebrate-pulse" />
          </g>
          <g :style="{ opacity: hero.handOpacity }">
            <circle :cx="hero.handRX" :cy="hero.handRY" r="11" fill="url(#hero-shell-grad)" stroke="#94a3b8" stroke-width="1.5" />
            <circle v-if="active" :cx="hero.handRX" :cy="hero.handRY" r="5" fill="url(#hero-glow-grad)" class="auth-celebrate-pulse" />
          </g>
        </svg>
      </div>

      <div class="auth-figure auth-figure--right" :class="{ 'auth-figure--celebrate': active }" :style="foxBoxStyle">
        <svg class="auth-figure__svg" viewBox="0 0 200 200" aria-hidden="true">
          <defs>
            <linearGradient id="fox-body-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#f97316" />
              <stop offset="100%" stop-color="#ea580c" />
            </linearGradient>
          </defs>

          <ellipse cx="100" cy="146" rx="38" ry="5" class="auth-shadow auth-shadow--orange" />

          <g :transform="`translate(${fox.swayX}, 0)`">
            <polygon points="62,94 58,58 84,86" fill="#f97316" stroke="#c2410c" stroke-width="1.8" stroke-linejoin="round" />
            <polygon points="65,90 62,68 78,85" fill="#ffedd5" />
            <polygon points="138,94 142,58 116,86" fill="#f97316" stroke="#c2410c" stroke-width="1.8" stroke-linejoin="round" />
            <polygon points="135,90 138,68 122,85" fill="#ffedd5" />
          </g>

          <polygon points="62,142 100,95 138,142" fill="url(#fox-body-grad)" stroke="#c2410c" stroke-width="2" stroke-linejoin="round" />
          <polygon points="100,121 102,125 106,126 103,129 104,133 100,131 96,133 97,129 94,126 98,125" fill="#fde047" stroke="#eab308" stroke-width="0.5" class="auth-celebrate-pulse" />

          <g :transform="`translate(${fox.swayX}, 0)`">
            <polygon points="65,95 100,122 135,95 100,74" fill="url(#fox-body-grad)" stroke="#c2410c" stroke-width="2" stroke-linejoin="round" />
            <polygon points="65,95 100,122 82,106" fill="#ffffff" stroke="#c2410c" stroke-width="1" stroke-linejoin="round" opacity="0.9" />
            <polygon points="135,95 100,122 118,106" fill="#ffffff" stroke="#c2410c" stroke-width="1" stroke-linejoin="round" opacity="0.9" />
            <polygon points="97,118 103,118 100,122" fill="#1e293b" />
          </g>

          <g :transform="`translate(${fox.lookX}, ${fox.lookY})`">
            <circle cx="78" cy="98" r="4.5" fill="#fda4af" :opacity="0.35 + (active ? 0.15 : 0)" />
            <circle cx="122" cy="98" r="4.5" fill="#fda4af" :opacity="0.35 + (active ? 0.15 : 0)" />

            <g v-if="active" class="auth-celebrate-pulse">
              <polygon points="85,88 87,92 91,93 88,96 89,100 85,98 81,100 82,96 79,93 83,92" fill="#fde047" stroke="#f59e0b" stroke-width="1" />
              <polygon points="115,88 117,92 121,93 118,96 119,100 115,98 111,100 112,96 109,93 113,92" fill="#fde047" stroke="#f59e0b" stroke-width="1" />
            </g>
            <template v-else-if="fox.shyness < 0.5">
              <path d="M 81 92 L 89 95" stroke="#7c2d12" stroke-width="3.5" stroke-linecap="round" />
              <path d="M 119 92 L 111 95" stroke="#7c2d12" stroke-width="3.5" stroke-linecap="round" />
            </template>
            <template v-else>
              <path d="M 81 90 L 88 95 L 81 100" fill="none" stroke="#7c2d12" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              <path d="M 119 90 L 112 95 L 119 100" fill="none" stroke="#7c2d12" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            </template>

            <path d="M 97 106 C 98 108, 100 108, 100 106 C 100 108, 102 108, 103 106" fill="none" stroke="#7c2d12" stroke-width="1.5" stroke-linecap="round" />
          </g>

          <circle :cx="fox.gloveLX" :cy="fox.gloveLY" r="7.5" fill="#f97316" stroke="#c2410c" stroke-width="1.5" />
          <circle :cx="fox.gloveRX" :cy="fox.gloveRY" r="7.5" fill="#f97316" stroke="#c2410c" stroke-width="1.5" />
        </svg>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  active: {
    type: Boolean,
    default: false,
  },
  passwordFocused: {
    type: Boolean,
    default: false,
  },
})

const { t } = useI18n()

const pointer = reactive({
  x: 400,
  y: 300,
})

const ticker = ref(0)
const shyness = ref(0)
let frameId = null
let shynessFrameId = null

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const toFigureSpace = (x, y, cx = 100, cy = 110) => {
  const dx = x - cx
  const dy = y - cy
  const distance = Math.sqrt(dx * dx + dy * dy) || 1
  const normX = dx / distance
  const normY = dy / distance

  return {
    dx,
    dy,
    lookX: normX * 8,
    lookY: normY * 5,
  }
}

const hero = computed(() => {
  const localX = 100 + (pointer.x - window.innerWidth / 2) / 20
  const localY = 100 + (pointer.y - window.innerHeight / 2) / 22
  const face = toFigureSpace(localX, localY)
  const hoverY = Math.sin(ticker.value) * 5
  const bodyY = 100 + hoverY
  const waveHandY = Math.sin(ticker.value * 3.5) * 12
  const waveHandX = Math.cos(ticker.value * 3.5) * 8
  const lookX = face.lookX * (1 - shyness.value)
  const lookY = face.lookY * (1 - shyness.value)

  return {
    bodyY,
    hoverY,
    lookX,
    lookY,
    shyness: shyness.value,
    handOpacity: 1,
    handLX: props.active ? 45 + waveHandX : 42 * (1 - shyness.value) + (90 + lookX) * shyness.value,
    handLY: props.active ? bodyY - 35 + waveHandY : (bodyY + 20) * (1 - shyness.value) + (bodyY - 6 + lookY) * shyness.value,
    handRX: props.active ? 155 - waveHandX : 158 * (1 - shyness.value) + (110 + lookX) * shyness.value,
    handRY: props.active ? bodyY - 35 - waveHandY : (bodyY + 20) * (1 - shyness.value) + (bodyY - 6 + lookY) * shyness.value,
  }
})

const butler = computed(() => {
  const localX = 100 + (pointer.x - window.innerWidth * 0.28) / 24
  const localY = 100 + (pointer.y - window.innerHeight * 0.58) / 24
  const face = toFigureSpace(localX, localY)
  const squishY = Math.sin(ticker.value) * 2
  const lookX = face.lookX * (1 - shyness.value)
  const lookY = face.lookY * (1 - shyness.value)
  const swayX = lookX * 0.3

  return {
    squishY,
    swayX,
    lookX,
    lookY,
    shyness: shyness.value,
    pawLX: props.active ? 50 + Math.cos(ticker.value * 3.5) * 6 : 72 * (1 - shyness.value) + (83 + swayX) * shyness.value,
    pawLY: props.active ? 110 + Math.sin(ticker.value * 3.5) * 10 : 138 * (1 - shyness.value) + (91 + lookY) * shyness.value,
    pawRX: props.active ? 150 - Math.cos(ticker.value * 3.5) * 6 : 128 * (1 - shyness.value) + (117 + swayX) * shyness.value,
    pawRY: props.active ? 110 - Math.sin(ticker.value * 3.5) * 10 : 138 * (1 - shyness.value) + (91 + lookY) * shyness.value,
  }
})

const fox = computed(() => {
  const localX = 100 + (pointer.x - window.innerWidth * 0.72) / 24
  const localY = 100 + (pointer.y - window.innerHeight * 0.58) / 24
  const face = toFigureSpace(localX, localY)
  const lookX = face.lookX * (1 - shyness.value)
  const lookY = face.lookY * (1 - shyness.value)
  const swayX = lookX * 0.3

  return {
    swayX,
    lookX,
    lookY,
    shyness: shyness.value,
    gloveLX: props.active ? 50 + Math.cos(ticker.value * 3.5) * 6 : 71 * (1 - shyness.value) + (81 + swayX) * shyness.value,
    gloveLY: props.active ? 110 + Math.sin(ticker.value * 3.5) * 10 : 138 * (1 - shyness.value) + (95 + lookY) * shyness.value,
    gloveRX: props.active ? 150 - Math.cos(ticker.value * 3.5) * 6 : 129 * (1 - shyness.value) + (119 + swayX) * shyness.value,
    gloveRY: props.active ? 110 - Math.sin(ticker.value * 3.5) * 10 : 138 * (1 - shyness.value) + (95 + lookY) * shyness.value,
  }
})

const butlerBoxStyle = computed(() => {
  const shiftX = clamp((pointer.x - window.innerWidth * 0.28) / 40, -10, 10)
  return {
    transform: `translate3d(${shiftX}px, 0, 0) scale(0.74)`,
  }
})

const heroBoxStyle = computed(() => {
  const shiftX = clamp((pointer.x - window.innerWidth / 2) / 44, -12, 12)
  const shiftY = clamp((pointer.y - window.innerHeight / 2) / 55, -8, 8)
  return {
    transform: `translate(-50%, -50%) translate3d(${shiftX}px, ${shiftY}px, 0) scale(1.28)`,
  }
})

const foxBoxStyle = computed(() => {
  const shiftX = clamp((pointer.x - window.innerWidth * 0.72) / 40, -10, 10)
  return {
    transform: `translate3d(${shiftX}px, 0, 0) scale(0.74)`,
  }
})

const handlePointerMove = (event) => {
  pointer.x = event.clientX
  pointer.y = event.clientY
}

const syncShyness = () => {
  if (typeof window === 'undefined') {
    shyness.value = props.passwordFocused ? 1 : 0
    return
  }

  const target = props.passwordFocused ? 1 : 0

  if (shynessFrameId) {
    window.cancelAnimationFrame(shynessFrameId)
  }

  const updateShyness = () => {
    const diff = target - shyness.value

    if (Math.abs(diff) < 0.001) {
      shyness.value = target
      shynessFrameId = null
      return
    }

    shyness.value += diff * 0.15
    shynessFrameId = window.requestAnimationFrame(updateShyness)
  }

  shynessFrameId = window.requestAnimationFrame(updateShyness)
}

const animate = () => {
  ticker.value += 0.04
  frameId = window.requestAnimationFrame(animate)
}

watch(
  () => props.passwordFocused,
  () => {
    syncShyness()
  },
  { immediate: true },
)

onMounted(() => {
  if (typeof window === 'undefined') return

  pointer.x = window.innerWidth / 2
  pointer.y = window.innerHeight / 2
  window.addEventListener('pointermove', handlePointerMove, { passive: true })
  frameId = window.requestAnimationFrame(animate)
})

onBeforeUnmount(() => {
  if (typeof window === 'undefined') return

  window.removeEventListener('pointermove', handlePointerMove)
  if (frameId) {
    window.cancelAnimationFrame(frameId)
  }
  if (shynessFrameId) {
    window.cancelAnimationFrame(shynessFrameId)
  }
})
</script>

<style scoped>
.auth-showcase {
  max-width: 39rem;
}

.auth-showcase__eyebrow {
  background: rgba(15, 23, 42, 0.92);
  color: #9ab4e1;
}

.auth-showcase__copy {
  margin-top: 1.55rem;
}

.auth-showcase__title {
  color: #1e293b;
  font-family: 'Space Grotesk', 'IBM Plex Sans', sans-serif;
  font-size: clamp(2.9rem, 5vw, 4.4rem);
  font-weight: 700;
  letter-spacing: -0.055em;
  line-height: 1.02;
}

.auth-showcase__description {
  margin-top: 1.2rem;
  max-width: 34rem;
  color: #64748b;
  font-size: 1.02rem;
  line-height: 1.85;
}

.auth-showcase__stage {
  position: relative;
  margin-top: 2rem;
  min-height: 25rem;
  overflow: hidden;
  border-radius: 2.35rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.1)),
    radial-gradient(circle at 50% 42%, rgba(255, 255, 255, 0.2), transparent 38%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
}

.auth-showcase__stage::before {
  content: '';
  position: absolute;
  inset: 1.15rem;
  border: 1px solid rgba(255, 255, 255, 0.34);
  border-radius: 2rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.04));
  pointer-events: none;
}

.auth-showcase__stage-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(56px);
  pointer-events: none;
}

.auth-showcase__stage-orb--sky {
  left: 6%;
  top: 10%;
  height: 15rem;
  width: 15rem;
  background: rgba(191, 219, 254, 0.5);
}

.auth-showcase__stage-orb--violet {
  right: 12%;
  top: 16%;
  height: 13rem;
  width: 13rem;
  background: rgba(199, 210, 254, 0.38);
}

.auth-showcase__stage-orb--orange {
  left: 40%;
  bottom: 2%;
  height: 11rem;
  width: 11rem;
  background: rgba(254, 215, 170, 0.32);
}

.auth-figure {
  position: absolute;
  width: 14rem;
  height: 14rem;
  transform-origin: center center;
  transition: transform 0.14s ease-out;
}

.auth-figure--left {
  left: 0;
  bottom: 0.35rem;
}

.auth-figure--center {
  left: 50%;
  top: 50%;
  width: 19rem;
  height: 19rem;
  transform: translate(-50%, -50%);
}

.auth-figure--right {
  right: 0;
  bottom: 0.35rem;
}

.auth-figure__svg {
  height: 100%;
  width: 100%;
  overflow: visible;
  filter: drop-shadow(0 18px 28px rgba(148, 163, 184, 0.22));
}

.auth-figure__svg--hero {
  filter: drop-shadow(0 26px 32px rgba(56, 189, 248, 0.16));
}

.auth-shadow {
  opacity: 0.6;
}

.auth-shadow--slate {
  fill: rgba(203, 213, 225, 0.6);
}

.auth-shadow--sky {
  fill: rgba(224, 242, 254, 0.9);
}

.auth-shadow--orange {
  fill: rgba(254, 215, 170, 0.55);
}

.auth-figure--celebrate {
  animation: auth-figure-hop 0.72s cubic-bezier(0.25, 1, 0.5, 1) infinite;
}

.auth-figure--center.auth-figure--celebrate {
  animation-delay: 0.14s;
}

.auth-figure--right.auth-figure--celebrate {
  animation-delay: 0.28s;
}

.auth-celebrate-pulse {
  animation: auth-pulse 1.15s ease-in-out infinite;
}

@keyframes auth-figure-hop {
  0%,
  100% {
    margin-top: 0;
  }

  35% {
    margin-top: -1.05rem;
  }

  65% {
    margin-top: -0.2rem;
  }
}

@keyframes auth-pulse {
  0%,
  100% {
    opacity: 0.9;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.06);
  }
}

@media (max-width: 1280px) {
  .auth-figure--left,
  .auth-figure--right {
    width: 12rem;
    height: 12rem;
  }

  .auth-figure--center {
    width: 17rem;
    height: 17rem;
  }
}
</style>

<script setup>
// components/DeviceCard.vue
// Renders a single device control card

const props = defineProps({
  device: {
    type: Object,
    required: true,
  },
  videoUrl: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['start', 'stop', 'refresh'])

// ── QFlow runtime config (only relevant when device.id === 'pc') ──────────────

const VIDEO_OPTIONS = [
  { label: '1-Way  (traffic.mp4)', value: 'traffic.mp4' },
  { label: '2-Way  (traffic_bi.mp4)', value: 'traffic_bi.mp4' },
]

const VALID_GRID_PRESETS = [
  { label: '2 × 1  (2)', rows: 2, cols: 1 },
  { label: '2 × 2  (4)', rows: 2, cols: 2 },
  { label: '2 × 4  (8)', rows: 2, cols: 4 },
  { label: '4 × 4  (16)', rows: 4, cols: 4 },
  { label: '4 × 8  (32)', rows: 4, cols: 8 },
  { label: '8 × 8  (64)', rows: 8, cols: 8 },
]

const qflowConfig = reactive({
  videoSource: 'traffic_bi.mp4',
  rows: 4,
  cols: 8,
})

const isQFlow = computed(() => props.device.id === 'pc')

function isPowerOfTwo(n) {
  return n > 0 && (n & (n - 1)) === 0
}

const gridValid = computed(() => isPowerOfTwo(qflowConfig.rows * qflowConfig.cols))

const gridWarning = computed(() => {
  if (gridValid.value) return null
  return `${qflowConfig.rows} × ${qflowConfig.cols} = ${qflowConfig.rows * qflowConfig.cols} — must be a power of 2`
})

function applyGridPreset(preset) {
  qflowConfig.rows = preset.rows
  qflowConfig.cols = preset.cols
}

function handleActivate() {
  if (isQFlow.value) {
    emit('start', {
      video_source: qflowConfig.videoSource,
      rows: qflowConfig.rows,
      cols: qflowConfig.cols,
    })
  } else {
    emit('start')
  }
}

// ── derived display values ────────────────────────────────────────────────────

const onlineBadgeColor = computed(() => {
  if (props.device.online === null) return 'neutral'
  return props.device.online ? 'success' : 'error'
})

const onlineBadgeLabel = computed(() => {
  if (props.device.online === null) return 'Superposition'
  return props.device.online ? 'Entangled' : 'Decoherent'
})

const runningBadgeColor = computed(() => {
  if (props.device.running === null) return 'neutral'
  return props.device.running ? 'info' : 'warning'
})

const runningBadgeLabel = computed(() => {
  if (props.device.running === null) return 'Unknown'
  return props.device.running ? 'Active' : 'Idle'
})

const chipColor = computed(() => {
  if (props.device.online === null) return 'neutral'
  return props.device.online ? 'success' : 'error'
})

// Video preview: show only if device is known to be online
const showVideo = computed(() => props.device.online === true)
const isLoading = computed(() => props.device.online === null)

// Append cache-buster so the <img> re-fetches after a hard refresh
const videoSrc = computed(() => `${props.videoUrl}/video_feed`)

const isExpanded = ref(false)
const expandedVideoContainer = ref(null)

function openExpanded() {
  if (!showVideo.value) return
  isExpanded.value = true
}

async function closeExpanded() {
  isExpanded.value = false

  if (!import.meta.client) return
  if (document.fullscreenElement && document.exitFullscreen) {
    try {
      await document.exitFullscreen()
    } catch {
      // Ignore browser-specific fullscreen exit issues.
    }
  }
}

async function toggleExpandedFullscreen() {
  if (!import.meta.client) return
  const container = expandedVideoContainer.value
  if (!container) return

  try {
    if (document.fullscreenElement && document.exitFullscreen) {
      await document.exitFullscreen()
      return
    }

    if (container.requestFullscreen) {
      await container.requestFullscreen()
      return
    }

    if (container.webkitRequestFullscreen) {
      container.webkitRequestFullscreen()
    }
  } catch {
    // Fallback is the expanded overlay itself.
  }
}

function onGlobalKeydown(event) {
  if (event.key === 'Escape' && isExpanded.value) {
    closeExpanded()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
})
</script>

<template>
  <UCard class="h-full flex flex-col quantum-card">
    <!-- ── Header ─────────────────────────────────────────────────────────── -->
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-3 min-w-0">
          <UChip :color="chipColor" inset size="sm">
            <UIcon :name="device.icon" class="text-2xl text-[#f4b88a]" />
          </UChip>
          <span class="font-semibold text-lg truncate">{{ device.label }}</span>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <UBadge :color="onlineBadgeColor" variant="subtle" size="sm">
            {{ onlineBadgeLabel }}
          </UBadge>
          <UBadge :color="runningBadgeColor" variant="subtle" size="sm">
            {{ runningBadgeLabel }}
          </UBadge>
        </div>
      </div>
    </template>

    <!-- ── Body ──────────────────────────────────────────────────────────── -->
    <div class="flex flex-col gap-4 flex-1">

      <!-- Video Preview -->
      <div class="rounded-lg overflow-hidden bg-stone-950 border quantum-video aspect-video flex items-center justify-center relative">

        <!-- Skeleton while status is unknown -->
        <template v-if="isLoading">
          <USkeleton class="absolute inset-0 w-full h-full rounded-lg" />
          <div class="relative z-10 flex flex-col items-center gap-2 text-[#b4694f]/60">
            <UIcon name="heroicons:cpu-chip" class="text-3xl animate-pulse" />
            <span class="text-xs tracking-widest uppercase">Initializing quantum state…</span>
          </div>
        </template>

        <!-- Live feed -->
        <template v-else-if="showVideo">
          <img
            :key="`feed-${device.running}`"
            :src="videoSrc"
            alt="Video feed"
            class="w-full h-full object-cover"
          />
          <span class="absolute top-2 left-2 text-xs font-bold px-2 py-0.5 rounded uppercase flex items-center gap-1 quantum-live-badge">
            <span class="w-1.5 h-1.5 bg-black/40 rounded-full animate-pulse inline-block"></span>
            Live
          </span>
          <UTooltip text="Open fullscreen preview" :delay-duration="400">
            <UButton
              size="xs"
              color="primary"
              variant="solid"
              icon="heroicons:arrows-pointing-out"
              class="absolute top-2 right-2"
              @click.stop="openExpanded"
            >
              Expand
            </UButton>
          </UTooltip>
        </template>

        <!-- Offline placeholder -->
        <template v-else>
          <div class="flex flex-col items-center gap-2 text-[#7a2d16]/80">
            <UIcon name="heroicons:signal-slash" class="text-4xl" />
            <span class="text-sm tracking-wide">No quantum channel</span>
          </div>
        </template>

      </div>

      <!-- QFlow runtime config panel -->
      <template v-if="isQFlow">
        <div class="rounded-lg border border-stone-800 bg-stone-950/60 p-3 space-y-3">
          <p class="text-xs font-semibold uppercase tracking-wider quantum-section-label">QFlow Config</p>

          <!-- Video source -->
          <div class="space-y-1">
            <label class="text-xs text-stone-400">Video Source</label>
            <div class="flex gap-2">
              <UButton
                v-for="opt in VIDEO_OPTIONS"
                :key="opt.value"
                size="xs"
                :variant="qflowConfig.videoSource === opt.value ? 'solid' : 'outline'"
                color="primary"
                class="flex-1 justify-center"
                @click="qflowConfig.videoSource = opt.value"
              >
                {{ opt.label }}
              </UButton>
            </div>
          </div>

          <!-- Grid dimensions -->
          <div class="space-y-1">
            <label class="text-xs text-stone-400">Grid (rows × cols)</label>
            <div class="flex items-center gap-2">
              <UInput
                v-model.number="qflowConfig.rows"
                type="number"
                min="1"
                max="16"
                size="sm"
                class="w-20"
                :ui="{ base: 'text-center' }"
              />
              <span class="text-stone-500 text-sm">×</span>
              <UInput
                v-model.number="qflowConfig.cols"
                type="number"
                min="1"
                max="16"
                size="sm"
                class="w-20"
                :ui="{ base: 'text-center' }"
              />
              <span class="text-xs text-stone-500 ml-1">= {{ qflowConfig.rows * qflowConfig.cols }}</span>
            </div>
            <!-- Preset quick-select -->
            <div class="flex flex-wrap gap-1 mt-1">
              <UButton
                v-for="p in VALID_GRID_PRESETS"
                :key="p.label"
                size="xs"
                variant="ghost"
                color="neutral"
                class="px-2 py-0.5 text-[10px]"
                @click="applyGridPreset(p)"
              >
                {{ p.rows }}×{{ p.cols }}
              </UButton>
            </div>
            <p v-if="gridWarning" class="text-xs text-amber-400 mt-1">
              {{ gridWarning }}
            </p>
          </div>
        </div>
      </template>

      <!-- Action buttons -->
      <div class="flex items-center gap-2 flex-wrap">
        <UTooltip
          :text="device.running === true ? 'Node already active' : 'Initialize quantum node'"
          :delay-duration="400"
        >
          <UButton
            color="primary"
            variant="solid"
            icon="heroicons:play"
            :loading="device.loading"
            :disabled="device.loading || device.running === true || (isQFlow && !gridValid)"
            class="flex-1"
            @click="handleActivate"
          >
            Activate
          </UButton>
        </UTooltip>

        <UTooltip
          :text="device.running === false ? 'Node already idle' : 'Halt quantum node'"
          :delay-duration="400"
        >
          <UButton
            color="primary"
            variant="outline"
            icon="heroicons:stop"
            :loading="device.loading"
            :disabled="device.loading || device.running === false"
            class="flex-1"
            @click="emit('stop')"
          >
            Halt
          </UButton>
        </UTooltip>

        <UTooltip text="Re-measure quantum state" :delay-duration="400">
          <UButton
            color="primary"
            variant="soft"
            icon="heroicons:arrow-path"
            :loading="device.loading"
            :disabled="device.loading"
            @click="emit('refresh')"
          />
        </UTooltip>
      </div>
        <UAlert
          v-if="device.error"
          color="error"
          variant="subtle"
          :description="device.error"
          icon="heroicons:exclamation-triangle"
        />
      </div>
  </UCard>

  <Teleport to="body">
    <div
      v-if="isExpanded"
      class="fixed inset-0 z-100 bg-black/95 p-4 sm:p-6 flex flex-col"
      style="background-image: radial-gradient(ellipse at 50% 50%, rgba(180, 105, 79, 0.04) 0%, transparent 70%);"
      @click.self="closeExpanded"
    >
      <div class="mx-auto w-full max-w-6xl flex items-center justify-between gap-3 text-gray-100">
        <div class="flex items-center gap-2 min-w-0">
          <UChip :color="chipColor" inset size="sm">
            <UIcon :name="device.icon" class="text-xl text-[#f4b88a]" />
          </UChip>
          <span class="font-semibold truncate">{{ device.label }} · Live Feed</span>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <UButton
            color="primary"
            variant="soft"
            size="sm"
            icon="heroicons:arrows-pointing-out"
            @click="toggleExpandedFullscreen"
          >
            Fullscreen
          </UButton>
          <UButton
            color="primary"
            variant="ghost"
            size="sm"
            icon="heroicons:x-mark"
            @click="closeExpanded"
          >
            Close
          </UButton>
        </div>
      </div>

      <div class="mx-auto mt-4 w-full max-w-6xl flex-1 min-h-0">
        <div
          ref="expandedVideoContainer"
          class="h-full w-full rounded-lg overflow-hidden bg-black border quantum-video flex items-center justify-center"
        >
          <img
            :key="`feed-expanded-${device.running}`"
            :src="videoSrc"
            :alt="`${device.label} video feed`"
            class="w-full h-full object-contain"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

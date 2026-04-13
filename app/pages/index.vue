<script setup>
// pages/index.vue
// Main control dashboard

const {
  pc,
  pi,
  fetchStatus,
  startDevice,
  stopDevice,
  refreshAll,
  startBoth,
  stopBoth,
  startPolling,
  logs,
} = useDevices()

const deviceRefs = {
  pc,
  pi,
}

function handleStart(deviceId, params = {}) {
  return startDevice(deviceRefs[deviceId], params)
}

function handleStop(deviceId) {
  return stopDevice(deviceRefs[deviceId])
}

function handleRefresh(deviceId) {
  return fetchStatus(deviceRefs[deviceId])
}

const config = useRuntimeConfig()
const pcVideoUrl  = config.public.pcAgentUrl
const piVideoUrl  = config.public.piAgentUrl

const globalLoading = computed(() => pc.value.loading && pi.value.loading)

onMounted(async () => {
  await refreshAll()
  startPolling(8000)
})

function clearLogs() {
  logs.value = []
}

const pcOnlineColor = computed(() => {
  if (pc.value.online === null) return 'neutral'
  return pc.value.online ? 'success' : 'error'
})

const piOnlineColor = computed(() => {
  if (pi.value.online === null) return 'neutral'
  return pi.value.online ? 'success' : 'error'
})
</script>

<template>
  <UApp>
    <UDashboardGroup>

      <!-- ── Sidebar ────────────────────────────────────────────────────────── -->
      <UDashboardSidebar>
        <template #header>
          <div class="px-2 py-3">
            <img src="/logo.png" alt="QuantumDrive" class="w-full object-contain" />
          </div>
        </template>

        <div class="flex flex-col h-full">
        <div class="px-2 space-y-5 py-2">

          <!-- Quantum Nodes section -->
          <div class="space-y-1">
            <p class="text-xs font-semibold uppercase px-2 mb-2 quantum-section-label">Quantum Nodes</p>

            <!-- PC row -->
            <div class="flex items-center gap-2.5 rounded-lg px-2 py-2 transition-colors quantum-device-row">
              <UChip :color="pcOnlineColor" inset size="sm" class="shrink-0">
                <UIcon name="heroicons:computer-desktop" class="text-xl text-(--steel-200)" />
              </UChip>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium">QFlow</p>
                <div class="flex items-center gap-1 mt-0.5">
                  <UBadge
                    :color="pc.online ? 'success' : pc.online === false ? 'error' : 'neutral'"
                    variant="subtle"
                    size="xs"
                  >
                    {{ pc.online === null ? '—' : pc.online ? 'Entangled' : 'Decoherent' }}
                  </UBadge>
                  <UBadge
                    :color="pc.running ? 'info' : 'warning'"
                    variant="subtle"
                    size="xs"
                  >
                    {{ pc.running === null ? '—' : pc.running ? 'Active' : 'Idle' }}
                  </UBadge>
                </div>
              </div>
            </div>

            <!-- Pi row -->
            <div class="flex items-center gap-2.5 rounded-lg px-2 py-2 transition-colors quantum-device-row">
              <UChip :color="piOnlineColor" inset size="sm" class="shrink-0">
                <UIcon name="heroicons:cpu-chip" class="text-xl text-(--steel-200)" />
              </UChip>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium">QFocus</p>
                <div class="flex items-center gap-1 mt-0.5">
                  <UBadge
                    :color="pi.online ? 'success' : pi.online === false ? 'error' : 'neutral'"
                    variant="subtle"
                    size="xs"
                  >
                    {{ pi.online === null ? '—' : pi.online ? 'Entangled' : 'Decoherent' }}
                  </UBadge>
                  <UBadge
                    :color="pi.running ? 'info' : 'warning'"
                    variant="subtle"
                    size="xs"
                  >
                    {{ pi.running === null ? '—' : pi.running ? 'Active' : 'Idle' }}
                  </UBadge>
                </div>
              </div>
            </div>
          </div>

          <USeparator />

          <!-- Network Control section -->
          <div class="space-y-2">
            <p class="text-xs font-semibold uppercase px-2 mb-2 quantum-section-label">Network Control</p>
            <UButton
              block
              color="primary"
              variant="solid"
              icon="heroicons:play-circle"
              :loading="globalLoading"
              size="sm"
              @click="startBoth"
            >
              Entangle All
            </UButton>
            <UButton
              block
              color="primary"
              variant="outline"
              icon="heroicons:stop-circle"
              :loading="globalLoading"
              size="sm"
              @click="stopBoth"
            >
              Decohere All
            </UButton>
            <UButton
              block
              color="primary"
              variant="soft"
              icon="heroicons:arrow-path"
              :loading="globalLoading"
              size="sm"
              @click="refreshAll"
            >
              Sync States
            </UButton>
          </div>

          <USeparator />

          <!-- Observability section -->
          <div class="space-y-2">
            <p class="text-xs font-semibold uppercase px-2 mb-2 quantum-section-label">Observability</p>
            <UButton
              block
              color="neutral"
              variant="outline"
              icon="heroicons:chart-bar"
              size="sm"
              trailing-icon="heroicons:arrow-top-right-on-square"
              as="a"
              href="https://email4burnerapps21.grafana.net/public-dashboards/1f09e0f8321046a5b58118d3d4959150"
              target="_blank"
              rel="noopener noreferrer"
            >
              Grafana Dashboard
            </UButton>
          </div>

        </div>

        <!-- Quantum Orb fills remaining sidebar space -->
        <div class="flex-1 flex items-center justify-center min-h-0 overflow-hidden">
          <QuantumOrb />
        </div>
        </div>

        <template #footer>
          <div class="flex items-center gap-2 px-3 py-2 text-xs text-(--steel-500) quantum-footer">
            <UIcon name="heroicons:signal" class="text-sm shrink-0" />
            <span>Quantum state sync every 8s · QKD secured</span>
          </div>
        </template>
      </UDashboardSidebar>

      <!-- ── Main panel ─────────────────────────────────────────────────────── -->
      <UDashboardPanel>
        <template #header>
          <UDashboardNavbar title="Quantum Node Monitor" icon="heroicons:cpu-chip">
            <template #right>
              <span class="text-xs text-(--steel-400) hidden sm:block tracking-wide">Q-IoT · March 2026</span>
            </template>
          </UDashboardNavbar>
        </template>

        <div class="p-4 sm:p-6 space-y-6 overflow-y-auto quantum-bg min-h-full">

          <!-- Device cards -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <DeviceCard
              :device="pc"
              :video-url="pcVideoUrl"
              @start="(params) => handleStart('pc', params)"
              @stop="handleStop('pc')"
              @refresh="handleRefresh('pc')"
            />
            <DeviceCard
              :device="pi"
              :video-url="piVideoUrl"
              @start="handleStart('pi')"
              @stop="handleStop('pi')"
              @refresh="handleRefresh('pi')"
            />
          </div>

          <!-- Logs panel -->
          <LogsPanel :logs="logs" @clear="clearLogs" />

        </div>
      </UDashboardPanel>

    </UDashboardGroup>

    <UToaster />
  </UApp>
</template>

<script setup>
// components/LogsPanel.vue
// Scrollable timestamped quantum event log

const props = defineProps({
  logs: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['clear'])

const scrollArea = ref(null)

// Auto-scroll to top (newest entry is at top via unshift)
watch(
  () => props.logs.length,
  () => {
    nextTick(() => {
      if (scrollArea.value?.$el) {
        const viewport = scrollArea.value.$el.querySelector('[data-radix-scroll-area-viewport]')
        if (viewport) viewport.scrollTop = 0
      }
    })
  }
)

const iconMap = {
  info:    'heroicons:information-circle',
  success: 'heroicons:check-circle',
  error:   'heroicons:x-circle',
  warning: 'heroicons:exclamation-triangle',
}

const colorMap = {
  info:    'text-[#b4694f]',
  success: 'text-green-400',
  error:   'text-red-400',
  warning: 'text-yellow-400',
}

function formatTime(date) {
  return new Date(date).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

</script>

<template>
  <UCard class="quantum-card">
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <UIcon name="heroicons:beaker" class="text-xl text-[#b4694f]" />
          <span class="font-semibold text-base">Quantum Event Log</span>
          <UBadge color="neutral" variant="subtle" size="xs">
            {{ logs.length }}
          </UBadge>
        </div>
        <UTooltip text="Clear all log entries" :delay-duration="400">
          <UButton
            color="primary"
            variant="ghost"
            size="xs"
            icon="heroicons:trash"
            :class="logs.length === 0 ? 'invisible pointer-events-none' : ''"
            @click="emit('clear')"
          >
            Clear
          </UButton>
        </UTooltip>
      </div>
    </template>

    <UScrollArea ref="scrollArea" class="h-72">
      <div
        v-if="logs.length === 0"
        class="flex flex-col items-center justify-center h-72 gap-2 text-(--steel-500) text-sm"
      >
        <UIcon name="heroicons:beaker" class="text-2xl" />
        <span>No quantum events — transmissions will appear here.</span>
      </div>

      <div
        v-for="entry in logs"
        :key="entry.id"
        class="flex items-start gap-2 py-1.5 px-1 border-b border-(--steel-600)/30 last:border-0 font-mono text-xs transition-colors quantum-log-entry"
      >
        <UIcon
          :name="iconMap[entry.type] || iconMap.info"
          :class="['text-base shrink-0 mt-0.5', colorMap[entry.type] || colorMap.info]"
        />
        <span class="text-(--steel-400) shrink-0 tabular-nums">{{ formatTime(entry.timestamp) }}</span>
        <span class="text-(--steel-100) break-all">{{ entry.message }}</span>
      </div>
    </UScrollArea>
  </UCard>
</template>

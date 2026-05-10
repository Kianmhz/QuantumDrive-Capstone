// server/api/devices/pc/status.get.js
// Proxies GET /status to the PC agent

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const baseUrl = config.pcAgentUrl

  try {
    const data = await $fetch(`${baseUrl}/status`, {
      method: 'GET',
      timeout: 5000,
    })
    return data
  } catch (err) {
    // Return a structured offline response rather than crashing
    return {
      online: false,
      running: false,
      name: 'Home PC',
      _error: err?.message || 'Unreachable',
    }
  }
})

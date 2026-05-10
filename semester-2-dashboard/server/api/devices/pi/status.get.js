// server/api/devices/pi/status.get.js
// Proxies GET /status to the Raspberry Pi agent

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const baseUrl = config.piAgentUrl

  try {
    const data = await $fetch(`${baseUrl}/status`, {
      method: 'GET',
      timeout: 5000,
    })
    return data
  } catch (err) {
    return {
      online: false,
      running: false,
      name: 'Raspberry Pi',
      _error: err?.message || 'Unreachable',
    }
  }
})

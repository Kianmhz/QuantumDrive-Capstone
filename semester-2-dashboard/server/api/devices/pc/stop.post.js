// server/api/devices/pc/stop.post.js
// Proxies POST /stop to the PC agent

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const baseUrl = config.pcAgentUrl

  try {
    const data = await $fetch(`${baseUrl}/stop`, {
      method: 'POST',
      timeout: 8000,
    })
    return { success: true, data }
  } catch (err) {
    return { success: false, error: err?.message || 'Unreachable' }
  }
})

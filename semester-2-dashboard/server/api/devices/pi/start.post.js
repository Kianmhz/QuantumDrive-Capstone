// server/api/devices/pi/start.post.js
// Proxies POST /start to the Raspberry Pi agent

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const baseUrl = config.piAgentUrl

  try {
    const data = await $fetch(`${baseUrl}/start`, {
      method: 'POST',
      timeout: 8000,
    })
    return { success: true, data }
  } catch (err) {
    return { success: false, error: err?.message || 'Unreachable' }
  }
})

// server/api/devices/pc/start.post.js
// Proxies POST /start to the PC agent

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const baseUrl = config.pcAgentUrl
  const body = await readBody(event).catch(() => ({}))

  try {
    const data = await $fetch(`${baseUrl}/start`, {
      method: 'POST',
      body: body || {},
      timeout: 8000,
    })
    return { success: true, data }
  } catch (err) {
    return { success: false, error: err?.message || 'Unreachable' }
  }
})

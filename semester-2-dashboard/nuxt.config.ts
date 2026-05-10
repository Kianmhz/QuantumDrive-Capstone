// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    // Private — server-side only (used by API proxy routes)
    pcAgentUrl: process.env.PC_AGENT_URL || 'http://localhost:8001',
    piAgentUrl: process.env.PI_AGENT_URL || 'http://localhost:8002',
    public: {
      // Public — exposed to the client (used for direct video feed URLs)
      pcAgentUrl: process.env.PC_AGENT_URL || 'http://localhost:8001',
      piAgentUrl: process.env.PI_AGENT_URL || 'http://localhost:8002',
    },
  },
})

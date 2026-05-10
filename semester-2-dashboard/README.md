# Capstone Control Dashboard

A web-based control panel for managing two remote device agents — a **Home PC** and a **Raspberry Pi** — built for a distributed systems university capstone demo.

## Overview

This dashboard is the **frontend/server layer only**. The actual program launch and stop logic runs on each device via lightweight local agents. The dashboard communicates with those agents through HTTP APIs, proxied through Nuxt server routes to avoid CORS issues.

```
Browser → Nuxt Dashboard (this app) → Device Agent (PC or Pi)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | [Nuxt 4](https://nuxt.com) |
| UI Components | [Nuxt UI v4](https://ui.nuxt.com) |
| Styling | Tailwind CSS (via Nuxt UI) |
| Language | JavaScript (Composition API + `<script setup>`) |
| Server routes | Nitro (built into Nuxt) |

## Project Structure

```
Capstone-Dashboard/
├── .env.example                      ← Template for local agent base URLs
├── .env                              ← Local env overrides (ignored by git)
├── nuxt.config.ts                    ← Nuxt UI module + runtimeConfig
├── app/
│   ├── app.vue                       ← Root shell
│   ├── assets/css/main.css           ← Tailwind + Nuxt UI base styles
│   ├── composables/
│   │   └── useDevices.js             ← Device state, actions, polling, logs
│   ├── components/
│   │   ├── DeviceCard.vue            ← Per-device control card
│   │   └── LogsPanel.vue             ← Timestamped event log panel
│   ├── pages/
│   │   └── index.vue                 ← Main dashboard page
│   └── types/
│       └── index.js                  ← JSDoc type definitions
└── server/api/devices/
    ├── pc/status.get.js              ← GET  /api/devices/pc/status
    ├── pc/start.post.js              ← POST /api/devices/pc/start
    ├── pc/stop.post.js               ← POST /api/devices/pc/stop
    ├── pi/status.get.js              ← GET  /api/devices/pi/status
    ├── pi/start.post.js              ← POST /api/devices/pi/start
    └── pi/stop.post.js               ← POST /api/devices/pi/stop
```

## Device Agent API Contract

Each device agent must expose these endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/status` | Returns `{ online, running, name }` |
| `POST` | `/start` | Starts the local program |
| `POST` | `/stop` | Stops the local program |
| `GET` | `/video_feed` | MJPEG stream (displayed in `<img>` tag) |

Example `/status` response:

```json
{
  "online": true,
  "running": true,
  "name": "Home PC"
}
```

## Environment Variables

Copy `.env.example` to `.env`, then set the real IP addresses of your devices:

```bash
PC_AGENT_URL=http://<pc-ip>:<port>
PI_AGENT_URL=http://<pi-ip>:<port>
```

Defaults (used when `.env` is absent):

```
PC_AGENT_URL=http://localhost:8001
PI_AGENT_URL=http://localhost:8002
```

> **Note:** `PC_AGENT_URL` and `PI_AGENT_URL` are used both server-side (for API proxying) and client-side (for the video feed `<img>` src). They must be reachable from both the Nuxt server and the user's browser.

## Setup & Running

Install dependencies:

```bash
npm install
```

Start the development server on `http://localhost:3000`:

```bash
npm run dev
```

Build for production:

```bash
npm run build
npm run preview
```

## Features

- **Two device cards** (Home PC + Raspberry Pi) side by side, stacked on mobile
- **Online / Offline** and **Running / Stopped** status badges per device
- **Start**, **Stop**, and **Refresh** buttons per device
- **Global controls** — Start Both, Stop Both, Refresh All
- **Live video preview** via MJPEG stream (`/video_feed`), with offline placeholder
- **Event log panel** — timestamped messages for every action and status change
- **Toast notifications** on success and error
- **Graceful offline handling** — no page crash if a device is unreachable
- **Auto-refresh** — polls both device statuses every 8 seconds
- **CORS-safe** — all agent requests are proxied through Nuxt server routes

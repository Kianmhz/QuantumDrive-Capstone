# Device Agent (Capstone)

This local agent exposes your existing traffic pipeline to the Nuxt dashboard.

API contract (matches dashboard):
- GET /status
- POST /start
- POST /stop
- GET /video_feed

## 1) Install dependencies

From the Capstone root:

```bash
pip install -r requirements.txt
```

## 2) Configure runtime (optional)

You can copy `.env.example` from the project root to `.env` and edit values there. The agent now loads the root `.env` automatically.

Default source is `traffic_bi.mp4` if it exists, otherwise `traffic.mp4`.

Common environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_NAME` | `Home PC` | Device label returned by `/status` |
| `PORT` | `8001` | Flask server port |
| `VIDEO_SOURCE` | auto (`traffic_bi.mp4` then `traffic.mp4`) | Input video |
| `LOOP_VIDEO` | `true` | Loop video when it ends |
| `TARGET_FPS` | `20` | Processing target FPS |
| `JPEG_QUALITY` | `80` | MJPEG quality for `/video_feed` |
| `MODEL_PATH` | `yolov8m.pt` | YOLO model path (auto-downloaded if missing) |
| `ROWS` / `COLS` | `4` / `8` | Grid dimensions (rows x cols must be power of 2) |
| `CONFIDENCE_THRESHOLD` | `0.5` | YOLO detection threshold |
| `YOLO_DEVICE` | `cuda` | `cpu`, `cuda`, or `mps` |
| `USE_QUANTUM` | `true` | Enable quantum counting in stream mode |
| `PRECISION_QUBITS` | `6` | QPE precision qubits |
| `SHOTS` | `512` | Quantum measurement shots |
| `QUANTUM_EVERY_N` | `5` | Run quantum every N frames |
| `GRAFANA_PUSH` | `true` | Push metrics when Grafana credentials are configured |
| `GRAFANA_PUSH_EVERY_N` | `5` | Push every N frames |
| `GRAFANA_URL` | - | Influx-compatible Grafana write endpoint |
| `GRAFANA_USER` | - | Grafana numeric user ID |
| `GRAFANA_TOKEN` | - | Grafana API token (MetricsPublisher) |
| `DIRECTION_SPLIT` | `vertical` | `vertical`, `horizontal`, or `none` |
| `SHOW_INFO` | `true` | Overlay panel visibility default |
| `START_ON_BOOT` | `false` | Auto-start stream when agent process starts |

PowerShell example:

```powershell
$env:DEVICE_NAME = "Home PC"
$env:PORT = "8001"
$env:VIDEO_SOURCE = "traffic_bi.mp4"
$env:USE_QUANTUM = "true"
$env:YOLO_DEVICE = "cuda"
```

To switch to the second demo clip:

```powershell
$env:VIDEO_SOURCE = "traffic.mp4"
$env:LOOP_VIDEO = "true"
```

`POST /start` can override a subset at runtime with JSON payload:

```json
{
	"video_source": "traffic.mp4",
	"rows": 8,
	"cols": 8,
	"direction_split": "horizontal"
}
```

## 3) Run the agent

```bash
python device-agent/agent.py
```

The server starts on `0.0.0.0:$PORT`.

Then set your Nuxt dashboard env:

```bash
PC_AGENT_URL=http://<your-pc-ip>:8001
```

If presenting from another machine, ensure both machines are on the same network and allow inbound firewall access for port 8001.

Grafana push notes:
- API mode (this agent): controlled by `GRAFANA_PUSH` and `GRAFANA_PUSH_EVERY_N`.
- CLI mode (`python -m src.pipeline`): controlled by `--grafana`.
- Both modes use the same credentials: `GRAFANA_URL`, `GRAFANA_USER`, `GRAFANA_TOKEN`.

## 4) Quick API checks

```bash
curl http://localhost:8001/status
curl -X POST http://localhost:8001/start -H "Content-Type: application/json" -d '{}'
curl -X POST http://localhost:8001/stop
```

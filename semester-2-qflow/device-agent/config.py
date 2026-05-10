"""
Configuration for the local PC device agent used by the Nuxt dashboard.

All values can be overridden with environment variables for presentation-day
setup without code edits.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _default_video_source() -> str:
    env_value = os.getenv("VIDEO_SOURCE")
    if env_value:
        return env_value

    for candidate in ("traffic_bi.mp4", "traffic.mp4"):
        if (ROOT_DIR / candidate).exists():
            return candidate

    return "traffic.mp4"


def _env_path(name: str, default: str) -> str:
    raw = os.getenv(name, default)
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str((ROOT_DIR / candidate).resolve(strict=False).relative_to(ROOT_DIR))


# Identity and network
DEVICE_NAME = os.getenv("DEVICE_NAME", "Home PC")
PORT = int(os.getenv("PORT", "8001"))

# Video source and stream output
# VIDEO_SOURCE should point to a local video file.
# Examples:
#   "traffic.mp4"
#   "traffic_bi.mp4"
#   "videos/demo.mp4"
VIDEO_SOURCE = _default_video_source()
LOOP_VIDEO = _env_bool("LOOP_VIDEO", True)
TARGET_FPS = int(os.getenv("TARGET_FPS", "20"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))

# Vision + occupancy settings
MODEL_PATH = _env_path("MODEL_PATH", "yolov8m.pt")
ROWS = int(os.getenv("ROWS", "4"))
COLS = int(os.getenv("COLS", "8"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
YOLO_DEVICE = os.getenv("YOLO_DEVICE", "cuda")

# Quantum settings (enabled by default)
USE_QUANTUM = _env_bool("USE_QUANTUM", True)
PRECISION_QUBITS = int(os.getenv("PRECISION_QUBITS", "6"))
SHOTS = int(os.getenv("SHOTS", "512"))
QUANTUM_EVERY_N = int(os.getenv("QUANTUM_EVERY_N", "5"))

# Metrics export settings
GRAFANA_PUSH = _env_bool("GRAFANA_PUSH", True)
GRAFANA_PUSH_EVERY_N = int(os.getenv("GRAFANA_PUSH_EVERY_N", "5"))

# Direction panel settings: vertical, horizontal, or none
_direction_raw = os.getenv("DIRECTION_SPLIT", "vertical").strip().lower()
if _direction_raw in {"none", "off", "false", "0"}:
    DIRECTION_SPLIT = None
elif _direction_raw in {"vertical", "horizontal"}:
    DIRECTION_SPLIT = _direction_raw
else:
    DIRECTION_SPLIT = "vertical"

SHOW_INFO = _env_bool("SHOW_INFO", True)
START_ON_BOOT = _env_bool("START_ON_BOOT", False)


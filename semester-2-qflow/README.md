# Quantum Traffic Density Estimation

A quantum computing approach to estimating traffic density using Grover's algorithm and Quantum Phase Estimation (QPE). This project demonstrates how quantum counting can achieve a theoretical quadratic speedup over classical counting methods.

## Overview

This system divides a video frame into a grid of regions, identifies which regions contain vehicles (using YOLO object detection), and uses **Quantum Counting** to estimate the traffic density — the fraction of regions occupied by cars.

### Key Innovation

Instead of classically counting all N regions (O(N) operations), quantum counting estimates the count M in **O(√N) oracle queries** — a quadratic speedup.

For a city-scale grid with 1,000,000 cells:
- **Classical**: 1,000,000 checks
- **Quantum**: ~1,000 oracle queries

## Architecture

```
+---------------------+     +--------------------+     +------------------------+
|    Video Frame      | --> |   YOLO Detection   | --> |    Bounding Boxes      |
|    (1920x1080)      |     |   (YOLOv8 + GPU)   |     | [(x1,y1,x2,y2), ...]  |
+---------------------+     +--------------------+     +------------------------+
                                                                    |
                                                                    v
+---------------------+     +--------------------+     +------------------------+
|  Traffic Density    | <-- |  Quantum Counting  | <-- |    Occupancy Grid      |
|    37.5%            |     |   (QPE + Grover)   |     |  [1, 0, 1, 1, 0, 0, ...]|
+---------------------+     +--------------------+     +------------------------+
```

## Project Structure

```
Capstone/
├── src/
│   ├── vision/
│   │   ├── grid.py               # Grid division utilities
│   │   ├── boxes_to_occupancy.py # Convert bounding boxes to binary grid
│   │   ├── video_processor.py    # YOLO video processing
│   │   └── visualization.py      # Overlay drawing utilities
│   ├── quantum/
│   │   ├── quantum_counting.py   # Core quantum counting algorithm (QPE + Grover)
│   │   └── demo.py               # Standalone CLI for benchmarking/testing
│   ├── utils/
│   │   ├── logging.py            # CSV logging and session summaries
│   │   └── grafana.py            # Optional Grafana/Influx metrics push
│   └── pipeline.py               # Main video pipeline CLI
├── device-agent/
│   ├── agent.py                  # Flask device API (/status, /start, /stop, /video_feed)
│   ├── config.py                 # .env + environment-based runtime config
│   └── stream_runner.py          # Background runner + MJPEG stream generator
├── logs/                          # Output logs (gitignored)
├── .env.example
├── requirements.txt
└── README.md
```

## Installation

### 1. Create Virtual Environment
```bash
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

On first run, Ultralytics downloads the YOLO model (for example, `yolov8m.pt`) if it is not already present.

### 3. (Optional) GPU Acceleration
For NVIDIA GPU support (recommended for video processing):
```bash
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## Usage

### Quantum Demo (No Video Required)
```bash
python -m src.quantum.demo
```

Runs three test scenarios comparing quantum vs classical counting. Useful for verifying the quantum circuit without needing a video file.

### Video Processing Pipeline
```bash
# Basic usage (quantum enabled by default)
python -m src.pipeline --video traffic.mp4

# Classical only (fast, no quantum)
python -m src.pipeline --video traffic.mp4 --no-quantum
```

### Device Agent (for dashboard streaming)
```bash
python device-agent/agent.py
```

Available endpoints:
- `GET /status`
- `POST /start`
- `POST /stop`
- `GET /video_feed`

The agent loads configuration from `.env` in the project root (see `.env.example`).

## CLI Reference

### Demo CLI

```
python -m src.quantum.demo [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--rows N` | 4 | Grid rows |
| `--cols N` | 4 | Grid columns |
| `--precision N`, `-p` | 4 | QPE precision qubits (try 6 for accuracy) |
| `--shots N`, `-s` | 2048 | Measurement shots |
| `--test-m M` | - | Test specific occupancy value M |
| `--random` | - | Run with random occupancy |
| `--benchmark` | - | Test all M values from 0 to N |

**Examples:**
```bash
# Default demo (3 test scenarios)
python -m src.quantum.demo

# Benchmark with high precision (shows accuracy for all M)
python -m src.quantum.demo --benchmark --precision 6

# Test specific M=5 occupancy
python -m src.quantum.demo --test-m 5 -p 6

# Larger grid (8x4 = 32 regions, needs more precision)
python -m src.quantum.demo --rows 8 --cols 4 --precision 7 --test-m 10

# Random occupancy test
python -m src.quantum.demo --random
```

### Video Pipeline CLI

```
python -m src.pipeline --video PATH [OPTIONS]
```

#### Input (required)
| Flag | Description |
|------|-------------|
| `--video PATH` | Path to input video file |

#### Grid Options
| Flag | Default | Description |
|------|---------|-------------|
| `--rows N` | 8 | Grid rows |
| `--cols N` | 8 | Grid columns |

Grid size (rows x cols) must be a power of 2 (e.g., 16, 32, 64). Search qubits are calculated as log2(N).

#### Quantum Options
| Flag | Default | Description |
|------|---------|-------------|
| `--no-quantum` | false | Disable quantum counting (classical only, faster) |
| `--precision N` | 6 | QPE precision qubits (more = accurate but slower) |
| `--shots N` | 1024 | Quantum measurement shots |
| `--quantum-every N` | 5 | Run quantum every N frames (synced with classical) |

#### Direction Options
| Flag | Default | Description |
|------|---------|-------------|
| `--split TYPE` | vertical | Direction boundary split: `vertical` or `horizontal` |
| `--no-direction` | false | Disable directional A/B density breakdown |

#### Processing Options
| Flag | Default | Description |
|------|---------|-------------|
| `--device DEV` | cuda | Device for YOLO: `cpu`, `cuda`, or `mps` |

#### Logging Options
| Flag | Default | Description |
|------|---------|-------------|
| `--no-log` | false | Disable CSV logging |
| `--log-dir PATH` | logs | Directory for log files |

#### Examples

```bash
# Fast mode (no quantum, classical only)
python -m src.pipeline --video traffic.mp4 --no-quantum

# High accuracy quantum (slower)
python -m src.pipeline --video traffic.mp4 --precision 7 --shots 2048 --quantum-every 1

# Balanced for real-time
python -m src.pipeline --video traffic.mp4 --precision 6 --quantum-every 10

# CPU-only processing
python -m src.pipeline --video traffic.mp4 --device cpu

# Custom grid (8x8 = 64 regions)
python -m src.pipeline --video traffic.mp4 --rows 8 --cols 8

# Horizontal direction split
python -m src.pipeline --video traffic.mp4 --split horizontal

# Disable directional breakdown
python -m src.pipeline --video traffic.mp4 --no-direction

# Push per-frame metrics to Grafana Cloud
python -m src.pipeline --video traffic.mp4 --grafana
```

### Device Agent Runtime Configuration

`device-agent/config.py` reads root `.env` values (or system environment variables), then the API can override a subset at start-time via `POST /start` payload (`video_source`, `rows`, `cols`, `direction_split`).

Common environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_NAME` | Home PC | Device identifier returned by `/status` |
| `PORT` | 8001 | Flask server port |
| `VIDEO_SOURCE` | auto (`traffic_bi.mp4` then `traffic.mp4`) | Input video source |
| `ROWS` / `COLS` | 4 / 8 | Grid dimensions (rows x cols must be power of 2) |
| `YOLO_DEVICE` | cuda | Inference device (`cpu`, `cuda`, `mps`) |
| `USE_QUANTUM` | true | Enable quantum counting in stream mode |
| `PRECISION_QUBITS` | 6 | QPE precision |
| `SHOTS` | 512 | Quantum shots |
| `QUANTUM_EVERY_N` | 5 | Run quantum every N frames |
| `GRAFANA_PUSH` | true | Enable Grafana push in device-agent (API mode) |
| `GRAFANA_PUSH_EVERY_N` | 5 | Push every N frames in API mode |
| `DIRECTION_SPLIT` | vertical | `vertical`, `horizontal`, or `none` |
| `START_ON_BOOT` | false | Auto-start stream on agent startup |

Grafana push is available in both modes:
- CLI pipeline mode: run with `--grafana`.
- API/stream-runner mode: controlled by `GRAFANA_PUSH` and `GRAFANA_PUSH_EVERY_N`.

For Grafana push in either mode, configure:
- `GRAFANA_URL`
- `GRAFANA_USER`
- `GRAFANA_TOKEN`

#### Keyboard Controls (during playback)
| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | Pause/Resume |
| `h` | Hide/show info panels |
| `s` | Save screenshot |

## Theoretical Background

### Grover's Operator

The Grover operator G consists of:
1. **Oracle (O)**: Flips the phase of marked states (occupied regions)
2. **Diffusion (D)**: Amplifies marked states via inversion about the mean

$$G = D \cdot O$$

### Eigenvalue Structure

The key insight is that G has eigenvalues:

$$G|\psi_\pm\rangle = e^{\pm 2i\theta}|\psi_\pm\rangle$$

where:

$$\sin(\theta) = \sqrt{\frac{M}{N}}$$

This encodes the count M in the angle theta.

### Quantum Phase Estimation

QPE extracts the phase theta from G's eigenvalues:

1. Prepare uniform superposition over search space |s>
2. Apply controlled-G^(2^k) operations for each precision qubit k
3. Apply inverse QFT to counting register
4. Measure to get phase phi

### Phase Interpretation (Important!)

When the search register is initialized in uniform superposition |s> (not a pure eigenstate), QPE produces measurement peaks **centered around phi = 0.5**, offset by +/-theta/pi:

$$\phi_{measured} = 0.5 \pm \frac{\theta}{\pi}$$

Therefore, to extract theta:

$$\theta = \pi \cdot |\phi_{measured} - 0.5|$$

And to get the count M:

$$M = N \cdot \sin^2(\theta)$$

### Precision vs Search Space

| Register | Symbol | Purpose |
|----------|--------|---------|
| **Search qubits** | n | Encode N = 2^n grid regions |
| **Precision qubits** | p | Determine phase measurement resolution (2^p bins) |

**Rule of thumb:** `precision >= search_qubits + 2` for accurate results.

| Grid | N | Search (n) | Recommended Precision (p) |
|------|---|------------|---------------------------|
| 4x4 | 16 | 4 | 6 |
| 8x4 | 32 | 5 | 7 |
| 8x8 | 64 | 6 | 8 |

### Complexity Analysis

| Method | Oracle Queries | Total Operations |
|--------|---------------|------------------|
| Classical Counting | N | O(N) |
| Quantum Counting | O(sqrt(N)) | O(sqrt(N) log N) |

## Important Assumptions

> **Academic Honesty Note**: This project makes the following assumptions that should be clearly stated in any report or presentation.

### The Oracle Assumption

Quantum counting achieves O(sqrt(N)) speedup **in oracle queries**. However, in our implementation:

1. We construct the oracle **classically** by iterating through all regions
2. This classical preprocessing is O(N)
3. The quantum speedup applies to the **oracle query complexity**, not total runtime

### When Would This Be Practical?

The quantum advantage would be realized if:
- Car detection could be performed by **quantum sensors** directly
- Occupancy data was stored in **quantum memory**
- The oracle was a true **black-box** (not constructed classically)

### What This Project Demonstrates

- Correct implementation of quantum counting algorithm
- How Grover's operator eigenvalues encode solution count
- QPE for phase extraction
- Theoretical foundation for future quantum sensing applications

## Algorithm Details

### Oracle Construction

For each marked index i, the oracle applies a phase flip:

```python
for idx in marked_indices:
    # X gates to convert |idx> to |11...1>
    # Multi-controlled Z gate
    # Undo X gates
```

### Controlled Grover Powers

QPE requires controlled-G^(2^k) for each precision qubit k:

```python
for k in range(precision_qubits):
    power = 2 ** k
    for _ in range(power):
        controlled_grover = grover_op.control(1)
        qc.compose(controlled_grover, ...)
```

### Phase Interpretation

Due to the symmetric eigenvalues (+/-theta), we observe peaks at phi and (1-phi), both symmetric around 0.5. They correspond to the same M value:

```python
# Extract theta from offset from 0.5
theta = math.pi * abs(phi - 0.5)
M = N * math.sin(theta) ** 2
```

### Circuit Caching

To avoid redundant transpilation overhead, circuits are cached at the module level:

```python
_circuit_cache: Dict[tuple, QuantumCircuit] = {}
# Key: (n_qubits, precision_qubits, frozenset(marked_indices))
# Max 64 entries -- avoids re-transpiling identical configurations
```

## Output Logs

When processing video, the pipeline writes to the `logs/` directory:

- **`logs/data.csv`**: Per-frame data (overwritten each run -- import into Grafana or similar)

  | Column | Description |
  |--------|-------------|
  | `timestamp_ms` | Frame timestamp in milliseconds |
  | `num_detections` | Raw YOLO detection count |
  | `classical_count` | Classical marked-cell count |
  | `classical_density` | Classical density (0-1) |
  | `quantum_count` | Quantum estimated count |
  | `quantum_density` | Quantum estimated density (0-1) |
  | `error` | abs(quantum_count - classical_count) |
  | `relative_error_pct` | error / classical_count * 100 |
  | `density_A` | Density in direction A region |
  | `density_B` | Density in direction B region |
  | `vehicles_A` | Vehicle count in direction A |
  | `vehicles_B` | Vehicle count in direction B |
  | `classical_count_time_ns` | Classical O(N) reference count time |
  | `circuit_build_time_ms` | Circuit build overhead |
  | `transpile_time_ms` | Qiskit transpilation overhead |
  | `simulation_run_time_ms` | Aer simulator run time |
  | `estimated_qpu_time_ns` | Modeled real QPU execution time |
  | `simulation_overhead_ms` | simulation_run_time_ms - estimated_qpu_time_ns |
  | `circuit_depth` | Quantum circuit depth |
  | `estimated_speedup_vs_classical` | classical_count_time_ns / estimated_qpu_time_ns |
  | `density_difference` | quantum_density - classical_density |
  | `count_agreement` | `true` when quantum_count == classical_count |
  | `grid_size_N` | Total grid cells (rows x cols) |
  | `classical_queries_O_N` | Classical oracle queries (= N) |
  | `quantum_queries_O_sqrtN` | Quantum oracle queries (= sqrt(N)) |
  | `theoretical_speedup` | N / sqrt(N) = sqrt(N) |

  > Classical and quantum values in each row are always computed from the same frame snapshot, ensuring a fair comparison.

Average error: **< 1 region** with proper precision settings.

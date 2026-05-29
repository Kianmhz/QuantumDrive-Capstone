# Architecture

This document is the umbrella navigation aid for the three subprojects.
Subproject READMEs cover their own depth; this file is for cross-cutting
context — the end-to-end runtime flow, the engineering decisions worth
defending, and a cold-read order when you (or anyone else) is opening the
repo with no prior context.

---

## TL;DR

Three subprojects, two semesters, one umbrella:

1. **`semester-1-planning/`** — autonomous-vehicle decision making in CARLA.
   Classical brute-force vs. a 2-qubit Grover search over the same candidate
   acceleration profiles. Identical inputs, identical cost function, fair
   comparison.
2. **`semester-2-qflow/`** — traffic density estimation. YOLO → occupancy
   grid → Quantum Phase Estimation on a Grover operator. Plus a Flask
   device-agent that exposes the pipeline as an HTTP service.
3. **`semester-2-dashboard/`** — Nuxt 4 control panel that talks to one or
   two of those device agents over HTTP, proxied through Nitro server
   routes.

---

## Runtime flow: live demo (dashboard → quantum)

```
┌──────────────┐     /api/devices/pc/start      ┌──────────────┐
│   Browser    │ ─────────────────────────────▶ │ Nitro server │
│  (Nuxt SPA)  │                                │  (proxy)     │
└──────┬───────┘ ◀───────────  status  ──────── └──────┬───────┘
       │                                               │
       │ <img src="…/video_feed">                      │ POST /start
       │ direct MJPEG (no proxy)                       ▼
       │                                        ┌──────────────┐
       │                                        │ device-agent │
       └───────────────────────────────────────▶│   (Flask)    │
                                                └──────┬───────┘
                                                       │ runner.start()
                                                       ▼
                                            ┌──────────────────────┐
                                            │ PipelineStreamRunner │
                                            │  (3 threads)         │
                                            │   • YOLO feeder      │
                                            │   • quantum worker   │
                                            │   • grafana pusher   │
                                            └──────────┬───────────┘
                                                       │ every Nth frame
                                                       ▼
                                            ┌──────────────────────┐
                                            │  quantum_counting()  │
                                            │  build → transpile → │
                                            │  Aer.run → decode    │
                                            └──────────────────────┘
```

Status JSON is proxied through Nitro to dodge CORS; the MJPEG `<img>`
points at the agent directly because Nitro can't easily pipe a
multipart/x-mixed-replace stream.

## Runtime flow: planning loop (semester 1)

```
CARLA world.tick (100 Hz)
        │
        │  every 20 ticks (5 Hz)
        ▼
  build_lane_polyline()  ──┐
  ped_predictor()          ├─▶  make_accel_profiles()  ─▶  eval_candidate() per profile
                           │           │                          │
                           │           │                          ▼
                           │           │                  cost J or "infeasible"
                           │           │                          │
                           │           ▼                          │
                           │   ┌──────────────────────────┐       │
                           │   │ classical: argmin(costs) │ ◀─────┘
                           │   │ quantum:   grover_search │
                           │   └────────────┬─────────────┘
                           │                │
                           ▼                ▼
                       accel_to_controls(a0, v0)  ──▶  ego.apply_control(...)
```

The classical and Grover branches share `make_accel_profiles()` and
`eval_candidate()`. Only the `argmin` step differs — that's the whole
point of the comparison.

---

## Code paths worth knowing

### Semester 1 — Grover over discrete actions

- Candidate profiles are generated in
  [src/planning/candidates.py](semester-1-planning/src/planning/candidates.py) —
  `make_accel_profiles(v0, cfg)`. Returns `{name: ndarray}`.
- Each profile is scored by
  [src/planning/evaluator.py](semester-1-planning/src/planning/evaluator.py)
  `eval_candidate(...)`. Returns `(valid, cost, diag)`. Infeasibility
  (collision with `d_safe`) is a hard reject before any cost math.
- Classical choice is `min(costs)` in
  [src/planning/selector.py](semester-1-planning/src/planning/selector.py).
- The quantum branch wraps the same `costs` dict and runs a 2-qubit
  Grover oracle from
  [src/quantum/grover.py](semester-1-planning/src/quantum/grover.py).
  Action ↔ bitstring mapping lives in
  [src/quantum/grover_ped_demo.py](semester-1-planning/src/quantum/grover_ped_demo.py)
  (`ACTION_TO_BIT`).
- Scenario entry points:
  [scenario1_ped_crossing.py](semester-1-planning/src/scenarios/scenario1_ped_crossing.py)
  (classical),
  [scenario1_ped_crossing_grover.py:134](semester-1-planning/src/scenarios/scenario1_ped_crossing_grover.py:134)
  (Grover circuit construction inline in the planning tick),
  [scenario2_vehicle_cutin.py](semester-1-planning/src/scenarios/scenario2_vehicle_cutin.py)
  (rule-based highway cut-in),
  [scenario2_quantum.py](semester-1-planning/src/scenarios/scenario2_quantum.py)
  (Grover variant with a 4th `evasive_left` action).

### Semester 2 — Quantum Counting

- The CLI entry point is `process_video_with_quantum(...)` in
  [src/pipeline.py:37](semester-2-qflow/src/pipeline.py:37). It opens the
  video, runs YOLO per frame, builds an occupancy grid, calls
  `quantum_counting()` every N frames, and emits a per-frame CSV row.
- The QPE-on-Grover circuit is built in
  [src/quantum/quantum_counting.py:183](semester-2-qflow/src/quantum/quantum_counting.py:183).
  The QPE loop at line 302 is where controlled-G^(2^k) is applied for
  each precision bit — this is *the* algorithmic core.
- YOLO + filtering by COCO vehicle class IDs lives in
  [src/vision/video_processor.py:51](semester-2-qflow/src/vision/video_processor.py:51).
- Boxes → occupancy uses a dual threshold (cell-fraction OR
  box-fraction) so that both big-vehicle-spanning and small-distant
  detections are handled:
  [src/vision/boxes_to_occupancy.py:10](semester-2-qflow/src/vision/boxes_to_occupancy.py:10).

### Semester 2 — Device-agent threading model

[device-agent/stream_runner.py](semester-2-qflow/device-agent/stream_runner.py)
is the most interesting piece of orchestration in the repo. Three
threads, one queue between each pair:

- **YOLO feeder** (line 215) — reads frames, runs YOLO, pushes
  `(result, ts)` into a `queue.Queue(maxsize=2)`. Drops on full so
  visualization never stalls inference.
- **Main loop** — drains that queue, builds the occupancy + visualization,
  encodes a JPEG, and *also* submits one quantum-counting job to a single
  `ThreadPoolExecutor` (line 274). The future is checked non-blocking
  each tick (line 286).
- **Grafana worker** (line 450) — drains a bounded payload queue and
  POSTs to Grafana Cloud. Drop-counter at line 405 surfaces saturation.

### Semester 2 — Dashboard reactive polling

- [app/composables/useDevices.js](semester-2-dashboard/app/composables/useDevices.js)
  is the single source of truth for both devices' state. Key trick:
  `fetchStatus(device, { silent: true })` (line 45) avoids touching
  `loading`/logs during background polling, so the UI doesn't flash
  every 8 seconds.
- Server routes
  [server/api/devices/pc/status.get.js](semester-2-dashboard/server/api/devices/pc/status.get.js)
  return a *structured offline payload* (`{ online: false, …,
  _error: msg }`) instead of throwing — the dashboard composable
  reads `_error` and treats it as a graceful offline.

---

## Engineering decisions to defend

| Decision | Where | Why |
|---|---|---|
| Cache transpiled quantum circuits by `(n, p, M)` | [quantum_counting.py:43](semester-2-qflow/src/quantum/quantum_counting.py:43) | Transpile + circuit-build dominate wall time. Stats depend only on `M`, not on which indices are marked — canonicalize by `M` for cache hits. |
| Separate YOLO feeder thread | [stream_runner.py:215](semester-2-qflow/device-agent/stream_runner.py:215) | Visualization + JPEG encode must not block on inference. Bounded queue (size 2) caps memory and drops stale frames. |
| Run classical *and* quantum every Nth frame | [pipeline.py](semester-2-qflow/src/pipeline.py) + [logging.py](semester-2-qflow/src/utils/logging.py) | Per-row pairing in `data.csv` is the basis of the fairness claim — same frame, both estimates, no drift. |
| Proxy through Nitro server routes | [server/api/devices/*](semester-2-dashboard/server/api/devices) | Avoids CORS on the JSON endpoints. The MJPEG stream is the only thing the browser hits directly, because piping multipart through Nitro is annoying. |
| Single Grover iteration for 4 candidates | [grover.py](semester-1-planning/src/quantum/grover.py) + [scenario1_ped_crossing_grover.py:134](semester-1-planning/src/scenarios/scenario1_ped_crossing_grover.py:134) | For `N=4, M=1`, the optimal iteration count is exactly 1 — one oracle+diffusion is provably max-amplitude. Worth stating in an interview. |
| `actual_oracle_calls = 2^p − 1` | [quantum_counting.py:227](semester-2-qflow/src/quantum/quantum_counting.py:227) | QPE applies controlled-G^(2^k) for k=0..p−1, total = Σ2^k = 2^p − 1. The empirical-vs-theoretical (`√N`) gap is real and worth being honest about. |
| Drop-on-full for Grafana payloads | [stream_runner.py:402](semester-2-qflow/device-agent/stream_runner.py:402) | Observability must never stall the realtime pipeline. Counter at line 406 surfaces when it's happening. |

---

## Cold-read order

When you (or a recruiter, or future-you) open this repo:

### Semester 1 — planning

1. [`semester-1-planning/README.md`](semester-1-planning/README.md) — the pitch.
2. [`src/planning/candidates.py`](semester-1-planning/src/planning/candidates.py) — what gets searched.
3. [`src/planning/evaluator.py`](semester-1-planning/src/planning/evaluator.py) — how candidates are scored.
4. [`src/scenarios/scenario1_ped_crossing_grover.py`](semester-1-planning/src/scenarios/scenario1_ped_crossing_grover.py) — Grover circuit lives inline in the planning tick.
5. [`src/quantum/grover.py`](semester-1-planning/src/quantum/grover.py) — the oracle + diffusion primitives.

### Semester 2 — QFlow

1. [`semester-2-qflow/README.md`](semester-2-qflow/README.md) — CLI ref + theory.
2. [`src/quantum/quantum_counting.py`](semester-2-qflow/src/quantum/quantum_counting.py) — the QPE-on-Grover construction.
3. [`src/pipeline.py`](semester-2-qflow/src/pipeline.py) — frame loop, classical baseline alongside quantum.
4. [`device-agent/stream_runner.py`](semester-2-qflow/device-agent/stream_runner.py) — threading, queues, future-polling.
5. [`src/utils/logging.py`](semester-2-qflow/src/utils/logging.py) — every CSV column is intentional.

### Semester 2 — Dashboard

1. [`semester-2-dashboard/README.md`](semester-2-dashboard/README.md) — API contract.
2. [`nuxt.config.ts`](semester-2-dashboard/nuxt.config.ts) — `runtimeConfig` wiring.
3. [`app/composables/useDevices.js`](semester-2-dashboard/app/composables/useDevices.js) — silent polling pattern.
4. [`server/api/devices/pc/start.post.js`](semester-2-dashboard/server/api/devices/pc/start.post.js) — proxy pattern (4 lines of real logic).
5. [`app/components/DeviceCard.vue`](semester-2-dashboard/app/components/DeviceCard.vue) — runtime-config panel + MJPEG embed.

---

## Interview cheat-sheet

| Question | Where to point |
|---|---|
| "How does the quantum part *actually* work?" | quantum_counting.py — Grover op has eigenvalues e^{±2iθ} with sin²θ = M/N; QPE measures θ, then M = N·sin²θ. |
| "What's the quantum advantage here?" | Theoretical O(N) → O(√N) oracle queries; the practical gap (2^p − 1 vs N) is tabulated in semester-2-qflow/README.md → "Oracle-Call Scaling" — 2.1× at N=64 widening to 8.1× at N=1024, with the constructed-oracle caveat in "Important Assumptions". |
| "What happens when YOLO is faster than the quantum step?" | stream_runner.py — quantum runs once per N frames in its own executor; main loop checks the future non-blocking, so visualization stays at 20 fps. |
| "Why JS for the dashboard but TS for the configs?" | Source code is Vue + Composition API in JS; configs (`nuxt.config.ts`, `app.config.ts`) are TS because Nuxt's type inference is strongest there. Pragmatic split, not religious. |
| "How would this scale to 32+ candidates?" | semester-1-planning/README.md → "Scalability Discussion"; the encoding is `log2(N)` qubits and Grover's iteration count is roughly π/4·√(N/M). |
| "What's broken / what would you redo?" | Be honest: simulated quantum hardware, oracle is constructed classically (it's not a true black-box), 2-qubit search is too small for measurable speedup yet. The framework is the contribution, not the speedup. |

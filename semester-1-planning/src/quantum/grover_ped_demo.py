# src/quantum/grover_ped_demo_all.py
import json
import math
from pathlib import Path
import time
import re

from qiskit import QuantumCircuit, transpile
from qiskit_aer import Aer

from src.planning.config import PlanConfig
from src.planning.candidates import make_accel_profiles
from src.planning.evaluator import eval_candidate

# --- constants --------------------------------------------------------------
SNAP_DIR = Path("snapshots")
SNAP_PATTERN = re.compile(r"ped_scenario_t([0-9.]+)\.json")

BIT_TO_ACTION = {
    "00": "keep",
    "01": "comfort_brake",
    "10": "hard_brake",
    "11": "creep",
}
ACTION_TO_BIT = {v: k for k, v in BIT_TO_ACTION.items()}


# --- helpers ----------------------------------------------------------------
def fake_lane_from_snapshot(ego_loc, ego_vel, N_pts=400, ds=1.0):
    v0 = math.hypot(ego_vel[0], ego_vel[1])
    heading = math.atan2(ego_vel[1], ego_vel[0]) if v0 > 0.1 else 0.0
    ux, uy = math.cos(heading), math.sin(heading)

    class P:
        __slots__ = ("x", "y", "z")
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    pts = [P(ego_loc[0] + ux * i * ds, ego_loc[1] + uy * i * ds, ego_loc[2])
           for i in range(N_pts)]
    return pts, v0


def grover_oracle_from_costs(costs: dict[str, float]) -> QuantumCircuit:
    qc = QuantumCircuit(2)
    # find strictly best action
    best_action = min(costs, key=costs.get)
    # find its bitstring
    best_bits = ACTION_TO_BIT[best_action]

    # mark that single state
    for q, b in enumerate(best_bits[::-1]):  # q0, q1
        if b == "0":
            qc.x(q)
    qc.cz(0, 1)
    for q, b in enumerate(best_bits[::-1]):
        if b == "0":
            qc.x(q)

    return qc


def grover_diffusion(n_qubits=2) -> QuantumCircuit:
    qc = QuantumCircuit(n_qubits)
    qc.h(range(n_qubits))
    qc.x(range(n_qubits))
    qc.h(n_qubits - 1)
    qc.mcx(list(range(n_qubits - 1)), n_qubits - 1)
    qc.h(n_qubits - 1)
    qc.x(range(n_qubits))
    qc.h(range(n_qubits))
    return qc


# --- main loop --------------------------------------------------------------
def process_snapshot(path: Path):
    snap = json.loads(path.read_text())

    cfg = PlanConfig(**snap["cfg"])
    ego_loc = snap["ego"]["loc"]
    ego_vel = snap["ego"]["vel"]
    ped_loc = snap["ped"]["loc"]
    ped_vel = snap["ped"]["vel"]
    ego_half_width = snap["ego"]["half_width"]
    t_world = snap["sim_time"]

    lane_points, v0 = fake_lane_from_snapshot(ego_loc, ego_vel)
    s0 = 0.0

    def ped_pred(t):
        dt = max(0.0, t - t_world)
        class P:
            __slots__ = ("x", "y", "z")
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z
        return P(ped_loc[0] + ped_vel[0] * dt,
                 ped_loc[1] + ped_vel[1] * dt,
                 ped_loc[2])

    # --- Classical evaluation
    all_profiles = make_accel_profiles(v0, cfg)
    profiles = {n: p for n, p in all_profiles.items() if n in ACTION_TO_BIT}

    per_action = {}
    best_name, best_cost, best_diag = None, float("inf"), None

    for name, prof in profiles.items():
        valid, cost, diag = eval_candidate(
            prof, v0, s0, lane_points, ped_pred,
            cfg, t_world=t_world, ego_half_width=ego_half_width,
        )
        per_action[name] = (valid, cost, diag)
        if valid and cost < best_cost:
            best_name, best_cost, best_diag = name, cost, diag

    costs = {name: cost for name, (valid, cost, _) in per_action.items() if valid}

    if not costs:
        print(f"  [Warning] No valid candidate profiles at t={t_world:.2f}s — skipping.")
        return {
            "time": t_world,
            "classical_best": best_name,
            "grover_best": None,
            "counts": {},
            "costs": {},
        }

    # --- Quantum run
    qc = QuantumCircuit(2, 2)
    qc.h([0, 1])
    oracle = grover_oracle_from_costs(costs)
    diffusion = grover_diffusion(2)
    qc.compose(oracle, [0, 1], inplace=True)
    qc.compose(diffusion, [0, 1], inplace=True)
    qc.measure([0, 1], [0, 1])

    backend = Aer.get_backend("aer_simulator")
    result = backend.run(transpile(qc, backend), shots=512).result()
    counts = result.get_counts()

    best_bits = max(counts, key=counts.get)
    best_action = BIT_TO_ACTION[best_bits]
    return {
        "time": t_world,
        "classical_best": best_name,
        "grover_best": best_action,
        "counts": counts,
        "costs": costs,
    }


def main():
    # collect only files matching ped_scenario_t<number>.json
    tagged = []
    for p in SNAP_DIR.glob("*.json"):
        m = SNAP_PATTERN.match(p.name)
        if not m:
            continue  # skip things like ped_scenario_tick.json
        t = float(m.group(1))
        tagged.append((t, p))

    snap_paths = [p for t, p in sorted(tagged, key=lambda x: x[0])]
    print(f"[Grover] Found {len(snap_paths)} snapshots in {SNAP_DIR}")

    if not snap_paths:
        print("[Grover] No matching ped_scenario_t*.json files found.")
        return

    results = []
    for p in snap_paths:
        print(f"\n=== Processing {p.name} ===")
        t0 = time.perf_counter()
        res = process_snapshot(p)
        t1 = time.perf_counter()
        results.append(res)

        print(f"  Classical best: {res['classical_best']}")
        print(f"  Grover best:    {res['grover_best']}")
        print(f"  Duration:       {t1 - t0:.3f}s")

    print("\n=== Summary ===")
    matches = sum(r["classical_best"] == r["grover_best"] for r in results)
    print(f"Grover agreed with classical planner {matches}/{len(results)} times.")



if __name__ == "__main__":
    main()

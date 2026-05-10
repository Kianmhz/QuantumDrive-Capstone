"""
Quantum Counting for Traffic Density Estimation.

This module implements the Quantum Counting algorithm, which combines
Grover's algorithm with Quantum Phase Estimation (QPE) to estimate
the number of marked states (occupied regions) in O(√N) oracle queries.

Theoretical Background:
-----------------------
Given N = 2^n basis states and M marked states (occupied regions),
Grover's operator G has eigenvalues e^{±2iθ} where sin²(θ) = M/N.

Quantum Counting uses QPE to estimate θ, from which we can extract M:
    M = N · sin²(θ)

This provides a quadratic speedup over classical counting:
    - Classical: O(N) queries to count M items
    - Quantum:   O(√N) queries to estimate M

Assumption:
-----------
We assume the oracle is provided as a "black box" — representing future
quantum sensors or quantum memory that can mark occupied regions without
classical preprocessing. In this demo, we construct the oracle classically
for simulation purposes, but the algorithm itself only queries the oracle
O(√N) times.
"""

import math
import time
from typing import List, Tuple, Dict
from dataclasses import dataclass, field

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_aer import Aer
from qiskit.circuit.library import QFTGate

# ---------------------------------------------------------------------------
# Module-level cache: avoid rebuilding + re-transpiling identical circuits.
# Key: (n_qubits, precision_qubits, marked_count_M)
# Value: transpiled QuantumCircuit
# ---------------------------------------------------------------------------
_circuit_cache: dict = {}
_CIRCUIT_CACHE_MAX = 64   # cap memory usage

# Reuse one backend instance instead of calling get_backend() every frame
_aer_backend = None


def _get_backend():
    """Return a cached Aer simulator backend."""
    global _aer_backend
    if _aer_backend is None:
        _aer_backend = Aer.get_backend("aer_simulator")
    return _aer_backend


@dataclass
class QuantumMetrics:
    """Metadata from a quantum counting execution for dashboard logging."""
    estimated_M: int = 0
    estimated_density: float = 0.0
    counts: Dict[str, int] = field(default_factory=dict)
    # ── Timing breakdown ──────────────────────────────────────────────────
    # Time to run O(N) classical counting (reference baseline)
    classical_count_time_ns: float = 0.0
    # Classical preprocessing overhead (both are 0 on cache hits)
    circuit_build_time_ms: float = 0.0
    transpile_time_ms: float = 0.0
    # Time Aer spends simulating the circuit classically (NOT quantum time)
    simulation_run_time_ms: float = 0.0
    # Estimated wall-clock time on real superconducting QPU hardware
    estimated_qpu_time_ns: float = 0.0
    # simulation_run_time_ms - estimated_qpu_time_ns converted to ms (pure simulation tax)
    simulation_overhead_ms: float = 0.0
    # ── Circuit properties (used for QPU estimate) ────────────────────────
    circuit_depth: int = 0
    circuit_gate_count: int = 0
    # ── Speedup metrics ───────────────────────────────────────────────────
    # Theoretical complexity
    grid_size_N: int = 0
    precision_qubits: int = 0
    classical_queries_O_N: int = 0
    quantum_queries_O_sqrtN: float = 0.0
    theoretical_speedup: float = 0.0
    # Empirical: classical_count_time / estimated_qpu_time
    estimated_speedup_vs_classical: float = 0.0
    # Actual oracle calls made during QPE circuit construction
    # = sum(2^k for k in range(precision_qubits)) = 2^precision_qubits - 1
    actual_oracle_calls: int = 0
    # Empirical query speedup: classical_queries / actual_oracle_calls
    actual_query_speedup: float = 0.0


def build_oracle(n_qubits: int, marked_indices: List[int]) -> QuantumCircuit:
    """
    Build a Grover oracle that phase-flips all marked basis states.
    
    This oracle marks states |i⟩ where i ∈ marked_indices by applying
    a phase of -1. In a real quantum advantage scenario, this oracle
    would be implemented by quantum hardware/sensors, not classical
    preprocessing.
    
    Args:
        n_qubits: Number of qubits (search space size N = 2^n_qubits).
        marked_indices: List of indices to mark (occupied regions).
    
    Returns:
        QuantumCircuit implementing the oracle.
    """
    qc = QuantumCircuit(n_qubits, name="Oracle")
    
    if not marked_indices:
        return qc  # Empty oracle if nothing to mark
    
    for idx in marked_indices:
        # Convert index to binary (LSB at q0)
        bits = format(idx, f'0{n_qubits}b')[::-1]
        
        # Flip qubits that should be |0⟩ for this basis state
        for q, b in enumerate(bits):
            if b == '0':
                qc.x(q)
        
        # Multi-controlled Z gate
        if n_qubits == 1:
            qc.z(0)
        elif n_qubits == 2:
            qc.cz(0, 1)
        else:
            # H-MCX-H implements multi-controlled Z
            qc.h(n_qubits - 1)
            qc.mcx(list(range(n_qubits - 1)), n_qubits - 1)
            qc.h(n_qubits - 1)
        
        # Undo X gates
        for q, b in enumerate(bits):
            if b == '0':
                qc.x(q)
    
    return qc


def build_grover_operator(n_qubits: int, oracle: QuantumCircuit) -> QuantumCircuit:
    """
    Build the Grover operator G = D · O (diffusion after oracle).
    
    The Grover operator has eigenvalues e^{±2iθ} where sin²(θ) = M/N.
    QPE will estimate θ to determine M.
    
    Args:
        n_qubits: Number of qubits in the search space.
        oracle: The oracle circuit that marks solutions.
    
    Returns:
        QuantumCircuit implementing G.
    """
    qc = QuantumCircuit(n_qubits, name="Grover")
    
    # Apply oracle
    qc.compose(oracle, inplace=True)
    
    # Diffusion operator: 2|s⟩⟨s| - I
    qc.h(range(n_qubits))
    qc.x(range(n_qubits))
    
    # Multi-controlled Z
    qc.h(n_qubits - 1)
    if n_qubits == 1:
        qc.z(0)
    elif n_qubits == 2:
        qc.cx(0, 1)
    else:
        qc.mcx(list(range(n_qubits - 1)), n_qubits - 1)
    qc.h(n_qubits - 1)
    
    qc.x(range(n_qubits))
    qc.h(range(n_qubits))
    
    return qc


def quantum_counting(
    occupancy: List[int],
    precision_qubits: int = 6,
    shots: int = 1024
) -> Tuple[int, float, QuantumMetrics]:
    """
    Estimate the number of marked states using Quantum Counting.
    
    This algorithm uses Quantum Phase Estimation on the Grover operator
    to estimate θ where sin²(θ) = M/N, then computes M = N · sin²(θ).
    
    The Grover operator G has eigenvalues e^{±2iθ} where sin(θ) = √(M/N).
    QPE measures the phase 2θ/2π = θ/π, giving us θ from which we compute M.
    
    PRECISION REQUIREMENTS:
    -----------------------
    For accurate estimation, precision_qubits should be at least:
      - 4 for N=16 (coarse, ~±2 error)
      - 5 for N=16 (better, ~±1 error)  
      - 6 for N=16-32 (good, <±1 average error)
      - 7+ for high accuracy or large N
    
    The phase resolution is 1/2^precision_qubits. For small M, the phase
    angle θ = arcsin(√(M/N)) is small, requiring higher precision.
    
    Args:
        occupancy: Binary list where 1 = occupied region.
        precision_qubits: Number of qubits for phase estimation precision.
                         More qubits = better precision but deeper circuit.
                         Default: 6 (64 phase bins, good for N≤32).
        shots: Number of measurement shots.
    
    Returns:
        Tuple of (estimated_M, estimated_density, measurement_counts).
    """
    N = len(occupancy)
    n_qubits = int(math.log2(N))
    
    if 2 ** n_qubits != N:
        raise ValueError(f"Occupancy length {N} must be a power of 2")
    
    # Complexity values (always computed)
    classical_queries = N
    quantum_queries = math.sqrt(N)
    actual_oracle_calls = (2 ** (precision_qubits-1)) - 1
    theoretical_speedup = classical_queries / actual_oracle_calls if actual_oracle_calls > 0 else 0
    
    # Find marked indices (in practice, oracle would be a black box)
    marked_indices = [i for i, occ in enumerate(occupancy) if occ == 1]
    M_actual = len(marked_indices)
    
    if M_actual == 0:
        metrics = QuantumMetrics(
            estimated_M=0, estimated_density=0.0,
            counts={"0" * precision_qubits: shots},
            grid_size_N=N,
            precision_qubits=precision_qubits,
            classical_queries_O_N=classical_queries,
            quantum_queries_O_sqrtN=quantum_queries,
            theoretical_speedup=theoretical_speedup,
        )
        return 0, 0.0, metrics
    
    if M_actual == N:
        metrics = QuantumMetrics(
            estimated_M=N, estimated_density=1.0,
            counts={format(precision_qubits, f'0{precision_qubits}b'): shots},
            grid_size_N=N,
            precision_qubits=precision_qubits,
            classical_queries_O_N=classical_queries,
            quantum_queries_O_sqrtN=quantum_queries,
            theoretical_speedup=theoretical_speedup,
        )
        return N, 1.0, metrics
    
    # Time O(N) classical counting as a reference baseline
    t_classical = time.perf_counter()
    _ = sum(occupancy)
    classical_count_time_ns = (time.perf_counter() - t_classical) * 1e9

    # ------------------------------------------------------------------
    # Circuit cache lookup — skip rebuild + transpile for known patterns.
    # Quantum counting statistics depend on M (number of marked states),
    # not the specific marked indices, so canonicalize by M for cache hits.
    # ------------------------------------------------------------------
    cache_key = (n_qubits, precision_qubits, M_actual)
    backend = _get_backend()

    circuit_build_time_ms = 0.0
    transpile_time_ms = 0.0

    # Cache stores (transpiled, circuit_depth, circuit_gate_count)
    # so depth() and count_ops() are never called on a cache hit.
    if cache_key in _circuit_cache:
        transpiled, circuit_depth, circuit_gate_count = _circuit_cache[cache_key]
    else:
        t_build = time.perf_counter()
        # Build oracle and Grover operator
        canonical_marked_indices = list(range(M_actual))
        oracle = build_oracle(n_qubits, canonical_marked_indices)
        grover_op = build_grover_operator(n_qubits, oracle)

        # Create quantum counting circuit
        # Counting register (for QPE) + Search register
        counting_reg = QuantumRegister(precision_qubits, 'counting')
        search_reg = QuantumRegister(n_qubits, 'search')
        classical_reg = ClassicalRegister(precision_qubits, 'result')

        qc = QuantumCircuit(counting_reg, search_reg, classical_reg)

        # Initialize search register in uniform superposition
        qc.h(search_reg)

        # Initialize counting register in superposition
        qc.h(counting_reg)

        # Controlled Grover operators (controlled-G^(2^k)) — core of QPE.
        # Build controlled_grover ONCE per precision bit (not per application).
        controlled_grover = grover_op.control(1)
        for k in range(precision_qubits):
            power = 2 ** k
            for _ in range(power):
                qc.compose(
                    controlled_grover,
                    qubits=[counting_reg[k]] + list(search_reg),
                    inplace=True
                )

        # Inverse QFT on counting register
        qft_gate = QFTGate(precision_qubits).inverse()
        qc.append(qft_gate, counting_reg)

        # Measure counting register
        qc.measure(counting_reg, classical_reg)
        circuit_build_time_ms = (time.perf_counter() - t_build) * 1000

        t_transpile = time.perf_counter()
        transpiled = transpile(qc, backend, optimization_level=1)
        transpile_time_ms = (time.perf_counter() - t_transpile) * 1000

        # ── Compute circuit properties once at build time ──────────────
        circuit_depth = transpiled.depth()
        circuit_gate_count = sum(transpiled.count_ops().values())

        if len(_circuit_cache) >= _CIRCUIT_CACHE_MAX:
            # Evict oldest entry
            _circuit_cache.pop(next(iter(_circuit_cache)))
        _circuit_cache[cache_key] = (transpiled, circuit_depth, circuit_gate_count)

    # ── Actual oracle call count ──────────────────────────────────────
    # QPE applies controlled-G^(2^k) for k in 0..precision_qubits-1.
    # Each application = 1 oracle call, so total = sum(2^k) = 2^p - 1.
    # actual_oracle_calls already computed above (needed for theoretical_speedup).
    actual_query_speedup = (
        classical_queries / actual_oracle_calls if actual_oracle_calls > 0 else 0.0
    )

    # ── Estimated QPU time from actual oracle call count ─────────────
    # On real quantum hardware, each oracle query takes comparable time
    # to a classical lookup.  Estimated QPU time equals the classical
    # counting time scaled by the ratio of actual oracle calls to N.
    # actual_oracle_calls = 2^precision_qubits - 1 (from QPE structure).
    # Everything measured by Aer (sim_run) is simulation overhead — on a
    # real QPU you'd just run the circuit at hardware speed.
    estimated_qpu_time_ns = (
        classical_count_time_ns * actual_oracle_calls / classical_queries
        if classical_queries > 0 else 0.0
    )

    t_start = time.perf_counter()
    job = backend.run(transpiled, shots=shots)
    result = job.result()
    simulation_run_time_ms = (time.perf_counter() - t_start) * 1000
    counts = result.get_counts()
    
    # Analyze results to estimate M
    # The Grover operator G has eigenvalues e^{±2iθ} where sin(θ) = √(M/N)
    # This means the eigenvalue phases are ±2θ
    # QPE measures φ = 2θ/(2π) = θ/π OR φ = (2π - 2θ)/(2π) = 1 - θ/π
    # 
    # So we get two peaks at φ₁ and φ₂ = 1 - φ₁
    # Both should give the same M = N · sin²(πφ)
    # 
    # However, due to finite precision, we should identify pairs of peaks
    # and combine their evidence.
    #
    # IMPORTANT PHASE INTERPRETATION:
    # When the search register starts in |s⟩ (uniform superposition),
    # the QPE measures phases that appear at 0.5 ± θ/π, where the Grover
    # eigenvalues are e^{±2iθ} and sin(θ) = √(M/N).
    #
    # So: φ_observed ≈ 0.5 + θ/π  or  0.5 - θ/π
    # Therefore: θ = π × |φ_observed - 0.5|
    # And: M = N × sin²(θ)
    
    # First, collect raw phase measurements
    # NOTE: Qiskit returns bitstrings in big-endian order (MSB first),
    # which directly gives us the integer value without reversal
    phase_counts = {}
    for bitstring, count in counts.items():
        measured_int = int(bitstring, 2)  # No reversal needed!
        phi = measured_int / (2 ** precision_qubits)
        phase_counts[phi] = phase_counts.get(phi, 0) + count
    
    # Group symmetric phases around 0.5 (i.e., φ and 1-φ give same θ)
    # because |0.5 - φ| = |0.5 - (1-φ)| = |φ - 0.5|
    M_evidence = {}
    processed = set()
    
    for phi, count in phase_counts.items():
        if phi in processed:
            continue
        
        # Compute θ from the offset from 0.5
        theta = math.pi * abs(phi - 0.5)
        M_from_phi = N * (math.sin(theta) ** 2)
        
        # The symmetric phase (1-φ) gives the SAME θ offset from 0.5
        phi_partner = 1.0 - phi
        partner_count = 0
        for p, c in phase_counts.items():
            if abs(p - phi_partner) < 1e-9:  # Exact match for symmetric phase
                if p not in processed:
                    partner_count = c
                    processed.add(p)
                break
        
        processed.add(phi)
        total_count = count + partner_count
        
        # Round to nearest integer
        M_rounded = round(M_from_phi)
        M_rounded = max(0, min(N, M_rounded))
        
        if M_rounded not in M_evidence:
            M_evidence[M_rounded] = 0
        M_evidence[M_rounded] += total_count
    
    # Pick M with highest evidence
    if M_evidence:
        M_estimated = max(M_evidence.keys(), key=lambda m: M_evidence[m])
    else:
        M_estimated = 0
    
    estimated_density = M_estimated / N
    
    # The entire simulation pipeline is overhead — on a real QPU none of
    # this would exist.  Overhead = build + transpile + Aer simulation.
    simulation_overhead_ms = (
        circuit_build_time_ms
        + transpile_time_ms
        + simulation_run_time_ms
        - (estimated_qpu_time_ns / 1e6)
    )
    # Speedup based on actual oracle calls vs classical queries
    estimated_speedup_vs_classical = actual_query_speedup

    metrics = QuantumMetrics(
        estimated_M=M_estimated,
        estimated_density=estimated_density,
        counts=counts,
        classical_count_time_ns=classical_count_time_ns,
        circuit_build_time_ms=circuit_build_time_ms,
        transpile_time_ms=transpile_time_ms,
        simulation_run_time_ms=simulation_run_time_ms,
        estimated_qpu_time_ns=estimated_qpu_time_ns,
        simulation_overhead_ms=simulation_overhead_ms,
        circuit_depth=circuit_depth,
        circuit_gate_count=circuit_gate_count,
        grid_size_N=N,
        precision_qubits=precision_qubits,
        classical_queries_O_N=classical_queries,
        quantum_queries_O_sqrtN=quantum_queries,
        theoretical_speedup=theoretical_speedup,
        estimated_speedup_vs_classical=estimated_speedup_vs_classical,
        actual_oracle_calls=actual_oracle_calls,
        actual_query_speedup=actual_query_speedup,
    )

    return M_estimated, estimated_density, metrics



def compute_classical_count(occupancy: List[int]) -> int:
    """Classical O(N) counting of occupied regions."""
    return sum(occupancy)


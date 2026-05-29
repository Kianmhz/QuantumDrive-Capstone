# Shared 2-qubit Grover primitives used by the planning demos and scenarios.
from qiskit import QuantumCircuit


def grover_oracle_from_costs(costs: dict[str, float], action_to_bit: dict[str, str]) -> QuantumCircuit:
    """Mark the single basis state for the lowest-cost action.

    `action_to_bit` maps each action name to its 2-bit string, letting callers
    reuse this oracle with different action encodings.
    """
    qc = QuantumCircuit(2)
    best_action = min(costs, key=costs.get)
    best_bits = action_to_bit[best_action]

    for q, b in enumerate(best_bits[::-1]):  # q0, q1
        if b == "0":
            qc.x(q)
    qc.cz(0, 1)
    for q, b in enumerate(best_bits[::-1]):
        if b == "0":
            qc.x(q)

    return qc


def grover_diffusion(n_qubits: int = 2) -> QuantumCircuit:
    """Standard Grover diffusion (inversion-about-the-mean) operator."""
    qc = QuantumCircuit(n_qubits)
    qc.h(range(n_qubits))
    qc.x(range(n_qubits))
    qc.h(n_qubits - 1)
    qc.mcx(list(range(n_qubits - 1)), n_qubits - 1)
    qc.h(n_qubits - 1)
    qc.x(range(n_qubits))
    qc.h(range(n_qubits))
    return qc

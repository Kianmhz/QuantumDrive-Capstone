"""
Demo CLI for Quantum Counting.

Standalone runner for testing and benchmarking the quantum counting algorithm
in isolation, without running the full video pipeline.

Run with:
    python -m src.quantum.demo [OPTIONS]
"""

import math
from typing import Dict, List, Tuple

from src.quantum.quantum_counting import quantum_counting, compute_classical_count
from src.vision.boxes_to_occupancy import boxes_to_occupancy


def analyze_quantum_counting_results(
    counts: Dict[str, int],
    N: int,
    precision_qubits: int
) -> List[Tuple[int, float, int]]:
    """
    Analyze QPE measurement results to show phase-to-M mapping.

    Args:
        counts: Measurement counts from quantum counting.
        N: Total number of regions.
        precision_qubits: Number of precision qubits used.

    Returns:
        List of (measured_value, estimated_M, count) tuples, sorted by count.
    """
    results = []
    for bitstring, count in counts.items():
        # Qiskit returns big-endian (MSB first), no reversal needed
        measured_int = int(bitstring, 2)
        phi = measured_int / (2 ** precision_qubits)
        theta = math.pi * abs(phi - 0.5)
        M_estimate = N * (math.sin(theta) ** 2)
        results.append((measured_int, M_estimate, count))

    return sorted(results, key=lambda x: x[2], reverse=True)


def print_comparison(
    occupancy: List[int],
    rows: int,
    cols: int,
    precision_qubits: int = 4,
    shots: int = 2048
) -> None:
    """
    Run quantum counting and compare with classical results.

    Args:
        occupancy: Binary occupancy list.
        rows: Grid rows (for display).
        cols: Grid columns (for display).
        precision_qubits: QPE precision.
        shots: Measurement shots.
    """
    N = len(occupancy)
    n_qubits = int(math.log2(N))

    print("=" * 70)
    print("Quantum Counting for Traffic Density Estimation")
    print("=" * 70)

    print(f"\nConfiguration:")
    print(f"  Grid size: {rows} × {cols} = {N} regions")
    print(f"  Search space qubits: {n_qubits}")
    print(f"  Precision qubits (QPE): {precision_qubits}")
    print(f"  Measurement shots: {shots}")

    # Display occupancy grid
    print(f"\nOccupancy Grid (■ = occupied, □ = empty):")
    for r in range(rows):
        row_str = "  "
        for c in range(cols):
            idx = r * cols + c
            row_str += "■ " if occupancy[idx] == 1 else "□ "
        print(row_str)

    # Classical count
    M_classical = compute_classical_count(occupancy)
    density_classical = M_classical / N

    print(f"\nClassical Count (O(N) = O({N}) operations):")
    print(f"  Occupied regions: {M_classical}")
    print(f"  Density: {density_classical:.4f} ({density_classical*100:.1f}%)")

    # Quantum counting
    print(f"\nRunning Quantum Counting (O(√N) = O({int(math.sqrt(N))}) oracle queries)...")
    M_quantum, density_quantum, qm = quantum_counting(
        occupancy, precision_qubits=precision_qubits, shots=shots
    )

    print(f"\nQuantum Counting Results:")
    print(f"  Estimated occupied regions: {M_quantum}")
    print(f"  Estimated density: {density_quantum:.4f} ({density_quantum*100:.1f}%)")

    # Show phase analysis
    print(f"\nPhase Estimation Analysis (top 5 measurements):")
    analysis = analyze_quantum_counting_results(qm.counts, N, precision_qubits)
    for measured, M_est, count in analysis[:5]:
        phi = measured / (2 ** precision_qubits)
        print(f"  |{measured:0{precision_qubits}b}⟩ → φ={phi:.4f} → M≈{M_est:.2f} (measured {count} times)")

    # Comparison
    print(f"\n" + "=" * 70)
    print("Comparison Summary")
    print("=" * 70)
    print(f"  Classical M:  {M_classical}")
    print(f"  Quantum M:    {M_quantum}")
    print(f"  Error:        {abs(M_quantum - M_classical)} regions")
    print(f"  Relative error: {abs(M_quantum - M_classical) / max(M_classical, 1) * 100:.1f}%")

    print(f"\nComplexity Comparison:")
    print(f"  Classical counting: O(N) = O({N}) queries")
    print(f"  Quantum counting:   O(√N) = O({int(math.sqrt(N))}) oracle queries")
    print(f"  Speedup factor:     {N / max(int(math.sqrt(N)), 1)}×")

    print(f"\nNote: The quantum advantage assumes the oracle is a black-box")
    print(f"      (e.g., from quantum sensors). In this demo, we construct")
    print(f"      the oracle classically for simulation purposes.")


def main():
    """
    Demo: Quantum Counting for traffic density estimation.

    Run with: python -m src.quantum.demo [OPTIONS]
    """
    import argparse
    import random

    parser = argparse.ArgumentParser(
        description="Quantum Counting Demo for Traffic Density Estimation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.quantum.demo
  python -m src.quantum.demo --rows 4 --cols 4
  python -m src.quantum.demo --precision 6 --shots 2048
  python -m src.quantum.demo --test-m 5
  python -m src.quantum.demo --random
  python -m src.quantum.demo --benchmark
        """
    )

    parser.add_argument('--rows', type=int, default=4, help='Grid rows (default: 4)')
    parser.add_argument('--cols', type=int, default=4, help='Grid columns (default: 4)')
    parser.add_argument('--precision', '-p', type=int, default=4,
                        help='QPE precision qubits (default: 4, try 6 for accuracy)')
    parser.add_argument('--shots', '-s', type=int, default=2048,
                        help='Measurement shots (default: 2048)')
    parser.add_argument('--test-m', type=int, default=None,
                        help='Test specific M value (number of occupied regions)')
    parser.add_argument('--random', action='store_true', help='Run with random occupancy')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run benchmark across all M values')

    args = parser.parse_args()

    N = args.rows * args.cols
    if N & (N - 1) != 0:
        parser.error(f"Grid size {args.rows}x{args.cols}={N} must be a power of 2")

    n_qubits = int(math.log2(N))

    print("\n" + "=" * 70)
    print("QUANTUM COUNTING TRAFFIC DENSITY DEMO")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Grid: {args.rows}×{args.cols} = {N} regions")
    print(f"  Search qubits: {n_qubits}")
    print(f"  Precision qubits: {args.precision}")
    print(f"  Shots: {args.shots}")

    # Mode: Benchmark
    if args.benchmark:
        print(f"\n" + "=" * 70)
        print("BENCHMARK: Testing all M values from 0 to N")
        print("=" * 70)
        print(f"\n{'M':>3} | {'Classical':>9} | {'Quantum':>7} | {'Error':>5} | {'Status'}")
        print("-" * 50)

        total_error = 0
        for m in range(N + 1):
            occ = [1] * m + [0] * (N - m)
            q, _, _ = quantum_counting(occ, args.precision, args.shots)
            error = abs(q - m)
            total_error += error
            status = "✓" if error == 0 else ("~" if error <= 1 else "✗")
            print(f"{m:>3} | {m:>9} | {q:>7} | {error:>5} | {status}")

        print("-" * 50)
        print(f"Average error: {total_error / (N + 1):.2f} regions")
        return

    # Mode: Test specific M
    if args.test_m is not None:
        m = args.test_m
        if m < 0 or m > N:
            parser.error(f"--test-m must be between 0 and {N}")
        occ = [1] * m + [0] * (N - m)
        random.shuffle(occ)
        print(f"\n" + "=" * 70)
        print(f"TEST: M = {m} occupied regions")
        print("=" * 70)
        print_comparison(occ, args.rows, args.cols, args.precision, args.shots)
        return

    # Mode: Random occupancy
    if args.random:
        m = random.randint(0, N)
        occ = [1] * m + [0] * (N - m)
        random.shuffle(occ)
        print(f"\n" + "=" * 70)
        print(f"RANDOM TEST: M = {m} occupied regions")
        print("=" * 70)
        print_comparison(occ, args.rows, args.cols, args.precision, args.shots)
        return

    # Default mode: Run 3 demo scenarios
    image_w, image_h = 1920, 1080

    print("\n" + "=" * 70)
    print("TEST 1: Moderate Traffic Density")
    print("=" * 70)
    mock_boxes_moderate = [
        (100, 100, 400, 300),
        (1400, 100, 1700, 350),
        (200, 600, 500, 850),
        (900, 500, 1200, 750),
        (1500, 700, 1800, 950),
    ]
    print(f"\nSimulated YOLO detections: {len(mock_boxes_moderate)} cars")
    occ = boxes_to_occupancy(mock_boxes_moderate, args.rows, args.cols, image_w, image_h)
    print_comparison(occ, args.rows, args.cols, args.precision, args.shots)

    print("\n\n" + "=" * 70)
    print("TEST 2: Low Traffic Density")
    print("=" * 70)
    mock_boxes_low = [
        (100, 100, 350, 280),
        (1000, 500, 1300, 700),
        (1600, 800, 1850, 980),
    ]
    print(f"\nSimulated YOLO detections: {len(mock_boxes_low)} cars")
    occ = boxes_to_occupancy(mock_boxes_low, args.rows, args.cols, image_w, image_h)
    print_comparison(occ, args.rows, args.cols, args.precision, args.shots)

    print("\n\n" + "=" * 70)
    print("TEST 3: High Traffic Density")
    print("=" * 70)
    mock_boxes_high = [
        (50, 50, 300, 200),
        (400, 80, 700, 250),
        (1000, 50, 1300, 200),
        (1500, 100, 1800, 280),
        (150, 400, 450, 600),
        (800, 350, 1100, 550),
        (1400, 400, 1700, 600),
        (200, 750, 500, 950),
        (900, 700, 1200, 900),
    ]
    print(f"\nSimulated YOLO detections: {len(mock_boxes_high)} cars")
    occ = boxes_to_occupancy(mock_boxes_high, args.rows, args.cols, image_w, image_h)
    print_comparison(occ, args.rows, args.cols, args.precision, args.shots)


if __name__ == "__main__":
    main()

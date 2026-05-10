"""
Logging utilities for tracking quantum vs classical density estimates.

Provides CSV logging and summary statistics for analysis.
"""

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import statistics

from src.utils.grafana import push_metrics_to_grafana


@dataclass
class FrameLog:
    """Log entry for a single frame."""
    timestamp_ms: float
    num_detections: int
    classical_count: int
    classical_density: float
    quantum_count: Optional[int]
    quantum_density: Optional[float]
    # --- Direction density ---
    density_A: Optional[float] = None
    density_B: Optional[float] = None
    vehicles_A: Optional[int] = None
    vehicles_B: Optional[int] = None
    # --- Timing breakdown ---
    classical_count_time_ns: Optional[float] = None     # O(N) classical reference time
    circuit_build_time_ms: Optional[float] = None       # build overhead (0 if cached)
    transpile_time_ms: Optional[float] = None           # transpile overhead (0 if cached)
    simulation_run_time_ms: Optional[float] = None      # Aer simulation time (NOT QPU)
    estimated_qpu_time_ns: Optional[float] = None       # estimated real hardware time
    simulation_overhead_ms: Optional[float] = None      # sim_run - estimated_qpu
    circuit_depth: Optional[int] = None
    estimated_speedup_vs_classical: Optional[float] = None
    # --- Quantum vs Classical comparison ---
    density_difference: Optional[float] = None      # quantum - classical (signed)
    count_agreement: Optional[bool] = None           # quantum == classical
    # --- Theoretical speedup ---
    grid_size_N: Optional[int] = None
    classical_queries_O_N: Optional[int] = None
    quantum_queries_O_sqrtN: Optional[float] = None
    theoretical_speedup: Optional[float] = None
    # --- Actual empirical oracle query counts ---
    actual_oracle_calls: Optional[int] = None      # real calls made: 2^precision_qubits - 1
    actual_query_speedup: Optional[float] = None   # classical_queries / actual_oracle_calls
    
    @property
    def error(self) -> Optional[int]:
        """Absolute error in region count."""
        if self.quantum_count is None:
            return None
        return abs(self.quantum_count - self.classical_count)
    
    @property
    def relative_error(self) -> Optional[float]:
        """Relative error as percentage."""
        if self.quantum_count is None or self.classical_count == 0:
            return None
        return abs(self.quantum_count - self.classical_count) / self.classical_count * 100


@dataclass 
class SessionStats:
    """Aggregate statistics for a processing session."""
    total_frames: int = 0
    quantum_frames: int = 0
    avg_classical_density: float = 0.0
    avg_quantum_density: float = 0.0
    avg_error: float = 0.0
    avg_relative_error: float = 0.0
    max_error: int = 0
    min_error: int = 0
    std_error: float = 0.0
    # Timing
    avg_classical_count_time_ns: float = 0.0
    avg_simulation_run_time_ms: float = 0.0
    avg_estimated_qpu_time_ns: float = 0.0
    avg_simulation_overhead_ms: float = 0.0
    avg_estimated_speedup_vs_classical: float = 0.0
    # Quantum vs Classical agreement
    agreement_rate: float = 0.0     # % of quantum frames where counts match
    avg_density_difference: float = 0.0
    # Theoretical speedup (constant per session)
    grid_size_N: int = 0
    theoretical_speedup: float = 0.0


class DensityLogger:
    """
    Logger for tracking quantum vs classical density estimates.
    
    Writes per-frame data to CSV and computes summary statistics.
    """
    
    def __init__(
        self,
        output_dir: str = "logs",
        session_name: Optional[str] = None,
        video_name: Optional[str] = None,
        grafana_push: bool = False,
    ):
        """
        Initialize the logger.
        
        Args:
            output_dir: Directory for log files.
            session_name: Custom session name (default: timestamp).
            video_name: Name of the video being processed.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        if session_name is None:
            session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.session_name = session_name
        self.video_name = video_name or "unknown"
        self.grafana_push = grafana_push
        
        # Fixed CSV file – overwritten on every run
        self.csv_path = self.output_dir / "data.csv"
        self.logs: List[FrameLog] = []
        
        # Initialize CSV with headers
        self._init_csv()
        
        # Config info for the summary
        self.config: Dict[str, Any] = {}
    
    def _init_csv(self):
        """Initialize CSV file with headers."""
        headers = [
            'timestamp_ms', 'num_detections',
            'classical_count', 'classical_density',
            'quantum_count', 'quantum_density',
            'error', 'relative_error_pct',
            # Direction density
            'density_A', 'density_B', 'vehicles_A', 'vehicles_B',
            # Timing breakdown
            'classical_count_time_ns',
            'circuit_build_time_ms',
            'transpile_time_ms',
            'simulation_run_time_ms',
            'estimated_qpu_time_ns',
            'simulation_overhead_ms',
            'circuit_depth',
            'estimated_speedup_vs_classical',
            # Quantum vs Classical comparison
            'density_difference', 'count_agreement',
            # Theoretical speedup
            'grid_size_N', 'classical_queries_O_N',
            'quantum_queries_O_sqrtN', 'theoretical_speedup',
            # Actual empirical oracle query counts
            'actual_oracle_calls', 'actual_query_speedup',
        ]
        
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
    
    def set_config(self, **kwargs):
        """Store configuration for summary."""
        self.config.update(kwargs)
    
    def log_frame(self, log: FrameLog):
        """
        Log a single frame's results.
        
        Args:
            log: FrameLog entry.
        """
        self.logs.append(log)

        # Push to Grafana (non-blocking best-effort)
        if self.grafana_push:
            push_metrics_to_grafana({
                "classical_count":              log.classical_count,
                "quantum_count":                log.quantum_count,
                "classical_density":            log.classical_density * 100 if log.classical_density is not None else None,
                "quantum_density":              log.quantum_density * 100 if log.quantum_density is not None else None,
                "error":                        log.error,
                "relative_error_pct":           log.relative_error,
                "density_A":                    log.density_A * 100 if log.density_A is not None else None,
                "density_B":                    log.density_B * 100 if log.density_B is not None else None,
                "num_detections":               log.num_detections,
                "count_agreement":              log.count_agreement,
                "theoretical_speedup":          log.theoretical_speedup,
                # New timing breakdown
                "classical_count_time_ns":      log.classical_count_time_ns,
                "circuit_build_time_ms":        log.circuit_build_time_ms,
                "transpile_time_ms":            log.transpile_time_ms,
                "simulation_run_time_ms":       log.simulation_run_time_ms,
                "estimated_qpu_time_ns":        log.estimated_qpu_time_ns,
                "simulation_overhead_ms":       log.simulation_overhead_ms,
                "circuit_depth":                log.circuit_depth,
                "estimated_speedup_vs_classical": log.estimated_speedup_vs_classical,
            })

        # Append to CSV
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                f"{log.timestamp_ms:.2f}",
                log.num_detections,
                log.classical_count,
                f"{log.classical_density:.4f}",
                log.quantum_count if log.quantum_count is not None else "",
                f"{log.quantum_density:.4f}" if log.quantum_density is not None else "",
                log.error if log.error is not None else "",
                f"{log.relative_error:.2f}" if log.relative_error is not None else "",
                # Direction density
                f"{log.density_A:.4f}" if log.density_A is not None else "",
                f"{log.density_B:.4f}" if log.density_B is not None else "",
                log.vehicles_A if log.vehicles_A is not None else "",
                log.vehicles_B if log.vehicles_B is not None else "",
                # Timing breakdown
                f"{log.classical_count_time_ns:.3f}" if log.classical_count_time_ns is not None else "",
                f"{log.circuit_build_time_ms:.2f}" if log.circuit_build_time_ms is not None else "",
                f"{log.transpile_time_ms:.2f}" if log.transpile_time_ms is not None else "",
                f"{log.simulation_run_time_ms:.4f}" if log.simulation_run_time_ms is not None else "",
                f"{log.estimated_qpu_time_ns:.3f}" if log.estimated_qpu_time_ns is not None else "",
                f"{log.simulation_overhead_ms:.4f}" if log.simulation_overhead_ms is not None else "",
                log.circuit_depth if log.circuit_depth is not None else "",
                f"{log.estimated_speedup_vs_classical:.4f}" if log.estimated_speedup_vs_classical is not None else "",
                # Quantum vs Classical comparison
                f"{log.density_difference:.4f}" if log.density_difference is not None else "",
                log.count_agreement if log.count_agreement is not None else "",
                # Theoretical speedup
                log.grid_size_N if log.grid_size_N is not None else "",
                log.classical_queries_O_N if log.classical_queries_O_N is not None else "",
                f"{log.quantum_queries_O_sqrtN:.2f}" if log.quantum_queries_O_sqrtN is not None else "",
                f"{log.theoretical_speedup:.2f}" if log.theoretical_speedup is not None else "",
                # Actual empirical oracle query counts
                log.actual_oracle_calls if log.actual_oracle_calls is not None else "",
                f"{log.actual_query_speedup:.4f}" if log.actual_query_speedup is not None else "",
            ])
    
    def compute_stats(self) -> SessionStats:
        """Compute aggregate statistics from logged frames."""
        if not self.logs:
            return SessionStats()
        
        stats = SessionStats()
        stats.total_frames = len(self.logs)
        
        # Filter frames where quantum was computed
        quantum_logs = [l for l in self.logs if l.quantum_count is not None]
        stats.quantum_frames = len(quantum_logs)
        
        # Classical stats
        classical_densities = [l.classical_density for l in self.logs]
        stats.avg_classical_density = statistics.mean(classical_densities)
        
        # Quantum stats (only frames where quantum ran)
        if quantum_logs:
            quantum_densities = [l.quantum_density for l in quantum_logs if l.quantum_density is not None]
            if quantum_densities:
                stats.avg_quantum_density = statistics.mean(quantum_densities)
            
            # Error stats
            errors = [l.error for l in quantum_logs if l.error is not None]
            if errors:
                stats.avg_error = statistics.mean(errors)
                stats.max_error = max(errors)
                stats.min_error = min(errors)
                if len(errors) > 1:
                    stats.std_error = statistics.stdev(errors)
            
            rel_errors = [l.relative_error for l in quantum_logs if l.relative_error is not None]
            if rel_errors:
                stats.avg_relative_error = statistics.mean(rel_errors)
        
        # Quantum timing
        classical_times = [l.classical_count_time_ns for l in self.logs if l.classical_count_time_ns is not None]
        if classical_times:
            stats.avg_classical_count_time_ns = statistics.mean(classical_times)

        sim_run_times = [l.simulation_run_time_ms for l in self.logs if l.simulation_run_time_ms is not None]
        if sim_run_times:
            stats.avg_simulation_run_time_ms = statistics.mean(sim_run_times)

        qpu_times = [l.estimated_qpu_time_ns for l in self.logs if l.estimated_qpu_time_ns is not None]
        if qpu_times:
            stats.avg_estimated_qpu_time_ns = statistics.mean(qpu_times)

        overhead_times = [l.simulation_overhead_ms for l in self.logs if l.simulation_overhead_ms is not None]
        if overhead_times:
            stats.avg_simulation_overhead_ms = statistics.mean(overhead_times)

        speedups = [l.estimated_speedup_vs_classical for l in self.logs if l.estimated_speedup_vs_classical is not None]
        if speedups:
            stats.avg_estimated_speedup_vs_classical = statistics.mean(speedups)

        # Quantum vs Classical agreement
        if quantum_logs:
            agreements = [l.count_agreement for l in quantum_logs if l.count_agreement is not None]
            if agreements:
                stats.agreement_rate = sum(1 for a in agreements if a) / len(agreements) * 100
            diffs = [l.density_difference for l in quantum_logs if l.density_difference is not None]
            if diffs:
                stats.avg_density_difference = statistics.mean(diffs)

        # Theoretical speedup (constant per session — take from first log that has it)
        for l in self.logs:
            if l.grid_size_N is not None:
                stats.grid_size_N = l.grid_size_N
                stats.theoretical_speedup = l.theoretical_speedup or 0.0
                break

        return stats
    
    def save_summary(self) -> str:
        """
        Save a summary report and return its path.
        
        Returns:
            Path to the summary file.
        """
        stats = self.compute_stats()
        summary_path = self.output_dir / f"summary_{self.session_name}.txt"
        
        with open(summary_path, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("QUANTUM TRAFFIC DENSITY ESTIMATION - SESSION SUMMARY\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"Session: {self.session_name}\n")
            f.write(f"Video: {self.video_name}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Configuration
            if self.config:
                f.write("Configuration:\n")
                for key, value in self.config.items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
            
            # Processing stats
            f.write("Processing Statistics:\n")
            f.write(f"  Total frames processed: {stats.total_frames}\n")
            f.write(f"  Frames with quantum counting: {stats.quantum_frames}\n")
            f.write(f"  Average simulation run time: {stats.avg_simulation_run_time_ms:.2f}ms\n\n")
            
            # Density stats
            f.write("Density Statistics:\n")
            f.write(f"  Average classical density: {stats.avg_classical_density*100:.2f}%\n")
            f.write(f"  Average quantum density: {stats.avg_quantum_density*100:.2f}%\n")
            f.write(f"  Average density difference: {stats.avg_density_difference*100:.2f} pp\n")
            f.write(f"  Count agreement rate: {stats.agreement_rate:.1f}%\n\n")

            # Timing breakdown
            f.write("Timing Breakdown (averages per quantum frame):\n")
            f.write(f"  Classical O(N) count time:      {stats.avg_classical_count_time_ns:.3f} ns  [reference]\n")
            f.write(f"  Aer simulation run time:        {stats.avg_simulation_run_time_ms:.2f} ms  [NOT quantum — classical sim overhead]\n")
            f.write(f"  Estimated real QPU time:        {stats.avg_estimated_qpu_time_ns:.3f} ns  [modeled from circuit depth × gate times]\n")
            f.write(f"  Pure simulation overhead:       {stats.avg_simulation_overhead_ms:.2f} ms  [sim_run - estimated_qpu]\n")
            f.write(f"  Estimated actual speedup:       {stats.avg_estimated_speedup_vs_classical:.2f}x  [classical_time / estimated_qpu_time]\n\n")

            # Theoretical speedup
            f.write("Theoretical Quantum Speedup:\n")
            f.write(f"  Grid size N: {stats.grid_size_N}\n")
            f.write(f"  Classical queries: O(N) = {stats.grid_size_N}\n")
            sqrt_n = math.sqrt(stats.grid_size_N) if stats.grid_size_N > 0 else 0
            f.write(f"  Quantum queries: O(sqrt(N)) = {sqrt_n:.1f}\n")
            f.write(f"  Theoretical speedup: {stats.theoretical_speedup:.1f}x\n\n")

            # Actual oracle query counts
            quantum_logs = [l for l in self.logs if l.actual_oracle_calls is not None]
            if quantum_logs:
                oracle_calls = quantum_logs[0].actual_oracle_calls
                query_speedup = quantum_logs[0].actual_query_speedup
                f.write("Actual Empirical Oracle Query Count:\n")
                f.write(f"  Classical queries (O(N)):       {stats.grid_size_N}\n")
                f.write(f"  Quantum oracle calls (2^p - 1): {oracle_calls}\n")
                f.write(f"  Actual query speedup:           {query_speedup:.2f}x\n")
                f.write(f"  Note: oracle calls = 2^precision_qubits - 1, constant for fixed N\n\n")
            
            # Error analysis
            f.write("Quantum Estimation Error Analysis:\n")
            f.write(f"  Average absolute error: {stats.avg_error:.2f} regions\n")
            f.write(f"  Average relative error: {stats.avg_relative_error:.2f}%\n")
            f.write(f"  Min error: {stats.min_error} regions\n")
            f.write(f"  Max error: {stats.max_error} regions\n")
            f.write(f"  Std deviation: {stats.std_error:.2f} regions\n\n")
            
            # Error distribution
            if self.logs:
                quantum_logs = [l for l in self.logs if l.quantum_count is not None and l.error is not None]
                if quantum_logs:
                    f.write("Error Distribution:\n")
                    error_counts = {}
                    for l in quantum_logs:
                        e = l.error
                        error_counts[e] = error_counts.get(e, 0) + 1
                    
                    for error in sorted(error_counts.keys()):
                        count = error_counts[error]
                        pct = count / len(quantum_logs) * 100
                        bar = "█" * int(pct / 2)
                        f.write(f"  {error:2d} regions: {count:4d} ({pct:5.1f}%) {bar}\n")
            
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"CSV log saved to: {self.csv_path}\n")
            f.write("=" * 70 + "\n")
        
        return str(summary_path)
    
    def print_summary(self):
        """Print summary to console."""
        stats = self.compute_stats()
        
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"Total frames: {stats.total_frames}")
        print(f"Quantum frames: {stats.quantum_frames}")
        print(f"Avg simulation run: {stats.avg_simulation_run_time_ms:.2f}ms")
        print(f"\nDensity Comparison:")
        print(f"  Classical avg: {stats.avg_classical_density*100:.2f}%")
        print(f"  Quantum avg:   {stats.avg_quantum_density*100:.2f}%")
        print(f"  Avg difference: {stats.avg_density_difference*100:.2f} pp")
        print(f"  Agreement rate: {stats.agreement_rate:.1f}%")
        print(f"\nTiming Breakdown:")
        print(f"  Classical O(N) count:   {stats.avg_classical_count_time_ns:.3f} ns")
        print(f"  Aer simulation run:     {stats.avg_simulation_run_time_ms:.2f} ms  (classical sim overhead)")
        print(f"  Est. real QPU time:     {stats.avg_estimated_qpu_time_ns:.3f} ns  (from circuit depth × gate model)")
        print(f"  Simulation overhead:    {stats.avg_simulation_overhead_ms:.2f} ms  (sim_run - est_qpu)")
        print(f"  Est. actual speedup:    {stats.avg_estimated_speedup_vs_classical:.2f}x  (classical / est_qpu)")
        print(f"\nTheoretical Speedup:")
        sqrt_n = math.sqrt(stats.grid_size_N) if stats.grid_size_N > 0 else 0
        print(f"  Grid N={stats.grid_size_N}: O(N)={stats.grid_size_N} vs O(√N)={sqrt_n:.1f} → {stats.theoretical_speedup:.1f}x")
        oracle_logs = [l for l in self.logs if l.actual_oracle_calls is not None]
        if oracle_logs:
            print(f"\nActual Oracle Query Count:")
            print(f"  Classical queries (O(N)):       {stats.grid_size_N}")
            print(f"  Quantum oracle calls (2^p - 1): {oracle_logs[0].actual_oracle_calls}")
            print(f"  Actual query speedup:           {oracle_logs[0].actual_query_speedup:.2f}x")
        print(f"\nQuantum Error Analysis:")
        print(f"  Mean error: {stats.avg_error:.2f} ± {stats.std_error:.2f} regions")
        print(f"  Mean relative error: {stats.avg_relative_error:.2f}%")
        print(f"  Error range: [{stats.min_error}, {stats.max_error}] regions")
        print(f"\nLogs saved to: {self.csv_path}")
        print("=" * 60)

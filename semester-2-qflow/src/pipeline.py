"""
Main pipeline: Video → YOLO → Quantum Counting → Visualization.

This module integrates all components for end-to-end traffic density
estimation using quantum counting.
"""

import argparse
import queue as _queue_module
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Optional

import cv2
from src.vision.boxes_to_occupancy import boxes_to_occupancy, directional_occupancy
from src.vision.visualization import create_visualization
from src.quantum.quantum_counting import (
    quantum_counting,
    compute_classical_count,
)
from src.utils.logging import DensityLogger, FrameLog

# Import video processor (with fallback to mock)
try:
    from src.vision.video_processor import VideoProcessor, YOLO_AVAILABLE, get_video_info
    if not YOLO_AVAILABLE:
        from src.vision.video_processor import MockVideoProcessor as VideoProcessor
        print("Warning: YOLO not available, using mock detections")
except ImportError as e:
    print(f"Error importing video processor: {e}")
    sys.exit(1)


def process_video_with_quantum(
    video_path: str,
    rows: int = 4,
    cols: int = 4,
    precision_qubits: int = 6,
    shots: int = 1024,
    confidence_threshold: float = 0.5,
    use_quantum: bool = True,
    device: str = "cuda",
    quantum_every_n: int = 5,
    enable_logging: bool = True,
    log_dir: str = "logs",
    direction_split: Optional[str] = "vertical",
    grafana_push: bool = False,
):

    # Validate grid size is power of 2
    N = rows * cols
    if N & (N - 1) != 0:
        print(f"Error: Grid size {rows}x{cols}={N} must be a power of 2")
        sys.exit(1)
    
    # Get video info
    info = get_video_info(video_path)
    print(f"\nVideo: {video_path}")
    print(f"  Resolution: {info['width']}x{info['height']}")
    print(f"  FPS: {info['fps']:.2f}")
    print(f"  Duration: {info['duration']:.2f}s ({info['frame_count']} frames)")
    
    print(f"\nConfiguration:")
    print(f"  Grid: {rows}x{cols} = {N} regions")
    print(f"  Quantum counting: {'Enabled' if use_quantum else 'Disabled'}")
    if use_quantum:
        print(f"  Precision qubits: {precision_qubits}")
        print(f"  Measurement shots: {shots}")
        print(f"  Quantum every N frames: {quantum_every_n}")
    print(f"  Direction split: {direction_split if direction_split else 'Disabled'}")
    print(f"  Logging: {'Enabled' if enable_logging else 'Disabled'}")
    
    # Initialize logger
    logger = None
    if enable_logging:
        video_name = Path(video_path).name
        logger = DensityLogger(output_dir=log_dir, video_name=video_name, grafana_push=grafana_push)
        logger.set_config(
            grid=f"{rows}x{cols}",
            total_regions=N,
            quantum_enabled=use_quantum,
            precision_qubits=precision_qubits,
            shots=shots,
            quantum_every_n=quantum_every_n,
            confidence_threshold=confidence_threshold,
            device=device,
            direction_split=direction_split if direction_split else "none",
        )
    
    # Initialize video processor
    print(f"\nInitializing YOLO model...")
    processor = VideoProcessor(
        confidence_threshold=confidence_threshold,
        device=device
    )
    
    # Process frames
    print(f"\nProcessing video...")
    print("Press 'q' to quit, 'p' to pause, 'h' to hide/show panels, 's' to save screenshot")
    print("-" * 60)
    
    frame_times = []
    paused = False
    show_info = True          # Toggle with 'h'

    # Create fullscreen window (scales frame to fill display)
    cv2.namedWindow("Quantum Traffic Density", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Quantum Traffic Density", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    last_quantum_density = None
    last_quantum_count = None
    last_quantum_metrics = None  # QuantumMetrics from most recent quantum run
    frames_since_calc = 0          # frames elapsed since last classical+quantum pair

    # Last known display values (shown every frame in visualization)
    last_classical_count = 0
    last_classical_density = 0.0

    # Classical snapshot stored at quantum submission time (for paired logging)
    pending_classical_count: Optional[int] = None
    pending_classical_density: Optional[float] = None
    pending_dir_data = None
    pending_timestamp_ms: Optional[float] = None

    target_fps = 20
    frame_duration = 1.0 / target_fps

    # Background threads: quantum simulation + logging I/O
    quantum_executor = ThreadPoolExecutor(max_workers=1)
    logging_executor = ThreadPoolExecutor(max_workers=1)
    quantum_future: Optional[Future] = None

    # YOLO runs on a background thread so the display loop never freezes.
    # The queue holds at most 2 pre-detected frames; if the main loop is
    # slower than YOLO the feeder blocks naturally (backpressure).
    _frame_queue: _queue_module.Queue = _queue_module.Queue(maxsize=2)
    _yolo_stop = threading.Event()

    def _yolo_worker() -> None:
        try:
            for result in processor.process_video(video_path):
                if _yolo_stop.is_set():
                    return
                _frame_queue.put(result)  # blocks when queue is full
        except Exception as exc:
            _frame_queue.put(exc)
        finally:
            _frame_queue.put(None)  # sentinel — video ended or worker exiting

    yolo_thread = threading.Thread(target=_yolo_worker, daemon=True, name="yolo-inference")
    yolo_thread.start()

    vis_frame = None  # last rendered frame; re-shown while YOLO processes the next

    try:
        while True:
            if paused:
                key = cv2.waitKey(30) & 0xFF
                if key == ord('p'):
                    paused = False
                elif key == ord('q'):
                    break
                continue

            # Non-blocking dequeue so the window stays responsive while YOLO is busy
            try:
                item = _frame_queue.get_nowait()
            except _queue_module.Empty:
                # YOLO hasn't finished the next frame yet — re-display the last
                # frame so the window doesn't freeze and key events keep firing.
                if vis_frame is not None:
                    cv2.imshow("Quantum Traffic Density", vis_frame)
                key = cv2.waitKey(5) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('p'):
                    paused = True
                elif key == ord('h'):
                    show_info = not show_info
                continue

            if item is None:
                break  # video finished
            if isinstance(item, Exception):
                raise item
            result = item

            start_time = time.time()  # includes all work: processing + logging + print
            
            # Always build occupancy grid and direction data (needed for visualization every frame)
            occupancy = boxes_to_occupancy(
                result.boxes_xyxy,
                rows, cols,
                info['width'], info['height']
            )
            dir_data = None
            if direction_split:
                dir_data = directional_occupancy(
                    result.boxes_xyxy,
                    rows, cols,
                    info['width'], info['height'],
                    split=direction_split,
                )

            # ── Decide whether to trigger a new classical+quantum computation ──
            # Trigger when N frames have elapsed AND no quantum job is still running
            # (so classical and quantum always see the exact same occupancy snapshot)
            trigger = frames_since_calc >= quantum_every_n and (
                not use_quantum or quantum_future is None
            )

            if trigger:
                # Classical density on this frame's occupancy
                last_classical_count = compute_classical_count(occupancy)
                last_classical_density = last_classical_count / N

                # Save snapshot for paired logging when quantum result arrives
                pending_classical_count = last_classical_count
                pending_classical_density = last_classical_density
                pending_dir_data = dir_data  # already computed above
                pending_timestamp_ms = (
                    result.frame_number / info['fps'] * 1000 if info['fps'] > 0 else 0
                )

                # Submit quantum job on the SAME occupancy snapshot
                if use_quantum:
                    _occ_snapshot = list(occupancy)
                    quantum_future = quantum_executor.submit(
                        quantum_counting,
                        _occ_snapshot,
                        precision_qubits,
                        shots
                    )

                frames_since_calc = 0
            else:
                frames_since_calc += 1

            # Use last known classical values for visualization every frame
            classical_count = last_classical_count
            classical_density = last_classical_density

            # Poll: collect quantum result if background job finished
            quantum_ran_this_frame = False
            if quantum_future is not None and quantum_future.done():
                try:
                    last_quantum_count, last_quantum_density, last_quantum_metrics = quantum_future.result()
                    quantum_ran_this_frame = True
                except Exception as _qe:
                    print(f"\nQuantum error: {_qe}")
                finally:
                    quantum_future = None

            quantum_density = last_quantum_density
            quantum_count = last_quantum_count

            # Create visualization
            labels = [d.class_name for d in result.detections]
            confidences = [d.confidence for d in result.detections]
            
            vis_frame = create_visualization(
                result.frame,
                result.boxes_xyxy,
                occupancy,
                rows, cols,
                classical_density,
                quantum_density=quantum_density,
                quantum_count=quantum_count,
                labels=labels,
                confidences=confidences,
                direction_data=dir_data,
                show_info=show_info,
            )
            
            # Log frame data — only when a matched classical+quantum pair is ready
            # Logging runs on a background thread to keep file I/O off the UI thread.
            if logger:
                if use_quantum and quantum_ran_this_frame and pending_classical_count is not None:
                    # Paired log: classical snapshot from submission time + quantum result
                    qm = last_quantum_metrics
                    density_diff = (
                        last_quantum_density - pending_classical_density
                        if last_quantum_density is not None else None
                    )
                    count_agree = (
                        last_quantum_count == pending_classical_count
                        if last_quantum_count is not None else None
                    )
                    _log_entry = FrameLog(
                        timestamp_ms=pending_timestamp_ms,
                        num_detections=len(result.detections),
                        classical_count=pending_classical_count,
                        classical_density=pending_classical_density,
                        quantum_count=last_quantum_count,
                        quantum_density=last_quantum_density,
                        density_A=pending_dir_data["density_A"] if pending_dir_data else None,
                        density_B=pending_dir_data["density_B"] if pending_dir_data else None,
                        vehicles_A=len(pending_dir_data["boxes_A"]) if pending_dir_data else None,
                        vehicles_B=len(pending_dir_data["boxes_B"]) if pending_dir_data else None,
                        classical_count_time_ns=qm.classical_count_time_ns if qm else None,
                        circuit_build_time_ms=qm.circuit_build_time_ms if qm else None,
                        transpile_time_ms=qm.transpile_time_ms if qm else None,
                        simulation_run_time_ms=qm.simulation_run_time_ms if qm else None,
                        estimated_qpu_time_ns=qm.estimated_qpu_time_ns if qm else None,
                        simulation_overhead_ms=qm.simulation_overhead_ms if qm else None,
                        circuit_depth=qm.circuit_depth if qm else None,
                        estimated_speedup_vs_classical=qm.estimated_speedup_vs_classical if qm else None,
                        density_difference=density_diff,
                        count_agreement=count_agree,
                        grid_size_N=N,
                        classical_queries_O_N=qm.classical_queries_O_N if qm else N,
                        quantum_queries_O_sqrtN=qm.quantum_queries_O_sqrtN if qm else None,
                        theoretical_speedup=qm.theoretical_speedup if qm else None,
                        actual_oracle_calls=qm.actual_oracle_calls if qm else None,
                        actual_query_speedup=qm.actual_query_speedup if qm else None,
                    )
                    logging_executor.submit(logger.log_frame, _log_entry)
                    pending_classical_count = None  # consumed — wait for next trigger
                elif not use_quantum and trigger:
                    # Classical-only logging (no quantum)
                    _log_entry = FrameLog(
                        timestamp_ms=pending_timestamp_ms,
                        num_detections=len(result.detections),
                        classical_count=last_classical_count,
                        classical_density=last_classical_density,
                        quantum_count=None,
                        quantum_density=None,
                        density_A=dir_data["density_A"] if dir_data else None,
                        density_B=dir_data["density_B"] if dir_data else None,
                        vehicles_A=len(dir_data["boxes_A"]) if dir_data else None,
                        vehicles_B=len(dir_data["boxes_B"]) if dir_data else None,
                        density_difference=None,
                        count_agreement=None,
                        grid_size_N=N,
                        classical_queries_O_N=N,
                        quantum_queries_O_sqrtN=None,
                        theoretical_speedup=None,
                    )
                    logging_executor.submit(logger.log_frame, _log_entry)
            
            # Measure processing elapsed (used for the frame-rate limiter)
            elapsed = time.time() - start_time
            frame_times.append(elapsed)

            # Show preview
            cv2.imshow("Quantum Traffic Density", vis_frame)
            
            # Cap frame rate to 30 FPS for smooth playback
            wait_time = max(1, int((frame_duration - elapsed) * 1000))
            key = cv2.waitKey(wait_time) & 0xFF

            # Total wall time including the sleep — used for accurate fps display
            frame_wall_time = time.time() - start_time
            fps_estimate = 1 / frame_wall_time if frame_wall_time > 0 else 0

            # Print progress every 5 frames to reduce terminal I/O overhead
            if result.frame_number % 5 == 0:
                dir_info = ""
                if dir_data:
                    dir_info = (f"  A={dir_data['density_A']*100:.1f}% "
                                f"B={dir_data['density_B']*100:.1f}%")
                print(f"\rFrame {result.frame_number}: "
                      f"Vehicles={len(result.detections)}, "
                      f"Classical={classical_density*100:.1f}%, "
                      f"{'Quantum=' + f'{quantum_density*100:.1f}%' if quantum_density else ''}"
                      f"{dir_info} "
                      f"({fps_estimate:.1f} fps)", end="")
            
            if key == ord('q'):
                print("\nQuitting...")
                break
            elif key == ord('p'):
                paused = True
            elif key == ord('h'):
                show_info = not show_info
            elif key == ord('s'):
                screenshot_path = f"screenshot_{result.frame_number}.png"
                cv2.imwrite(screenshot_path, vis_frame)
                print(f"\nSaved screenshot: {screenshot_path}")
    
    finally:
        # Stop the YOLO worker and drain the queue so it can unblock from put()
        _yolo_stop.set()
        while True:
            try:
                _frame_queue.get_nowait()
            except _queue_module.Empty:
                break
        yolo_thread.join(timeout=3)

        if quantum_future is not None:
            quantum_future.cancel()
        quantum_executor.shutdown(wait=False)
        logging_executor.shutdown(wait=True)   # flush pending log writes
        cv2.destroyAllWindows()
    
    # Print summary
    print("\n" + "-" * 60)
    if frame_times:
        avg_time = sum(frame_times) / len(frame_times)
        print(f"\nProcessed {len(frame_times)} frames")
        print(f"Average processing time: {avg_time*1000:.1f}ms/frame ({1/avg_time:.1f} fps)")
    
    # Save and print logging summary
    if logger:
        summary_path = logger.save_summary()
        logger.print_summary()
        print(f"\nDetailed logs: {logger.csv_path}")
        print(f"Summary report: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Quantum Traffic Density Estimation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Input
    parser.add_argument('--video', type=str, required=True, help='Path to input video')

    # Grid options
    parser.add_argument('--rows', type=int, default=8, help='Grid rows (default: 8)')
    parser.add_argument('--cols', type=int, default=8, help='Grid columns (default: 8)')
    
    # Quantum options
    parser.add_argument('--no-quantum', action='store_true',
                       help='Disable quantum counting (faster)')
    parser.add_argument('--precision', type=int, default=6,
                       help='QPE precision qubits (default: 6, more=accurate but slower)')
    parser.add_argument('--shots', type=int, default=512,
                       help='Quantum measurement shots (default: 512, more=accurate)')
    parser.add_argument('--quantum-every', type=int, default=5,
                       help='Run quantum+classical counting every N frames (default: 5)')
    
    # Processing options
    parser.add_argument('--device', type=str, default='cuda',
                       choices=['cpu', 'cuda', 'mps'],
                       help='Device for YOLO inference (default: cuda)')
    
    # Logging options
    parser.add_argument('--no-log', action='store_true',
                       help='Disable logging to CSV')
    parser.add_argument('--log-dir', type=str, default='logs',
                       help='Directory for log files (default: logs)')
    parser.add_argument('--grafana', action='store_true',
                       help='Push per-frame metrics to Grafana Cloud '
                            '(requires GRAFANA_URL, GRAFANA_USER, GRAFANA_TOKEN env vars)')

    # Direction comparison options
    parser.add_argument('--split', type=str, default='vertical',
                       choices=['vertical', 'horizontal'],
                       help='Split orientation for direction A/B comparison '
                            '(default: vertical — left=A, right=B)')
    parser.add_argument('--no-direction', action='store_true',
                       help='Disable direction A/B comparison')

    args = parser.parse_args()

    # Resolve direction split
    direction_split = None if args.no_direction else args.split
    
    # Validate grid size
    N = args.rows * args.cols
    if N & (N - 1) != 0:
        parser.error(f"Grid size {args.rows}x{args.cols}={N} must be a power of 2")
    
    process_video_with_quantum(
        video_path=args.video,
        rows=args.rows,
        cols=args.cols,
        precision_qubits=args.precision,
        shots=args.shots,
        use_quantum=not args.no_quantum,
        device=args.device,
        quantum_every_n=args.quantum_every,
        enable_logging=not args.no_log,
        log_dir=args.log_dir,
        direction_split=direction_split,
        grafana_push=args.grafana,
    )


if __name__ == "__main__":
    main()
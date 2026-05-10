"""
Video processing pipeline with YOLO object detection.

This module captures video frames, runs YOLO to detect vehicles,
and feeds the detections into the quantum counting pipeline.
"""

import cv2
from pathlib import Path
from typing import List, Tuple, Optional, Generator
from dataclasses import dataclass

# Try to import ultralytics (YOLO), but make it optional for testing
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    YOLO = None


@dataclass
class Detection:
    """A single object detection."""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int
    class_name: str


@dataclass
class FrameResult:
    """Result of processing a single frame."""
    frame: any  # numpy array (cv2 image)
    frame_number: int
    detections: List[Detection]
    boxes_xyxy: List[Tuple[int, int, int, int]]


class VideoProcessor:
    """
    Process video frames with YOLO object detection.
    
    Attributes:
        model: YOLO model for object detection.
        vehicle_classes: Set of class IDs considered as vehicles.
        confidence_threshold: Minimum confidence for detections.
    """
    
    # COCO class IDs for vehicles
    VEHICLE_CLASS_IDS = {2, 3, 5, 7}  # car, motorcycle, bus, truck
    VEHICLE_CLASS_NAMES = {'car', 'motorcycle', 'bus', 'truck'}
    
    def __init__(
        self,
        model_path: str = "yolov8m.pt",
        confidence_threshold: float = 0.2,
        device: str = "cuda"
    ):
        """
        Initialize the video processor.
        
        Args:
            model_path: Path to YOLO model weights (will download if not found).
                       Options: yolov8n.pt (fast), yolov8s.pt (balanced), yolov8m.pt (accurate)
            confidence_threshold: Minimum confidence for detections.
            device: Device to run inference on ('cpu', 'cuda', 'mps').
        """
        if not YOLO_AVAILABLE:
            raise ImportError(
                "ultralytics is not installed. "
                "Install it with: pip install ultralytics"
            )
        
        self.model = YOLO(model_path)
        self.device = device
        self.confidence_threshold = confidence_threshold
        
        # Use half precision (FP16) on GPU for faster inference
        self.use_half = device == "cuda"
        if self.use_half:
            self.model.to(device)
            print(f"  Using GPU with FP16 for faster inference")
        else:
            self.model.to(device)
    
    def detect_vehicles(self, frame) -> List[Detection]:
        """
        Run YOLO inference on a frame and return vehicle detections.
        
        Args:
            frame: BGR image (numpy array from cv2).
        
        Returns:
            List of Detection objects for vehicles only.
        """
        # Run inference with half precision on GPU
        results = self.model(frame, verbose=False, half=self.use_half)[0]
        
        detections = []
        for box in results.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            
            # Filter by confidence and vehicle class
            if confidence < self.confidence_threshold:
                continue
            if class_id not in self.VEHICLE_CLASS_IDS:
                continue
            
            # Extract bounding box (xyxy format)
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bbox = (int(x1), int(y1), int(x2), int(y2))
            
            # Get class name
            class_name = results.names[class_id]
            
            detections.append(Detection(
                bbox=bbox,
                confidence=confidence,
                class_id=class_id,
                class_name=class_name
            ))
        
        return detections
    
    def process_frame(self, frame, frame_number: int = 0) -> FrameResult:
        """
        Process a single frame: detect vehicles and extract bounding boxes.
        
        Args:
            frame: BGR image (numpy array).
            frame_number: Frame index for tracking.
        
        Returns:
            FrameResult with detections and bounding boxes.
        """
        detections = self.detect_vehicles(frame)
        boxes_xyxy = [d.bbox for d in detections]
        
        return FrameResult(
            frame=frame,
            frame_number=frame_number,
            detections=detections,
            boxes_xyxy=boxes_xyxy,
        )
    
    def process_video(
        self,
        video_path: str,
        max_frames: Optional[int] = None
    ) -> Generator[FrameResult, None, None]:
        """
        Process a video file frame by frame.
        
        Args:
            video_path: Path to video file.
            max_frames: Maximum number of frames to process (None = all).
        
        Yields:
            FrameResult for each processed frame.
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        frame_count = 0
        processed_count = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Check max frames limit
                if max_frames is not None and processed_count >= max_frames:
                    break
                
                yield self.process_frame(frame, frame_count)
                
                frame_count += 1
                processed_count += 1
        
        finally:
            cap.release()
    
def get_video_info(video_path: str) -> dict:
    """
    Get metadata about a video file.
    
    Args:
        video_path: Path to video file.
    
    Returns:
        Dictionary with width, height, fps, frame_count, duration.
    """
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    
    try:
        info = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        }
        info['duration'] = info['frame_count'] / info['fps'] if info['fps'] > 0 else 0
        return info
    finally:
        cap.release()


# For testing without YOLO - generates mock detections
class MockVideoProcessor:
    """
    Mock video processor for testing without YOLO installed.
    Generates random vehicle detections.
    """
    
    def __init__(self, **kwargs):
        """Accept any kwargs for API compatibility."""
        import random
        self.random = random
    
    def detect_vehicles(self, frame) -> List[Detection]:
        """Generate random mock detections."""
        h, w = frame.shape[:2]
        num_cars = self.random.randint(2, 8)
        
        detections = []
        for _ in range(num_cars):
            # Random bounding box
            x1 = self.random.randint(0, w - 200)
            y1 = self.random.randint(0, h - 150)
            x2 = x1 + self.random.randint(100, 200)
            y2 = y1 + self.random.randint(80, 150)
            
            detections.append(Detection(
                bbox=(x1, y1, x2, y2),
                confidence=self.random.uniform(0.6, 0.95),
                class_id=2,
                class_name='car'
            ))
        
        return detections
    
    def process_frame(self, frame, frame_number: int = 0) -> FrameResult:
        """Process frame with mock detections."""
        detections = self.detect_vehicles(frame)
        boxes_xyxy = [d.bbox for d in detections]
        
        return FrameResult(
            frame=frame,
            frame_number=frame_number,
            detections=detections,
            boxes_xyxy=boxes_xyxy,
        )
    
    def process_video(self, video_path: str, **kwargs):
        """Process video with mock detections."""
        cap = cv2.VideoCapture(video_path)
        frame_count = 0
        max_frames = kwargs.get('max_frames')
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if max_frames and frame_count >= max_frames:
                    break
                
                yield self.process_frame(frame, frame_count)
                frame_count += 1
        finally:
            cap.release()

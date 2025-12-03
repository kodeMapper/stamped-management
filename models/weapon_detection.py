"""
Weapon Detection Module
Uses YOLOv8 for detecting weapons (guns, knives)
"""
import cv2
import numpy as np
import torch
from typing import Tuple, List, Optional
from pathlib import Path
from threading import Lock
import time


class WeaponDetector:
    """Detects weapons using YOLOv8 object detection"""
    
    def __init__(self, 
                 model_path: str = "yolov8n.pt",
                 confidence_threshold: float = 0.25,
                 target_classes: List[str] = None):
        """
        Initialize weapon detector
        
        Args:
            model_path: Path to YOLO model weights
            confidence_threshold: Minimum confidence for detections
            target_classes: List of class names to detect (default: ['knife', 'gun'])
        """
        self.confidence_threshold = confidence_threshold
        self.target_classes = [cls.lower() for cls in (target_classes or ['knife', 'gun'])]
        self.keyword_map = {
            'gun': {'gun', 'pistol', 'firearm', 'revolver', 'handgun', 'weapon'},
            'knife': {'knife', 'dagger', 'blade', 'sword', 'weapon'}
        }
        self.model = None
        self.model_loaded = False
        self.model_path = self._resolve_model_path(model_path)
        self.inference_lock = Lock()
        self.cache: dict[int, dict] = {}
        self.cache_ttl = 0.4  # seconds
        if self.model_path is None:
            print(f"[WeaponDetector] Could not locate weights file '{model_path}'")
            return
        
        # Try to load YOLO model
        try:
            # Fix PyTorch 2.6+ weights_only issue
            try:
                from ultralytics.nn import tasks as u_tasks
                torch.serialization.add_safe_globals([
                    torch.nn.modules.container.Sequential,
                    u_tasks.DetectionModel
                ])
            except Exception as e:
                print(f"[WeaponDetector] Warning: Could not register safe globals: {e}")
            
            # Import and load YOLO
            from ultralytics import YOLO
            self.model = YOLO(str(self.model_path))
            self.model_loaded = True
            print(f"[WeaponDetector] Successfully loaded model: {self.model_path}")
            
        except Exception as e:
            print(f"[WeaponDetector] Failed to load YOLO model: {e}")
            print("[WeaponDetector] Weapon detection will be disabled")
            self.model_loaded = False

    def _resolve_model_path(self, model_path: str) -> Optional[Path]:
        """Resolve weights path relative to project if needed."""
        candidates = []
        path = Path(model_path)
        if path.is_file():
            candidates.append(path)
        base_dir = Path(__file__).resolve().parent.parent
        candidates.append(base_dir / model_path)
        candidates.append(base_dir / "models" / model_path)
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _is_target_class(self, label: str) -> bool:
        label = (label or "").lower()
        if label in self.target_classes:
            return True
        for key in self.target_classes:
            keywords = self.keyword_map.get(key, {key})
            if any(keyword in label for keyword in keywords):
                return True
        return False
    
    def detect_weapons(self, frame: np.ndarray, camera_id: Optional[int] = None) -> Tuple[np.ndarray, bool, List[dict]]:
        """
        Detect weapons in a frame
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Tuple of (annotated_frame, weapon_detected, detections_list)
        """
        if frame is None or not self.model_loaded:
            return frame if frame is not None else None, False, []

        cache_key = camera_id if camera_id is not None else None
        if cache_key is not None:
            cached = self.cache.get(cache_key)
            if cached and (time.time() - cached['timestamp'] <= self.cache_ttl):
                return cached['frame'].copy(), cached['weapon_detected'], list(cached['detections'])
        
        try:
            with self.inference_lock:
                # Run YOLO inference (align with working final_weapon pipeline)
                results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            
            annotated_frame = frame.copy()
            weapon_detected = False
            detections = []
            
            # Process first result set for current frame
            result = results[0] if isinstance(results, list) else results
            if hasattr(result, 'boxes') and result.boxes is not None:
                data = result.boxes.data.cpu().numpy()
                names = getattr(result, 'names', self.model.names)
                for det in data:
                    x1, y1, x2, y2, conf, cls_id = det
                    cls_id = int(cls_id)
                    conf = float(conf)
                    class_name = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else names[cls_id]
                    if conf < self.confidence_threshold:
                        continue
                    if not self._is_target_class(class_name):
                        continue
                    weapon_detected = True
                    x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
                    detections.append({
                        'class': class_name,
                        'confidence': conf,
                        'bbox': (x1, y1, x2, y2)
                    })
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    label_text = f"{class_name.upper()} {conf:.2f}"
                    label_size, _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(annotated_frame, (x1, y1 - label_size[1] - 10),
                                  (x1 + label_size[0], y1), (0, 0, 255), -1)
                    cv2.putText(annotated_frame, label_text, (x1, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            if cache_key is not None:
                self.cache[cache_key] = {
                    'frame': annotated_frame.copy(),
                    'weapon_detected': weapon_detected,
                    'detections': list(detections),
                    'timestamp': time.time()
                }

            return annotated_frame, weapon_detected, detections
            
        except Exception as e:
            print(f"[WeaponDetector] Error during detection: {e}")
            return frame, False, []
    
    def add_overlay(self, frame: np.ndarray, weapon_detected: bool, detections: List[dict]) -> np.ndarray:
        """
        Add alert overlay to frame
        
        Args:
            frame: Input frame
            weapon_detected: Whether a weapon was detected
            detections: List of detection dictionaries
            
        Returns:
            Frame with overlay
        """
        if frame is None:
            return None
        
        h, w = frame.shape[:2]
        
        if weapon_detected:
            # Add red flashing border
            cv2.rectangle(frame, (0, 0), (w-1, h-1), (0, 0, 255), 8)
            
            # Add alert banner
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 255), -1)
            frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
            
            # Alert text
            alert_text = "ALERT: WEAPON DETECTED!"
            cv2.putText(frame, alert_text, (w//2 - 200, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            
            # List detected weapons
            y_offset = 100
            for det in detections:
                text = f"{det['class'].upper()}: {det['confidence']*100:.1f}%"
                cv2.putText(frame, text, (20, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_offset += 30
        else:
            # Normal status
            overlay = frame.copy()
            cv2.rectangle(overlay, (10, 10), (250, 60), (0, 0, 0), -1)
            frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
            
            cv2.putText(frame, "Status: CLEAR", (20, 45),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return frame
    
    def is_loaded(self) -> bool:
        """Check if the model is loaded and ready"""
        return self.model_loaded

"""
Unified Camera Manager for Integrated Surveillance System
Handles shared camera access across all detection models
"""
import cv2
import numpy as np
from threading import Thread, Lock
import time
from typing import Optional, Dict, Callable


class CameraStream:
    """Manages a single camera stream with thread-safe frame access"""
    
    def __init__(self, camera_id: int, name: str, width: int = 640, height: int = 480):
        self.camera_id = camera_id
        self.name = name
        self.width = width
        self.height = height
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional[np.ndarray] = None
        self.running = False
        self.thread: Optional[Thread] = None
        self.lock = Lock()
        self.last_update = 0
        
    def start(self) -> bool:
        """Start the camera stream"""
        if self.running:
            return True
            
        try:
            # Try to open camera with DirectShow backend (Windows)
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                # Fallback to default backend
                self.cap = cv2.VideoCapture(self.camera_id)
            
            if not self.cap.isOpened():
                print(f"[CameraStream] Failed to open camera {self.camera_id}")
                return False
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
            
            # Start capture thread
            self.running = True
            self.thread = Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            
            print(f"[CameraStream] Started {self.name} (ID: {self.camera_id})")
            return True
            
        except Exception as e:
            print(f"[CameraStream] Error starting {self.name}: {e}")
            return False
    
    def _capture_loop(self):
        """Continuously capture frames from the camera"""
        consecutive_failures = 0
        
        while self.running:
            try:
                if not self.cap or not self.cap.isOpened():
                    print(f"[CameraStream] {self.name} disconnected, attempting reconnect...")
                    self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
                    time.sleep(1)
                    continue
                
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > 10:
                        print(f"[CameraStream] {self.name} failed to read frame")
                        time.sleep(1)
                        consecutive_failures = 0
                    continue
                
                # Reset failure counter
                consecutive_failures = 0
                
                # Store frame with thread safety
                with self.lock:
                    self.frame = frame.copy()
                    self.last_update = time.time()
                
                # Small delay to prevent CPU overuse
                time.sleep(0.01)
                
            except Exception as e:
                print(f"[CameraStream] Error in {self.name} capture loop: {e}")
                time.sleep(1)
    
    def read(self) -> Optional[np.ndarray]:
        """Get the latest frame from the camera"""
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()
    
    def stop(self):
        """Stop the camera stream"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()
        print(f"[CameraStream] Stopped {self.name}")


class CameraManager:
    """Central manager for all camera streams"""
    
    def __init__(self):
        self.cameras: Dict[int, CameraStream] = {}
        self.initialized = False
    
    def add_camera(self, camera_id: int, name: str, width: int = 640, height: int = 480) -> bool:
        """Add a camera to the manager"""
        if camera_id in self.cameras:
            print(f"[CameraManager] Camera {camera_id} already exists")
            return True
        
        camera = CameraStream(camera_id, name, width, height)
        if camera.start():
            self.cameras[camera_id] = camera
            return True
        return False
    
    def get_frame(self, camera_id: int) -> Optional[np.ndarray]:
        """Get the latest frame from a specific camera"""
        camera = self.cameras.get(camera_id)
        if camera:
            return camera.read()
        return None
    
    def get_camera(self, camera_id: int) -> Optional[CameraStream]:
        """Get a camera stream object"""
        return self.cameras.get(camera_id)
    
    def stop_all(self):
        """Stop all camera streams"""
        for camera in self.cameras.values():
            camera.stop()
        self.cameras.clear()
        self.initialized = False
    
    def initialize_default_cameras(self) -> bool:
        """Initialize default cameras (0 and 1)"""
        if self.initialized:
            return True
        
        success = True
        if not self.add_camera(0, "Main Camera"):
            print("[CameraManager] Warning: Main camera (0) not available")
            success = False
        
        if not self.add_camera(1, "External Camera"):
            print("[CameraManager] Warning: External camera (1) not available")
            # Don't set success to False - one camera is okay
        
        self.initialized = True
        return success


# Global camera manager instance
camera_manager = CameraManager()

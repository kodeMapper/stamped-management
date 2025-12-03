"""
Face Recognition Module
Uses OpenCV Haar cascade for detection and FaceNet embeddings (facenet-pytorch)
with a template-based fallback when the deep model is unavailable.
"""
from __future__ import annotations

import numpy as np
import cv2
import torch
from typing import Tuple, Optional

try:
    from facenet_pytorch import InceptionResnetV1
except ImportError:
    InceptionResnetV1 = None


class FaceRecognizer:
    """Face recognition pipeline backed by FaceNet embeddings."""

    def __init__(self, match_threshold: float = 0.65):
        """Initialize recognizer.

        Args:
            match_threshold: Cosine similarity threshold (0-1) for declaring a match.
        """
        self.match_threshold = float(min(max(match_threshold, 0.4), 0.9))
        self.reference_embedding: Optional[np.ndarray] = None
        self.reference_name = "Unknown"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.engine = 'template'

        # Load FaceNet if facenet-pytorch is available
        self.embedder = None
        if InceptionResnetV1 is not None:
            try:
                self.embedder = InceptionResnetV1(pretrained='vggface2').to(self.device).eval()
                self.engine = 'facenet'
                print("[FaceRecognizer] Using FaceNet embeddings (facenet-pytorch)")
            except Exception as e:
                print(f"[FaceRecognizer] Warning: Failed to load FaceNet model: {e}")
        else:
            print("[FaceRecognizer] facenet-pytorch not installed. Falling back to template matcher.")

        # Fallback template matcher state (ORB + histogram)
        self.template_threshold = 0.3
        self.reference_template: Optional[np.ndarray] = None
        self.reference_descriptors: Optional[np.ndarray] = None
        self.reference_histogram: Optional[np.ndarray] = None
        self.orb = cv2.ORB_create(nfeatures=500)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        # Initialize Haar detector
        try:
            model_file = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(model_file)
            print("[FaceRecognizer] Using OpenCV Haar Cascade for face detection")
        except Exception as e:
            print(f"[FaceRecognizer] Warning: Could not load face detector: {e}")
            self.face_cascade = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resize_if_needed(self, img: np.ndarray, max_dim: int = 900) -> np.ndarray:
        largest_dim = max(img.shape[:2])
        if largest_dim > max_dim:
            scale = max_dim / largest_dim
            new_size = (int(img.shape[1] * scale), int(img.shape[0] * scale))
            img = cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)
            print(f"[FaceRecognizer] Resized reference image to {new_size} for faster processing")
        return img

    def _extract_face_boxes(self, gray: np.ndarray) -> np.ndarray:
        return self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80)
        )

    def _prepare_face_rgb(self, frame_bgr: np.ndarray, box: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        x, y, w, h = box
        face = frame_bgr[y:y+h, x:x+w]
        if face.size == 0:
            return None
        face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        face_rgb = cv2.resize(face_rgb, (160, 160))
        return face_rgb

    def _preprocess_tensor(self, face_rgb: np.ndarray) -> torch.Tensor:
        # Convert to tensor in [-1, 1]
        tensor = torch.from_numpy(face_rgb.astype(np.float32) / 255.0)
        tensor = tensor.permute(2, 0, 1).unsqueeze(0)
        tensor = (tensor - 0.5) / 0.5
        return tensor.to(self.device)

    def _compute_embedding(self, face_rgb: np.ndarray) -> Optional[np.ndarray]:
        if self.embedder is None:
            return None
        tensor = self._preprocess_tensor(face_rgb)
        with torch.no_grad():
            embedding = self.embedder(tensor).cpu().numpy().flatten()
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None
        return embedding / norm

    def _compute_template_features(self, face_gray: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        keypoints, descriptors = self.orb.detectAndCompute(face_gray, None)
        hist = cv2.calcHist([face_gray], [0], None, [64], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        return descriptors, hist

    # ------------------------------------------------------------------
    # Reference upload
    # ------------------------------------------------------------------
    def upload_reference_face(self, image_data: bytes, name: str = "Target") -> bool:
        try:
            if self.face_cascade is None:
                print("[FaceRecognizer] Face detector not available")
                return False

            np_img = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
            if img is None:
                print("[FaceRecognizer] Failed to decode image")
                return False

            img = self._resize_if_needed(img)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self._extract_face_boxes(gray)
            if len(faces) == 0:
                print("[FaceRecognizer] No face detected in uploaded image")
                return False

            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            target_box = faces[0]
            face_rgb = self._prepare_face_rgb(img, target_box)
            if face_rgb is None:
                print("[FaceRecognizer] Unable to crop reference face")
                return False

            if self.engine == 'facenet' and self.embedder is not None:
                embedding = self._compute_embedding(face_rgb)
                if embedding is None:
                    print("[FaceRecognizer] Failed to compute embedding")
                    return False
                self.reference_embedding = embedding
                print(f"[FaceRecognizer] Stored FaceNet embedding for {name}")
            else:
                face_gray = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2GRAY)
                descriptors, hist = self._compute_template_features(face_gray)
                if descriptors is None or len(descriptors) < 12:
                    print("[FaceRecognizer] Not enough reference features detected")
                    return False
                self.reference_template = face_gray
                self.reference_descriptors = descriptors
                self.reference_histogram = hist
                print(f"[FaceRecognizer] Stored template features for {name}")

            self.reference_name = name
            return True

        except Exception as e:
            print(f"[FaceRecognizer] Error uploading reference face: {e}")
            return False

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _match_with_facenet(self, face_rgb: np.ndarray) -> Tuple[bool, float]:
        embedding = self._compute_embedding(face_rgb)
        if embedding is None or self.reference_embedding is None:
            return False, 0.0
        similarity = float(np.dot(self.reference_embedding, embedding))
        return similarity >= self.match_threshold, similarity

    def _match_with_template(self, face_rgb: np.ndarray) -> Tuple[bool, float]:
        face_gray = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2GRAY)
        descriptors, hist = self._compute_template_features(face_gray)
        match_ratio = 0.0
        hist_score = 0.0

        if descriptors is not None and self.reference_descriptors is not None:
            matches = self.matcher.match(descriptors, self.reference_descriptors)
            if matches:
                good_matches = [m for m in matches if m.distance < 70]
                match_ratio = len(good_matches) / max(len(self.reference_descriptors), 1)

        if hist is not None and self.reference_histogram is not None:
            hist_score = cv2.compareHist(hist.astype(np.float32), self.reference_histogram.astype(np.float32), cv2.HISTCMP_CORREL)
            hist_score = max(0.0, min(float(hist_score), 1.0))

        combined_score = (match_ratio * 0.7) + (hist_score * 0.3)
        return combined_score >= self.template_threshold, combined_score

    def detect_and_match(self, frame: np.ndarray) -> Tuple[np.ndarray, bool, int]:
        if frame is None or self.face_cascade is None:
            return frame if frame is not None else None, False, 0

        if not self.has_reference():
            return frame, False, 0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._extract_face_boxes(gray)
        annotated_frame = frame.copy()
        match_found = False
        num_faces = len(faces)

        for (x, y, w, h) in faces:
            face_rgb = self._prepare_face_rgb(frame, (x, y, w, h))
            if face_rgb is None:
                continue

            if self.engine == 'facenet' and self.reference_embedding is not None:
                is_match, score = self._match_with_facenet(face_rgb)
                confidence = max(0.0, min(99.9, ((score - self.match_threshold) / (1 - self.match_threshold + 1e-6)) * 100.0))
            else:
                is_match, score = self._match_with_template(face_rgb)
                confidence = min(99.9, (score / max(self.template_threshold, 1e-6)) * 100.0)

            if is_match:
                match_found = True
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
                label = f"{self.reference_name} ({confidence:.1f}%)"
                cv2.putText(annotated_frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(annotated_frame, "Unknown", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        return annotated_frame, match_found, num_faces

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def clear_reference(self):
        self.reference_embedding = None
        self.reference_template = None
        self.reference_descriptors = None
        self.reference_histogram = None
        self.reference_name = "Unknown"
        print("[FaceRecognizer] Reference face cleared")

    def has_reference(self) -> bool:
        if self.engine == 'facenet':
            return self.reference_embedding is not None
        return self.reference_template is not None

    def add_overlay(self, frame: np.ndarray, match_found: bool, num_faces: int) -> np.ndarray:
        if frame is None:
            return frame

        overlay_frame = frame.copy()
        if match_found:
            color = (0, 255, 0)
            status = f"✓ MATCH FOUND: {self.reference_name}"
        elif num_faces > 0:
            color = (0, 165, 255)
            status = f"Searching... ({num_faces} faces detected)"
        elif self.has_reference():
            color = (255, 200, 0)
            status = f"Searching for: {self.reference_name}"
        else:
            color = (128, 128, 128)
            status = "No reference face uploaded"

        cv2.rectangle(overlay_frame, (0, 0), (frame.shape[1], 50), color, -1)
        cv2.putText(overlay_frame, status, (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        return overlay_frame

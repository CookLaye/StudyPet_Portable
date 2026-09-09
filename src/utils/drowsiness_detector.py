"""
Drowsiness Detector Module
Detects drowsiness using a pre-trained model and camera input.
"""
import os
import cv2
import numpy as np
import tensorflow as tf
import threading
from typing import Tuple, Optional, Callable
from .camera import CameraHandler as CameraManager

class DrowsinessDetector:
    """Detects drowsiness using a pre-trained model and camera input."""
    
    def __init__(self, model_path: str, cascade_path: str = None, root_window=None):
        """Initialize the Drowsiness Detector.
        
        Args:
            model_path: Path to the drowsiness model file
            cascade_path: Path to the Haar Cascade classifier for face detection
            root_window: Optional Tkinter root window for thread-safe callbacks
        """
        self.model = self._load_model(model_path)
        self.input_size = (80, 80)  # Default input size for the model
        self.camera = CameraManager()
        self.is_detecting = False
        self.on_detection_callback = None
        self.root_window = root_window  # Store reference to root window for thread safety
        self._stop_event = threading.Event()
        
        # Load face and eye cascade classifiers
        if cascade_path is None:
            cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml')
        
        # Drowsiness detection parameters
        self.eye_closed_frames = 0
        self.EYE_AR_THRESH = 0.25  # Eye aspect ratio threshold
        self.EYE_AR_CONSEC_FRAMES = 10  # Number of consecutive frames for drowsiness
        self.COUNTER = 0
        self.ALARM_ON = False
        
    def _load_model(self, model_path: str) -> tf.keras.Model:
        """Load the pre-trained drowsiness detection model."""
        try:
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found: {model_path}")
                
            model = tf.keras.models.load_model(model_path, compile=False)
            
            # Update input size based on model
            if hasattr(model, 'input_shape') and model.input_shape[1:3] != (None, None):
                self.input_size = model.input_shape[1:3]
                
            return model
            
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess the image for the model."""
        if image is None or image.size == 0:
            return None
            
        # Resize and normalize the image
        image = cv2.resize(image, self.input_size)
        image = image.astype('float32') / 255.0
        
        # Add batch dimension if needed
        if len(image.shape) == 3:
            image = np.expand_dims(image, axis=0)
            
        return image
    
    def detect_face(self, frame: np.ndarray) -> list:
        """Detect faces in the frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return self.face_cascade.detectMultiScale(gray, 1.3, 5)
    
    def detect_eyes(self, face_roi: np.ndarray) -> list:
        """Detect eyes in the face region."""
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        return self.eye_cascade.detectMultiScale(gray_face)
    
    def predict_drowsiness(self, frame: np.ndarray) -> Tuple[bool, float, float]:
        """Predict drowsiness from the frame.
        
        Returns:
            tuple: (is_drowsy, drowsy_confidence, awake_confidence)
            - is_drowsy (bool): True if drowsy, False if awake
            - drowsy_confidence (float): Confidence score for drowsy class (0-1)
            - awake_confidence (float): Confidence score for awake class (0-1)
        """
        try:
            # Preprocess the frame
            processed_frame = self.preprocess_image(frame)
            if processed_frame is None:
                return False, 0.0, 0.0
            
            # Make prediction
            prediction = self.model.predict(processed_frame, verbose=0)[0]
            
            # Get the probabilities for both classes
            awake_prob = float(prediction[1]) if len(prediction) > 1 else 1.0 - float(prediction[0])
            drowsy_prob = float(prediction[0]) if len(prediction) > 1 else float(prediction[0])
            
            # Ensure probabilities sum to ~1.0
            total = awake_prob + drowsy_prob
            if total > 0:
                awake_prob /= total
                drowsy_prob /= total
            
            # Determine the predicted class (drowsy if probability > 0.5)
            is_drowsy = drowsy_prob > 0.5
            
            return is_drowsy, drowsy_prob, awake_prob
            
        except Exception as e:
            print(f"Error in prediction: {e}")
            return False, 0.0, 0.0
    
    def draw_detection(self, frame: np.ndarray, face: tuple, is_drowsy: bool, 
                      drowsy_confidence: float, awake_confidence: float) -> np.ndarray:
        """Draw detection results on the frame."""
        x, y, w, h = face
        
        # Draw face rectangle
        color = (0, 0, 255) if is_drowsy else (0, 255, 0)
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
        
        # Add status text
        status = "DROWSY" if is_drowsy else "AWAKE"
        text_color = (0, 0, 255) if is_drowsy else (0, 255, 0)
        cv2.putText(frame, f"Status: {status}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
        
        # Add confidence scores
        cv2.putText(frame, f"Drowsy: {drowsy_confidence:.2f}", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
        cv2.putText(frame, f"Awake: {awake_confidence:.2f}", (10, 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 1)
        
        # Add alarm if drowsy
        if is_drowsy:
            cv2.putText(frame, "ALERT! DROWSINESS DETECTED!", (10, 130),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return frame
    
    def _process_frame(self, frame: np.ndarray) -> None:
        """Process a single frame for drowsiness detection."""
        if frame is None or not self.is_detecting:
            return
            
        try:
            # Create a copy for display
            display_frame = frame.copy()
            
            # Detect faces
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            for (x, y, w, h) in faces:
                # Extract face ROI
                face_roi = frame[y:y+h, x:x+w]
                
                # Predict drowsiness
                is_drowsy, drowsy_conf, awake_conf = self.predict_drowsiness(face_roi)
                
                # Update UI in a thread-safe way if we have a callback
                if self.on_detection_callback:
                    if self.root_window:
                        # Schedule the callback to run in the main thread
                        self.root_window.after(0, lambda: self.on_detection_callback({
                            'is_drowsy': is_drowsy,
                            'drowsy_confidence': drowsy_conf,
                            'awake_confidence': awake_conf,
                            'frame': display_frame
                        }))
                    else:
                        # No root window, call directly (not thread-safe)
                        self.on_detection_callback({
                            'is_drowsy': is_drowsy,
                            'drowsy_confidence': drowsy_conf,
                            'awake_confidence': awake_conf,
                            'frame': display_frame
                        })
                
        except Exception as e:
            print(f"Error processing frame: {e}")
    
    def start_detection(self, callback: Optional[Callable] = None) -> bool:
        """Start the drowsiness detection.
        
        Args:
            callback: Optional callback function that receives detection results
            
        Returns:
            bool: True if detection started successfully, False otherwise
        """
        if self.is_detecting:
            print("Detection already running")
            return False
            
        self.on_detection_callback = callback
        self._stop_event.clear()
        self.is_detecting = True
        
        # Initialize camera with frame callback
        self.camera.initialize(callback=self._process_frame)
        return True
    
    def stop_detection(self) -> None:
        """Stop the drowsiness detection."""
        self.is_detecting = False
        self._stop_event.set()
        self.camera.release()
    
    def __del__(self):
        """Ensure resources are released when the object is destroyed."""
        self.stop_detection()


def test_detector():
    """Test function for the DrowsinessDetector."""
    # Get the absolute path to the model
    model_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'models', 'drowsiness_model.keras'
    ))
    
    if not os.path.exists(model_path):
        print(f"Error: Model file not found at {model_path}")
        return
    
    # Create and start the detector
    detector = DrowsinessDetector(model_path)
    detector.start_detection()


if __name__ == "__main__":
    test_detector()

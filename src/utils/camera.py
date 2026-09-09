"""
Camera Module
Handles camera input and frame processing.
"""
import cv2
import numpy as np
from typing import Tuple, Optional, Callable

class CameraHandler:
    """Handles camera input and frame processing."""
    
    def __init__(self, camera_index: int = 0, frame_width: int = 640, frame_height: int = 480):
        """Initialize the camera handler.
        
        Args:
            camera_index: Index of the camera to use (default: 0)
            frame_width: Desired frame width
            frame_height: Desired frame height
        """
        self.camera_index = camera_index
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.cap = None
        self.is_running = False
    
    def start(self) -> bool:
        """Start the camera capture.
        
        Returns:
            bool: True if camera started successfully, False otherwise
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                raise RuntimeError("Could not open camera")
                
            # Set frame dimensions
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.is_running = True
            return True
            
        except Exception as e:
            print(f"Error starting camera: {e}")
            self.stop()
            return False
    
    def stop(self) -> None:
        """Stop the camera capture and release resources."""
        if self.cap is not None:
            self.cap.release()
        self.is_running = False
    
    def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Get the next frame from the camera.
        
        Returns:
            tuple: (success, frame) where success is a boolean indicating 
                  if the frame was captured successfully, and frame is the 
                  captured image (or None if capture failed)
        """
        if not self.is_running or self.cap is None:
            return False, None
            
        ret, frame = self.cap.read()
        if not ret:
            return False, None
            
        return True, frame
    
    def process_frame(self, frame: np.ndarray, callback: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
        """Process a frame using the provided callback function.
        
        Args:
            frame: Input frame to process
            callback: Function that takes a frame and returns a processed frame
            
        Returns:
            Processed frame
        """
        if frame is None:
            return None
        return callback(frame)
    
    def release(self) -> None:
        """Release camera resources."""
        self.stop()
        cv2.destroyAllWindows()


def test_camera():
    """Test function for the camera module."""
    camera = CameraHandler()
    
    try:
        if not camera.start():
            print("Failed to start camera")
            return
            
        print("Camera started. Press 'q' to quit.")
        
        while True:
            ret, frame = camera.get_frame()
            if not ret:
                print("Failed to capture frame")
                break
                
            # Display the frame
            cv2.imshow('Camera Test', frame)
            
            # Break the loop on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nStopping camera...")
    finally:
        camera.release()
        print("Camera released.")


if __name__ == "__main__":
    test_camera()

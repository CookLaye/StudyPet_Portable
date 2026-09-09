"""Centralized state management for pet display updates."""
import threading
from typing import Callable
from enum import Enum

class PetStateChange(Enum):
    STAGE = "stage"
    EMOTION = "emotion"
    TYPE = "type"
    ALL = "all"

class StateManager:
    _instance = None
    _callbacks = []
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        with self._lock:
            if not self._initialized:
                self._initialized = True

    @classmethod
    def subscribe(cls, callback: Callable[[PetStateChange], None]) -> None:
        """Subscribe to state change notifications."""
        with cls._lock:
            if callback not in cls._callbacks:
                cls._callbacks.append(callback)

    @classmethod
    def unsubscribe(cls, callback: Callable[[PetStateChange], None]) -> None:
        """Unsubscribe from state change notifications."""
        with cls._lock:
            if callback in cls._callbacks:
                cls._callbacks.remove(callback)

    @classmethod
    def notify_state_change(cls, change_type: PetStateChange) -> None:
        """Notify all subscribers of a state change."""
        with cls._lock:
            callbacks_copy = cls._callbacks[:]

        for callback in callbacks_copy:  # Iterate outside lock to prevent deadlocks
            try:
                callback(change_type)
            except Exception as e:
                print(f"Error in state change callback: {e}")

# Global instance for easy access
state_manager = StateManager()

"""
Application State - Manages user data, settings, and game state
"""

import os
import threading
from typing import Dict, Optional, Any, TypeVar, Type
from datetime import timedelta
from src.utils.file_utils import atomic_write, atomic_read, backup_file
from .pet import Pet, PetType, PetStage, PetEmotion
from .user import User
from .state_manager import state_manager, PetStateChange

T = TypeVar('T', bound='AppState')

class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass

class AppState:
    """Manages the application state including user data and settings."""

    def __init__(self):
        self._lock = threading.RLock()

        self.username = "Player"
        self.pet_name = ""
        self.pet_type = None
        self._pet_stage = 1
        self._affection = 0
        self._emotion = PetEmotion.HAPPY
        self.total_study_time = 0
        self.last_day_visited = None
        self.current_streak = 0
        self.longest_streak = 0
        self.on_evolve = None
        self.last_saved_at = None
        self.tasks = []



        self.save_file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'user_data', 'save_data.json'
        ))

        # Per-run counters (in-memory only)
        self.run_total_study_time = 0

        # Runtime study session state (not persisted)
        self.study_session = {
            'active': False,
            'type': None,
            'schedule': None,
            'current_block': 0,
            'block_type': None,
            'block_duration': 0,
            'block_start_time': None,
            'start_time': None,
            'paused': False,
            'last_activity': None,
            'completed_blocks': [],
            'total_study_time': 0,
            'session_paused': False
        }

        self.current_pet: Optional[Pet] = None
        self.user: Optional[User] = None
        self.settings = {}

        # Load existing data if available
        self.load_data()

    @property
    def affection_cap(self) -> int:
        """Get the current affection cap based on the pet's stage."""
        with self._lock:
            return 1000 if self.stage == PetStage.BATTLE_FIT else 200

    @property
    def affection_percentage(self) -> float:
        """Get the current affection as a percentage of the current cap."""
        with self._lock:
            return (self._affection / self.affection_cap) * 100 if self.affection_cap > 0 else 0

    @property
    def stage(self) -> PetStage:
        with self._lock:
            return PetStage(self._pet_stage)

    @stage.setter
    def stage(self, value):
        with self._lock:
            if isinstance(value, int):
                value = PetStage(value)

            old_stage = PetStage(self._pet_stage)
            if old_stage == value:
                return

            self._pet_stage = value.value
            self._affection = 0
            self._update_emotion()

            state_manager.notify_state_change(PetStateChange.STAGE)
            self.save_data()

    @property
    def emotion(self) -> PetEmotion:
        with self._lock:
            return self._emotion

    @emotion.setter
    def emotion(self, value):
        with self._lock:
            if isinstance(value, str):
                try:
                    self._emotion = PetEmotion(value.lower())
                except ValueError:
                    self._emotion = PetEmotion.HAPPY
            elif isinstance(value, PetEmotion):
                self._emotion = value
            else:
                self._emotion = PetEmotion.HAPPY

            state_manager.notify_state_change(PetStateChange.EMOTION)

    @property
    def affection(self) -> int:
        with self._lock:
            return self._affection

    @affection.setter
    def affection(self, value: int):
        with self._lock:
            old_value = self._affection
            self._affection = max(0, min(value, self.affection_cap))

            if self._affection != old_value:
                self._update_emotion_from_affection()
                state_manager.notify_state_change(PetStateChange.AFFECTION if hasattr(PetStateChange, 'AFFECTION') else PetStateChange.ALL)

                if abs(self._affection - old_value) >= 10:
                    self.save_data()

                if self._affection >= self.affection_cap:
                    self._check_evolution()

    def _update_emotion(self):
        """Update pet's emotion based on affection percentage."""
        # MUST be called under lock
        percentage = self.affection_percentage
        if percentage < 20:
            self._emotion = PetEmotion.SAD
        elif percentage < 40:
            self._emotion = PetEmotion.WORRIED
        elif percentage < 60:
            self._emotion = PetEmotion.HUNGRY
        elif percentage < 80:
            self._emotion = PetEmotion.HAPPY
        else:
            self._emotion = PetEmotion.ANGRY
        state_manager.notify_state_change(PetStateChange.EMOTION)

    def _update_emotion_from_affection(self):
        """Update emotion based on current affection percentage."""
        self._update_emotion()

    def _check_evolution(self) -> bool:
        """Check if pet should evolve to the next stage."""
        # MUST be called under lock
        if self.stage == PetStage.BATTLE_FIT:
            return False

        if self._affection >= self.affection_cap:
            current_stage = self.stage
            if current_stage == PetStage.GROWN:
                new_stage = PetStage.BATTLE_FIT
            else:
                new_stage = PetStage(current_stage.value + 1)

            old_stage = self.stage
            self.stage = new_stage
            self._affection = 0
            self.save_data()

            if self.on_evolve:
                try:
                    self.on_evolve(old_stage, new_stage)
                except Exception as e:
                    print(f"Error in evolution callback: {e}")

            return True
        return False

    def is_first_time_user(self) -> bool:
        with self._lock:
            return self.pet_type is None

    def set_selected_pet(self, pet_type: PetType, name: str = ""):
        with self._lock:
            self.pet_type = pet_type
            self.pet_name = name or "Axos"
            self.stage = PetStage.EGG
            self.affection = 0

            self.current_pet = Pet(pet_type, self.pet_name)
            if self.user is None:
                self.user = User(self.username)

            self.save_data()

    def set_last_day_visited(self, date_str: Optional[str], persist: bool = False) -> None:
        with self._lock:
            self.last_day_visited = date_str
            if persist:
                self.save_data()

    def set_pet_state(self, pet_stage: int, affection: int, persist: bool = False) -> None:
        """Updates the persisted pet state values."""
        # These properties handle lock and notify
        self.stage = PetStage(pet_stage)
        self.affection = affection
        if persist:
            self.save_data()

    def flush_run_study_time(self) -> int:
        with self._lock:
            flushed = int(self.run_total_study_time or 0)
            if flushed <= 0:
                return 0

            self.run_total_study_time = 0
            self.save_data()
            return flushed

    def get_current_pet(self) -> Optional[Pet]:
        with self._lock:
            return self.current_pet

    def get_user(self) -> Optional[User]:
        with self._lock:
            return self.user

    def add_affection_to_pet(self, amount: int) -> bool:
        """
        Deprecated: Use PetState.affection setter instead.
        This method is kept for legacy API compatibility but now simply warns.
        """
        print("Warning: add_affection_to_pet is deprecated. Use global_pet_state.affection instead.")
        return False

    def _serialize_for_save(self) -> Dict[str, Any]:
        with self._lock:
            from datetime import datetime
            data = {
                'version': '2.0',
                'username': self.username,
                'pet_name': self.pet_name,
                'pet_type': self.pet_type.value if self.pet_type else None,
                'pet_stage': self.stage.value,
                'affection': self.affection,
                'total_study_time': self.total_study_time,
                'last_day_visited': self.last_day_visited,
                'current_streak': self.current_streak,
                'longest_streak': self.longest_streak,
                'last_saved_at': datetime.now().isoformat(),
                'tasks': self.tasks,
                'settings': self.settings
            }



        def make_serializable(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            if isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [make_serializable(x) for x in obj]
            return str(obj)

        return make_serializable(data)

    def update_user_stats(self, study_time: int, questions_answered: int, persist: bool = False):
        with self._lock:
            study_time = int(study_time or 0)
            self.run_total_study_time += study_time
            self.total_study_time += study_time

            from datetime import datetime
            today = datetime.now().strftime("%m/%d/%Y")

            if self.last_day_visited != today:
                yesterday = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) -
                           timedelta(days=1)).strftime("%m/%d/%Y")

                if self.last_day_visited == yesterday:
                    self.current_streak += 1
                else:
                    self.current_streak = 1

                self.last_day_visited = today
                self.longest_streak = max(self.longest_streak, self.current_streak)

            if self.user:
                self.user.add_study_time(study_time)
                self.user.add_questions_answered(questions_answered)

            if persist:
                self.save_data()

    def get_setting(self, key: str, default=None):
        with self._lock:
            return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        with self._lock:
            self.settings[key] = value
            self.save_data()

    @classmethod
    def get_save_dir(cls) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'user_data')

    @classmethod
    def get_save_path(cls) -> str:
        return os.path.join(cls.get_save_dir(), 'save_data.json')

    def validate_data(self, data: Dict[str, Any]) -> bool:
        try:
            if not isinstance(data, dict):
                return False
            if 'version' not in data:
                return False
            if data['version'] == '2.0':
                required_fields = ['username', 'pet_type', 'pet_stage', 'affection',
                                     'total_study_time', 'current_streak', 'longest_streak']
                return all(field in data for field in required_fields)
            elif data['version'] in ['1.0', '1.5']:
                required_fields = ['user', 'settings', 'pet', 'pet_state']
                return all(field in data for field in required_fields)
            return True
        except Exception:
            return False

    def save_data(self, force_backup: bool = False) -> bool:
        with self._lock:
            try:
                serialized_data = self._serialize_for_save()
                os.makedirs(os.path.dirname(self.save_file_path), exist_ok=True)

                if force_backup:
                    backup_file(self.save_file_path)

                return atomic_write(self.save_file_path, serialized_data)
            except Exception as e:
                print(f"Error saving data: {e}")
                import traceback
                traceback.print_exc()
                return False

    @classmethod
    def load_or_create(cls: Type[T]) -> T:
        instance = cls()
        instance.load_data()
        return instance

    def load_data(self) -> bool:
        with self._lock:
            # 1. Crash Detection: Check for runtime backup
            from src.utils.file_utils import read_runtime_backup, delete_runtime_backup, atomic_read
            runtime_data = read_runtime_backup(self.save_file_path)

            # Try primary save file
            if os.path.exists(self.save_file_path):
                data = atomic_read(self.save_file_path)
                if data and self.validate_data(data):
                    # If runtime backup exists, compare timestamps to see if a crash happened
                    if runtime_data and self.validate_data(runtime_data):
                        main_time = data.get('last_saved_at')
                        runtime_time = runtime_data.get('last_saved_at')

                        # If runtime backup is newer than main save, it means the app crashed
                        # before the final save on close.
                        if runtime_time and main_time and runtime_time > main_time:
                            print("⚠️ Unsaved progress detected from previous session crash.")
                            # We'll prioritize the runtime backup if it's newer
                            data = runtime_data

                    if self._apply_data(data):
                        return True

            # 2. Recovery: If main save failed or was missing, try runtime backup
            if runtime_data and self.validate_data(runtime_data):
                print("♻️ Restoring from runtime backup after failure/crash...")
                if self._apply_data(runtime_data):
                    return True

            # Fallback to timestamped backups
            backup_dir = os.path.join(os.path.dirname(self.save_file_path), 'backups')
            if os.path.exists(backup_dir):
                backups = sorted(
                    [f for f in os.listdir(backup_dir) if f.endswith('_save_data.json')],
                    reverse=True
                )
                for backup_file_name in backups:
                    backup_path = os.path.join(backup_dir, backup_file_name)
                    data = atomic_read(backup_path)
                    if data and self.validate_data(data):
                        if self._apply_data(data):
                            return True

            return False

    def start_session(self):
        """Create a runtime backup to mark the start of a session."""
        with self._lock:
            from src.utils.file_utils import write_runtime_backup
            try:
                data = self._serialize_for_save()
                write_runtime_backup(self.save_file_path, data)
            except Exception as e:
                print(f"Warning: Could not create runtime backup: {e}")

    def end_session(self):
        """Delete the runtime backup to mark a normal closure."""
        with self._lock:
            from src.utils.file_utils import delete_runtime_backup
            try:
                delete_runtime_backup(self.save_file_path)
            except Exception as e:
                print(f"Warning: Could not clear runtime backup: {e}")


    def _apply_data(self, data: Dict[str, Any]) -> bool:
        try:
            version = data.get('version', '1.0')
            if version == '2.0':
                self.username = data.get('username', 'Player')
                self.pet_name = data.get('pet_name', '')
                pet_type_str = data.get('pet_type')
                self.pet_type = PetType(pet_type_str) if pet_type_str else None
                self.stage = PetStage(data.get('pet_stage', 1))
                self.affection = data.get('affection', 0)
                self.total_study_time = data.get('total_study_time', 0)
                self.last_day_visited = data.get('last_day_visited')
                self.current_streak = data.get('current_streak', 0)
                self.longest_streak = data.get('longest_streak', 0)
                self.last_saved_at = data.get('last_saved_at')
                self.tasks = data.get('tasks', [])
                self.settings = data.get('settings', {})
            elif version in ['1.0', '1.5']:
                self._migrate_from_legacy_format(data)

            self._create_legacy_objects()
            return True
        except Exception as e:
            print(f"Error applying data: {e}")
            return False

    def _migrate_from_legacy_format(self, data: Dict[str, Any]) -> None:
        try:
            user_data = data.get('user', {})
            self.username = user_data.get('username', 'Player')
            self.total_study_time = user_data.get('total_study_time', 0)
            streak_days = user_data.get('streak_days', 0)
            self.current_streak = streak_days
            self.longest_streak = streak_days

            pet_data = data.get('pet', {})
            if pet_data:
                self.pet_name = pet_data.get('name', '')
                pet_type_str = pet_data.get('pet_type')
                if pet_type_str:
                    try:
                        self.pet_type = PetType(pet_type_str)
                    except (ValueError, TypeError):
                        self.pet_type = PetType.PENGUIN

            pet_state = data.get('pet_state', {})
            self.stage = PetStage(pet_state.get('stage', 1))
            self.affection = pet_state.get('affection', 0)

            last_study_date = user_data.get('last_study_date')
            if last_study_date:
                try:
                    from datetime import datetime
                    if isinstance(last_study_date, str):
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S']:
                            try:
                                dt = datetime.strptime(last_study_date, fmt)
                                self.last_day_visited = dt.strftime('%m/%d/%Y')
                                break
                            except ValueError:
                                continue
                except Exception:
                    pass
        except Exception as e:
            print(f"Error during legacy migration: {e}")
            self.username = 'Player'
            self.pet_name = ''
            self.pet_type = None
            self.total_study_time = 0
            self.last_day_visited = None
            self.current_streak = 0
            self.longest_streak = 0

    def _create_legacy_objects(self) -> None:
        try:
            if self.user is None:
                self.user = User(self.username)
                self.user.total_study_time = self.total_study_time
                self.user.streak_days = self.current_streak

            if self.current_pet is None and self.pet_type:
                self.current_pet = Pet(self.pet_type, self.pet_name)
                self.current_pet.stage = PetStage(self.stage)
                self.current_pet.affection = self.affection
        except Exception as e:
            print(f"Error creating legacy objects: {e}")

    def reset_data(self):
        with self._lock:
            import shutil
            import time
            from pathlib import Path

            def safe_delete(path):
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        if os.path.exists(path):
                            if os.path.isfile(path) or os.path.islink(path):
                                os.unlink(path)
                            else:
                                shutil.rmtree(path)
                        return True
                    except (OSError, PermissionError) as e:
                        if attempt == max_retries - 1:
                            print(f"Failed to delete {path}: {e}")
                            return False
                        time.sleep(0.1 * (attempt + 1))
                return False

            try:
                self.username = "Player"
                self.pet_name = ""
                self.pet_type = None
                self.stage = PetStage.EGG
                self.affection = 0
                self.total_study_time = 0
                self.last_day_visited = None
                self.current_streak = 0
                self.longest_streak = 0
                self.current_pet = None
                self.user = None
                self.settings = {}

                self.study_session = {
                    'active': False, 'type': None, 'schedule': None, 'current_block': 0,
                    'block_type': None, 'block_duration': 0, 'block_start_time': None,
                    'start_time': None, 'paused': False, 'last_activity': None,
                    'completed_blocks': [], 'total_study_time': 0, 'session_paused': False
                }

                user_data_dir = os.path.dirname(self.save_file_path)
                if os.path.exists(user_data_dir):
                    for item in os.listdir(user_data_dir):
                        item_path = os.path.join(user_data_dir, item)
                        safe_delete(item_path)
                    os.makedirs(user_data_dir, exist_ok=True)
                    self.save_data()

                import gc
                gc.collect()
                return True
            except Exception as e:
                print(f"Critical error during reset_data: {e}")
                return False

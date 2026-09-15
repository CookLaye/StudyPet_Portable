"""
Session Manager - Manages study sessions with scheduled blocks

This module handles the creation, execution, and tracking of study sessions
with alternating study and break blocks.

Author: CookLaye
Version: 1.0
"""

import time
from datetime import datetime
from typing import Optional, Callable

# Constants
DEFAULT_COUNTDOWN_SECONDS = 300  # 5 minutes for block confirmation
BLOCK_TICK_INTERVAL = 1000  # Update interval in milliseconds


class SessionManager:
    """
    Manages study sessions with scheduled blocks.
    
    Handles session lifecycle including:
    - Starting and stopping sessions
    - Managing study/break blocks
    - Tracking user data and statistics
    - UI updates and callbacks
    
    Attributes:
        app_state: Global application state manager
        user_data_path: Path to user data file
        ui_callback: Optional callback for UI updates
        countdown_seconds: Time to confirm next block (default: 300s)
    """
    
    def __init__(self, app_state, user_data_path: str):
        """
        Initialize the session manager.
        
        Args:
            app_state: Global application state manager
            user_data_path: Path to store user session data
        """
        self.app_state = app_state
        self.user_data_path = user_data_path
        self.ui_callback: Optional[Callable] = None
        self.countdown_seconds = DEFAULT_COUNTDOWN_SECONDS
        
        # Timer tracking
        self._block_after_id: Optional[str] = None
        self._countdown_after_id: Optional[str] = None
        self._countdown_start: Optional[float] = None
        
        # Load existing user data
        self._load_user_data()
    
    def set_ui_callback(self, callback: Callable[[str, bool], None]) -> None:
        """
        Set the UI callback for session updates.
        
        Args:
            callback: Function that receives (status_text, show_continue) parameters
        """
        self.ui_callback = callback

    def _load_user_data(self) -> None:
        """
        Load user data from AppState with proper error handling.
        
        Initializes default values if no data exists.
        """
        try:
            # Load data from AppState instead of separate file
            if hasattr(self.app_state, 'total_study_time'):
                self.user_data = {
                    'study_time': self.app_state.total_study_time,
                    'sessions': [],
                    'total_sessions': 0,
                    'total_study_minutes': self.app_state.total_study_time // 60,
                    'last_session_date': self.app_state.last_day_visited
                }
            else:
                self.user_data = {}
        except Exception as e:
            print(f"Warning: Failed to load user data from AppState, using defaults: {e}")
            self.user_data = {}
        
        # Ensure required fields exist
        self._ensure_default_fields()
    
    def _ensure_default_fields(self) -> None:
        """
        Ensure all required user data fields exist with default values.
        """
        defaults = {
            'study_time': 0,
            'sessions': [],
            'total_sessions': 0,
            'total_study_minutes': 0,
            'last_session_date': None
        }
        
        for field, default_value in defaults.items():
            if field not in self.user_data:
                self.user_data[field] = default_value
    
    def save_user_data(self) -> bool:
        """
        Save user data to file.
        """
        try:
            # Update AppState with session data
            if 'study_time' in self.user_data:
                desired_total = int(self.user_data.get('study_time', 0) or 0)
                current_total = int(getattr(self.app_state, 'total_study_time', 0) or 0)
                delta = max(0, desired_total - current_total)
                if delta:
                    self.app_state.update_user_stats(delta, 0, persist=False)
            
            if 'last_session_date' in self.user_data:
                last_date = self.user_data['last_session_date']
                if hasattr(self.app_state, 'set_last_day_visited'):
                    self.app_state.set_last_day_visited(last_date, persist=False)
                else:
                    try:
                        self.app_state.last_day_visited = last_date
                    finally:
                        if hasattr(self.app_state, 'write_runtime_backup'):
                            self.app_state.write_runtime_backup()
            
            return True
            
        except Exception as e:
            print(f"Error saving user data to AppState: {e}")
            return False

    def start_session(self) -> bool:
        """
        Start a new study session.
        
        Returns:
            bool: True if session started successfully, False otherwise
        """
        if not self.app_state.study_session.get('schedule'):
            print("Error: No schedule found for session")
            return False
        
        session = self.app_state.study_session
        session.update({
            'active': True,
            'start_time': time.time(),
            'last_activity': time.time(),
            'current_block': 0,
            'completed_blocks': [],
            'total_study_time': 0,
            'session_paused': False
        })
        
        self._start_block()
        return True
    
    def _start_block(self) -> None:
        """
        Start the current block in the session.
        
        Handles both study and break blocks.
        """
        session = self.app_state.study_session
        
        # Check if session is complete
        if session['current_block'] >= len(session['schedule']['blocks']):
            self._complete_session()
            return
        
        # Get current block info
        block = session['schedule']['blocks'][session['current_block']]
        session.update({
            'block_start_time': time.time(),
            'block_type': block['type'],
            'block_duration': int(block['duration']) * 60  # Convert to seconds
        })
        
        # Cancel any existing timers
        self._cancel_after(self._countdown_after_id)
        self._countdown_after_id = None
        
        # Start block timer
        self._schedule_block_tick()
        
        # Update UI
        if self.ui_callback:
            block_type = "Study" if block['type'] == 'study' else "Break"
            status = (
                f"Current: {block_type} Block\n"
                f"Duration: {block['duration']} minutes\n"
                f"Block {session['current_block'] + 1} of {len(session['schedule']['blocks'])}"
            )
            self.ui_callback(status, show_continue=False)
    
    def _schedule_block_tick(self) -> None:
        """
        Schedule the next block update tick.
        """
        self._cancel_after(self._block_after_id)
        self._block_after_id = self.app_state.root.after(BLOCK_TICK_INTERVAL, self._update_block)
    
    def _cancel_after(self, after_id: Optional[str]) -> None:
        """
        Cancel a scheduled after callback.
        
        Args:
            after_id: The ID of the scheduled callback to cancel
        """
        if after_id and hasattr(self.app_state.root, 'after_cancel'):
            try:
                self.app_state.root.after_cancel(after_id)
            except Exception as e:
                print(f"Warning: Failed to cancel timer: {e}")

    def _update_block(self) -> None:
        """
        Update the current block timer and UI.
        
        Called every second to update the remaining time.
        """
        session = self.app_state.study_session
        
        # Skip if session is not active or is paused
        if not session.get('active') or session.get('session_paused'):
            self._schedule_block_tick()
            return
        
        # Calculate remaining time
        elapsed = int(time.time() - session.get('block_start_time', time.time()))
        remaining = max(0, int(session.get('block_duration', 0)) - elapsed)
        
        # Check if block is complete
        if remaining <= 0:
            self.complete_block()
            return
        
        # Update UI with remaining time
        minutes, seconds = divmod(remaining, 60)
        block_type = "Study" if session.get('block_type') == 'study' else "Break"
        
        if self.ui_callback:
            self.ui_callback(f"{block_type}: {minutes:02d}:{seconds:02d} remaining", show_continue=False)
        
        # Schedule next update
        self._schedule_block_tick()
    
    def complete_block(self) -> bool:
        """
        Complete the current block and handle transition to the next state.

        Returns:
            bool: True if block completed successfully and session continues, False if session ended
        """
        session = self.app_state.study_session

        # Cancel current block timer
        self._cancel_after(self._block_after_id)
        self._block_after_id = None

        # Check if session is complete
        if session['current_block'] >= len(session['schedule']['blocks']):
            self._complete_session()
            return False

        # Get block info
        block = session['schedule']['blocks'][session['current_block']]
        duration_sec = int(time.time() - session.get('block_start_time', time.time()))

        # Update study time for study blocks
        if block['type'] == 'study':
            study_time_added = max(0, duration_sec)
            self.user_data['study_time'] = int(self.user_data.get('study_time', 0)) + study_time_added
            session['total_study_time'] = int(session.get('total_study_time', 0)) + study_time_added

            # Also update app_state stats for real-time tracking
            self.app_state.update_user_stats(study_time_added, 0)

        # Record completed block
        session['completed_blocks'].append({
            'type': block['type'],
            'scheduled_duration': block['duration'],
            'actual_duration_sec': duration_sec,
            'completed_at': datetime.now().isoformat()
        })

        # Move to next block
        session['current_block'] += 1

        # Determine transition based on the block that just finished
        if block['type'] == 'study':
            # If next block is break, start it immediately
            if session['current_block'] < len(session['schedule']['blocks']) and \
               session['schedule']['blocks'][session['current_block']]['type'] == 'break':
                self._start_block()
                return True
        elif block['type'] == 'break':
            # Break ends -> Back to selection state immediately
            self._complete_session()
            return False

        # Default: start countdown for next block (e.g. study -> study)
        self._start_countdown()
        return True
    
    def _start_countdown(self) -> None:
        """
        Start countdown for user to confirm next block.
        
        Gives user time to prepare for the next block.
        """
        session = self.app_state.study_session
        
        # Check if session is complete
        if session['current_block'] >= len(session['schedule']['blocks']):
            self._complete_session()
            return
        
        self._countdown_start = time.time()
        self._schedule_countdown_tick()
    
    def _schedule_countdown_tick(self) -> None:
        """
        Schedule the next countdown update tick.
        """
        self._cancel_after(self._countdown_after_id)
        self._countdown_after_id = self.app_state.root.after(BLOCK_TICK_INTERVAL, self._update_countdown)

    def _update_countdown(self) -> None:
        """
        Update the countdown timer for the next block.
        
        Shows time remaining until the next block starts.
        """
        session = self.app_state.study_session
        
        if not session.get('active'):
            return
        
        # Calculate remaining countdown time
        elapsed = int(time.time() - (self._countdown_start or time.time()))
        remaining = max(0, self.countdown_seconds - elapsed)
        
        # Get next block info
        next_block = session['schedule']['blocks'][session['current_block']]
        block_type = "Study" if next_block['type'] == 'study' else "Break"
        
        # Check if countdown expired
        if remaining <= 0:
            self.end_session()
            return
        
        # Update UI with countdown
        minutes, seconds = divmod(remaining, 60)
        if self.ui_callback:
            status = (
                f"Next {block_type} block in: {minutes:02d}:{seconds:02d}\n"
                f"Duration: {next_block['duration']} minutes"
            )
            self.ui_callback(status, show_continue=True)
        
        # Schedule next update
        self._schedule_countdown_tick()
    
    def confirm_next_block(self) -> bool:
        """
        Confirm and start the next block in the session.
        
        Returns:
            bool: True if next block started successfully, False if session ended
        """
        # Cancel countdown
        self._cancel_after(self._countdown_after_id)
        self._countdown_after_id = None
        
        session = self.app_state.study_session
        
        # Check if session is complete
        if session['current_block'] >= len(session['schedule']['blocks']):
            self._complete_session()
            return False
        
        # Start next block
        self._start_block()
        return True
    
    def end_session(self) -> bool:
        """
        End the current study session.
        
        Returns:
            bool: True if session ended successfully
        """
        return self._complete_session()
    
    def _complete_session(self) -> bool:
        """
        Complete the current session and save data.
        
        Returns:
            bool: True if session completed successfully
        """
        session = self.app_state.study_session
        
        # Cancel all timers
        self._cancel_after(self._block_after_id)
        self._cancel_after(self._countdown_after_id)
        self._block_after_id = None
        self._countdown_after_id = None
        
        # Save session data if it was active
        if session.get('active'):
            study_time_sec = int(session.get('total_study_time', 0))
            
            # Create session record
            session_data = {
                'start_time': datetime.fromtimestamp(session.get('start_time') or time.time()).isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_study_time_sec': study_time_sec,
                'blocks_completed': len(session.get('completed_blocks', [])),
                'schedule_name': (session.get('schedule') or {}).get('name', 'Custom')
            }
            
            # Update user statistics in AppState using the proper method
            self.app_state.update_user_stats(study_time_sec, 0)  # 0 questions_answered for now
            
            # Update internal user_data for compatibility
            self.user_data['sessions'].append(session_data)
            self.user_data['total_sessions'] = len(self.user_data['sessions'])
            self.user_data['total_study_minutes'] = self.app_state.total_study_time // 60
            self.user_data['last_session_date'] = self.app_state.last_day_visited
            
            # Save data through AppState
            self._save_user_data()
        
        # Reset session state
        session.update({
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
        })
        if self.ui_callback:
            self.ui_callback("Session completed!", show_continue=False)
        return max(0, (self.user_data.get('study_time', 0) or 0) // 60)

    def pause(self):
        s = self.app_state.study_session
        if not s.get('active') or s.get('session_paused'):
            return False
        s['session_paused'] = True
        s['pause_time'] = time.time()
        return True

    def resume(self):
        s = self.app_state.study_session
        if not s.get('active') or not s.get('session_paused'):
            return False
        paused_dur = time.time() - s.get('pause_time', time.time())
        if s.get('block_start_time'):
            s['block_start_time'] += paused_dur
        s['session_paused'] = False
        s.pop('pause_time', None)
        return True

    def _save_user_data(self) -> bool:
        """Private alias for save_user_data — called internally after session completion."""
        return self.save_user_data()

"""
Main Game Screen - Primary interface showing pet, study controls, and navigation

This module provides the main game interface for StudyPet, including:
- Pet display and interaction
- Study timer and session management
- Music player controls
- Drowsiness detection integration
- Settings and configuration access

Author: CookLaye
Version: 1.0
"""

import os
import random
import threading
import tkinter as tk
from tkinter import ttk, simpledialog, scrolledtext
from PIL import Image, ImageTk
import pygame
# Local imports
from ui.simple_theme import simple_theme, create_rounded_button
from ui.rounded_widgets import RoundedPanel
from ui.unified_settings import show_unified_settings
from ui.pet_theme import apply_pet_theme
from ui.tasks_panel import TasksPanel
from utils.notifications import NotificationManager
from utils.model_manager import ModelManager
from utils.chatbot_utils import ChatBot
from models.pet import PetStage, PetEmotion

class CustomTimerDialog(tk.Toplevel):
    """Dialog for setting custom timer duration and speed multiplier."""
    def __init__(self, parent, developer_mode=False):
        super().__init__(parent)
        self.title("Custom Duration")
        self.place(relwidth=0.3, relheight=0.2)
        self.resizable(False, False)
        self.grab_set()

        self.result = None

        frame = tk.Frame(self, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Duration (minutes):").pack(pady=(0, 5))
        self.duration_entry = tk.Entry(frame, justify="center")
        self.duration_entry.pack(pady=(0, 15))
        self.duration_entry.focus_set()

        if developer_mode:
            tk.Label(frame, text="Speed Multiplier:").pack(pady=(0, 5))
            self.speed_var = tk.StringVar(value="1x")
            self.speed_combo = ttk.Combobox(frame, textvariable=self.speed_var,
                                         values=["1x", "2x", "3x"],
                                         state="readonly", justify="center")
            self.speed_combo.pack(pady=(0, 15))

        btn = tk.Button(frame, text="Start", command=self.confirm)
        btn.pack()

    def confirm(self):
        try:
            duration_str = self.duration_entry.get()
            if not duration_str:
                return

            duration = int(duration_str)
            speed = 1
            if hasattr(self, 'speed_var'):
                speed = int(self.speed_var.get().replace('x', ''))

            if 1 <= duration <= 60:
                self.result = (duration, speed)
                self.destroy()
            else:
                NotificationManager.error("Invalid Duration", "Duration must be between 1 and 60 minutes.")
        except ValueError:
            NotificationManager.error("Invalid Input", "Please enter a valid number.")

# Constants
DEFAULT_STUDY_DURATION = 25  # Default study session in minutes
TIMER_PRESETS = [10, 15, 20, 25, 30]  # Quick-start timer options
UI_UPDATE_INTERVAL = 1000  # UI update interval in milliseconds

class MainGameScreen:
    """
    Main game screen providing the core StudyPet interface.

    This class manages the primary game interface including pet display,
    study sessions, music controls, and user interactions.

    === Attributes ===
    parent: Parent Tkinter window
    app_state: Global application state manager
    music_player: Background music player instance
    app_controller: Reference to main application controller
    frame: Main container frame for all UI elements
    playground_renderer: Pet display and animation handler
    chat_interface: AI chat interface component

    === Study Session Attributes ===
    study_timer_active: Whether study timer is currently running
    study_timer_paused: Whether study timer is paused
    study_time_remaining: Time remaining in current session (seconds)
    study_session_duration: Total duration of current session (minutes)

    === UI State Attributes ===
    timer_var: StringVar for timer display
    study_progress_var: StringVar for progress messages
    status_var: StringVar for status updates
    """
    
    # === Timer Management ===
    def stop_study_timer(self):
        """Safely stop the study timer if it's running."""
        try:
            if hasattr(self, 'timer_id') and self.timer_id:
                if hasattr(self, 'parent') and self.parent:
                    try:
                        self.parent.after_cancel(self.timer_id)
                    except (tk.TclError, AttributeError) as e:
                        if "can't invoke" not in str(e):
                            print(f"Error stopping timer: {e}")
                self.timer_id = None

            self.study_timer_active = False
            self.timer_running = False

        except Exception as e:
            print(f"Error in stop_study_timer: {e}")
    
    # === Initialization ===
    def __init__(self, parent, app_state, music_player, app_controller=None, session_manager=None):
        """
        Initialize the main game screen.

        Args:
            parent: Parent Tkinter window
            app_state: Global application state manager
            music_player: Background music player instance
            app_controller: Reference to main application controller
        """
        print("Initializing MainGameScreen...")  # Debug print
        
        # Store core references
        self.parent = parent
        self.app_state = app_state
        self.music_player = music_player
        self.app_controller = app_controller
        self.session_manager = session_manager

        # UI scale factor: compensates for the DPI-awareness fix so that all
        # hardcoded pixel geometry (heights, widths, padx/pady) grows
        # proportionally with fonts on high-DPI displays.
        try:
            self.ui_scale = parent.winfo_fpixels('1i') / 96.0
        except Exception:
            self.ui_scale = 1.0
        def s(px):
            """Scale a pixel value by the display DPI factor."""
            return max(1, round(px * self.ui_scale))
        self.s = s
        
        # Initialize theme system
        self.theme = simple_theme
        self.colors = self.theme.colors
        
        # Set up pet evolution callback
        self.app_state.on_evolve = self._handle_pet_evolution
        
        try:
            self._initialize_core_state()
            self._initialize_ui_state()
            self._initialize_camera_state()
            self._initialize_chat_state()
            self._initialize_playground_state()
            self._setup_ui()

            # Configure Pomodoro styles for progress bars
            style = ttk.Style()
            style.configure("Study.Horizontal.TProgressbar",
                            troughcolor=self.colors.get("bg_secondary", "#F5F5F5"),
                            background=self.colors.get("accent", "#4CAF50"))
            style.configure("Break.Horizontal.TProgressbar",
                            troughcolor=self.colors.get("bg_secondary", "#F5F5F5"),
                            background="#4A90E2") # Blue for break

            # Set default style for the taskbar timer progress
            if hasattr(self, 'taskbar_timer_progress'):
                self.taskbar_timer_progress.configure(style="Study.Horizontal.TProgressbar")

            # Scheduler temporarily disabled
            # self.schedule_plan = None  # e.g., {"mode": "quick", "focus": 25}
            # self.scheduled_session_ready = False
            
            # Set up the screen after all initialization is complete
            self.setup_ui()
            self.setup_dynamic_fonts()
            self.update_pet_info_display()
            self.update_music_button_states()
            
            # Bind window resize event for dynamic behaviors
            self._resize_after_id = None
            self.parent.bind('<Configure>', self.handle_window_resize)

            if hasattr(self.app_controller, 'session_manager'):
                self.app_controller.session_manager.set_ui_callback(self.update_session_ui)

        except Exception as e:
            import traceback
            print(f"❌ Error initializing MainGameScreen: {e}")
            print("Full traceback:")
            traceback.print_exc()
            # Re-raise to let the main app handle it
            raise e
    
    # === Utility Methods ===
    def _safe_destroy_widget(self, widget):
        """Safely destroy a widget if it exists."""
        try:
            if widget and hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                # First, destroy all children
                for child in widget.winfo_children():
                    self._safe_destroy_widget(child)
                # Then destroy the widget itself
                widget.destroy()
        except (tk.TclError, AttributeError) as e:
            if "can't invoke" not in str(e) and "invalid command name" not in str(e):
                print(f"Warning: Error destroying widget: {e}")
    
    def _safe_unbind_events(self, widget):
        """Safely unbind all events from a widget.

        Args:
            widget: The Tkinter widget to unbind events from
        """
        try:
            # Check if widget exists and is a valid Tkinter widget
            if not widget or not hasattr(widget, 'winfo_exists') or not widget.winfo_exists():
                return
                
            # Check if widget has the bind method
            if not hasattr(widget, 'bind') or not callable(widget.bind):
                return
                
            # Get all bound events
            try:
                bindings = widget.bind()
                if not bindings:
                    return
                    
                # Unbind each event
                for sequence in list(bindings):  # Create a copy of the list to avoid modification during iteration
                    try:
                        # Skip empty or invalid sequences
                        if not sequence or not isinstance(sequence, str):
                            continue
                            
                        # Special handling for mouse wheel events on Windows/Linux
                        if sequence.startswith('<MouseWheel') or sequence.startswith('<Button-4>') or sequence.startswith('<Button-5>'):
                            try:
                                widget.unbind_all(sequence)
                            except tk.TclError:
                                pass
                        else:
                            widget.unbind(sequence)
                            
                    except tk.TclError as e:
                        # Ignore errors about non-existent bindings
                        if 'no binding' not in str(e).lower():
                            print(f"Warning: Error unbinding sequence '{sequence}': {e}")
                    except Exception as e:
                        print(f"Warning: Unexpected error unbinding sequence '{sequence}': {e}")
                        
            except tk.TclError as e:
                # Handle case where widget is being destroyed
                if 'bad window path name' not in str(e):
                    print(f"Warning: Error getting bindings: {e}")
                    
        except Exception as e:
            # Catch any other unexpected errors
            if 'bad window path name' not in str(e):  # Skip the specific error we're trying to prevent
                print(f"Warning: Error in _safe_unbind_events: {e}")
                import traceback
                traceback.print_exc()
    
    def cleanup(self):
        """
        Clean up all resources, timers, and references.
        This should be called before destroying the screen.
        """
        try:
            # 1. First stop any active timers and animations
            if hasattr(self, 'stop_study_timer'):
                try:
                    self.stop_study_timer()
                except Exception as e:
                    print(f"Error in stop_study_timer: {e}")
            
            # 2. Stop any background threads
            if hasattr(self, '_stop_drowsiness_detection'):
                try:
                    self._stop_drowsiness_detection()
                except Exception as e:
                    print(f"Error in stop_drowsiness_detection: {e}")
            
            # 3. Clear any scheduled callbacks
            if hasattr(self, 'timer_id') and self.timer_id:
                try:
                    if hasattr(self, 'root') and self.root and hasattr(self.root, 'after'):
                        self.root.after_cancel(self.timer_id)
                except (tk.TclError, AttributeError) as e:
                    if "can't invoke" not in str(e):
                        print(f"Error cancelling timer: {e}")
                self.timer_id = None
            
            # 4. Clean up camera and other hardware resources
            if hasattr(self, 'camera_manager') and self.camera_manager:
                try:
                    self.camera_manager.cleanup()
                except Exception as e:
                    print(f"Error cleaning up camera manager: {e}")
                self.camera_manager = None
            
            if hasattr(self, 'drowsiness_detector') and self.drowsiness_detector:
                try:
                    self.drowsiness_detector.cleanup()
                except Exception as e:
                    print(f"Error cleaning up drowsiness detector: {e}")
                self.drowsiness_detector = None
            
            # 5. Clean up playground renderer
            if hasattr(self, 'playground_renderer') and self.playground_renderer:
                try:
                    # Store reference to canvas before cleanup
                    canvas = getattr(self.playground_renderer, 'canvas', None)
                    
                    # Call cleanup on the renderer
                    if hasattr(self.playground_renderer, 'cleanup'):
                        self.playground_renderer.cleanup()
                    
                    # Additional canvas cleanup if it still exists
                    if canvas and hasattr(canvas, 'winfo_exists') and canvas.winfo_exists():
                        try:
                            canvas.delete('all')
                        except tk.TclError as e:
                            if "can't invoke" not in str(e):
                                print(f"Error cleaning up canvas: {e}")
                except Exception as e:
                    print(f"Error cleaning up playground renderer: {e}")
                finally:
                    self.playground_renderer = None
            
            # 6. Clean up chat interface
            if hasattr(self, 'chat_interface') and self.chat_interface:
                try:
                    if hasattr(self.chat_interface, 'cleanup'):
                        self.chat_interface.cleanup()
                except Exception as e:
                    print(f"Error cleaning up chat interface: {e}")
                self.chat_interface = None

            if hasattr(self, 'model_manager') and self.model_manager:
                try:
                    self.model_manager.stop_server()
                except Exception as e:
                    print(f"Error stopping AI server: {e}")
                self.model_manager = None
            
            # 7. Clean up frame and its widgets (do this after cleaning up children)
            if hasattr(self, 'frame') and self.frame:
                try:
                    # First, unbind all events
                    self._safe_unbind_events(self.frame)
                    
                    # Then destroy all child widgets
                    self._safe_destroy_widget(self.frame)
                    
                    # Finally, destroy the frame itself if it still exists
                    if hasattr(self.frame, 'winfo_exists') and self.frame.winfo_exists():
                        try:
                            self.frame.destroy()
                        except tk.TclError as e:
                            if "can't invoke" not in str(e):
                                print(f"Error destroying frame: {e}")
                    
                    # Clear the reference
                    self.frame = None
                    
                except Exception as e:
                    print(f"Error during frame cleanup: {e}")
                    
                    print(f"Error during widget cleanup: {e}")
            
            # Clean up any remaining widgets that might be direct children of parent
            if hasattr(self, 'parent') and self.parent:
                try:
                    for widget in self.parent.winfo_children():
                        if widget != self.frame:  # Skip frame if it's still there
                            self._safe_destroy_widget(widget)
                except Exception as e:
                    print(f"Error cleaning up parent widgets: {e}")
            
            # Clear all widget lists and references
            for attr in ['font_widgets', 'timer_widgets', 'control_widgets']:
                if hasattr(self, attr):
                    getattr(self, attr).clear()
            
            # Clear other references
            for attr in ['app_state', 'music_player', 'app_controller', 'root', 'parent']:
                if hasattr(self, attr):
                    setattr(self, attr, None)
            
            # Clean up any remaining references
            if hasattr(self, '_study_stop_event') and self._study_stop_event:
                try:
                    self._study_stop_event.set()
                except Exception:
                    pass
            
            # Force garbage collection
            import gc
            gc.collect()
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Ensure we don't keep any circular references
            if hasattr(self, 'parent') and self.parent:
                try:
                    self.parent.unbind('<Configure>', None)
                except Exception:
                    pass
    
    def _initialize_core_state(self) -> None:
        """Initialize core application state and theme."""
        # Developer mode state - load from settings if available
        self.developer_mode = False
        if hasattr(self, 'app_state') and hasattr(self.app_state, 'settings'):
            self.developer_mode = self.app_state.settings.get('developer_mode', False)
        
        # Initialize theme based on selected pet
        self.setup_pet_theme()
        self.colors = self.theme.colors
    
    def _initialize_ui_state(self) -> None:
        """Initialize UI-related state variables."""
        # Study session state
        self.study_timer_active = False
        self.study_timer_paused = False
        self.study_time_remaining = 0
        self.study_session_duration = DEFAULT_STUDY_DURATION
        self.study_thread = None
        self.timer_running = False
        self.timer_id = None
        self.total_duration_seconds = DEFAULT_STUDY_DURATION * 60
        self.time_remaining = self.total_duration_seconds

        # Pomodoro State
        self.pomo_phase = "WORK" # "WORK" or "BREAK"
        self.pomo_work_duration = 25 * 60
        self.pomo_break_duration = 5 * 60
        self.pomo_cycle_count = 0
        self.selected_task_idx = None # Index of task linked to current session
        self.timer_speed = 1 # Speed multiplier for the timer (1 = normal)


        # Timer presets for quick-start
        self.timer_presets = TIMER_PRESETS

        # UI variables
        self.timer_var = tk.StringVar(value=f"{DEFAULT_STUDY_DURATION}:00")
        self.study_progress_var = tk.StringVar(value="Ready to study!")
        self.status_var = tk.StringVar(value="Timer ready")
    
    def _initialize_camera_state(self) -> None:
        """Initialize camera and drowsiness detection state."""
        self.camera_manager = None
        self.drowsiness_detector = None
        self.drowsiness_detection_active = False
        self.drowsiness_thread = None
        self._drowsiness_stop_event = threading.Event()
        self.drowsy_start_time = 0
        self.consecutive_drowsy_sessions = 0
    
    def _initialize_chat_state(self) -> None:
        """Initialize chat system state."""
        self.chat_interface = None
        self.chat_locked = None  # Track whether chat is locked (EGG stage)
        self.chat_panel = None  # Reference to chat panel for dynamic updates
        self.speech_bubble_visible = False
        self.speech_bubble_image = None
        self.speech_bubble_label = None

        # Initialize AI Backend
        self.model_manager = ModelManager()
        current_pet = self.app_state.get_current_pet()
        pet_name = getattr(current_pet, 'name', 'StudyPet') if current_pet else 'StudyPet'
        self.chatbot = ChatBot(pet_name=pet_name)

        # Start server in background thread to avoid freezing UI during init
        threading.Thread(target=self.model_manager.start_server, daemon=True).start()

        # Messages for locked chat (Egg stage)
        self.locked_chat_messages = [
            "Your pet is still an egg and too sleepy to talk!",
            "Shhh... the little one is still dreaming in its shell!",
            "It's a bit too early for conversations. Let's help it grow!",
            "The pet is focusing all its energy on evolving right now!",
            "Patience is a virtue! Your pet will talk to you soon!",
            "Something wonderful is happening inside that egg... just wait!",
            "Not quite ready for chat, but it feels your love!"
        ]

        # Encouragement messages for study sessions
        self.encouraging_messages = [
            "Stay focused! You're doing great!",
            "Keep it up! Just a bit longer!",
            "You've got this! Stay with me!",
            "Don't give up! You're almost there!",
            "Take a deep breath and refocus!"
        ]

        # Rest messages for break periods
        self.rest_messages = [
            "Time for a break! You've earned it.",
            "Let's take a short break and come back refreshed!",
            "Your brain needs a rest. Take a short walk!",
            "A quick break now will help you focus better later!"
        ]
    
    def _initialize_playground_state(self) -> None:
        """Initialize playground and pet display state."""
        self.playground_renderer = None
        self.playground_canvas = None
    
    def _setup_ui(self) -> None:
        """Set up the main UI components."""
        # This will be called after all initialization is complete
        pass
    
    # === Music Controls ===
    def update_pet_info_display(self):
        """Update the pet information display in the status panel."""
        
        if not hasattr(self, 'app_state') or not self.app_state:
            return
            
        current_pet = self.app_state.get_current_pet()
        if not current_pet or not hasattr(self, 'status_labels'):
            return
            
        try:
            # Get pet attributes
            name = getattr(current_pet, 'name', 'Unnamed Pet')
            level = getattr(current_pet, 'level', 1)
            
            # Get values from global state
            stage = self.app_state.stage.name.replace('_', ' ').title()
            emotion = self.app_state.emotion.name.title()
            affection = self.app_state.affection
            max_affection = self.app_state.affection_cap
            
            # Update status labels if they exist
            if hasattr(self, 'status_labels'):
                labels = self.status_labels
                if 'name' in labels and labels['name'].winfo_exists():
                    labels['name'].config(text=f"Name: {name}")
                if 'level' in labels and labels['level'].winfo_exists():
                    labels['level'].config(text=f"Level: {level}")
                if 'stage' in labels and labels['stage'].winfo_exists():
                    labels['stage'].config(text=f"Stage: {stage}")
                if 'emotion' in labels and labels['emotion'].winfo_exists():
                    labels['emotion'].config(text=f"Mood: {emotion}")
                if 'affection' in labels and labels['affection'].winfo_exists():
                    labels['affection'].config(
                        text=f"Affection: {affection}/{max_affection} "
                             f"({self.app_state.affection_percentage:.1f}%)"
                    )
            
            # Update window title
            if hasattr(self, 'parent') and hasattr(self.parent, 'title'):
                self.parent.title(f"StudyPet - {name}")
                
            # Update taskbar name label if it exists
            if hasattr(self, 'taskbar_name_label') and self.taskbar_name_label.winfo_exists():
                self.taskbar_name_label.config(text=name)
                
            # Update affection progress bar if it exists
            if hasattr(self, 'affection_progress') and self.affection_progress.winfo_exists():
                # Calculate percentage based on current cap
                percentage = (affection / max_affection * 100) if max_affection > 0 else 0
                self.affection_progress.configure(value=min(100, max(0, percentage)))

            # Update taskbar evolution progress bar if it exists
            if hasattr(self, 'taskbar_evolution_progress') and self.taskbar_evolution_progress.winfo_exists():
                # Calculate percentage based on current cap
                percentage = (affection / max_affection * 100) if max_affection > 0 else 0
                self.taskbar_evolution_progress.configure(value=min(100, max(0, percentage)))
        except Exception as e:
            print(f"Error updating pet info display: {e}")
            import traceback
            traceback.print_exc()
                
    def setup_pet_theme(self):
        """Set up the pet theme based on the current pet."""
        self.theme = simple_theme
        apply_pet_theme(app_state=self.app_state)
        self.colors = self.theme.colors

    # Study timer related methods have been removed
    
    # Timer related methods have been removed
    
    # Study timer panel refresh method has been removed
    
    def update_session_ui(self, status_text="", show_continue=False):
        """Update the session UI elements."""
        try:
            if hasattr(self, 'session_status_label'):
                if status_text:
                    self.session_status_label.config(text=status_text)
            
            s = getattr(self.app_state, 'study_session', {})
            if s.get('active') and hasattr(self, 'session_progress'):
                total_blocks = len((s.get('schedule') or {}).get('blocks', [])) or 1
                completed = len(s.get('completed_blocks', []))
                progress = (completed / total_blocks) * 100
                self.session_progress['value'] = progress
            
            # Update button states
            if hasattr(self, 'btn_start_session') and hasattr(self, 'btn_continue'):
                has_schedule = bool(s.get('schedule'))
                is_active = s.get('active', False)
                
                self.btn_start_session.config(
                    state=tk.NORMAL if has_schedule and not is_active else tk.DISABLED
                )
                self.btn_continue.config(
                    state=tk.NORMAL if show_continue and is_active else tk.DISABLED
                )
                
                # Manage countdown frame visibility
                if hasattr(self, 'countdown_frame'):
                    if show_continue:
                        # Show the countdown frame with the current status text
                        self.countdown_label.config(text=status_text)
                        if not self.countdown_frame.winfo_ismapped():
                            self.countdown_frame.pack(fill='x', pady=5, after=self.session_status_label)
                    else:
                        # Hide the countdown frame
                        if self.countdown_frame.winfo_ismapped():
                            self.countdown_frame.pack_forget()
                        
        except Exception as e:
            print(f"Error updating timer UI: {e}")
            import traceback
            traceback.print_exc()
    
    def start_session(self):
        """Start a new study session."""
        s = getattr(self.app_state, 'study_session', {})
        schedule = s.get('schedule', {})
        blocks = schedule.get('blocks', [])
        
        if not blocks:
            NotificationManager.error("Error", "No schedule selected")
            return

        # Show session summary
        summary = "Study Session Schedule:\\n\\n"
        for i, b in enumerate(blocks, 1):
            block_type = 'Study' if b.get('type') == 'study' else 'Break'
            summary += f"{i}. {block_type}: {b.get('duration', 0)} minutes\\n"
            
        total_minutes = sum(b.get('duration', 0) for b in blocks)
        summary += f"\\nTotal duration: {total_minutes} minutes\\n\\n"
        summary += "You'll have 5 minutes to confirm each block. Start session?"
        
        if NotificationManager.confirm("Start Session", summary):
            if hasattr(self, 'app_controller') and hasattr(self.app_controller, 'session_manager'):
                if self.app_controller.session_manager.start_session():
                    self.update_session_ui("Starting first block...")
                    return
            NotificationManager.error("Error", "Failed to start session")
    
    def confirm_next_block(self):
        """Confirm continuing to the next block."""
        if hasattr(self, 'app_controller') and hasattr(self.app_controller, 'session_manager'):
            if self.app_controller.session_manager.confirm_next_block():
                self.update_session_ui("Starting next block...")
    

    def setup_ui(self):
        """Create new layered layout: Full-screen playground with compact UI blocks."""
        # Define header background color for UI consistency
        # Main frame fills entire window
        self.frame = tk.Frame(self.parent)
        self.frame.pack(fill="both", expand=True)

        # === LAYER 0: Full-screen playground canvas (background) ===
        self.playground_canvas = tk.Canvas(
            self.frame,
            highlightthickness=0,
            bg=self.colors["bg_main"]
        )
        self.playground_canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        # Ensure canvas is at the bottom layer
        # Removed lower() call that was causing hanging
        # self.playground_canvas.lower()

        # Bind click-to-move functionality
        self.playground_canvas.bind("<Button-1>", self.handle_playground_click)

        # Force canvas to update its size immediately and set a visible background
        self.playground_canvas.update_idletasks()
        # Set a visible background color immediately
        current_pet = self.app_state.get_current_pet()
        if current_pet:
            self.playground_canvas.configure(bg=self.colors.get("bg_main", "#FFFFFF"))

        # Initialize playground immediately instead of using after()
        if current_pet:
            try:
                # Safely get pet data
                pet_type_str = None

                if hasattr(current_pet.pet_type, 'value'):
                    pet_type_str = current_pet.pet_type.value
                else:
                    pet_type_str = str(current_pet.pet_type)

                if pet_type_str:
                    # Just call with pet_type, stage and emotion will be taken from self.app_state
                    self._init_playground_immediately(pet_type_str)
                else:
                    print("Warning: Missing pet type for playground initialization")
            except Exception as e:
                print(f"Warning: Error initializing playground: {e}")
        
        # === LAYER 2: Top navigation bar ===
        nav_frame = tk.Frame(
            self.frame,
            bg=self.colors["bg_secondary"],  # Use pet-specific secondary background
            relief="flat",
            bd=0
        )
        nav_frame.place(x=0, y=0, relwidth=1.0, relheight=0.07)

        # Navigation buttons (NO dev button here - moved to settings)
        nav_buttons = [
            ("📅 Tasks", lambda: self.switch_tab("tasks")),
            ("📊 Stats", lambda: self.switch_tab("stats")),
            ("🎵 Music", lambda: self.switch_tab("music")),
            ("⚙️ Settings", lambda: self.switch_tab("settings")),
            ("🎮 Minigame", lambda: self.start_minigame())
        ]

        for text, command in nav_buttons:
            btn = create_rounded_button(
                nav_frame,
                text,
                command=command,
                style="accent",
                radius=20,
                padding=(self.s(12), self.s(6)),
                font=("Arial", 10, "bold")
            )
            btn.pack(side="left", padx=self.s(8), pady=self.s(6))

        # Music controls removed from top bar to eliminate redundancy with Music panel

        # === LAYER 1: Collapsible UI blocks ===
        # Pet Status (top-left, collapsible)
        self.status_expanded = False
        self.status_container = RoundedPanel(self.frame, radius=15, bg=self.colors["bg_main"], fit_content=False)
        self.status_container.place(x=self.s(20), y=self.s(60), relwidth=0.15, relheight=0.05)

        self.status_header = tk.Frame(self.status_container.inner, bg=self.colors["bg_secondary"], relief="flat", bd=0, cursor="hand2")  # Use pet-specific background
        self.status_header.pack(fill="x")
        self.status_header.bind("<Button-1>", self.toggle_status_panel)
        status_header_label = tk.Label(
            self.status_header,
            text="📊 Pet Status ▼",
            font=("Arial", 10, "bold"),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_dark"],  # Use pet-specific dark text
            cursor="hand2"
        )
        status_header_label.pack(pady=self.s(2))
        status_header_label.bind("<Button-1>", self.toggle_status_panel)

        self.status_panel = tk.Frame(self.status_container.inner, bg=self.colors["bg_secondary"])  # Use pet-specific background

        # Status content (no scrolling)
        self.status_content = tk.Frame(self.status_panel, bg=self.colors["bg_secondary"])  # Use pet-specific background
        # Initially hidden until expanded

        # Initialize status labels dictionary if it doesn't exist
        if not hasattr(self, 'status_labels'):
            self.status_labels = {}
            
        # Contents of status panel
        status_items = ["name", "stage", "emotion", "affection"]
        panel_bg = self.colors["bg_secondary"]  # Use pet-specific background
        
        # Clear existing labels if they exist
        for widget in self.status_content.winfo_children():
            widget.destroy()
            
        # Create new labels with just the values (no field names)
        for item in status_items:
            # Create label for the value only
            value_label = tk.Label(
                self.status_content,
                text="...",
                font=("Arial", 10),
                bg=panel_bg,
                fg=self.colors["text_dark"],
                anchor="w"
            )
            value_label.pack(fill="x", pady=self.s(2), padx=self.s(5))
            self.status_labels[item] = value_label
        
        # Make sure the status content is packed and visible
        self.status_content.pack(fill="both", expand=True, padx=self.s(5), pady=self.s(5))
        
        # Force an immediate update of the pet info display using parent's after method
        if hasattr(self, 'parent') and hasattr(self.parent, 'after'):
            self.parent.after(100, self.update_pet_info_display)
            
        # Add developer tools section
        self.dev_tools_frame = tk.Frame(self.status_content, bg=panel_bg, bd=1, relief="groove")
        
        # Developer tools header
        self.dev_header = tk.Label(
            self.dev_tools_frame,
            text="🔧 Developer Tools",
            font=("Arial", 9, "bold"),
            bg=panel_bg,
            fg=self.colors["text_dark"]
        )
        self.dev_header.pack(anchor="w", pady=(self.s(5), self.s(2)), padx=self.s(5))
        
        # Developer buttons frame - using grid for better layout control
        self.dev_buttons_frame = tk.Frame(self.dev_tools_frame, bg=panel_bg)
        self.dev_buttons_frame.pack(fill="x", padx=self.s(5), pady=(0, self.s(5)))
        
        # Top row: Affection controls
        self.affection_frame = tk.Frame(self.dev_buttons_frame, bg=panel_bg)
        self.affection_frame.pack(fill="x", pady=(0, 5))
        
        # +50 Affection button
        self.add_affection_btn = create_rounded_button(
            self.affection_frame,
            text="+50 Affection",
            command=self.add_affection,
            style="accent",
            radius=15,
            padding=(self.s(8),  self.s(4)),
            font=("Arial", 9, "bold")
        )
        self.add_affection_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))
        
        # Reset Affection button
        self.reset_affection_btn = create_rounded_button(
            self.affection_frame,
            text="Reset Affection",
            command=self.reset_affection,
            style="accent",
            radius=15,
            padding=(self.s(8),  self.s(4)),
            font=("Arial", 9, "bold")
        )
        self.reset_affection_btn.pack(side="right", expand=True, fill="x", padx=(3, 0))
        
        # Middle row: Evolution controls
        self.evolution_frame = tk.Frame(self.dev_buttons_frame, bg=panel_bg)
        self.evolution_frame.pack(fill="x", pady=(0, 5))
        
        # Force Evolve button
        self.force_evolve_btn = create_rounded_button(
            self.evolution_frame,
            text="Force Evolve",
            command=self.force_evolve,
            style="accent",
            radius=15,
            padding=(self.s(8),  self.s(4)),
            font=("Arial", 9, "bold")
        )
        self.force_evolve_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))
        
        # Set Stage button
        self.set_stage_btn = create_rounded_button(
            self.evolution_frame,
            text="Set Stage",
            command=self.set_pet_stage,
            style="accent",
            radius=15,
            padding=(self.s(8),  self.s(4)),
            font=("Arial", 9, "bold")
        )
        self.set_stage_btn.pack(side="right", expand=True, fill="x", padx=(3, 0))
        
        # Bottom row: Emotion control
        self.emotion_frame = tk.Frame(self.dev_buttons_frame, bg=panel_bg)
        self.emotion_frame.pack(fill="x", pady=(0, 5))
        
        # Set Emotion button (centered in its own row)
        self.set_emotion_btn = create_rounded_button(
            self.emotion_frame,
            text="Set Emotion",
            command=self.set_pet_emotion,
            style="accent",
            radius=15,
            padding=(self.s(8),  self.s(4)),
            font=("Arial", 9, "bold")
        )
        self.set_emotion_btn.pack(expand=True, fill="x")
        
        # Add some space at the bottom
        tk.Frame(self.status_content, height=10, bg=self.colors["bg_secondary"]).pack(fill='x')
        
        # Initially hide developer tools
        self.dev_tools_frame.pack_forget()
        
        # Pack status content inside status panel
        self.status_content.pack(fill="both", expand=True)

        # Study Timer (next to chat, top-right, collapsible)
        self.timer_expanded = False
        self.timer_container = RoundedPanel(self.frame, radius=15, bg=self.colors["bg_main"], fit_content=False)
        # Place to the left of chat (chat left is at -350, distance d=20, timer width=0.23)
        self.timer_container.place(relx=1.0, x=-self.s(720), y=self.s(60), relwidth=0.23, relheight=0.05)


        self.timer_header = tk.Frame(self.timer_container.inner, bg=self.colors["bg_secondary"], relief="flat", bd=0, cursor="hand2")
        self.timer_header.pack(fill="x")
        self.timer_header.bind("<Button-1>", self.toggle_timer_panel)
        self.timer_header_label = tk.Label(
            self.timer_header,
            text="⏱️ Study Timer ▼",
            font=("Arial", 10, "bold"),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_dark"],
            cursor="hand2"
        )
        self.timer_header_label.pack(pady=self.s(2))
        self.timer_header_label.bind("<Button-1>", self.toggle_timer_panel)

        self.timer_panel = tk.Frame(self.timer_container.inner, bg=self.colors["bg_secondary"])
        self.timer_content = tk.Frame(self.timer_panel, bg=self.colors["bg_secondary"])
        self.timer_content.pack(fill='both', expand=True)
        
        # Create unified timer interface
        self.create_timer_ui(self.timer_content)
        
        # Show timer content by default since we're removing scrolling

        # === LAYER 2: Compact collapsible chatbox (top-right, below nav) ===
        self.chat_expanded = False
        self.chat_container = RoundedPanel(self.frame, radius=15, bg=self.colors["bg_main"], fit_content=False)
        self.chat_container.place(relx=1.0, x=-self.s(350), y=self.s(60), relwidth=0.225, relheight=0.05)


        # Chat header (always visible, clickable) - square
        self.chat_header = tk.Frame(
            self.chat_container.inner,
            bg=self.colors["bg_secondary"],  # Use pet-specific secondary background
            relief="flat",
            bd=0
        )
        self.chat_header.pack(fill="x")
        self.chat_header.bind("<Button-1>", self.toggle_chat_panel)

        chat_header_label = tk.Label(
            self.chat_header,
            text="💬 Pet Chat ▼",
            font=("Arial", 10, "bold"),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_dark"],  # Use pet-specific dark text
            cursor="hand2"
        )
        chat_header_label.pack(pady=self.s(2))
        chat_header_label.bind("<Button-1>", self.toggle_chat_panel)

        # Chat panel (hidden initially, expands on click) - square interior
        self.chat_panel = tk.Frame(self.chat_container.inner, bg=self.colors["bg_secondary"])  # Use pet-specific background

        # Chat content frame (no scrolling)
        self.chat_content = tk.Frame(self.chat_panel, bg=self.colors["bg_secondary"])
        # Initially hidden, contents created in create_chat_ui
        self.create_chat_ui(self.chat_content)

        # Initialize chat lock state
        self.chat_locked = None  # Will be set based on pet stage
        self.update_chat_lock_state(force=True)

        # === LAYER 3: Bottom overlay taskbar (with pet name + evolution progress) ===
        try:
            self.taskbar = tk.Frame(self.frame, bg=self.colors["bg_secondary"], bd=0, highlightthickness=0)
            # Near bottom, with margins; overlay style
            window_height = self.parent.winfo_height()
            self.taskbar.place(relx=0.5, rely=1.0, anchor='s', relwidth=0.9, height=0.06 * window_height, y=-self.s(10))

            # Left: Pet info frame
            left = tk.Frame(self.taskbar, bg=self.colors["bg_secondary"]) 
            left.pack(side="left", padx=self.s(10))
            
            # Pet name
            name_frame = tk.Frame(left, bg=self.colors["bg_secondary"])
            name_frame.pack(side="top", fill="x")
            tk.Label(name_frame, text="Name:", font=("Arial", 9, "bold"), 
                    bg=self.colors["bg_secondary"], 
                    fg=self.colors["text_medium"]).pack(side="left", padx=(0,4))
            self.taskbar_name_label = tk.Label(name_frame, text="...", 
                                             font=("Arial", 11, "bold"), 
                                             bg=self.colors["bg_secondary"], 
                                             fg=self.colors["text_dark"]) 
            self.taskbar_name_label.pack(side="left")
            
            # Empty frame for consistent spacing
            tk.Frame(left, height=10, bg=self.colors["bg_secondary"]).pack()

            # Center-left: Affection progress bar
            center_left = tk.Frame(self.taskbar, bg=self.colors["bg_secondary"]) 
            center_left.pack(side="left", fill="x", expand=True, padx=self.s(10))
            
            # Evolution Progress label
            tk.Frame(center_left, height=2, bg=self.colors["bg_secondary"]).pack()  # Spacer
            tk.Label(center_left, text="Evolution Progress", font=("Arial", 9, "bold"), 
                    bg=self.colors["bg_secondary"], 
                    fg=self.colors["text_medium"],
                    anchor="w").pack(fill="x")
            
            ttk.Style().configure("Taskbar.Horizontal.TProgressbar", thickness=8)
            self.taskbar_evolution_progress = ttk.Progressbar(
                center_left, 
                mode='determinate', 
                style="Taskbar.Horizontal.TProgressbar",
                maximum=100  # Set maximum to 100 for percentage
            )
            self.taskbar_evolution_progress.pack(fill="x", pady=(2, 0))

            # Center-right: XP progress bar
            center_right = tk.Frame(self.taskbar, bg=self.colors["bg_secondary"]) 
            center_right.pack(side="left", fill="x", expand=True, padx=self.s(10))
            
            # Timer Progress label
            tk.Frame(center_right, height=2, bg=self.colors["bg_secondary"]).pack()  # Spacer
            tk.Label(center_right, text="Timer Progress", font=("Arial", 9, "bold"), 
                   bg=self.colors["bg_secondary"], 
                   fg=self.colors["text_medium"],
                   anchor="w").pack(fill="x")
            
            ttk.Style().configure("TaskbarTimer.Horizontal.TProgressbar", thickness=8)
            self.taskbar_timer_progress = ttk.Progressbar(
                center_right, 
                mode='determinate', 
                style="TaskbarTimer.Horizontal.TProgressbar"
            )
            self.taskbar_timer_progress.pack(fill="x", pady=(2, 0))

            # Right spacer
            tk.Frame(self.taskbar, bg=self.colors["bg_secondary"], width=10).pack(side="right")
        except Exception:
            pass

        # Force UI update
        self.parent.update_idletasks()

    # === STUDY TIMER SYSTEM ===
    def start_study_session(self, duration_minutes=25):
        """Start a study session with the specified duration.

        Args:
            duration_minutes: Duration of the study session in minutes
        """
        # Stop any existing timer before starting a new session
        self.stop_study_timer()

        if self.study_timer_active:
            return

        # Set up the study session
        self.study_session_duration = duration_minutes
        self.time_remaining = duration_minutes * 60  # Convert to seconds
        self.study_timer_active = True
        self.study_timer_paused = False
        self.timer_running = True

        # Reset drowsiness counters at the start of each session
        self.consecutive_drowsy_sessions = 0

        # Auto-expand the timer panel if not already expanded
        if not self.timer_expanded:
            self.toggle_timer_panel()

        # Update UI
        self.update_timer_ui()

    def stop_study_session(self):
        """Stop the study session and reset UI to selection state."""
        # Stop the timer loop immediately
        self.stop_study_timer()

        # Stop drowsiness detection if active
        self._stop_drowsiness_detection()

        # Hide speech bubble if visible
        if hasattr(self, '_speech_bubble_timer'):
            self.frame.after_cancel(self._speech_bubble_timer)
        self._hide_speech_bubble()
        
        if self.study_timer_active:
            self.study_timer_active = False
            self.study_timer_paused = False
            self.study_progress_var.set("Study session stopped")
            self.timer_var.set("")
            pass  # Thread join removed as timer is now after()-based
            self.study_thread = None
            
            # Hide control buttons
            if hasattr(self, 'pause_resume_button'):
                self.pause_resume_button.pack_forget()
            if hasattr(self, 'stop_session_button'):
                self.stop_session_button.pack_forget()

            # Hide countdown section
            if hasattr(self, 'countdown_frame'):
                self.countdown_frame.pack_forget()

            # Update UI to show duration selection
            self.update_timer_ui()
            
        # Reset session state
        self.pomo_phase = "WORK"
        self.consecutive_drowsy_sessions = 0

        # Reset UI buttons to selection state
        if hasattr(self, 'start_pause_btn'):
            self.start_pause_btn.config(text="Start", command=self.start_timer)
        if hasattr(self, 'stop_btn'):
            self.stop_btn.config(state="disabled")

        # Reset progress bar to study color
        if hasattr(self, 'taskbar_timer_progress'):
            try:
                self.taskbar_timer_progress.configure(style="Study.Horizontal.TProgressbar")
            except Exception:
                pass

    def pause_resume_study_session(self):
        """Pause or resume the current study session."""
        if self.study_timer_active:
            if self.study_timer_paused:
                self.study_timer_paused = False
                self.study_progress_var.set("Study session resumed!")
                self.start_pause_btn.config(text="⏸️ Pause")
            else:
                self.study_timer_paused = True
                self.study_progress_var.set("Study session paused")
                self.start_pause_btn.config(text="▶️ Resume")

    def confirm_stop_session(self):
        """Confirm stopping the current study session."""
        if self.study_timer_active:
            result = NotificationManager.confirm(
                "Stop Study Session",
                "Are you sure you want to stop the current study session?\n\nThis will end your progress."
            )
            if result:
                self.stop_study_session()

    def start_custom_session(self):
        """Start a custom duration session with speed multiplier support."""
        if self.study_timer_active:
            NotificationManager.notify("Timer Active", "A study session is already running!")
            return

        # Ask for custom duration and speed using the dialog
        dlg = CustomTimerDialog(self.parent, developer_mode=self.developer_mode)
        self.parent.wait_window(dlg)

        if dlg.result:
            duration, speed = dlg.result
            self.timer_speed = speed
            self.start_study_session(duration)

        # Reset speed to 1 after the session if desired,
        # but usually we keep it until the next custom session or reset.

    def toggle_status_panel(self, event=None):
        """Toggle pet status panel expansion/collapse."""
        if not hasattr(self, 'status_expanded') or self.status_panel is None:
            return
        if self.status_expanded:
            # Collapse
            self.status_panel.pack_forget()
            if hasattr(self, 'status_container'):
                window_height = self.parent.winfo_height()
                self.status_container.place(height=0.04 * window_height, relheight=0)
            self.status_expanded = False
            for widget in self.status_header.winfo_children():
                if isinstance(widget, tk.Label):
                    widget.config(text="📊 Pet Status ▼")
        else:
            # Expand
            self.status_panel.pack(fill="both", expand=True, pady=(5, 0))
            if hasattr(self, 'status_container'):
                # Use larger height if developer mode is enabled
                height = self.s(240) if hasattr(self, 'developer_mode') and self.developer_mode else self.s(140)
                self.status_container.place(height=height, relheight=0)
            self.status_expanded = True
            for widget in self.status_header.winfo_children():
                if isinstance(widget, tk.Label):
                    widget.config(text="📊 Pet Status ▲")

    def toggle_timer_panel(self, event=None, force_expand=None):
        """Toggle or force the timer panel expansion."""
        if force_expand is not None:
            self.timer_expanded = force_expand
        else:
            self.timer_expanded = not getattr(self, 'timer_expanded', False)

        if self.timer_expanded:
            # Expanded state - adjust height based on content
            base_height = self.s(360)  # Reduced to ~90% of 400 to better fit timer content
            if getattr(self, 'scheduled_session_ready', False):
                base_height += 50  # Add space for the plan CTA if visible

            # Show the panel with proper expansion and increased padding
            self.timer_panel.pack(fill="both", expand=True, pady=(self.s(10), 0), padx=self.s(5))

            # Update container height
            if hasattr(self, 'timer_container'):
                self.timer_container.place(height=base_height, relheight=0)

            # Ensure panel is visible and properly sized
            self.timer_panel.update_idletasks()

            # Update header text to show collapse indicator
            self.timer_header_label.config(text="⏱️ Study Timer ▲")

            # Ensure UI content reflects state
            try:
                # Removed self.update_timer_ui() call to prevent duplicate timer loops
                pass
            except Exception as e:
                print(f"Error updating timer UI: {e}")
        else:
            # Collapsed state
            self.timer_panel.pack_forget()
            if hasattr(self, 'timer_container'):
                window_height = self.parent.winfo_height()
                self.timer_container.place(height=0.04 * window_height, relheight=0)
            for widget in self.timer_header.winfo_children():
                if isinstance(widget, tk.Label):
                    widget.config(text="⏱️ Study Timer ▼")

    def toggle_chat_panel(self, event=None):
        """Toggle chat panel expansion/collapse."""
        if not hasattr(self, 'chat_expanded') or self.chat_panel is None:
            return
        if self.chat_expanded:
            # Collapse
            self.chat_panel.pack_forget()
            try:
                self.chat_content.pack_forget()
            except Exception:
                pass
            if hasattr(self, 'chat_container'):
                window_height = self.parent.winfo_height()
                self.chat_container.place(height=0.04 * window_height, relheight=0)
            self.chat_expanded = False
            # Update header text
            for widget in self.chat_header.winfo_children():
                if isinstance(widget, tk.Label):
                    widget.config(text="💬 Pet Chat ▼")
        else:
            # Expand
            self.chat_panel.pack(fill="both", expand=True, pady=(5, 0))
            # Ensure chat content is visible
            try:
                self.chat_content.pack(fill='both', expand=True)
            except Exception:
                pass
            if hasattr(self, 'chat_container'):
                window_height = self.parent.winfo_height()
                self.chat_container.place(height=0.45 * window_height, relheight=0)
            self.chat_expanded = True
            # Update header text
            for widget in self.chat_header.winfo_children():
                if isinstance(widget, tk.Label):
                    widget.config(text="💬 Pet Chat ▲")


    def handle_playground_click(self, event):
        """Handle left-click on playground to move pet to click location"""
        try:
            if self.playground_renderer and hasattr(self.playground_renderer, 'playground'):
                # Get click coordinates relative to canvas
                click_x = event.x
                click_y = event.y

                # Check if click is in UI area (avoid moving pet into UI panels)
                # UI boundaries: nav bar (top), status panel (left), timer/chat panels (right)
                canvas_width = self.playground_canvas.winfo_width()
                canvas_height = self.playground_canvas.winfo_height()

                # Use configuration-based boundaries for better click detection
                ui_left_boundary = self.playground_renderer.playground.PET_CONFIG["ui_block_right_margin"] + 20  # Status panel + margin
                ui_right_boundary = canvas_width - (self.playground_renderer.playground.PET_CONFIG["ui_block_right_margin"] + 20)  # Timer/chat + margin
                ui_top_boundary = 60   # Nav bar height + small margin
                ui_bottom_boundary = canvas_height - (self.playground_renderer.playground.PET_CONFIG["ui_block_bottom_margin"] + 50)  # Bottom UI + more margin for click area

                # Only move if click is outside UI areas AND pet is not an egg
                current_pet = self.app_state.get_current_pet()
                is_egg = False
                if current_pet and hasattr(current_pet, 'stage'):
                    try:
                        if hasattr(current_pet.stage, 'value'):
                            is_egg = current_pet.stage.value == 1
                        else:
                            is_egg = int(current_pet.stage) == 1
                    except Exception as e:
                        print(f"Warning: Error checking pet stage: {e}")

                # More permissive click detection - allow clicks closer to UI
                is_in_ui_area = (click_x <= ui_left_boundary or
                                click_x >= ui_right_boundary or
                                click_y <= ui_top_boundary or
                                click_y >= ui_bottom_boundary)

                if not is_in_ui_area and not is_egg:  # Don't allow movement for eggs
                    # Move pet gradually to click location using the movement system
                    # Ground pets only move horizontally, aquatic pets move in all directions
                    current_pet = self.app_state.get_current_pet()
                    if current_pet and hasattr(current_pet, 'pet_type'):
                        try:
                            pet_type_str = None
                            if hasattr(current_pet.pet_type, 'value'):
                                pet_type_str = current_pet.pet_type.value
                            else:
                                pet_type_str = str(current_pet.pet_type)

                            # Check if it's a ground pet (Dog, Cat, Raccoon)
                            is_ground_pet = pet_type_str.lower() in ['dog', 'cat', 'raccoon']

                            if is_ground_pet:
                                # Ground pets only move horizontally to mouse x position, stay on ground
                                self.playground_renderer.playground.set_target(click_x, self.playground_renderer.playground.pet_y)
                            else:
                                # Aquatic pets (Axolotl) can move to both x and y
                                self.playground_renderer.playground.set_target(click_x, click_y)
                        except Exception as e:
                            print(f"Warning: Error moving pet: {e}")
                            # Fallback to old behavior if pet type unknown
                            self.playground_renderer.playground.set_target(click_x, click_y)
                    else:
                        # Fallback to old behavior if pet type unknown
                        self.playground_renderer.playground.set_target(click_x, click_y)

                    # Update the pet display
                    self.update_pet_info_display()

        except Exception as e:
            print(f"Warning: Error in handle_playground_click: {e}")

    def _init_playground_immediately(self, pet_type_str, stage_int=None, emotion_str=None):
        """Initialize playground renderer immediately with proper canvas sizing"""
        
        # Define default values at the start
        canvas_width, canvas_height = 800, 600
        pet_type_key = 'penguin'
        stage = 1
        emotion = 'HAPPY'
        
        def _safe_get_pet_info():
            """Safely get pet information with error handling"""
            nonlocal canvas_width, canvas_height, pet_type_key, stage, emotion
            
            try:
                # Ensure canvas has proper dimensions
                self.playground_canvas.update_idletasks()
                
                # Safely get canvas dimensions with fallbacks
                try:
                    canvas_width = max(self.playground_canvas.winfo_width(), 100)
                    canvas_height = max(self.playground_canvas.winfo_height(), 100)
                    
                    # Configure canvas with safe dimensions
                    self.playground_canvas.configure(width=canvas_width, height=canvas_height)
                except tk.TclError as e:
                    print(f"Warning: Could not configure canvas: {e}")

                # Safely get current pet type with fallback
                try:
                    current_pet = self.app_state.get_current_pet()
                    if current_pet and hasattr(current_pet, 'pet_type'):
                        pet_type_key = current_pet.pet_type.value if hasattr(current_pet.pet_type, 'value') else str(current_pet.pet_type)
                except Exception as e:
                    print(f"Warning: Could not get current pet: {e}")
                    
                # Ensure pet_type_key is a string and has a value
                pet_type_key = str(pet_type_key) if pet_type_key else 'penguin'
                
                # Safely get stage and emotion from global pet state with fallbacks
                try:
                    stage = stage_int if stage_int is not None else self.app_state.stage.value
                    emotion = emotion_str.upper() if emotion_str else (
                        self.app_state.emotion.name.upper() 
                        if hasattr(self.app_state.emotion, 'name') 
                        else str(self.app_state.emotion).upper()
                    )
                except Exception as e:
                    print(f"Warning: Error getting pet state, using defaults: {e}")
                    stage = 1  # Default to EGG stage
                    emotion = 'HAPPY'  # Default emotion
                    
            except Exception as e:
                print(f"Error in _safe_get_pet_info: {e}")
                import traceback
                traceback.print_exc()
        
        # Call the function to get pet info
        _safe_get_pet_info()
        
        # If we already have a renderer, just update its state
        if hasattr(self, 'playground_renderer') and self.playground_renderer is not None:
            try:
                # Update the existing renderer's state
                self.playground_renderer.update_pet_state(
                    pet_type=pet_type_key,
                    pet_stage=stage,
                    pet_emotion=emotion.lower()
                )
                print(f"✅ Updated pet state: {pet_type_key} (Stage: {stage}, Emotion: {emotion})")
                self.update_pet_info_display()
                return  # Exit after updating state
            except Exception as e:
                print(f"Error updating existing renderer: {e}")
                # If update fails, continue with reinitialization
        
        # Initialize the simple playground renderer with robust error handling
        try:
            from graphics.simple_playground import SimplePlayground
            
            # Ensure we have valid values before initialization
            stage = max(1, min(5, int(stage) if str(stage).isdigit() else 1))  # Clamp to 1-5
            emotion = str(emotion).upper()
            
            try:
                self.playground_renderer = SimplePlayground(
                    self.playground_canvas,
                    app_state=self.app_state,
                    pet_type=pet_type_key,
                    pet_stage=stage,
                    pet_emotion=emotion.lower()
                )
                print(f"✅ SimplePlayground initialized with {pet_type_key} (Stage: {stage}, Emotion: {emotion})")
                self.update_pet_info_display()
                
            except tk.TclError as te:
                print(f"⚠️ Tkinter error initializing playground: {te}")
                self._show_playground_error(canvas_width, canvas_height, pet_type_key, stage, emotion)
            except Exception as e:
                print(f"⚠️ Error initializing playground: {e}")
                import traceback
                traceback.print_exc()
                self._show_playground_error(canvas_width, canvas_height, pet_type_key, stage, emotion)
                
        except ImportError as ie:
            print(f"⚠️ Could not import SimplePlayground: {ie}")
            self._show_playground_error(canvas_width, canvas_height, pet_type_key, stage, emotion)
                
    def _show_playground_error(self, width, height, pet_type, stage, emotion):
        """Display a fallback UI when the playground fails to initialize"""
        try:
            self.playground_renderer = None
            self.playground_canvas.delete("all")
            self.playground_canvas.create_text(
                width // 2, 
                height // 2,
                text=f"Pet: {pet_type}\nStage: {stage}\nEmotion: {emotion}",
                fill="black",
                font=('Arial', 12),
                tags=("fallback_text",)
            )
            self.update_pet_info_display()
        except Exception as e:
            print(f"⚠️ Error showing fallback UI: {e}")
            # Still try to update display even if renderer fails
            try:
                self.update_pet_info_display()
            except Exception as update_error:
                print(f"⚠️ Error updating pet info: {update_error}")


    def create_timer_ui(self, parent_frame):
        """
        Create a clean and organized timer interface with controls and presets.
        
        Args:
            parent_frame: The parent frame to place the timer UI in
        """
        # Clear any existing widgets
        for widget in parent_frame.winfo_children():
            widget.destroy()
        
        # Get background color from parent
        bg_color = parent_frame['bg']
        text_color = self.colors.get("text_dark", "#333333")
        accent_color = self.colors.get("accent", "#4CAF50")
        
        # Configure parent frame to expand
        parent_frame.pack_propagate(False)
        
        # Main container with padding
        container = tk.Frame(parent_frame, bg=bg_color)
        container.pack(fill='both', expand=True, padx=self.s(15), pady=self.s(15))
        
        # Timer display frame
        self.timer_display_frame = tk.Frame(container, bg=bg_color)
        self.timer_display_frame.pack(fill='x', pady=(0, 20))
        
        # Timer display
        self.timer_var = tk.StringVar(value="25:00")
        self.timer_label = tk.Label(
            self.timer_display_frame,
            textvariable=self.timer_var,
            font=("Arial", 48, "bold"),
            bg=bg_color,
            fg=text_color
        )
        self.timer_label.pack()
        
        # Status message
        self.status_var = tk.StringVar(value="Ready to study!")
        status_label = tk.Label(
            self.timer_display_frame,
            textvariable=self.status_var,
            font=("Arial", 10),
            bg=bg_color,
            fg=text_color
        )
        status_label.pack(pady=(0, 20))
        
        # Control buttons frame
        btn_frame = tk.Frame(container, bg=bg_color)
        btn_frame.pack(fill='x', pady=(0, 15))
        
        # Start/Pause button
        self.start_pause_btn = tk.Button(
            btn_frame,
            text="Start",
            command=self.start_timer,
            bg=self.colors.get("bg_accent", accent_color),
            fg=self.colors.get("text_dark", "#333"),
            font=("Arial", 10, "bold"),
            relief="flat",
            padx=self.s(20),
            pady=self.s(8),
            bd=0
        )
        self.start_pause_btn.pack(side='left', expand=True, padx=self.s(5))
        
        # Stop button
        self.stop_btn = tk.Button(
            btn_frame,
            text="Stop",
            command=self.stop_timer,
            bg=self.colors.get("bg_secondary", "#eee"),
            fg=self.colors.get("text_dark", "#333"),
            font=("Arial", 10, "bold"),
            relief="flat",
            padx=self.s(20),
            pady=self.s(8),
            bd=0,
            state="disabled"
        )
        self.stop_btn.pack(side='left', expand=True, padx=self.s(5))
        
        # Create a separator line
        separator = ttk.Separator(container, orient='horizontal')
        separator.pack(fill='x', pady=self.s(10))
        
        # Create a frame for preset buttons
        presets_frame = tk.Frame(container, bg=bg_color)
        presets_frame.pack(fill='x', pady=(0, 10))

        # Function to create preset buttons
        def create_preset_row(title, presets, break_info, row):
            # Title label with break info in parentheses
            title_label = tk.Label(
                presets_frame,
                text=f"{title} ({break_info})",
                font=("Arial", 9, "bold"),
                bg=bg_color,
                fg=text_color,
                anchor='w'
            )
            title_label.grid(row=row*2, column=0, columnspan=4, sticky='w', pady=(10, 5))

            # Preset buttons
            for i, (work, break_dur, text) in enumerate(presets):
                btn = tk.Button(
                    presets_frame,
                    text=text,
                    command=lambda w=work, b=break_dur: self.set_pomo_duration(w, b),
                    bg=self.colors.get("bg_secondary", "#f0f0f0"),
                    fg=text_color,
                    font=("Arial", 9),
                    relief="flat",
                    padx=10,
                    pady=5,
                    bd=1,
                    activebackground=self.colors.get("bg_accent", "#e0e0e0")
                )
                btn.grid(row=row*2+1, column=i, padx=self.s(2), pady=(0, self.s(10)), sticky='ew')

            # Configure column weights for even spacing
            for i in range(4):
                presets_frame.columnconfigure(i, weight=1)

        # Define Pomodoro presets
        pomo_presets = [
            (25, 5, "Classic"),
            (30, 10, "Extended"),
            (50, 10, "Intense")
        ]

        # Create Pomodoro presets row
        create_preset_row("Pomodoro", pomo_presets, "Work/Break", 0)

        # Task Selection Row
        task_row = tk.Frame(container, bg=bg_color)
        task_row.pack(fill='x', pady=(10, 0))

        tk.Label(task_row, text="Focus Task:", font=("Arial", 9, "bold"), bg=bg_color, fg=text_color).pack(side='left', padx=(0, 5))

        self.task_selector = ttk.Combobox(task_row, state="readonly", font=("Arial", 9))
        self.task_selector.pack(side='left', fill='x', expand=True)

        # Populate initial task list
        self.update_task_selector_list()

        # Initialize timer with default duration (25 minutes)
        default_minutes = 25
        self.total_duration_seconds = default_minutes * 60
        self.time_remaining = self.total_duration_seconds
        self.timer_var.set(self.format_time(self.time_remaining))
        self.status_var.set(f"Set for {default_minutes} minutes")

        # Reset taskbar timer progress
        try:
            if hasattr(self, 'taskbar_timer_progress'):
                self.taskbar_timer_progress.configure(maximum=self.total_duration_seconds)
                self.taskbar_timer_progress.configure(value=0)
        except Exception:
            pass
                
    def _prompt_for_task_selection(self):
        """Open a dialog to select a task for the current study session."""
        if not self.app_state.tasks:
            NotificationManager.notify("No Tasks", "Please add some tasks in the Task panel first!")
            return

        dlg = tk.Toplevel(self.parent)
        dlg.title("Select Task")
        dlg.place(relwidth=0.4, relheight=0.6)
        dlg.resizable(False, False)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Which task are you focusing on?", font=("Arial", 12, "bold")).pack(pady=(0, 15))

        # Task list container with scrolling
        list_frame = tk.Frame(frame)
        list_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_frame, bg=self.colors["bg_main"], highlightthickness=0)
        vsb = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.colors["bg_main"])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def select_task(idx):
            self.select_task_for_session(idx)
            dlg.destroy()
            # Now that a task is selected, we can actually start the timer
            self.start_timer(from_resume=False)

        for idx, task in enumerate(self.app_state.tasks):
            # Only show non-done tasks or timed tasks
            if task.get("done"): continue

            btn_text = f"{task['title']} {'(Daily)' if task.get('daily') else ''}"
            btn = create_rounded_button(
                scroll_frame,
                text=btn_text,
                command=lambda i=idx: select_task(i),
                style="secondary",
                radius=10,
                padding=(10, 5),
                font=("Arial", 10)
            )
            btn.pack(fill="x", pady=self.s(2), padx=self.s(5))

        # Option to study without a specific task
        create_rounded_button(
            frame,
            text="Study without a task",
            command=lambda: (setattr(self, 'selected_task_idx', -1), dlg.destroy(), self.start_timer(from_resume=False)),
            style="accent",
            radius=10,
            padding=(10, 5),
            font=("Arial", 10, "bold")
        ).pack(pady=(15, 0))
    
    def _start_timer_after_camera_check(self, from_resume=False):
        """Internal method to start the timer after camera permission is handled.

        Args:
            from_resume (bool): Whether this is being called from resume operation
        """
        # Ensure any existing timer is stopped before starting a new one to prevent duplicates
        self.stop_study_timer()

        if not self.timer_running and self.time_remaining > 0:
            try:
                # Auto-expand timer panel if collapsed
                if not getattr(self, 'timer_expanded', False):
                    self.toggle_timer_panel(force_expand=True)
            except Exception:
                pass
                
            self.timer_running = True
            self.start_pause_btn.config(text="⏸️ Pause")
            self.stop_btn.config(state="normal")
            self.update_timer_ui()

        
        # Timer state is now initialized in __init__

        
        # Study tips are now shown as notifications when the timer starts
        
    def format_time(self, seconds):
        """Format seconds into MM:SS format."""
        mins, secs = divmod(int(seconds), 60)
        return f"{mins:02d}:{secs:02d}"
        
    def set_timer_duration(self, minutes):
        """Set the timer duration in minutes and refresh progress baseline."""
        self.total_duration_seconds = max(1, minutes * 60)
        self.time_remaining = self.total_duration_seconds
        self.study_session_duration = minutes
        self.timer_var.set(self.format_time(self.time_remaining))
        self.status_var.set(f"Set for {minutes} minutes")

        # Reset taskbar timer progress
        try:
            if hasattr(self, 'taskbar_timer_progress'):
                self.taskbar_timer_progress.configure(value=0, maximum=self.total_duration_seconds)
        except Exception as e:
            print(f"Error updating taskbar progress: {e}")

    def set_pomo_duration(self, work_mins, break_mins):
        """Set the Pomodoro work and break durations.
        If the timer is already running, the changes will apply to the next phase.
        """
        self.timer_speed = 1 # Reset speed to normal for preset sessions
        self.pomo_work_duration = work_mins * 60
        self.pomo_break_duration = break_mins * 60

        # If timer is NOT running, we can reset to the new work duration
        if not getattr(self, 'timer_running', False):
            self.pomo_phase = "WORK"
            self.total_duration_seconds = self.pomo_work_duration
            self.time_remaining = self.total_duration_seconds
            self.study_session_duration = work_mins
            self.timer_var.set(self.format_time(self.time_remaining))

        self.status_var.set(f"Pomodoro: {work_mins}m Work / {break_mins}m Break")

        try:
            if hasattr(self, 'taskbar_timer_progress'):
                # Only update maximum if not running, or update it and scale current value
                if not getattr(self, 'timer_running', False):
                    self.taskbar_timer_progress.configure(value=0, maximum=self.total_duration_seconds)
        except Exception:
            pass

    def update_task_selector_list(self):
        """Update the task dropdown with current non-completed tasks."""
        if not hasattr(self, 'task_selector'):
            return

        tasks = getattr(self.app_state, 'tasks', [])
        # Only show tasks that aren't done
        filtered_tasks = [t['title'] for t in tasks if not t.get('done')]

        if not filtered_tasks:
            filtered_tasks = ["No active tasks"]

        self.task_selector['values'] = filtered_tasks
        if not self.task_selector.get():
            self.task_selector.current(0)

    def select_task_for_session(self, task_idx):
        """Link the current study session to a specific task."""
        self.selected_task_idx = task_idx
        task_title = self.app_state.tasks[task_idx]["title"] if task_idx < len(self.app_state.tasks) else "Unknown"
        self.status_var.set(f"Linked to: {task_title}")
        NotificationManager.notify("Task Linked", f"Session now linked to: {task_title}")
            
    def update_timer_ui(self):
        """Tick the countdown timer once and reschedule if still running."""
        if not hasattr(self, 'timer_var') or not hasattr(self, 'time_remaining'):
            return

        if getattr(self, 'timer_running', False):
            # Only decrement time if not paused
            if not getattr(self, 'study_timer_paused', False):
                if self.time_remaining > 0:
                    # Subtract based on timer speed multiplier
                    self.time_remaining -= getattr(self, 'timer_speed', 1)

            self.timer_var.set(self.format_time(self.time_remaining))
            if hasattr(self, 'taskbar_timer_progress') and hasattr(self, 'total_duration_seconds'):
                try:
                    self.taskbar_timer_progress.configure(maximum=self.total_duration_seconds, value=max(0, self.total_duration_seconds - self.time_remaining))
                except Exception:
                    pass
            if self.time_remaining <= 0:
                self.timer_running = False
                self.timer_id = None
                try:
                    self.parent.after(0, self.timer_finished)
                except Exception:
                    pass
            else:
                try:
                    self.timer_id = self.parent.after(1000, self.update_timer_ui)
                except Exception as e:
                    print(f"Error scheduling timer tick: {e}")
                    self.timer_running = False
        else:
            self.timer_var.set(self.format_time(self.time_remaining))
            if hasattr(self, 'taskbar_timer_progress') and hasattr(self, 'total_duration_seconds'):
                try:
                    self.taskbar_timer_progress.configure(maximum=self.total_duration_seconds, value=max(0, self.total_duration_seconds - self.time_remaining))
                except Exception:
                    pass
        
    def start_timer(self, from_resume=False):
        """Start or resume the countdown timer.

        Args:
            from_resume (bool): Whether this is being called from resume operation
        """
        # Ensure any existing timer is stopped before starting a new one to prevent duplicates
        self.stop_study_timer()

        # Task selection before starting
        if not from_resume:
            # Get task from the dropdown instead of prompting with a dialog
            if hasattr(self, 'task_selector'):
                selected_text = self.task_selector.get()
                if selected_text and selected_text != "No active tasks":
                    # Find the index of the task with this title
                    task_idx = next((i for i, t in enumerate(self.app_state.tasks)
                                   if t['title'] == selected_text and not t.get('done')), None)
                    if task_idx is not None:
                        self.select_task_for_session(task_idx)
                    else:
                        self.selected_task_idx = -1 # Study without specific task
                else:
                    self.selected_task_idx = -1 # Study without specific task
            else:
                self.selected_task_idx = -1

        # Check for developer mode and ask for custom time
        if not from_resume and self._check_developer_mode_and_prompt():
            return  # User cancelled or set custom timer will be started later

        # Initialize time_remaining if it doesn't exist
        if not hasattr(self, 'time_remaining') or self.time_remaining <= 0:
            print("Initializing time_remaining")
            # Default to 25 minutes if not set
            self.time_remaining = getattr(self, 'total_duration_seconds', 25 * 60)

        # Make sure we have a valid time to count down from
        if not hasattr(self, 'total_duration_seconds') or self.total_duration_seconds <= 0:
            self.total_duration_seconds = 25 * 60  # Default to 25 minutes

        # Sync progress bar maximum
        try:
            if hasattr(self, 'taskbar_timer_progress'):
                self.taskbar_timer_progress.configure(maximum=self.total_duration_seconds)
        except Exception:
            pass

        self.time_remaining = self.total_duration_seconds

        try:
            # Auto-expand timer panel if collapsed
            if not getattr(self, 'timer_expanded', False):
                self.toggle_timer_panel(force_expand=True)
        except Exception as e:
            print(f"Error toggling timer panel: {e}")

        # Update UI
        self.study_timer_active = True
        self.study_timer_paused = False
        self.timer_running = True
        if hasattr(self, 'start_pause_btn'):
            self.start_pause_btn.config(text="⏸️ Pause", command=self.pause_resume_study_session)


        if hasattr(self, 'stop_btn'):
            self.stop_btn.config(state="normal")

        # Clear any existing timer ID and start the timer
        self.timer_id = None
        self.update_timer_ui()
        
    def timer_finished(self):
        """Handle timer completion and handle session phase transitions (Study -> Break -> Reset)."""
        # Handle Session Transitions
        if self.pomo_phase == "WORK":
            # 1. Reward & Task Update
            self.pomo_cycle_count += 1
            if self.selected_task_idx is not None and 0 <= self.selected_task_idx < len(self.app_state.tasks):
                self.app_state.tasks[self.selected_task_idx]["pomo_count"] = self.app_state.tasks[self.selected_task_idx].get("pomo_count", 0) + 1
                self.app_state.save_data()
                # Redraw tasks panel if it's visible
                if hasattr(self, 'tasks_container'):
                    self.tasks_container._render_timeline()
                    self.tasks_container._render_daily()

            # Reward affection for completing a work block
            try:
                study_minutes = self.pomo_work_duration // 60
                affection_to_add = (study_minutes // 5) * 10
                if affection_to_add > 0:
                    self.app_state.affection += affection_to_add
                    self.update_pet_info_display()
                    NotificationManager.notify("Well Done!", f"+{affection_to_add} Affection for completing a work block!")
            except Exception as e:
                print(f"Error rewarding affection: {e}")

            # 2. Transition to BREAK
            self.pomo_phase = "BREAK"
            self.total_duration_seconds = self.pomo_break_duration
            self.time_remaining = self.total_duration_seconds
            self.status_var.set("Work complete! Time for a break. ☕")
            NotificationManager.notify("Break Time", "Work session finished! Take a short break to recharge.")

            # Enable minigame after completing WORK phase
            self.app_state.minigame_available = True
            self.app_state.save_data()

            # Change progress bar to break color (blue)
            if hasattr(self, 'taskbar_timer_progress'):
                try:
                    self.taskbar_timer_progress.configure(style="Break.Horizontal.TProgressbar")
                except Exception:
                    pass

        else: # pomo_phase == "BREAK"
            # Return to selection state
            self.stop_study_session()
            self.status_var.set("Break finished! Ready for a new session.")
            NotificationManager.notify("Session Cycle Complete", "You've finished a full Work/Break cycle. Ready to start again?")

            # IMPORTANT: Do NOT restart the timer after a break.
            # The user must manually start a new session.
            return

        # Update UI for the new phase
        self.timer_var.set(self.format_time(self.time_remaining))
        if hasattr(self, 'taskbar_timer_progress'):
            self.taskbar_timer_progress['value'] = 0
            self.taskbar_timer_progress['maximum'] = self.total_duration_seconds

        # Automatically restart the timer for the next phase
        self.timer_running = True
        if hasattr(self, 'start_pause_btn'):
            self.start_pause_btn.config(text="⏸️ Pause", command=self.pause_resume_study_session)
        if hasattr(self, 'stop_btn'):
            self.stop_btn.config(state="normal")

        # Kickstart the timer loop for the new phase
        self.update_timer_ui()

    def _show_encouragement_message(self):
        """Show encouragement message on main thread."""

    def _show_encouragement_message(self):
        """Show encouragement message on main thread."""
        try:
            elapsed_minutes = (self.total_duration_seconds - self.time_remaining) / 60
            NotificationManager.notify(
                "💪 Keep Going!",
                f"You studied for {elapsed_minutes:.1f} minute{'s' if elapsed_minutes != 1 else ''}.\n\n"
                "Try to study for at least 5 minutes next time to save your progress!\n\n"
                "You're doing great - every minute counts toward your goals!"
            )
        except Exception as e:
            print(f"Error showing encouragement message: {e}")
            if hasattr(self, 'show_notification'):
                self.show_notification("Keep going! Study a bit more to save progress.")
            else:
                print("Keep going! Study a bit more to save progress.")
    
    def _show_stop_message(self):
        """Show stop message on main thread."""
        try:
            elapsed_seconds = self.total_duration_seconds - self.time_remaining
            elapsed_minutes = elapsed_seconds / 60
            affection_chunks = int(elapsed_minutes) // 5
            affection_points = affection_chunks * 10
            study_text = f"{elapsed_minutes:.1f} minute{'s' if elapsed_minutes != 1 else ''}"
            affection_text = f"+{affection_points} affection" if affection_points > 0 else "no affection"
            NotificationManager.notify(
                "⏹️ Session Stopped",
                f"You studied for {study_text} and earned {affection_text}.\n\n"
                "Your progress has been saved. Keep up the good work!"
            )
        except Exception as e:
            print(f"Error showing stop message: {e}")
            # Fallback notification
            if hasattr(self, 'show_notification'):
                self.show_notification("Session stopped and saved!")
            else:
                print("Session stopped and saved!")

    def _show_completion_message(self):
        """Show completion message on main thread."""
        try:
            study_minutes = int(getattr(self, 'total_duration_seconds', 25 * 60) // 60)
            affection_chunks = study_minutes // 5
            affection_points = affection_chunks * 10
            affection_text = f"+{affection_points} affection" if affection_points > 0 else "no affection"
            NotificationManager.notify(
                "🎉 Session Complete!",
                f"Congratulations! You completed a {study_minutes}-minute study session and earned {affection_text}.\n\n"
                "Great job staying focused! Take a well-deserved break."
            )
        except Exception as e:
            print(f"Error showing completion message: {e}")
            # Fallback notification
            if hasattr(self, 'show_notification'):
                self.show_notification("Timer completed!")
            else:
                print("Timer completed!")
    
    #             # Clear any existing plan frame
    #             if hasattr(self, 'plan_frame'):
    #                 self.plan_frame.destroy()
                
    #             # Create new plan frame in the container
    #             self.plan_frame = tk.Frame(self.plan_frame_container, bg=self.colors["bg_secondary"])
    #             self.plan_frame.pack(fill='x', expand=True)
                
    #             # Recreate the CTA button in the new frame
    #             self.plan_cta = tk.Button(
    #                 self.plan_frame,
    #                 text=f"Start {plan['focus']} Minute Focus Session",
    #                 command=self.begin_study_plan,
    #                 bg=self.colors.get("bg_accent", "#4CAF50"),
    #                 fg=self.colors.get("text_dark", "#333"),
    #                 font=("Arial", 10, "bold"),
    #                 relief="flat",
    #                 padx=10,
    #                 pady=5,
    #                 bd=0,
    #                 activebackground=self.colors.get("bg_accent", "#e0e0e0")
    #             )
    #             self.plan_cta.pack(anchor='w', padx=5, pady=5)
                
    #             # Ensure the container is visible
    #             self.plan_frame_container.pack(fill='x', pady=(10, 0), padx=5, before=None)
                
    #             # Force update to ensure UI is refreshed
    #             self.plan_frame.update_idletasks()
                
    #         except Exception as e:
    #             print(f"Error showing plan frame: {e}")
    #     finally:
    #         try:
    #             window.destroy()
    #         except Exception:
    #             pass

    def begin_study_plan(self):
        """Begin the prepared schedule plan."""
        if not self.scheduled_session_ready or not self.schedule_plan:
            return
        focus = int(self.schedule_plan.get('focus', 25))
        self.set_timer_duration(focus)
        self.start_timer()
        # Hide CTA after starting
        try:
            self.plan_frame.pack_forget()
        except Exception:
            pass
        self.scheduled_session_ready = False


    def update_chat_lock_state(self, force=False):
        """Refresh chat lock state based on current pet stage."""
        try:
            current_pet = self.app_state.get_current_pet()
            if not current_pet or not hasattr(current_pet, 'stage'):
                return

            stage_value = None
            try:
                if hasattr(current_pet.stage, 'value'):
                    stage_value = current_pet.stage.value
                else:
                    stage_value = current_pet.stage
            except Exception as e:
                print(f"Warning: Error getting stage value: {e}")
                return

            should_lock = (stage_value == 1)
            self.chat_locked = should_lock # Update the state
            if force or self.chat_locked is None or should_lock != self.chat_locked:
                self.refresh_chat_ui()
        except Exception as e:
            print(f"Warning: Error in update_chat_lock_state: {e}")


    def create_chat_ui(self, parent_frame):
        """Create a functional AI chat interface in the given parent frame."""
        # Clear existing widgets
        for w in list(parent_frame.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        # Handle Locked State (Egg Stage)
        if getattr(self, 'chat_locked', False):
            # Center container for the locked message
            lock_container = tk.Frame(parent_frame, bg=self.colors["bg_secondary"])
            lock_container.place(relx=0.5, rely=0.5, anchor="center")

            # Lock Header
            lock_header = tk.Label(
                lock_container,
                text="🥚 Chat Locked",
                font=("Arial", 12, "bold"),
                bg=self.colors["bg_secondary"],
                fg=self.colors["text_dark"]
            )
            lock_header.pack(pady=(0, 10))

            # Randomized encouraging message
            random_msg = random.choice(self.locked_chat_messages)
            lock_msg = tk.Label(
                lock_container,
                text=random_msg,
                font=("Arial", 10, "italic"),
                bg=self.colors["bg_secondary"],
                fg=self.colors["text_medium"],
                wraplength=250,
                justify="center"
            )
            lock_msg.pack(pady=(0, 15))

            # Notice about availability
            notice_label = tk.Label(
                lock_container,
                text="Chat will be available after your pet evolves\nand you restart the app!",
                font=("Arial", 9),
                bg=self.colors["bg_secondary"],
                fg=self.colors["text_dark"],
                justify="center"
            )
            notice_label.pack()
            return

        # Use a grid for responsiveness within the panel
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.rowconfigure(1, weight=1)

        # 1. Chat History (Rounded Panel)
        self.chat_history_panel = RoundedPanel(
            parent_frame,
            radius=15,
            bg=self.colors["bg_secondary"],
            padding=15,
            fit_content=False
        )
        self.chat_history_panel.grid(row=1, column=0, sticky="nsew", padx=5, pady=(5, 10))

        # Create a container for text and scrollbar
        chat_text_frame = tk.Frame(self.chat_history_panel.inner, bg=self.colors["bg_secondary"])
        chat_text_frame.pack(fill="both", expand=True)

        self.chat_display = tk.Text(
            chat_text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_dark"],
            bd=0,
            highlightthickness=0,
            state="disabled"
        )

        self.chat_scrollbar = tk.Scrollbar(
            chat_text_frame,
            command=self.chat_display.yview
        )
        self.chat_display.config(yscrollcommand=self.chat_scrollbar.set)

        self.chat_scrollbar.pack(side="right", fill="y")
        self.chat_display.pack(side="left", fill="both", expand=True)

        # 2. Input Area
        self.chat_input_frame = tk.Frame(parent_frame, bg=self.colors["bg_secondary"])
        self.chat_input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

        # Container to center the input and button
        input_container = tk.Frame(self.chat_input_frame, bg=self.colors["bg_secondary"])
        input_container.pack(anchor="center")

        self.chat_entry = tk.Entry(
            input_container,
            font=("Segoe UI", 11),
            bg=self.colors.get("white", "#FFFFFF"),
            fg=self.colors["text_dark"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors.get("silver_accent", "#CCC")
        )
        self.chat_entry.pack(side="left", padx=(0, 5), ipady=5)
        self.chat_entry.bind("<Return>", lambda e: self.send_message())

        self.chat_send_btn = create_rounded_button(
            input_container,
            text="Send 🐾",
            command=self.send_message,
            style="accent",
            radius=12,
            padding=(10, 5),
            font=("Arial", 9, "bold")
        )
        self.chat_send_btn.pack(side="right")

        # 3. AI Disclaimer
        self.chat_disclaimer = tk.Label(
            parent_frame,
            text="StudyPet AI can be wrong and has limited memory. Hehe!",
            font=("Segoe UI", 8, "italic"),
            bg=self.colors["bg_secondary"],
            fg=self.colors.get("text_medium", "#888888"),
            anchor="center"
        )
        self.chat_disclaimer.grid(row=3, column=0, pady=(0, 5), sticky="ew")

        # Initial message
        self.append_message("System", "Server started! I'm ready to chat. ✨")

    def append_message(self, sender, text):
        """Append a message to the chat display."""
        if not hasattr(self, 'chat_display') or not self.chat_display:
            return

        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, f"{sender}: ", "bold")
        self.chat_display.insert(tk.END, f"{text}\n\n")
        self.chat_display.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        self.chat_display.config(state="disabled")

        # Use after to ensure the text is rendered before scrolling to the bottom
        def safe_scroll():
            try:
                if hasattr(self, 'chat_display') and self.chat_display.winfo_exists():
                    self.chat_display.see(tk.END)
            except (tk.TclError, AttributeError):
                pass

        self.parent.after(10, safe_scroll)

    def send_message(self):
        """Handle sending a user message and getting a bot response."""
        user_text = self.chat_entry.get().strip()
        if not user_text:
            return

        self.chat_entry.delete(0, tk.END)
        self.append_message("You", user_text)

        # Disable input while bot thinks
        self.chat_entry.config(state="disabled")
        if hasattr(self, 'chat_send_btn'):
            self.chat_send_btn.set_enabled(False)

        # Run prediction in a separate thread to keep UI responsive
        threading.Thread(target=self._get_bot_response, args=(user_text,), daemon=True).start()

    def _get_bot_response(self, text):
        """Get response from the AI backend and update the UI."""
        print(f"[ChatBot] Processing request: {text}")
        try:
            # Ensure pet name is up to date in the bot
            current_pet = self.app_state.get_current_pet()
            pet_name = getattr(current_pet, 'name', 'StudyPet') if current_pet else 'StudyPet'
            self.chatbot.update_pet_name(pet_name)

            print(f"[ChatBot] Requesting prediction from bot (Pet Name: {pet_name})...")
            response = self.chatbot.predict(text)
            print(f"[ChatBot] Received response: {response}")

            # Update UI on the main thread
            self.parent.after(0, lambda: self.append_message("Pet", response))
        except Exception as e:
            print(f"[ChatBot] Error during prediction: {e}")
            import traceback
            traceback.print_exc()
            self.parent.after(0, lambda: self.append_message("Error", str(e)))
        finally:
            # Re-enable input on the main thread
            self.parent.after(0, lambda: self._enable_chat_input())

    def _enable_chat_input(self):
        """Re-enable the chat input field and send button."""
        if hasattr(self, 'chat_entry'):
            self.chat_entry.config(state="normal")
        if hasattr(self, 'chat_send_btn'):
            self.chat_send_btn.set_enabled(True)
            self.chat_entry.focus_set()


    def refresh_chat_ui(self):
        """Recreate chat UI when lock state may have changed."""
        if not self.chat_panel:
            return
        for chat_widget in self.chat_content.winfo_children():
            chat_widget.destroy()
        self.create_chat_ui(self.chat_content)


    def show_tasks_panel(self):
        """Show the task management panel in a popup window."""
        from ui.simple_theme import simple_theme
        colors = simple_theme.colors

        tasks_window = tk.Toplevel(self.parent)
        tasks_window.title("📅 Study Tasks")

        # Calculate size relative to parent
        parent_w = self.parent.winfo_width() if self.parent.winfo_width() > 1 else 1280
        parent_h = self.parent.winfo_height() if self.parent.winfo_height() > 1 else 720
        win_w = max(self.s(600), int(parent_w * 0.8))
        win_h = max(self.s(400), int(parent_h * 0.8))
        tasks_window.geometry(f"{win_w}x{win_h}")

        tasks_window.minsize(self.s(600), self.s(650))
        tasks_window.resizable(True, True)
        tasks_window.configure(bg=colors.get("bg_main", "#FFFFFF"))

        # Create the TasksPanel inside the window
        # We use fit_content=False so it fills the window and handles its own scrolling
        tasks_panel = TasksPanel(tasks_window, app_state=self.app_state, main_game_screen=self, fit_content=False)
        tasks_panel.pack(fill="both", expand=True, padx=self.s(20), pady=self.s(20))

    def show_statistics(self):
        """Display user and pet statistics in a clean format."""
        if not hasattr(self, 'app_state') or not hasattr(self.app_state, 'user') or not self.app_state.user:
            NotificationManager.notify("Statistics", "No user data available.")
            return

        user = self.app_state.user
        today_stats = user.get_today_stats()
        week_stats = user.get_week_stats()

        # Format statistics message
        stats_message = (
            f"📊 Your Study Statistics\n\n"
            f"📅 Level: {user.level} (XP: {user.experience}/{(user.level) * 100})\n"
            f"🔥 Current Streak: {user.streak_days} days\n"
            f"⏱️  Total Study Time: {user.total_study_time // 60}h {user.total_study_time % 60}m\n\n"
            f"📈 Today's Progress\n"
            f"⏱️  {today_stats['study_time'] // 60}h {today_stats['study_time'] % 60}m studied\n\n"
            f"📆 This Week\n"
            f"⏱️  {week_stats['study_time'] // 60}h {week_stats['study_time'] % 60}m studied"
        )

        # Add pet statistics if available
        if hasattr(self.app_state, 'current_pet') and self.app_state.current_pet:
            pet = self.app_state.current_pet
            stats_message += f"\n\n🐾 Pet: {pet.name if hasattr(pet, 'name') and pet.name else 'Unnamed'}"
            stats_message += f"\n❤️  Affection: {pet.affection if hasattr(pet, 'affection') else 0}"
            if hasattr(pet, 'stage'):
                stats_message += f"\n📈 Stage: {pet.stage.name if hasattr(pet.stage, 'name') else 'Egg'}"

        NotificationManager.notify("Your Study Statistics", stats_message)

    def switch_tab(self, tab_name):
        """Switch to different tab/functionality."""
        if tab_name == "tasks":
            self.show_tasks_panel()
        elif tab_name == "schedule":
            NotificationManager.notify("Schedule", "📅 Study schedule feature coming soon!")
        elif tab_name == "stats":
            # Save current data before showing statistics
            try:
                if hasattr(self, 'app_state') and hasattr(self.app_state, 'save_data'):
                    self.app_state.save_data()
            except Exception as e:
                print(f"Error saving data before showing stats: {e}")
            self.show_statistics()
        elif tab_name == "music":
            self.show_music_player()
        elif tab_name == "settings":
            self.show_settings()

    def setup_dynamic_fonts(self):
        """Initialize dynamic font sizing system."""
        # Store current font sizes for dynamic scaling
        self.base_font_sizes = {
            "title": 32,
            "subtitle": 18,
            "button": 10,
            "label": 9,
            "small": 8
        }

    def update_music_button_states(self):
        """Update main nav bar music controls based on playback state."""
        try:
            available_tracks = self.music_player.get_available_tracks()
            if available_tracks:
                # Ensure widgets are visible
                try:
                    self.music_label.pack_info()
                except tk.TclError:
                    self.music_label.pack(side="left", padx=(0, 5))
                try:
                    self.prev_button.pack_info()
                except tk.TclError:
                    self.prev_button.pack(side="left", padx=self.s(2))
                try:
                    self.play_pause_button.pack_info()
                except tk.TclError:
                    self.play_pause_button.pack(side="left", padx=self.s(2))
                try:
                    self.next_button.pack_info()
                except tk.TclError:
                    self.next_button.pack(side="left", padx=self.s(2))
                # Update play/pause text
                if self.music_player.is_music_playing():
                    self._btn_set_text(self.play_pause_button, "⏸️")
                else:
                    self._btn_set_text(self.play_pause_button, "▶️")
                # Always enable prev/next
                self._btn_set_enabled(self.prev_button, True)
                self._btn_set_enabled(self.next_button, True)
            else:
                # Hide if nothing to show
                self.music_label.pack_forget()
                self.play_pause_button.pack_forget()
                self.prev_button.pack_forget()
                self.next_button.pack_forget()
        except AttributeError:
            pass

    def _btn_set_text(self, btn, text):
        """Set text on a rounded button."""
        try:
            if hasattr(btn, 'set_text'):
                btn.set_text(text)
            else:
                btn.config(text=text)
        except Exception:
            pass

    def _btn_set_enabled(self, btn, enabled):
        """Enable/disable a button."""
        try:
            if hasattr(btn, 'set_enabled'):
                btn.set_enabled(enabled)
            else:
                btn.config(state="normal" if enabled else "disabled")
        except Exception:
            pass

    def previous_track_and_update(self):
        """Go to previous track and update UIs."""
        if self.music_player.previous_track():
            self.update_music_displays()

    def next_track_and_update(self):
        """Go to next track and update UIs."""
        if self.music_player.next_track():
            self.update_music_displays()

    def toggle_music_playback(self):
        """Toggle music play/pause from main nav bar button."""
        available_tracks = self.music_player.get_available_tracks()
        if not available_tracks:
            NotificationManager.notify(
                "No Music Found",
                "No music files found in the bgm folder!\n\n"
                "To add background music:\n"
                "1. Add MP3, WAV, OGG, or M4A files to the bgm folder\n"
                "2. Open the Music window to refresh"
            )
            return
        current_track = self.music_player.get_current_track_info()
        if not current_track:
            # Auto-select and play the first available track (no popup)
            if self.music_player.play_track(0):
                self.update_music_displays()
                self.update_music_button_states()
            return
        if self.music_player.is_music_playing():
            self.music_player.pause()
        else:
            self.music_player.resume()
        self.update_music_displays()
        self.update_music_button_states()

    def update_music_displays(self):
        """Update current track label and play/pause button in music window, then nav bar."""
        try:
            current_track = self.music_player.get_current_track_info()
            current_text = current_track["name"] if current_track else "No track selected"
            try:
                if hasattr(self, 'current_track_label') and self.current_track_label.winfo_exists():
                    self.current_track_label.configure(text=current_text)
            except Exception:
                pass

            # Update tick marks on track buttons in the music window (if open)
            try:
                if hasattr(self, 'music_track_buttons') and isinstance(self.music_track_buttons, list):
                    for idx, btn, track_name in list(self.music_track_buttons):
                        try:
                            if not btn.winfo_exists():
                                continue
                            is_current = bool(current_track) and current_track.get('name') == track_name
                            btn_text = f"🎵 {track_name}" + ("  ✓" if is_current else "")
                            self._btn_set_text(btn, btn_text)
                        except Exception:
                            pass
            except Exception:
                pass

            # Music window play/pause button may exist even after the window was closed;
            # guard against updating a destroyed widget so the main nav still updates.
            try:
                if hasattr(self, 'music_play_pause_btn') and self.music_play_pause_btn.winfo_exists():
                    if self.music_player.is_music_playing():
                        self._btn_set_text(self.music_play_pause_btn, "⏸️")
                    else:
                        self._btn_set_text(self.music_play_pause_btn, "▶️")
            except Exception:
                pass

            self.update_music_button_states()
        except AttributeError:
            pass

    def show_music_player(self):
        """Show music player controls in a popup."""
        from src.ui.pet_theme import apply_pet_theme
        from ui.simple_theme import simple_theme

        apply_pet_theme(app_state=self.app_state)
        colors = simple_theme.colors

        music_window = tk.Toplevel(self.parent)
        music_window.title("🎵 Music Player")

        # Calculate size relative to parent
        parent_w = self.parent.winfo_width() if self.parent.winfo_width() > 1 else 1280
        parent_h = self.parent.winfo_height() if self.parent.winfo_height() > 1 else 720
        win_w = max(self.s(420), int(parent_w * 0.5))
        win_h = max(self.s(460), int(parent_h * 0.7))
        music_window.geometry(f"{win_w}x{win_h}")

        music_window.minsize(self.s(420), self.s(460))
        music_window.resizable(True, True)
        music_window.configure(bg=colors.get("bg_main", "#FFFFFF"))

        style = ttk.Style(music_window)
        style.configure("Music.TFrame", background=colors.get("bg_main", "#FFFFFF"))
        style.configure(
            "Music.TLabel",
            background=colors.get("bg_main", "#FFFFFF"),
            foreground=colors.get("text_dark", "#000000"),
        )
        style.configure(
            "Music.Title.TLabel",
            background=colors.get("bg_main", "#FFFFFF"),
            foreground=colors.get("text_dark", "#000000"),
            font=("Arial", 18, "bold"),
        )
        style.configure(
            "Music.Subtitle.TLabel",
            background=colors.get("bg_main", "#FFFFFF"),
            foreground=colors.get("text_medium", colors.get("text_dark", "#000000")),
            font=("Arial", 12, "bold"),
        )
        style.configure(
            "Music.TLabelframe",
            background=colors.get("bg_main", "#FFFFFF"),
            foreground=colors.get("text_dark", "#000000"),
        )
        style.configure(
            "Music.TLabelframe.Label",
            background=colors.get("bg_main", "#FFFFFF"),
            foreground=colors.get("text_dark", "#000000"),
            font=("Arial", 10, "bold"),
        )
        style.configure(
            "Music.TButton",
            padding=(10, 6),
        )
        style.configure(
            "Music.Horizontal.TScale",
            background=colors.get("bg_main", "#FFFFFF"),
            troughcolor=colors.get("bg_secondary", "#F5F5F5"),
        )

        # Main container with scrollable frame
        main_canvas = tk.Canvas(
            music_window,
            highlightthickness=0,
            bd=0,
            bg=colors.get("bg_main", "#FFFFFF"),
        )
        scrollbar = ttk.Scrollbar(music_window, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas, style="Music.TFrame")

        # Update scrollregion when frame changes
        def update_scrollregion(event=None):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))

        scrollable_frame.bind("<Configure>", update_scrollregion)

        content_window_id = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="n")

        def _sync_canvas_width(event):
            try:
                main_canvas.itemconfigure(content_window_id, width=event.width)
                update_scrollregion()  # Update scrollregion after width sync
            except Exception:
                pass

        main_canvas.bind("<Configure>", _sync_canvas_width)
        main_canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            main_canvas.unbind_all("<MouseWheel>")

        main_canvas.bind("<Enter>", _bind_mousewheel)
        main_canvas.bind("<Leave>", _unbind_mousewheel)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Music controls frame
        controls_frame = ttk.Frame(scrollable_frame, padding=(24, 18), style="Music.TFrame")
        controls_frame.pack(fill="both", expand=True, anchor="n")

        # Title
        ttk.Label(controls_frame, text="🎵 Music Player", style="Music.Title.TLabel").pack(pady=(0, 18), anchor="center")

        # Current track info
        now_playing_frame = ttk.LabelFrame(controls_frame, text="Now Playing", padding=15, style="Music.TLabelframe")
        now_playing_frame.pack(fill="x", pady=(0, 14), anchor="center")

        current_track = self.music_player.get_current_track_info()
        current_text = current_track["name"] if current_track else "No track selected"

        self.current_track_label = ttk.Label(now_playing_frame, text=current_text, style="Music.Subtitle.TLabel")
        self.current_track_label.pack(anchor="center")

        # Playback controls
        playback_frame = ttk.LabelFrame(controls_frame, text="Playback Controls", padding=15, style="Music.TLabelframe")
        playback_frame.pack(fill="x", pady=(0, 14), anchor="center")

        button_frame = tk.Frame(playback_frame, bg=colors.get("bg_main", "#FFFFFF"))
        button_frame.pack(anchor="center")

        # Control buttons
        create_rounded_button(
            button_frame,
            text="⏮️ Previous",
            command=lambda: self.previous_track_and_update(),
            radius=15,
            padding=(10, 6),
            font=("Arial", 9, "bold"),
            style="accent"
        ).grid(row=0, column=0, padx=self.s(5), pady=self.s(5))

        play_pause_btn = create_rounded_button(
            button_frame,
            text="⏸️ Pause" if self.music_player.is_music_playing() else "▶️ Play",
            command=lambda: self.toggle_music_and_update(),
            radius=15,
            padding=(10, 6),
            font=("Arial", 9, "bold"),
            style="accent"
        )
        play_pause_btn.grid(row=0, column=1, padx=self.s(5), pady=self.s(5))

        # Store reference for dynamic updates
        self.music_play_pause_btn = play_pause_btn

        create_rounded_button(
            button_frame,
            text="⏭️ Next",
            command=lambda: self.next_track_and_update(),
            radius=15,
            padding=(10, 6),
            font=("Arial", 9, "bold"),
            style="accent"
        ).grid(row=0, column=2, padx=self.s(5), pady=self.s(5))

        # Stop button
        create_rounded_button(
            button_frame,
            text="⏹️ Stop",
            command=lambda: self.stop_music_and_update(),
            radius=15,
            padding=(10, 6),
            font=("Arial", 9, "bold"),
            style="accent"
        ).grid(row=1, column=1, padx=self.s(5), pady=self.s(5))

        # Volume control
        volume_frame = ttk.LabelFrame(controls_frame, text="Volume Control", padding=15, style="Music.TLabelframe")
        volume_frame.pack(fill="x", pady=(0, 14), anchor="center")

        volume_control_frame = ttk.Frame(volume_frame, style="Music.TFrame")
        volume_control_frame.pack(fill="x", anchor="center")

        ttk.Label(volume_control_frame, text="🔈", style="Music.TLabel", font=("Arial", 12)).pack(side="left", padx=(0, 10))

        volume_scale = ttk.Scale(
            volume_control_frame,
            from_=0, to=100,
            orient="horizontal",
            command=lambda v: self.music_player.set_volume(float(v)/100),
            style="Music.Horizontal.TScale",
        )
        volume_scale.set(self.music_player.get_volume() * 100)
        volume_scale.pack(side="left", fill="x", expand=True)

        ttk.Label(volume_control_frame, text="🔊", style="Music.TLabel", font=("Arial", 12)).pack(side="left", padx=(10, 0))

        # Available tracks
        tracks_frame = ttk.LabelFrame(controls_frame, text="Track Library", padding=15, style="Music.TLabelframe")
        tracks_frame.pack(fill="both", expand=True, pady=(0, 14), anchor="center")

        available_tracks = self.music_player.get_available_tracks()
        if available_tracks:
            # Store references so we can update the "✓" indicator live
            self.music_track_buttons = []
            for i, track in enumerate(available_tracks):
                track_frame = tk.Frame(tracks_frame, bg=colors.get("bg_main", "#FFFFFF"))
                track_frame.pack(fill="x", pady=2, anchor="center")

                current_track = self.music_player.get_current_track_info()
                is_current = current_track and current_track.get('name') == track['name']

                btn_text = f"🎵 {track['name']}" + ("  ✓" if is_current else "")
                track_button = create_rounded_button(
                    track_frame,
                    text=btn_text,
                    command=lambda idx=i: self.select_track_and_update(idx),
                    radius=12,
                    padding=(self.s(8),  self.s(4)),
                    font=("Arial", 9),
                    style="secondary"
                )
                track_button.pack(fill="x")
                self.music_track_buttons.append((i, track_button, track['name']))

        # Close button
        close_btn_frame = tk.Frame(controls_frame, bg=colors.get("bg_main", "#FFFFFF"))
        close_btn_frame.pack(pady=(10, 6), anchor="center")
        create_rounded_button(
            close_btn_frame,
            text="❌ Close Player",
            command=music_window.destroy,
            radius=15,
            padding=(10, 6),
            font=("Arial", 9, "bold"),
            style="primary"
        ).pack()

    def select_track_and_update(self, track_index):
        """Select a track and immediately start playing it, then update UIs."""
        if self.music_player.play_track(track_index):
            self.update_music_displays()
            self.update_music_button_states()

    def toggle_music_and_update(self):
        """Toggle music in player window and refresh buttons."""
        current_track = self.music_player.get_current_track_info()
        if not current_track:
            NotificationManager.notify(
                "No Track Selected",
                "Please choose a track first!\n\n"
                "Click on any track name in the Track Library to select it,"
                "then press Play to start listening."
            )
            return
        self.music_player.toggle_playback()
        self.update_music_displays()
        self.update_music_button_states()

    def stop_music_and_update(self):
        """Stop playback and hide main nav play button."""
        self.music_player.stop_playback()
        self.update_music_displays()
        try:
            self.play_pause_button.pack_forget()
        except AttributeError:
            pass

    def toggle_developer_mode(self):
        """Toggle developer mode on/off."""
        self.developer_mode = not self.developer_mode
        self.refresh_developer_ui()
        
        # Save the state
        self.app_state.settings['developer_mode'] = self.developer_mode
        self.app_state.save_settings()

    def _init_drowsiness_detector(self) -> bool:
        """Drowsiness detection is disabled in the Neo StudyPet replica."""
        self.drowsiness_detector = None
        return False

    def _show_speech_bubble(self, message):
        """Show a speech bubble with the given message."""
        if self.speech_bubble_visible:
            return
            
        try:
            # Load the speech bubble image if not already loaded
            if self.speech_bubble_image is None:
                bubble_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "assets", "img", "Speech_Bubble.png"
                )
                if os.path.exists(bubble_path):
                    self.speech_bubble_image = Image.open(bubble_path)
                    self.speech_bubble_image = self.speech_bubble_image.resize((200, 100), Image.Resampling.LANCZOS)
                    self.speech_bubble_photo = ImageTk.PhotoImage(self.speech_bubble_image)
                else:
                    print(f"Speech bubble image not found at {bubble_path}")
                    return
            
            # Create the speech bubble label if it doesn't exist
            if not hasattr(self, 'speech_bubble_label') or not self.speech_bubble_label.winfo_exists():
                self.speech_bubble_label = tk.Label(
                    self.frame,
                    image=self.speech_bubble_photo,
                    borderwidth=0,
                    highlightthickness=0,
                    bg=self.colors["bg_primary"]
                )
                
                # Position the speech bubble near the pet
                self.speech_bubble_label.place(relx=0.7, rely=0.3, anchor='center')
                
                # Add text to the speech bubble
                self.speech_text = tk.Label(
                    self.speech_bubble_label,
                    text=message,
                    wraplength=160,
                    justify='center',
                    bg='white',
                    fg='black',
                    font=('Arial', 10)
                )
                self.speech_text.place(relx=0.5, rely=0.5, anchor='center')
            else:
                # Update existing speech bubble
                self.speech_text.config(text=message)
                self.speech_bubble_label.lift()
                
            self.speech_bubble_visible = True
            
            # Schedule hiding the speech bubble after 5 seconds
            if hasattr(self, '_speech_bubble_timer'):
                self.frame.after_cancel(self._speech_bubble_timer)
            self._speech_bubble_timer = self.frame.after(5000, self._hide_speech_bubble)
            
        except Exception as e:
            print(f"Error showing speech bubble: {e}")
    
    def _show_notification(self, title, message):
        """Show a system notification."""
        try:
            NotificationManager.notify(
                title=title,
                message=message
            )
        except Exception as e:
            print(f"Error showing notification: {e}")

    def show_notification(self, message, title="StudyPet"):
        """Public single-argument notification helper used throughout the screen."""
        self._show_notification(title, message)

    def _start_drowsiness_detection(self):
        """No-op: drowsiness detection is disabled in the Neo StudyPet replica."""
        return
    
    def _handle_prolonged_drowsiness(self):
        """Handle when user is drowsy for a prolonged period."""
        self.consecutive_drowsy_sessions += 1
        
        # Show speech bubble with encouraging message
        message = random.choice(self.encouraging_messages)
        self._show_speech_bubble(message)
        
        # Show notification
        self._show_notification("Stay Focused!", message)
        
        # If this is the 3rd force stop the session
        if self.consecutive_drowsy_sessions >= 3:
            self._handle_excessive_drowsiness()
    
    def _handle_excessive_drowsiness(self):
        """Handle when user is consistently not focusing."""
        # Stop the current session
        was_running = self.study_timer_active and not self.study_timer_paused
        if was_running:
            self.stop_study_session()
        
        # Show speech bubble with rest message
        rest_message = random.choice(self.rest_messages)
        self._show_speech_bubble(rest_message)
        
        # Show notification
        self._show_notification("Time for a Break!", rest_message)
        
        # Reset counter
        self.consecutive_drowsy_sessions = 0
    
    def _stop_drowsiness_detection(self):
        """No-op: drowsiness detection is disabled in the Neo StudyPet replica."""
        try:
            self.drowsiness_detection_active = False
            self._drowsiness_stop_event.set()
        except Exception:
            pass
        self.drowsiness_detector = None
    
    def _handle_drowsiness_detected(self):
        """No-op: drowsiness detection is disabled in the Neo StudyPet replica."""
        return
    
    def show_settings(self):
        """Show unified settings window."""
        try:
            # Get has_dev_key from app_controller if available
            has_dev_key = getattr(self.app_controller, 'has_dev_key', False)
            
            # Pass correct arguments including has_dev_key and game_screen reference
            show_unified_settings(
                parent=self.parent, 
                app_state=self.app_state,
                title="StudyPet Settings - Game Screen",
                has_dev_key=has_dev_key,
                game_screen=self  # Pass self as game_screen for proper cleanup
            )
        except Exception as e:
            error_msg = f"Could not open settings: {str(e)}"
            print(f"Error in show_settings: {error_msg}")
            NotificationManager.error(
                "Error",
                error_msg
            )

    def handle_window_resize(self, event):
        """Handle window resize events."""
        try:
            # Check if parent exists and has the after method
            if not hasattr(self, 'parent') or not hasattr(self.parent, 'after'):
                return
                
            # Cancel any pending resize
            if hasattr(self, '_resize_after_id') and self._resize_after_id is not None:
                try:
                    self.parent.after_cancel(self._resize_after_id)
                except (tk.TclError, AttributeError):
                    pass
            
            # Schedule the update
            try:
                self._resize_after_id = self.parent.after(150, self.update_pet_info_display)
            except (tk.TclError, AttributeError):
                self._resize_after_id = None
        except Exception as e:
            print(f"Error in handle_window_resize: {e}")
            import traceback
            traceback.print_exc()

    def add_affection(self, amount=50):
        """
        Add affection points to the current pet using the global state.
        
        Args:
            amount (int): Amount of affection to add (default: 50)
        """
        
        try:
            # Store old stage to check for evolution
            old_stage = self.app_state.stage
            
            # Add affection (this will handle the cap automatically)
            self.app_state.affection += amount
            
            # Update the UI
            self.update_pet_info_display()
            
            # Show a small notification
            if hasattr(self, 'show_notification'):
                self.show_notification(f"+{amount} Affection!")
            
            # Check for evolution
            if self.app_state.stage != old_stage:
                NotificationManager.notify(
                    "Pet Evolved!",
                    f"Your pet has evolved to {self.app_state.stage.name.replace('_', ' ').title()}!"
                )

            print(f"Added {amount} affection points. New total: {self.app_state.affection}")
            
        except Exception as e:
            print(f"Error updating affection: {e}")
            import traceback
            traceback.print_exc()
            
    def subtract_affection(self, amount=20):
        """
        Subtract affection points from the current pet using the global state.
        
        Args:
            amount (int): Amount of affection to subtract (default: 20)
        """
        
        try:
            # Store old affection for notification
            old_affection = self.app_state.affection
            
            # Subtract affection (ensuring it doesn't go below 0)
            new_affection = max(0, old_affection - amount)
            self.app_state.affection = new_affection
            
            # Update the UI
            self.update_pet_info_display()
            
            # Show a small notification
            if hasattr(self, 'show_notification'):
                self.show_notification(f"-{amount} Affection!")
                
            print(f"Subtracted {amount} affection points. New total: {new_affection}")
            
        except Exception as e:
            print(f"Error subtracting affection: {e}")
            import traceback
            traceback.print_exc()

    def set_pet_stage(self):
        """Open a dialog to set the pet's stage directly."""
        from tkinter import simpledialog
        
        try:
            current_stage = self.app_state.stage
            
            stage = simpledialog.askinteger(
                "Set Pet Stage",
                f"Enter stage (1-5):\n1. Egg\n2. Baby\n3. Child\n4. Grown\n5. Battle Fit\n\nCurrent: {current_stage.name.replace('_', ' ').title()} ({current_stage.value})",
                parent=self.parent,
                minvalue=1,
                maxvalue=5
            )
            
            if stage is not None:
                # Convert to PetStage enum
                new_stage = PetStage(stage)
                self.app_state.stage = new_stage
                
                # Update UI
                self.update_pet_info_display()
                
                # Show success message
                NotificationManager.notify(
                    "Stage Updated",
                    f"Pet stage set to {new_stage.name.replace('_', ' ').title()}"
                )

                print(f"Pet stage set to {new_stage.name}")
                
        except Exception as e:
            print(f"Error setting pet stage: {e}")
            import traceback
            traceback.print_exc()
            NotificationManager.error("Error", f"Failed to set stage: {e}")

    def set_pet_emotion(self):
        """Set the pet's emotion through a dialog."""
        from tkinter import simpledialog
        
        try:
            current_emotion = self.app_state.emotion
            
            # Show dialog to select new emotion
            emotion_names = [e.name for e in PetEmotion]
            emotion = simpledialog.askstring(
                "Set Pet Emotion",
                f"Current emotion: {current_emotion.name}\n\n"
                f"Available emotions: {', '.join(emotion_names)}\n"
                "Enter new emotion:",
                parent=self.parent
            )
            
            if emotion and emotion.upper() in emotion_names:
                # Set the new emotion
                self.app_state.emotion = PetEmotion[emotion.upper()]
                
                # Update the UI
                self.update_pet_info_display()
                
                # Show a small notification
                if hasattr(self, 'show_notification'):
                    self.show_notification(f"Pet emotion changed to {emotion.upper()}")
                
                print(f"Pet emotion changed to {emotion.upper()}")
            
        except Exception as e:
            print(f"Error resetting affection: {e}")
            import traceback
            traceback.print_exc()

    def force_evolve(self):
        """Force the pet to evolve to the next stage using the global state."""
        
        try:
            # Store current stage before evolving
            old_stage = self.app_state.stage
            
            # Check if already at max stage
            if old_stage == PetStage.BATTLE_FIT:
                if hasattr(self, 'show_notification'):
                    self.show_notification("Max stage reached!")
                NotificationManager.notify(
                    "Max Stage",
                    "Your pet is already at the maximum evolution stage!"
                )
                return
                
            # Move to next stage
            self.app_state.stage = PetStage(old_stage.value + 1)
            
            # Update UI
            self.update_pet_info_display()
            
            # Show evolution message
            NotificationManager.notify(
                "Pet Evolved!",
                f"Your pet has evolved from {old_stage.name.replace('_', ' ').title()} to {self.app_state.stage.name.replace('_', ' ').title()}!"
            )

            print(f"Pet force evolved to {self.app_state.stage.name}")
            
        except Exception as e:
            print(f"Error forcing evolution: {e}")
            import traceback
            traceback.print_exc()

    def _handle_pet_evolution(self, old_stage, new_stage):
        """Handle pet evolution event by updating the display."""
        try:
            print(f"Pet evolved from {old_stage.name} to {new_stage.name}")
            
            # Update the pet info display
            self.update_pet_info_display()
            
            # Reinitialize the playground with the new stage
            current_pet = self.app_state.get_current_pet()
            if current_pet and hasattr(self, 'playground_canvas'):
                # Ensure pet_type is a string
                pet_type = str(current_pet.pet_type)
                if hasattr(current_pet.pet_type, 'value'):  # If it's an enum with value
                    pet_type = str(current_pet.pet_type.value)
                elif hasattr(current_pet.pet_type, 'name'):  # If it's an enum with name
                    pet_type = str(current_pet.pet_type.name)
                
                # Also ensure emotion is a string
                emotion = getattr(current_pet, 'emotion', 'HAPPY')
                if hasattr(emotion, 'name'):  # If it's an enum
                    emotion = emotion.name
                
                # Reinitialize the playground with pet type
                # Stage and emotion will be taken from self.app_state
                self._init_playground_immediately(pet_type
                )
                
                # Show evolution notification
                if hasattr(self, 'show_notification'):
                    self.show_notification(f"Evolved to {new_stage.name.replace('_', ' ').title()}!")
                    
        except Exception as e:
            print(f"Error handling pet evolution: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_developer_ui(self):
        """Update developer UI elements based on current state."""
        if hasattr(self, 'dev_tools_frame'):
            if self.developer_mode:
                self.dev_tools_frame.pack(fill="x", pady=(self.s(10), self.s(5)), padx=self.s(5))
                # Update status panel height if expanded
                if hasattr(self, 'status_expanded') and self.status_expanded and hasattr(self, 'status_container'):
                    self.status_container.place_configure(height=self.s(460), relheight=0)
            else:
                self.dev_tools_frame.pack_forget()
                # Reset status panel height if expanded
                if hasattr(self, 'status_expanded') and self.status_expanded and hasattr(self, 'status_container'):
                    self.status_container.place_configure(height=self.s(240), relheight=0)

    # -------------------------------------------------------------------------
    # Missing method implementations (restored)
    # -------------------------------------------------------------------------

    def stop_timer(self):
        """Stop the countdown timer and reset to start state."""
        if not self.timer_running and self.time_remaining == getattr(self, 'total_duration_seconds', 25 * 60):
            return  # Nothing to stop

        # Cancel any scheduled tick
        if hasattr(self, 'timer_id') and self.timer_id:
            try:
                self.parent.after_cancel(self.timer_id)
            except Exception:
                pass
            self.timer_id = None

        self.timer_running = False
        self.time_remaining = getattr(self, 'total_duration_seconds', 25 * 60)

        if hasattr(self, 'timer_var'):
            self.timer_var.set(self.format_time(self.time_remaining))
        if hasattr(self, 'start_pause_btn'):
            self.start_pause_btn.config(text="Start", command=self.start_timer)
        if hasattr(self, 'stop_btn'):
            self.stop_btn.config(state="disabled")
        if hasattr(self, 'taskbar_timer_progress'):
            try:
                self.taskbar_timer_progress.configure(value=0)
            except Exception:
                pass

        self.show_notification("Session stopped and saved!")

    def reset_affection(self):
        """Reset the current pet's affection to zero (dev tool)."""
        try:
            self.app_state.affection = 0
            self.update_pet_info_display()
            self.show_notification("Affection reset to 0")
        except Exception as e:
            print(f"Error resetting affection: {e}")

    def _hide_speech_bubble(self):
        """Hide the speech bubble overlay if visible."""
        try:
            if hasattr(self, 'speech_bubble_label') and self.speech_bubble_label:
                try:
                    if self.speech_bubble_label.winfo_exists():
                        self.speech_bubble_label.place_forget()
                except Exception:
                    pass
            self.speech_bubble_visible = False
        except Exception as e:
            print(f"Error hiding speech bubble: {e}")

    def _check_developer_mode_and_prompt(self) -> bool:
        """Check if developer mode is active and prompt for a custom timer duration.

        Returns:
            True  – caller should return early (user cancelled or set custom time).
            False – proceed with normal timer start.
        """
        if not getattr(self, 'developer_mode', False):
            return False  # Normal mode: just start

        try:
            from tkinter import simpledialog
            raw = simpledialog.askstring(
                "Developer Mode",
                "Enter custom timer duration (minutes), or cancel for default:",
                parent=self.parent,
            )
            if raw is None:
                return False  # User cancelled → fall through to default start
            minutes = float(raw.strip())
            if minutes <= 0:
                raise ValueError("Must be positive")
            self.total_duration_seconds = int(minutes * 60)
            self.time_remaining = self.total_duration_seconds
            if hasattr(self, 'timer_var'):
                self.timer_var.set(self.format_time(self.time_remaining))
            if hasattr(self, 'taskbar_timer_progress'):
                try:
                    self.taskbar_timer_progress.configure(value=0, maximum=self.total_duration_seconds)
                except Exception:
                    pass
            return False  # Proceed to start with the new duration
        except (ValueError, TypeError):
            self.show_notification("Invalid duration — using default.")
            return False

    def start_minigame(self):
        """Start the minigame session."""
        if not self.app_state.minigame_available:
            NotificationManager.notify("Minigame Unavailable", "You've already played the minigame! Complete a study session to unlock it again.")
            return

        # Disable minigame and persist
        self.app_state.minigame_available = False
        self.app_state.save_data()

        # Minigame state
        self.minigame_active = True
        self.minigame_score = 0

        # Create Stop Game button
        self.btn_stop_game = create_rounded_button(
            self.frame,
            text="Stop Game",
            command=self.stop_minigame,
            style="accent",
            radius=25,
            padding=(15, 10),
            font=("Arial", 12, "bold")
        )
        # Position bottom-right
        self.btn_stop_game.place(relx=0.95, rely=0.95, anchor='se')

        # Tell playground to start spawning circles
        if self.playground_renderer:
            self.playground_renderer.start_minigame(self)

        NotificationManager.notify("🎮 Minigame Started!", "Eat as many circles as you can!")

    def stop_minigame(self):
        """Stop the minigame session and reward the user."""
        if not hasattr(self, 'minigame_active') or not self.minigame_active:
            return

        self.minigame_active = False

        # Get score from playground renderer
        score = 0
        if self.playground_renderer:
            score = getattr(self.playground_renderer, 'circles_eaten', 0)

        # Reward: for every 10 circles (round up), add 10 affection
        import math
        reward = math.ceil(score / 10) * 10

        if reward > 0:
            self.app_state.affection += reward
            self.update_pet_info_display()
            NotificationManager.notify("🎮 Game Over!", f"You ate {score} circles and earned +{reward} affection!")
        else:
            NotificationManager.notify("🎮 Game Over!", f"You ate {score} circles. Try harder next time!")

        # Cleanup UI
        if hasattr(self, 'btn_stop_game'):
            self.btn_stop_game.destroy()

        # Tell playground to clear circles
        if self.playground_renderer:
            self.playground_renderer.stop_minigame()



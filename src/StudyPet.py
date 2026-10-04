import sys
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

"""
StudyPet - AI-powered virtual pet study companion

Main application entry point that manages the GUI, screens, and application lifecycle.
This class handles screen navigation, state management, and resource cleanup.

Author: CookLaye
Version: 1.0
"""

import os
import sys

# Add project root to Python path to allow imports from 'src' package
# This is necessary when running the script as 'python src/StudyPet.py'
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Do NOT add 'src' to sys.path to avoid duplicate module imports (e.g., 'src.models' vs 'models')

import warnings
import gc
from typing import Optional

# ── DPI awareness (must happen before any GUI toolkit initialises) ──────────
# On Windows, Tkinter renders at 96 DPI by default and Windows upscales it,
# which makes text and widgets look blurry on HiDPI / 4K displays.
# Setting Per-Monitor DPI awareness tells Windows to let Tk draw at native
# resolution so everything stays sharp.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-Monitor v1
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()    # Fallback: System DPI
        except Exception:
            pass

# ── System font selection ────────────────────────────────────────────────────
# These fonts are hinted for on-screen readability and render emoji correctly.
if sys.platform == "win32":
    UI_FONT   = "Segoe UI"
    MONO_FONT = "Cascadia Code"   # falls back gracefully if not installed
elif sys.platform == "darwin":
    UI_FONT   = "SF Pro Text"
    MONO_FONT = "SF Mono"
else:
    UI_FONT   = "Ubuntu"
    MONO_FONT = "Ubuntu Mono"

# Configure environment variables before importing libraries
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Suppress TensorFlow oneDNN warnings
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'  # Suppress pygame support message
os.environ.setdefault('OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS', '0')  # STUDYPET-LAUNCHER-FIX: faster, more reliable Windows webcam start-up
os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'  # Allow screensaver during gameplay

# Configure warning filters
warnings.filterwarnings("ignore", category=UserWarning, module="pygame.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources.*")

import tkinter as tk
from tkinter import font as tkfont
from src.utils.notifications import NotificationManager
import pygame

# Local imports
from src.screens.greeting_screen import GreetingScreen
from src.screens.pet_selection_screen import PetSelectionScreen
from src.screens.hatch_screen import HatchScreen
from src.screens.main_game_screen import MainGameScreen
from src.models.app_state import AppState
from src.models.pet import PetType, Pet  # Import Pet class for pet creation
from src.utils.music_player import MusicPlayer
from src.ui.simple_theme import simple_theme
from src.utils.session_manager import SessionManager

# Application constants
DEFAULT_WINDOW_TITLE = "StudyPet"
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
DEFAULT_FULLSCREEN_SIZE = "1200x800"
USER_DATA_DIR = "user_data"
SAVE_DATA_FILE = "save_data.json"
DEV_MODE_KEY_FILE = "dev_mode.key"

# Font configuration — use the system UI font chosen above for crisp rendering
FONT_CONFIGURATIONS = [
    ("TkDefaultFont",  UI_FONT, 11),
    ("TkTextFont",     UI_FONT, 11),
    ("TkMenuFont",     UI_FONT, 10),
    ("TkTooltipFont",  UI_FONT, 10),
    ("TkCaptionFont",  UI_FONT, 10),
    ("TkFixedFont",    MONO_FONT, 11),
]
MIN_FONT_SIZE = 10
MAX_FONT_SIZE = 13

class VirtualPetStudyApp:
    """
    Main application controller for StudyPet.

    Manages the Tkinter GUI, screen navigation, application state,
    and resource cleanup. Handles the complete application lifecycle
    from initialization to shutdown.

    Attributes:
        root: Main Tkinter window
        app_state: Global application state manager
        current_screen: Currently active screen instance
        music_player: Background music player
        session_manager: User session data manager
    """

    def __init__(self):
        """Initialize the StudyPet application."""
        # Initialize main window
        self.root = tk.Tk()
        self.root.title(DEFAULT_WINDOW_TITLE)

        # Set up cleanup handler for window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Check for development mode
        self.has_dev_key = self._check_dev_key()

        # Configure application icon and appearance
        self._set_application_icon()
        self._configure_fonts()
        self._configure_window()

        # Initialize core components
        self.app_state = self._initialize_app_state()
        self.app_state.start_session()  # Create crash marker
        self.music_player = MusicPlayer()
        self.music_player.play_random_default()
        self.music_player.queue_analysis_for_library()
        self.session_manager = self._initialize_session_manager()

        # Start with greeting screen
        self.current_screen = None
        self.show_greeting()
        self._schedule_auto_save()

    def _schedule_auto_save(self):
        """Periodically save application state to prevent data loss."""
        try:
            if hasattr(self, 'app_state') and hasattr(self.app_state, 'save_data'):
                self.app_state.save_data()
        except Exception as e:
            print(f"Error during auto-save: {e}")

        # Schedule next auto-save in 5 minutes
        if hasattr(self, 'root') and self.root:
            self.root.after(300000, self._schedule_auto_save)

    def _check_dev_key(self) -> bool:
        """Check if development mode key file exists.

        Returns:
            bool: True if dev_mode.key exists, False otherwise
        """
        dev_key_path = os.path.join(project_root, DEV_MODE_KEY_FILE)
        return os.path.exists(dev_key_path)

    def _configure_fonts(self) -> None:
        """Configure global font settings with DPI-aware scaling.

        tk scaling controls how Tkinter converts font point sizes to pixels.
        Default is 96/72 ≈ 1.333 (96 DPI baseline). Setting it to actual_DPI/72
        makes every widget — including those with hardcoded ("Arial", 10) tuples —
        render at the same physical size as before the DPI awareness fix, but at
        native resolution so text is sharp rather than upscaled-blurry.
        """
        try:
            dpi = self.root.winfo_fpixels('1i')   # true pixels-per-inch
            self.root.tk.call('tk', 'scaling', dpi / 72.0)
        except Exception:
            pass

        for font_name, family, size in FONT_CONFIGURATIONS:
            try:
                font = tkfont.nametofont(font_name)
                font.configure(family=family, size=size)
            except (tk.TclError, ValueError) as e:
                print(f"Warning: Could not configure font {font_name}: {e}")

    def _configure_window(self) -> None:
        """Configure main window properties and event bindings."""
        # Set window state and size constraints
        self.root.state('zoomed')
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.resizable(True, True)

        # Bind keyboard shortcuts
        self.root.bind('<F11>', self.toggle_fullscreen)

        # Apply theme
        self.root.configure(bg=simple_theme.get_color("bg_main"))

    def _initialize_app_state(self) -> 'AppState':
        """Initialize application state with error handling.

        Returns:
            AppState: Initialized application state instance
        """
        try:
            app_state = AppState.load_or_create()
            app_state.root = self.root

            return app_state
        except Exception as e:
            print(f"Error initializing app state: {e}")
            # Create minimal working state as fallback
            app_state = AppState()
            app_state.root = self.root
            return app_state
        except Exception as e:
            print(f"Error initializing app state: {e}")
            # Create minimal working state as fallback
            app_state = AppState()
            app_state.root = self.root
            return app_state

    def _initialize_session_manager(self) -> Optional['SessionManager']:
        """Initialize session manager for data persistence.

        Returns:
            SessionManager: Initialized session manager or None if failed
        """
        try:
            user_data_dir = os.path.join(project_root, USER_DATA_DIR)
            os.makedirs(user_data_dir, exist_ok=True)
            return SessionManager(
                self.app_state,
                os.path.join(user_data_dir, 'save_data.json')  # Keep for compatibility but won't be used
            )
        except Exception as e:
            print(f"Error initializing session manager: {e}")
            return None

    def _set_application_icon(self) -> None:
        """Set application icon with multiple fallback options.

        Tries different icon formats and locations, falling back to
        system default if none are available.
        """
        icon_paths = [
            os.path.join(project_root, 'assets', 'img', 'Axos.ico'),
            os.path.join(project_root, 'assets', 'img', 'Axos.png'),
            os.path.join(project_root, 'Axos.ico'),
            os.path.join(project_root, 'Axos.png')
        ]

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                    return
                except (tk.TclError, AttributeError) as e:
                    print(f"Warning: Could not load icon {icon_path}: {e}")
                    continue

        # Fallback to system default icon
        try:
            self.root.iconbitmap()
        except tk.TclError as e:
            print(f"Warning: Could not set default icon: {e}")

    def show_greeting(self) -> Optional['GreetingScreen']:
        """Display the greeting screen with proper cleanup and theme refresh.

        Returns:
            GreetingScreen: The created greeting screen instance, or None if failed
        """
        self._reset_window_title()
        self._stress_gate_done = False      # next entry to the main screen starts with the check-in
        self._cleanup_current_screen()

        try:
            self.current_screen = GreetingScreen(
                parent=self.root,
                on_start_callback=self.handle_start_game,
                app_state=self.app_state,
                app_controller=self
            )

            # Apply theme and refresh UI
            if hasattr(self.current_screen, 'refresh_theme'):
                self.current_screen.refresh_theme()
            self.root.update_idletasks()

            return self.current_screen

        except Exception as e:
            print(f"Error creating greeting screen: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _reset_window_title(self) -> None:
        """Reset window title to default."""
        if hasattr(self, 'root') and self.root:
            self.root.title(DEFAULT_WINDOW_TITLE)

    def _cleanup_current_screen(self) -> None:
        """Safely cleanup and destroy the current screen."""
        if self.current_screen and hasattr(self.current_screen, 'destroy'):
            try:
                # Call cleanup method if it exists
                if hasattr(self.current_screen, 'cleanup'):
                    self.current_screen.cleanup()
                self.current_screen.destroy()
            except (tk.TclError, AttributeError) as e:
                print(f"Warning: Error destroying screen: {e}")
        self.current_screen = None

    def show_pet_selection(self) -> Optional['PetSelectionScreen']:
        """Display the pet selection screen.

        Returns:
            PetSelectionScreen: The created pet selection screen, or None if failed
        """
        self._cleanup_current_screen()

        try:
            self.current_screen = PetSelectionScreen(
                self.root,
                on_pet_selected_callback=self.handle_pet_selected
            )
            self.root.update_idletasks()
            return self.current_screen

        except Exception as e:
            print(f"Error creating pet selection screen: {e}")
            import traceback
            traceback.print_exc()
            return None

    def show_hatch_screen(self):
        """Show the click-to-hatch screen for a chosen but unhatched pet."""
        self._cleanup_current_screen()
        self._update_window_title_with_pet()
        try:
            self.current_screen = HatchScreen(
                parent=self.root,
                app_state=self.app_state,
                on_hatched_callback=self.handle_hatched,
            )
            self.root.update_idletasks()
            return self.current_screen
        except Exception as e:
            print(f"Error creating hatch screen: {e}")
            import traceback; traceback.print_exc()
            # Fail safe: never strand the user on a broken screen. Hatch instantly and continue.
            self.app_state.hatch_pet()
            return self.show_main_game()

    def handle_hatched(self):
        """Called by HatchScreen after the pet has been hatched (stage is now BABY)."""
        self.show_main_game()

    def show_main_game(self, access_mode="full") -> Optional['MainGameScreen']:
        """Display the main game screen with pet-specific theme.

        Returns:
            MainGameScreen: The created main game screen, or None if failed
        """
        # An unhatched pet (stage EGG == 1) must never reach the main screen.
        # Covers: quit-during-hatch, old saves stuck on Egg, legacy saves.
        try:
            if self.app_state.pet_type is not None and self.app_state.stage.value == 1:
                return self.show_hatch_screen()
        except Exception as e:
            print(f"Warning: hatch check failed: {e}")

        # Stress check-in: the main screen stays hidden until it is done (once per launch)
        if not getattr(self, "_stress_gate_done", False):
            return self.show_stress_gate()

        self._cleanup_current_screen()
        self._update_window_title_with_pet()

        try:
            self.current_screen = MainGameScreen(
                self.root,
                self.app_state,
                self.music_player,
                app_controller=self,
                session_manager=self.session_manager,
                access_mode=access_mode,
            )
            # Ensure pet theme is applied and UI refreshed on first run
            # MainGameScreen already calls setup_pet_theme in __init__, but we re-apply to be safe
            if hasattr(self.current_screen, 'setup_pet_theme'):
                self.current_screen.setup_pet_theme()
            # MainGameScreen has no refresh_theme method; theme is applied via setup_pet_theme
            # Force a UI update to ensure colors are applied
            self.root.update_idletasks()
            return self.current_screen

        except Exception as e:
            print(f"❌ Error creating MainGameScreen: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to greeting screen
            self.show_greeting()
            return None

    def show_stress_gate(self):
        """Full-screen stress check-in shown before the main screen."""
        self._cleanup_current_screen()
        self._update_window_title_with_pet()
        try:
            from screens.stress_gate_screen import StressGateScreen
            self.current_screen = StressGateScreen(
                self.root, self.app_state, self.music_player,
                on_finished=self._on_stress_gate_finished,
            )
            self.root.update_idletasks()
            return self.current_screen
        except Exception as e:
            print(f"Error creating stress gate: {e}")
            import traceback
            traceback.print_exc()
            # Fail safe: never strand the user on a broken screen.
            self._stress_gate_done = True
            return self.show_main_game()

    def _on_stress_gate_finished(self, access_mode="full"):
        """Called by the gate: 'full' or 'restricted'."""
        self._stress_gate_done = True
        self.show_main_game(access_mode=access_mode)

    def _update_window_title_with_pet(self) -> None:
        """Update window title to include current pet's name."""
        try:
            current_pet = self.app_state.get_current_pet()
            if current_pet and hasattr(current_pet, 'name') and current_pet.name:
                self.root.title(f"{DEFAULT_WINDOW_TITLE} - {current_pet.name}")
            else:
                self.root.title(DEFAULT_WINDOW_TITLE)
        except Exception as e:
            print(f"Warning: Could not update window title: {e}")
            self.root.title(DEFAULT_WINDOW_TITLE)

    def handle_start_game(self) -> None:
        """Handle start game action from greeting screen.

        Routes to appropriate screen based on whether user is first-time.
        """
        if self.app_state.is_first_time_user():
            self.show_pet_selection()
        else:
            self.show_main_game()

    def handle_pet_selected(self, pet_type: PetType, pet_name: str) -> None:
        """Handle pet selection and transition to main game screen.

        Args:
            pet_type: The type of pet to create
            pet_name: The name to assign to the pet

        Creates a new pet instance, updates application state,
        and navigates to the main game screen.
        """
        if not pet_type:
            NotificationManager.error("Error", "No pet type specified")
            return

        try:
            # Use the AppState set_selected_pet method to ensure all fields are set
            self.app_state.set_selected_pet(pet_type, pet_name or "")

            # Update window title and navigate to main game
            self._update_window_title_with_pet()
            self.root.update_idletasks()
            self.show_hatch_screen()

        except Exception as e:
            self._handle_pet_selection_error(e)

    def _save_app_data(self) -> None:
        """Save application data with error handling."""
        try:
            self.app_state.save_data()
        except (IOError, OSError) as e:
            print(f"Warning: Could not save pet data: {e}")

    def _handle_pet_selection_error(self, error: Exception) -> None:
        """Handle errors during pet selection process.

        Args:
            error: The exception that occurred
        """
        error_msg = f"Failed to select pet: {str(error)}"
        print(f"Error in handle_pet_selected: {error_msg}")

        try:
            NotificationManager.error("Error", error_msg)
        except Exception as msg_err:
            print(f"Could not show error message: {msg_err}")

        # Attempt recovery
        self._attempt_screen_recovery()

    def _attempt_screen_recovery(self) -> None:
        """Attempt to recover from screen errors by showing fallback screens."""
        try:
            self.show_pet_selection()
        except Exception as recover_err:
            print(f"Failed to recover to pet selection: {recover_err}")
            try:
                self.show_greeting()
            except Exception as fatal_err:
                print(f"Fatal error: Could not recover to any screen: {fatal_err}")
                self.root.quit()

    def force_theme_refresh_all_screens(self) -> None:
        """Force theme refresh on current screen with error handling."""
        if not hasattr(self, 'current_screen') or not self.current_screen:
            return

        if hasattr(self.current_screen, 'refresh_theme'):
            try:
                self.current_screen.refresh_theme()
                self.root.update_idletasks()
            except (AttributeError, tk.TclError) as e:
                print(f"Warning: Error refreshing theme: {e}")

    def _reinitialize_app_state(self) -> bool:
        """
        Reinitialize the application state after a reset.

        Returns:
            bool: True if reinitialization was successful, False otherwise
        """
        try:
            # Clear existing state
            if hasattr(self, 'app_state'):
                try:
                    if hasattr(self.app_state, 'reset_data'):
                        self.app_state.reset_data()
                except Exception as e:
                    print(f"Error resetting app state: {e}")

            # Reinitialize the app state
            from src.models.app_state import AppState
            self.app_state = AppState()
            self.app_state.root = self.root

            # Reinitialize session manager with proper error handling
            try:
                user_data_dir = os.path.join(project_root, 'user_data')
                os.makedirs(user_data_dir, exist_ok=True)
                self.session_manager = SessionManager(
                    self.app_state,
                    os.path.join(user_data_dir, 'save_data.json')  # Keep for compatibility but won't be used
                )
            except Exception as e:
                print(f"Error reinitializing session manager: {e}")
                # Continue with a basic session manager if initialization fails
                self.session_manager = None

            # Reset the music player
            try:
                if hasattr(self, 'music_player'):
                    self.music_player.cleanup()
                self.music_player = MusicPlayer()
                self.music_player.play_random_default()
                self.music_player.queue_analysis_for_library()
            except Exception as e:
                print(f"Error reinitializing music player: {e}")
                self.music_player = None

            # Force garbage collection
            import gc
            gc.collect()

            return True

        except Exception as e:
            print(f"Critical error reinitializing app state: {e}")
            return False

    def reset_to_default_greeting(self):
        """
        Reset the application to its initial state and show the greeting screen.
        This performs a complete cleanup of all resources and resets all states.
        """
        from src.models.pet import PetStage, PetEmotion

        # Show confirmation dialog
        if not NotificationManager.confirm(
            "Reset Application",
            "Are you sure you want to reset the application?\n"
            "All your data will be permanently deleted and the pet will be reset to its initial state."
        ):
            return False

        try:
            # 1. Reset window title to default immediately
            if hasattr(self, 'root') and self.root:
                self.root.title("StudyPet")
                self.root.update_idletasks()

            # 2. Clean up current screen if it exists
            if hasattr(self, 'current_screen') and self.current_screen:
                try:
                    # Call cleanup method if it exists
                    if hasattr(self.current_screen, 'cleanup'):
                        self.current_screen.cleanup()

                    # Destroy the screen's frame if it exists
                    if hasattr(self.current_screen, 'frame') and self.current_screen.frame:
                        try:
                            frame = self.current_screen.frame
                            # Check if frame still exists
                            try:
                                if not frame.winfo_exists():
                                    return

                                # Unbind all events to prevent memory leaks
                                for sequence in frame.bind():
                                    try:
                                        frame.unbind_all(sequence)
                                    except tk.TclError:
                                        pass

                                # Destroy all children widgets safely
                                for widget in frame.winfo_children():
                                    try:
                                        if widget.winfo_exists():
                                            widget.destroy()
                                    except (tk.TclError, AttributeError) as e:
                                        if "can't invoke" not in str(e):
                                            print(f"Warning: Error destroying widget: {e}")

                                # Destroy the frame itself if it still exists
                                if frame.winfo_exists():
                                    frame.destroy()

                            except tk.TclError as e:
                                if "can't invoke" not in str(e):
                                    print(f"Warning: Error accessing frame: {e}")

                        except Exception as e:
                            print(f"Error during frame cleanup: {e}")

                    # Clear the reference
                    self.current_screen = None

                    # Force garbage collection
                    import gc
                    gc.collect()

                except Exception as e:
                    print(f"Error during screen cleanup: {e}")

            # 3. Reset application state
            if hasattr(self, 'app_state') and hasattr(self.app_state, 'reset_data'):
                if not self.app_state.reset_data():
                    NotificationManager.warn(
                        "Reset Warning",
                        "Some data may not have been fully reset.\n"
                        "The application will continue with a fresh state."
                    )

            # 4. Reinitialize app state to get fresh data
            try:
                self.app_state = AppState.load_or_create()
                self.app_state.root = self.root
            except Exception as e:
                print(f"Error reinitializing app state: {e}")
                self.app_state = AppState()
                self.app_state.root = self.root

            # 5. Reset pet state to default values
            try:
                # Reset pet stage to EGG
                self.app_state.stage = PetStage.EGG
                # Reset emotion to HAPPY
                self.app_state.emotion = PetEmotion.HAPPY
                # Reset affection to 0
                self.app_state.affection = 0

                # Save the reset state
                self.app_state.save_data()
                print("Pet state reset to default values")
            except Exception as e:
                print(f"Error resetting pet state: {e}")

            # 6. Reset the session manager with new app state
            user_data_dir = os.path.join(project_root, 'user_data')
            os.makedirs(user_data_dir, exist_ok=True)
            self.session_manager = SessionManager(
                self.app_state,
                os.path.join(user_data_dir, 'save_data.json')  # Keep for compatibility but won't be used
            )

            # 7. Clear any remaining references
            if hasattr(self, 'frame') and self.frame:
                try:
                    self.frame.destroy()
                    self.frame = None
                except Exception as e:
                    print(f"Error cleaning up main frame: {e}")

            # 8. Force update the UI to reflect changes
            if hasattr(self, 'root') and self.root:
                self.root.update_idletasks()

            # 9. Show the greeting screen with fresh state
            self.show_greeting()

            # Show success message
            NotificationManager.notify(
                "Reset Complete",
                "Successfully reset! Ready for a new adventure!"
            )

            return True

        except Exception as e:
            print(f"Error during reset: {e}")
            import traceback
            traceback.print_exc()
            NotificationManager.error(
                "Reset Error",
                "An error occurred while resetting the application.\n"
                f"Error: {str(e)}\n"
                "Please restart the application."
            )
            return False

    def toggle_fullscreen(self, event: Optional[tk.Event] = None) -> None:
        """Toggle fullscreen mode with proper window sizing.

        Args:
            event: The keyboard event that triggered this function
        """
        current_state = self.root.attributes('-fullscreen')
        new_state = not current_state
        self.root.attributes('-fullscreen', new_state)

        if not new_state:
            # Center window when exiting fullscreen
            self.root.geometry(DEFAULT_FULLSCREEN_SIZE)
            self.root.update_idletasks()
            x = (self.root.winfo_screenwidth() // 2) - (1200 // 2)
            y = (self.root.winfo_screenheight() // 2) - (800 // 2)
            self.root.geometry(f"{DEFAULT_FULLSCREEN_SIZE}+{x}+{y}")

    def _on_close(self) -> None:
        """Handle application close event with proper cleanup.

        Saves pet state only when closing from main game screen to prevent
        unnecessary saves from other screens. Cleans up all resources.
        """
        print("[REPRO] VirtualPetStudyApp._on_close called")
        try:
            # Save pet state if on main game screen
            self._save_pet_state_on_close()

            # End session marker (deletes .runtime file)
            if hasattr(self, 'app_state'):
                self.app_state.end_session()

            # Cleanup resources
            self._cleanup_resources()
        except Exception as e:
            print(f"Critical error during close cleanup: {e}")
        finally:
            # Close application - MUST always happen
            self._shutdown_application()

    def _save_pet_state_on_close(self) -> None:
        """Save pet state and application data on close."""
        print("[REPRO] VirtualPetStudyApp._save_pet_state_on_close called")
        if hasattr(self, 'current_screen') and self.current_screen is not None:
            try:
                from src.screens.main_game_screen import MainGameScreen
                if isinstance(self.current_screen, MainGameScreen):
                    self.app_state.save_data()

                    if hasattr(self, 'app_state') and hasattr(self.app_state, 'flush_run_study_time'):
                        self.app_state.flush_run_study_time()
                    print("✅ Pet state saved successfully")
                else:
                    print("ℹ️  Not saving - not on main game screen")
            except Exception as e:
                print(f"⚠️ Error saving pet state on close: {e}")
        else:
            print("ℹ️  No active screen - skipping save")

        # Always attempt to save general application data (XP, streaks, etc.)
        try:
            if hasattr(self, 'app_state') and hasattr(self.app_state, 'save_data'):
                self.app_state.save_data()
                print("✅ Application state saved successfully")
        except Exception as e:
            print(f"Warning: Could not save application state on close: {e}")

        # Runtime backup cleanup is handled in _on_close via app_state.end_session()

    def _cleanup_resources(self) -> None:
        """Cleanup application resources."""
        if hasattr(self, 'music_player'):
            try:
                self.music_player.stop_playback()
            except Exception as e:
                print(f"⚠️ Error stopping music player: {e}")

    def _shutdown_application(self) -> None:
        """Safely shutdown the application."""
        try:
            self.root.destroy()
        except (KeyboardInterrupt, Exception) as e:
            print(f"⚠️ Error destroying root window: {e}")
            # Force exit if destroy fails or is interrupted
            os._exit(0)

    def run(self) -> None:
        """Start the main application loop."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            try:
                self._on_close()
            except KeyboardInterrupt:
                # If interrupted again during cleanup, force exit
                os._exit(0)
        except Exception as e:
            print(f"Unexpected error: {e}")
            try:
                self._on_close()
            except Exception:
                os._exit(0)

def main() -> None:
    """Main entry point for the StudyPet application."""
    app = VirtualPetStudyApp()
    app.run()

if __name__ == "__main__":
    main()

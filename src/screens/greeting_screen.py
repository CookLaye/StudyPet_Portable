"""
Greeting Screen - The startup screen of the Virtual Pet Study App
"""

import tkinter as tk
from tkinter import ttk
from utils.notifications import NotificationManager
from ui.simple_theme import simple_theme, create_styled_button, create_rounded_button
from ui.rounded_widgets import RoundedPanel

from ui.pet_theme import apply_pet_theme
from ui.unified_settings import show_unified_settings

class GreetingScreen:
    """Greeting screen with app title and start button."""
    
    def __init__(self, parent, on_start_callback, app_state=None, app_controller=None):
        self.parent = parent
        self.on_start_callback = on_start_callback
        self.app_state = app_state
        self.app_controller = app_controller
        self.frame = None
        try:
            self.ui_scale = parent.winfo_fpixels('1i') / 96.0
        except Exception:
            self.ui_scale = 1.0
        self.s = lambda px: max(1, round(px * self.ui_scale))

        # Initialize theme based on selected pet
        self.setup_pet_theme()
        self.create_widgets()
    
    def setup_pet_theme(self):
        """Set up theme based on selected pet."""
        self.theme = simple_theme
        apply_pet_theme(app_state=self.app_state)
        self.colors = self.theme.colors

    def refresh_theme(self):
        """Refresh the theme based on current pet selection."""
        self.setup_pet_theme()

        # Update existing widgets with new colors
        if self.frame:
            self.parent.configure(bg=self.colors["bg_main"])
            self.frame.configure(bg=self.colors["bg_main"])

            # Update title colors if they exist
            for widget in self.frame.winfo_children():
                if hasattr(widget, 'inner'):  # RoundedPanel
                    widget.configure(bg=self.colors["bg_main"])
                    widget.inner.configure(bg=self.colors["bg_secondary"])
                    for child in widget.inner.winfo_children():
                        if isinstance(child, tk.Frame):
                            child.configure(bg=self.colors["bg_secondary"])
                            # Update title labels
                            for label in child.winfo_children():
                                if isinstance(label, tk.Label):
                                    if "StudyPet" in label.cget("text"):
                                        label.configure(fg=self.colors["text_pink"])
                                    elif "Virtual Study Companion" in label.cget("text"):
                                        label.configure(fg=self.colors["text_medium"])
                                elif hasattr(label, 'bg_normal'):  # Start button
                                    # Use unified theme system
                                    try:
                                        from src.ui.pet_theme import apply_pet_theme
                                        apply_pet_theme(app_state=self.app_state)
                                        theme = simple_theme
                                        colors = theme.colors
                                        
                                        label.bg_normal = colors.get("bg_primary", colors.get("accent", "#BDBDBD"))
                                        label.bg_hover = colors.get("bg_primary_hover", colors.get("accent_hover", "#AFAFAF"))
                                        label.bg_active = colors.get("bg_primary_active", colors.get("accent_active", "#9E9E9E"))
                                        label.fg = colors.get("button_primary_text", colors.get("text_primary", "#FFFFFF"))
                                        label.draw()
                                    except Exception as e:
                                        print(f"Warning: Could not update start button colors: {e}")

                                    
            # Update button colors if buttons exist
            for widget in self.frame.winfo_children():
                if isinstance(widget, tk.Frame):  # Bottom frame containing buttons
                    for child in widget.winfo_children():
                        if hasattr(child, 'bg_normal'):  # RoundedButton
                            # Use unified theme system for all buttons
                            try:
                                from src.ui.pet_theme import apply_pet_theme
                                apply_pet_theme(app_state=self.app_state)
                                theme = simple_theme
                                colors = theme.colors
                                
                                if hasattr(child, 'text'):
                                    button_text = child.text
                                    if "START" in button_text:
                                        # Primary button - use high contrast colors
                                        child.bg_normal = colors.get("bg_primary", colors.get("accent", "#BDBDBD"))
                                        child.bg_hover = colors.get("bg_primary_hover", colors.get("accent_hover", "#AFAFAF"))
                                        child.bg_active = colors.get("bg_primary_active", colors.get("accent_active", "#9E9E9E"))
                                        child.fg = colors.get("button_primary_text", colors.get("text_primary", "#FFFFFF"))
                                    else:
                                        # Secondary buttons (Settings, About) - ensure good contrast
                                        child.bg_normal = colors.get("bg_secondary", "#6E6E6E")
                                        child.bg_hover = colors.get("bg_secondary_hover", "#5A5A5A")
                                        child.bg_active = colors.get("bg_secondary_active", "#4A4A4A")
                                        child.fg = colors.get("button_secondary_text", colors.get("text_secondary", "#000000"))
                                else:
                                    # Default to secondary style
                                    child.bg_normal = colors.get("bg_secondary", "#6E6E6E")
                                    child.bg_hover = colors.get("bg_secondary_hover", "#5A5A5A")
                                    child.bg_active = colors.get("bg_secondary_active", "#4A4A4A")
                                    child.fg = colors.get("text_secondary", "#FFFFFF")
                                
                                child.draw()
                            except Exception as e:
                                print(f"Warning: Could not update button colors: {e}")

    def create_widgets(self):
        """Create and layout the greeting screen widgets with simple theme."""
        # Configure parent background
        self.parent.configure(bg=self.colors["bg_main"])
        
        # Main frame with theme
        self.frame = tk.Frame(self.parent, bg=self.colors["bg_main"])
        self.frame.pack(fill="both", expand=True, padx=30, pady=30)
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=0)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Title section with beautiful rounded background
        title_panel = RoundedPanel(self.frame, radius=60, bg=self.colors["bg_secondary"], padding=16)
        title_panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))
        
        title_frame = tk.Frame(title_panel.inner, bg=self.colors["bg_secondary"])
        title_frame.pack(expand=True, pady=20)
        
        # App title
        title_label = tk.Label(
            title_frame,
            text="StudyPet",
            font=("Comic Sans MS", 32, "bold"),
            fg=self.colors["text_pink"],  # Use pet-specific pink accent
            bg=self.colors["bg_secondary"]
        )
        title_label.pack(pady=(40, 20))
        
        # Subtitle with enhanced styling
        subtitle_label = tk.Label(
            title_frame,
            text="Learn and Relaxolotl!",
            font=("Arial", 18, "bold"),
            fg=self.colors["text_medium"],  # Use pet-specific medium text color
            bg=self.colors["bg_secondary"]
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Start button with enhanced styling
        start_button = create_rounded_button(
            title_frame,
            text="START!",
            command=self.on_start_clicked,
            style="primary",
            radius=20,
            padding=(30, 15),
            font=("Arial", 16, "bold")
        )
        start_button.pack(pady=20)
        start_button.update_idletasks()

        # Bottom buttons frame with theme
        bottom_frame = tk.Frame(self.frame, bg=self.colors["bg_main"])
        bottom_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)

        # Settings button with styling
        settings_button = create_rounded_button(
            bottom_frame,
            text="Settings",
            command=self.show_settings,
            style="secondary",
            radius=20
        )
        settings_button.grid(row=0, column=0, sticky="w", padx=20, pady=(10, 20))

        # About button with styling
        about_button = create_rounded_button(
            bottom_frame,
            text="About",
            command=self.show_about,
            style="secondary",
            radius=20
        )
        about_button.grid(row=0, column=1, sticky="e", padx=20, pady=(10, 20))

        # Update button colors to match pet theme
        self.update_button_colors(start_button, settings_button, about_button)

    def update_button_colors(self, start_button, settings_button, about_button):
        """Update button colors to match the current pet theme using unified system."""
        # Use the unified theme system - no duplicate color definitions
        try:
            # Apply current pet theme to ensure colors are up to date
            if hasattr(self, 'app_state') and self.app_state:
                from src.ui.pet_theme import apply_pet_theme
                apply_pet_theme(app_state=self.app_state)
            
            # Get theme colors from simple_theme
            theme = simple_theme
            colors = theme.colors
            
            # Update start button (use primary/accent colors)
            if hasattr(start_button, 'bg_normal'):
                start_button.bg_normal = colors.get("bg_primary", colors.get("accent", "#BDBDBD"))
                start_button.bg_hover = colors.get("bg_primary_hover", colors.get("accent_hover", "#AFAFAF"))
                start_button.bg_active = colors.get("bg_primary_active", colors.get("accent_active", "#9E9E9E"))
                start_button.fg = colors.get("button_primary_text", colors.get("text_primary", "#FFFFFF"))
                start_button.draw()
            
            # Update settings and about buttons (use secondary colors)
            for button in [settings_button, about_button]:
                if hasattr(button, 'bg_normal'):
                    button.bg_normal = colors.get("bg_secondary", "#6E6E6E")
                    button.bg_hover = colors.get("bg_secondary_hover", "#5A5A5A")
                    button.bg_active = colors.get("bg_secondary_active", "#4A4A4A")
                    button.fg = colors.get("button_secondary_text", colors.get("text_secondary", "#000000"))
                    button.draw()
        except Exception as e:
            print(f"Warning: Could not update button colors: {e}")
            # Fallback to default behavior if theme system fails
    
    def on_start_clicked(self):
        """Handle start button click."""
        if self.on_start_callback:
            self.on_start_callback()

    def show_settings(self):
        """Show unified settings dialog."""
        try:
            # Get has_dev_key from app_controller if available
            has_dev_key = getattr(self.app_controller, 'has_dev_key', False)
            
            show_unified_settings(
                parent=self.parent, 
                app_state=self.app_state, 
                title="StudyPet Settings - Welcome Screen",
                has_dev_key=has_dev_key,
                game_screen=None  # No game screen when called from greeting
            )
        except Exception as e:
            print(f"Error showing settings: {e}")
            NotificationManager.error(
                "Error",
                "Could not open settings. Please try again."
            )

    def show_about(self):
        """Show about dialog."""
        NotificationManager.alert(
            "About StudyPet",
            "StudyPet v1.5\n\n" +
            "A gamified learning companion featuring virtual pets " +
            "that evolve based on your study progress.\n\n" +
            "Features:\n" +
            "• Clean and modern interface\n" +
            "• 5-emotion system (Happy, Worried, Hungry, Sad, Angry)\n" +
            "• Dynamic theming based on selected pet\n" +
            "• Scrollable interfaces for small screens\n" +
            "• 5 different pet types with evolution stages\n" +
            "• Smart emotion system with context awareness\n" +
            "• Study timer with pet encouragement\n" +
            "• Interactive chat with your pet companion\n" +
            "• Built-in music player with focus tracks\n\n"
        )
    
    def destroy(self):
        """Clean up the screen."""
        if self.frame:
            self.frame.destroy()
            self.frame = None
"""
Pet Selection Screen - First-time user pet selection interface
"""

import tkinter as tk
from tkinter import ttk
from utils.notifications import NotificationManager
from src.models.pet import PetType
from graphics.pet_graphics import pet_graphics
from ui.simple_theme import simple_theme, create_styled_button, create_rounded_button
from ui.rounded_widgets import RoundedPanel

class PetSelectionScreen:
    """Screen for selecting a virtual pet for first-time users."""
    
    def __init__(self, parent, on_pet_selected_callback):
        self.parent = parent
        self.on_pet_selected_callback = on_pet_selected_callback
        self.frame = None
        self.selected_pet_type = None
        self.pet_name_var = tk.StringVar(value="")
        try:
            self.ui_scale = parent.winfo_fpixels('1i') / 96.0
        except Exception:
            self.ui_scale = 1.0
        self.s = lambda px: max(1, round(px * self.ui_scale))

        # Initialize container references to None to prevent AttributeError
        self.egg_container = None
        self.preview_emoji = None
        self.text_frame = None
        self.preview_name = None
        self.preview_description = None
        self.confirm_button = None
        self.name_entry = None
        self.pet_buttons = {}
        self.pet_image_labels = {}
        self._deferred_pet_selection = None
        self._deferred_retry_count = 0
        
        # Pet display information - Axolotl first as main pet
        self.pet_info = {
            PetType.AXOLOTL: {
                "type_name": "axolotl", 
                "name": "Axolotl", 
                "description": "🌟 Main companion! Regenerative genius that absorbs knowledge like water!"
            },
            PetType.CAT: {
                "type_name": "cat",
                "name": "Cat", 
                "description": "Playful but can get worried, loves to learn new things!"
            },
            PetType.DOG: {
                "type_name": "dog", 
                "name": "Dog", 
                "description": "Loyal and energetic, always ready for study sessions!"
            },
            PetType.RACCOON: {
                "type_name": "raccoon", 
                "name": "Raccoon", 
                "description": "Clever and nimble, perfect for solving study puzzles!"
            },
            PetType.PENGUIN: {
                "type_name": "penguin", 
                "name": "Penguin", 
                "description": "Cool Antarctic companion that waddles through studies with focus!"
            }
        }
        
        # Use centralized simple theme
        self.theme = simple_theme
        self.colors = self.theme.colors
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create a responsive, horizontally fitting pet selection screen."""
        # Configure parent background
        self.parent.configure(bg=self.colors["bg_main"])

        # Main frame (responsive grid)
        self.frame = tk.Frame(self.parent, bg=self.colors["bg_main"])
        self.frame.pack(fill="both", expand=True, padx=self.s(12), pady=self.s(12))

        # Grid weights for responsiveness
        self.frame.grid_rowconfigure(0, weight=0)  # Title
        self.frame.grid_rowconfigure(1, weight=1)  # Pets row
        self.frame.grid_rowconfigure(2, weight=0)  # Preview (fixed height)
        self.frame.grid_rowconfigure(3, weight=0)  # Buttons
        self.frame.grid_columnconfigure(0, weight=1)

        # Configure custom styles
        self._configure_styles()

        # Title
        title_frame = tk.Frame(self.frame, bg=self.colors["bg_main"])
        title_frame.grid(row=0, column=0, sticky="ew", pady=(2, 8))

        tk.Label(
            title_frame,
            text="🌸 Choose Your Study Companion 🌸",
            font=("Comic Sans MS", 24, "bold"),
            fg=self.colors["text_pink"],
            bg=self.colors["bg_main"]
        ).pack()

        tk.Label(
            title_frame,
            text="Pick your perfect pet partner for learning adventures!",
            font=("Arial", 11),
            fg=self.colors["text_medium"],
            bg=self.colors["bg_main"]
        ).pack(pady=(2, 0))

        # Pets container (horizontally fitting)
        pets_panel = RoundedPanel(self.frame, radius=12, bg=self.colors["bg_panel"], padding=8)
        pets_panel.set_padding(10)
        pets_panel.grid(row=1, column=0, sticky="nsew", padx=self.s(8), pady=self.s(6))
        pets_container = pets_panel.inner
        pets_container.configure(bg=self.colors["bg_panel"])
        pets_container.grid_columnconfigure((0,1,2,3,4), weight=1)
        pets_container.grid_rowconfigure(1, weight=1)

        tk.Label(
            pets_container,
            text="✨ Available Pets ✨",
            font=("Arial", 16, "bold"),
            fg=self.colors["coral_pink"],
            bg=self.colors["bg_panel"]
        ).grid(row=0, column=0, columnspan=5, pady=(8, 2))

        pets_frame = tk.Frame(pets_container, bg=self.colors["bg_panel"])
        pets_frame.grid(row=1, column=0, columnspan=5, sticky="nsew", padx=self.s(6), pady=self.s(6))
        for c in range(5):
            pets_frame.grid_columnconfigure(c, weight=1, uniform="pets")
        pets_frame.grid_rowconfigure(0, weight=1)

        # Create pet selection buttons with egg images
        self.pet_buttons = {}
        self.pet_image_labels = {}

        # Determine egg size based on current width (will update on resize)
        current_width = max(self.parent.winfo_width(), 1200)
        base_egg = min(max(current_width // 20, 72), 140)

        for i, (pet_type, info) in enumerate(self.pet_info.items()):
            btn_frame = tk.Frame(pets_frame, bg=self.colors["bg_panel"])
            btn_frame.grid(row=0, column=i, padx=self.s(6), pady=self.s(2), sticky="n")

            egg_widget = pet_graphics.create_pet_display_widget(
                btn_frame,
                info["type_name"],
                stage=1,
                size=(base_egg, base_egg)
            )

            if hasattr(egg_widget, 'image') and egg_widget.image:
                egg_widget.pack(pady=(0, 2))
                egg_widget.bind("<Button-1>", lambda e, pt=pet_type: self.select_pet(pt))
                egg_widget.bind("<Enter>", lambda e, frame=btn_frame: frame.configure(bg=self.colors["soft_pink"]))
                egg_widget.bind("<Leave>", lambda e, frame=btn_frame: frame.configure(bg=self.colors["bg_panel"]))
                self.pet_image_labels[pet_type] = egg_widget
            else:
                egg_button = tk.Button(
                    btn_frame,
                    text="🥚",
                    font=("Arial", max(min(max(base_egg//2, 28), 56)-2, 18)),
                    bg=self.colors["pastel_lavender"],
                    fg=self.colors["coral_pink"],
                    relief="raised",
                    bd=3,
                    command=lambda pt=pet_type: self.select_pet(pt),
                    cursor="hand2"
                )
                egg_button.pack(pady=(0, 2), fill="both", expand=True)
                egg_button.bind("<Enter>", lambda e, btn=egg_button: btn.configure(bg=self.colors["soft_pink"]))
                egg_button.bind("<Leave>", lambda e, btn=egg_button: btn.configure(bg=self.colors["pastel_lavender"]))
                self.pet_buttons[pet_type] = egg_button

            name_label = tk.Label(
                btn_frame,
                text=info["name"],
                font=("Arial", 11, "bold"),
                fg=self.colors["text_dark"],
                bg=self.colors["bg_panel"]
            )
            name_label.pack(pady=(2, 6))
            btn_frame.bind("<Button-1>", lambda e, pt=pet_type: self.select_pet(pt))
            name_label.bind("<Button-1>", lambda e, pt=pet_type: self.select_pet(pt))

        # Preview container
        preview_panel = RoundedPanel(self.frame, radius=12, bg=self.colors["pastel_mint"], padding=10)
        preview_panel.set_padding(14)
        preview_panel.set_min_size(height=self.s(280))
        preview_panel.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 6))

        self.preview_frame = tk.Frame(preview_panel.inner, bg=self.colors["pastel_mint"], relief="flat", bd=0)
        self.preview_frame.pack(fill="both", expand=True)

        # Horizontal layout: text on left, egg on right
        self.preview_content_frame = tk.Frame(self.preview_frame, bg=self.colors["pastel_mint"])
        self.preview_content_frame.pack(fill="both", expand=True, padx=self.s(20), pady=self.s(10))

        # Right side: egg display area (created first)
        self.egg_frame = tk.Frame(self.preview_content_frame, bg=self.colors["pastel_mint"], width=self.s(140))
        self.egg_frame.pack(side="right", fill="y", padx=(self.s(20), 0))
        self.egg_frame.pack_propagate(False)  # Maintain fixed width

        # Container for egg with proper centering (created first)
        self.egg_container = tk.Frame(self.egg_frame, bg=self.colors["pastel_mint"])
        self.egg_container.pack(expand=True)

        # Initial preview emoji in the egg container (created after container exists)
        self.preview_emoji = tk.Label(self.egg_container, text="❓", font=("Arial", 48), fg=self.colors["coral_pink"], bg=self.colors["pastel_mint"])
        self.preview_emoji.pack(expand=True)  # This should center it properly

        # Left side: text content (created after right side)
        self.text_frame = tk.Frame(self.preview_content_frame, bg=self.colors["pastel_mint"])
        self.text_frame.pack(side="left", fill="both", expand=True)

        tk.Label(
            self.text_frame,
            text="💖 Your Chosen Companion 💖",
            font=("Arial", 16, "bold"),
            fg=self.colors["text_pink"],
            bg=self.colors["pastel_mint"]
        ).pack(pady=(12, 6))

        self.preview_name = tk.Label(self.text_frame, text="Select a pet above", font=("Comic Sans MS", 15, "bold"), fg=self.colors["text_dark"], bg=self.colors["pastel_mint"])
        self.preview_name.pack()

        self.preview_description = tk.Label(
            self.text_frame,
            text="Choose your study companion to begin your learning journey!",
            font=("Arial", 11),
            fg=self.colors["text_medium"],
            bg=self.colors["pastel_mint"],
            wraplength=400  # Shorter wrap for horizontal layout
        )
        self.preview_description.pack(pady=(10, 16))

        # Name entry section (below the horizontal layout)
        name_container = tk.Frame(self.preview_frame, bg=self.colors["pastel_mint"])
        name_container.pack(fill="x", pady=(10, 0))

        tk.Label(name_container, text="🏷️ Pet Name:", font=("Arial", 14, "bold"), fg=self.colors["text_dark"], bg=self.colors["pastel_mint"]).pack(side="left", padx=(0, 10))

        self.name_entry = tk.Entry(name_container, textvariable=self.pet_name_var, font=("Arial", 14), width=20, bg=self.colors["white"], fg=self.colors["text_dark"], relief="flat", bd=0, highlightthickness=0)
        self.name_entry.pack(side="left", ipady=5)

        # Buttons
        buttons_frame = tk.Frame(self.frame, bg=self.colors["bg_main"])
        buttons_frame.grid(row=3, column=0, sticky="ew", pady=12)
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)

        back_button = create_rounded_button(
            buttons_frame,
            text="← Back to Start",
            command=self.go_back,
            style="secondary",
            radius=20,
            font=("Arial", 12, "bold")
        )
        back_button.grid(row=0, column=0, sticky="w")

        self.confirm_button = create_rounded_button(
            buttons_frame,
            text="✨ CONFIRM & START! ✨",
            command=self.confirm_selection,
            style="primary",
            radius=20,
            padding=(20, 10),
            font=("Arial", 14, "bold")
        )
        self.confirm_button.grid(row=0, column=1, sticky="e")
        try:
            # Disable until a pet is selected
            self.confirm_button.set_enabled(False)
        except Exception:
            pass

        # Handle dynamic layout on window resize
        self.parent.bind('<Configure>', self.on_window_resize)

        # Process any deferred pet selection (in case user clicked before container was ready)
        self.parent.after(100, self._process_deferred_selection)

    def _process_deferred_selection(self):
        """Process any deferred pet selection after widgets are ready."""
        if hasattr(self, '_deferred_pet_selection') and self._deferred_pet_selection is not None:
            pet_type = self._deferred_pet_selection

            # Only proceed if egg_container is ready
            if self.egg_container is not None:
                # Clear the deferred selection flag
                self._deferred_pet_selection = None
                self._deferred_retry_count = 0
                self.select_pet(pet_type)
            else:
                # Retry after a short delay, but don't retry forever
                self._deferred_retry_count += 1
                if self._deferred_retry_count < 10:  # Max 10 retries (1 second total)
                    self.parent.after(100, self._process_deferred_selection)
                else:
                    self._deferred_pet_selection = None
                    self._deferred_retry_count = 0
    
    def on_window_resize(self, event):
        """Adjust layout and wrap lengths dynamically on resize."""
        try:
            width = max(self.parent.winfo_width(), 800)
            # Adjust description wraplength for horizontal layout (shorter since text is on left side)
            wrap = min(max(int(width * 0.3), 300), 500)  # Even shorter for side-by-side layout
            if hasattr(self, 'preview_description') and self.preview_description.winfo_exists():
                self.preview_description.configure(wraplength=wrap)

            # Adjust egg container width based on window size
            if hasattr(self, 'egg_frame') and self.egg_frame.winfo_exists():
                egg_width = min(max(width // 8, 120), 160)  # Responsive egg container width
                self.egg_frame.configure(width=egg_width)

        except Exception:
            pass

    def _configure_styles(self):
        """Configure custom styles for the interface."""
        style = ttk.Style()
        
        # Configure ttk styles if needed
        style.configure("Pink.TButton", 
                       background=self.colors["accent_blue"],
                       foreground=self.colors["white"],
                       font=("Arial", 12, "bold"))
    
    def select_pet(self, pet_type):
        """Handle pet selection with egg image preview."""
        self.selected_pet_type = pet_type
        info = self.pet_info[pet_type]

        # Ensure egg_container exists and is ready before trying to use it
        if self.egg_container is None:
            # Store selection for later processing
            self._deferred_pet_selection = pet_type
            return

        # Reset retry counter since we're processing successfully
        self._deferred_retry_count = 0

        # Clear the right side egg container first (including the initial ? emoji)
        for widget in self.egg_container.winfo_children():
            widget.destroy()

        # Create egg image for preview (optimal size for right side container)
        egg_preview = pet_graphics.create_pet_display_widget(
            self.egg_container,
            info["type_name"],
            stage=1,  # Egg stage
            size=(100, 100)  # Size optimized for right side container
        )

        # If no egg image available, use fallback emoji
        if not (hasattr(egg_preview, 'image') and egg_preview.image):
            egg_preview = tk.Label(
                self.egg_container,
                text="🥚",
                font=("Arial", 48),
                fg=self.colors["coral_pink"],
                bg=self.colors["pastel_mint"]
            )

        # Center the egg in the right container
        egg_preview.pack(expand=True)

        # Update the preview_emoji reference to the new widget
        self.preview_emoji = egg_preview

        # Update text content on the left side (with safety checks)
        if self.preview_name is not None:
            self.preview_name.configure(text=f"{info['name']} Egg")
        if self.preview_description is not None:
            self.preview_description.configure(text=info["description"])

        # Set default name if empty
        if not self.pet_name_var.get():
            self.pet_name_var.set(f"My {info['name']}")

        # Enable confirm button with animation
        if self.confirm_button is not None:
            try:
                self.confirm_button.set_enabled(True)
            except Exception:
                pass

        # Visual feedback for selection - highlight the chosen pet (with safety checks)
        try:
            for pet_type_key in self.pet_info.keys():
                # Find the pet frame (parent of the egg widget or button)
                for widget in self.pet_buttons:
                    if widget == pet_type_key:
                        # Find the button's parent frame
                        if pet_type_key in self.pet_buttons:
                            btn = self.pet_buttons[pet_type_key]
                            if pet_type_key == pet_type:
                                btn.configure(bg=self.colors["gold_accent"], relief="sunken")
                            else:
                                btn.configure(bg=self.colors["pastel_lavender"], relief="raised")
                        elif pet_type_key in self.pet_image_labels:
                            # Handle image labels - change parent frame background
                            img_widget = self.pet_image_labels[pet_type_key]
                            parent_frame = img_widget.master
                            if pet_type_key == pet_type:
                                parent_frame.configure(bg=self.colors["gold_accent"], relief="sunken", bd=3)
                            else:
                                parent_frame.configure(bg=self.colors["bg_panel"], relief="flat", bd=1)
        except Exception:
            pass
    
    def confirm_selection(self):
        """Handle confirm button click."""
        if not self.selected_pet_type:
            NotificationManager.warn("No Pet Selected", "Please select a pet first!")
            return

        pet_name = self.pet_name_var.get().strip()
        if not pet_name:
            NotificationManager.warn("No Name", "Please enter a name for your pet!")
            if self.name_entry is not None:
                self.name_entry.focus()
            return

        # Confirm the selection
        info = self.pet_info[self.selected_pet_type]
        confirm = NotificationManager.confirm(
            "Confirm Pet Selection",
            f"Are you sure you want to choose {info['name']} named '{pet_name}' as your study companion?\n\n" +
            f"{info['description']}"
        )

        if confirm:
            if self.on_pet_selected_callback:
                self.on_pet_selected_callback(self.selected_pet_type, pet_name)
    
    def go_back(self):
        """Handle back button click."""
        # For now, just show a message. In a full implementation,
        # this would return to the previous screen
        NotificationManager.notify(
            "Going Back",
            "This would return to the start screen.\n\n" +
            "For now, please select a pet to continue!"
        )
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        try:
            if hasattr(self, 'canvas') and self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except (tk.TclError, AttributeError):
            # Canvas has been destroyed or doesn't exist, ignore scrolling
            pass
    
    def destroy(self):
        """Clean up the screen."""
        # Cancel any deferred selection processing
        if hasattr(self, '_deferred_pet_selection'):
            delattr(self, '_deferred_pet_selection')
        if hasattr(self, '_deferred_retry_count'):
            delattr(self, '_deferred_retry_count')

        # Cancel any pending after callbacks
        if hasattr(self, 'parent') and self.parent:
            try:
                # Cancel the deferred selection callback
                self.parent.after_cancel(self._process_deferred_selection)
            except (AttributeError, ValueError):
                pass  # Callback may not exist or already cancelled

        # Clear all widget references
        for attr in ['egg_container', 'preview_emoji', 'text_frame', 'preview_name',
                     'preview_description', 'confirm_button', 'name_entry', 'egg_frame',
                     'preview_content_frame', 'preview_frame', 'name_container']:
            if hasattr(self, attr):
                setattr(self, attr, None)

        # Clear button and image label collections
        self.pet_buttons.clear()
        self.pet_image_labels.clear()

        # Destroy all child widgets first
        if hasattr(self, 'frame') and self.frame and self.frame.winfo_exists():
            for child in self.frame.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass

        # Explicitly destroy egg_container and its contents
        if hasattr(self, 'egg_container') and self.egg_container and self.egg_container.winfo_exists():
            try:
                for child in self.egg_container.winfo_children():
                    child.destroy()
                self.egg_container.destroy()
                self.egg_container = None
            except Exception:
                pass

        # Explicitly destroy preview_emoji if it exists and is different from egg_container contents
        if hasattr(self, 'preview_emoji') and self.preview_emoji and self.preview_emoji.winfo_exists():
            try:
                self.preview_emoji.destroy()
                self.preview_emoji = None
            except Exception:
                pass

        if hasattr(self, 'canvas'):
            self.canvas.destroy()
        if hasattr(self, 'scrollbar'):
            self.scrollbar.destroy()
        if self.frame:
            self.frame.destroy()
            self.frame = None

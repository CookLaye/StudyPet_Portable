"""
Simple Black and White Theme System for StudyPet
Clean monochrome color scheme for a minimalist interface
"""

import sys
import tkinter as tk
from tkinter import ttk
from .rounded_widgets import RoundedButton

# ── System font ──────────────────────────────────────────────────────────────
if sys.platform == "win32":
    _UI_FONT = "Segoe UI"
elif sys.platform == "darwin":
    _UI_FONT = "SF Pro Text"
else:
    _UI_FONT = "Ubuntu"

class SimpleTheme:
    """Centralized black and white color management system."""
    
    def __init__(self):
        # Simple black and white color palette
        self.colors = {
            # Primary colors (black/white/gray)
            "primary_red": "#000000",          # Black
            "primary_blue": "#000000",         # Black
            "primary_yellow": "#000000",       # Black
            "primary_green": "#000000",        # Black
            "primary_orange": "#000000",       # Black
            
            # Light versions (grays)
            "light_red": "#CCCCCC",           # Light gray
            "light_blue": "#CCCCCC",          # Light gray
            "light_yellow": "#CCCCCC",        # Light gray
            "light_green": "#CCCCCC",         # Light gray
            "light_orange": "#CCCCCC",        # Light gray
            
            # Accent colors
            "gold_accent": "#333333",         # Dark gray for highlights
            "silver_accent": "#999999",       # Medium gray for borders
            "white": "#FFFFFF",               # Pure white
            "off_white": "#F5F5F5",           # Slightly off white
            
            # Text colors
            "text_dark": "#000000",           # Black text
            "text_medium": "#666666",         # Medium gray
            "text_light": "#999999",          # Light gray
            "text_accent": "#000000",         # Black text for accents
            
            # Status colors (grayscale)
            "success_green": "#333333",       # Dark gray
            "warning_yellow": "#666666",      # Medium gray
            "error_red": "#000000",           # Black
            "info_blue": "#666666",           # Medium gray
            
            # Interactive states
            "hover_red": "#333333",           # Dark gray hover
            "hover_blue": "#333333",          # Dark gray hover
            "hover_yellow": "#333333",        # Dark gray hover
            "active_red": "#000000",          # Black active
            "active_blue": "#000000",         # Black active
            "disabled_gray": "#CCCCCC",       # Light gray disabled
            "selected_yellow": "#E0E0E0",     # Very light gray selected
            
            # Accent colors for UI elements
            "accent": "#4A90E2",              # Blue accent color for primary actions
            "error": "#E74C3C",               # Red color for errors/destructive actions
            
            # Background variations
            "bg_main": "#FFFFFF",             # White main background
            "bg_secondary": "#F5F5F5",        # Light gray secondary
            "bg_accent": "#EEEEEE",           # Light gray accent
            "bg_panel": "#FAFAFA",            # Very light gray panel
            "bg_light": "#E0E0E0",            # Very light gray
            "bg_medium": "#CCCCCC",           # Light gray
            "bg_dark": "#666666",             # Medium gray
            "selected_gold": "#E0E0E0",       # Very light gray
            "accent_blue": "#4A90E2",         # Blue accent for buttons
            "soft_pink": "#F5F5F5",           # Light gray (legacy name)
            
            # Legacy color names mapped to grayscale (for compatibility)
            "text_pink": "#000000",           # Black text
            "coral_pink": "#666666",          # Medium gray
            "pastel_purple": "#CCCCCC",       # Light gray
            "pastel_lavender": "#E0E0E0",     # Very light gray
            "pastel_mint": "#E0E0E0",         # Very light gray
            "pastel_cream": "#F5F5F5",        # Almost white
            "pastel_peach": "#E0E0E0",        # Very light gray
            "success_pink": "#333333",        # Dark gray
            "warning_peach": "#666666",       # Medium gray
            "error_coral": "#000000",         # Black
            "info_lavender": "#666666",       # Medium gray
            "hover_pink": "#333333",          # Dark gray
            "active_pink": "#000000",         # Black
        }
        
        # Theme presets for different components (black and white)
        self.component_themes = {
            "main_window": {
                "background": self.colors["bg_main"],
                "foreground": self.colors["text_dark"]
            },
            
            "title_bar": {
                "background": self.colors["text_dark"],
                "foreground": self.colors["white"],
                "font_weight": "bold"
            },
            
            "button_primary": {
                "background": self.colors["text_dark"],
                "foreground": self.colors["white"],
                "active_background": self.colors["active_red"],
                "hover_background": self.colors["hover_red"],
                "border": self.colors["text_dark"]
            },
            
            "button_secondary": {
                "background": self.colors["text_medium"],
                "foreground": self.colors["white"],
                "active_background": self.colors["active_blue"],
                "hover_background": self.colors["hover_blue"],
                "border": self.colors["text_medium"]
            },
            
            "button_accent": {
                "background": self.colors["bg_secondary"],
                "foreground": self.colors["text_dark"],
                "active_background": self.colors["bg_accent"],
                "hover_background": self.colors["bg_accent"]
            },
            
            "input_field": {
                "background": self.colors["white"],
                "foreground": self.colors["text_dark"],
                "border": self.colors["text_medium"],
                "focus_border": self.colors["text_dark"]
            },
            
            "panel": {
                "background": self.colors["bg_panel"],
                "border": self.colors["text_light"],
                "title_background": self.colors["bg_secondary"],
                "title_foreground": self.colors["text_dark"]
            },
            
            "status_bar": {
                "background": self.colors["bg_secondary"],
                "foreground": self.colors["text_medium"],
                "border": self.colors["text_light"]
            },
            
            "menu": {
                "background": self.colors["bg_secondary"],
                "foreground": self.colors["text_dark"],
                "active_background": self.colors["bg_accent"],
                "separator": self.colors["silver_accent"]
            },
            
            "pet_display": {
                "background": self.colors["bg_panel"],
                "border": self.colors["text_light"],
                "shadow": self.colors["silver_accent"]
            },
            
            "study_timer": {
                "background": self.colors["bg_secondary"],
                "progress_bar": self.colors["text_dark"],
                "text": self.colors["text_dark"]
            }
        }
    
    def get_color(self, color_name):
        """Get a color by name."""
        return self.colors.get(color_name, "#000000")  # Fallback to black
    
    def get_component_theme(self, component_name):
        """Get a complete theme for a component."""
        return self.component_themes.get(component_name, {})
    
    def apply_to_widget(self, widget, component_name):
        """Apply theme to a tkinter widget."""
        theme = self.get_component_theme(component_name)
        
        try:
            if "background" in theme:
                widget.configure(bg=theme["background"])
            if "foreground" in theme:
                widget.configure(fg=theme["foreground"])
            if "border" in theme and hasattr(widget, 'configure'):
                # Some widgets support border colors
                try:
                    widget.configure(highlightbackground=theme["border"])
                except Exception:
                    pass
        except Exception as e:
            print(f"Could not apply theme to widget: {e}")
    
    def create_button_style(self, style_name="primary"):
        """Create button styling dictionary."""
        if style_name == "primary":
            theme = self.component_themes["button_primary"]
        elif style_name == "secondary":
            theme = self.component_themes["button_secondary"]
        elif style_name == "accent":
            theme = self.component_themes["button_accent"]
        else:
            theme = self.component_themes["button_primary"]
        
        return {
            "bg": theme.get("background", self.colors["bg_secondary"]),
            "fg": theme.get("foreground", self.colors["text_dark"]),
            "activebackground": theme.get("active_background", theme.get("hover_background", self.colors["bg_accent"])),
            "relief": "flat",
            "bd": 0,
            "highlightthickness": 0,
            "cursor": "hand2",
            "font": (_UI_FONT, 11, "bold")
        }
    
    def get_hover_bindings(self, widget, style_name="primary"):
        """Get hover effect bindings for a widget."""
        if style_name == "primary":
            theme = self.component_themes["button_primary"]
        elif style_name == "secondary":
            theme = self.component_themes["button_secondary"] 
        elif style_name == "accent":
            theme = self.component_themes["button_accent"]
        else:
            theme = self.component_themes["button_primary"]
        
        def on_enter(event):
            widget.configure(bg=theme["hover_background"])
        
        def on_leave(event):
            widget.configure(bg=theme["background"])
        
        return on_enter, on_leave
    
    def update_colors_from_yellow(self, old_color):
        """Convert any color to black/white/gray equivalents."""
        color_to_bw_map = {
            "#FFFF00": self.colors["text_medium"],      # Bright yellow -> medium gray
            "#FFFACD": self.colors["bg_secondary"],     # Light yellow -> light gray  
            "#FFE4B5": self.colors["bg_secondary"],     # Moccasin -> light gray
            "#F0E68C": self.colors["bg_accent"],        # Khaki -> light gray
            "#FFD700": self.colors["gold_accent"],      # Gold -> dark gray accent
            "#FFFF99": self.colors["bg_secondary"],     # Light yellow -> light gray
            "#FFFFF0": self.colors["off_white"],        # Ivory -> off white
        }
        
        return color_to_bw_map.get(old_color, self.colors["text_medium"])

# Global theme instance
simple_theme = SimpleTheme()

# Helper functions for easy access
def get_color(color_name):
    """Quick access to get a color."""
    return simple_theme.get_color(color_name)

def get_component_theme(component_name):
    """Quick access to get component theme."""
    return simple_theme.get_component_theme(component_name)

def apply_theme_to_widget(widget, component_name):
    """Quick apply theme to widget."""
    return simple_theme.apply_to_widget(widget, component_name)

def create_styled_button(parent, text, command=None, style="primary"):
    """Create a pre-styled button with simple black/white theme."""
    button_style = simple_theme.create_button_style(style)
    button = tk.Button(parent, text=text, command=command, **button_style)
    
    # Add hover effects
    on_enter, on_leave = simple_theme.get_hover_bindings(button, style)
    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
    
    return button

def create_rounded_button(parent, text, command=None, style="accent", radius=20, padding=(14,8), font=None):
    """Create a rounded button using canvas with theme colors."""
    if font is None:
        font = (_UI_FONT, 11, "bold")
    colors = simple_theme.colors

    if style == "primary":
        bg = colors.get("text_pink", colors.get("text_dark", "#000000"))
        fg = colors.get("white", "#FFFFFF")
        hover_bg = colors.get("coral_pink", bg)
        active_bg = colors.get("text_dark", bg)
    elif style == "secondary":
        bg = colors.get("soft_pink", colors.get("bg_secondary", "#F5F5F5"))
        fg = colors.get("text_dark", "#000000")
        hover_bg = colors.get("bg_accent", bg)
        active_bg = colors.get("bg_medium", bg)
    else:
        bg = colors.get("bg_light", "#E0E0E0")
        fg = colors.get("text_dark", "#000000")
        hover_bg = colors.get("bg_medium", "#CCCCCC")
        active_bg = colors.get("bg_dark", "#999999")

    btn = RoundedButton(parent, text=text, command=command, radius=radius, bg=bg, fg=fg, hover_bg=hover_bg, active_bg=active_bg, padding=padding, font=font)
    return btn

def apply_global_ttk_style(root):
    """Apply global flat, borderless ttk styles with solid colors."""
    try:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        colors = simple_theme.colors
        # Frames and labels
        style.configure("TFrame", background=colors["bg_main"])
        style.configure("TLabel", background=colors["bg_main"], foreground=colors["text_dark"])
        # LabelFrame borderless
        style.configure("TLabelframe", background=colors["bg_panel"], borderwidth=0, relief="flat")
        style.configure("TLabelframe.Label", background=colors["bg_panel"], foreground=colors["text_dark"]) 
        # Buttons flat, borderless
        style.configure(
            "TButton",
            background=colors["bg_secondary"],
            foreground=colors["text_dark"],
            borderwidth=0,
            relief="flat",
            padding=(10, 6)
        )
        style.map(
            "TButton",
            background=[("active", colors["bg_accent"]), ("pressed", colors["bg_accent"])],
            relief=[("pressed", "flat"), ("active", "flat")]
        )
        # Entry flat
        style.configure("TEntry", fieldbackground=colors["white"], foreground=colors["text_dark"], borderwidth=0, relief="flat")
        # Scrollbars flat
        style.configure("Vertical.TScrollbar", gripcount=0, background=colors["bg_medium"], borderwidth=0, relief="flat")
        style.configure("Horizontal.TScrollbar", gripcount=0, background=colors["bg_medium"], borderwidth=0, relief="flat")
    except Exception:
        pass
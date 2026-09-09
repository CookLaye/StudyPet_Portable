"""Centralized pet theme system.

This module is the single source of truth for pet-specific UI palettes.
It applies palettes into `simple_theme.colors`, which is used throughout the UI.
"""

from __future__ import annotations

from typing import Dict, Optional

from ui.simple_theme import simple_theme


PET_PALETTES: Dict[str, Dict[str, str]] = {
    "axolotl": {
        "bg_main": "#FDF2F8",
        "bg_secondary": "#FCE7F3",
        "bg_accent": "#FBCFE8",
        "bg_panel": "#FCE7F3",
        "text_dark": "#831843",
        "text_medium": "#BE185D",
        "text_light": "#DB2777",
        "text_pink": "#EC4899",
        "coral_pink": "#F472B6",
        "soft_pink": "#F9A8D4",
        "accent": "#EC4899",
        # High contrast variants for better readability
        "text_primary": "#FFFFFF",  # For dark backgrounds
        "text_secondary": "#831843",  # For light backgrounds
        "bg_primary": "#EC4899",  # Dark accent for buttons
        "bg_primary_hover": "#DB2777",
        "bg_primary_active": "#BE185D",
    },
    "cat": {
        "bg_main": "#F8F9FA",
        "bg_secondary": "#E5E7EB",
        "bg_accent": "#D1D5DB",
        "bg_panel": "#E5E7EB",
        "text_dark": "#374151",
        "text_medium": "#6B7280",
        "text_light": "#9CA3AF",
        "text_pink": "#8B5CF6",
        "coral_pink": "#6366F1",
        "soft_pink": "#A78BFA",
        "accent": "#8B5CF6",
        # High contrast variants
        "text_primary": "#FFFFFF",
        "text_secondary": "#374151",
        "bg_primary": "#8B5CF6",
        "bg_primary_hover": "#7C3AED",
        "bg_primary_active": "#6D28D9",
    },
    "dog": {
        "bg_main": "#FFFBF0",
        "bg_secondary": "#FEF3C7",
        "bg_accent": "#FDE68A",
        "bg_panel": "#FEF3C7",
        "text_dark": "#92400E",
        "text_medium": "#B45309",
        "text_light": "#D97706",
        "text_pink": "#F59E0B",
        "coral_pink": "#FCD34D",
        "soft_pink": "#FDE047",
        "accent": "#F59E0B",
        # High contrast variants
        "text_primary": "#FFFFFF",
        "text_secondary": "#92400E",
        "bg_primary": "#F59E0B",
        "bg_primary_hover": "#D97706",
        "bg_primary_active": "#B45309",
    },
    "raccoon": {
        "bg_main": "#FEF7ED",
        "bg_secondary": "#FED7AA",
        "bg_accent": "#FDBA74",
        "bg_panel": "#FED7AA",
        "text_dark": "#9A3412",
        "text_medium": "#C2410C",
        "text_light": "#EA580C",
        "text_pink": "#DC2626",
        "coral_pink": "#F97316",
        "soft_pink": "#FB923C",
        "accent": "#DC2626",
        # High contrast variants
        "text_primary": "#FFFFFF",
        "text_secondary": "#9A3412",
        "bg_primary": "#DC2626",
        "bg_primary_hover": "#B91C1C",
        "bg_primary_active": "#991B1B",
    },
    "penguin": {
        "bg_main": "#FFFFFF",
        "bg_secondary": "#F5F5F5",
        "bg_accent": "#E5E5E5",
        "bg_panel": "#F5F5F5",
        "text_dark": "#000000",
        "text_medium": "#666666",
        "text_light": "#999999",
        "text_pink": "#000000",
        "coral_pink": "#666666",
        "soft_pink": "#F5F5F5",
        "accent": "#000000",
        # High contrast variants
        "text_primary": "#FFFFFF",
        "text_secondary": "#000000",
        "bg_primary": "#000000",
        "bg_primary_hover": "#333333",
        "bg_primary_active": "#666666",
    },
}


def _normalize_pet_type(pet_type: object) -> str:
    if pet_type is None:
        return "penguin"
    try:
        if hasattr(pet_type, "value"):
            return str(pet_type.value).lower()
        return str(pet_type).lower()
    except Exception:
        return "penguin"


def get_current_pet_type(app_state: object) -> str:
    if not app_state or not hasattr(app_state, "get_current_pet"):
        return "penguin"
    pet = app_state.get_current_pet()
    if not pet:
        return "penguin"
    return _normalize_pet_type(getattr(pet, "pet_type", None))


def apply_pet_theme(*, app_state: object = None, pet_type: Optional[object] = None) -> Dict[str, str]:
    """Apply a pet palette into the global `simple_theme.colors`.

    Provide either `app_state` (preferred) or `pet_type`.

    Returns:
        The updated `simple_theme.colors` dict.
    """
    pet_key = _normalize_pet_type(pet_type) if pet_type is not None else get_current_pet_type(app_state)
    palette = PET_PALETTES.get(pet_key, PET_PALETTES["penguin"])

    simple_theme.colors.update(palette)

    # Legacy palette keys used across older screens/widgets.
    # These are intentionally simple derivations so the rest of the UI can keep using
    # the keys it expects without each screen managing its own palette.
    simple_theme.colors.setdefault("pastel_lavender", palette.get("bg_accent", palette["bg_secondary"]))
    simple_theme.colors.setdefault("pastel_mint", palette.get("bg_secondary", palette["bg_main"]))
    simple_theme.colors.setdefault("pastel_cream", palette.get("bg_main", "#FFFFFF"))
    simple_theme.colors.setdefault("pastel_peach", palette.get("soft_pink", palette["bg_secondary"]))
    simple_theme.colors.setdefault("pastel_purple", palette.get("soft_pink", palette["bg_secondary"]))
    simple_theme.colors.setdefault("gold_accent", palette.get("coral_pink", palette.get("accent", "#333333")))

    # Ensure a few foundational keys exist.
    simple_theme.colors.setdefault("white", "#FFFFFF")
    simple_theme.colors.setdefault("off_white", palette.get("bg_main", "#F5F5F5"))

    # Keep a few compatibility aliases used in older code.
    if "text_pink" in palette:
        simple_theme.colors["accent_blue"] = palette["text_pink"]
    
    # Button text color overrides for greeting screen
    if pet_key == "penguin":
        # Penguin theme: START button white, Settings/About buttons black
        simple_theme.colors["button_primary_text"] = "#FFFFFF"
        simple_theme.colors["button_secondary_text"] = "#000000"
    elif pet_key == "axolotl":
        # Axolotl theme: START button white, Settings/About buttons dark
        simple_theme.colors["button_primary_text"] = "#FFFFFF"
        simple_theme.colors["button_secondary_text"] = "#831843"
    elif pet_key == "cat":
        # Cat theme: START button white, Settings/About buttons dark
        simple_theme.colors["button_primary_text"] = "#FFFFFF"
        simple_theme.colors["button_secondary_text"] = "#374151"
    elif pet_key == "dog":
        # Dog theme: START button white, Settings/About buttons dark
        simple_theme.colors["button_primary_text"] = "#FFFFFF"
        simple_theme.colors["button_secondary_text"] = "#92400E"
    elif pet_key == "raccoon":
        # Raccoon theme: START button white, Settings/About buttons dark
        simple_theme.colors["button_primary_text"] = "#FFFFFF"
        simple_theme.colors["button_secondary_text"] = "#9A3412"
    else:
        # Default fallback
        simple_theme.colors["button_primary_text"] = "#FFFFFF"
        simple_theme.colors["button_secondary_text"] = "#000000"

    return simple_theme.colors

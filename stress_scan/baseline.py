import json
import os
from typing import Dict, Optional

# Spec Step 7: Baseline management

def save_baseline(baseline_path: str, features: Dict[str, float]):
    """
    Saves the median features to baseline.json.
    """
    with open(baseline_path, 'w') as f:
        json.dump(features, f, indent=4)

def load_baseline(baseline_path: str) -> Optional[Dict[str, float]]:
    """
    Loads personal baseline from baseline.json.
    Returns None if missing or invalid.
    """
    if not os.path.exists(baseline_path):
        return None
    try:
        with open(baseline_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

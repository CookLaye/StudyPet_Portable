# STUDYPET-LAUNCHER-FIX
"""
Downloads everything StudyPet needs besides Python packages:
  1. the llama.cpp server binary   (chat engine)
  2. the Llama 3.2 1B GGUF model    (chat brain, ~0.8 GB)
  3. the face-scan models           (stress scan, ~20 MB; skipped if the scan libraries are not installed)

Each step is independent: if one fails the others are still tried, and the exit code is 1 if any failed.
Run by the launchers right before the app starts. Safe to run again at any time.
"""

import importlib.util
import sys
from pathlib import Path

# The launcher may run with a console that cannot print emoji; never crash because of a symbol.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

current_file = Path(__file__).resolve()
src_path = current_file.parent.parent
project_root = src_path.parent

# 'utils' lives in src/, 'stress_scan' lives in the project root.
for _p in (str(src_path), str(project_root)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from utils.model_manager import ModelManager
except ImportError as e:
    print(f"[X] Import Error: {e}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)


def _setup_scan_models():
    """Download the face-scan models unless the scan libraries are missing (then they are useless)."""
    if importlib.util.find_spec("mediapipe") is None or importlib.util.find_spec("onnxruntime") is None:
        print("Face-scan libraries are not installed - skipping the face-scan models.")
        return
    from stress_scan.live_scan import ensure_models, models_ready
    if models_ready():
        print("Face-scan models already present.")
        return
    print("Downloading face-scan models (about 20 MB, first run only)...")
    ensure_models()
    print("Face-scan models ready.")


def main():
    print("Initializing StudyPet AI Engine Assets...")
    mgr = ModelManager()

    steps = (
        ("AI server (llama.cpp)", mgr.setup_backend),
        ("chat model", mgr.setup_model),
        ("face-scan models", _setup_scan_models),
    )
    failed = []
    for label, step in steps:
        try:
            step()
        except Exception as e:
            print(f"[X] {label} failed: {e}")
            failed.append(label)

    if failed:
        print("[X] AI setup incomplete. Not set up: " + ", ".join(failed))
        sys.exit(1)
    print("[V] AI assets verified and ready.")


if __name__ == "__main__":
    main()

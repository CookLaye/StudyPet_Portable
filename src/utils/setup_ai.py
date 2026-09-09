import sys
import os
from pathlib import Path

# 1. Get the absolute path of the current file
current_file = Path(__file__).resolve()

# 2. Identify the project root
project_root = current_file.parent.parent.parent
src_path = current_file.parent.parent

# 3. Add the 'src' directory to sys.path so that 'utils' can be imported
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    # Now 'utils' should be discoverable because its parent (src) is in sys.path
    from utils.model_manager import ModelManager
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

def main():
    print("Initializing StudyPet AI Engine Assets...")
    mgr = ModelManager()
    try:
        # Ensure both the binary backend and the model file are downloaded
        mgr.setup_backend()
        mgr.setup_model()
        print("✅ AI assets verified and ready.")
    except Exception as e:
        print(f"❌ AI Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

import os
import subprocess
import platform
import urllib.request
import time
import socket
import zipfile
from pathlib import Path

class ModelManager:
    """
    Manages the lifecycle of the local LLM server.
    Shifted to a standalone binary architecture for maximum stability on Windows.
    """
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.model_dir = self.project_root / "assets" / "models" / "gpt_pet"
        self.bin_dir = self.model_dir / "bin"
        self.model_path = self.model_dir / "llama-3.2-1b-instruct-q4_k_m.gguf"
        self.server_exe = self.bin_dir / "llama-server.exe"
        self.server_process = None
        self.log_file = None
        self.port = 8080

        # Ensure directories exist
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.bin_dir.mkdir(parents=True, exist_ok=True)

    def get_python_executable(self):
        """Returns the path to the python executable (venv preferred)."""
        venv_python = self.project_root / ".venv" / "Scripts" / "python.exe" if platform.system() == "Windows" else self.project_root / ".venv" / "bin" / "python"
        return str(venv_python) if venv_python.exists() else os.sys.executable

    def detect_hardware(self):
        """Detects if NVIDIA GPU is available."""
        try:
            subprocess.run(["nvidia-smi"], capture_output=True, check=True)
            return "cuda"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "cpu"

    def _download_file(self, url, dest):
        """Helper to download files."""
        print(f"Downloading: {url} ...")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"Downloaded to {dest}")
        except Exception as e:
            print(f"Download failed: {e}")
            raise

    def setup_model(self):
        """Downloads the Llama 3.2 1B GGUF model."""
        if self.model_path.exists():
            print("Model file already exists.")
            return self.model_path

        print("Downloading Llama 3.2 1B GGUF model (approx 700MB)...")
        model_url = "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
        self._download_file(model_url, self.model_path)
        return self.model_path

    def setup_backend(self):
        """Downloads and extracts the standalone llama-server binary."""
        if self.server_exe.exists():
            print("llama-server.exe already exists.")
            return self.server_exe

        hw = self.detect_hardware()
        print(f"Detecting hardware: {hw}")

        # Updated to current release b9975 filenames from official releases
        release_tag = "b9975"
        if hw == "cuda":
            # Using CUDA 12.4 as the most compatible current target
            zip_url = f"https://github.com/ggml-org/llama.cpp/releases/download/{release_tag}/llama-{release_tag}-bin-win-cuda-12.4-x64.zip"
        else:
            zip_url = f"https://github.com/ggml-org/llama.cpp/releases/download/{release_tag}/llama-{release_tag}-bin-win-cpu-x64.zip"

        zip_path = self.bin_dir / "backend.zip"

        try:
            self._download_file(zip_url, zip_path)

            print("Extracting server binaries...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.bin_dir)

            # Search for the server executable in the extracted files
            for file in self.bin_dir.glob("**/*.exe"):
                if "llama-server" in file.name.lower():
                    # Move it to the root of bin folder for consistency
                    target_path = self.server_exe
                    if file != target_path:
                        # If a file with the same name exists, remove it first
                        if target_path.exists():
                            target_path.unlink()
                        file.rename(target_path)
                    break

            if not self.server_exe.exists():
                raise FileNotFoundError("Could not find llama-server.exe in the downloaded zip.")

            # Cleanup zip
            zip_path.unlink()
            print("Backend binaries setup successfully.")

        except Exception as e:
            print(f"Backend setup failed: {e}")
            raise

        return self.server_exe

    def is_server_running(self):
        """Checks if the server is responding with a successful HTTP request to the models endpoint."""
        try:
            # Try to fetch the models endpoint to ensure the model is loaded and serving
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/v1/models", timeout=1) as response:
                return response.getcode() == 200
        except Exception:
            return False

    def start_server(self):
        """Launches the standalone llama-server and waits for it to be ready."""
        if self.server_process:
            if self.is_server_running():
                print("Server is already running.")
                return
            else:
                self.stop_server()

        self.setup_model()
        server_exe = self.setup_backend()
        hw = self.detect_hardware()

        # Standalone llama-server arguments
        cmd = [
            str(server_exe),
            "-m", str(self.model_path),
            "-c", "2048",
            "--port", str(self.port),
            "-ngl", "32" if hw == "cuda" else "0",
            "-t", "8",
            "--flash-attn", "on"
        ]

        print(f"Starting AI server: {server_exe}")

        # Open log file for capturing server output
        log_file_path = self.model_dir / "server.log"

        try:
            self.log_file = open(log_file_path, "w", encoding="utf-8")

            self.server_process = subprocess.Popen(
                cmd,
                stdout=self.log_file,
                stderr=self.log_file,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )

            print("Waiting for server to initialize", end="", flush=True)
            timeout = 60
            start_time = time.time()

            while time.time() - start_time < timeout:
                if self.is_server_running():
                    print(f"\nAI Server is online on port {self.port}.")
                    return
                print(".", end="", flush=True)
                time.sleep(1)

            print("\nServer timed out while starting.")
            self.stop_server()
            raise TimeoutError("AI Server failed to start within 60 seconds.")

        except Exception as e:
            print(f"\nFailed to start server: {e}")
            raise

    def stop_server(self):
        """Kills the server process."""
        if self.server_process:
            print("\nStopping AI server...")
            self.server_process.terminate()
            self.server_process = None

        if self.log_file:
            self.log_file.close()
            self.log_file = None

        print("Server stopped.")

if __name__ == "__main__":
    mgr = ModelManager()
    try:
        mgr.start_server()
        time.sleep(5)
        mgr.stop_server()
    except KeyboardInterrupt:
        mgr.stop_server()

"""
ModelManager - downloads and runs the local llama.cpp server used by the StudyPet chatbot.

Layout on disk (created on first run):
    assets/models/gpt_pet/llama-3.2-1b-instruct-q4_k_m.gguf     <- the model
    assets/models/gpt_pet/bin/...                               <- llama.cpp release archive, extracted as-is

The server binary is NEVER moved out of the folder the archive put it in: it needs the
DLLs / dylibs that sit next to it.
"""

import os
import platform
import signal
import socket
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# ---- Configuration ---------------------------------------------------------------
LLAMA_RELEASE_TAG = "b9975"   # pinned on purpose: newer tags may rename assets or change flags
RELEASE_BASE_URL = "https://github.com/ggml-org/llama.cpp/releases/download"
MODEL_FILENAME = "llama-3.2-1b-instruct-q4_k_m.gguf"
MODEL_URL = ("https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/"
             "Llama-3.2-1B-Instruct-Q4_K_M.gguf")
MIN_MODEL_BYTES = 300 * 1024 * 1024   # sanity floor; the real file is roughly 0.8 GB
SERVER_PORT = 8080            # preferred port; if it is busy a free one is chosen automatically

# Windows exit codes that have a known, fixable cause (shown to the user if llama-server dies at start-up)
WINDOWS_EXIT_HINTS = {
    0xC0000135: ("A required DLL is missing. Install the Microsoft Visual C++ Redistributable (x64) from "
                 "https://aka.ms/vc14/vc_redist.x64.exe , restart Windows, then start StudyPet again."),
    0xC000001D: ("This CPU cannot run the downloaded llama-server build (illegal instruction). "
                 "StudyPet's AI chat needs a reasonably modern 64-bit CPU."),
}
# ------------------------------------------------------------------------------------


def _run_quiet(cmd):
    """Run a small helper command; return its stdout, or '' on any failure."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=flags)
        return result.stdout or ""
    except Exception:
        return ""


def _process_name(pid):
    """Lower-case executable name of a running process, or None if there is no such process."""
    if platform.system() == "Windows":
        out = _run_quiet(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]).strip()
        first = out.splitlines()[0] if out else ""
        return first.split('","')[0].strip('"').lower() if first.startswith('"') else None
    out = _run_quiet(["ps", "-p", str(pid), "-o", "comm="]).strip()
    return os.path.basename(out).lower() if out else None


def _kill_pid(pid):
    try:
        if platform.system() == "Windows":
            _run_quiet(["taskkill", "/PID", str(pid), "/F"])
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def explain_exit_code(code):
    """Human-readable hint for a llama-server exit code on Windows ('' if there is none)."""
    if platform.system() != "Windows" or code is None:
        return ""
    return WINDOWS_EXIT_HINTS.get(code & 0xFFFFFFFF, "")


class ModelManager:
    """Manages the lifecycle of the local LLM server (standalone llama-server binary)."""

    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent.parent
        self.model_dir = self.project_root / "assets" / "models" / "gpt_pet"
        self.bin_dir = self.model_dir / "bin"
        self.model_path = self.model_dir / MODEL_FILENAME
        self.pid_file = self.model_dir / "server.pid"
        self.server_process = None
        self.log_file = None

        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.bin_dir.mkdir(parents=True, exist_ok=True)

        self._reap_stale_server()
        # Callers (e.g. the chat client) must read `self.port` instead of hard-coding 8080.
        self.port = self._pick_port(SERVER_PORT)

    # ---- port + leftover-process safety ------------------------------------------
    @staticmethod
    def _pick_port(preferred):
        """`preferred` if nothing is listening on it, otherwise any free port."""
        for candidate in (preferred, 0):
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.bind(("127.0.0.1", candidate))
                return probe.getsockname()[1]
            except OSError:
                continue
            finally:
                probe.close()
        return preferred

    def _reap_stale_server(self):
        """Stop a llama-server left over from an earlier session (e.g. the launcher window was closed).

        Safety rules: it only ever touches the PID recorded in server.pid, only if that process still
        is a llama-server, and only if the StudyPet process that started it is gone. It never kills
        anything by port number.
        """
        try:
            server_pid, owner_pid = (int(x) for x in self.pid_file.read_text().split()[:2])
        except (OSError, ValueError):
            self.pid_file.unlink(missing_ok=True)
            return

        owner = _process_name(owner_pid)
        if owner is not None and owner.startswith("python"):
            return                                   # its owner is still running: leave it alone

        name = _process_name(server_pid)
        if name and name.startswith("llama-server"):
            print(f"Stopping a leftover AI server (PID {server_pid}) from a previous session...")
            _kill_pid(server_pid)
        self.pid_file.unlink(missing_ok=True)

    # ---- locating things ---------------------------------------------------------
    @property
    def server_binary_name(self):
        return "llama-server.exe" if platform.system() == "Windows" else "llama-server"

    def find_server_exe(self):
        """Return the llama-server binary wherever the archive put it, or None."""
        name = self.server_binary_name
        direct = self.bin_dir / name
        if direct.is_file():
            return direct
        for candidate in self.bin_dir.rglob(name):
            if candidate.is_file():
                return candidate
        return None

    @property
    def server_exe(self):
        """Backward-compatible attribute: path of the server binary (may not exist yet)."""
        return self.find_server_exe() or (self.bin_dir / self.server_binary_name)

    @staticmethod
    def is_valid_model(path):
        """True only for a complete-looking GGUF file (right size floor + 'GGUF' magic bytes)."""
        try:
            p = Path(path)
            if not p.is_file() or p.stat().st_size < MIN_MODEL_BYTES:
                return False
            with open(p, "rb") as f:
                return f.read(4) == b"GGUF"
        except OSError:
            return False

    def assets_ready(self):
        return self.find_server_exe() is not None and self.is_valid_model(self.model_path)

    def get_python_executable(self):
        """Returns the path to the python executable (venv preferred)."""
        if platform.system() == "Windows":
            venv_python = self.project_root / ".venv" / "Scripts" / "python.exe"
        else:
            venv_python = self.project_root / ".venv" / "bin" / "python"
        return str(venv_python) if venv_python.exists() else os.sys.executable

    @staticmethod
    def _is_apple_silicon():
        """True on Apple Silicon, even when Python itself runs under Rosetta (which reports x86_64)."""
        if platform.system() != "Darwin":
            return False
        if platform.machine().lower() in ("arm64", "aarch64"):
            return True
        return _run_quiet(["sysctl", "-in", "hw.optional.arm64"]).strip() == "1"

    def detect_hardware(self):
        """'metal' on Apple Silicon (GPU offload), otherwise 'cpu'.

        Windows is CPU-only on purpose: the CUDA build of llama.cpp needs separate CUDA runtime
        DLLs, and a 1B model is fast enough on CPU.
        """
        return "metal" if self._is_apple_silicon() else "cpu"

    # ---- downloading -------------------------------------------------------------
    @staticmethod
    def _stream_to(url, part):
        """Stream url into the file `part`; returns (bytes_written, expected_total_or_0).

        Uses `requests`, which carries its own CA certificate bundle (certifi). That matters on macOS:
        a Python build without system certificates fails HTTPS with CERTIFICATE_VERIFY_FAILED when it
        uses urllib. Falls back to urllib only if requests is somehow missing.  # STUDYPET-LAUNCHER-FIX
        """
        headers = {"User-Agent": "StudyPet-setup", "Accept-Encoding": "identity"}
        done = 0
        try:
            import requests
        except ImportError:
            requests = None

        def show(done_bytes, total_bytes):
            if total_bytes:
                print(f"\rProgress: {100 * done_bytes // total_bytes}% "
                      f"({done_bytes // (1024 * 1024)} / {total_bytes // (1024 * 1024)} MB)",
                      end="", flush=True)

        if requests is not None:
            with requests.get(url, stream=True, timeout=(15, 60), headers=headers) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0) or 0)
                with open(part, "wb") as out:
                    for chunk in response.iter_content(256 * 1024):
                        if chunk:
                            out.write(chunk)
                            done += len(chunk)
                            show(done, total)
            return done, total

        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response, open(part, "wb") as out:
            total = int(response.headers.get("Content-Length", 0) or 0)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                show(done, total)
        return done, total

    def _download_file(self, url, dest, attempts=3):
        """Download url -> dest safely: writes dest.part, checks the size, then renames.

        A half-finished download can therefore never be mistaken for a finished file.
        Every failed attempt prints its real error so a failure can be diagnosed from the console.
        """
        dest = Path(dest)
        part = dest.with_name(dest.name + ".part")
        last_error = None

        for attempt in range(1, attempts + 1):
            try:
                print(f"Downloading ({attempt}/{attempts}): {url}")
                done, total = self._stream_to(url, part)
                print()
                if total and done != total:
                    raise IOError(f"incomplete download: got {done} of {total} bytes")
                os.replace(part, dest)          # atomic; only now does `dest` exist
                return dest
            except Exception as e:              # network drop, timeout, HTTP error, size mismatch...
                last_error = e
                part.unlink(missing_ok=True)
                print(f"\n  Attempt {attempt} failed: {type(e).__name__}: {e}")
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    print("  (HTTPS certificate problem: check the computer's date and time, and any "
                          "VPN / proxy / antivirus that inspects HTTPS traffic.)")
                status = getattr(getattr(e, "response", None), "status_code", None) or getattr(e, "code", None)
                if isinstance(status, int) and 400 <= status < 500:
                    break                       # 404 etc.: retrying the same URL will not help
            if attempt < attempts:
                time.sleep(2 * attempt)

        raise RuntimeError(f"Download failed: {url} ({type(last_error).__name__}: {last_error})")

    def setup_model(self):
        """Ensure the GGUF model exists and is complete. Re-downloads a broken/partial file."""
        if self.is_valid_model(self.model_path):
            print("Model file already exists.")
            return self.model_path

        if self.model_path.exists():
            print("Existing model file looks incomplete/corrupt - downloading it again.")
            self.model_path.unlink()

        print("Downloading Llama 3.2 1B GGUF model (approx 0.8 GB, first run only)...")
        self._download_file(MODEL_URL, self.model_path)
        if not self.is_valid_model(self.model_path):
            self.model_path.unlink(missing_ok=True)
            raise RuntimeError("Downloaded model failed validation (not a complete GGUF file).")
        return self.model_path

    # ---- backend (llama-server) --------------------------------------------------
    def _backend_urls(self):
        """Candidate download URLs for this OS/CPU, in order of preference."""
        system = platform.system()
        machine = platform.machine().lower()
        if system == "Darwin":
            is_arm = self._is_apple_silicon()
        else:
            is_arm = machine in ("arm64", "aarch64")
        arch = "arm64" if is_arm else "x64"                              # NOTE: 'x64', not 'x86_64'
        prefix = f"{RELEASE_BASE_URL}/{LLAMA_RELEASE_TAG}/llama-{LLAMA_RELEASE_TAG}-bin-"

        if system == "Windows":
            return [f"{prefix}win-cpu-{arch}.zip"]
        if system == "Darwin":
            stem = f"{prefix}macos-{arch}"
            return [stem + ".tar.gz", stem + ".zip"]      # macOS builds are .tar.gz; .zip kept as a fallback
        raise NotImplementedError(f"OS {system} is not supported for automatic binary setup.")

    @staticmethod
    def _extract(archive, dest):
        name = Path(archive).name.lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                z.extractall(dest)
        elif name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive, "r:gz") as t:
                try:
                    t.extractall(dest, filter="data")       # Python 3.12+: safe extraction
                except TypeError:
                    t.extractall(dest)                       # older Python
        else:
            raise ValueError(f"Unsupported archive type: {archive}")

    def setup_backend(self):
        """Download and extract llama-server (does nothing if it is already there)."""
        exe = self.find_server_exe()
        if exe:
            print(f"{exe.name} already installed: {exe}")
            return exe

        print(f"System: {platform.system()} {platform.machine()}, hardware: {self.detect_hardware()}")
        errors = []
        for url in self._backend_urls():
            archive = self.bin_dir / url.rsplit("/", 1)[1]
            try:
                self._download_file(url, archive)
            except RuntimeError as e:
                errors.append(str(e))
                continue
            try:
                print("Extracting server binaries...")
                self._extract(archive, self.bin_dir)
            finally:
                archive.unlink(missing_ok=True)
            exe = self.find_server_exe()
            if exe:
                break
            errors.append(f"{archive.name} did not contain {self.server_binary_name}")

        if not exe:
            raise RuntimeError("Could not set up the llama-server backend:\n  " + "\n  ".join(errors))

        if platform.system() != "Windows":
            exe.chmod(0o755)
        if platform.system() == "Darwin":
            # A downloaded binary can carry a quarantine flag that makes macOS refuse to run it.
            _run_quiet(["xattr", "-dr", "com.apple.quarantine", str(self.bin_dir)])
        print("Backend binaries setup successfully.")
        return exe

    # ---- running the server ------------------------------------------------------
    def is_server_running(self):
        """True if something answers /v1/models on our port."""
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/v1/models", timeout=1) as response:
                return response.getcode() == 200
        except Exception:
            return False

    def start_server(self):
        """Launch llama-server and wait (up to 60 s) until it answers."""
        if self.server_process:
            if self.is_server_running():
                print("Server is already running.")
                return
            self.stop_server()
        elif self.is_server_running():
            # Only possible if something started answering on our (free) port after it was picked.
            print(f"An AI server is already answering on port {self.port}; using it.")
            return

        self.setup_model()
        server_exe = self.setup_backend()

        cmd = [
            str(server_exe),
            "-m", str(self.model_path),
            "-c", "2048",
            "--host", "127.0.0.1",
            "--port", str(self.port),
        ]
        if self.detect_hardware() == "metal":
            cmd += ["-ngl", "99"]            # offload all layers to the Apple GPU
        # No "-t": llama.cpp picks a sensible thread count. No "--flash-attn": auto by default,
        # and the flag's syntax differs between llama.cpp versions.

        print(f"Starting AI server: {server_exe}")
        log_file_path = self.model_dir / "server.log"

        try:
            self.log_file = open(log_file_path, "w", encoding="utf-8")
            creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            self.server_process = subprocess.Popen(
                cmd,
                cwd=str(server_exe.parent),
                stdout=self.log_file,
                stderr=self.log_file,
                creationflags=creationflags,
            )

            self.pid_file.write_text(f"{self.server_process.pid} {os.getpid()}")

            print("Waiting for AI server to initialize", end="", flush=True)
            timeout = 60
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.server_process.poll() is not None:
                    code = self.server_process.returncode
                    hint = explain_exit_code(code)
                    raise RuntimeError(
                        f"llama-server exited with code {code}. {hint} See {log_file_path}".replace("  ", " "))
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
        """Stop the server process (if we started one)."""
        if self.server_process:
            print("\nStopping AI server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.server_process = None

        if self.log_file:
            self.log_file.close()
            self.log_file = None

        self.pid_file.unlink(missing_ok=True)
        print("Server stopped.")


if __name__ == "__main__":
    mgr = ModelManager()
    try:
        mgr.start_server()
        time.sleep(5)
        mgr.stop_server()
    except KeyboardInterrupt:
        mgr.stop_server()

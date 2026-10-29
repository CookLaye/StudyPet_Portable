import os
import platform
import subprocess

def _run_quiet(cmd):
    """Run a small helper command; return its stdout, or '' on any failure."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=flags)
        return result.stdout or ""
    except Exception:
        return ""

def get_total_ram_gb() -> float | None:
    """Returns the total physical RAM in GB."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_uint32),
                    ("dwMemoryLoad", ctypes.c_uint32),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("sullAvailExtendedVirtual", ctypes.c_uint64),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / (1024**3)
        
        elif system == "Darwin":
            # macOS: sysctl -n hw.memsize returns bytes
            out = _run_quiet(["sysctl", "-n", "hw.memsize"]).strip()
            if out:
                return int(out) / (1024**3)
        
        elif system == "Linux":
            # Linux: /proc/meminfo MemTotal: 12345678 kB
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        return int(parts[1]) / (1024**2) # kB to GB
                        
    except Exception as e:
        print(f"Error detecting RAM: {e}")
    return None

def get_cpu_threads() -> int:
    """Returns the number of logical CPU threads."""
    try:
        count = os.cpu_count()
        return count if count is not None else 1
    except Exception:
        return 1

def describe_machine() -> str:
    """One line description of the machine's hardware."""
    ram = get_total_ram_gb()
    ram_str = f"{ram:.1f} GB" if ram is not None else "Unknown"
    cpus = get_cpu_threads()
    sys_info = f"{platform.system()} {platform.machine()}"
    return f"RAM {ram_str}, {cpus} logical CPUs, {sys_info}"

if __name__ == "__main__":
    print(describe_machine())

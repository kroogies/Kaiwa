"""First-run setup: hardware detection, model recommendation, phone (Tailscale) status.

Used by the onboarding wizard to pick an Ollama model that will actually be
snappy on the user's machine, instead of making non-technical users guess.
"""
import json
import os
import platform
import subprocess


def _ram_bytes() -> int | None:
    system = platform.system()
    try:
        if system == "Darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=3))
        if system == "Linux":
            return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        if system == "Windows":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys
    except Exception:
        pass
    return None


# (model tag, approx download size, why) — tags must exist in the Ollama library.
_TIERS = {
    "fast_gpu": ("qwen3:8b", "5.2 GB",
                 "Your machine has GPU acceleration and plenty of RAM — a larger model stays fast."),
    "standard": ("qwen3:4b-instruct-2507-q4_K_M", "2.5 GB",
                 "Best balance of speed and quality for this machine."),
    "light": ("qwen3:1.7b", "1.4 GB",
              "A lighter model keeps replies quick on limited RAM."),
}


def hardware_info() -> dict:
    system = platform.system()
    arch = platform.machine()
    cores = os.cpu_count() or 1
    ram = _ram_bytes()
    ram_gb = round(ram / (1024 ** 3)) if ram else None
    apple_silicon = system == "Darwin" and arch == "arm64"

    if apple_silicon and (ram_gb or 0) >= 16:
        tier = "fast_gpu"
    elif ram_gb is not None and ram_gb < 8:
        tier = "light"
    else:
        tier = "standard"
    model, size, reason = _TIERS[tier]

    return {
        "system": system,
        "arch": arch,
        "cores": cores,
        "ram_gb": ram_gb,
        "apple_silicon": apple_silicon,
        "recommended": {"model": model, "size": size, "reason": reason},
    }


_TAILSCALE_PATHS = [
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",  # macOS app bundle
    "tailscale",                                             # PATH (brew, Linux)
    r"C:\Program Files\Tailscale\tailscale.exe",             # Windows default
]


def phone_info() -> dict:
    """Tailscale status for the 'use Kaiwa on your phone' guide."""
    for ts in _TAILSCALE_PATHS:
        try:
            out = subprocess.check_output([ts, "status", "--json"], timeout=5,
                                          stderr=subprocess.DEVNULL)
            st = json.loads(out)
            running = st.get("BackendState") == "Running"
            dns = ((st.get("Self") or {}).get("DNSName") or "").rstrip(".")
            return {"installed": True, "running": running,
                    "url": f"https://{dns}" if running and dns else None}
        except FileNotFoundError:
            continue
        except Exception:
            return {"installed": True, "running": False, "url": None}
    return {"installed": False, "running": False, "url": None}

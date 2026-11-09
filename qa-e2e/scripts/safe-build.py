"""Run a low-parallelism Windows frontend build, stopping if host RAM runs low."""
import ctypes
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
GB = 1024 ** 3

class Memory(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]

def available():
    value = Memory()
    value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise RuntimeError("Cannot read RAM")
    return value.available

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if available() < 1.75 * GB or shutil.disk_usage(ROOT).free < 10 * GB:
        raise SystemExit("Build not started: need 1.75 GiB available RAM and 10 GiB free disk.")
    env = {**os.environ, "NODE_OPTIONS":"--max-old-space-size=384", "NEXT_BUILD_CPUS":"1", "NEXT_TELEMETRY_DISABLED":"1"}
    child = subprocess.Popen(["node.exe", "--max-old-space-size=384", "node_modules/next/dist/bin/next", "build"], cwd=ROOT / "frontend", env=env, creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    def output():
        for line in iter(child.stdout.readline, b""):
            print(line.decode("utf-8", errors="replace").rstrip(), flush=True)
    reader = threading.Thread(target=output, daemon=True)
    reader.start()
    deadline = time.monotonic() + 720
    try:
        while child.poll() is None:
            if available() < GB or shutil.disk_usage(ROOT).free < 8 * GB or time.monotonic() > deadline:
                print("Stopping this build process tree: resource safety threshold reached.", flush=True)
                return 2
            time.sleep(.5)
        reader.join(timeout=3)
        return child.returncode
    finally:
        if child.poll() is None:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            child.wait(timeout=20)

if __name__ == "__main__":
    sys.exit(main())

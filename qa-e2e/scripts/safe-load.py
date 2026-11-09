"""Small read-only localhost load probe with host-memory safety guards (Windows)."""
import concurrent.futures
import ctypes
import json
import pathlib
import shutil
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "test-reports" / "safe-load.json"
GB = 1024 ** 3
stop = threading.Event()
reason = []
samples = []
results = []

class Memory(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]

def free_ram():
    value = Memory()
    value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise RuntimeError("Cannot read memory; refusing load")
    return value.available / GB

def monitor():
    while not stop.is_set():
        try:
            available = free_ram()
            samples.append(round(available, 3))
            if available < 2.5 or shutil.disk_usage(ROOT).free < 10 * GB:
                reason.append("Stopped: free RAM below 2.5 GiB or disk below 10 GiB")
                stop.set()
        except Exception:
            reason.append("Stopped: resource monitor unavailable")
            stop.set()
        stop.wait(0.5)

PATHS = ["/", "/api/v1/products?limit=20", "/tram-cuu-ho", "/api/v1/categories"]

def request(path):
    if stop.is_set():
        return None
    start = time.monotonic()
    status = 0
    size = 0
    try:
        with urllib.request.urlopen("http://127.0.0.1" + path, timeout=3) as response:
            status = response.status
            size = len(response.read(1024 * 1024))
    except Exception:
        status = 0
    return {"path": path, "status": status, "ms": round((time.monotonic()-start)*1000, 1), "bytes": size}

def main():
    before = free_ram()
    if before < 4 or shutil.disk_usage(ROOT).free < 10 * GB:
        print(f"NOT STARTED: free RAM {before:.2f} GiB; need 4 GiB and 10 GiB disk")
        return
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            for rate in (1, 3, 5):
                rows = []
                pending = set()
                started = time.monotonic()
                deadline = started + 20
                tick = started
                index = 0
                while time.monotonic() < deadline and not stop.is_set():
                    for task in list(pending):
                        if task.done():
                            row = task.result()
                            if row: rows.append(row)
                            pending.remove(task)
                    if len(rows) >= 10 and sum(r["status"] != 200 for r in rows) / len(rows) > 0.05:
                        reason.append("Stopped: request error rate over 5%")
                        stop.set()
                        break
                    if len(rows) >= 20 and sorted(r["ms"] for r in rows)[int((len(rows)-1)*.95)] > 2000:
                        reason.append("Stopped: p95 over 2 seconds")
                        stop.set()
                        break
                    if time.monotonic() >= tick:
                        if len(pending) < 5:
                            pending.add(pool.submit(request, PATHS[index % len(PATHS)]))
                            index += 1
                        tick = time.monotonic() + 1/rate
                    stop.wait(.02)
                for task in pending:
                    row = task.result()
                    if row: rows.append(row)
                elapsed = time.monotonic()-started
                latencies = sorted(r["ms"] for r in rows)
                summary = {"target_rps":rate, "completed":len(rows), "elapsed_seconds":round(elapsed,2), "observed_rps":round(len(rows)/elapsed,2), "errors":sum(r["status"] != 200 for r in rows), "p95_ms":latencies[int((len(rows)-1)*.95)] if rows else None, "max_ms":max(latencies) if rows else None}
                results.append({**summary,"requests":rows})
                print(json.dumps(summary), flush=True)
                if stop.is_set(): break
    finally:
        stop.set()
        watcher.join(timeout=1)
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps({"scope":"read-only localhost; 5 maximum in-flight requests; 3-second timeout; no browser assets or uploads", "free_ram_before_gib":before, "min_free_ram_gib":min(samples) if samples else None,"stop_reason":reason,"stages":results},indent=2),encoding="utf-8")
        print("Report:", OUT)

if __name__ == "__main__":
    main()

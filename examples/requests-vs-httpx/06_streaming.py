"""Download 50 MiB buffered and streamed with both libraries (stream_cases.py); wall time and peak RSS, one process per case."""
import subprocess
import sys

CASES = {
    "requests.get().content (buffered)": "requests_buffered",
    "requests stream=True, iter_content(1 MiB)": "requests_streamed",
    "httpx.get().content (buffered)": "httpx_buffered",
    "httpx.stream(), iter_bytes(1 MiB)": "httpx_streamed",
}
print("--- GET /bytes/52428800 (50 MiB), plain HTTP, one process per case, median of 3 runs")
unit = 1024 * 1024 if sys.platform == "darwin" else 1024   # ru_maxrss is bytes on macOS, KiB on Linux
for label, func in CASES.items():
    results = []
    for _ in range(3):
        p = subprocess.run([sys.executable, "stream_cases.py", func], capture_output=True, text=True, check=True)
        n, secs, rss = p.stdout.split()
        results.append((float(secs), int(rss)))
    results.sort()
    secs, rss = results[1]
    print(f"{label:<44} bytes {n}  median {secs:6.3f} s  peak RSS {rss / unit:6.0f} MiB")

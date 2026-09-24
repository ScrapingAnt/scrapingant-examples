"""Wall-clock time of the full HTTP call to /v2/markdown for the fixture, N sequential requests per mode (LATENCY_N, default 10). One client, one day."""
import os
import statistics
from _common import FIXTURE, call, require_key

require_key()
N = int(os.environ.get("LATENCY_N", "10"))
for browser in ("true", "false"):
    times, costs, statuses = [], set(), set()
    for _ in range(N):
        status, headers, _, secs = call("markdown", {"url": FIXTURE, "browser": browser})
        times.append(secs); costs.add(headers.get("Ant-credits-cost")); statuses.add(status)
    times.sort()
    p90 = times[min(len(times) - 1, int(round(0.9 * len(times))) - 1)] if len(times) > 1 else times[0]
    print(f"browser={browser:<5} N={N}  min {times[0]:.2f} s  median {statistics.median(times):.2f} s  p90 {p90:.2f} s  max {times[-1]:.2f} s  statuses {sorted(statuses)}  credits per call {sorted(costs)}")
print("sequential calls, one client, full request time including TLS and JSON download; numbers are this client's on this day")

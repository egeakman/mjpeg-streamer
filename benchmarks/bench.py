"""Benchmark delivered fps, latency, server CPU and bandwidth at several viewer counts.

    uv run python benchmarks/bench.py [--viewers 1 5 20] [--seconds 10] [--json out.json]

Benchmark the last release instead of the working tree (same interpreter, isolated environment):

    uv run --isolated --no-project --with mjpeg-streamer==2024.2.8 --with psutil python benchmarks/bench.py

For each viewer count it starts benchmarks/serve.py in its own process (so its CPU is measured alone), waits for a
warm-up, then N viewer threads read the stream for a fixed time. Every 5th frame is decoded to read the timestamp
the producer stamped into it. CPU is the server process's CPU time over the window, as a percentage of one core.
"""

import argparse
import http.client
import json
import os
import platform
import socket
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import psutil

import mjpeg_streamer

BOUNDARY = b"--image-boundary"
BITS, BLOCK, SRC_W, SRC_H = 32, 32, 1280, 720
HERE = Path(__file__).resolve().parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_port(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"server did not listen on {port}")


def read_stamp(jpeg: bytes) -> int | None:
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    h, w = image.shape
    y = int((BLOCK / 2) * h / SRC_H)
    millis = 0
    for bit in range(BITS):
        x = int((bit * BLOCK + BLOCK / 2) * w / SRC_W)
        if image[y, x] > 127:
            millis |= 1 << bit
    return millis


class ViewerStats:
    def __init__(self) -> None:
        self.frames = 0
        self.bytes = 0
        self.latencies_ms: list[float] = []


def view(port: int, until: float, stats: ViewerStats) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", "/bench")
    response = conn.getresponse()
    buffer = b""
    while time.monotonic() < until:
        chunk = response.read1(65536)
        if not chunk:
            break
        stats.bytes += len(chunk)
        buffer += chunk
        while True:
            start = buffer.find(BOUNDARY)
            head_end = buffer.find(b"\r\n\r\n", start)
            if start < 0 or head_end < 0:
                break
            headers = buffer[start:head_end].lower()
            length = int(headers.split(b"content-length:")[1].split(b"\r\n")[0])
            body_end = head_end + 4 + length
            if len(buffer) < body_end:
                break
            stats.frames += 1
            if stats.frames % 5 == 0:
                sent = read_stamp(buffer[head_end + 4 : body_end])
                if sent is not None:
                    now = int(time.time() * 1000) & 0xFFFFFFFF
                    stats.latencies_ms.append(float((now - sent) & 0xFFFFFFFF))
            buffer = buffer[body_end:]
    conn.close()


def run_case(viewers: int, seconds: float, warmup: float, fps: int) -> dict:
    port = free_port()
    server = subprocess.Popen(
        [
            sys.executable,
            str(HERE / "serve.py"),
            "--port",
            str(port),
            "--fps",
            str(fps),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_port(port)
        proc = psutil.Process(server.pid)
        time.sleep(warmup)
        stats = [ViewerStats() for _ in range(viewers)]
        until = time.monotonic() + seconds
        cpu_start, wall_start = proc.cpu_times(), time.monotonic()
        threads = [threading.Thread(target=view, args=(port, until, s)) for s in stats]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        cpu_end, wall = proc.cpu_times(), time.monotonic() - wall_start
    finally:
        server.kill()
        server.wait()

    cpu = (cpu_end.user + cpu_end.system) - (cpu_start.user + cpu_start.system)
    fps_each = [s.frames / wall for s in stats]
    latencies = sorted(lat for s in stats for lat in s.latencies_ms)
    return {
        "viewers": viewers,
        "target_fps": fps,
        "fps_mean": statistics.mean(fps_each),
        "fps_min": min(fps_each),
        "latency_p50_ms": statistics.median(latencies) if latencies else None,
        "latency_p95_ms": latencies[int(0.95 * (len(latencies) - 1))]
        if latencies
        else None,
        "server_cpu_pct": 100 * cpu / wall,
        "egress_kib_s": sum(s.bytes for s in stats) / wall / 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--viewers", type=int, nargs="+", default=[1, 5, 20])
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--warmup", type=float, default=2)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    env = {
        "mjpeg_streamer": getattr(mjpeg_streamer, "__version__", "?"),
        "location": str(Path(mjpeg_streamer.__file__ or ".").parent),
        "python": platform.python_version(),
        "opencv": cv2.__version__,
        "machine": f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs",
    }
    results = [run_case(n, args.seconds, args.warmup, args.fps) for n in args.viewers]
    print(json.dumps(env))
    print("| Viewers | fps mean (min) | Latency p50 / p95 | Server CPU | Egress |")
    print("|---|---|---|---|---|")
    for r in results:
        lat = (
            f"{r['latency_p50_ms']:.0f} / {r['latency_p95_ms']:.0f} ms"
            if r["latency_p50_ms"] is not None
            else "n/a"
        )
        print(
            f"| {r['viewers']} | {r['fps_mean']:.1f} ({r['fps_min']:.1f}) of {r['target_fps']} | {lat} "
            f"| {r['server_cpu_pct']:.0f}% | {r['egress_kib_s']:.0f} KiB/s |"
        )
    if args.json:
        args.json.write_text(json.dumps({"env": env, "results": results}, indent=2))


if __name__ == "__main__":
    main()

"""Benchmark server process: one stream fed by a producer thread at a fixed rate.

    python benchmarks/serve.py --port 8765 [--fps 30] [--quality 50] [--size 640x480]

Each frame is 1280x720 with the wall-clock time (milliseconds, 32 bits) stamped into its top row as black and white
blocks, so viewers can measure end-to-end latency. Only the public API shared by every release is used
(`MjpegServer`, `Stream`, `set_frame`), so the same script benchmarks 2024.2.8 and the working tree.
"""

import argparse
import threading
import time

import numpy as np

from mjpeg_streamer import MjpegServer, Stream

SRC_W, SRC_H = 1280, 720
BITS, BLOCK = 32, 32


def base_frames(count: int = 30) -> list[np.ndarray]:
    """Smooth gradients plus mild noise, so JPEG sizes resemble camera footage."""
    rng = np.random.default_rng(0)
    y, x = np.mgrid[0:SRC_H, 0:SRC_W]
    frames = []
    for i in range(count):
        b = (x * 255 / SRC_W + i * 8) % 256
        g = (y * 255 / SRC_H + i * 5) % 256
        r = ((x + y) * 255 / (SRC_W + SRC_H) + i * 3) % 256
        frame = np.dstack([b, g, r]) + rng.normal(0, 6, (SRC_H, SRC_W, 3))
        frames.append(np.clip(frame, 0, 255).astype(np.uint8))
    return frames


def stamp(frame: np.ndarray, millis: int) -> np.ndarray:
    out = frame.copy()
    for bit in range(BITS):
        value = 255 if (millis >> bit) & 1 else 0
        out[0:BLOCK, bit * BLOCK : (bit + 1) * BLOCK] = value
    return out


def produce(stream: Stream, fps: float, stop: threading.Event) -> None:
    frames = base_frames()
    interval = 1.0 / fps
    next_at = time.perf_counter()
    i = 0
    while not stop.is_set():
        stream.set_frame(
            stamp(frames[i % len(frames)], int(time.time() * 1000) & 0xFFFFFFFF)
        )
        i += 1
        next_at += interval
        time.sleep(max(0.0, next_at - time.perf_counter()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--fps", type=float, default=30)
    parser.add_argument("--quality", type=int, default=50)
    parser.add_argument("--size", default="640x480")
    args = parser.parse_args()
    width, height = (int(v) for v in args.size.split("x"))

    stream = Stream(
        "bench", size=(width, height), quality=args.quality, fps=int(args.fps)
    )
    server = MjpegServer("127.0.0.1", args.port)
    server.add_stream(stream)
    stop = threading.Event()
    threading.Thread(target=produce, args=(stream, args.fps, stop), daemon=True).start()
    server.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()

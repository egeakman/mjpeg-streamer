"""Compare JPEG encoders on camera-like frames: time per frame and output size.

    uv run --with simplejpeg --with PyTurboJPEG python benchmarks/encoders.py

Each case resizes (when the output size differs) and encodes at quality 50, like a stream does. Encoders that are
not installed, or whose native library is missing, are reported as unavailable.
"""

import statistics
import time

import cv2
import numpy as np

QUALITY = 50
CASES = [  # (source width, height) -> (output width, height)
    ((1280, 720), (640, 480)),
    ((1280, 720), (1280, 720)),
    ((1920, 1080), (1920, 1080)),
]


def camera_like(width: int, height: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    y, x = np.mgrid[0:height, 0:width]
    frame = np.dstack(
        [x * 255 / width, y * 255 / height, (x + y) * 255 / (width + height)]
    )
    return np.clip(frame + rng.normal(0, 6, frame.shape), 0, 255).astype(np.uint8)


def opencv(frame: np.ndarray) -> bytes:
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, QUALITY])
    assert ok
    return jpeg.tobytes()


def encoders() -> dict:
    found = {"opencv " + cv2.__version__: opencv}
    try:
        import simplejpeg

        found["simplejpeg " + simplejpeg.__version__] = lambda f: (
            simplejpeg.encode_jpeg(
                np.ascontiguousarray(f), quality=QUALITY, colorspace="BGR"
            )
        )
    except ImportError as exc:
        print("simplejpeg unavailable:", exc)
    try:
        from turbojpeg import TurboJPEG

        tj = TurboJPEG()
        found["PyTurboJPEG"] = lambda f: tj.encode(f, quality=QUALITY)
    except (ImportError, OSError, RuntimeError) as exc:
        print("PyTurboJPEG unavailable:", exc)
    return found


def main() -> None:
    found = encoders()
    print("| Source -> output | Encoder | ms per frame (median) | Size |")
    print("|---|---|---|---|")
    for (sw, sh), (ow, oh) in CASES:
        frame = camera_like(sw, sh)
        for name, encode in found.items():
            times, size = [], 0
            for _ in range(60):
                start = time.perf_counter()
                out = frame if (sw, sh) == (ow, oh) else cv2.resize(frame, (ow, oh))
                size = len(encode(out))
                times.append((time.perf_counter() - start) * 1000)
            print(
                f"| {sw}x{sh} -> {ow}x{oh} | {name} | {statistics.median(times[10:]):.2f} | {size // 1024} KiB |"
            )


if __name__ == "__main__":
    main()

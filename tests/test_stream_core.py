"""Phase 2 behavior of the streaming core. These are not contract tests: 2024.2.8 does not do these things."""

import asyncio
import concurrent.futures
import logging
import subprocess
import sys
import threading
import time

import cv2
import numpy as np
import pytest

import mjpeg_streamer.stream as stream_module
from mjpeg_streamer import MjpegServer, Stream
from tests.helpers import Viewer, decode, free_port, solid, wait_for_port


@pytest.fixture
def encode_counter(monkeypatch):
    """Count cv2.imencode calls made by the stream module."""
    calls = {"n": 0}
    real = cv2.imencode

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(stream_module.cv2, "imencode", counting)
    return calls


# Encode once, fan out --------------------------------------------------------------------------------------------


def test_one_frame_is_encoded_once_for_many_viewers(serve, viewer, encode_counter):
    stream = Stream("cam", fps=30)
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    port = serve(stream)
    viewers = [viewer(port, "/cam") for _ in range(10)]
    for v in viewers:
        for _ in range(3):
            v.next_part()
    assert encode_counter["n"] == 1


def test_nothing_is_encoded_without_viewers(encode_counter):
    stream = Stream("cam")
    for i in range(20):
        stream.set_frame(solid(64, 48, (i, i, i)))
    assert encode_counter["n"] == 0


def test_encodes_are_capped_at_fps(serve, viewer, encode_counter):
    stream = Stream("cam", fps=10)
    stop = threading.Event()

    def produce():
        i = 0
        while not stop.is_set():
            stream.set_frame(solid(64, 48, (i % 255, 0, 0)))
            i += 1
            time.sleep(0.002)

    producer = threading.Thread(target=produce, daemon=True)
    producer.start()
    try:
        v = viewer(serve(stream), "/cam")
        start = time.monotonic()
        while time.monotonic() - start < 1.0:
            v.next_part()
    finally:
        stop.set()
    assert encode_counter["n"] <= 13  # about 10 per second, never the producer's ~500


def test_one_stream_on_two_servers_is_encoded_once(viewer, encode_counter):
    stream = Stream("cam")
    stream.set_frame(solid(64, 48, (255, 0, 0)))
    ports = []
    for _ in range(2):
        port = free_port()
        server = MjpegServer("127.0.0.1", port)
        server.add_stream(stream)
        server.start()
        wait_for_port(port)
        ports.append(port)
    a, b = viewer(ports[0], "/cam"), viewer(ports[1], "/cam")
    assert a.next_part()["body"] == b.next_part()["body"]
    assert encode_counter["n"] == 1


def _producer(stream: Stream, fps: float, stop: threading.Event) -> threading.Thread:
    def run():
        i, next_at = 0, time.monotonic()
        while not stop.is_set():
            stream.set_frame(solid(64, 48, (i % 255, 0, 0)))
            i += 1
            next_at += 1 / fps
            time.sleep(max(0.0, next_at - time.monotonic()))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def count_parts(v, seconds: float) -> int:
    v.next_part()
    start, parts = time.monotonic(), 0
    while time.monotonic() - start < seconds:
        v.next_part()
        parts += 1
    return parts


def test_new_frames_are_delivered_at_the_target_fps(serve, viewer):
    stream = Stream("cam", fps=20)
    stop = threading.Event()
    _producer(stream, 20, stop)
    try:
        parts = count_parts(viewer(serve(stream), "/cam"), 2.0)
    finally:
        stop.set()
    assert 38 <= parts <= 42  # 20 fps for 2 s, within 5%


def test_faster_producer_is_capped_at_fps(serve, viewer):
    stream = Stream("cam", fps=20)
    stop = threading.Event()
    _producer(stream, 100, stop)
    try:
        parts = count_parts(viewer(serve(stream), "/cam"), 2.0)
    finally:
        stop.set()
    assert 38 <= parts <= 42


def test_static_scene_is_resent_close_to_fps(serve, viewer):
    stream = Stream("cam", fps=20)
    stream.set_frame(solid(64, 48, (0, 0, 255)))
    parts = count_parts(viewer(serve(stream), "/cam"), 2.0)
    assert (
        32 <= parts <= 42
    )  # re-sent every 1/fps plus a short grace (at most 10 ms) for a late frame


# Validation ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fps", [0, -1, 1001])
def test_invalid_fps_is_rejected(fps):
    with pytest.raises(ValueError, match="fps"):
        Stream("cam", fps=fps)


@pytest.mark.parametrize("fps", ["30", None, True])
def test_non_numeric_fps_is_rejected(fps):
    with pytest.raises(TypeError, match="fps"):
        Stream("cam", fps=fps)


@pytest.mark.parametrize("size", [(0, 10), (10, -1), (20000, 10)])
def test_out_of_range_size_is_rejected(size):
    with pytest.raises(ValueError, match="size"):
        Stream("cam", size=size)


@pytest.mark.parametrize("size", [(10,), (10, 10, 10), (10.0, 5), "640x480", 640])
def test_malformed_size_is_rejected(size):
    with pytest.raises(TypeError, match="size"):
        Stream("cam", size=size)


@pytest.mark.parametrize(
    ("frame", "error"),
    [
        (None, TypeError),
        ([[0, 0], [0, 0]], TypeError),
        (np.zeros((0, 10, 3), np.uint8), ValueError),
        (np.zeros((10, 10, 2), np.uint8), ValueError),
        (np.zeros((10, 10, 3), np.float32), ValueError),
        (np.zeros((10,), np.uint8), ValueError),
    ],
)
def test_invalid_frames_are_rejected(frame, error):
    with pytest.raises(error, match="frame"):
        Stream("cam").set_frame(frame)


def test_quality_setter_clamps_and_reencodes():
    stream = Stream("cam", quality=90)
    frame = np.random.default_rng(1).integers(0, 256, (48, 64, 3), dtype=np.uint8)
    stream.set_frame(frame)
    high = stream.latest_jpeg()
    stream.quality = 500
    assert stream.quality == 100
    stream.quality = 5
    assert stream.quality == 5
    assert len(stream.latest_jpeg()) < len(high)


def test_size_setter_reencodes_at_the_new_size():
    stream = Stream("cam", size=(64, 48))
    stream.set_frame(solid(160, 120, (0, 255, 0)))
    assert decode(stream.latest_jpeg()).shape[:2] == (48, 64)
    stream.size = (32, 16)
    assert decode(stream.latest_jpeg()).shape[:2] == (16, 32)


# Failures and placeholder ------------------------------------------------------------------------------------------


def test_failed_encode_skips_the_frame(serve, viewer, monkeypatch, caplog):
    stream = Stream("cam", fps=30)
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    v = viewer(serve(stream), "/cam")
    good = v.next_part()["body"]

    monkeypatch.setattr(stream_module.cv2, "imencode", lambda *a, **k: (False, None))
    with caplog.at_level(logging.WARNING, logger="mjpeg_streamer.stream"):
        stream.set_frame(solid(64, 48, (255, 0, 0)))
        bodies = [v.next_part()["body"] for _ in range(5)]
    assert all(b == good for b in bodies), "the previous frame keeps being served"
    assert sum("encoding failed" in r.getMessage() for r in caplog.records) == 1


@pytest.mark.parametrize(("size", "shape"), [((64, 48), (48, 64)), (None, (240, 320))])
def test_placeholder_is_black_at_the_stream_size(size, shape):
    image = decode(Stream("cam", size=size).latest_jpeg())
    assert image.shape[:2] == shape
    assert image.max() < 10


# Bandwidth ----------------------------------------------------------------------------------------------------------


def test_bandwidth_is_bytes_sent_per_second_over_all_viewers(serve, viewer):
    stream = Stream("cam", fps=20)
    stream.set_frame(
        np.random.default_rng(3).integers(0, 256, (120, 160, 3), dtype=np.uint8)
    )
    port = serve(stream)
    viewers = [viewer(port, "/cam") for _ in range(3)]
    first = viewers[0].next_part()
    part_len = len(first["header"]) + len(first["body"]) + len(first["gap"])
    for v in viewers[1:]:
        v.next_part()
    start, received = time.monotonic(), 0
    while time.monotonic() - start < 2.0:
        for v in viewers:
            v.next_part()
            received += part_len
    measured = stream.get_bandwidth()
    assert measured == pytest.approx(received / (time.monotonic() - start), rel=0.2)


def test_bandwidth_drops_to_zero_without_viewers():
    assert Stream("cam").get_bandwidth() == 0


# Disconnects and warnings -------------------------------------------------------------------------------------------


def test_disconnect_is_quiet(serve, caplog):
    stream = Stream("cam", fps=30)
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    port = serve(stream)
    with caplog.at_level(logging.DEBUG):
        v = Viewer(port, "/cam")
        v.next_part()
        v.close()
        time.sleep(0.3)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("disconnected" in r.getMessage() for r in caplog.records)


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_serving_raises_no_deprecation_warnings(serve, viewer):
    stream = Stream("cam")
    stream.set_frame(solid(32, 32, (1, 2, 3)))
    viewer(serve(stream), "/cam").next_part()


# Deprecated and new accessors ---------------------------------------------------------------------------------------


async def _call(coro):
    return await coro


def test_get_frame_is_deprecated_and_still_works():
    import asyncio

    stream = Stream("cam")
    frame = solid(64, 48, (0, 0, 255))
    stream.set_frame(frame)
    with pytest.warns(DeprecationWarning, match="latest_frame"):
        assert asyncio.run(_call(stream.get_frame())) is frame
    with pytest.warns(DeprecationWarning, match="latest_jpeg"):
        jpeg = asyncio.run(_call(stream.get_frame_processed()))
    assert isinstance(jpeg, np.ndarray)
    assert decode(jpeg.tobytes()).shape[:2] == (48, 64)


def test_latest_frame_and_jpeg():
    stream = Stream("cam", quality=80)
    frame = solid(64, 48, (0, 255, 0))
    stream.set_frame(frame)
    assert stream.latest_frame() is frame
    ok, expected = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    assert ok
    assert stream.latest_jpeg() == expected.tobytes()


# Concurrency regressions (found by the Phase 2 review) ------------------------------------------------------------


class _HeldPool:
    """An encoder pool whose jobs wait until the test runs them."""

    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args):
        future = concurrent.futures.Future()
        self.jobs.append((future, fn, args))
        return future

    def run_all(self):
        for future, fn, args in self.jobs:
            if future.set_running_or_notify_cancel():
                future.set_result(fn(*args))


def test_cancelling_one_caller_does_not_cancel_the_shared_encode(monkeypatch):
    pool = _HeldPool()
    monkeypatch.setattr(stream_module, "_encoder_pool", lambda: pool)
    stream = Stream("cam")
    stream.set_frame(solid(64, 48, (0, 255, 0)))

    async def scenario():
        leaving = asyncio.create_task(stream._next_part())
        staying = asyncio.create_task(stream._next_part())
        await asyncio.sleep(0)
        leaving.cancel()
        await asyncio.sleep(0)
        assert len(pool.jobs) == 1, "both callers share one encode"
        assert not pool.jobs[0][0].cancelled()
        pool.run_all()
        part = await asyncio.wait_for(staying, 2)
        assert part.startswith(b"--image-boundary")
        assert await stream._next_part() == part  # the stream is not left broken

    asyncio.run(scenario())


def test_failed_encode_does_not_poison_the_frame(monkeypatch):
    stream = Stream("cam", size=(32, 24))
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    real_resize = cv2.resize
    calls = {"n": 0}

    def flaky_resize(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise MemoryError("simulated")
        return real_resize(*args, **kwargs)

    monkeypatch.setattr(stream_module.cv2, "resize", flaky_resize)
    with pytest.raises(MemoryError):
        asyncio.run(stream._next_part())
    assert decode(asyncio.run(stream._next_part()).split(b"\r\n\r\n", 1)[1][:-4]).shape[
        :2
    ] == (24, 32)


def test_encoding_survives_interpreter_shutdown_while_threads_run(tmp_path):
    script = tmp_path / "shutdown.py"
    script.write_text(
        "import asyncio, threading, time\n"
        "import numpy as np\n"
        "from mjpeg_streamer import Stream\n"
        "stream = Stream('cam')\n"
        "stream.set_frame(np.zeros((48, 64, 3), np.uint8))\n"
        "def later():\n"
        "    time.sleep(0.5)  # the main thread has returned: the interpreter is shutting down\n"
        "    try:\n"
        "        stream.set_frame(np.full((48, 64, 3), 255, np.uint8))\n"
        "        asyncio.run(stream._next_part())\n"
        "        print('encoded after shutdown began', flush=True)\n"
        "    except Exception as exc:\n"
        "        print('failed:', repr(exc), flush=True)\n"
        "threading.Thread(target=later).start()\n"
    )
    out = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert "encoded after shutdown began" in out.stdout, out.stdout + out.stderr

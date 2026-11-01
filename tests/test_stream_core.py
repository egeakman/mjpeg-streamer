"""Phase 2 behavior of the streaming core. These are not contract tests: 2024.2.8 does not do these things."""

import asyncio
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


class _EncodeCounter:
    """Counts encodes per stream name, so streams left running by earlier tests are not counted."""

    def __init__(self):
        self.by_stream = {}

    def of(self, stream_name: str) -> int:
        return self.by_stream.get(stream_name, 0)


@pytest.fixture
def encode_counter(monkeypatch):
    counter = _EncodeCounter()
    real = Stream._encode

    def counting(self, *args, **kwargs):
        counter.by_stream[self.name] = counter.by_stream.get(self.name, 0) + 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Stream, "_encode", counting)
    return counter


def test_one_frame_is_encoded_once_for_many_viewers(serve, viewer, encode_counter):
    stream = Stream("once", fps=30)
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    port = serve(stream)
    viewers = [viewer(port, "/once") for _ in range(10)]
    for v in viewers:
        for _ in range(3):
            v.next_part()
    assert encode_counter.of("once") == 1


def test_nothing_is_encoded_without_viewers(encode_counter):
    stream = Stream("idle")
    for i in range(20):
        stream.set_frame(solid(64, 48, (i, i, i)))
    assert encode_counter.of("idle") == 0


def test_encodes_are_capped_at_fps(serve, viewer, encode_counter):
    stream = Stream("capped", fps=10)
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
        v = viewer(serve(stream), "/capped")
        start = time.monotonic()
        while time.monotonic() - start < 1.0:
            v.next_part()
    finally:
        stop.set()
    assert (
        encode_counter.of("capped") <= 13
    )  # about 10 per second, never the producer's ~500


def test_one_stream_on_two_servers_is_encoded_once(viewer, encode_counter):
    stream = Stream("shared")
    stream.set_frame(solid(64, 48, (255, 0, 0)))
    ports = []
    for _ in range(2):
        port = free_port()
        server = MjpegServer("127.0.0.1", port)
        server.add_stream(stream)
        server.start()
        wait_for_port(port)
        ports.append(port)
    a, b = viewer(ports[0], "/shared"), viewer(ports[1], "/shared")
    assert a.next_part()["body"] == b.next_part()["body"]
    assert encode_counter.of("shared") == 1


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


def test_tight_producer_keeps_the_target_fps(serve, viewer):
    """A producer much faster than fps (a video file read in a loop) must not drift the tick schedule."""
    stream = Stream("cam", fps=30)
    stop = threading.Event()

    def produce():
        frame = solid(64, 48, (0, 255, 0))
        while not stop.is_set():
            stream.set_frame(frame)
            time.sleep(0.002)

    threading.Thread(target=produce, daemon=True).start()
    try:
        parts = count_parts(viewer(serve(stream), "/cam"), 2.0)
    finally:
        stop.set()
    assert 57 <= parts <= 63  # 30 fps for 2 s, within 5%


def _paced_producer(stream: Stream, gaps: list[float], stop: threading.Event) -> None:
    def run():
        i, next_at = 0, time.monotonic()
        while not stop.is_set():
            stream.set_frame(solid(64, 48, (i % 255, 0, 0)))
            next_at += gaps[i % len(gaps)]
            i += 1
            time.sleep(max(0.0, next_at - time.monotonic()))

    threading.Thread(target=run, daemon=True).start()


@pytest.mark.parametrize(
    ("label", "gaps"),
    [
        ("30 fps camera", [1 / 30]),
        ("irregular 12/55 ms", [0.012, 0.055]),
        ("slow 20 fps camera", [1 / 20]),
    ],
)
def test_delivery_rate_is_the_stream_fps_whatever_the_producer(
    serve, viewer, label, gaps
):
    stream = Stream("cam", fps=25)
    stop = threading.Event()
    _paced_producer(stream, gaps, stop)
    try:
        parts = count_parts(viewer(serve(stream), "/cam"), 2.0)
    finally:
        stop.set()
    assert 47 <= parts <= 53, f"{label}: {parts} parts in 2 s at fps 25"


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="eager_task_factory is new in 3.12"
)
def test_join_does_not_deadlock_under_an_eager_task_factory(monkeypatch):
    calls = {"n": 0}

    async def first_tick_now(self, tick, interval):
        calls["n"] += 1
        if calls["n"] > 1:
            await asyncio.sleep(0.01)
        return True

    monkeypatch.setattr(stream_module._Fanout, "_sleep_until", first_tick_now)
    stream = Stream("cam")
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    done = threading.Event()

    async def scenario():
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        fanout = stream._join()
        await asyncio.sleep(0.05)
        stream._leave(fanout)
        done.set()

    threading.Thread(target=asyncio.run, args=(scenario(),), daemon=True).start()
    assert done.wait(3), (
        "joining deadlocked: the fan-out ran its first tick while the stream lock was held"
    )


def test_raising_fps_takes_effect_quickly(serve, viewer):
    stream = Stream("cam", fps=0.5)
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    v = viewer(serve(stream), "/cam")
    v.next_part()
    stream.fps = 30
    start = time.monotonic()
    v.next_part()
    assert time.monotonic() - start < 0.5, (
        "the old 2 s interval must not delay the new rate"
    )


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


# Concurrency regressions (found by the Phase 2 review; black-box, so they hold for any design) -------------------


def _start_server(*streams: Stream) -> int:
    port = free_port()
    server = MjpegServer("127.0.0.1", port)
    for stream in streams:
        server.add_stream(stream)
    server.start()
    wait_for_port(port)
    return port


def test_viewer_leaving_one_server_does_not_affect_another(viewer):
    stream = Stream("cam", fps=30)
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    port_a, port_b = _start_server(stream), _start_server(stream)
    stay = viewer(port_b, "/cam")
    for _ in range(5):
        leave = Viewer(port_a, "/cam")
        leave.next_part()
        leave.close()
        stream.set_frame(solid(64, 48, (0, 0, 255)))
        stay.next_part()
    stream.set_frame(solid(64, 48, (255, 0, 0)))
    assert any(
        decode(stay.next_part()["body"]).mean(axis=(0, 1)).argmax() == 0
        for _ in range(30)
    ), "the remaining viewer still gets new frames"
    late = viewer(port_a, "/cam")
    assert late.next_part()["body"][:2] == b"\xff\xd8", (
        "a new viewer on the first server still works"
    )


def test_failed_encode_does_not_poison_the_stream(serve, viewer, monkeypatch):
    stream = Stream("cam", size=(32, 24), fps=30)
    real_resize = cv2.resize
    calls = {"n": 0}

    def flaky_resize(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise MemoryError("simulated")
        return real_resize(*args, **kwargs)

    monkeypatch.setattr(stream_module.cv2, "resize", flaky_resize)
    stream.set_frame(solid(64, 48, (0, 255, 0)))
    with pytest.raises(MemoryError):
        stream.latest_jpeg()
    assert decode(stream.latest_jpeg()).shape[:2] == (24, 32)
    v = viewer(serve(stream), "/cam")
    stream.set_frame(solid(64, 48, (0, 0, 255)))
    assert decode(v.next_part()["body"]).shape[:2] == (24, 32)


def test_streaming_survives_main_thread_exit(tmp_path):
    script = tmp_path / "shutdown.py"
    script.write_text(
        "import http.client, socket, threading, time\n"
        "import numpy as np\n"
        "from mjpeg_streamer import MjpegServer, Stream\n"
        "s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()\n"
        "stream = Stream('cam', fps=30)\n"
        "server = MjpegServer('127.0.0.1', port); server.add_stream(stream); server.start()\n"
        "def produce():\n"
        "    for i in range(100):\n"
        "        stream.set_frame(np.full((48, 64, 3), i, np.uint8)); time.sleep(0.02)\n"
        "def watch():\n"
        "    time.sleep(0.5)  # the main thread has returned: the interpreter is shutting down\n"
        "    try:\n"
        "        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)\n"
        "        conn.request('GET', '/cam'); r = conn.getresponse(); data = b''\n"
        "        while data.count(b'--image-boundary') < 3:\n"
        "            data += r.read1(65536)\n"
        "        print('streamed after shutdown began', flush=True)\n"
        "    except Exception as exc:\n"
        "        print('failed:', repr(exc), flush=True)\n"
        "threading.Thread(target=produce).start()\n"
        "threading.Thread(target=watch).start()\n"
    )
    out = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "streamed after shutdown began" in out.stdout, out.stdout + out.stderr

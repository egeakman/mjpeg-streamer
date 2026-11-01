"""A stream: the latest frame, its cached JPEG part, and what was sent.

Threading model
---------------
`set_frame()` is called from any producer thread. Viewers run on one or more server event loops. Everything shared
is guarded by one `threading.Lock` and held only for a few assignments; encoding happens outside the lock.

A new frame is encoded once, by whichever viewer needs it first, on a shared worker pool (OpenCV releases the GIL
while encoding). Every other viewer, on any server, reuses the cached bytes, so cost no longer grows with the
number of viewers. Nothing is encoded while nobody is watching, and encodes are capped at the stream's fps.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import queue
import threading
import time
import warnings
from collections import deque
from numbers import Real

import cv2
import numpy as np

__all__ = ["Stream"]

log = logging.getLogger(__name__)

BOUNDARY = "image-boundary"
_PART_HEADER = (
    b"--"
    + BOUNDARY.encode()
    + b"\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
)
_PART_TRAILER = b"\r\n\r\n"  # the multipart CRLF, then the extra CRLF 2024.2.8 always sent (RULE-011)
_PLACEHOLDER_SIZE = (320, 240)  # width, height when no size is configured (RULE-004)
_MAX_SIDE = 16384


class _EncoderPool:
    """A few daemon threads that encode JPEGs.

    Not concurrent.futures.ThreadPoolExecutor: that pool refuses new work as soon as the interpreter starts shutting
    down, which happens while non-daemon threads (a user's capture loop) are still running and the daemon server
    is still serving. These workers live exactly as long as the server thread does.
    """

    def __init__(self, workers: int) -> None:
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        for i in range(workers):
            threading.Thread(
                target=self._work, name=f"mjpeg-encode-{i}", daemon=True
            ).start()

    def submit(self, fn, *args) -> concurrent.futures.Future:
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._queue.put((future, fn, args))
        return future

    def _work(self) -> None:
        while True:
            future, fn, args = self._queue.get()
            if not future.set_running_or_notify_cancel():
                continue
            try:
                result = fn(*args)
            except BaseException as exc:  # noqa: BLE001 - delivered to whoever awaits the future
                future.set_exception(exc)
            else:
                future.set_result(result)


_pool: _EncoderPool | None = None
_pool_lock = threading.Lock()


def _encoder_pool() -> _EncoderPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = _EncoderPool(min(4, os.cpu_count() or 1))
        return _pool


def _deprecated(old: str, new: str) -> None:
    warnings.warn(
        f"Stream.{old}() is deprecated and will be removed in a release at least 12 months after 2026; "
        f"use Stream.{new}() instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def _check_size(size: object) -> tuple[int, int] | None:
    if size is None:
        return None
    if (
        not isinstance(size, (tuple, list))
        or len(size) != 2
        or not all(isinstance(v, int) and not isinstance(v, bool) for v in size)
    ):
        raise TypeError(
            f"size must be None or a (width, height) pair of ints, got {size!r}"
        )
    width, height = size
    if not (0 < width <= _MAX_SIDE and 0 < height <= _MAX_SIDE):
        raise ValueError(
            f"size must be between 1 and {_MAX_SIDE} on each side, got {size!r}"
        )
    return int(width), int(height)


def _check_quality(quality: object) -> int:
    if not isinstance(quality, Real) or isinstance(quality, bool):
        raise TypeError(f"quality must be a number, got {quality!r}")
    return max(1, min(round(float(quality)), 100))  # clamped, as in 2024.2.8 (RULE-003)


def _check_fps(fps: object) -> float:
    if not isinstance(fps, Real) or isinstance(fps, bool):
        raise TypeError(f"fps must be a number, got {fps!r}")
    value = float(fps)
    if not 0 < value <= 1000:
        raise ValueError(f"fps must be greater than 0 and at most 1000, got {fps!r}")
    return value


def _check_frame(frame: object) -> np.ndarray:
    if not isinstance(frame, np.ndarray):
        raise TypeError(f"frame must be a numpy array, got {type(frame).__name__}")
    if (
        frame.size == 0
        or frame.ndim not in (2, 3)
        or (frame.ndim == 3 and frame.shape[2] not in (1, 3, 4))
    ):
        raise ValueError(
            f"frame must be a non-empty HxW, HxWx1, HxWx3 or HxWx4 image, got shape {frame.shape}"
        )
    if frame.dtype != np.uint8:
        raise ValueError(f"frame must have dtype uint8, got {frame.dtype}")
    return frame


def _jpeg_part(frame: np.ndarray, quality: int) -> bytes | None:
    """The frame as a complete multipart part, or None if OpenCV could not encode it."""
    try:
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    except cv2.error:
        return None
    if not ok or jpeg is None:
        return None
    body = jpeg.tobytes()
    return (_PART_HEADER % len(body)) + body + _PART_TRAILER


class _RateMeter:
    """Bytes per second over a rolling window, safe to use from any thread."""

    def __init__(self, window: float = 1.0) -> None:
        self._window = window
        self._samples: deque[tuple[float, int]] = deque()
        self._total = 0
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self._window
        while self._samples and self._samples[0][0] <= cutoff:
            self._total -= self._samples.popleft()[1]

    def add(self, nbytes: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._samples.append((now, nbytes))
            self._total += nbytes
            self._prune(now)

    def rate(self) -> float:
        with self._lock:
            self._prune(time.monotonic())
            return self._total / self._window


class _Fanout:
    """Delivery for one stream on one event loop.

    A single ticker task wakes on the stream's tick, gets that tick's part once, and resolves one shared future that
    every viewer on the loop is waiting on. Viewers keep no timers of their own; one that is still writing when a
    tick fires simply picks up the next one. Ticks sit on the shared monotonic clock, so viewers on every server ask
    for the same frame at the same moment and it is encoded once. Lives on its loop's thread, except for the viewer
    count (stream lock).
    """

    def __init__(self, stream: Stream, loop: asyncio.AbstractEventLoop) -> None:
        self.stream = stream
        self.loop = loop
        self.viewers = 0
        self.sent = 0  # bytes written by this loop's viewers since the last flush
        self.waiter: asyncio.Future[bytes] = loop.create_future()
        self.task = loop.create_task(self._run(), name=f"mjpeg-fanout:{stream.name}")

    async def _run(self) -> None:
        tick = float("-inf")
        try:
            while True:
                interval = 1 / self.stream.fps
                now = self.loop.time()
                # Ticks sit just after the moment frames arrive (see Stream.set_frame), so a camera running at
                # the stream's fps has each frame sent right away instead of waiting up to a full interval.
                offset = self.stream._arrival_phase + min(interval / 4, 0.006)
                next_tick = ((now - offset) // interval + 1) * interval + offset
                # Woke a hair before the tick: don't serve it twice.
                if next_tick <= tick + interval / 2:
                    next_tick += interval
                tick = next_tick
                await asyncio.sleep(tick - now)
                part = await self.stream._next_part()
                waiter, self.waiter = self.waiter, self.loop.create_future()
                waiter.set_result(part)
                self.flush()
        except Exception as exc:
            log.exception("Stream %r: frame delivery stopped", self.stream.name)
            self._fail(exc)
        finally:
            # However the task ends (cancelled when the last viewer leaves, or failed), nobody may be left waiting.
            self._fail(
                ConnectionResetError(f"delivery of stream {self.stream.name!r} stopped")
            )

    def _fail(self, exc: BaseException) -> None:
        if not self.waiter.done():
            self.waiter.set_exception(exc)
            self.waiter.exception()  # mark it retrieved: there may be no viewer left to await it

    async def next_part(self) -> bytes:
        # shield: a viewer that disconnects must not cancel the future the other viewers share
        return await asyncio.shield(self.waiter)

    def flush(self) -> None:
        if self.sent:
            self.stream._sent.add(self.sent)
            self.sent = 0


class Stream:
    """One MJPEG stream: give it frames with `set_frame()` and add it to one or more servers.

    Args:
        name: Stream name. Lower-cased with spaces replaced by underscores; the result is its URL path.
        size: Output (width, height), or None to keep each frame's own size. Frames are not letterboxed.
        quality: JPEG quality, clamped to 1-100.
        fps: Frames per second sent to each viewer. The last frame is re-sent until a new one arrives.
    """

    def __init__(
        self,
        name: str,
        size: tuple[int, int] | None = None,
        quality: int = 50,
        fps: float = 30,
    ) -> None:
        self.name = name.lower().casefold().replace(" ", "_")
        self._lock = threading.Lock()
        self._size = _check_size(size)
        self._quality = _check_quality(quality)
        self._fps = _check_fps(fps)
        self._params = (
            0  # bumped whenever size or quality changes, so cached JPEGs are re-encoded
        )
        self._frame: np.ndarray | None = None
        self._frame_seq = 0  # 0 means "no frame yet": the placeholder is served
        self._part: bytes | None = None  # cached multipart part for _part_key
        self._part_key: tuple[int, int] | None = None  # (frame_seq, params)
        self._pending: concurrent.futures.Future[bytes] | None = None
        self._pending_key: tuple[int, int] | None = None
        self._fanouts: dict[asyncio.AbstractEventLoop, _Fanout] = {}
        self._arrival_phase = (
            0.0  # when, within a 1/fps interval, the latest frame arrived
        )
        self._sent = _RateMeter()
        self._warned_encode_failure = False

    # Configuration --------------------------------------------------------------------------------------------

    @property
    def size(self) -> tuple[int, int] | None:
        return self._size

    @size.setter
    def size(self, value: tuple[int, int] | None) -> None:
        size = _check_size(value)
        with self._lock:
            self._size = size
            self._params += 1

    @property
    def quality(self) -> int:
        return self._quality

    @quality.setter
    def quality(self, value: int) -> None:
        quality = _check_quality(value)
        with self._lock:
            self._quality = quality
            self._params += 1

    @property
    def fps(self) -> float:
        return self._fps

    @fps.setter
    def fps(self, value: float) -> None:
        self._fps = _check_fps(value)

    # Producer side ----------------------------------------------------------------------------------------------

    def set_frame(self, frame: np.ndarray) -> None:
        """Make `frame` the stream's latest frame. Safe to call from any thread.

        The array is used as is, without a copy: do not modify it afterwards.
        """
        frame = _check_frame(frame)
        now = time.monotonic()
        with self._lock:
            self._frame = frame
            self._frame_seq += 1
            self._arrival_phase = now % (1 / self._fps)

    def latest_frame(self) -> np.ndarray:
        """The latest frame, or the black placeholder if none was set yet."""
        with self._lock:
            frame, size = self._frame, self._size
        return frame if frame is not None else self._placeholder(size)

    def latest_jpeg(self) -> bytes:
        """The latest frame as JPEG bytes, encoded in the calling thread if it is not cached yet."""
        with self._lock:
            key = (self._frame_seq, self._params)
            part = self._part if self._part_key == key else None
            frame, size, quality = self._frame, self._size, self._quality
        if part is None:
            part = self._encode(key, frame, size, quality)
        return part[part.index(b"\r\n\r\n") + 4 : -len(_PART_TRAILER)]

    def get_bandwidth(self) -> float:
        """Bytes per second sent to all viewers of this stream, over the last second."""
        return self._sent.rate()

    # Deprecated (2024.2.8 API) ------------------------------------------------------------------------------------

    async def get_frame(self) -> np.ndarray:
        """Deprecated: use `latest_frame()`."""
        _deprecated("get_frame", "latest_frame")
        return self.latest_frame()

    async def get_frame_processed(self) -> np.ndarray:
        """Deprecated: use `latest_jpeg()`. Returns the JPEG bytes as a uint8 array, as 2024.2.8 did."""
        _deprecated("get_frame_processed", "latest_jpeg")
        part = await self._next_part()
        body = part[part.index(b"\r\n\r\n") + 4 : -len(_PART_TRAILER)]
        return np.frombuffer(body, dtype=np.uint8)

    # Server side (used by the handler) ---------------------------------------------------------------------------

    async def _next_part(self) -> bytes:
        """The multipart part to send now: cached if current, otherwise encoded once on the worker pool.

        Each loop's fan-out calls this once per tick, on the same ticks for every loop, and concurrent calls for the
        same frame share one encode: a frame is encoded at most once, and encodes never exceed fps.
        """
        pool = (
            _encoder_pool()
        )  # created outside the stream lock: starting threads must not stall producers
        with self._lock:
            key = (self._frame_seq, self._params)
            if self._part is not None and self._part_key == key:
                return self._part
            if (
                self._pending is not None
                and self._pending_key == key
                and not self._pending.done()  # a failed or cancelled encode is retried, never reused
            ):
                future = self._pending
            else:
                frame, size, quality = self._frame, self._size, self._quality
                future = pool.submit(self._encode, key, frame, size, quality)
                self._pending, self._pending_key = future, key
        # shield: cancelling one caller (a viewer leaving, a server stopping) must not cancel the encode that
        # callers on other loops share
        return await asyncio.shield(asyncio.wrap_future(future))

    def _encode(
        self,
        key: tuple[int, int],
        frame: np.ndarray | None,
        size: tuple[int, int] | None,
        quality: int,
    ) -> bytes:
        try:
            return self._encode_part(key, frame, size, quality)
        finally:
            with self._lock:
                if self._pending_key == key:
                    self._pending, self._pending_key = None, None

    def _encode_part(
        self,
        key: tuple[int, int],
        frame: np.ndarray | None,
        size: tuple[int, int] | None,
        quality: int,
    ) -> bytes:
        if frame is None:
            frame = self._placeholder(size)
        target = size or (frame.shape[1], frame.shape[0])
        if (frame.shape[1], frame.shape[0]) != target:
            frame = cv2.resize(frame, target)
        part = _jpeg_part(frame, quality)
        if part is not None:
            with self._lock:
                if self._part_key is None or key >= self._part_key:
                    self._part, self._part_key = part, key
            return part
        with self._lock:
            previous = self._part
            warn, self._warned_encode_failure = not self._warned_encode_failure, True
        if warn:
            log.warning(
                "Stream %r: JPEG encoding failed; serving the previous frame", self.name
            )
        if previous is not None:
            return previous
        part = _jpeg_part(self._placeholder(size), quality)
        if part is None:
            raise RuntimeError("OpenCV cannot encode JPEG images")
        return part

    def _join(self) -> _Fanout:
        """Register a viewer on the running event loop and return that loop's fan-out."""
        loop = asyncio.get_running_loop()
        with self._lock:
            fanout = self._fanouts.get(loop)
            if fanout is None or fanout.task.done():
                fanout = self._fanouts[loop] = _Fanout(self, loop)
            fanout.viewers += 1
        return fanout

    def _leave(self, fanout: _Fanout) -> None:
        with self._lock:
            fanout.viewers -= 1
            if fanout.viewers == 0:
                fanout.task.cancel()
                if self._fanouts.get(fanout.loop) is fanout:
                    del self._fanouts[fanout.loop]
        fanout.flush()

    def _viewer_count(self) -> int:
        with self._lock:
            return sum(f.viewers for f in self._fanouts.values())

    @staticmethod
    def _placeholder(size: tuple[int, int] | None) -> np.ndarray:
        width, height = size or _PLACEHOLDER_SIZE
        return np.zeros((height, width, 3), dtype=np.uint8)

    def __repr__(self) -> str:
        return f"Stream(name={self.name!r}, size={self._size!r}, quality={self._quality}, fps={self._fps})"

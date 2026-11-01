"""Behavior Contract: what each frame looks like on the wire (RULE-005, RULE-006, RULE-007)."""

import time

import cv2
import numpy as np
import pytest
from conftest import decode, solid

from mjpeg_streamer import Stream

pytestmark = pytest.mark.contract

RED, GREEN, BLUE = (0, 0, 255), (0, 255, 0), (255, 0, 0)


def dominant_channel(image: np.ndarray) -> int:
    return int(np.argmax(image.reshape(-1, image.shape[-1]).mean(axis=0)))


def wait_for_channel(v, channel: int, attempts: int = 30) -> bool:
    return any(
        dominant_channel(decode(v.next_part()["body"])) == channel
        for _ in range(attempts)
    )


def test_rule_005_latest_frame_wins(serve, viewer):
    stream = Stream("cam", fps=30)
    stream.set_frame(solid(64, 48, RED))
    stream.set_frame(solid(64, 48, BLUE))  # replaces RED before any viewer tick
    v = viewer(serve(stream), "/cam")

    for _ in range(3):
        assert dominant_channel(decode(v.next_part()["body"])) == 0, (
            "only the latest frame (blue) is served"
        )

    stream.set_frame(solid(64, 48, GREEN))
    assert wait_for_channel(v, 1), "a newer frame replaces the old one"


def test_rule_005_last_frame_repeats_until_replaced(serve, viewer):
    stream = Stream("cam", fps=30)
    stream.set_frame(solid(64, 48, GREEN))
    v = viewer(serve(stream), "/cam")
    time.sleep(0.2)

    bodies = [v.next_part()["body"] for _ in range(4)]
    assert all(dominant_channel(decode(b)) == 1 for b in bodies)


def test_rule_006_resized_to_configured_size(serve, viewer):
    stream = Stream("cam", size=(64, 48))
    stream.set_frame(solid(160, 120, GREEN))
    v = viewer(serve(stream), "/cam")

    assert decode(v.next_part()["body"]).shape[:2] == (48, 64)


def test_rule_006_aspect_ratio_not_preserved(serve, viewer):
    stream = Stream("cam", size=(100, 20))
    stream.set_frame(solid(160, 120, GREEN))
    v = viewer(serve(stream), "/cam")

    assert decode(v.next_part()["body"]).shape[:2] == (20, 100)


def test_rule_006_native_size_when_no_size(serve, viewer):
    stream = Stream("cam")
    stream.set_frame(solid(160, 120, GREEN))
    v = viewer(serve(stream), "/cam")

    assert decode(v.next_part()["body"]).shape[:2] == (120, 160)


def test_rule_007_jpeg_at_stream_quality(serve, viewer):
    frame = np.random.default_rng(7).integers(0, 256, (48, 64, 3), dtype=np.uint8)
    stream = Stream("cam", quality=37)
    stream.set_frame(frame)
    v = viewer(serve(stream), "/cam")

    ok, expected = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 37])
    assert ok
    assert v.next_part()["body"] == expected.tobytes()


def test_rule_007_quality_changes_the_encoding(serve, viewer):
    frame = np.random.default_rng(7).integers(0, 256, (48, 64, 3), dtype=np.uint8)
    low, high = Stream("low", quality=10), Stream("high", quality=95)
    low.set_frame(frame)
    high.set_frame(frame)
    port = serve(low, high)

    assert len(viewer(port, "/low").next_part()["body"]) < len(
        viewer(port, "/high").next_part()["body"]
    )

"""Behavior Contract: the MJPEG wire format clients parse (RULE-009, RULE-011).

OctoPrint, Home Assistant, VLC and browsers read these bytes, so they must not drift.
"""

import pytest
from conftest import solid

from mjpeg_streamer import Stream

pytestmark = pytest.mark.contract


def test_rule_009_stream_response_header(serve, viewer):
    stream = Stream("cam")
    stream.set_frame(solid(64, 48, (0, 128, 255)))
    v = viewer(serve(stream), "/cam")

    assert v.response.status == 200
    assert v.response.reason == "OK"
    assert (
        v.response.getheader("Content-Type")
        == "multipart/x-mixed-replace;boundary=image-boundary"
    )


def test_rule_011_part_layout(serve, viewer):
    stream = Stream("cam", quality=50, fps=30)
    stream.set_frame(solid(64, 48, (200, 200, 200)))
    v = viewer(serve(stream), "/cam")

    for _ in range(3):
        part = v.next_part()
        length = len(part["body"])
        assert part["header"] == (
            b"--image-boundary\r\nContent-Type: image/jpeg\r\n"
            + f"Content-Length: {length}\r\n\r\n".encode()
        )
        assert part["body"][:2] == b"\xff\xd8", "JPEG must start with SOI"
        assert part["body"][-2:] == b"\xff\xd9", "JPEG must end with EOI"
        assert part["gap"] == b"\r\n\r\n", (
            "multipart CRLF plus the extra CRLF, then the next boundary"
        )


def test_rule_011_stream_keeps_flowing_and_never_closes_boundary(serve, viewer):
    stream = Stream("cam", fps=30)
    stream.set_frame(solid(32, 32, (10, 20, 30)))
    v = viewer(serve(stream), "/cam")

    parts = [v.next_part() for _ in range(10)]
    assert len(parts) == 10
    assert b"--image-boundary--" not in v.buffer

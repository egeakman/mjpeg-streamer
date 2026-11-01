"""Property-based tests for Stream configuration and encoding (Phase 2)."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from mjpeg_streamer import Stream
from tests.helpers import decode

sizes = st.tuples(st.integers(1, 640), st.integers(1, 480))


@settings(max_examples=60, deadline=None)
@given(
    size=sizes, quality=st.integers(-50, 200), channels=st.sampled_from([None, 1, 3, 4])
)
def test_any_valid_frame_is_served_at_the_configured_size(size, quality, channels):
    shape = (37, 53) if channels is None else (37, 53, channels)
    stream = Stream("cam", size=size, quality=quality)
    stream.set_frame(np.full(shape, 128, np.uint8))
    assert 1 <= stream.quality <= 100
    assert decode(stream.latest_jpeg()).shape[:2] == (size[1], size[0])


@settings(max_examples=60, deadline=None)
@given(
    frame=arrays(
        np.uint8, st.tuples(st.integers(1, 64), st.integers(1, 64), st.just(3))
    )
)
def test_native_size_is_kept_for_any_frame(frame):
    stream = Stream("cam")
    stream.set_frame(frame)
    assert decode(stream.latest_jpeg()).shape[:2] == frame.shape[:2]


@settings(max_examples=100, deadline=None)
@given(fps=st.floats(allow_nan=True, allow_infinity=True))
def test_fps_is_accepted_only_in_range(fps):
    if 0 < fps <= 1000:
        assert Stream("cam", fps=fps).fps == fps
    else:
        with pytest.raises(ValueError, match="fps"):
            Stream("cam", fps=fps)

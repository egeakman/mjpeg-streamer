"""Behavior Contract: server defaults, routing and serving (RULE-015, RULE-022, RULE-023)."""

import http.client
import inspect

import pytest

from mjpeg_streamer import MjpegServer, Stream
from tests.helpers import solid

pytestmark = pytest.mark.contract


def test_rule_015_default_bind_is_localhost_8080():
    params = inspect.signature(MjpegServer).parameters
    assert params["host"].default == "localhost"
    assert params["port"].default == 8080


def test_rule_022_duplicate_route_rejected():
    server = MjpegServer("127.0.0.1", 0)
    server.add_stream(Stream("Front Door"))
    with pytest.raises(ValueError, match="already exists"):
        server.add_stream(Stream("front_door"))


def test_rule_022_same_stream_on_two_servers_is_allowed():
    stream = Stream("cam")
    MjpegServer("127.0.0.1", 0).add_stream(stream)
    MjpegServer("127.0.0.1", 0).add_stream(stream)


def test_rule_023_streams_and_index_served_together(serve):
    a, b = Stream("Cam A"), Stream("cam_b")
    a.set_frame(solid(32, 32, (0, 0, 255)))
    b.set_frame(solid(32, 32, (255, 0, 0)))
    port = serve(a, b)

    for path in ("/cam_a", "/cam_b"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type", "").startswith(
            "multipart/x-mixed-replace"
        )
        conn.close()

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/")
    index = conn.getresponse()
    assert index.status == 200
    assert index.getheader("Content-Type", "").startswith("text/html")
    page = index.read().decode()
    assert "/cam_a" in page
    assert "/cam_b" in page
    conn.close()

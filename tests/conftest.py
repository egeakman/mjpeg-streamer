"""Fixtures shared by all tests.

Contract tests (tests/contract) run against the working tree and against the released 2024.2.8 wheel (CI baseline
job), so these fixtures only use the public API both versions share. Servers are never stopped: in 2024.2.8, stop()
raises SystemExit in the caller (RULE-026). Each test uses its own port and the server thread is a daemon.
"""

import pytest

from mjpeg_streamer import MjpegServer, Stream
from tests.helpers import Viewer, free_port, wait_for_port


@pytest.fixture
def serve():
    """serve(*streams) starts a server on a free loopback port and returns the port."""

    def _serve(*streams: Stream) -> int:
        port = free_port()
        server = MjpegServer("127.0.0.1", port)
        for stream in streams:
            server.add_stream(stream)
        server.start()
        wait_for_port(port)
        return port

    return _serve


@pytest.fixture
def viewer():
    opened = []

    def _viewer(port: int, path: str) -> Viewer:
        v = Viewer(port, path)
        opened.append(v)
        return v

    yield _viewer
    for v in opened:
        v.close()

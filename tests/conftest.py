"""Camera-free helpers shared by the contract tests.

The same suite runs against the working tree and against the released 2024.2.8 wheel (see the CI baseline job), so
it only uses the public API both versions share. Servers are never stopped: in 2024.2.8, stop() raises SystemExit in
the caller (RULE-026). Each test uses its own port and the server thread is a daemon.
"""

import http.client
import socket
import time

import cv2
import numpy as np
import pytest

from mjpeg_streamer import MjpegServer, Stream

BOUNDARY = b"--image-boundary"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"nothing is listening on port {port}")


def solid(width: int, height: int, bgr: tuple[int, int, int]) -> np.ndarray:
    return np.full((height, width, 3), bgr, dtype=np.uint8)


def decode(jpeg: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_UNCHANGED)
    assert image is not None, "part body is not a decodable image"
    return image


class Viewer:
    """Reads one MJPEG stream the way a browser does (HTTP/1.1, chunked) and splits it into parts."""

    def __init__(self, port: int, path: str) -> None:
        self.conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.conn.request("GET", path)
        self.response = self.conn.getresponse()
        self.buffer = b""

    def _fill(self) -> None:
        chunk = self.response.read1(65536)
        if not chunk:
            raise EOFError("stream ended")
        self.buffer += chunk

    def next_part(self) -> dict:
        """Return {"header": raw header bytes, "headers": {lower-name: value}, "body": bytes, "gap": bytes}.

        "gap" is everything between the end of the body and the next boundary.
        """
        while BOUNDARY not in self.buffer:
            self._fill()
        start = self.buffer.index(BOUNDARY)
        while b"\r\n\r\n" not in self.buffer[start:]:
            self._fill()
        header_end = self.buffer.index(b"\r\n\r\n", start) + 4
        header = self.buffer[start:header_end]
        headers = {}
        for line in header.split(b"\r\n")[1:]:
            if b":" in line:
                key, value = line.split(b":", 1)
                headers[key.strip().lower().decode()] = value.strip().decode()
        length = int(headers["content-length"])
        while BOUNDARY not in self.buffer[header_end + length :]:
            self._fill()
        body = self.buffer[header_end : header_end + length]
        next_start = self.buffer.index(BOUNDARY, header_end + length)
        gap = self.buffer[header_end + length : next_start]
        self.buffer = self.buffer[next_start:]
        return {"header": header, "headers": headers, "body": body, "gap": gap}

    def close(self) -> None:
        self.conn.close()


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

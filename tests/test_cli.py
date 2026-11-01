"""Behavior Contract: CLI sources and stream names (RULE-031, RULE-032).

The CLI runs in a subprocess. A small wrapper records what cv2.VideoCapture is asked to open, and never opens a
real camera: a device index is swapped for a missing file, so the tests are safe on a machine with webcams.
"""

import http.client
import os
import subprocess
import sys

import cv2
import numpy as np
import pytest
from conftest import free_port, wait_for_port

pytestmark = [pytest.mark.contract, pytest.mark.cli]

WRAPPER = """
import sys
import cv2

_real = cv2.VideoCapture

def _recording(source, *args, **kwargs):
    print("OPEN", type(source).__name__, repr(source), flush=True)
    return _real(source if isinstance(source, str) else "no-such-device.avi", *args, **kwargs)

cv2.VideoCapture = _recording
sys.argv = ["mjpeg-streamer"] + sys.argv[1:]
from mjpeg_streamer.cli import main
main()
"""


def write_video(path, frames: int = 15) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 15, (64, 48))
    assert writer.isOpened(), "OpenCV cannot write MJPG/AVI here"
    for i in range(frames):
        writer.write(np.full((48, 64, 3), (i * 15) % 255, np.uint8))
    writer.release()


def run_cli(cwd, *args):
    port = free_port()
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            WRAPPER,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            *args,
        ],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, port


def stop(proc) -> str:
    proc.kill()
    out, _ = proc.communicate(timeout=10)
    return out


def get_status(port: int, path: str) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    response = conn.getresponse()
    status, ctype = response.status, response.getheader("Content-Type", "")
    conn.close()
    return status, ctype


def test_rule_031_digit_source_opens_a_camera_index(tmp_path):
    proc, port = run_cli(tmp_path, "-s", "7")
    try:
        wait_for_port(port)
        status, ctype = get_status(port, "/source_7")
    finally:
        out = stop(proc)
    assert "OPEN int 7" in out
    assert status == 200
    assert ctype.startswith("multipart/x-mixed-replace")


def test_rule_031_non_digit_source_is_a_path(tmp_path):
    write_video(tmp_path / "clip.avi")
    proc, port = run_cli(tmp_path, "-s", "clip.avi")
    try:
        wait_for_port(port)
    finally:
        out = stop(proc)
    assert "OPEN str 'clip.avi'" in out


def test_rule_032_stream_named_prefix_and_sanitized_source(tmp_path):
    write_video(tmp_path / "video file.avi")
    proc, port = run_cli(
        tmp_path, "-s", "video file.avi", "-s", "7", "--prefix", "ender 3 pro"
    )
    try:
        wait_for_port(port)
        file_status, _ = get_status(port, "/ender_3_pro_video_file_avi")
        cam_status, _ = get_status(port, "/ender_3_pro_7")
    finally:
        stop(proc)
    assert file_status == 200
    assert cam_status == 200

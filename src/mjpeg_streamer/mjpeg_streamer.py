"""Kept so `from mjpeg_streamer.mjpeg_streamer import MjpegServer, Stream` (the 2024.2.8 layout) still works."""

from .server import MjpegServer
from .stream import Stream

__all__ = ["MjpegServer", "Stream"]

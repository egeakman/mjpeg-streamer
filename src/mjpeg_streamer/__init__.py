from importlib.metadata import version

from .mjpeg_streamer import MjpegServer, Stream

__all__ = ["MjpegServer", "Stream"]
__version__ = version("mjpeg-streamer")

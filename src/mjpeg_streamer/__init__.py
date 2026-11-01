from importlib.metadata import version

from .server import MjpegServer
from .stream import Stream

__all__ = ["MjpegServer", "Stream"]
__version__ = version("mjpeg-streamer")

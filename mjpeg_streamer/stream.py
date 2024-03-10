import asyncio
import time
import uuid
from collections import deque
from typing import Deque, List, Optional, Set, Tuple, Union

import cv2
import numpy as np


class StreamBase:
    def __init__(
        self,
        name: str,
        fps: int = 30,
    ) -> None:
        if type(self) is StreamBase:
            raise TypeError(
                "StreamBase is an abstract class and cannot be instantiated"
            )
        self.name = name.lower().casefold().replace(" ", "_")
        self.fps = fps
        self._frame: np.ndarray = np.zeros((320, 240, 1), dtype=np.uint8)
        self._lock: asyncio.Lock = asyncio.Lock()
        self._frame_buffer: Deque[int,] = deque(maxlen=fps)
        self._bandwidth_last_modified_time: float = time.time()
        self._deque_background_task: Optional[asyncio.Task] = None
        self._active_viewers: Set[str,] = set()

    async def _add_viewer(self, viewer_token: Optional[str] = None) -> str:
        viewer_token = viewer_token or str(uuid.uuid4())
        self._active_viewers.add(viewer_token)
        return viewer_token

    async def _remove_viewer(self, viewer_token: str) -> None:
        self._active_viewers.discard(viewer_token)

    async def __clear_deque(self) -> None:
        while True:
            await asyncio.sleep(1 / self.fps)
            if (
                len(self._frame_buffer) > 0
                and time.time() - self._bandwidth_last_modified_time >= 1
            ):
                self._frame_buffer.clear()

    async def _ensure_background_tasks(self) -> None:
        if self._deque_background_task is None or self._deque_background_task.done():
            self._deque_background_task = asyncio.create_task(self.__clear_deque())

    def _check_encoding(self, frame: np.ndarray) -> str:
        if isinstance(frame, np.ndarray) and frame.ndim == 1 and frame.size > 2:
            # Check JPEG header (0xFFD8) and footer (0xFFD9)
            if (
                frame[0] == 255
                and frame[1] == 216
                and frame[-2] == 255
                and frame[-1] == 217
            ):
                return "jpeg"
            return "one-dim-non-jpeg"
        if isinstance(frame, np.ndarray):
            return "multi-dim"
        return "unknown"

    def settings(self) -> None:
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            print(f"{key}: {value}")

    def has_demand(self) -> bool:
        return len(self._active_viewers) > 0

    def active_viewers(self) -> int:
        return len(self._active_viewers)

    def get_bandwidth(self) -> float:
        return sum(self._frame_buffer)

    def set_fps(self, fps: int) -> None:
        self.fps = fps

    # Method for delivering the frame to the StreamHandler
    async def _get_frame(self) -> np.ndarray:
        # A little hacky, if you have a better way, please let me know
        await self._ensure_background_tasks()
        # Checking here to avoid continous polling
        if self._check_encoding(self._frame) != "jpeg":
            raise ValueError(
                "Input is not an encoded JPEG frame. Use OpenCV's imencode method to encode the frame to JPEG."
            )
        self._frame_buffer.append(len(self._frame.tobytes()))
        self._bandwidth_last_modified_time = time.time()
        async with self._lock:
            return self._frame

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = frame

    # Not very useful, but it's here for the sake of completeness
    def get_frame(self) -> np.ndarray:
        return self._frame


class Stream(StreamBase):
    def __init__(
        self,
        name: str,
        fps: int = 30,
        size: Optional[Tuple[int, int]] = None,
        quality: int = 50,
    ) -> None:
        self.size = size
        self.quality = max(1, min(quality, 100))
        self._is_encoded = False
        super().__init__(name, fps)

    async def __process_current_frame(self) -> np.ndarray:
        if not self._is_encoded:
            frame = cv2.resize(
                self._frame, self.size or (self._frame.shape[1], self._frame.shape[0])
            )
            val, frame = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality]
            )
            if not val:
                raise ValueError("Error encoding frame")
            self._frame_buffer.append(len(frame.tobytes()))
            self._bandwidth_last_modified_time = time.time()
            return frame
        return self._frame

    async def _get_frame(self) -> np.ndarray:
        await self._ensure_background_tasks()
        async with self._lock:
            return await self.__process_current_frame()

    def set_size(self, size: Tuple[int, int]) -> None:
        self.size = size

    def set_quality(self, quality: int) -> None:
        self.quality = max(1, min(quality, 100))

    def set_frame(self, frame: np.ndarray) -> None:
        self._is_encoded = False
        if self._check_encoding(frame) == "jpeg":
            print(
                "The frame is already encoded, I will not encode it again. \
                    Consider using CustomStream if you want to handle the processing yourself."
            )
            self._is_encoded = True
        self._frame = frame

    def get_frame(self) -> np.ndarray:
        return super().get_frame()


class CustomStream(StreamBase):
    # Same as StreamBase, but with a friendly name
    def __init__(
        self,
        name: str,
        fps: int = 30,
    ) -> None:
        super().__init__(name, fps)


class ManagedStream(StreamBase):
    def __init__(
        self,
        name: str,
        fps: int = 30,
        size: Optional[Tuple[int, int]] = None,
        quality: int = 50,
        source: Union[int, str] = 0,
        mode: str = "fast-on-demand",
        poll_delay_ms: Optional[Union[float, int]] = None,
    ) -> None:
        self.mode = mode
        self._available_modes: List[str,] = ["fast-on-demand", "full-on-demand"]
        if self.mode not in self._available_modes:
            raise ValueError(f"Invalid mode. Available modes: {self._available_modes}")
        self.size = size
        self.quality = max(1, min(quality, 100))
        self.source = source
        self.poll_delay_ms = poll_delay_ms / 1000 if poll_delay_ms else 1 / fps
        self._cap_is_open: bool = False
        self._cap: cv2.VideoCapture = cv2.VideoCapture(self.source)
        self._cap_background_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        super().__init__(name, fps)

    async def _ensure_background_tasks(self) -> None:
        await super()._ensure_background_tasks()
        if self._cap_background_task is None or self._cap_background_task.done():
            self._cap_background_task = asyncio.create_task(self.__manage_cap_state())

    async def __manage_cap_state(self) -> None:
        while True:
            await asyncio.sleep(self.poll_delay_ms)
            if self.mode == "full-on-demand":
                if self.has_demand() and not self._cap_is_open:
                    self.__open_cap()
                elif not self.has_demand() and self._cap_is_open:
                    self.__close_cap()
            elif not self._cap_is_open:
                self.__open_cap()

    def __open_cap(self) -> None:
        if not self._cap_is_open:
            self._cap = cv2.VideoCapture(self.source)
            if not self._cap.isOpened():
                raise ValueError("Cannot open the capture device")
            self._cap_is_open = True

    def __close_cap(self) -> None:
        if self._cap_is_open:
            self._cap.release()
            self._cap_is_open = False

    async def __read_frame(self) -> None:
        if self._cap_is_open:
            val, frame = self._cap.read()
            if not val:
                raise ValueError("Error reading frame")
            self._frame = frame
        else:
            self.__open_cap()

    async def __process_current_frame(self) -> np.ndarray:
        if not self.has_demand():
            return self._frame
        await self.__read_frame()
        frame = cv2.resize(
            self._frame, self.size or (self._frame.shape[1], self._frame.shape[0])
        )
        val, frame = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality]
        )
        if not val:
            raise ValueError("Error encoding frame")
        self._frame_buffer.append(len(frame.tobytes()))
        self._bandwidth_last_modified_time = time.time()
        return frame

    async def _get_frame(self) -> np.ndarray:
        if not self._is_running:
            raise RuntimeError("Stream has not started yet")
        await self._ensure_background_tasks()
        async with self._lock:
            return await self.__process_current_frame()

    def set_size(self, size: Tuple[int, int]) -> None:
        self.size = size

    def set_quality(self, quality: int) -> None:
        self.quality = max(1, min(quality, 100))

    def set_frame(self, frame: np.ndarray) -> None:
        raise NotImplementedError(
            "This method is not available for ManagedStream, use Stream or CustomStream instead."
        )

    def change_mode(self, mode: str) -> None:
        if mode not in self._available_modes:
            raise ValueError(f"Invalid mode. Available modes: {self._available_modes}")
        self.mode = mode

    def change_source(self, source: Union[int, str]) -> None:
        self.source = source
        if self._cap_is_open:
            self.__close_cap()
            self.__open_cap()

    def set_poll_delay_ms(self, poll_delay_ms: float) -> None:
        self.poll_delay_ms = poll_delay_ms / 1000

    def start(self) -> None:
        if not self._is_running:
            self._is_running = True
        else:
            raise RuntimeError("Stream has already started")

    def stop(self) -> None:
        if self._is_running:
            self._is_running = False
            self._cap_background_task.cancel()
            if self._cap_is_open:
                self.__close_cap()
        else:
            raise RuntimeError("Stream has already stopped")

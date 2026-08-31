import asyncio
import time
import uuid
from collections import deque
from typing import Deque, Dict, List, Optional, Set, Tuple, Union

import cv2
import numpy as np


class StreamBase:
    def __init__(
        self,
        name: str,
        fps: int = 30,
    ) -> None:
        self.name = name.casefold().replace(" ", "_")
        self.fps = fps
        self._frame: np.ndarray = np.zeros((320, 240, 1), dtype=np.uint8)
        self._last_processed_frame: np.ndarray = cv2.imencode(
            ".jpg", self._frame, [cv2.IMWRITE_JPEG_QUALITY, 1]
        )[1]
        self._lock: asyncio.Lock = asyncio.Lock()
        self._frames_buffer: Deque[int] = deque(maxlen=fps)
        self._bandwidth_last_modified_time: float = time.time()
        self._active_viewers: Set[str] = set()
        self._tasks: Dict[str, asyncio.Task] = {"_clear_bandwidth": None}

    async def _ensure_background_tasks(self) -> None:
        for task_name, task in self._tasks.items():
            if task is None or task.done():
                self._tasks[task_name] = asyncio.create_task(
                    eval(f"self.{task_name}()")
                )

    async def _clear_bandwidth(self) -> None:
        while True:
            await asyncio.sleep(1.0 / self.fps)
            if (
                len(self._frames_buffer) > 0
                and time.time() - self._bandwidth_last_modified_time >= 1
            ):
                self._frames_buffer.clear()

    async def _add_viewer(self, viewer_token: Optional[str] = None) -> str:
        viewer_token = viewer_token or str(uuid.uuid4())
        async with self._lock:
            self._active_viewers.add(viewer_token)
        return viewer_token

    async def _remove_viewer(self, viewer_token: str) -> None:
        async with self._lock:
            self._active_viewers.discard(viewer_token)

    async def _process_current_frame(self) -> np.ndarray:
        self._last_processed_frame = self._frame
        return self._frame

    async def __check_encoding(self, frame: np.ndarray) -> str:
        if isinstance(frame, np.ndarray) and frame.ndim == 1 and frame.size > 2:
            # Check JPG header (0xFFD8) and footer (0xFFD9)
            if (
                frame[0] == 255
                and frame[1] == 216
                and frame[-2] == 255
                and frame[-1] == 217
            ):
                return "jpg"
            return "one-dim-non-jpg"
        if isinstance(frame, np.ndarray):
            return "multi-dim"
        return "unknown"

    async def _resize_and_encode_frame(
        self, frame: np.ndarray, size: Tuple[int, int], quality: int
    ) -> np.ndarray:
        resized_frame = cv2.resize(frame, size)
        if not await self.__check_encoding(resized_frame) == "jpg":
            val, encoded_frame = cv2.imencode(
                ".jpg", resized_frame, [cv2.IMWRITE_JPEG_QUALITY, quality]
            )
        if not val:
            raise ValueError(
                f"Error encoding frame. Format/shape: {await self.__check_encoding(resized_frame)}"
            )
        return encoded_frame

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
        return sum(self._frames_buffer)

    def set_fps(self, fps: int) -> None:
        self.fps = fps
        self._frames_buffer = deque(maxlen=fps)

    async def _get_frame(self) -> np.ndarray:
        await self._ensure_background_tasks()  # A little hacky
        if time.time() - self._bandwidth_last_modified_time <= 1.0 / self.fps:
            return self._last_processed_frame  # Prevents redundant processing
        async with self._lock:
            self._frames_buffer.append(len(self._last_processed_frame.tobytes()))
            self._bandwidth_last_modified_time = time.time()
            return await self._process_current_frame()

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = frame


class Stream(StreamBase):
    def __init__(
        self,
        name: str,
        fps: int = 30,
        size: Optional[Tuple[int, int]] = None,
        quality: int = 50,
    ) -> None:
        super().__init__(name, fps)
        self.size = size
        self.quality = max(1, min(quality, 100))
        self._last_processed_frame: np.ndarray = np.zeros((320, 240, 1), dtype=np.uint8)

    async def _process_current_frame(self) -> np.ndarray:
        frame = await self._resize_and_encode_frame(
            self._frame,
            self.size or (self._frame.shape[1], self._frame.shape[0]),
            self.quality,
        )
        self._last_processed_frame = frame
        return frame

    def set_size(self, size: Tuple[int, int]) -> None:
        self.size = size

    def set_quality(self, quality: int) -> None:
        self.quality = max(1, min(quality, 100))


class ManagedStream(StreamBase):
    def __init__(
        self,
        name: str,
        source: Union[int, str] = 0,
        fps: int = 30,
        size: Optional[Tuple[int, int]] = None,
        quality: int = 50,
        mode: str = "fast-on-demand",
        poll_delay_ms: Optional[Union[float, int]] = None,
    ) -> None:
        super().__init__(name, fps)
        self.source = source
        self.mode = mode
        self._available_modes: List[str,] = ["fast-on-demand", "full-on-demand"]
        if self.mode not in self._available_modes:
            raise ValueError(f"Invalid mode. Available modes: {self._available_modes}")
        self.size = size
        self.quality = max(1, min(quality, 100))
        self.poll_delay_seconds = poll_delay_ms / 1000.0 if poll_delay_ms else 1.0 / fps
        self._cap_is_open: bool = False
        self._cap: cv2.VideoCapture = None
        self._is_running: bool = False
        self._tasks["_manage_cap_state"] = None

    async def _manage_cap_state(self) -> None:
        while True:
            await asyncio.sleep(self.poll_delay_seconds)
            if self.mode == "full-on-demand":
                if self.has_demand() and not self._cap_is_open:
                    async with self._lock:
                        await self.__open_cap()
                elif not self.has_demand() and self._cap_is_open:
                    async with self._lock:
                        await self.__close_cap()
            elif not self._cap_is_open:
                async with self._lock:
                    await self.__open_cap()

    async def __open_cap(self) -> None:
        if not self._cap_is_open and self._is_running:
            self._cap = cv2.VideoCapture(self.source)
            if not self._cap.isOpened():
                raise ValueError("Cannot open the capture device")
            self._cap_is_open = True

    async def __close_cap(self) -> None:
        if self._cap_is_open and self._is_running:
            self._cap.release()
            self._cap_is_open = False

    async def __read_frame(self) -> None:
        if self._cap_is_open and self._is_running:
            val, frame = self._cap.read()
            if not val:
                async with self._lock:
                    val, frame = self._cap.read()
                    if not val:
                        raise RuntimeError("Error reading frame")
            self._frame = frame
        else:
            await self.__open_cap()

    async def _process_current_frame(self) -> np.ndarray:
        if not self.has_demand():
            return self._last_processed_frame
        await self.__read_frame()
        frame = await self._resize_and_encode_frame(
            self._frame,
            self.size or (self._frame.shape[1], self._frame.shape[0]),
            self.quality,
        )
        self._last_processed_frame = frame
        return frame

    async def _get_frame(self) -> np.ndarray:
        if not self._is_running:
            raise RuntimeError(
                "Stream is not running, please call the start method first."
            )
        return await super()._get_frame()

    def set_size(self, size: Tuple[int, int]) -> None:
        self.size = size

    def set_quality(self, quality: int) -> None:
        self.quality = max(1, min(quality, 100))

    def set_frame(self, frame: np.ndarray) -> None:
        raise NotImplementedError(
            "This method is not available for ManagedStream, use Stream or StreamBase instead."
        )

    def change_mode(self, mode: str) -> None:
        if mode not in self._available_modes:
            print(f"Invalid mode. Available modes: {self._available_modes}")
        self.mode = mode

    def change_source(self, source: Union[int, str]) -> None:
        self.source = source
        self.__close_cap()
        self.__open_cap()

    def set_poll_delay_ms(self, poll_delay_ms: float) -> None:
        self.poll_delay_seconds = poll_delay_ms / 1000.0

    def start(self) -> None:
        if not self._is_running:
            self._is_running = True
        else:
            print("Stream has already started")

    def stop(self) -> None:
        if self._is_running:
            for task in self._tasks.values():
                if task and not task.done():
                    task.cancel()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.__close_cap())
            loop.close() if loop.is_running() else None
            self._is_running = False
            self._cap_is_open = False
        else:
            print("Stream has already stopped")

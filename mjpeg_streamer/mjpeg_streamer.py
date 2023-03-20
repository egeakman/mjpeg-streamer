import asyncio
import threading
from typing import List, Optional, Tuple

import aiohttp
import cv2
import numpy as np
from aiohttp import MultipartWriter, web
from aiohttp.web_runner import GracefulExit


class Stream:
    def __init__(
        self,
        name: str,
        size: Optional[Tuple[int, int]] = None,
        quality: int = 50,
        fps: int = 24,
    ) -> None:
        self.name = name
        self.size = size
        self.quality = max(1, min(quality, 100))
        self.fps = fps
        self._frame = np.zeros((320, 240, 1), dtype=np.uint8)
        self._lock = asyncio.Lock()

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = frame

    async def _get_frame(self) -> np.ndarray:
        async with self._lock:
            return self._frame


class _StreamHandler:
    def __init__(self, stream: Stream) -> None:
        self._stream = stream

    async def __call__(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "multipart/x-mixed-replace;boundary=image-boundary"
            },
        )
        await response.prepare(request)

        while True:
            await asyncio.sleep(1 / self._stream.fps)
            frame = await self._stream._get_frame()
            frame = cv2.resize(
                frame, self._stream.size or (frame.shape[1], frame.shape[0])
            )
            val, frame = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._stream.quality]
            )

            if not val:
                print("Error while encoding frame")
                break

            with MultipartWriter("image/jpeg", boundary="image-boundary") as mpwriter:
                mpwriter.append(frame.tobytes(), {"Content-Type": "image/jpeg"})
                try:
                    await mpwriter.write(response, close_boundary=False)
                except ConnectionResetError:
                    print("Client connection closed")
                    break
            await response.write(b"\r\n")


class MjpegServer:
    def __init__(self, host: str = "localhost", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._app = web.Application()
        self._cam_routes: List[str,] = []

    async def __root_handler(self, _) -> web.Response:
        text = "<h2>Available streams:</h2>\n\n"
        for route in self._cam_routes:
            text += f"<a href='http://{self._host}:{self._port}{route}'>{route}</a>\n\n"
        return aiohttp.web.Response(text=text, content_type="text/html")

    def add_stream(self, stream: Stream) -> None:
        route = f"/{stream.name}"
        if route in self._cam_routes:
            raise ValueError(f"Route {route} already exists")
        self._cam_routes.append(route)
        self._app.router.add_route("GET", route, _StreamHandler(stream))

    def __start_func(self) -> None:
        self._app.router.add_route("GET", "/", self.__root_handler)
        runner = web.AppRunner(self._app)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, self._host, self._port)
        loop.run_until_complete(site.start())
        loop.run_forever()

    def start(self) -> None:
        thread = threading.Thread(target=self.__start_func, daemon=True)
        thread.start()

    def stop(self) -> None:
        raise GracefulExit()

from __future__ import annotations

import asyncio
import sys
import threading
from typing import Optional, Union

import aiohttp
import cv2
import netifaces
import numpy as np
from aiohttp import MultipartWriter, web
from aiohttp.web_runner import GracefulExit


class Stream:
    def __init__(
        self,
        name: str,
        size: Optional[tuple[int, int]] = None,
        quality: int = 50,
        fps: int = 24,
    ) -> None:
        self.name = name.lower().casefold().replace(" ", "_")
        self.size = size
        self.quality = max(1, min(quality, 100))
        self.fps = fps
        self._frame = np.zeros((320, 240, 1), dtype=np.uint8)
        self._lock = asyncio.Lock()

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = frame

    def get_bandwidth(self) -> float:
        global byte_frame_size
        if len(byte_frame_size) > self.fps:
            for _ in range(len(byte_frame_size) - self.fps):
                byte_frame_size.pop(0)
        return sum(byte_frame_size)

    async def get_frame(self) -> np.ndarray:
        async with self._lock:
            return self._frame


class _StreamHandler:
    def __init__(self, stream: Stream) -> None:
        global byte_frame_size
        self._stream = stream
        byte_frame_size = []

    async def __call__(self, request: web.Request) -> web.StreamResponse:
        global byte_frame_size
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
            frame = await self._stream.get_frame()
            frame = cv2.resize(
                frame, self._stream.size or (frame.shape[1], frame.shape[0])
            )
            val, frame = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._stream.quality]
            )

            if not val:
                print("Error while encoding frame")
                break

            byte_frame_size.append(sys.getsizeof(frame.tobytes()))

            with MultipartWriter("image/jpeg", boundary="image-boundary") as mpwriter:
                mpwriter.append(frame.tobytes(), {"Content-Type": "image/jpeg"})
                try:
                    await mpwriter.write(response, close_boundary=False)
                except ConnectionResetError:
                    return web.Response(status=499, text="Client closed the connection")
            await response.write(b"\r\n")


class MjpegServer:
    def __init__(self, host: Union[str, int] = "localhost", port: int = 8080) -> None:
        if isinstance(host, str) and host != "0.0.0.0":
            self._host = [host]
        elif isinstance(host, list):
            if "0.0.0.0" in host:
                host.remove("0.0.0.0")
                host = host + [
                    netifaces.ifaddresses(iface)[netifaces.AF_INET][0]["addr"]
                    for iface in netifaces.interfaces()
                    if netifaces.AF_INET in netifaces.ifaddresses(iface)
                ]
            self._host = list(dict.fromkeys(host))
        else:
            self._host = [
                netifaces.ifaddresses(iface)[netifaces.AF_INET][0]["addr"]
                for iface in netifaces.interfaces()
                if netifaces.AF_INET in netifaces.ifaddresses(iface)
            ]
        self._port = port
        self._app = web.Application()
        self._app.is_running = False
        self._cap_routes: list[str,] = []

    def is_running(self) -> bool:
        return self._app.is_running

    async def __root_handler(self, _) -> web.Response:
        text = "<h2>Available streams:</h2>\n\n"
        for route in self._cap_routes:
            text += (
                f"<a href='http://{self._host[0]}:{self._port}{route}'>{route}</a>\n\n"
            )
        return aiohttp.web.Response(text=text, content_type="text/html")

    def add_stream(self, stream: Stream) -> None:
        if self.is_running():
            raise RuntimeError("Cannot add stream after the server has started")
        route = f"/{stream.name}"
        if route in self._cap_routes:
            raise ValueError(f"A stream with the name {route} already exists")
        self._cap_routes.append(route)
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
        if not self.is_running():
            thread = threading.Thread(target=self.__start_func, daemon=True)
            thread.start()
            self._app.is_running = True
        else:
            print("\nServer is already running\n")

        print("\nAvailable streams:\n")
        for addr in self._host:
            for route in self._cap_routes:  # route has a leading slash
                print(f"http://{addr}:{self._port!s}{route}")
            print("--------------------------------")
        print("\nPress Ctrl+C to stop the server\n")

    def stop(self) -> None:
        if self.is_running():
            self._app.is_running = False
            raise GracefulExit
        print("\nServer is not running\n")

import asyncio
import threading
from typing import List, Union

import aiohttp
from aiohttp import MultipartWriter, web
from aiohttp.web_runner import GracefulExit
from multidict import MultiDict

from .stream import StreamBase


class _StreamHandler:
    def __init__(self, stream: StreamBase) -> None:
        self._stream = stream

    async def __call__(self, request: web.Request) -> web.StreamResponse:
        viewer_token = request.cookies.get("viewer_token")
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "multipart/x-mixed-replace;boundary=image-boundary"
            },
        )
        await response.prepare(request)
        if not viewer_token:
            viewer_token = await self._stream._add_viewer()
            response.set_cookie("viewer_token", viewer_token)
        elif viewer_token not in self._stream._active_viewers:
            await self._stream._add_viewer(viewer_token)
        try:
            while True:
                try:
                    await asyncio.sleep(1 / self._stream.fps)
                    frame = await self._stream._get_frame()
                    with MultipartWriter(
                        "image/jpeg", boundary="image-boundary"
                    ) as mpwriter:
                        mpwriter.append(
                            frame.tobytes(),
                            MultiDict({"Content-Type": "image/jpeg"}),
                        )
                        await mpwriter.write(response, close_boundary=False)
                    await response.write(b"\r\n")
                except (ConnectionResetError, ConnectionAbortedError):
                    break
        finally:
            await self._stream._remove_viewer(viewer_token)
        return response


class Server:
    def __init__(
        self, host: Union[str, List[str,]] = "localhost", port: int = 8080
    ) -> None:
        if isinstance(host, str):
            self._host: List[str,] = [
                host,
            ]
        elif isinstance(host, list):
            if "0.0.0.0" in host:
                host = ["0.0.0.0"]
            if "localhost" in host and "127.0.0.1" in host:
                host.remove("localhost")
            self._host = list(set(host))
        self._port = port
        self._app: web.Application = web.Application()
        self._app_is_running: bool = False
        self._cap_routes: List[str,] = []

    def is_running(self) -> bool:
        return self._app_is_running

    async def __root_handler(self, _) -> web.Response:
        text = "<h2>Available streams:</h2>"
        for route in self._cap_routes:
            text += f"<a href='http://{self._host[0]}:{self._port}{route}'>{route}</a>\n<br>\n"
        return aiohttp.web.Response(text=text, content_type="text/html")

    def add_stream(self, stream: StreamBase) -> None:
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
            self._app_is_running = True
        else:
            print("\nServer is already running\n")

        for addr in self._host:
            print(f"\nStreams index: http://{addr}:{self._port!s}")
            print("Available streams:\n")
            for route in self._cap_routes:  # route has a leading slash
                print(f"http://{addr}:{self._port!s}{route}")
            print("--------------------------------\n")
        print("\nPress Ctrl+C to stop the server\n")

    def stop(self) -> None:
        if self.is_running():
            self._app_is_running = False
            print("\nStopping...\n")
            GracefulExit()
            print("\nServer stopped\n")
        else:
            print("\nServer is not running\n")


class MjpegServer(Server):
    # Alias for Server, to maintain backwards compatibility
    def __init__(
        self, host: Union[str, List[str,]] = "localhost", port: int = 8080
    ) -> None:
        super().__init__(host, port)

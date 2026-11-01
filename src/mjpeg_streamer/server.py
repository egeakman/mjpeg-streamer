"""The HTTP server that serves streams.

The server lifecycle below (start, stop, host handling) is still the 2024.2.8 behavior; it is rebuilt in a later
phase. The per-viewer stream handler is new.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable

import aiohttp
import netifaces
from aiohttp import web
from aiohttp.web_runner import GracefulExit

from .stream import BOUNDARY, Stream

__all__ = ["MjpegServer"]

log = logging.getLogger(__name__)

CONTENT_TYPE = f"multipart/x-mixed-replace;boundary={BOUNDARY}"


def _stream_handler(
    stream: Stream,
) -> Callable[[web.Request], Awaitable[web.StreamResponse]]:
    async def handler(request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200, reason="OK", headers={"Content-Type": CONTENT_TYPE}
        )
        await response.prepare(request)
        fanout = None
        try:
            fanout = stream._join()
            part = await stream._next_part()  # the first frame goes out right away
            while True:
                await response.write(part)
                fanout.sent += len(part)
                part = (
                    await fanout.next_part()
                )  # then one part per tick, shared by every viewer
        except ConnectionError:
            log.debug("Viewer of %r disconnected (%s)", stream.name, request.remote)
        finally:
            if fanout is not None:
                stream._leave(fanout)
        return response

    return handler


class MjpegServer:
    def __init__(self, host: str | int = "localhost", port: int = 8080) -> None:
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
        self._cap_routes: list[str] = []

    def is_running(self) -> bool:
        return self._app.is_running

    async def __root_handler(self, _) -> web.Response:
        text = "<h2>Available streams:</h2>"
        for route in self._cap_routes:
            text += f"<a href='http://{self._host[0]}:{self._port}{route}'>{route}</a>\n<br>\n"
        return aiohttp.web.Response(text=text, content_type="text/html")

    def add_stream(self, stream: Stream) -> None:
        if self.is_running():
            raise RuntimeError("Cannot add stream after the server has started")
        route = f"/{stream.name}"
        if route in self._cap_routes:
            raise ValueError(f"A stream with the name {route} already exists")
        self._cap_routes.append(route)
        self._app.router.add_route("GET", route, _stream_handler(stream))

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

        for addr in self._host:
            print(f"\nStreams index: http://{addr}:{self._port!s}")
            print("Available streams:\n")
            for route in self._cap_routes:  # route has a leading slash
                print(f"http://{addr}:{self._port!s}{route}")
            print("--------------------------------\n")
        print("\nPress Ctrl+C to stop the server\n")

    def stop(self) -> None:
        if self.is_running():
            self._app.is_running = False
            print("\nStopping...\n")
            raise GracefulExit
        print("\nServer is not running\n")

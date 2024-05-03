import time

from mjpeg_streamer import ManagedStream, Server

server = Server()
stream = ManagedStream(
    "test",
    source=0,
    fps=30,
    size=(640, 480),
    quality=50,
    mode="fast-on-demand",
    poll_delay_ms=None,
)

server.add_stream(stream)
server.start()
stream.start()

while True:
    time.sleep(1 / 30)

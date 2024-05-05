import time

from mjpeg_streamer import ManagedStream, Server

server = Server(host="0.0.0.0", port=8080)
stream = ManagedStream(
    "test",
    source=0,
    fps=30,
    size=(640, 480),
    quality=50,
    mode="full-on-demand",
    poll_delay_ms=None,
)

server.add_stream(stream)
server.start()
stream.start()

print(stream.settings())

while True:
    time.sleep(1 / 30)
    print(stream.get_bandwidth() / 1024, "KB/s", end="\r")

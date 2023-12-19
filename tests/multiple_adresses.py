from mjpeg_streamer import MjpegServer, Stream
from time import sleep

cap = 0

stream = Stream("first_source", cap, size=(640, 480), quality=50, fps=30)

# You can have a single server running on multiple addresses
server = MjpegServer(["localhost", "192.168.1.100"], 8080)
server.add_stream(stream)
server.start()

while input() == 'q':
    pass

server.stop()
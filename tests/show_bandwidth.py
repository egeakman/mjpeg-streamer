from mjpeg_streamer import MjpegServer, Stream
from time import sleep

cap = 0

stream = Stream("my_source", cap, size=(640, 480), quality=50, fps=30)

server = MjpegServer("localhost", 8080)
server.add_stream(stream)
server.start()


while True:
    # Print the bandwidth in KB/s
    print(round(stream.get_bandwidth() / 1024, 2), "KB/s")
    sleep(1)

server.stop()

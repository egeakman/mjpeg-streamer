from mjpeg_streamer import MjpegServer, Stream

cap = 0

stream = Stream("my_source", cap, size=(640, 480), quality=50, fps=30)

server = MjpegServer("localhost", 8080)
server.add_stream(stream)
server.start()

while input() != 'q':
    pass

server.stop()

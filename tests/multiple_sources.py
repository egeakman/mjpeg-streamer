from mjpeg_streamer import MjpegServer, Stream

cap = 0
cap2 = "best_mjpeg_streamer.mp4"

# You can have multiple sources feeding different streams
stream = Stream("first_source", cap, size=(640, 480), quality=50, fps=30)
stream2 = Stream("second_source", cap2, size=(320, 240), quality=40, fps=24)
stream3 = Stream("third_source", cap2, size=(640, 480), quality=80, fps=15)

# You can also have a single server streaming multiple streams
server = MjpegServer("localhost", 8080)
server.add_stream(stream)
server.add_stream(stream2)
server.start()


while input() != 'q':
    pass

server.stop()

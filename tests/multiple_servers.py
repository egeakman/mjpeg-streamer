from mjpeg_streamer import MjpegServer, Stream

cap = 0

# You can feed multiple streams from the same source
stream = Stream("my_source", cap, size=(640, 480), quality=50, fps=30)
stream2 = Stream("my_source2", cap, size=(320, 240), quality=20, fps=10)

# You can also have multiple servers streaming the same stream
server = MjpegServer("localhost", 8080)
server2 = MjpegServer("192.168.1.100", 8080)
server3 = MjpegServer("localhost", 8081)
server.add_stream(stream)
server2.add_stream(stream)
server3.add_stream(stream2)
server.start()
server2.start()
server3.start()

while input() != 'q':
    pass

server.stop()
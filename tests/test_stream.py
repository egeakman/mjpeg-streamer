import cv2

from mjpeg_streamer import Server, Stream

capture = cv2.VideoCapture(0)

server = Server(host="0.0.0.0", port=8080)
stream = Stream("test", fps=30, size=(640, 480), quality=50)
server.add_stream(stream)
server.start()

print(stream.settings())

while True:
    frame = capture.read()[1]
    stream.set_frame(frame)
    print(stream.get_bandwidth() / 1024, "KB/s", end="\r")

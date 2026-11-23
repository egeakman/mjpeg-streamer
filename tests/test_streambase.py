import cv2

from mjpeg_streamer import Server, StreamBase

capture = cv2.VideoCapture(0)

server = Server(host="0.0.0.0", port=8080)
stream = StreamBase("test", fps=30)

server.add_stream(stream)
server.start()

print(stream.settings())

while True:
    frame = capture.read()[1]
    frame = cv2.imencode(".jpg", frame)[1]
    stream.set_frame(frame)
    print(stream.get_bandwidth() / 1024, "KB/s", end="\r")

import cv2

from mjpeg_streamer import Server, StreamBase

capture = cv2.VideoCapture(0)

server = Server()
stream = StreamBase("test", fps=30)

server.add_stream(stream)
server.start()

while True:
    frame = capture.read()[1]
    frame = cv2.imencode(".jpg", frame)[1]
    stream.set_frame(frame)

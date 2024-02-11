import os

import cv2

from mjpeg_streamer import MjpegServer, Stream

print(os.getpid())

cap = cv2.VideoCapture(0)

stream = Stream("my_source", size=(640, 480), quality=50, fps=30)

server = MjpegServer("localhost", 8080)
server.add_stream(stream)
server.start()

while True:
    _, frame = cap.read()
    stream.set_frame(frame)

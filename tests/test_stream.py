import cv2

from mjpeg_streamer import Server, Stream

capture = cv2.VideoCapture(0)

server = Server()
stream = Stream("test", fps=30, size=(640, 480), quality=50)
server.add_stream(stream)
server.start()

while True:
    frame = capture.read()[1]
    stream.set_frame(frame)

import cv2
from mjpeg_streamer import MjpegServer, Stream

cap = cv2.VideoCapture(0)

stream = Stream("first_source", size=(640, 480), quality=50, fps=30)

# You can have a single server running on multiple addresses
server = MjpegServer(["localhost", "192.168.1.100"], 8080)
server.add_stream(stream)
server.start()

while True:
    _, frame = cap.read()
    cv2.imshow(stream.name, frame)
    if cv2.waitKey(1) == ord("q"):
        break

    stream.set_frame(frame)

server.stop()
cap.release()
cv2.destroyAllWindows()

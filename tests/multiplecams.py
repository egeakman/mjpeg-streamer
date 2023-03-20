import cv2
from mjpeg_streamer import MjpegServer, Stream

cap = cv2.VideoCapture(0)
cap2 = cv2.VideoCapture(1)

stream = Stream("first_cam", size=(640, 480), quality=50, fps=30)
stream2 = Stream("second_cam", size=(320, 240), quality=80, fps=15)

server = MjpegServer("localhost", 8080)
server.add_stream(stream)
server.add_stream(stream2)
server.start()

while True:
    _, frame = cap.read()
    _, frame2 = cap2.read()
    cv2.imshow(stream.name, frame)
    cv2.imshow(stream2.name, frame2)
    if cv2.waitKey(1) == ord("q"):
        break

    stream.set_frame(frame)
    stream2.set_frame(frame2)

server.stop()
cap.release()
cap2.release()
cv2.destroyAllWindows()

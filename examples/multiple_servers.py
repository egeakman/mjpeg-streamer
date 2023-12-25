import cv2
from mjpeg_streamer import MjpegServer, Stream

cap = cv2.VideoCapture(0)

# You can feed multiple streams from the same source
stream = Stream("my_source", size=(640, 480), quality=50, fps=30)
stream2 = Stream("my_source2", size=(320, 240), quality=20, fps=10)

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

while True:
    _, frame = cap.read()
    cv2.imshow(stream.name, frame)
    if cv2.waitKey(1) == ord("q"):
        break

    stream.set_frame(frame)
    stream2.set_frame(frame)

server.stop()
server2.stop()
server3.stop()
cap.release()
cv2.destroyAllWindows()

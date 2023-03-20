import cv2
from mjpeg_streamer import MjpegServer, Stream

cap = cv2.VideoCapture(0)
cap2 = cv2.VideoCapture("best_mjpeg_streamer.mp4")

# You can have multiple sources feeding different streams
stream = Stream("first_source", size=(640, 480), quality=50, fps=30)
stream2 = Stream("second_source", size=(320, 240), quality=40, fps=24)
stream3 = Stream("third_source", size=(640, 480), quality=80, fps=15)

# You can also have a single server streaming multiple streams
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

    # Here we set the same frame to both first and second stream,
    # that way we can stream the same source with different settings
    stream.set_frame(frame)
    stream2.set_frame(frame)

    # Here we stream a video file to the third stream
    stream3.set_frame(frame2)

server.stop()
cap.release()
cap2.release()
cv2.destroyAllWindows()

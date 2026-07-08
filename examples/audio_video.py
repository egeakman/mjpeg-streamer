"""Example: Stream webcam video + microphone audio together."""

import cv2
from mjpeg_streamer import AudioStream, MjpegServer, Stream

# Video source (webcam 0)
cap = cv2.VideoCapture(0)

# Video stream
video = Stream("camera", size=(640, 480), quality=50, fps=30)

# Audio stream (default microphone)
audio = AudioStream("microphone")

server = MjpegServer("localhost", 8080)
server.add_stream(video)
server.add_stream(audio)
server.start()

print("Open http://localhost:8080/player in your browser")

while True:
    _, frame = cap.read()
    video.set_frame(frame)
    if cv2.waitKey(1) == ord("q"):
        break

audio.stop()
server.stop()
cap.release()
cv2.destroyAllWindows()

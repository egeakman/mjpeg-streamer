import cv2

from mjpeg_streamer.mjpeg_streamer import MjpegServer, Stream

# Create a server
server = MjpegServer()

# # Create a stream
# stream = ManagedStream('test')

# # Add the stream to the server
# server.add_stream(stream)

# # Start the server
# server.start()

# while True:
#     pass

# Create a stream
stream = Stream("test")

# Add the stream to the server
server.add_stream(stream)

# Start the server
server.start()
cap = cv2.VideoCapture(0)

while True:
    _, frame = cap.read()
    stream.set_frame(frame)
    cv2.imshow("frame", frame)


server.stop()
cap.release()

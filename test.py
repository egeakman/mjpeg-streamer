# import time

# import cv2

# from mjpeg_streamer.mjpeg_streamer import (
#     CustomStream,
#     ManagedStream,
#     MjpegServer,
#     Stream,
# )

# # Create a server
# server = MjpegServer("0.0.0.0")

# # # Create a stream
# # stream = ManagedStream('test', mode="od")

# # # Add the stream to the server
# # server.add_stream(stream)

# # # Start the server
# # server.start()

# # while True:
# #     print(stream.get_bandwidth(), end="\r")

# # Create a stream
# stream = ManagedStream(
#     "test",
#     fps=30,
#     quality=50,
#     size=(640, 480),
#     source=0,
#     mode="full-on-demand",
#     poll_delay_ms=100,
# )
# # stream = CustomStream('test')

# # Add the stream to the server
# server.add_stream(stream)

# # Start the server
# server.start()
# # cap = cv2.VideoCapture(0)

# while True:
#     print(round(stream.get_bandwidth() / 1024 / 1024, 2), end="\r")
#     # _, frame = cap.read()
#     # frame = cv2.resize(frame, (640, 480))
#     # frame = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])[1]
#     # stream.set_frame(frame)
#     # # print(stream.get_bandwidth())
#     # print(round(stream.get_bandwidth() / 1024 / 1024, 2), end="\r")
#     # # print(stream.settings())


# server.stop()
# # cap.release()


from mjpeg_streamer import MjpegServer

server = MjpegServer(["192.168.1.4", "127.0.0.1", "192.168.1.4"], 8080)

server.start()

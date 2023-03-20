# mjpeg-streamer

## Overview

The mjpeg-streamer package provides a simple, flexible and efficient way to stream MJPEG video from OpenCV-compatible sources over HTTP. It provides a flexible interface that allows users to specify the video source and configure various parameters such as image size, quality, and FPS.

## Installation

You can install the package via pip:

```bash
pip install mjpeg-streamer
```

## Usage

Here's a simple example that shows how to use the MJPEG Server package to stream video from a webcam:

```python
import cv2
from mjpeg_streamer import MjpegServer, Stream

cap = cv2.VideoCapture(0)

stream = Stream("my_camera", size=(640, 480), quality=50, fps=30)

server = MjpegServer("localhost", 8080)
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
```

This example starts the MJPEG server on localhost:8080 and streams video from the webcam with the index of ``0``. The video is resized to 640x480 pixels, compressed with JPEG quality of 50, and streamed at 30 FPS.

To view the video stream, you can open a web browser and navigate to http://localhost:8080/my_camera.

Don't forget to check out the [tests](tests) directory for more examples.

## Class Reference

### *Stream*
A class that represents a single video stream. A stream consists of a sequence of frames that can be set and retrieved using the set_frame and _get_frame methods.

***Constructor:***

```python
Stream(name: str, size: Optional[Tuple[int, int]] = None, quality: int = 50, fps: int = 24)
```

Creates a new Stream instance with the given unique name, image size, JPEG quality (1-100), and FPS.

***Methods:***

- *set_frame*

    ```python
    set_frame(frame: np.ndarray)
    ```

    Sets the current frame to the given Numpy array (OpenCV frame).

<br>

- *_get_frame* (private)

    ```python
    _get_frame()
    ```
    Returns the current frame as a Numpy array.

### *MjpegServer*

A class that represents an MJPEG server. The server can serve multiple video streams, each identified by a unique name.

***Constructor:***

```python
MjpegServer(host: str = "localhost", port: int = 8080)
```

Creates a new MjpegServer instance with the given host and port.

***Methods:***

- *add_stream*

    ```python
    add_stream(stream: Stream)
    ```

    Adds a new video stream to the server.

<br>

- *start*

    ```python
    start()
    ```

    Starts the server in a separate thread.

<br>

- *stop*

    ```python
    stop()
    ```

    Stops the server.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.
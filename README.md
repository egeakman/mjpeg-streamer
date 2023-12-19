# on demand mjpeg-streamer

This is a fork of the [original mjpeg-streamer](https://github.com/egeakman/mjpeg-streamer) implementing On Demand feature. This version works similarly as the original with the main advantage that the stream from the video input is on only if there is a connected client. 
The reason for this change relies in the need to use webcam web streams in project with limited cpu performance or battery life that don't need to be wasted letting the camera record if no client is connected.

## Overview

The mjpeg-streamer package provides a simple, flexible and efficient way to stream MJPEG video from OpenCV-compatible sources over HTTP. It provides a flexible interface that allows users to specify the video source and configure various parameters such as image size, quality, and FPS.

## Usage

Here's a simple example that shows how to use the MJPEG Server package to stream video from a webcam:

```python
import od-mjpeg_streamer

capture_device = 0

stream = Stream("my_camera", capture_device, size=(640, 480), quality=50, fps=30)

server = MjpegServer("localhost", 8080)
server.add_stream(stream)
server.start()

while True:
    pass

server.stop()
```

This example starts the MJPEG server on localhost:8080 and streams video from the webcam with the index of ``0``. The video is resized to 640x480 pixels, compressed with JPEG quality of 50, and streamed at 30 FPS.

To view the video stream, you can open a web browser and navigate to http://localhost:8080/my_camera.

Don't forget to check out the [tests](tests) directory for more examples.

## Class Reference

### *Stream*
A class that represents a single video stream. A stream consists of a sequence of frames that can be set and retrieved using the set_frame and _get_frame methods.

***Constructor:***

```python
Stream(name: str, cap: int | str, size: Optional[Tuple[int, int]] = None, quality: int = 50, fps: int = 24)
```

Creates a new Stream instance with the given unique name, capture device, image size, JPEG quality (1-100), and FPS.

***Methods:***

- *set_frame*

    ```python
    set_frame(frame: np.ndarray)
    ```

    Sets the current frame to the given Numpy array (OpenCV frame).

<br>

- *get_bandwidth*

    ```python
    get_bandwidth()
    ```

    Returns the bandwidth of the stream in bytes per second.

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
# mjpeg-streamer


## Overview

The mjpeg-streamer package provides a simple, flexible and efficient way to stream MJPEG video from OpenCV-compatible sources over HTTP. It provides a flexible interface that allows users to specify the video source and configure various parameters such as image size, quality, and FPS.


## Installation

You can install the package via pip:

```bash
pip install mjpeg-streamer
```

I would really recommend using `--prefer-binary`, especially with older versions of Python (e.g. 3.6). This will install pre-compiled binaries instead of building from source, which is much faster and less error-prone.

```bash
pip install mjpeg-streamer --prefer-binary
```

*Latest versions of dependencies (e.g. Numpy) don't always ship with pre-compiled binaries for older versions of Python, so this option installs the latest compatible version instead, even though it might be a bit older.*


## Usage

### Library

Here's a simple example that shows how to use the *mjpeg_streamer* package to stream video from a webcam:

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

To view the streams index, you can open a web browser and navigate to http://localhost:8080.

Don't forget to check out the [examples](examples) directory for more examples.

Check out the [class reference](#class-reference) for more details on the classes and methods provided by the package.

### Command Line Interface

The package also provides a simple command line interface that allows you to stream video from multiple sources using a single command. Here's an example that shows how to stream video from a webcam and a video file:

```bash
$ mjpeg-streamer -s 0 -s "video file.mp4" --prefix "ender 3 pro" --quality 75 --fps 24 --show-bandwidth

Streams index: http://localhost:8080
Available streams:

http://localhost:8080/ender_3_pro_0
http://localhost:8080/ender_3_pro_video_file_mp4
--------------------------------


Press Ctrl+C to stop the server

ender_3_pro_video_file_mp4: 599.28 KB/s | ender_3_pro_0: 824.44 KB/s
```

This command starts the MJPEG server on localhost:8080 and streams video from the webcam with the index of ``0`` and the video file "video file.mp4". The streams are prefixed with "ender 3 pro" and compressed with JPEG quality of 75 and streamed at 24 FPS. The bandwidth of each stream is displayed in the console.

To view the video streams, you can open a web browser and navigate to the URLs displayed in the console.

Run ``mjpeg-streamer --help`` for more information on the available options.

***Note that*** the command line interface is limited and doesn't provide the same level of flexibility as the library. It's recommended to use the library if you need to customize the video streams or integrate them into your own application.


## Class Reference

### *Stream*
A class that represents a single video stream. A stream consists of a sequence of frames that can be set and retrieved using the set_frame and get_frame methods.

***Constructor:***

```python
Stream(name: str, size: Optional[Tuple[int, int]] = None, quality: int = 50, fps: int = 30)
```

Creates a new Stream instance with the given unique name, image size, JPEG quality (1-100), and FPS.

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
    *Tip: Divide the result by 1024 to get the bandwidth in kilobytes per second.*

<br>

- *get_frame*

    ```python
    get_frame()
    ```
    Returns the current frame as a Numpy array.

<br>

- *get_frame_processed*

    ```python
    get_frame_processed()
    ```

    Returns the current frame as a Numpy array after processing it with the specified image size and JPEG quality.

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

***TL;DR: You can use, modify, and distribute this software for free or for profit, but you must make the source code available to your users and include a copy of this license in your project. This license should also mention the original author and a link to this repository.***

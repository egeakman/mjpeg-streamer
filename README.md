# mjpeg-streamer


## Overview

The mjpeg-streamer package provides a simple, flexible and efficient way to stream MJPEG video and audio from OpenCV-compatible sources over HTTP. It supports multiple video streams, audio streaming via PyAudio, and includes a built-in browser player for synced audio+video playback.


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

### Audio Support

To enable audio streaming, install with the `audio` extra:

```bash
pip install mjpeg-streamer[audio]
```

This installs [PyAudio](https://pypi.org/project/PyAudio/), which is required for capturing and streaming audio from input devices.


## Usage

### Library

#### Video Only

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

This example starts the MJPEG server on ``localhost:8080`` and streams video from the webcam with the index of ``0``. The video is resized to 640x480 pixels, compressed with JPEG quality of 50, and streamed at 30 FPS.

To view the video stream, you can open a web browser and navigate to http://localhost:8080/my_camera.

To view the streams index, you can open a web browser and navigate to http://localhost:8080.

Don't forget to check out the [examples](examples) directory for more examples.

Check out the [class reference](#class-reference) for more details on the classes and methods provided by the package.

#### Video + Audio

```python
import cv2
from mjpeg_streamer import AudioStream, MjpegServer, Stream

cap = cv2.VideoCapture(0)

video = Stream("camera", size=(640, 480), quality=50, fps=30)
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
```

This streams both webcam video and microphone audio. Open http://localhost:8080/player in your browser to view the synced player with volume controls.

#### ManagedStream (Auto-Capture)

`ManagedStream` wraps a `cv2.VideoCapture` and reads frames automatically, supporting on-demand capture modes:

```python
import cv2
from mjpeg_streamer import ManagedStream, MjpegServer

# fast-on-demand: always captures (default)
# full-on-demand: only captures when viewers are connected
stream = ManagedStream("camera", source=0, fps=30, size=(640, 480), mode="full-on-demand")

server = MjpegServer("localhost", 8080)
server.add_stream(stream)
stream.start()
server.start()
```

### Command Line Interface

The package also provides a simple command line interface that allows you to stream video from multiple sources using a single command.

#### Video Only

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

#### Video + Audio

```bash
$ mjpeg-streamer -s 0 --audio --show-bandwidth
```

This streams webcam video with microphone audio. The player URL will be printed in the console.

#### List Audio Devices

To see available audio input devices and their indices:

```bash
$ mjpeg-streamer --list-devices

Audio input devices:

  [0] Microsoft Sound Mapper - Input
       Channels: 2, Rate: 44100 Hz
  [1] Microphone (C-Media(R) Audio)
       Channels: 2, Rate: 44100 Hz
```

Then use the device index with `--audio-device`:

```bash
$ mjpeg-streamer -s 0 --audio --audio-device 1
```

Run ``mjpeg-streamer --help`` for all available options.

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

### *ManagedStream*
A class that manages its own video capture, automatically reading frames from a source (webcam index, video file path, etc.).

***Constructor:***

```python
ManagedStream(
    name: str,
    source: Union[int, str] = 0,
    fps: int = 30,
    size: Optional[Tuple[int, int]] = None,
    quality: int = 50,
    mode: str = "fast-on-demand",
    poll_delay_ms: Optional[Union[float, int]] = None,
)
```

Creates a new ManagedStream instance. `mode` can be `"fast-on-demand"` (always capturing) or `"full-on-demand"` (only captures when viewers are connected).

***Methods:***

- *start* / *stop* - Start or stop the capture loop.
- *set_size* / *set_quality* - Adjust output dimensions or JPEG quality.
- *change_mode* - Switch between on-demand modes at runtime.
- *change_source* - Switch the video capture source.

### *AudioStream*
A class that captures and streams audio from an input device as WAV over HTTP. Requires the `pyaudio` extra.

***Constructor:***

```python
AudioStream(
    name: str,
    source: Optional[int] = None,
    sample_rate: int = 44100,
    channels: int = 1,
    sample_width: int = 2,
    chunk_size: int = 1024,
)
```

Creates a new AudioStream instance. If `source` is `None`, the system default input device is used.

***Methods:***

- *start* / *stop* - Start or stop audio capture.
- *get_bandwidth* - Returns the bandwidth of the stream in bytes per second.
- *active_viewers* - Returns the number of active viewers.

### *MjpegServer*

A class that represents an MJPEG server. The server can serve multiple video and audio streams, each identified by a unique name.

***Constructor:***

```python
MjpegServer(host: str = "localhost", port: int = 8080)
```

Creates a new MjpegServer instance with the given host and port.

***Methods:***

- *add_stream*

    ```python
    add_stream(stream: Union[Stream, ManagedStream, AudioStream])
    ```

    Adds a new video or audio stream to the server.

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

***TL;DR: You can use, modify, and distribute this software for free or for profit, but you must make the source code available to your users and include a copy of [this license](LICENSE) in your project. Your modified work's license should also mention the original author and a link to this repository.***

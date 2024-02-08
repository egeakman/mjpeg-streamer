import argparse
import re
import threading
from typing import List, Tuple, Union

import cv2

from mjpeg_streamer import MjpegServer, Stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--prefix", type=str, default="source", help="Name prefix for the streams"
    )
    parser.add_argument(
        "--source",
        "-s",
        action="append",
        nargs="+",
        required=False,
        help="Source(s) to stream (repeatable)",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--quality", "-q", type=int, default=50)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--show-bandwidth",
        action="store_true",
        help="Shows the bandwidth used by each stream in kilobytes per second",
    )
    args: argparse.Namespace = parser.parse_args()
    args.prefix = re.sub("[^0-9a-zA-Z]+", "_", args.prefix)
    args.source: List[Union[int, str],] = [[0]] if args.source is None else args.source
    args.source = [item for sublist in args.source for item in sublist]
    args.source = list(set(args.source))
    return args


def run(
    cap: cv2.VideoCapture,
    stream: Stream,
    stop_event: threading.Event,
    show_bandwidth: bool,
) -> None:
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            stop_event.set()
            break
        stream.set_frame(frame)
        if show_bandwidth:
            global bandwidth
            bandwidth[stream.name] = stream.get_bandwidth()
    cap.release()


def main() -> None:
    args = parse_args()
    size: Tuple[int, int] = (args.width, args.height)
    server = MjpegServer(args.host, args.port)
    threads: List[threading.Thread,] = []
    stop_events: List[threading.Event,] = []

    if args.show_bandwidth:
        global bandwidth
        bandwidth = {}  # dict[str, int]

    for source in args.source:
        source: Union[int, str] = int(source) if str(source).isdigit() else source
        cap = cv2.VideoCapture(source)
        source_display = (
            re.sub("[^0-9a-zA-Z]+", "_", source) if isinstance(source, str) else source
        )
        stream = Stream(
            f"{args.prefix}_{source_display!s}",
            size=size,
            quality=args.quality,
            fps=args.fps,
        )
        server.add_stream(stream)
        stop_event = threading.Event()
        stop_events.append(stop_event)
        thread = threading.Thread(
            target=run, args=(cap, stream, stop_event, args.show_bandwidth)
        )
        threads.append(thread)

    try:
        for thread in threads:
            thread.start()
        server.start()
        while True:
            if args.show_bandwidth:
                print(
                    f"{' | '.join([f'{k}: {round(v / 1024, 2)} KB/s' for k, v in bandwidth.items()])}",
                    end="\r",
                )
    except KeyboardInterrupt:
        for stop_event in stop_events:
            stop_event.set()
        server.stop()
        for thread in threads:
            thread.join()
    except Exception as e:
        print(e)
        for stop_event in stop_events:
            stop_event.set()
        server.stop()
        for thread in threads:
            thread.join()


if __name__ == "__main__":
    main()

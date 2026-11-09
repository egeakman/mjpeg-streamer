import argparse
import re
import time
from typing import Dict, List, Tuple, Union

from .server import Server
from .stream import ManagedStream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--prefix", type=str, default="", help="Name prefix for the streams"
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
    args.source = [[0]] if args.source is None else args.source
    args.source = [item for sublist in args.source for item in sublist]
    args.source = list(set(args.source))
    return args


def main() -> None:
    args = parse_args()
    size: Tuple[int, int] = (args.width, args.height)
    streams: List[ManagedStream] = []
    server = Server(args.host, args.port)

    if args.show_bandwidth:
        bandwidth: Dict[str, int] = {}

    for source in args.source:
        source: Union[int, str] = int(source) if str(source).isdigit() else source
        source_display = (
            re.sub("[^0-9a-zA-Z]+", "_", source) if isinstance(source, str) else source
        )
        stream = ManagedStream(
            f"{args.prefix}{'_' if args.prefix else ''}{source_display!s}",
            source=source,
            size=size,
            quality=args.quality,
            fps=args.fps,
        )
        server.add_stream(stream)
        streams.append(stream)

    try:
        for stream in streams:
            stream.start()
        server.start()
        while True:
            if args.show_bandwidth:
                for stream in streams:
                    bandwidth[stream.name] = stream.get_bandwidth()
                print(
                    f"{' | '.join([f'{k}: {round(v / 1024, 2)} KB/s' for k, v in bandwidth.items()])}",
                    end="\r",
                )
            else:
                time.sleep(1)  # Keep the main thread alive, but don't consume CPU
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print("Error:", e)
    finally:
        for stream in streams:
            stream.stop()
        server.stop()


if __name__ == "__main__":
    main()

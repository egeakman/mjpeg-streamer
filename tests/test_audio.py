"""Unit tests for AudioStream."""

import asyncio
import struct
from unittest.mock import MagicMock, patch

import pytest

from mjpeg_streamer.stream import AudioStream


@pytest.fixture
def audio_stream():
    with patch("mjpeg_streamer.stream.pyaudio"):
        return AudioStream(
            name="test_audio",
            source=0,
            sample_rate=44100,
            channels=1,
            sample_width=2,
            chunk_size=1024,
        )


class TestWavHeader:
    def test_header_length(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        assert len(header) == 44

    def test_riff_chunk(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        assert header[0:4] == b"RIFF"
        # Size field = 0xFFFFFFFF for streaming
        riff_size = struct.unpack_from("<I", header, 4)[0]
        assert riff_size == 0xFFFFFFFF

    def test_waveFormat(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        assert header[8:12] == b"WAVE"
        assert header[12:16] == b"fmt "

    def test_pcm_format(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        # fmt chunk: audio format at offset 20 (after RIFF(8) + "WAVE"(4) + "fmt "(4) + chunk size(4))
        audio_format = struct.unpack_from("<H", header, 20)[0]
        assert audio_format == 1  # PCM

    def test_channels(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        channels = struct.unpack_from("<H", header, 22)[0]
        assert channels == 1

    def test_sample_rate(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        sample_rate = struct.unpack_from("<I", header, 24)[0]
        assert sample_rate == 44100

    def test_byte_rate(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        byte_rate = struct.unpack_from("<I", header, 28)[0]
        # 44100 * 1 * 2 = 88200
        assert byte_rate == 88200

    def test_block_align(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        block_align = struct.unpack_from("<H", header, 32)[0]
        # 1 * 2 = 2
        assert block_align == 2

    def test_bits_per_sample(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        bits = struct.unpack_from("<H", header, 34)[0]
        assert bits == 16

    def test_data_chunk(self, audio_stream):
        header = audio_stream._make_wav_header_bytes()
        assert header[36:40] == b"data"
        data_size = struct.unpack_from("<I", header, 40)[0]
        assert data_size == 0xFFFFFFFF  # streaming

    def test_header_with_known_data_size(self, audio_stream):
        header = audio_stream._make_wav_header(88200)
        riff_size = struct.unpack_from("<I", header, 4)[0]
        assert riff_size == 36 + 88200
        data_size = struct.unpack_from("<I", header, 40)[0]
        assert data_size == 88200

    def test_stereo_header(self):
        with patch("mjpeg_streamer.stream.pyaudio"):
            stream = AudioStream("stereo", channels=2, sample_width=2, sample_rate=44100)
        header = stream._make_wav_header_bytes()
        channels = struct.unpack_from("<H", header, 22)[0]
        byte_rate = struct.unpack_from("<I", header, 28)[0]
        block_align = struct.unpack_from("<H", header, 32)[0]
        assert channels == 2
        assert byte_rate == 44100 * 2 * 2  # 176400
        assert block_align == 2 * 2  # 4


class TestViewerLifecycle:
    def test_add_viewer(self, audio_stream):
        token = asyncio.get_event_loop().run_until_complete(
            audio_stream._add_viewer()
        )
        assert isinstance(token, str)
        assert len(token) > 0
        assert audio_stream.active_viewers() == 1

    def test_add_multiple_viewers(self, audio_stream):
        asyncio.get_event_loop().run_until_complete(audio_stream._add_viewer())
        asyncio.get_event_loop().run_until_complete(audio_stream._add_viewer("custom"))
        assert audio_stream.active_viewers() == 2

    def test_remove_viewer(self, audio_stream):
        token = asyncio.get_event_loop().run_until_complete(
            audio_stream._add_viewer()
        )
        asyncio.get_event_loop().run_until_complete(audio_stream._remove_viewer(token))
        assert audio_stream.active_viewers() == 0

    def test_remove_nonexistent_viewer(self, audio_stream):
        asyncio.get_event_loop().run_until_complete(
            audio_stream._remove_viewer("nonexistent")
        )
        assert audio_stream.active_viewers() == 0

    def test_has_demand(self, audio_stream):
        assert not audio_stream.has_demand()
        asyncio.get_event_loop().run_until_complete(audio_stream._add_viewer())
        assert audio_stream.has_demand()


class TestBandwidth:
    def test_initial_bandwidth(self, audio_stream):
        assert audio_stream.get_bandwidth() == 0

    def test_bandwidth_after_chunks(self, audio_stream):
        audio_stream._bandwidth_buffer.append(1024)
        audio_stream._bandwidth_buffer.append(2048)
        assert audio_stream.get_bandwidth() == 3072


class TestStartStop:
    def test_start_sets_running(self, audio_stream):
        audio_stream.start()
        assert audio_stream._is_running
        audio_stream.stop()

    def test_stop_clears_running(self, audio_stream):
        audio_stream.start()
        audio_stream.stop()
        assert not audio_stream._is_running

    def test_double_start(self, audio_stream, capsys):
        audio_stream.start()
        audio_stream.start()  # should print warning
        captured = capsys.readouterr()
        assert "already started" in captured.out
        audio_stream.stop()

    def test_double_stop(self, audio_stream, capsys):
        audio_stream.start()
        audio_stream.stop()
        audio_stream.stop()  # should print warning
        captured = capsys.readouterr()
        assert "already stopped" in captured.out

    def test_first_chunk_event_clears_on_start(self, audio_stream):
        audio_stream._first_chunk_ready.set()
        audio_stream.start()
        assert not audio_stream._first_chunk_ready.is_set()
        audio_stream.stop()


class TestSettings:
    def test_settings_prints_public_attrs(self, audio_stream, capsys):
        audio_stream.settings()
        captured = capsys.readouterr()
        assert "name" in captured.out
        assert "sample_rate" in captured.out
        assert "channels" in captured.out

    def test_settings_skips_private_attrs(self, audio_stream, capsys):
        audio_stream.settings()
        captured = capsys.readouterr()
        assert "_lock" not in captured.out
        assert "_pa" not in captured.out


class TestNameNormalization:
    def test_name_lowercased(self):
        with patch("mjpeg_streamer.stream.pyaudio"):
            stream = AudioStream("MyAudio")
        assert stream.name == "myaudio"

    def test_spaces_replaced(self):
        with patch("mjpeg_streamer.stream.pyaudio"):
            stream = AudioStream("My Audio Stream")
        assert stream.name == "my_audio_stream"

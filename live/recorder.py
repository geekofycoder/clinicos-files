"""
recorder.py — chunked audio capture for live pipeline.

Captures mic audio continuously. Every CHUNK_SECONDS seconds, flushes
the buffer to a temp WAV and calls on_chunk(wav_path) in a new thread
so transcription + LLM can run without blocking the capture loop.
"""

import queue
import tempfile
import threading
from typing import Callable

import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16_000
CHANNELS = 1
SUBTYPE = "PCM_16"
CHUNK_SECONDS = 15


class ChunkedRecorder:
    def __init__(self, on_chunk: Callable[[str], None]):
        self._on_chunk = on_chunk
        self._audio_q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=CHUNK_SECONDS + 5)

    def _run(self) -> None:
        def callback(indata, frames, time_info, status):
            self._audio_q.put(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
            while not self._stop.is_set():
                self._flush_chunk()

    def _flush_chunk(self) -> None:
        frames_needed = SAMPLE_RATE * CHUNK_SECONDS
        blocks, collected = [], 0

        while collected < frames_needed and not self._stop.is_set():
            try:
                block = self._audio_q.get(timeout=0.5)
                blocks.append(block)
                collected += len(block)
            except queue.Empty:
                continue

        if not blocks:
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with sf.SoundFile(tmp.name, mode="w", samplerate=SAMPLE_RATE,
                          channels=CHANNELS, subtype=SUBTYPE) as wav:
            for block in blocks:
                wav.write(block)

        threading.Thread(target=self._on_chunk, args=(tmp.name,), daemon=True).start()

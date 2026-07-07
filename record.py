"""
record.py — capture a role-played consult from the laptop mic into one WAV.

Why one shared WAV (and not live streaming per engine):
the bake-off compares ASR *models*, so every engine must transcribe the
byte-for-byte identical audio. One recording = one controlled input you can
replay into Sarvam, ElevenLabs and Google in turn, and re-run after tweaking
prompts. 16 kHz mono PCM is the sweet spot all three engines accept directly.

Usage:
    python record.py --name consult_01            # press Enter to stop
    python record.py --name consult_01 --seconds 90   # fixed length
"""

import argparse
import queue
import sys
import threading
from pathlib import Path

import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16_000   # 16 kHz: required by Sarvam PCM, ideal for Google LINEAR16
CHANNELS = 1           # mono — laptop mic, no need for stereo
SUBTYPE = "PCM_16"     # 16-bit linear PCM inside the WAV container


def record(output_path: Path, seconds: float | None = None) -> None:
    """Record from the default input device until Enter (or `seconds` elapses)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio_q: "queue.Queue" = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        audio_q.put(indata.copy())

    stop = threading.Event()
    if seconds is None:
        print("Recording... press Enter to stop.")
        threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()
    else:
        print(f"Recording for {seconds:.0f}s...")
        threading.Timer(seconds, stop.set).start()

    with sf.SoundFile(
        output_path, mode="w",
        samplerate=SAMPLE_RATE, channels=CHANNELS, subtype=SUBTYPE,
    ) as wav:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
            while not stop.is_set():
                wav.write(audio_q.get())
            # drain anything still buffered after stop
            while not audio_q.empty():
                wav.write(audio_q.get_nowait())
                
    info = sf.info(output_path)
    print(f"Saved {output_path}  ({info.duration:.1f}s, {info.samplerate} Hz, {info.channels}ch)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Record a consult to WAV.")
    ap.add_argument("--name", required=True, help="base filename, e.g. consult_01")
    ap.add_argument("--seconds", type=float, default=None,
                    help="fixed duration; omit to stop on Enter")
    ap.add_argument("--out-dir", default="recordings", help="output directory")
    args = ap.parse_args()
    out = Path(args.out_dir) / f"{args.name}.wav"
    record(out, args.seconds)


if __name__ == "__main__":
    main()

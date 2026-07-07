"""
transcribe_all.py — the fan-out. Takes ONE wav and runs every engine that has
credentials configured, then writes the transcripts side by side.

    python transcribe_all.py recordings/consult_01.wav

Each engine gets the SAME audio and the SAME keyterm list, so any difference in
output is the model, not the input. A failure in one engine is caught and
reported, not allowed to kill the run — you still get the others' transcripts.

Output per engine (in transcripts/):
  <consult>__<engine>.txt          — full plain transcript
  <consult>__<engine>__diarized.txt — speaker-labelled turns (if available)
"""

import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

from stt import SarvamEngine, ElevenLabsEngine, GoogleEngine

load_dotenv()

# Common drug names + dosage units to bias engines that support keyterms.
# Edit this to match the drugs your role-played consults actually mention.
DRUG_KEYTERMS = [
    "Metformin", "Glimepiride", "Semaglutide", "Ozempic", "Rybelsus",
    "Telmisartan", "Amlodipine", "Atorvastatin", "Rosuvastatin",
    "Pantoprazole", "Amoxicillin", "Azithromycin", "Insulin",
    "mg", "ml", "OD", "BD", "TDS", "HbA1c",
]


def build_engines():
    """Instantiate only the engines whose credentials are present."""
    engines = []
    if os.getenv("SARVAM_API_KEY"):
        engines.append(SarvamEngine())
    if os.getenv("ELEVENLABS_API_KEY"):
        engines.append(ElevenLabsEngine())
    if os.getenv("GOOGLE_CLOUD_PROJECT") and GoogleEngine is not None:
        engines.append(GoogleEngine())
    if not engines:
        sys.exit("No engine credentials found. Copy .env.example to .env and fill it in.")
    return engines


def format_diarized(speaker_turns: list) -> str:
    """Format speaker turns into a readable labelled transcript."""
    if not speaker_turns:
        return "(no diarization data)"
    lines = []
    for speaker, text in speaker_turns:
        lines.append(f"[{speaker}]: {text}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python transcribe_all.py <path/to/consult.wav>")
    wav_path = Path(sys.argv[1])
    if not wav_path.exists():
        sys.exit(f"File not found: {wav_path}")

    out_dir = Path("transcripts")
    out_dir.mkdir(exist_ok=True)
    consult = wav_path.stem

    for engine in build_engines():
        print(f"\n{'='*50}")
        print(f"  {engine.name.upper()}")
        print(f"{'='*50}")
        t_start = time.perf_counter()
        try:
            result = engine.transcribe(
                str(wav_path), keyterms=DRUG_KEYTERMS, language="auto"
            )
        except Exception:
            elapsed = time.perf_counter() - t_start
            print(f"[{engine.name}] FAILED after {elapsed:.1f}s:")
            traceback.print_exc()
            continue
        elapsed = time.perf_counter() - t_start

        # --- plain transcript ---
        plain_file = out_dir / f"{consult}__{engine.name}.txt"
        plain_file.write_text(result.text, encoding="utf-8")

        # --- diarized transcript ---
        diarized_file = out_dir / f"{consult}__{engine.name}__diarized.txt"
        diarized_text = format_diarized(result.speaker_turns)
        diarized_file.write_text(diarized_text, encoding="utf-8")

        # --- console preview ---
        print(f"Language detected : {result.language}")
        print(f"Transcription time: {elapsed:.2f}s")
        print(f"\n--- Transcript (first 500 chars) ---")
        print(result.text[:500] + ("..." if len(result.text) > 500 else ""))
        if result.speaker_turns:
            print(f"\n--- Diarized ({len(result.speaker_turns)} turns) ---")
            for spk, txt in result.speaker_turns[:6]:
                preview = txt[:120] + ("..." if len(txt) > 120 else "")
                print(f"  [{spk}]: {preview}")
            if len(result.speaker_turns) > 6:
                print(f"  ... ({len(result.speaker_turns) - 6} more turns)")
        print(f"\n-> {plain_file}")
        print(f"-> {diarized_file}")


if __name__ == "__main__":
    main()

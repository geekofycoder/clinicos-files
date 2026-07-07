"""
pipeline.py — end-to-end ClinicOS Scribe pipeline.

    python pipeline.py --name consult_01
    python pipeline.py --name consult_01 --seconds 90   # fixed-length recording

Steps:
  1. Record mic audio → recordings/<name>.wav
  2. Transcribe with Sarvam and ElevenLabs (engines with credentials)
  3. Extract structured prescription JSON via LLM for each transcript
  4. Save results/sarvam_result.json and results/elevenlabs_result.json
"""

import argparse
import json
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

from record import record
from stt import SarvamEngine, ElevenLabsEngine
from llm import extract

load_dotenv()

DRUG_KEYTERMS = [
    "Metformin", "Glimepiride", "Semaglutide", "Ozempic", "Rybelsus",
    "Telmisartan", "Amlodipine", "Atorvastatin", "Rosuvastatin",
    "Pantoprazole", "Amoxicillin", "Azithromycin", "Insulin",
    "mg", "ml", "OD", "BD", "TDS", "HbA1c",
]


def build_engines():
    import os
    engines = []
    if os.getenv("SARVAM_API_KEY"):
        engines.append(SarvamEngine())
    if os.getenv("ELEVENLABS_API_KEY"):
        engines.append(ElevenLabsEngine())
    if not engines:
        raise RuntimeError("No STT engine credentials found. Fill .env with SARVAM_API_KEY / ELEVENLABS_API_KEY.")
    return engines


def run(name: str, seconds: float | None, wav: str | None = None) -> None:
    wav_path = Path(wav) if wav else Path("recordings") / f"{name}.wav"

    if wav:
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV not found: {wav_path}")
        print(f"\n=== SKIPPING RECORDING — using {wav_path} ===")
    else:
        # --- Step 1: Record ---
        print("\n=== RECORDING ===")
        record(wav_path, seconds)

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    engines = build_engines()

    for engine in engines:
        print(f"\n{'='*55}")
        print(f"  ENGINE: {engine.name.upper()}")
        print(f"{'='*55}")

        # --- Step 2: Transcribe ---
        t0 = time.perf_counter()
        try:
            result = engine.transcribe(str(wav_path), keyterms=DRUG_KEYTERMS, language="auto")
        except Exception:
            elapsed = time.perf_counter() - t0
            print(f"[{engine.name}] Transcription FAILED after {elapsed:.1f}s:")
            traceback.print_exc()
            continue
        stt_elapsed = time.perf_counter() - t0
        print(f"Transcription time : {stt_elapsed:.2f}s")
        print(f"Language detected  : {result.language}")
        print(f"Transcript preview : {result.text[:200]}{'...' if len(result.text) > 200 else ''}")

        # --- Save plain + diarized transcripts ---
        txt_dir = Path("transcripts") / name
        txt_dir.mkdir(parents=True, exist_ok=True)
        (txt_dir / f"{engine.name}.txt").write_text(result.text, encoding="utf-8")
        diarized = "\n".join(f"[{spk}]: {txt}" for spk, txt in result.speaker_turns) or "(no diarization data)"
        (txt_dir / f"{engine.name}__diarized.txt").write_text(diarized, encoding="utf-8")
        print(f"Transcripts saved  : transcripts/{name}/{engine.name}.txt")

        # --- Step 3: LLM extraction ---
        print(f"\nExtracting prescription via LLM...")
        t1 = time.perf_counter()
        try:
            prescription = extract(result.text)
        except Exception:
            elapsed = time.perf_counter() - t1
            print(f"[{engine.name}] LLM extraction FAILED after {elapsed:.1f}s:")
            traceback.print_exc()
            continue
        llm_elapsed = time.perf_counter() - t1
        print(f"LLM extraction time: {llm_elapsed:.2f}s")

        # --- Step 4: Save result ---
        out_file = results_dir / f"{engine.name}_result.json"
        payload = {
            "engine": engine.name,
            "stt_seconds": round(stt_elapsed, 2),
            "llm_seconds": round(llm_elapsed, 2),
            "transcript": result.text,
            "prescription": prescription.model_dump(),
        }
        out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved → {out_file}")


def main():
    ap = argparse.ArgumentParser(description="ClinicOS Scribe end-to-end pipeline.")
    ap.add_argument("--name", required=True, help="consult name, e.g. consult_01")
    ap.add_argument("--seconds", type=float, default=None,
                    help="fixed recording duration; omit to stop on Enter")
    ap.add_argument("--wav", default=None,
                    help="path to existing WAV — skips recording, goes straight to transcription + LLM")
    args = ap.parse_args()
    run(args.name, args.seconds, args.wav)


if __name__ == "__main__":
    main()

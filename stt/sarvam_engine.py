"""
sarvam_engine.py — Sarvam Saaras v3 via the Batch Speech-to-Text job API.

Why batch (not the sync REST endpoint): Sarvam's sync API caps at 30s per
request, so a multi-minute consult would force you to chunk and stitch (word
drops at the seams). The batch job API handles up to 1 hour natively and gives
speaker diarization, so the audio goes in whole.

Modes (Saaras v3): "transcribe" keeps the original language with light
normalisation; "codemix" renders Hindi-English naturally; "verbatim" keeps
every filler. For the bake-off we want faithful Hinglish, so "transcribe" is a
good default — switch self.mode to "codemix" if you prefer raw code-mix output.

Domain prompting (drug names): Saaras supports a `prompt` for hotword/entity
retention. Batch SDK support varies by version, so we pass it best-effort and
fall back if the installed SDK rejects it.
"""

import glob
import json
import os
import tempfile
from typing import Optional

from sarvamai import SarvamAI

from .base import STTEngine, TranscriptResult


class SarvamEngine(STTEngine):
    name = "sarvam"

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "saaras:v3", mode: str = "codemix"):
        self.client = SarvamAI(
            api_subscription_key=api_key or os.environ["SARVAM_API_KEY"]
        )
        self.model = model
        self.mode = mode

    def transcribe(self, wav_path, keyterms=None, language="hi-IN"):
        kwargs = dict(
            model=self.model,
            mode=self.mode,
            language_code=("unknown" if language == "auto" else language),
            with_diarization=True,
            num_speakers=2,
        )
        if keyterms:
            kwargs["prompt"] = (
                "Medical consultation. Preserve these terms exactly: "
                + ", ".join(keyterms)
            )

        try:
            job = self.client.speech_to_text_job.create_job(**kwargs)
        except TypeError:
            # installed SDK doesn't accept `prompt` on batch jobs — drop it
            kwargs.pop("prompt", None)
            job = self.client.speech_to_text_job.create_job(**kwargs)

        job.upload_files(file_paths=[wav_path])
        job.start()
        job.wait_until_complete()

        with tempfile.TemporaryDirectory() as out_dir:
            job.download_outputs(output_dir=out_dir)
            result_files = sorted(glob.glob(os.path.join(out_dir, "*.json")))
            if not result_files:
                raise RuntimeError("Sarvam job produced no output files")
            with open(result_files[0], encoding="utf-8") as f:
                data = json.load(f)

        text = data.get("transcript", "") or ""
        turns = []
        for seg in data.get("diarized_transcript", {}).get("entries", []) or []:
            turns.append((seg.get("speaker_id", "?"), seg.get("transcript", "")))

        return TranscriptResult(
            engine=self.name,
            text=text.strip(),
            language=data.get("language_code"),
            speaker_turns=turns,
            raw=data,
        )

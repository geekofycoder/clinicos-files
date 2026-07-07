"""
elevenlabs_engine.py — ElevenLabs Scribe v2 (batch) via speech_to_text.convert.

Scribe v2 handles long files natively (no chunking) and auto-detects language
WITH code-switching when you leave language_code unset — which is what we want
for Hinglish. Its keyterm prompting is the cleanest match for the scope's
highest-weighted metric (drug-name accuracy): the spoken drug list goes
straight into `keyterms`.

Output text is in the spoken language (mixed Hindi/English); the LLM step
renders English later.
"""

import os
from typing import Optional

from elevenlabs import ElevenLabs

from .base import STTEngine, TranscriptResult

# ElevenLabs uses ISO-639-3 codes when you DO pin a language.
_ISO3 = {"hi-IN": "hin", "en-IN": "eng", "hi": "hin", "en": "eng"}


class ElevenLabsEngine(STTEngine):
    name = "elevenlabs"

    def __init__(self, api_key: Optional[str] = None, model_id: str = "scribe_v2"):
        self.client = ElevenLabs(api_key=api_key or os.environ["ELEVENLABS_API_KEY"])
        self.model_id = model_id

    def transcribe(self, wav_path, keyterms=None, language="auto"):
        kwargs = dict(
            model_id=self.model_id,
            diarize=True,                  # who-said-what
            timestamps_granularity="word",
        )
        # Leave language unset for auto-detect + code-switch (best for Hinglish).
        if language != "auto":
            kwargs["language_code"] = _ISO3.get(language, language)
        if keyterms:
            kwargs["keyterms"] = keyterms  # up to 100 terms

        with open(wav_path, "rb") as audio:
            result = self.client.speech_to_text.convert(file=audio, **kwargs)

        text = getattr(result, "text", "") or ""
        lang = getattr(result, "language_code", None)

        # Reconstruct speaker turns from word-level speaker_ids if present.
        turns = []
        words = getattr(result, "words", None) or []
        current_spk, buf = None, []
        for w in words:
            spk = getattr(w, "speaker_id", None)
            tok = getattr(w, "text", "")
            if spk != current_spk and buf:
                turns.append((current_spk or "?", "".join(buf).strip()))
                buf = []
            current_spk = spk
            buf.append(tok)
        if buf:
            turns.append((current_spk or "?", "".join(buf).strip()))

        raw = result.model_dump() if hasattr(result, "model_dump") else {}
        return TranscriptResult(self.name, text.strip(), lang, turns, raw)

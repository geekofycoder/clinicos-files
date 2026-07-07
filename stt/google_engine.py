"""
google_engine.py — Google Cloud Speech-to-Text V2, Chirp 2 / Chirp 3.

Two honest caveats this engine surfaces (both worth noting in the memo):

1) Long audio: the synchronous `recognize` call caps around 60s. The fully
   "correct" path for longer files is `batch_recognize` with a GCS URI, which
   needs a Cloud Storage bucket + upload. To keep the demo runnable without
   that setup, files longer than ~55s are auto-split at the quietest point near
   each boundary and stitched. Seams can drop a word — flag it if it happens.
   For production accuracy, switch to batch_recognize.

2) Code-switching: Chirp's multi-language support varies by model + method, so
   we try ["hi-IN","en-IN"] and fall back to ["hi-IN"] on InvalidArgument.
   Chirp handles code-switching "in practice" but doesn't guarantee it — this
   is exactly the engine the scope says to test rather than trust.

Keyterms: Google biasing uses model adaptation (phrase sets), which is more
involved and not reliably supported with Chirp. We accept keyterms but do NOT
wire adaptation by default — so Google goes into the bake-off WITHOUT a
drug-name boost. That asymmetry is real and belongs in the memo.
"""

import io
import os
from typing import Optional

import numpy as np
import soundfile as sf
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import InvalidArgument
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech

from .base import STTEngine, TranscriptResult

MAX_SYNC_SECONDS = 55  # stay under the ~60s sync cap


def _wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _split_on_quiet(audio: np.ndarray, sr: int, max_s: int = MAX_SYNC_SECONDS):
    """Split into <=max_s chunks, cutting at the quietest 0.5s near each boundary."""
    max_len = int(max_s * sr)
    win = int(0.5 * sr)
    chunks, i, n = [], 0, len(audio)
    while i < n:
        end = min(i + max_len, n)
        if end < n:  # search back up to 5s for a low-energy cut point
            search_start = max(i + max_len - int(5 * sr), i + win)
            best, best_e = end, None
            for j in range(search_start, end - win, win):
                seg = audio[j:j + win].astype(np.float32)
                e = float(np.mean(seg * seg))
                if best_e is None or e < best_e:
                    best_e, best = e, j + win // 2
            end = best
        chunks.append(audio[i:end])
        i = end
    return chunks


class GoogleEngine(STTEngine):
    name = "google"

    def __init__(self, project_id: Optional[str] = None,
                 location: str = "us-central1", model: str = "chirp_2",
                 language_codes=("hi-IN", "en-IN")):
        self.project_id = project_id or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.location = location
        self.model = model
        self.language_codes = list(language_codes)
        endpoint = (f"{location}-speech.googleapis.com"
                    if location != "global" else None)
        opts = ClientOptions(api_endpoint=endpoint) if endpoint else None
        self.client = SpeechClient(client_options=opts)

    def _recognize(self, content: bytes, language_codes: list[str]) -> str:
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=language_codes,
            model=self.model,
        )
        request = cloud_speech.RecognizeRequest(
            recognizer=(f"projects/{self.project_id}/locations/"
                        f"{self.location}/recognizers/_"),
            config=config,
            content=content,
        )
        resp = self.client.recognize(request=request)
        return " ".join(
            r.alternatives[0].transcript
            for r in resp.results if r.alternatives
        ).strip()

    def _recognize_with_fallback(self, content: bytes) -> str:
        try:
            return self._recognize(content, self.language_codes)
        except InvalidArgument:
            # model/method may reject multi-language — retry with primary only
            return self._recognize(content, [self.language_codes[0]])

    def transcribe(self, wav_path, keyterms=None, language="auto"):
        audio, sr = sf.read(wav_path, dtype="int16")
        if audio.ndim > 1:               # safety: collapse to mono
            audio = audio[:, 0]

        if len(audio) / sr <= MAX_SYNC_SECONDS:
            text = self._recognize_with_fallback(_wav_bytes(audio, sr))
        else:
            parts = [self._recognize_with_fallback(_wav_bytes(c, sr))
                     for c in _split_on_quiet(audio, sr)]
            text = " ".join(p for p in parts if p)

        return TranscriptResult(
            engine=self.name,
            text=text,
            language=",".join(self.language_codes),
            raw={},
        )

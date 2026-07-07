"""
base.py — the contract every STT engine implements.

Keeping a single interface is what makes the bake-off fair and the fan-out
trivial: transcribe_all.py just loops over a list of STTEngine objects and
calls .transcribe(wav_path) on each, with the same audio and the same
keyterm list. Swapping or adding an engine is one new subclass.

Design choice: every engine returns the transcript in the SPOKEN language
(verbatim-ish Hinglish), NOT pre-translated to English. The English rendering
happens later in the LLM step. This keeps ASR error and translation/extraction
error separable — exactly what the scope's "attribute the error" rule needs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TranscriptResult:
    engine: str                       # "sarvam" | "elevenlabs" | "google"
    text: str                         # full transcript, spoken language
    language: Optional[str] = None    # detected/used language code(s)
    speaker_turns: list = field(default_factory=list)  # [(speaker, text), ...] if diarized
    raw: dict = field(default_factory=dict)             # provider's raw response


class STTEngine(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(
        self,
        wav_path: str,
        keyterms: Optional[list[str]] = None,
        language: str = "auto",
    ) -> TranscriptResult:
        """Transcribe one WAV file.

        Args:
            wav_path: path to a 16 kHz mono PCM WAV.
            keyterms: domain terms to bias toward (drug names, dosage units).
                      Applied where the provider supports it; see each engine.
            language: "auto" to let the engine detect/code-switch, or a code
                      like "hi-IN". For Hinglish, "auto" is usually best.
        """
        raise NotImplementedError

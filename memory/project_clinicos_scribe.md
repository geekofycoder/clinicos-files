---
name: project-clinicos-scribe
description: ClinicOS Scribe STT bake-off — what's been built, what's pending, key design decisions
metadata:
  type: project
---

**Project:** ClinicOS Scribe — ASR bake-off, Phase 1 (STT layer complete).

**Goal:** Record a role-played Hindi-English (Hinglish) doctor-patient consult on a laptop, transcribe with 3 hosted STT engines on identical audio, score them, then feed the best transcript to an LLM that fills a prescription JSON in English.

**What's built:**
- `record.py` — mic capture to 16kHz mono PCM WAV
- `stt/base.py` — STTEngine ABC + TranscriptResult dataclass
- `stt/sarvam_engine.py` — Sarvam saaras:v3 via batch job API
- `stt/elevenlabs_engine.py` — ElevenLabs scribe_v2 via speech_to_text.convert
- `stt/google_engine.py` — Google Chirp 2 with chunking for long audio
- `stt/__init__.py`, `transcribe_all.py` (fan-out runner), `requirements.txt`, `.env.example`, `README.md`

**Architecture flow:** `record.py` → `recordings/<name>.wav` → `transcribe_all.py` → `transcripts/<name>__<engine>.txt`

**What's NOT built yet:**
1. LLM prescription extraction (blocker: ClinicOS prescription schema not yet provided)
2. Scoring sheet + metric definitions (WER, code-switch survival, drug/dose accuracy)
3. Decision memo (commit to one API with numbers)

**STT engines in bake-off:**
- Sarvam (saaras:v3) — native Hinglish, batch API, diarization
- ElevenLabs (scribe_v2) — auto code-switch, keyterms param for drug names
- Google (chirp_2) — NO keyterm boost wired (intentional asymmetry for memo)

**Top metric:** Medical-term accuracy (drug name + dose). Wrong dose = hard FAIL.

**Key design decision:** Record one WAV, batch-transcribe — NOT streaming. Engines return spoken Hinglish, NOT English. English happens in the LLM step only.

**Why:** Batch ensures identical input per engine (fair comparison). Keeping ASR output raw separates ASR errors from LLM extraction errors.

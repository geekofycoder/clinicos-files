# ClinicOS Scribe — Project Context

## Setup

```bash
# macOS dependencies (once)
brew install portaudio libsndfile

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
```

---

## What this project is

A two-phase AI scribe for clinic consultations.

**Phase 1 (built):** STT bake-off — record one consult audio and transcribe it with multiple engines side-by-side to find the best one.

**Phase 2 (built):** Live autocomplete — while the doctor is consulting, stream the audio in 15-second chunks, transcribe each chunk, and incrementally extract 3 clinical fields (chief complaints, diagnoses, advice) via LLM. Results push to a browser UI in real time.

---

## Directory map

```
record.py               Mic → WAV recorder (press Enter to stop, or fixed --seconds)
transcribe_all.py       Batch bake-off: runs all STT engines on a WAV, saves transcripts
pipeline.py             End-to-end: record → transcribe (Sarvam + ElevenLabs) → LLM extract → JSON

stt/
  base.py               STTEngine abstract base + TranscriptResult dataclass
  sarvam_engine.py      Sarvam Saaras v3 via batch job API (handles >30s natively, diarization)
  elevenlabs_engine.py  ElevenLabs Scribe v2
  google_engine.py      Google Chirp 2 (chunked for >55s audio)

llm/
  schema.py             Pydantic models: Prescription, Complaint, Diagnosis, Medication, etc.
  extractor.py          One-shot full-transcript → Prescription (used by pipeline.py)

live/
  app.py                FastAPI backend: /start, /stop, /stream (SSE)
  recorder.py           ChunkedRecorder — 15s audio chunks → fires on_chunk callback
  incremental.py        Claude call: (previous state + new chunk) → updated 3 fields
  static/index.html     Browser UI: record button + 3 panels (complaints, diagnoses, advice)

recordings/             WAV files from record.py / pipeline.py
transcripts/            Plain + diarized TXT files per engine per consult
results/                JSON output from pipeline.py (sarvam_result.json, elevenlabs_result.json)
```

---

## Live pipeline — how it works

```
[mic] → ChunkedRecorder (15s chunks)
  → each chunk → Sarvam sync STT → chunk text
  → incremental_extract(chunk_text, previous_state) via Claude
  → updated {chief_complaints, diagnoses, advice}
  → pushed via SSE → browser panels update automatically
```

Key design choice: **incremental extraction (Strategy C)**. Claude only sees the new 15s of speech + the previous extraction — not the full transcript from scratch. This keeps prompt size and cost small. Each call updates/appends; it never overwrites unless the doctor corrected something.

Each chunk prints to terminal:
```
[STT] chunk: <first 120 chars of transcript>...
[LLM] {'chief_complaints': [...], 'diagnoses': [...], 'advice': '...'}
```

---

## Key design decisions

**Language code in STT**
- Bake-off (`sarvam_engine.py`): defaults `language="hi-IN"` — controlled test, known language, more accurate scoring. `language="auto"` maps to `"unknown"` for Sarvam.
- Live (`app.py`): hardcoded `language_code="unknown"` — real consult, unpredictable code-switching, auto-detect is safer.

**Diarization**
- Bake-off: `with_diarization=True, num_speakers=2` — speaker turns saved for scoring.
- Live: no diarization — only text content matters for extraction, diarization adds latency.

**Two separate transcription paths**
- Chunked live buffer: drives the autocomplete during the consult (up to 15s stale, good enough).
- Full-file batch pass: used for scoring in the bake-off (clean, no seam errors).

**Incremental vs on-demand extraction**
- Chosen: background incremental (every 15s chunk), not on-click-lazy. SSE pushes updates automatically.
- Doctor edits in the UI are local (stored in JS `store` object) and survive SSE updates — the next extraction won't clobber manual edits to existing items (new items are appended, not overwritten).

**LLM prompt safety**
- `incremental.py` instructs Claude to only extract what was explicitly said — never hallucinate. Diagnosis and advice fields must stay empty if not discussed.

---

## Data models (llm/schema.py)

| Model | Fields |
|---|---|
| `Complaint` | text, entry_type, code |
| `Diagnosis` | text, entry_type, code |
| `Medication` | text, entry_type, dosage (Dosage sub-model) |
| `Dosage` | frequency_code (OD/BD/TDS…), dose_pattern, timing, duration_days, route |
| `Investigation` | text, entry_type, is_panel, fasting_required |
| `FollowUp` | date, reason |
| `VaccineItem` | vaccine, flagged, eligibility_note |
| `Prescription` | vitals + all above lists + advice |

Live pipeline uses `PartialPrescription` (only chief_complaints, diagnoses, advice) to keep prompts small.

---

## Running

```bash
source .venv/bin/activate

# Record a consult (press Enter to stop)
python record.py --name consult_01

# Bake-off (transcribe with all configured engines)
python transcribe_all.py recordings/consult_01.wav

# Full pipeline (record → transcribe → LLM extract → JSON)
python pipeline.py --name consult_01
python pipeline.py --name consult_01 --wav recordings/consult_01.wav  # skip recording

# Live autocomplete server → http://localhost:8000
uvicorn live.app:app --reload
```

---

## Environment variables (.env)

| Key | Used by |
|---|---|
| `SARVAM_API_KEY` | sarvam_engine.py, live/app.py |
| `ELEVENLABS_API_KEY` | elevenlabs_engine.py |
| `GOOGLE_APPLICATION_CREDENTIALS` | google_engine.py |
| `ANTHROPIC_API_KEY` | llm/extractor.py, live/incremental.py |

---

## STT engine comparison

| Engine | Model | Long audio | Keyterm boost | Hinglish | Diarization |
|---|---|---|---|---|---|
| Sarvam | saaras:v3 (batch job) | native to 1h | `prompt` field | native codemix | yes |
| ElevenLabs | scribe_v2 | native | `keyterms` (up to 100) | auto-detect | yes |
| Google | chirp_2 | chunked >55s | not wired | varies | no |

Drug keyterms list lives in `pipeline.py` and `transcribe_all.py` (`DRUG_KEYTERMS`).

---

## What's next / open questions

- Scoring sheet: WER comparison of each engine transcript vs. hand-written reference
- Doctor's manual edits in the UI — should a later re-extraction respect or overwrite them? (Currently: UI edits are local, SSE pushes can only append new items)
- Upgrading to Strategy C's true incremental transcription vs. current chunk-and-replace
- Adding Deepgram Nova-3 or Soniox as a fourth engine

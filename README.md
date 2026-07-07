# ClinicOS Scribe

An AI scribe for clinic consultations, built in two phases.

**Phase 1 — STT bake-off.** Record one consult, run the identical audio through
several hosted ASR engines (Sarvam, ElevenLabs, Google), and lay the
transcripts side by side so they can be scored. Each engine returns the
transcript in whatever language was actually spoken (Hinglish kept as spoken,
not pre-translated) — keeping ASR and translation/extraction separate is what
lets you later pin a wrong prescription on the ASR or the LLM specifically,
instead of guessing.

**Phase 2 — live autocomplete.** While the doctor is talking, the mic streams
in 15-second chunks. Each chunk gets transcribed, then Claude folds it into
three running fields — chief complaints, diagnoses, advice — and the update
pushes to a browser UI over SSE. Claude only ever sees the new chunk plus its
own last output, not the transcript from scratch, so the prompt stays small
and cheap no matter how long the consult runs. It's instructed to extract only
what was explicitly said; diagnosis and advice stay empty until they're
actually discussed, and a doctor's manual edits in the UI survive later
updates (new extractions append, they don't clobber).

## Why record-then-batch for phase 1, not live

The bake-off's whole point is comparing *models*, so every engine has to see
the same audio — a recorded WAV is the one controlled, replayable input that
makes that a fair fight. Batch transcription also lets each engine use
right-context it wouldn't get while streaming, so slower/non-streaming models
aren't penalized for something orthogonal to transcription quality. You have
to record the consult anyway to write the reference answer key, so the WAV
exists regardless of how it's transcribed.

## Layout

```
record.py               mic -> WAV (press Enter to stop, or fixed --seconds)
transcribe_all.py       WAV -> Sarvam | ElevenLabs | Google, transcripts saved side by side
pipeline.py             record -> transcribe (Sarvam + ElevenLabs) -> LLM extract -> JSON

stt/                    one class per engine behind a common STTEngine interface
llm/                    schema.py (Prescription/Complaint/Diagnosis/Medication/... pydantic models)
                        extractor.py (one-shot full transcript -> Prescription, used by pipeline.py)
live/                   app.py        FastAPI backend: /start, /stop, /stream (SSE)
                        recorder.py   ChunkedRecorder — 15s chunks, fires on_chunk callback
                        incremental.py  Claude call: (prior state + new chunk) -> updated 3 fields
                        static/index.html  record button + 3 live panels
transcripts/            plain + diarized txt, one per engine per consult
results/                JSON output from pipeline.py
```

## Setup

Requires Python 3.10+ and PortAudio (for mic capture):

- macOS: `brew install portaudio libsndfile`
- Ubuntu/Debian: `sudo apt-get install libportaudio2 libsndfile1`

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in keys for whichever engines you want to test
```

You only need credentials for the engines you intend to run — each is skipped
if its key is missing. `GOOGLE_APPLICATION_CREDENTIALS` points at a service
account JSON file (not checked in).

## Running

```bash
# Bake-off: record a consult, then transcribe it with every configured engine
python record.py --name consult_01
python transcribe_all.py recordings/consult_01.wav

# Full pipeline: record -> transcribe -> LLM extract -> prescription JSON
python pipeline.py --name consult_01
python pipeline.py --name consult_01 --wav recordings/consult_01.wav   # skip recording

# Live autocomplete server
uvicorn live.app:app --reload   # http://localhost:8000
```

Drug names and dosage units to bias the ASR live in `DRUG_KEYTERMS` at the top
of `transcribe_all.py` / `pipeline.py` — edit to match what your consults
actually say.

## Engines and their quirks

| Engine | Model | Long audio | Keyterm boost | Hinglish | Diarization |
|---|---|---|---|---|---|
| Sarvam | `saaras:v3` (batch job) | native, to 1h | best-effort `prompt` | native code-mix | yes |
| ElevenLabs | `scribe_v2` | native | `keyterms` (up to 100) | auto-detect + switch | yes |
| Google | `chirp_2` | chunked >55s | not wired by default | varies, test it | no |

## Key design decisions

- **Language code**: bake-off defaults `language="hi-IN"` (controlled test,
  known language, more accurate scoring); live hardcodes
  `language_code="unknown"` (real consult, code-switching is unpredictable,
  auto-detect is safer).
- **Diarization**: on for the bake-off (needed to score speaker turns), off
  for live (only the text matters for extraction, and diarization adds
  latency).
- **Two transcription paths**: the chunked live buffer drives autocomplete
  during the consult (up to 15s stale, good enough); a full-file batch pass
  is what actually gets scored (clean, no seam errors between chunks).

## Adding a fourth engine

Subclass `STTEngine` in `stt/`, implement `transcribe()` returning a
`TranscriptResult`, register it in `build_engines()` in `transcribe_all.py`.
Deepgram Nova-3 and Soniox are the obvious next candidates.

## Open questions

- Scoring sheet: WER of each engine's transcript against a hand-written
  reference, plus code-switch survival and drug/dose accuracy.
- Whether a later re-extraction should ever be allowed to overwrite a
  doctor's manual edit, not just append around it.
- True incremental transcription (Strategy C) vs. the current chunk-and-replace.

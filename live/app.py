"""
app.py — FastAPI backend for live autocomplete.

Routes:
  GET  /        → serves index.html
  POST /start   → starts chunked recording + processing
  POST /stop    → stops recording
  GET  /stream  → SSE stream of extraction updates
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sarvamai import SarvamAI
from sse_starlette.sse import EventSourceResponse

load_dotenv(Path(__file__).parent.parent / ".env")

from .incremental import incremental_extract
from .recorder import ChunkedRecorder

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

_sarvam = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

_state: dict = {"chief_complaints": [], "diagnoses": [], "advice": None}
_update_queue: asyncio.Queue = asyncio.Queue()
_recorder: ChunkedRecorder | None = None
_loop: asyncio.AbstractEventLoop | None = None


def _on_chunk(wav_path: str) -> None:
    # 1. Transcribe via Sarvam sync API
    try:
        with open(wav_path, "rb") as f:
            result = _sarvam.speech_to_text.transcribe(
                file=f,
                model="saaras:v3",
                mode="codemix",
                language_code="unknown",
            )
        chunk_text = result.transcript or ""
    except Exception as e:
        print(f"[STT] error: {e}")
        return
    finally:
        Path(wav_path).unlink(missing_ok=True)

    if not chunk_text.strip():
        return

    print(f"[STT] chunk: {chunk_text[:120]}...")

    # 2. Incremental LLM extraction
    try:
        updated = incremental_extract(chunk_text, _state)
    except Exception as e:
        print(f"[LLM] error: {e}")
        return

    print(f"[LLM] {updated}")

    # 3. Update shared state and push to SSE
    _state.update(updated)
    if _loop:
        asyncio.run_coroutine_threadsafe(_update_queue.put(dict(_state)), _loop)


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text())


@app.post("/start")
async def start():
    global _recorder, _state, _loop
    _loop = asyncio.get_event_loop()
    _state = {"chief_complaints": [], "diagnoses": [], "advice": None}
    _recorder = ChunkedRecorder(on_chunk=_on_chunk)
    _recorder.start()
    return {"status": "recording"}


@app.post("/stop")
async def stop():
    global _recorder
    if _recorder:
        _recorder.stop()
        _recorder = None
    return {"status": "stopped"}


@app.get("/stream")
async def stream():
    async def generator():
        while True:
            data = await _update_queue.get()
            yield {"data": json.dumps(data)}
    return EventSourceResponse(generator())

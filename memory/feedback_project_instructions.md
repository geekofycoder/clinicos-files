---
name: feedback-project-instructions
description: Hard rules from the ClinicOS Scribe brief — things Claude must not change
metadata:
  type: feedback
---

Do NOT switch design to live/streaming transcription for the bake-off. Record-then-batch is intentional.

**Why:** Bake-off compares models — every engine must process byte-for-byte identical audio. Streaming commits without right-context and scores lower. Reproducibility matters over real-time.

**How to apply:** If user asks about streaming, explain the design choice and redirect. Do not add streaming paths.

---

Do NOT make engines output English directly (no Sarvam translate mode in the bake-off path). Keep transcripts in spoken Hinglish; English rendering happens in the LLM step only.

**Why:** Separates ASR error from translation/extraction error. The brief explicitly requires attributing errors to ASR vs LLM.

**How to apply:** Never set Sarvam mode to 'translate' in the transcription path.

---

Preserve the common STTEngine interface. New engines must be subclasses returning TranscriptResult.

Keep ASR scoring and prescription scoring separate.

Treat medical-term (drug + dose) accuracy as the top metric; a wrong dose is a hard fail.

When building the LLM step: ask for / use the ClinicOS prescription schema; output must be English JSON.

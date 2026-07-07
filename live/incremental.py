"""
incremental.py — Strategy C LLM extraction.

Given a new transcript chunk and the previous extraction state,
returns updated chief_complaints, diagnoses, and advice.
Only these three fields are extracted (not the full Prescription)
to keep prompts small and responses fast.
"""

import json
import os
from typing import Optional

import anthropic
from pydantic import BaseModel

from llm.schema import Complaint, Diagnosis


class PartialPrescription(BaseModel):
    chief_complaints: list[Complaint]
    diagnoses: list[Diagnosis]
    advice: Optional[str] = None


_SYSTEM = (
    "You are updating a clinical extraction incrementally. "
    "You receive a previous extraction and a new transcript chunk.\n"
    "Rules:\n"
    "- Add new complaints or diagnoses not already present\n"
    "- Correct or remove if the doctor explicitly corrected something\n"
    "- Update advice only if new advice was given in the chunk\n"
    "- If no new info for a field, return it unchanged\n"
    "- Only extract what was explicitly said — never hallucinate\n"
    "- Output English only"
)


def incremental_extract(new_chunk: str, previous: dict, api_key: str | None = None) -> dict:
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    user_msg = (
        f"Previous extraction:\n{json.dumps(previous, indent=2)}\n\n"
        f"New transcript chunk:\n{new_chunk}\n\n"
        "Return updated chief_complaints, diagnoses, and advice."
    )
    response = client.messages.parse(
        model="claude-opus-4-7",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        output_format=PartialPrescription,
    )
    return response.parsed_output.model_dump()

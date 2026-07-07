import os

import anthropic

from .schema import Prescription


def extract(transcript: str, api_key: str | None = None) -> Prescription:
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.parse(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=(
            "Extract structured clinical information from the doctor-patient transcript. "
            "Use null for anything not mentioned. Output English only."
        ),
        messages=[{"role": "user", "content": f"Transcript:\n\n{transcript}"}],
        output_format=Prescription,
    )
    return response.parsed_output

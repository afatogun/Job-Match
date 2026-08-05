"""Thin wrapper over the OpenAI SDK.

Everything AI-facing goes through here so there is exactly one place that knows
about API keys, models and structured-output plumbing.
"""

import json
import logging
from typing import TypeVar

from pydantic import BaseModel

from .config import get_openai_key

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class MissingAPIKey(RuntimeError):
    pass


def get_client():
    from openai import OpenAI

    key = get_openai_key()
    if not key:
        raise MissingAPIKey(
            "No OpenAI API key configured. Add one in Settings, or set OPENAI_API_KEY in .env"
        )
    return OpenAI(api_key=key)


def complete_structured(
    *,
    model: str,
    system: str,
    user: str,
    schema_model: type[T],
    max_tokens: int = 8000,
) -> T:
    """One chat completion constrained to schema_model, parsed and validated.

    Uses the SDK's parse helper so the model cannot return malformed JSON.
    """
    client = get_client()
    try:
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=schema_model,
            max_completion_tokens=max_tokens,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Model returned no parsable content")
        return parsed
    except Exception as exc:
        # Older/cheaper models may not support the parse helper; fall back to
        # plain JSON mode and validate ourselves.
        if "response_format" not in str(exc) and "json_schema" not in str(exc):
            raise
        log.info("Structured parse unsupported for %s, falling back to JSON mode", model)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"{system}\n\nRespond with JSON only."},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=max_tokens,
        )
        content = completion.choices[0].message.content or "{}"
        return schema_model.model_validate(json.loads(content))


def complete_text(*, model: str, system: str, user: str, max_tokens: int = 4000) -> str:
    client = get_client()
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_completion_tokens=max_tokens,
    )
    return (completion.choices[0].message.content or "").strip()

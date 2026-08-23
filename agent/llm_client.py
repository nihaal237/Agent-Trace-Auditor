"""
LLM client - talks to Groq's API (OpenAI-compatible endpoint, free tier).

Requires the GROQ_API_KEY environment variable to be set.
"""

import os
from openai import OpenAI

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY environment variable not set. "
                "PowerShell: $env:GROQ_API_KEY = 'gsk_...'"
            )
        _client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    return _client


def query_llm(system_prompt: str, user_prompt: str,
              model: str = "openai/gpt-oss-20b", temperature: float = 0.2) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content
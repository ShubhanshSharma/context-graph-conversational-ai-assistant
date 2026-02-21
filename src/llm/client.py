# Wrapper around API.

# One function:

# generate(prompt)


# src/llm/client.py

import os
from openai import OpenAI


MODEL = "llama-3.3-70b-versatile"  # good default on Groq


def generate(prompt: str) -> str:
    """
    Send prompt to Groq.
    Falls back to mock if API key missing.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print("⚠️ No GROQ_API_KEY found -> using mock LLM")
        return mock_generate(prompt)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        return resp.choices[0].message.content.strip()

    except Exception as e:
        print(f"Groq error: {e}")
        print("⚠️ Falling back to mock LLM")
        return mock_generate(prompt)


def mock_generate(prompt: str) -> str:
    """
    Deterministic backup.
    Guarantees demo always works.
    """

    if "extension (approved)" in prompt:
        return "Yes. Your extension is approved, so you can submit within the extended time window. [Decision:dec1]"

    if "deadline_help" in prompt:
        return "The deadline is active. You may need to request an extension. [Deadline:d1]"

    return "I need more information."

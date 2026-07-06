"""
Optional AI stretch goal: summarize/tag a /report's text using Groq's
free-tier API (no credit card). If GROQ_API_KEY isn't set, this quietly
does nothing and the rest of the app works exactly the same without it.
"""
import logging
import os

import requests

logger = logging.getLogger("bot")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def summarize_text(text: str) -> str | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not text:
        return None

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Summarize the user's report in under 15 words, plain text. "
                            "Then add ' | urgency: low' or 'medium' or 'high' based on tone."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                "max_tokens": 60,
                "temperature": 0.2,
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.exception("AI summarize call failed - continuing without it")
        return None

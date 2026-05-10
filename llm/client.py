import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "https://devops-incident-analyzer.local",
                "X-Title": "DevOps Incident Analyzer",
            },
        )
    return _client


def get_model() -> str:
    return os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")


def get_reviewer_model() -> str:
    model = os.getenv("REVIEWER_MODEL", "google/gemini-flash-latest")
    print(model)
    return model


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


def chat(messages: list[dict], json_mode: bool = False, model: str | None = None) -> str:
    client = _get_client()
    kwargs: dict = {"model": model or get_model(), "messages": messages}
    print(kwargs)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def chat_json(messages: list[dict], model: str | None = None) -> dict:
    """Send messages and parse response as JSON. Retries once with a correction prompt."""
    last_raw = ""
    print(model)
    for attempt in range(2):
        try:
            raw = chat(messages, json_mode=True, model=model)
            last_raw = raw
            return json.loads(_extract_json(raw))
        except Exception:
            if attempt == 1:
                raise RuntimeError(
                    f"JSON parse failed after 2 attempts. Last response:\n{last_raw}"
                )
            messages = messages + [
                {"role": "assistant", "content": last_raw},
                {"role": "user", "content": "Your response was not valid JSON. Return only a raw JSON object with no prose or markdown."},
            ]
    return {}

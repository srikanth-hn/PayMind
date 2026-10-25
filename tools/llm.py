import json
import os
import re

from langchain_openai import ChatOpenAI


def get_api_key() -> str | None:
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip().strip('"').strip("'")
    return key or None


def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    """OpenAI-compatible client. Defaults to OpenRouter; change the env vars to switch provider."""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to your .env file.")
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=temperature,
        timeout=30,
        max_retries=1,
    )


def ask(system: str, user: str, temperature: float = 0.2) -> str:
    response = get_llm(temperature).invoke([("system", system), ("human", user)])
    return str(response.content).strip()


def ask_json(system: str, user: str) -> dict:
    """Ask for a JSON object and parse it, tolerating code fences around it."""
    text = ask(system + "\nRespond with one JSON object only, no other text.", user, temperature=0)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"The model did not return JSON: {text[:200]}")
    return json.loads(match.group(0))
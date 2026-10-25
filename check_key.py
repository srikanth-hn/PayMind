"""Run `python check_key.py` to test your OpenRouter key outside the app."""
import os

from dotenv import load_dotenv

load_dotenv(override=True)
from tools.llm import ask, get_api_key  # noqa: E402

key = get_api_key()
if not key:
    print("❌ OPENROUTER_API_KEY not found. Is .env in this folder?")
else:
    print(f"Key found: starts with {key[:10]}…, length {len(key)} (OpenRouter keys start with sk-or-v1-)")
    print(f"Model: {os.getenv('LLM_MODEL', 'openai/gpt-4o-mini')}")
    try:
        print("✅ Model replied:", ask("Reply with one word.", "Say OK"))
    except Exception as error:
        print("❌ Call failed:", error)
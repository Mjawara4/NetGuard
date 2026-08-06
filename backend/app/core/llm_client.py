import logging
import os
import re

import openai

logger = logging.getLogger(__name__)


def _clean_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _api_key_for(provider: str) -> str | None:
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "kimi":
        return os.getenv("KIMI_API_KEY")
    return None


def chat_completion(prompt: str, response_format: str | None = None) -> str | None:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    api_key = _api_key_for(provider)

    if not api_key:
        logger.warning(f"No API key configured for LLM provider: {provider}")
        return None

    try:
        if provider == "gemini":
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            return _clean_response(response.text)

        if provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            kwargs = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
            }
            if response_format == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            completion = client.chat.completions.create(**kwargs)
            return _clean_response(completion.choices[0].message.content)

        if provider == "kimi":
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.moonshot.ai/v1",
            )
            kwargs = {
                "model": "kimi-k2.5",
                "messages": [{"role": "user", "content": prompt}],
            }
            if response_format == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            completion = client.chat.completions.create(**kwargs)
            return _clean_response(completion.choices[0].message.content)

        logger.error(f"Unknown LLM provider: {provider}")
        return None

    except Exception as e:
        logger.error(f"LLM chat completion failed for provider {provider}: {e}")
        return None

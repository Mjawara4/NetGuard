import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from app.core import llm_client


def test_chat_completion_returns_none_for_unknown_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}, clear=True):
        result = llm_client.chat_completion("hello")
        assert result is None


def test_chat_completion_returns_none_when_key_missing():
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "kimi", "KIMI_API_KEY": ""},
        clear=True,
    ):
        result = llm_client.chat_completion("hello")
        assert result is None


def test_clean_response_strips_json_fences():
    raw = "```json\n{\"foo\": \"bar\"}\n```"
    cleaned = llm_client._clean_response(raw)
    assert cleaned == '{"foo": "bar"}'


def test_clean_response_strips_plain_fences():
    raw = "```\nhello world\n```"
    cleaned = llm_client._clean_response(raw)
    assert cleaned == "hello world"


if __name__ == "__main__":
    test_chat_completion_returns_none_for_unknown_provider()
    test_chat_completion_returns_none_when_key_missing()
    test_clean_response_strips_json_fences()
    test_clean_response_strips_plain_fences()
    print("All llm_client tests passed")

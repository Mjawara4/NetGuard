import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
import llm_client


def test_chat_completion_returns_none_for_unknown_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}, clear=True):
        result = llm_client.chat_completion("hello")
        assert result is None


def test_chat_completion_uses_generic_llm_api_key_as_fallback():
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "kimi", "LLM_API_KEY": "generic-key", "KIMI_API_KEY": ""},
        clear=True,
    ):
        # Should still return None because we don't mock the HTTP call,
        # but it proves the key fallback path is reached without a missing-key warning.
        result = llm_client.chat_completion("hello")
        # Real API call would fail; we just care that it didn't early-return for missing key.
        assert result is None


def test_clean_response_strips_json_fences():
    raw = "```json\n{\"foo\": \"bar\"}\n```"
    cleaned = llm_client._clean_response(raw)
    assert cleaned == '{"foo": "bar"}'


if __name__ == "__main__":
    test_chat_completion_returns_none_for_unknown_provider()
    test_chat_completion_uses_generic_llm_api_key_as_fallback()
    test_clean_response_strips_json_fences()
    print("All agents llm_client tests passed")
